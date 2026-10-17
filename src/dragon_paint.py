"""The dragon's paint (2026-10-17). Daniel: "You can start the paint. I think it should be interesting to add normal
maps into this, since it is a big creature. You can even add more material properties if desired, but I think normal
maps do the job." Then, on the first pass: "we need more pixels for the texture, I can see it is pixelated. The
texture isn't that good yet, keep improving" and "specifically, the wings texture isn't that good".

The beasts' framework (beast_paint): Cycles bakes rest position, normal, part (the build's 'info' attribute) and AO
per texel; this module paints colour and smoothness in numpy and writes a tangent-space normal map from a height
field (height_normals: differences inside each UV island, so seams add no ridges). The height is computed from 3D
positions, so it is continuous across the UV islands.

Second pass (after his notes):
- resolution: the body at 4096 (was 2048, packed tighter); the wings at 4096 with both wings on the same mirrored
  layout (each wing had half of a 1024 before: ~2 mm a texel now, ~8 mm then);
- wings: veins that wander, thick at the bones and tapering, branching, over a capillary net; the membrane thick and
  dark at the bones and along the trailing edge, thin and light in the middle of each bay; elastic fibres along the
  edge; mottling;
- body: bigger overlapping scales with a light catching on their raised tail-ward rims, keeled scutes down the top
  line, mottling, a darker saddle, a warm band where the flanks meet the belly, each belly plate its own shade with
  fine lines; spikes and claws light at the base and dark at the tip; iris fibres, a limbal ring and a glow round the
  pupil; dark rings round the eyes and along the lips; teeth stained toward the gum.

Third pass (from close-ups at 4096):
- "pixelated" was mostly aliasing, not resolution: every plate's and scute's free edge dropped in one texel and drew
  stair-steps (EDGE now ramps it over 8 mm), and the plates' phase jumped wherever a texel's nearest spine row changed
  (the chest: teeth along every edge). _spine now blends the nearby rows, and the plates are measured along the
  belly's own line, so they stay even over the chest instead of fanning out to 40 cm;
- plates: no parallel fine lines (they read as corduroy), a firm per-plate edge against the flank scales (a wide
  blend ran the grooves through the scales), pitch from the section's width (neck ~10 cm, was 7);
- nostrils (Daniel: "the inside of the nostrils should not have scales, or we should have a scale ring over the
  nostril"): a dark, matte cavity, a smooth lip, two staggered rows of small scales (ring_cells, log-polar);
- scale size and direction blend over the shoulders and hips, finer down to the toes;
- wings: the capillaries only at the ridged noise's crests (a wide threshold made blotches like map borders), softer
  and broken elastic fibres, a broad thick-to-thin gradient and a darker edge band (they read as one flat orange at
  a distance), fine creases drawn out along the span.

Colour presets (Daniel: "Dragons will come in many colors"): the fields are computed once; each preset is its own
albedo (T_Dragon, T_Dragon_<Name>; T_DragonWing...) over one normal map, like the warg's coats. 'rust' is Daniel's
first (rusty red back, golden belly, dark horns and spikes, amber eyes); 'ash' and 'bronze' are mine.
"""
import bpy, bmesh, math, os
import numpy as np

import beast_paint as BP
import dragon_body as DB
import dragon_head as DH
import dragon_skin as S
from beast_common import smoothstep, fbm, vnoise, hexc, _hash3

PART = S.PART
SIZE, WING_SIZE = 4096, 4096
RELIEF = 5.0                     # normal strength at 4096 (height_normals works per texel: twice the 2048 value)
RELIEF_WING = 4.0
WING_SPAN = 8.4                  # metres of wing across the (shared, mirrored) wing texture

PRESETS = {
    "rust": dict(back="8c2e14", back_dark="5c1a0b", flank="b0461c", scale_hi="c9642a", crevice="3a0d05",
                 belly="d9a04c", belly_hi="ecc27a", belly_edge="8a4a1c", horn_base="5a4636", horn_tip="17120f",
                 claw="1c1714", tooth="e8dcc0", tooth_root="b09a6a", gum="6a2422", mouth="5e1c1a",
                 tongue="8a3a36", eye="ffa21a", eye_dark="a8520a", eye_glow="ffd36a", membrane="6e2412",
                 membrane_thin="bd5a26", vein="3e1108", rim="4a1409"),
    "ash": dict(back="3d3936", back_dark="1f1d1b", flank="5a3426", scale_hi="6e6862", crevice="121110",
                belly="c8692c", belly_hi="e08a46", belly_edge="6a3014", horn_base="a09684", horn_tip="1e1c1a",
                claw="1a1918", tooth="e8dcc0", tooth_root="a89470", gum="5a2220", mouth="4a1a18", tongue="7a3430",
                eye="ffd23c", eye_dark="b06a10", eye_glow="fff0a0", membrane="44241c", membrane_thin="944428",
                vein="1a0b07", rim="2a1410"),
    "bronze": dict(back="6e6328", back_dark="3e3714", flank="8a7a34", scale_hi="aa9c52", crevice="1e1a08",
                   belly="e2cf98", belly_hi="f2e4b8", belly_edge="8a7448", horn_base="5a4632", horn_tip="14100c",
                   claw="1a1612", tooth="e8dcc0", tooth_root="a8946a", gum="5e2a20", mouth="4e1e18",
                   tongue="7e3a32", eye="8fe85a", eye_dark="3f8a1e", eye_glow="d8ffa0", membrane="54481e",
                   membrane_thin="a8924a", vein="221d08", rim="352d10"),
}
SMOOTH = dict(skin=0.30, belly=0.45, mouth=0.62, horn=0.55, claw=0.62, tooth=0.68, tongue=0.60, eye=0.93, pupil=0.95,
              frill=0.34, membrane=0.34)
UV_SCALE = {"head": 1.7, PART["eye"]: 2.5, PART["pupil"]: 2.5, PART["tooth"]: 0.6, PART["tongue"]: 0.7,
            PART["mouth"]: 0.8}


