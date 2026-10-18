"""The hydra's paint (2026-10-17), after the dragon's finished paint (dragon_paint, its machinery reused): smart
projected UVs, per-texel fields baked once (position, normal, part, AO), colour presets painted over them in numpy,
one normal map from a height field (scales, belly plates with anti-aliased edges, fin rays).

What differs from the dragon:
- four axes instead of one spine: the trunk and the three necks. Each texel takes its coordinates (place along,
  section, plate phase) from the axis it lies nearest to; the belly's share blends over the axes (the vertex
  colours' lesson: the nearest axis alone flipped at the necks' roots);
- the heads are the dragon's, so each head's texels get the dragon's head treatment in the dragon's head space
  (hydra_skin.to_head / SCALE): eye rings, the nostrils' scale ring, the lips' shade, the jaw's plates;
- aquatic: smaller scales, sparse dark spots along the back and flanks, a wetter shine, and fins (HydraFins: gill
  fans, toe webs, the tail's fin and keel) painted like the dragon's wing membranes -- rays, thin toward the edge,
  a coral edge.
Presets: 'sea' (the blockout's sea green), 'swamp' and 'abyss' (mine).
"""
import bpy, math, os
import numpy as np

import beast_paint as BP
import dragon_paint as DP
import dragon_head as DH
import hydra_body as HB
import hydra_head as HH
import hydra_skin as HS
from beast_common import smoothstep, fbm, hexc, _hash3
from dragon_paint import _c, _mix, _f32

SIZE, FIN_SIZE = 4096, 2048
RELIEF, RELIEF_FIN = 5.0, 3.0
PART = HS.PART
S = HH.SCALE

PRESETS = {
    "sea": dict(back="1f4a44", back_dark="12302c", flank="2c6a5c", scale_hi="3f8070", crevice="0a1c1a",
                belly="c9c08a", belly_hi="e0d8a8", belly_edge="7a7448", spot="0d2420", claw="1c1c18",
                tooth="e8e2cc", tooth_root="b0a682", mouth="5a2a2a", tongue="8a4a44", eye="e8d040",
                eye_dark="8a7010", eye_glow="fff0a0", fin="2f6e66", fin_thin="4a9a88", fin_edge="c06a58",
                fin_ray="173e38"),
    "swamp": dict(back="45452a", back_dark="2a2a18", flank="5a5a30", scale_hi="78784a", crevice="14140a",
                  belly="b8a878", belly_hi="d0c498", belly_edge="6a5e3a", spot="22220f", claw="1c1a14",
                  tooth="e2dac0", tooth_root="a89a70", mouth="5a2e24", tongue="844a3c", eye="ffb020",
                  eye_dark="9a5a08", eye_glow="ffe2a0", fin="5e6230", fin_thin="8a8e4a", fin_edge="b0603a",
                  fin_ray="303218"),
    "abyss": dict(back="1a2438", back_dark="0c1220", flank="243858", scale_hi="38507a", crevice="05080e",
                  belly="8aa0a8", belly_hi="b0c4c8", belly_edge="4a5a66", spot="070b14", claw="101218",
                  tooth="dce4e8", tooth_root="98a4aa", mouth="3a2030", tongue="6a3a50", eye="90f0ff",
                  eye_dark="2a8aa0", eye_glow="e0ffff", fin="1e3a5a", fin_thin="3a6a90", fin_edge="3ab0c0",
                  fin_ray="0e1e34"),
}
SMOOTH = dict(skin=0.44, belly=0.52, mouth=0.62, claw=0.6, tooth=0.68, tongue=0.62, eye=0.93, pupil=0.95, fin=0.5)


# ----------------------------------------------------------------------------------------- axes
def _axis_rows():
    """The trunk's rows and each neck's (x, y, z, a, b, c), and the heads' ids."""
    return [HB.BODY_ROWS] + [HB._neck_rows(n, 3) for n in HB.neck_ids(3)]