def _c(h):
    return np.asarray(hexc(h), np.float32)


def _mix(a, b, t):
    t = np.clip(np.asarray(t, np.float32), 0, 1)[..., None]
    return a * (1 - t) + b * t


def _f32(a):
    return np.asarray(a, np.float32)


# ----------------------------------------------------------------------------------------- UVs
def _vertex_parts(ob):
    me = ob.data
    a = np.zeros(len(me.vertices) * 4, np.float32)
    me.color_attributes["info"].data.foreach_get("color", a)
    return np.rint(a.reshape(-1, 4)[:, 0] * 255).astype(int)


def _head_verts(ob):
    gi = {g.name: g.index for g in ob.vertex_groups}
    hj = {gi.get("Head"), gi.get("Jaw")}
    return np.array([sum(g.weight for g in v.groups if g.group in hj) > 0.5 for v in ob.data.vertices])


def unwrap_body(ob, margin=0.0012):
    """Smart project (the skin is one closed piece: no natural seams to hand), one texel density, then the head
    larger (its face is seen in game), the eyes larger still, teeth and mouth smaller; packed by shape."""
    parts, head = _vertex_parts(ob), _head_verts(ob)
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.hide_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    for u in list(ob.data.uv_layers):
        ob.data.uv_layers.remove(u)
    ob.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.seams_from_islands()
    bm = bmesh.from_edit_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    BP._tame_islands(bm, uv)
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        if len(e.link_faces) == 2 and not e.seam:
            a, b = e.link_faces
            parent[find(a.index)] = find(b.index)
    islands = {}
    for f in bm.faces:
        islands.setdefault(find(f.index), []).append(f)
    for fs in islands.values():
        vs = [v.index for f in fs for v in f.verts]
        pv = np.bincount(parts[vs], minlength=16).argmax()
        k = UV_SCALE.get(int(pv), UV_SCALE["head"] if head[vs].mean() > 0.5 else 1.0)
        if k != 1.0:
            loops = [l for f in fs for l in f.loops]
            c = sum((l[uv].uv for l in loops), loops[0][uv].uv * 0) / len(loops)
            for l in loops:
                l[uv].uv = c + (l[uv].uv - c) * k
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.select_all(action='SELECT')
    try:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True, shape_method='CONCAVE')
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return len(islands)


def unwrap_membrane(ob):
    """Planar from above in the bind pose (the wings spread flat), both wings on the same mirrored layout, one
    density both ways."""
    me = ob.data
    for u in list(me.uv_layers):
        me.uv_layers.remove(u)
    uvl = me.uv_layers.new(name="UVMap")
    co = np.array([v.co[:] for v in me.vertices])
    vi = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", vi)
    P = co[vi]
    u = np.clip((np.abs(P[:, 0]) - 0.05) / WING_SPAN, 0.002, 0.998)
    w = np.clip((P[:, 1] + 1.95) / WING_SPAN, 0.002, 0.998)
    uvl.data.foreach_set("uv", np.stack([u, w], 1).ravel())


# ----------------------------------------------------------------------------------------- noise helpers
def voronoi(P, size, seed):
    """3D jittered-grid cells: (border: F2 - F1 in cell units, nearest feature point (world), the cell's random)."""
    q = P / size
    c0 = np.floor(q).astype(np.int64)
    b1 = np.full(len(P), 9.0, np.float32)
    b2 = np.full(len(P), 9.0, np.float32)
    feat = np.zeros_like(q)
    rid = np.zeros(len(P), np.float32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = c0 + np.array((dx, dy, dz))
                f = c + 0.1 + 0.8 * np.stack([_hash3(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
                d = np.linalg.norm(q - f, axis=1)
                closer = d < b1
                b2 = np.where(closer, b1, np.minimum(b2, d))
                feat = np.where(closer[:, None], f, feat)
                rid = np.where(closer, _hash3(c[:, 0], c[:, 1], c[:, 2], seed + 7), rid)
                b1 = np.where(closer, d, b1)
    return b2 - b1, feat * size, rid


def ridged(Q, octaves=3, seed=0):
    """Ridged noise in 0..1: sharp crests where the noise crosses zero (vein-like lines)."""
    return 1 - np.abs(fbm(Q, octaves, seed=seed))


def ring_cells(phi, rn, n_ang=16, step=1.4, r0=1.45, seed=61):
    """Scales in rows round an opening: log-polar cells, each row `step` times further out than the last and its
    cells about as wide as they are long, staggered row to row. -> (border F2 - F1, outward position in the cell,
    the cell's random, row coordinate y (0 at r0))"""
    x = (phi / (2 * np.pi)) % 1.0 * n_ang
    y = np.log(np.maximum(rn, 1e-3) / r0) / np.log(step)
    sx = (2 * np.pi / n_ang) / np.log(step)
    j0 = np.floor(y).astype(np.int64)
    b1, b2, fy, rid = np.full(len(x), 9.0), np.full(len(x), 9.0), np.zeros(len(x)), np.zeros(len(x))
    zero = np.zeros_like(j0)
    for dj in (-1, 0, 1):
        j = j0 + dj
        off = 0.5 * (j % 2)
        i0 = np.floor(x - off).astype(np.int64)
        for di in (-1, 0, 1):
            i = i0 + di
            iw = i % n_ang
            cx = i + off + 0.5 + 0.5 * (_hash3(iw, j, zero, seed) - 0.5)
            cy = j + 0.5 + 0.4 * (_hash3(iw, j, zero, seed + 1) - 0.5)
            d = np.hypot((x - cx) * sx, y - cy)
            closer = d < b1
            b2 = np.where(closer, b1, np.minimum(b2, d))
            fy = np.where(closer, cy, fy)
            rid = np.where(closer, _hash3(iw, j, zero, seed + 2), rid)
            b1 = np.where(closer, d, b1)
    return b2 - b1, y - fy, rid, y


def _seg_dist(P, segs):
    """Distance from points to a set of segments [(a, b)] and the arc parameter on the nearest one."""
    best = np.full(len(P), 9e9, np.float32)
    t = np.zeros(len(P), np.float32)
    which = np.zeros(len(P), int)
    for k, (a, b) in enumerate(segs):
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        u = np.clip(((P - a) @ d) / max(d @ d, 1e-12), 0, 1)
        dist = np.linalg.norm(P - (a + u[:, None] * d), axis=1)
        m = dist < best
        best[m] = dist[m]
        t[m] = u[m]
        which[m] = k
    return best, t, which


# ----------------------------------------------------------------------------------------- body fields
SIZES = (0.024, 0.036, 0.055, 0.08, 0.11)
EDGE = 0.008                     # metres over which a plate's or scute's free edge falls (a one-texel cliff aliases)


def scales(P, F, size, chunk=200000):
    """Overlapping scales: blend of the Voronoi layers at the wanted size. -> (height, crevice, highlight, tint)"""
    n = len(P)
    h, crev, hi, tint = (np.zeros(n, np.float32) for _ in range(4))
    ls = np.log(np.array(SIZES))
    t = np.interp(np.log(size), ls, np.arange(len(SIZES)))
    for li, sz in enumerate(SIZES):
        w = np.clip(1 - np.abs(t - li), 0, 1).astype(np.float32)
        sel = np.nonzero(w > 1e-3)[0]
        for k in range(0, len(sel), chunk):
            s = sel[k:k + chunk]
            border, feat, rid = voronoi(P[s], sz, 11 + li * 17)
            g = smoothstep(0.0, 0.25, border)
            along = ((P[s] - feat) * F[s]).sum(1) / sz
            ramp = np.clip(0.5 + along * 1.25, 0, 1)
            h[s] += w[s] * g * (0.30 + 0.70 * ramp ** 1.4) * (0.85 + 0.15 * rid)
            crev[s] += w[s] * g
            hi[s] += w[s] * g * ramp ** 2
            tint[s] += w[s] * rid
    return h, crev, hi, tint


def _spine(P, chunk=50000, k=10):
    """Per point: its place along the spine and its coordinates in the section there (u side, v up), blended over
    the nearby rows, each weighted by how close the point lies to the row's plane. (Taking the nearest row alone
    jumped wherever the body bulges far from the spine -- the chest -- and stepped every plate edge into teeth.)
    The plates' phase runs along the belly's line (each section's lowest point) instead: measured from the spine,
    the chest -- far out on the outside of the neck's bend -- fanned its plates out to 40 cm."""
    R, s = S.spine_rows(6)
    C = R[:, :3]
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.array((0, 0, 1.0)) - (T @ np.array((0, 0, 1.0)))[:, None] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    Sx = np.cross(T, N)
    ds = np.gradient(s)
    pitch = np.clip(0.3 * R[:, 3], 0.05, 0.20)          # about a third of the belly's half-width (neck ~10 cm)
    Cv = C - N * R[:, 5:6]
    Tv = np.gradient(Cv, axis=0)
    Tv /= np.maximum(np.linalg.norm(Tv, axis=1), 1e-9)[:, None]
    sv = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Cv, axis=0), axis=1))])
    dsv = np.maximum(np.gradient(sv), 0.02)
    phase = np.concatenate([[0], np.cumsum(np.diff(sv) / pitch[1:])])
    n = len(P)
    out = {key: np.empty(n, np.float64) for key in ("s", "u", "v", "a", "b", "c", "phase", "pitch")}
    Tb = np.empty((n, 3), np.float64)
    idx = np.empty(n, int)
    for k0 in range(0, n, chunk):
        Pc = P[k0:k0 + chunk].astype(np.float64)
        m = len(Pc)
        D2 = ((Pc[:, None, :] - C[None]) ** 2).sum(-1)
        nn = np.argpartition(D2, k, axis=1)[:, :k]
        dist = np.sqrt(np.take_along_axis(D2, nn, 1))
        idx[k0:k0 + m] = nn[np.arange(m), np.argmin(dist, 1)]
        d = Pc[:, None, :] - C[nn]
        al = (d * T[nn]).sum(-1)
        logw = -(al / ds[nn]) ** 2 - ((dist - dist.min(1, keepdims=True)) / 0.25) ** 2
        w = np.exp(logw - logw.max(1, keepdims=True))
        w /= w.sum(1, keepdims=True)
        o = slice(k0, k0 + m)
        out["s"][o] = (w * (s[nn] + al)).sum(1)
        D2v = ((Pc[:, None, :] - Cv[None]) ** 2).sum(-1)
        nv = np.argpartition(D2v, k, axis=1)[:, :k]
        dv = np.sqrt(np.take_along_axis(D2v, nv, 1))
        alv = ((Pc[:, None, :] - Cv[nv]) * Tv[nv]).sum(-1)
        lw = -(alv / dsv[nv]) ** 2 - ((dv - dv.min(1, keepdims=True)) / 0.25) ** 2
        wv = np.exp(lw - lw.max(1, keepdims=True))
        wv /= wv.sum(1, keepdims=True)
        out["phase"][o] = (wv * (phase[nv] + alv / pitch[nv])).sum(1)
        out["pitch"][o] = (wv * pitch[nv]).sum(1)
        out["u"][o] = (w * (d * Sx[nn]).sum(-1)).sum(1)
        out["v"][o] = (w * (d * N[nn]).sum(-1)).sum(1)
        for j, key in ((3, "a"), (4, "b"), (5, "c")):
            out[key][o] = (w * R[nn, j]).sum(1)
        Tb[o] = (w[..., None] * T[nn]).sum(1)
    Tb /= np.linalg.norm(Tb, axis=1)[:, None]
    u, v, a, b, c = out["u"], out["v"], out["a"], out["b"], out["c"]
    e = np.sqrt((u / a) ** 2 + (v / np.where(v > 0, b, c)) ** 2)
    ventral = -v / np.maximum(np.hypot(u, v), 1e-6)       # within the section (the chest's front sits ahead of
                                                          # its row: the full offset read it as a flank, no plates)
    return dict(idx=idx, s=_f32(out["s"]), T=_f32(Tb), u=_f32(u), v=_f32(v), a=_f32(a), b=_f32(b), c=_f32(c),
                e=_f32(e), ventral=_f32(ventral), phase=out["phase"], s_end=s[-1], pitch=_f32(out["pitch"]))