def _outside(P, rows, chunk=40000):
    """Distance from each point to the nearest of an axis's sections (outside it, roughly)."""
    from beast_common import spline
    R = spline(rows, 6)
    C, r = R[:, :3], np.minimum(R[:, 3], R[:, 5])
    out = np.empty(len(P))
    for k in range(0, len(P), chunk):
        D2 = ((P[k:k + chunk, None, :] - C[None]) ** 2).sum(-1)
        i = np.argmin(D2, axis=1)
        out[k:k + chunk] = np.sqrt(D2[np.arange(len(i)), i]) - r[i]
    return out


LIMB_SEGS = (("FRONT", "sho", "elb", 0.30, 0.12), ("FRONT", "elb", "wri", 0.22, 0.0), ("FRONT", "wri", "paw", 0.18, 0.0),
             ("HIND", "hip", "knee", 0.34, 0.15), ("HIND", "knee", "hock", 0.22, 0.0), ("HIND", "hock", "paw", 0.18, 0.0))


def limb_weight(P):
    """How much a point belongs to a leg: near a leg bone (its radius plus a 10 cm fade), past the first stretch of
    the upper bones (their joints sit at the body's side; the belly between the legs stays the belly's). Daniel: "We
    have the same issue as the belly texture bleeding into the members" -- the dragon's gold once lit up its knee."""
    w = np.zeros(len(P))
    for s_ in (1, -1):
        for limb, a, b, r, t0 in LIMB_SEGS:
            L = getattr(HB, limb)
            A, B = np.array(DB_m(L[a], s_)), np.array(DB_m(L[b], s_))
            d = B - A
            t = np.clip(((P - A) @ d) / (d @ d), 0, 1)
            dist = np.linalg.norm(P - (A + t[:, None] * d), axis=1)
            w = np.maximum(w, smoothstep(r + 0.10, r, dist) * smoothstep(t0, t0 + 0.12, t))
    return w