def _tangent(F, N):
    F = F - (F * N).sum(1)[:, None] * N
    return F / np.maximum(np.linalg.norm(F, axis=1), 1e-6)[:, None]


def _spike_segments():
    """Every spike and claw as (base, tip) (the shells' own layouts), for a base-to-tip gradient."""
    segs = []
    side, centre, ribs = DH._spikes()
    for s_ in (1, -1):
        for a, b, r, c in side + ribs:
            segs.append((DH.FRAME.hx(np.asarray(a, float) * (s_, 1, 1)), DH.FRAME.hx(np.asarray(b, float) * (s_, 1, 1))))
        for base, knuckle, tip, r, dd, bone in S.toes(s_):
            segs.append((tip - dd * 0.02, tip + dd * 0.20))
        W = DB.WING
        th0, th1 = S._m(W["wri"], s_), S._m(W["thumb"], s_)
        dd = (th1 - th0) / np.linalg.norm(th1 - th0)
        segs.append((th1, th1 + dd * 0.24))
    for a, b, r, c in centre:
        segs.append((DH.FRAME.hx(np.asarray(a, float)), DH.FRAME.hx(np.asarray(b, float))))
    for base, tip, r in S.dorsal_spikes():
        segs.append((base, tip))
    return segs


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
    headside = S.cut_side(P) < 0
    Ph = _f32(DH.FRAME.hx_inv(P))
    sp = _spine(P)
    z = P[:, 2]
    leg = skin & ~headside & (sp["e"] > 1.55) & (z < 2.0)
    toe = leg & (z < 0.30)
    arm = skin & ~headside & (sp["e"] > 1.55) & ~leg
    Pm = Ph.copy()
    Pm[:, 0] = np.abs(Pm[:, 0])

    # flow (scales point down it): toward the tail along the body, back along the head, down the legs, out the arms
    w_limb = (smoothstep(1.35, 1.75, sp["e"]) * (skin & ~headside))[:, None]
    limb_dir = np.where((z < 2.0)[:, None], np.array((0, 0, -1.0)), np.stack([np.sign(P[:, 0]), 0 * z, 0 * z], 1))
    flow = sp["T"] * (1 - w_limb) + limb_dir * w_limb
    flow[headside] = DH.FRAME.hx_dir(np.array((0.0, 1.0, 0.0)))
    flow = _f32(_tangent(flow, N))

    # scale size by region: with the section's size along the body; small on the face (larger on the brow), legs,
    # toes and arms
    size = np.clip(0.07 * np.sqrt(np.maximum(sp["a"], (sp["b"] + sp["c"]) / 2) / 0.5), 0.04, 0.09)
    brow = np.linalg.norm((Pm - np.array((0.24, -0.45, 0.24))) / np.array((0.12, 0.30, 0.10)), axis=1) < 1
    limb = np.where(z < 2.0, 0.042, 0.04) * (1 - smoothstep(0.42, 0.26, z) * 0.43)      # finer down to the toes
    size = size * (1 - w_limb[:, 0]) + limb * w_limb[:, 0]
    size = np.where(headside, np.where(brow, 0.045, 0.028), size)
    h_sc, crev, hi, tint = (np.zeros(n, np.float32) for _ in range(4))
    crev[:] = 1
    sel = np.nonzero(skin)[0]
    hs, cr, hh, ti = scales(P[sel], flow[sel], size[sel])
    h_sc[sel], crev[sel], hi[sel], tint[sel] = hs, cr, hh, ti

    # keeled scutes down the top line of the neck, back and tail
    vb = sp["v"] / np.maximum(sp["b"], 1e-3)
    dtop = smoothstep(0.80, 0.97, vb) * (skin & ~headside & ~leg & ~arm)
    sfrac = (sp["s"] / 0.14) % 1.0
    scute = smoothstep(0.0, 0.12, sfrac) * (0.4 + 0.6 * sfrac) * smoothstep(1.0, 1.0 - EDGE / 0.14, sfrac) + \
        0.35 * smoothstep(0.30, 0.0, np.abs(sp["u"]) / sp["a"])
    h_sc = h_sc * (1 - dtop) + scute * dtop

    # the belly plates (the gold): along the trunk, neck and tail; across the underside of the jaw
    lim = np.interp(sp["s"], (0.0, 1.8, 2.6, sp["s_end"]), (1.8, 1.8, 1.2, 1.3))
    k_belly = smoothstep(0.30, 0.62, sp["ventral"]) * smoothstep(lim, lim - 0.3, sp["e"])
    frac = sp["phase"] % 1.0
    pid = np.floor(sp["phase"]).astype(np.int64)
    crown = np.clip(1 - (sp["u"] / sp["a"]) ** 2, 0, 1) ** 0.25
    we = EDGE / sp["pitch"]
    plate = smoothstep(0.0, 0.10, frac) * (0.5 + 0.5 * frac) * (0.7 + 0.3 * crown) * smoothstep(1.0, 1.0 - we, frac)
    groove = np.maximum(1 - smoothstep(0.0, 0.10, frac), smoothstep(1.0 - we, 1.0, frac))
    jb = DH.at(DH.JAW, Ph[:, 1], 3)
    k_jaw = smoothstep(jb + 0.10, jb + 0.03, Ph[:, 2]) * (Ph[:, 2] < DH.lip(Ph[:, 1]) - 0.05)
    jfrac = (Ph[:, 1] / 0.065) % 1.0
    k_belly = np.where(headside, k_jaw, k_belly)
    wj = EDGE / 0.065
    plate = np.where(headside, smoothstep(0.0, 0.12, jfrac) * (0.5 + 0.5 * jfrac) * smoothstep(1.0, 1.0 - wj, jfrac),
                     plate)
    groove = np.where(headside, np.maximum(1 - smoothstep(0.0, 0.12, jfrac), smoothstep(1.0 - wj, 1.0, jfrac)), groove)
    frac = np.where(headside, jfrac, frac)
    pid = np.where(headside, np.floor(Ph[:, 1] / 0.065).astype(np.int64) + 1000, pid)
    k_belly = _f32(np.where(skin & ~leg & ~arm, k_belly, 0.0))
    mouth = part == PART["mouth"]
    k_belly[mouth] = 0.0
    prand = _f32(_hash3(pid, pid * 7 + 3, np.zeros_like(pid), 41))
    # the plates end against the flank scales at a firm edge, each a little further in or out (a wide blend
    # left their grooves running through the scales); fine pitting instead of parallel lines
    kp = _f32(smoothstep(0.36, 0.46, k_belly + 0.12 * (prand - 0.5)))
    stria = _f32(fbm(P / 0.012, 2, seed=43))
    height = np.where(skin, h_sc * (1 - kp) + (plate + 0.03 * stria) * kp, 0.0).astype(np.float32)
    height[mouth] = 0.15 * fbm(P[mouth] / 0.03, 2, seed=3)

    # dorsal shade (a darker saddle) and large, soft mottling
    dorsal = np.where(headside, smoothstep(0.15, 0.35, Ph[:, 2]) * 0.6, smoothstep(0.35, 0.95, vb))
    dorsal = _f32(np.where(skin & ~leg & ~arm, dorsal, 0.0))
    mottle = _f32(fbm(P / 0.7, 3, seed=31))

    # head: dark rings round the eyes, nostrils and along the lips
    eu, ev, ew = DH._eye_local(Pm)
    er = _f32(np.sqrt((eu / DH.EYE["A"]) ** 2 + (ev / DH.EYE["B"]) ** 2))
    eye_ring = (smoothstep(1.0, 1.15, er) * smoothstep(1.9, 1.3, er) * (np.abs(ew) < 0.06)).astype(np.float32)
    nos = np.linalg.norm((Pm - np.array(DH.NOSTRIL_HOLE[0])) / 0.07, axis=1)
    nostril = _f32(0.5 * smoothstep(1.3, 0.5, nos))
    lipd = np.abs(Ph[:, 2] - DH.lip(Ph[:, 1]))
    lips = _f32(smoothstep(0.045, 0.012, lipd) * (Ph[:, 1] < DH.Y_CORNER + 0.02) * skin * ~mouth)
    shade_head = np.where(headside, np.maximum(np.maximum(eye_ring, nostril), lips), 0.0).astype(np.float32)

    # nostrils (Daniel: "the inside of the nostrils should not have scales, or we should have a scale ring over the
    # nostril"): a dark cavity, a smooth lip round it, then two staggered rows of small scales (log-polar cells,
    # growing outward) that end at a groove where the face's own scales take over
    hc, hr = np.array(DH.NOSTRIL_HOLE[0]), np.array(DH.NOSTRIL_HOLE[1])
    ax = hc - np.array(DH.NOSTRIL[0])
    ax /= np.linalg.norm(ax)
    e1 = np.cross(ax, (0.0, 0.0, 1.0))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    q = Pm - hc
    rn = np.linalg.norm(q / hr, axis=1)
    phi = np.arctan2(q @ e2, q @ e1)
    R0, R_OUT = 1.45, 2.84                                # the lip's outer edge; two rows out (step 1.4)
    near = headside & skin & (rn < 3.0)
    sel = np.nonzero(near)[0]
    border, along, rid, _ = ring_cells(phi[sel], rn[sel], r0=R0)
    r_ = rn[sel]
    g = smoothstep(0.0, 0.22, border) * smoothstep(R0, R0 + 0.10, r_) * smoothstep(R_OUT, R_OUT - 0.10, r_)
    ramp = np.clip(0.5 + along * 1.25, 0, 1)
    ring_h = g * (0.30 + 0.70 * ramp ** 1.4) * (0.85 + 0.15 * rid)
    lip_h = 0.55 * smoothstep(0.80, 1.12, r_) * smoothstep(R0 + 0.02, R0 - 0.12, r_)
    in_ring = smoothstep(R_OUT + 0.16, R_OUT, r_)         # the face's scales fade in just past the outer groove
    lip = r_ < R0
    nh = np.maximum(ring_h, lip_h)
    h_sc[sel] = h_sc[sel] * (1 - in_ring) + nh * in_ring
    crev[sel] = np.where(lip, 1.0, crev[sel] * (1 - in_ring) + g * in_ring)
    hi[sel] = np.where(lip, 0.25 * lip_h, hi[sel] * (1 - in_ring) + g * ramp ** 2 * in_ring)
    tint[sel] = np.where(lip, 0.5, tint[sel] * (1 - in_ring) + rid * in_ring)
    height[sel] = h_sc[sel]                              # (the plates and the jaw never reach the nostrils)
    nos_in = np.zeros(n, np.float32)                      # the cavity, darkest at its back
    nos_in[sel] = smoothstep(1.02, 0.72, r_) * (0.75 + 0.25 * smoothstep(0.7, 0.2, r_))
    nos_lip = np.zeros(n, np.float32)
    nos_lip[sel] = smoothstep(0.80, 1.0, r_) * smoothstep(R0 + 0.02, R0 - 0.08, r_)

    # horns: rings by the position along each horn; spikes and claws light at the base, dark at the tip
    horn = part == PART["horn"]
    claw = part == PART["claw"]
    ht = np.full(n, 0.6, np.float32)
    hsel = np.nonzero(horn | claw)[0]
    on_horn = np.zeros(n, bool)
    if len(hsel):
        best = np.full(len(hsel), 9.0)
        for s_, sfx in DB.SIDES:
            rows = [(*DB._m(DB.hk(p), s_), p[3] * DB.HEAD_K) for p in DB.HORN]
            t, dist = BP.polyline_t(P[hsel], rows)
            m = dist < best
            ht[hsel[m]] = t[m]
            best[m] = dist[m]
        oh = (best < 0.16) & horn[hsel]
        on_horn[hsel[oh]] = True
        rest = hsel[~oh]
        if len(rest):
            d, t, _ = _seg_dist(P[rest].astype(np.float64), _spike_segments())
            ht[rest] = t
        rings = 0.5 + 0.5 * np.cos(2 * np.pi * ht[hsel] * 18)
        grain = fbm(P[hsel] / 0.02, 2, seed=5)
        height[hsel] = np.where(on_horn[hsel], 0.55 * smoothstep(0.25, 0.75, rings) + 0.15 * grain, 0.22 * grain)
    tongue = part == PART["tongue"]
    height[tongue] = 0.35 * smoothstep(0.2, 0.8, fbm(P[tongue] / 0.012, 2, seed=8) * 0.5 + 0.5)
    tooth = part == PART["tooth"]
    tooth_t = _f32(np.clip(np.abs(Ph[:, 2] - DH.lip(Ph[:, 1])) / 0.10, 0, 1))

    # eyes: iris fibres round the pupil
    eye = (part == PART["eye"]) | (part == PART["pupil"])
    eth = np.arctan2(ev, eu)
    fibres = _f32(0.5 + 0.5 * np.sin(eth * 36 + 2.0 * fbm(Pm / 0.03, 2, seed=12)))

    # frills: veins fanning from the base, the membrane thin between the ribs
    frill = part == PART["frill"]
    rel = Pm - np.array(DH.FRILL_BASE)
    th = np.arctan2(rel[:, 2], rel[:, 1])
    fv = np.abs(np.cos(th * 9 + 0.6 * fbm(Pm / 0.12, 2, seed=9)))
    vein_f = _f32(smoothstep(0.80, 0.98, fv) * frill)
    fthin = _f32(smoothstep(0.05, 0.35, np.linalg.norm(rel, axis=1)) * (1 - smoothstep(0.6, 0.98, fv)))
    height[frill] = 0.6 * vein_f[frill]

    F.update(skin=skin, headside=headside, leg=leg, arm=arm, crev=crev, hi=hi, tint=tint, k_belly=k_belly, kp=kp,
             groove=_f32(groove), frac=_f32(frac), prand=prand, stria=stria, height=height, dorsal=dorsal,
             mottle=mottle, shade_head=shade_head, nos_in=nos_in, nos_lip=nos_lip, horn=horn, claw=claw, on_horn=on_horn, ht=ht, eye=eye, er=er,
             fibres=fibres, pupil=part == PART["pupil"], tongue=tongue, tooth=tooth, tooth_t=tooth_t, mouth=mouth,
             frill=frill, vein_f=vein_f, fthin=fthin)
    return F


# ----------------------------------------------------------------------------------------- body painting
def paint_body(F, preset):
    """-> (colour (H, W, 3), smoothness (H, W), height (H, W)) for a preset (dict of hex colours)."""
    C = {k: _c(v) for k, v in preset.items()}
    n = len(F["P"])
    col = np.zeros((n, 3), np.float32)
    sm = np.full(n, SMOOTH["skin"], np.float32)
    skin = F["skin"]
    kb, kp, sc = F["k_belly"], F["kp"], 1 - F["kp"]

    # skin: back, a darker saddle, a warm band where the flank meets the belly, mottling
    base = np.broadcast_to(C["back"], (n, 3)) * (1 + 0.10 * F["mottle"])[:, None]
    base = _mix(base, C["back_dark"], F["dorsal"] * 0.55)
    band = smoothstep(0.02, 0.40, kb) * (1 - smoothstep(0.45, 0.90, kb))
    base = _mix(base, C["flank"], band * 0.7)
    # scales: each a little lighter or darker, light catching on the raised rims, dark in the crevices
    base = base * (1 + sc * (0.18 * F["tint"] - 0.09))[:, None]
    base = _mix(base, C["scale_hi"], sc * F["hi"] * 0.45)
    base = _mix(base, C["crevice"], sc * (1 - F["crev"]) * 0.65)
    # plates: each its own shade, lighter toward its overlapping edge, fine lines, dark grooves
    # (the plate shading only where the plates are: the gold runs on over the flank scales without their grooves)
    pl = _mix(np.broadcast_to(C["belly"], (n, 3)), C["belly_hi"], F["frac"] * 0.35 * kp)
    pl = pl * (1 + kp * (0.16 * (F["prand"] - 0.5) + 0.04 * F["stria"]))[:, None]
    pl = _mix(pl, C["belly_edge"], F["groove"] * 0.75 * kp)
    base = _mix(base, pl, kb)
    base = _mix(base, C["crevice"], F["shade_head"] * 0.55)
    base = _mix(base, C["back_dark"], F["nos_lip"] * 0.35)          # nostrils: a smooth darker lip, a dark cavity
    base = _mix(base, C["crevice"] * 0.45, F["nos_in"] * 0.92)
    col[skin] = base[skin]
    sm[skin] = (0.30 + 0.14 * F["hi"] * sc - 0.12 * (1 - F["crev"]) * sc + (0.45 - 0.30) * kb
                - 0.10 * F["nos_in"])[skin]
    m = F["mouth"]
    col[m] = C["mouth"] * (0.85 + 0.15 * F["tint"][m, None])
    sm[m] = SMOOTH["mouth"]

    h = F["horn"]
    oh = F["on_horn"]
    col[h] = _mix(np.broadcast_to(C["horn_base"], (h.sum(), 3)), C["horn_tip"], F["ht"][h] ** 0.8)
    col[h] *= (0.85 + 0.3 * F["height"][h])[:, None]
    col[oh] *= (0.92 + 0.16 * F["height"][oh])[:, None]
    sm[h] = SMOOTH["horn"]
    c = F["claw"]
    col[c] = _mix(np.broadcast_to(C["horn_base"] * 0.7, (c.sum(), 3)), C["claw"], smoothstep(0.0, 0.5, F["ht"][c]))
    sm[c] = SMOOTH["claw"]
    t = F["tooth"]
    col[t] = _mix(np.broadcast_to(C["tooth_root"], (t.sum(), 3)), C["tooth"], smoothstep(0.0, 0.5, F["tooth_t"][t]))
    sm[t] = SMOOTH["tooth"]
    t = F["tongue"]
    col[t] = C["tongue"] * (0.85 + 0.3 * F["height"][t, None])
    sm[t] = SMOOTH["tongue"]

    e = F["eye"]                                     # iris: fibres, a glow round the pupil, a dark limbal ring
    er = F["er"][e]
    iris = _mix(np.broadcast_to(C["eye"], (e.sum(), 3)), C["eye_dark"], smoothstep(0.35, 0.95, er))
    iris = iris * (0.88 + 0.24 * F["fibres"][e])[:, None]
    iris = _mix(iris, C["eye_glow"], smoothstep(0.42, 0.18, er) * 0.5)
    iris = _mix(iris, _c("2a1404"), smoothstep(0.84, 1.0, er) * 0.8)
    col[e] = iris
    col[F["pupil"]] = _c("0a0705")
    sm[e] = SMOOTH["eye"]

    f = F["frill"]
    fr = _mix(np.broadcast_to(C["membrane"], (f.sum(), 3)), C["membrane_thin"], F["fthin"][f] * 0.7)
    col[f] = _mix(fr, C["vein"], F["vein_f"][f] * 0.75)
    sm[f] = SMOOTH["frill"]

    col *= (0.55 + 0.45 * np.clip(F["ao"], 0, 1))[:, None]
    return _assemble(F, col, sm, F["height"])