# ----------------------------------------------------------------------------------------- body fields
def body_fields(D):
    """Everything the painter needs that doesn't depend on the colours (computed once for all presets)."""
    valid = D["valid"]
    idx = np.nonzero(valid.ravel())[0]
    P = D["P"].reshape(-1, 3)[idx].astype(np.float32)
    N = D["N"].reshape(-1, 3)[idx].astype(np.float32)
    part = D["part"].ravel()[idx]
    ao = _f32(D["ao"].ravel()[idx])
    n = len(P)
    F = dict(idx=idx, P=P, part=part, ao=ao, shape=valid.shape)
    skin = (part == PART["skin"]) | (part == PART["mouth"])
    z = P[:, 2]

    # which head each texel belongs to (its side of that neck's seam, near the head), and its dragon head space
    nids = list(HB.neck_ids(3))
    score = np.full((len(nids), n), np.inf)                      # the nearest head whose side of its seam it is on
    for h, nid in enumerate(nids):
        dist = np.linalg.norm(P - np.array(HS._M(nid).translation), axis=1)
        score[h] = np.where((HS.cut_side(nid, P) < 0) & (dist < 1.7), dist, np.inf)
    head_of = np.where(np.isfinite(score.min(0)), np.argmin(score, axis=0), -1)
    headside = head_of >= 0
    Pd = np.zeros((n, 3), np.float32)
    for h, nid in enumerate(nids):
        sel = head_of == h
        Pd[sel] = HS.to_head(nid, P[sel]) / S
    Pm = Pd.copy()
    Pm[:, 0] = np.abs(Pm[:, 0])

    # the axes: weights by nearness, each axis's coordinates where it matters
    rows = _axis_rows()
    body = ~headside
    O = np.stack([_outside(P, r) for r in rows])                 # (axes, n)
    W = np.exp(-((O - O.min(0)) / 0.12) ** 2) * body[None]
    dom = np.argmax(np.where(body[None], -O, -1e9), axis=0)
    kb = np.zeros(n, np.float32)
    wsum = np.zeros(n, np.float32)
    phase = np.zeros(n)
    pitch = np.full(n, 0.1, np.float32)
    flow = np.zeros((n, 3), np.float32)
    e = np.zeros(n, np.float32)
    vb = np.zeros(n, np.float32)
    size = np.full(n, 0.04, np.float32)
    for a, r in enumerate(rows):
        sel = np.nonzero(W[a] > 0.02)[0]
        if not len(sel):
            continue
        sp = DP._spine(P[sel], rows=r)
        lim = 1.35 if a == 0 else 1.6                            # tight along the trunk (the dragon's lesson)
        ka = smoothstep(0.30, 0.62, sp["ventral"]) * smoothstep(lim, lim - 0.3, sp["e"])
        kb[sel] += W[a, sel] * ka
        wsum[sel] += W[a, sel]
        d = sel[dom[sel] == a]                                   # the dominant axis's own coordinates
        m = dom[sel] == a
        phase[d] = sp["phase"][m] + 1000.0 * a                   # (each axis its own run of plates)
        pitch[d] = sp["pitch"][m]
        flow[d] = sp["T"][m]
        e[d] = sp["e"][m]
        vb[d] = sp["v"][m] / np.maximum(sp["b"][m], 1e-3)
        size[d] = np.clip(0.055 * np.sqrt(np.maximum(sp["a"][m], (sp["b"][m] + sp["c"][m]) / 2) / 0.5), 0.032, 0.065)
    kb = np.where(wsum > 0, kb / np.maximum(wsum, 1e-6), 0.0)

    # legs: scales smaller and pointing down, finer toward the toes; heads: smaller, pointing back along the head
    w_limb = np.maximum(smoothstep(1.35, 1.75, e) * (z < 1.3), limb_weight(P.astype(np.float64))) * body
    flow = flow * (1 - w_limb[:, None]) + np.array((0, 0, -1.0)) * w_limb[:, None]
    limb = 0.034 * (1 - smoothstep(0.30, 0.16, z) * 0.40)
    size = size * (1 - w_limb) + limb * w_limb
    brow = np.linalg.norm((Pm - np.array((0.24, -0.45, 0.24))) / np.array((0.12, 0.30, 0.10)), axis=1) < 1
    for h, nid in enumerate(nids):
        sel = head_of == h
        back_dir = np.array(HS._M(nid).to_3x3().col[1][:])
        flow[sel] = back_dir
        size[sel] = np.where(brow[sel], 0.032, 0.021)
    flow = _f32(DP._tangent(flow, N))
    h_sc, crev, hi, tint = (np.zeros(n, np.float32) for _ in range(4))
    crev[:] = 1
    sel = np.nonzero(skin)[0]
    hs_, cr, hh, ti = DP.scales(P[sel], flow[sel], size[sel])
    h_sc[sel], crev[sel], hi[sel], tint[sel] = hs_, cr, hh, ti

    # the belly plates (trunk, necks; across the jaws' undersides on the heads)
    k_belly = _f32(np.where(skin, kb * (1 - w_limb), 0.0))
    # the breast where the necks part faces forward and is belly. No axis owned it -- it lies in front of the
    # trunk's first section and on the necks' inner sides -- so it came out as an X of back scales (Daniel: "fix that
    # chest area where scales show up but should be a belly texture"). Picked by the baked normal and position.
    breast = smoothstep(-0.15, -0.45, N[:, 1]) * smoothstep(-1.05, -1.45, P[:, 1]) * smoothstep(2.75, 2.35, z) *         smoothstep(1.0, 0.7, np.abs(P[:, 0])) * body * skin * (1 - w_limb)
    k_belly = np.maximum(k_belly, breast).astype(np.float32)
    # where two axes' plates meet (the necks' roots on the chest) their runs don't line up: the edge between them
    # stepped into a dashed line. Fade the plates' relief and grooves out there.
    Ws = np.sort(W, axis=0)
    second = np.where(body, Ws[-2] / np.maximum(Ws[-1], 1e-6), 0.0)
    pfade = smoothstep(0.25, 0.65, second)
    frac = phase % 1.0
    pid = np.floor(phase).astype(np.int64)
    we = DP.EDGE / pitch
    plate = smoothstep(0.0, 0.10, frac) * (0.5 + 0.5 * frac) * smoothstep(1.0, 1.0 - we, frac)
    groove = np.maximum(1 - smoothstep(0.0, 0.10, frac), smoothstep(1.0 - we, 1.0, frac))
    plate = plate * (1 - pfade) + 0.75 * pfade
    groove = groove * (1 - pfade)
    y = Pd[:, 1]
    jb = DH.at(DH.JAW, y, 3)
    k_jaw = smoothstep(jb + 0.10, jb + 0.03, Pd[:, 2]) * (Pd[:, 2] < DH.lip(y) - 0.05)
    jfrac = (y / 0.065) % 1.0
    wj = DP.EDGE / (0.065 * float(np.mean(S)))
    k_belly = np.where(headside & skin, k_jaw, k_belly).astype(np.float32)
    plate = np.where(headside, smoothstep(0.0, 0.12, jfrac) * (0.5 + 0.5 * jfrac) * smoothstep(1.0, 1.0 - wj, jfrac),
                     plate)
    groove = np.where(headside, np.maximum(1 - smoothstep(0.0, 0.12, jfrac), smoothstep(1.0 - wj, 1.0, jfrac)), groove)
    frac = np.where(headside, jfrac, frac)
    pid = np.where(headside, np.floor(y / 0.065).astype(np.int64) + 100000 * (head_of + 1), pid)
    mouth = part == PART["mouth"]
    k_belly[mouth] = 0.0
    prand = _f32(_hash3(pid, pid * 7 + 3, np.zeros_like(pid), 41))
    kp = _f32(smoothstep(0.36, 0.46, k_belly + 0.12 * (prand - 0.5)))
    stria = _f32(fbm(P / 0.012, 2, seed=43))
    height = np.where(skin, h_sc * (1 - kp) + (plate + 0.03 * stria) * kp, 0.0).astype(np.float32)
    height[mouth] = 0.15 * fbm(P[mouth] / 0.03, 2, seed=3)

    # a darker saddle down the back, sparse dark spots on the back and flanks, soft mottling
    dorsal = np.where(headside, smoothstep(0.10, 0.30, Pd[:, 2]) * 0.6, smoothstep(0.35, 0.95, vb))
    dorsal = _f32(np.where(skin & (w_limb < 0.5), dorsal, 0.0))
    border, _, rid = DP.voronoi(P.astype(np.float64), 0.24, 77)
    spot = smoothstep(0.30, 0.46, border) * (rid < 0.38) * (1 - smoothstep(0.1, 0.4, k_belly)) * skin * (w_limb < 0.6)
    spot = _f32(spot * (z > 0.25))                               # (not on the feet)
    mottle = _f32(fbm(P / 0.6, 3, seed=31))

    # heads: dark rings round the eyes, along the lips; the nostrils' cavity, lip and ring of small scales
    eu, ev, ew = DH._eye_local(Pm)
    er = _f32(np.sqrt((eu / DH.EYE["A"]) ** 2 + (ev / DH.EYE["B"]) ** 2))
    eye_ring = (smoothstep(1.0, 1.15, er) * smoothstep(1.9, 1.3, er) * (np.abs(ew) < 0.06)).astype(np.float32)
    lipd = np.abs(Pd[:, 2] - DH.lip(Pd[:, 1]))
    lips = _f32(smoothstep(0.045, 0.012, lipd) * (Pd[:, 1] < DH.Y_CORNER + 0.02) * skin * ~mouth)
    shade_head = np.where(headside, np.maximum(eye_ring, lips), 0.0).astype(np.float32)
    hc, hr = np.array(DH.NOSTRIL_HOLE[0]), np.array(DH.NOSTRIL_HOLE[1])
    ax = hc - np.array(DH.NOSTRIL[0])
    ax /= np.linalg.norm(ax)
    e1 = np.cross(ax, (0.0, 0.0, 1.0))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    q = Pm - hc
    rn = np.linalg.norm(q / hr, axis=1)
    phi = np.arctan2(q @ e2, q @ e1)
    R0, R_OUT = 1.45, 2.84
    near = headside & skin & (rn < 3.0)
    sel = np.nonzero(near)[0]
    nos_in = np.zeros(n, np.float32)
    nos_lip = np.zeros(n, np.float32)
    if len(sel):
        border2, along, rid2, _ = DP.ring_cells(phi[sel], rn[sel], r0=R0)
        r_ = rn[sel]
        g = smoothstep(0.0, 0.22, border2) * smoothstep(R0, R0 + 0.10, r_) * smoothstep(R_OUT, R_OUT - 0.10, r_)
        ramp = np.clip(0.5 + along * 1.25, 0, 1)
        ring_h = g * (0.30 + 0.70 * ramp ** 1.4) * (0.85 + 0.15 * rid2)
        lip_h = 0.55 * smoothstep(0.80, 1.12, r_) * smoothstep(R0 + 0.02, R0 - 0.12, r_)
        in_ring = smoothstep(R_OUT + 0.16, R_OUT, r_)
        lip = r_ < R0
        nh = np.maximum(ring_h, lip_h)
        h_sc[sel] = h_sc[sel] * (1 - in_ring) + nh * in_ring
        crev[sel] = np.where(lip, 1.0, crev[sel] * (1 - in_ring) + g * in_ring)
        hi[sel] = np.where(lip, 0.25 * lip_h, hi[sel] * (1 - in_ring) + g * ramp ** 2 * in_ring)
        tint[sel] = np.where(lip, 0.5, tint[sel] * (1 - in_ring) + rid2 * in_ring)
        height[sel] = h_sc[sel]
        nos_in[sel] = smoothstep(1.02, 0.72, r_) * (0.75 + 0.25 * smoothstep(0.7, 0.2, r_))
        nos_lip[sel] = smoothstep(0.80, 1.0, r_) * smoothstep(R0 + 0.02, R0 - 0.08, r_)

    # claws light at the base, dark at the tip; teeth stained toward the gum; tongue papillae; iris fibres
    claw = part == PART["claw"]
    ct = np.full(n, 0.6, np.float32)
    csel = np.nonzero(claw)[0]
    if len(csel):
        segs = []
        for s_ in (1, -1):
            for base, knuckle, tip, r, dd, bone in HS.toes(s_):
                segs.append((tip - dd * 0.02, tip + dd * 0.12))
        _, t, _ = DP._seg_dist(P[csel].astype(np.float64), segs)
        ct[csel] = t
        height[csel] = 0.22 * fbm(P[csel] / 0.02, 2, seed=5)
    tongue = part == PART["tongue"]
    height[tongue] = 0.35 * smoothstep(0.2, 0.8, fbm(P[tongue] / 0.010, 2, seed=8) * 0.5 + 0.5)
    tooth = part == PART["tooth"]
    tooth_t = _f32(np.clip(np.abs(Pd[:, 2] - DH.lip(Pd[:, 1])) / 0.10, 0, 1))
    eye = (part == PART["eye"]) | (part == PART["pupil"])
    eth = np.arctan2(ev, eu)
    fibres = _f32(0.5 + 0.5 * np.sin(eth * 36 + 2.0 * fbm(Pm / 0.03, 2, seed=12)))

    F.update(skin=skin, headside=headside, crev=crev, hi=hi, tint=tint, k_belly=k_belly, kp=kp, groove=_f32(groove),
             frac=_f32(frac), prand=prand, stria=stria, height=height, dorsal=dorsal, spot=spot, mottle=mottle,
             shade_head=shade_head, nos_in=nos_in, nos_lip=nos_lip, claw=claw, ct=ct, eye=eye, er=er,
             fibres=fibres, pupil=part == PART["pupil"], tongue=tongue, tooth=tooth, tooth_t=tooth_t, mouth=mouth,
             w_limb=_f32(w_limb))
    return F


def paint_body(F, preset):
    """-> (colour (H, W, 3), smoothness (H, W), height (H, W))"""
    C = {k: _c(v) for k, v in preset.items()}
    n = len(F["P"])
    col = np.zeros((n, 3), np.float32)
    sm = np.full(n, SMOOTH["skin"], np.float32)
    skin = F["skin"]
    kb, kp, sc = F["k_belly"], F["kp"], 1 - F["kp"]
    base = np.broadcast_to(C["back"], (n, 3)) * (1 + 0.10 * F["mottle"])[:, None]
    base = _mix(base, C["back_dark"], F["dorsal"] * 0.55)
    band = smoothstep(0.02, 0.40, kb) * (1 - smoothstep(0.45, 0.90, kb))
    base = _mix(base, C["flank"], band * 0.6)
    base = _mix(base, C["spot"], F["spot"] * 0.75)
    base = base * (1 + sc * (0.16 * F["tint"] - 0.08))[:, None]
    base = _mix(base, C["scale_hi"], sc * F["hi"] * 0.40)
    base = _mix(base, C["crevice"], sc * (1 - F["crev"]) * 0.60)
    pl = _mix(np.broadcast_to(C["belly"], (n, 3)), C["belly_hi"], F["frac"] * 0.35 * kp)
    pl = pl * (1 + kp * (0.14 * (F["prand"] - 0.5) + 0.04 * F["stria"]))[:, None]
    pl = _mix(pl, C["belly_edge"], F["groove"] * 0.70 * kp)
    base = _mix(base, pl, kb)
    base = _mix(base, C["crevice"], F["shade_head"] * 0.55)
    base = _mix(base, C["back_dark"], F["nos_lip"] * 0.35)
    base = _mix(base, C["crevice"] * 0.45, F["nos_in"] * 0.92)
    col[skin] = base[skin]
    sm[skin] = (SMOOTH["skin"] + 0.14 * F["hi"] * sc - 0.12 * (1 - F["crev"]) * sc +
                (SMOOTH["belly"] - SMOOTH["skin"]) * kb - 0.10 * F["nos_in"])[skin]
    m = F["mouth"]
    col[m] = C["mouth"] * (0.85 + 0.15 * F["tint"][m, None])
    sm[m] = SMOOTH["mouth"]
    c = F["claw"]
    col[c] = _mix(np.broadcast_to(C["back_dark"], (c.sum(), 3)), C["claw"], smoothstep(0.0, 0.5, F["ct"][c]))
    sm[c] = SMOOTH["claw"]
    t = F["tooth"]
    col[t] = _mix(np.broadcast_to(C["tooth_root"], (t.sum(), 3)), C["tooth"], smoothstep(0.0, 0.5, F["tooth_t"][t]))
    sm[t] = SMOOTH["tooth"]
    t = F["tongue"]
    col[t] = C["tongue"] * (0.85 + 0.3 * F["height"][t, None])
    sm[t] = SMOOTH["tongue"]
    e = F["eye"]
    er = F["er"][e]
    iris = _mix(np.broadcast_to(C["eye"], (e.sum(), 3)), C["eye_dark"], smoothstep(0.35, 0.95, er))
    iris = iris * (0.88 + 0.24 * F["fibres"][e])[:, None]
    iris = _mix(iris, C["eye_glow"], smoothstep(0.42, 0.18, er) * 0.5)
    iris = _mix(iris, _c("0e0a06"), smoothstep(0.84, 1.0, er) * 0.8)
    col[e] = iris
    col[F["pupil"]] = _c("080605")
    sm[e] = SMOOTH["eye"]
    col *= (0.55 + 0.45 * np.clip(F["ao"], 0, 1))[:, None]
    return DP._assemble(F, col, sm, F["height"])