def _assemble(F, col, sm, height):
    H, W = F["shape"]
    out = np.zeros((H * W, 3), np.float32)
    out[F["idx"]] = np.clip(col, 0, 1)
    s2 = np.zeros(H * W, np.float32)
    s2[F["idx"]] = np.clip(sm, 0, 1)
    h2 = np.zeros(H * W, np.float32)
    h2[F["idx"]] = height
    return out.reshape(H, W, 3), s2.reshape(H, W), h2.reshape(H, W)


# ----------------------------------------------------------------------------------------- wings
def _wing_layout():
    """The left wing's bones and edges (rest pose): bones = arm + fingers, edges = trailing + leading."""
    W = DB.WING
    sh, el, wr, kn, att = (np.array(W[k], float) for k in ("sho", "elb", "wri", "knu", "att"))
    fingers = [DB.finger_pts(i) for i in range(4)]
    tips = [f[-1] for f in fingers]
    bones = [(sh, el), (el, wr), (wr, kn)]
    for f in fingers:
        bones += [(f[k], f[k + 1]) for k in range(len(f) - 1)]
    edges = []
    for i in range(3):
        te = DB._sag(tips[i], tips[i + 1], kn, 24, 0.18)
        edges += [(te[k], te[k + 1]) for k in range(len(te) - 1)]
    te = DB._sag(att, tips[3], el, 30, 0.12)
    edges += [(te[k], te[k + 1]) for k in range(len(te) - 1)]
    lead = np.linspace(sh, wr, 16) + np.array((0, -0.12, 0.02)) * np.sin(np.linspace(0, math.pi, 16))[:, None]
    edges += [(lead[k], lead[k + 1]) for k in range(len(lead) - 1)]
    return bones, edges, kn, el