# ----------------------------------------------------------------------------------------- fins
def fin_fields(D):
    """Per fin texel: which fin (gill fan, toe web, tail fin or keel), how far out (0 root .. 1 edge) and its rays."""
    valid = D["valid"]
    idx = np.nonzero(valid.ravel())[0]
    P = D["P"].reshape(-1, 3)[idx].astype(np.float64)
    ao = _f32(D["ao"].ravel()[idx])
    n = len(P)
    out_u = np.zeros(n)
    ray = np.zeros(n)
    kind = np.full(n, 2)                                          # 0 gill, 1 web, 2 tail
    G = HH.GILL
    for nid in HB.neck_ids(3):                                    # gill fans: rays at the pleats' folds
        M = HS._M(nid)
        R3 = np.array(M.to_3x3())
        for s_ in (1, -1):
            root = HS.to_world(nid, np.array(G["root"]) * (s_, 1, 1))
            d1 = R3 @ (np.array(G["back"], float) * (s_, 1, 1))
            d1 /= np.linalg.norm(d1)
            d2 = R3 @ np.array(G["up"], float)
            d2 -= d1 * (d1 @ d2)
            d2 /= np.linalg.norm(d2)
            rel = P - root
            r = np.linalg.norm(rel, axis=1)
            near = r < G["radius"] * 1.15
            th = np.arctan2(rel @ d2, rel @ d1)
            a0, a1 = (math.radians(a) for a in G["arc"])
            v = (th - a0) / (a1 - a0)
            sel = near & (kind == 2)
            kind[sel] = 0
            out_u[sel] = np.clip(r[sel] / G["radius"], 0, 1)
            ray[sel] = smoothstep(0.75, 0.97, np.abs(np.sin(v[sel] * math.pi * 2 * G["pleats"])))
    web = (P[:, 2] < 0.25) & (kind == 2)                          # toe webs: veins fanning from the paw
    if web.any():
        paws = []
        for s_ in (1, -1):
            for paw in (HB.FRONT["paw"], HB.HIND["paw"]):
                paws.append(np.array(DB_m(paw, s_)))
        paws = np.array(paws)
        Pw = P[web]
        j = np.argmin(((Pw[:, None, :] - paws[None]) ** 2).sum(-1), axis=1)
        rel = Pw - paws[j]
        r = np.linalg.norm(rel[:, :2], axis=1)
        th = np.arctan2(rel[:, 0], -rel[:, 1])
        kind[web] = 1
        out_u[web] = np.clip(r / 0.42, 0, 1)
        ray[web] = smoothstep(0.80, 0.98, np.abs(np.sin(th * 9)))
    tail = kind == 2                                              # tail fin and keel: rays slanting back
    if tail.any():
        Pt = P[tail]
        from beast_common import spline
        Rr = spline(HB.BODY_ROWS, 12)
        i = np.argmin(np.abs(Rr[:, 1][None, :] - Pt[:, 1][:, None]), axis=1)
        top = Pt[:, 2] > Rr[i, 2]
        z0 = np.where(top, Rr[i, 2] + Rr[i, 4] * 0.9, Rr[i, 2] - Rr[i, 5] * 0.9)
        hmax = np.where(top, np.interp(Pt[:, 1], *zip(*HB.TAIL_FIN)), np.interp(Pt[:, 1], *zip(*HB.TAIL_KEEL)))
        hh = np.abs(Pt[:, 2] - z0)
        out_u[tail] = np.clip(hh / np.maximum(hmax, 0.03), 0, 1)
        ray[tail] = smoothstep(0.86, 0.99, np.abs(np.sin(math.pi * (Pt[:, 1] - 0.35 * hh) / 0.26)))   # (13 cm: corrugated)
    wrinkle = fbm(P / 0.05, 2, seed=23)
    height = 0.6 * ray * (1 - 0.5 * out_u) + 0.05 * wrinkle + 0.2 * smoothstep(0.92, 1.0, out_u)
    return dict(idx=idx, ao=ao, u=_f32(out_u), ray=_f32(ray), kind=kind, mottle=_f32(fbm(P / 0.5, 2, seed=29)),
                height=_f32(height), shape=valid.shape)


def DB_m(p, s):
    return (s * p[0], p[1], p[2])


def paint_fins(F, preset):
    C = {k: _c(v) for k, v in preset.items()}
    n = len(F["idx"])
    u = F["u"]
    col = _mix(np.broadcast_to(C["fin"], (n, 3)), C["fin_thin"], smoothstep(0.15, 0.75, u) * 0.6)
    col = _mix(col, C["fin_edge"], smoothstep(0.55, 1.0, u) * np.where(F["kind"] == 0, 0.9, 0.55))
    col = col * (1 + 0.10 * F["mottle"])[:, None]
    col = _mix(col, C["fin_ray"], F["ray"] * 0.55)
    col *= (0.70 + 0.30 * np.clip(F["ao"], 0, 1))[:, None]
    sm = SMOOTH["fin"] + 0.06 * F["ray"]
    return DP._assemble(F, col, sm, F["height"])


# ----------------------------------------------------------------------------------------- build
HEAD_GROUPS = tuple(f"{b}{n}" for n in ("", "L", "R") for b in ("Head", "Jaw"))
_CACHE = {}


def build(size=SIZE, fin_size=FIN_SIZE, presets=("sea", "swamp", "abyss"), unwrap=True, body=True, fins=True):
    """UVs, bakes, the presets' albedos and the normal maps into textures/; the materials M_Hydra and M_HydraFins
    (the first preset) on HydraBody and HydraFins. The bake and fields are kept in _CACHE. -> report"""
    ob = bpy.data.objects["HydraBody"]
    of = bpy.data.objects["HydraFins"]
    rep, paths = {}, []
    if body:
        if unwrap:
            rep["islands"] = DP.unwrap_body(ob, head_groups=HEAD_GROUPS)
        D = BP.bake_data(ob, size=size)
        rep["coverage"] = float(D["valid"].mean())
        F = body_fields(D)
        _CACHE.update(D=D, F=F)
        nrm = None
        for p in presets:
            col, sm, hgt = paint_body(F, PRESETS[p])
            if nrm is None:
                path, nrm = BP.write_normal_map(D, hgt, "T_Hydra_Normal", strength=RELIEF)
                paths.append(path)
            name = "T_Hydra" if p == presets[0] else "T_Hydra_" + p.title()
            paths.append(BP.write_texture(D, col, sm, name, ob if p == presets[0] else None, "M_Hydra", normal=nrm))
    if fins:
        if unwrap:
            rep["fin_islands"] = DP.unwrap_body(of, head_groups=())
        Df = BP.bake_data(of, size=fin_size, ao_samples=32)
        rep["fin_coverage"] = float(Df["valid"].mean())
        Ff = fin_fields(Df)
        _CACHE.update(Df=Df, Ff=Ff)
        nrm_f = None
        for p in presets:
            col, sm, hgt = paint_fins(Ff, PRESETS[p])
            if nrm_f is None:
                path, nrm_f = BP.write_normal_map(Df, hgt, "T_HydraFins_Normal", strength=RELIEF_FIN)
                paths.append(path)
            name = "T_HydraFins" if p == presets[0] else "T_HydraFins_" + p.title()
            paths.append(BP.write_texture(Df, col, sm, name, of if p == presets[0] else None, "M_HydraFins",
                                          normal=nrm_f))
    rep["paths"] = paths
    return rep


def use_preset(name):
    """Swap the body's and fins' albedo to a preset already written, for a look in Blender."""
    import beast_common
    for mat, tex in (("M_Hydra", "T_Hydra"), ("M_HydraFins", "T_HydraFins")):
        fn = tex if name == "sea" else tex + "_" + name.title()
        path = os.path.join(beast_common.ROOT, "textures", fn + ".png")
        img = bpy.data.images.load(path, check_existing=True)
        m = bpy.data.materials[mat]
        node = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and
                    n.image.colorspace_settings.name != 'Non-Color')
        node.image = img