def wing_fields(D):
    valid = D["valid"]
    idx = np.nonzero(valid.ravel())[0]
    P = D["P"].reshape(-1, 3)[idx].astype(np.float64)
    ao = _f32(D["ao"].ravel()[idx])
    Q = P.copy()
    Q[:, 0] = np.abs(Q[:, 0])                            # one mirrored layout: paint the left wing
    bones, edges, kn, el = _wing_layout()
    d_bone, t_bone, which = _seg_dist(Q, bones)
    d_edge, _, _ = _seg_dist(Q, edges)

    # main veins: wandering lines fanning from the knuckle (from the elbow in the arm's panel), thick near the bones
    # and the knuckle, tapering outward, faded out on the bones themselves
    centre = np.where((Q[:, 0] > kn[0] - 0.35)[:, None], kn, el)
    rel = Q[:, :2] - centre[:, :2]
    r = np.linalg.norm(rel, axis=1)
    th = np.arctan2(rel[:, 1], rel[:, 0])
    warp = 0.35 * fbm(Q / 0.9, 3, seed=21) + 0.12 * fbm(Q / 0.25, 2, seed=27)
    lines = np.abs(np.sin(th * 11 + warp * 3.0))
    width = np.clip(0.11 * (1.15 - r / 7.0), 0.025, 0.11)
    main = smoothstep(width, width * 0.25, lines) * smoothstep(0.25, 0.9, r)
    # branches: a second, finer family further out, broken into pieces
    lines2 = np.abs(np.sin(th * 23 + warp * 4.0 + 1.3))
    br = smoothstep(0.045, 0.01, lines2) * smoothstep(1.8, 3.0, r) * smoothstep(-0.1, 0.4, fbm(Q / 0.6, 2, seed=24))
    # capillaries: a ridged net between the veins
    # (a wide threshold made broad blotchy bands, like map borders: keep only the crests)
    cap = smoothstep(0.962, 0.994, ridged(Q / 0.22 + 0.4 * fbm(Q / 0.8, 2, seed=25)[:, None], 3, seed=26))
    cap = cap * smoothstep(-0.2, 0.3, fbm(Q / 0.5, 2, seed=30))      # in patches, not everywhere
    # a vein along each bone, either side of it
    along_bone = smoothstep(0.035, 0.0, np.abs(d_bone - 0.10)) * smoothstep(0.0, 0.2, t_bone) * \
        smoothstep(1.0, 0.8, t_bone)
    near_bone = smoothstep(0.07, 0.0, d_bone)
    vein = np.clip(np.maximum.reduce([main, 0.75 * br, 0.28 * cap, 0.7 * along_bone]) * (1 - near_bone), 0, 1)
    # thickness: thick at the bones and along the edges, thin in the middle of each bay (a broad gradient: a narrow
    # one left the wing one flat orange at a distance)
    thin = smoothstep(0.08, 1.30, d_bone) * smoothstep(0.04, 0.50, d_edge)
    band = smoothstep(0.45, 0.0, d_edge)                 # a darker band along the edges
    # fine leathery creases between the veins, drawn out along the span (round, they read as a maze)
    crease = smoothstep(0.93, 0.99, ridged(Q / np.array((0.14, 0.035, 0.07)) + 0.3 * fbm(Q / 0.3, 2, seed=32)[:, None],
                                           2, seed=33))
    # elastic fibres running along the trailing edge, fine wrinkles
    fib = 0.5 + 0.5 * np.sin(d_edge / 0.08 * 2 * np.pi + 3.0 * fbm(Q / 0.5, 2, seed=28))
    fib = fib * smoothstep(-0.1, 0.4, fbm(Q / 0.7, 2, seed=31))       # (even stripes read as corduroy)
    wrinkle = fbm(Q / 0.06, 2, seed=23)
    mottle = fbm(Q / 1.1, 3, seed=29)
    height = 0.75 * vein + 0.05 * fib * thin + 0.06 * wrinkle + 0.06 * crease * (1 - vein) + \
        0.25 * smoothstep(0.10, 0.02, d_bone)
    return dict(idx=idx, ao=ao, vein=_f32(vein), thin=_f32(thin), fib=_f32(fib), mottle=_f32(mottle),
                rim=_f32(smoothstep(0.07, 0.0, d_edge)), band=_f32(band), crease=_f32(crease), height=_f32(height),
                shape=valid.shape)


def paint_wing(F, preset):
    C = {k: _c(v) for k, v in preset.items()}
    n = len(F["idx"])
    col = _mix(np.broadcast_to(C["membrane"], (n, 3)), C["membrane_thin"], F["thin"] * 0.9)
    col = col * (1 + 0.14 * F["mottle"] + 0.04 * (F["fib"] - 0.5) * F["thin"] - 0.04 * F["crease"])[:, None]
    col = _mix(col, C["rim"], F["band"] * 0.35)
    col = _mix(col, C["rim"], F["rim"] * 0.6)
    col = _mix(col, C["vein"], F["vein"] * 0.85)
    col *= (0.70 + 0.30 * np.clip(F["ao"], 0, 1))[:, None]
    sm = SMOOTH["membrane"] + 0.08 * F["vein"] - 0.06 * F["thin"]
    return _assemble(F, col, sm, F["height"])


# ----------------------------------------------------------------------------------------- build
def build(size=SIZE, wing_size=WING_SIZE, presets=("rust", "ash", "bronze"), unwrap=True, body=True, wings=True):
    """UVs, bakes, the presets' albedos and the normal maps into textures/; the game materials M_Dragon and
    M_DragonWing (the first preset) on DragonBody and DragonWingMembrane. -> report"""
    ob = bpy.data.objects["DragonBody"]
    om = bpy.data.objects["DragonWingMembrane"]
    rep, paths = {}, []
    if body:
        if unwrap:
            rep["islands"] = unwrap_body(ob)
        D = BP.bake_data(ob, size=size)
        rep["coverage"] = float(D["valid"].mean())
        F = body_fields(D)
        del D["P"], D["N"]
        nrm = None
        for p in presets:
            col, sm, hgt = paint_body(F, PRESETS[p])
            if nrm is None:
                path, nrm = BP.write_normal_map(D, hgt, "T_Dragon_Normal", strength=RELIEF)
                paths.append(path)
            name = "T_Dragon" if p == presets[0] else "T_Dragon_" + p.title()
            paths.append(BP.write_texture(D, col, sm, name, ob if p == presets[0] else None, "M_Dragon", normal=nrm))
        del F
    if wings:
        if unwrap:
            unwrap_membrane(om)
        Dw = BP.bake_data(om, size=wing_size, ao_samples=32)
        rep["wing_coverage"] = float(Dw["valid"].mean())
        Fw = wing_fields(Dw)
        nrm_w = None
        for p in presets:
            col, sm, hgt = paint_wing(Fw, PRESETS[p])
            if nrm_w is None:
                path, nrm_w = BP.write_normal_map(Dw, hgt, "T_DragonWing_Normal", strength=RELIEF_WING)
                paths.append(path)
            name = "T_DragonWing" if p == presets[0] else "T_DragonWing_" + p.title()
            paths.append(BP.write_texture(Dw, col, sm, name, om if p == presets[0] else None, "M_DragonWing",
                                          normal=nrm_w))
    rep["paths"] = paths
    return rep


def use_preset(name):
    """Swap the body's and wings' albedo to a preset already written (T_Dragon_<Name>), for a look in Blender."""
    import beast_common
    for mat, tex in (("M_Dragon", "T_Dragon"), ("M_DragonWing", "T_DragonWing")):
        fn = tex if name == "rust" else tex + "_" + name.title()
        path = os.path.join(beast_common.ROOT, "textures", fn + ".png")
        img = bpy.data.images.load(path, check_existing=True)
        m = bpy.data.materials[mat]
        node = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and
                    n.image.colorspace_settings.name != 'Non-Color')
        node.image = img
