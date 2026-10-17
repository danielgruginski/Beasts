"""The dragon's paint (2026-10-17). Daniel: "You can start the paint. I think it should be interesting to add normal
maps into this, since it is a big creature. You can even add more material properties if desired, but I think normal
maps do the job."

The beasts' framework (beast_paint): Cycles bakes rest position, normal, part (the build's 'info' attribute) and AO
per texel; this module paints colour and smoothness in numpy and writes a tangent-space normal map from a height
field (height_normals: differences inside each UV island, so seams add no ridges). The height is computed from 3D
positions, so it is continuous across the many UV islands.

Colour presets (Daniel: "Dragons will come in many colors"): the fields below are computed once; paint_body(fields,
preset) is cheap, and every preset is its own albedo (T_Dragon, T_Dragon_<Name>) over one normal map
(T_Dragon_Normal), like the warg's coats. 'rust' is Daniel's first: rusty red back, golden belly, dark horns and
spikes, amber eyes. 'ash' and 'bronze' are mine (from the options he was shown), to prove the presets.

Relief:
- pebbled scales on all the skin: 3D Voronoi cells in four sizes blended by region (large on the back and tail,
  small on the face, legs and toes), grooved at their borders and raised toward their tail-ward edge so they read as
  overlapping;
- the belly: broad plates from the throat down the chest and belly to the tail tip, their pitch following the
  section's depth, and plates across the underside of the jaw;
- rings round the horns, a fine grain on spikes and claws, papillae on the tongue; veins on the frills and wings.
"""
import bpy, bmesh, math, os
import numpy as np

import beast_paint as BP
import dragon_body as DB
import dragon_head as DH
import dragon_skin as S
from beast_common import smoothstep, fbm, hexc, _hash3

PART = S.PART
RELIEF = 2.6                     # normal map strength (beast_paint.height_normals)
RELIEF_WING = 2.0

PRESETS = {
    "rust": dict(back="8c2e14", back_dark="5c1a0b", belly="d9a04c", belly_edge="a8632a", horn_base="4f3d2f",
                 horn_tip="17120f", claw="1c1714", membrane="7a2a14", vein="45140a", eye="ffa21a", eye_dark="a8520a",
                 mouth="5e1c1a", tongue="8a3a36", tooth="e8dcc0", gum="6a2422"),
    "ash": dict(back="3d3936", back_dark="1f1d1b", belly="c8692c", belly_edge="7a3a18", horn_base="8c8172",
                horn_tip="1e1c1a", claw="1a1918", membrane="5a2c1e", vein="2a120a", eye="ffd23c", eye_dark="b06a10",
                mouth="4a1a18", tongue="7a3430", tooth="e8dcc0", gum="5a2220"),
    "bronze": dict(back="6e6328", back_dark="3e3714", belly="e2cf98", belly_edge="a8925a", horn_base="4a3a28",
                   horn_tip="14100c", claw="1a1612", membrane="6a5a26", vein="3a3010", eye="8fe85a", eye_dark="3f8a1e",
                   mouth="4e1e18", tongue="7e3a32", tooth="e8dcc0", gum="5e2a20"),
}
SMOOTH = dict(skin=0.36, belly=0.44, mouth=0.62, horn=0.55, claw=0.62, tooth=0.68, tongue=0.60, eye=0.93, pupil=0.95,
              frill=0.30, membrane=0.30)
UV_SCALE = {"head": 1.7, PART["eye"]: 2.5, PART["pupil"]: 2.5, PART["tooth"]: 0.6, PART["tongue"]: 0.7,
            PART["mouth"]: 0.8}


def _c(h):
    return np.asarray(hexc(h), float)


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


def unwrap_body(ob, margin=0.002):
    """Smart project (the skin is one closed piece: no natural seams to hand), one texel density, then the head
    larger (its face is seen in game), the eyes larger still, teeth and mouth smaller; packed."""
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
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0,
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
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return len(islands)


def unwrap_membrane(ob):
    """Planar, from above in the bind pose (the wings spread flat): the left wing on the top half, the right below,
    both at about one density."""
    me = ob.data
    for u in list(me.uv_layers):
        me.uv_layers.remove(u)
    uvl = me.uv_layers.new(name="UVMap")
    co = np.array([v.co[:] for v in me.vertices])
    vi = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", vi)
    P = co[vi]
    u = np.clip((np.abs(P[:, 0]) - 0.05) / 8.3, 0.002, 0.998)
    w = np.clip((P[:, 1] + 1.95) / 5.3, 0.004, 0.996) * 0.5 + np.where(P[:, 0] >= 0, 0.5, 0.0)
    uvl.data.foreach_set("uv", np.stack([u, w], 1).ravel())


# ----------------------------------------------------------------------------------------- fields
def voronoi(P, size, seed):
    """3D jittered-grid cells: (border: F2 - F1 in cell units, nearest feature point (world), the cell's random)."""
    q = P / size
    c0 = np.floor(q).astype(np.int64)
    b1 = np.full(len(P), 9.0)
    b2 = np.full(len(P), 9.0)
    feat = np.zeros_like(q)
    rid = np.zeros(len(P))
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


SIZES = (0.022, 0.034, 0.052, 0.08)


def scales(P, F, size, chunk=150000):
    """Pebbled, overlapping scales: blend of the Voronoi layers at the wanted size. -> (height, crevice, tint)"""
    n = len(P)
    h, crev, tint = np.zeros(n), np.zeros(n), np.zeros(n)
    ls = np.log(np.array(SIZES))
    t = np.interp(np.log(size), ls, np.arange(len(SIZES)))
    for li, sz in enumerate(SIZES):
        w = np.clip(1 - np.abs(t - li), 0, 1)
        sel = np.nonzero(w > 1e-3)[0]
        for k in range(0, len(sel), chunk):
            s = sel[k:k + chunk]
            border, feat, rid = voronoi(P[s], sz, 11 + li * 17)
            g = smoothstep(0.0, 0.22, border)
            along = ((P[s] - feat) * F[s]).sum(1) / sz
            ramp = np.clip(0.5 + along * 1.1, 0, 1)
            h[s] += w[s] * g * (0.45 + 0.55 * ramp) * (0.85 + 0.15 * rid)
            crev[s] += w[s] * g
            tint[s] += w[s] * rid
    return h, crev, tint


def _spine(P, chunk=60000):
    """Per point: the nearest spine row's index and the point's coordinates in its section."""
    R, s = S.spine_rows(6)
    C = R[:, :3]
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.array((0, 0, 1.0)) - (T @ np.array((0, 0, 1.0)))[:, None] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    Sx = np.cross(T, N)
    idx = np.empty(len(P), int)
    for k in range(0, len(P), chunk):
        idx[k:k + chunk] = np.argmin(((P[k:k + chunk, None, :] - C[None]) ** 2).sum(-1), axis=1)
    d = P - C[idx]
    u, v, along = (d * Sx[idx]).sum(1), (d * N[idx]).sum(1), (d * T[idx]).sum(1)
    a, b, c = R[idx, 3], R[idx, 4], R[idx, 5]
    e = np.sqrt((u / a) ** 2 + (v / np.where(v > 0, b, c)) ** 2)
    ventral = -v / np.maximum(np.hypot(u, v), 1e-6)       # within the section (the chest's front sits ahead of
                                                          # its row: the full offset read it as a flank, no plates)
    pitch = np.clip(0.13 * R[:, 5], 0.035, 0.19)
    phase = np.concatenate([[0], np.cumsum(np.diff(s) / pitch[1:])])
    return dict(idx=idx, s=s[idx], T=T[idx], u=u, v=v, a=a, b=b, c=c, e=e, ventral=ventral,
                phase=phase[idx] + along / pitch[idx], s_end=s[-1])


def _tangent(F, N):
    F = F - (F * N).sum(1)[:, None] * N
    return F / np.maximum(np.linalg.norm(F, axis=1), 1e-6)[:, None]


def body_fields(D):
    """Everything the painter needs that doesn't depend on the colours (computed once for all presets)."""
    valid = D["valid"]
    idx = np.nonzero(valid.ravel())[0]
    P = D["P"].reshape(-1, 3)[idx].astype(np.float64)
    N = D["N"].reshape(-1, 3)[idx].astype(np.float64)
    part = D["part"].ravel()[idx]
    ao = D["ao"].ravel()[idx]
    n = len(P)
    F = dict(idx=idx, P=P, N=N, part=part, ao=ao, shape=valid.shape)
    skin = (part == PART["skin"]) | (part == PART["mouth"])
    headside = S.cut_side(P) < 0
    Ph = DH.FRAME.hx_inv(P)
    sp = _spine(P)
    z = P[:, 2]
    leg = skin & ~headside & (sp["e"] > 1.55) & (z < 2.0)
    toe = leg & (z < 0.30)
    arm = skin & ~headside & (sp["e"] > 1.55) & ~leg

    # flow (scales point down it): toward the tail along the body, back along the head, down the legs, out the arms
    flow = sp["T"].copy()
    flow[headside] = DH.FRAME.hx_dir(np.array((0.0, 1.0, 0.0)))
    flow[leg] = (0, 0, -1.0)
    flow[arm] = np.stack([np.sign(P[arm, 0]), np.zeros(arm.sum()), np.zeros(arm.sum())], 1)
    flow = _tangent(flow, N)

    # scale size by region: with the section's size along the body, small on the face, legs, toes and arms
    size = np.clip(0.06 * np.sqrt(np.maximum(sp["a"], (sp["b"] + sp["c"]) / 2) / 0.5), 0.03, 0.08)
    size = np.where(headside, 0.026, size)
    size = np.where(leg, 0.036, size)
    size = np.where(toe, 0.022, size)
    size = np.where(arm, 0.034, size)
    h_sc, crev, tint = np.zeros(n), np.ones(n), np.zeros(n)
    sel = np.nonzero(skin)[0]
    hs, cr, ti = scales(P[sel], flow[sel], size[sel])
    h_sc[sel], crev[sel], tint[sel] = hs, cr, ti

    # the belly plates (the gold): along the trunk, neck and tail; across the underside of the jaw
    lim = np.interp(sp["s"], (0.0, 1.8, 2.6, sp["s_end"]), (1.8, 1.8, 1.2, 1.3))
    k_belly = smoothstep(0.30, 0.62, sp["ventral"]) * smoothstep(lim, lim - 0.3, sp["e"])
    frac = sp["phase"] % 1.0
    crown = np.clip(1 - (sp["u"] / sp["a"]) ** 2, 0, 1) ** 0.25
    plate = smoothstep(0.0, 0.10, frac) * (0.5 + 0.5 * frac) * (0.7 + 0.3 * crown)
    groove = 1 - smoothstep(0.0, 0.10, frac)
    jb = DH.at(DH.JAW, Ph[:, 1], 3)
    k_jaw = smoothstep(jb + 0.10, jb + 0.03, Ph[:, 2]) * (Ph[:, 2] < DH.lip(Ph[:, 1]) - 0.05)
    jfrac = (Ph[:, 1] / 0.065) % 1.0
    k_belly = np.where(headside, k_jaw, k_belly)
    plate = np.where(headside, smoothstep(0.0, 0.12, jfrac) * (0.5 + 0.5 * jfrac), plate)
    groove = np.where(headside, 1 - smoothstep(0.0, 0.12, jfrac), groove)
    k_belly = np.where(skin & ~leg & ~arm, k_belly, 0.0)
    mouth = part == PART["mouth"]
    k_belly[mouth] = 0.0

    kp = smoothstep(0.2, 0.7, k_belly)                    # the plates take over well before the gold is full
    height = np.where(skin, h_sc * (1 - kp) + plate * kp, 0.0)
    height[mouth] = 0.15 * fbm(P[mouth] / 0.03, 2, seed=3)

    # dorsal shade: darker down the top line of the neck, back and tail
    dorsal = np.where(headside, smoothstep(0.15, 0.35, Ph[:, 2]) * 0.6,
                      smoothstep(0.45, 0.95, sp["v"] / np.maximum(sp["b"], 1e-3)))
    dorsal = np.where(skin & ~leg & ~arm, dorsal, 0.0)

    # horns: rings by the position along each horn; spikes and claws a fine grain
    horn = part == PART["horn"]
    claw = part == PART["claw"]
    ht = np.full(n, 0.6)
    hsel = np.nonzero(horn)[0]
    if len(hsel):
        best = np.full(len(hsel), 9.0)
        for s_, sfx in DB.SIDES:
            rows = [(*DB._m(DB.hk(p), s_), p[3] * DB.HEAD_K) for p in DB.HORN]
            t, dist = BP.polyline_t(P[hsel], rows)
            m = dist < best
            ht[hsel[m]] = t[m]
            best[m] = dist[m]
        on_horn = best < 0.18
        rings = 0.5 + 0.5 * np.cos(2 * np.pi * ht[hsel] * 18)
        grain = fbm(P[hsel] / 0.02, 2, seed=5)
        height[hsel] = np.where(on_horn, 0.55 * smoothstep(0.25, 0.75, rings) + 0.15 * grain, 0.25 * grain)
        ht[hsel[~on_horn]] = 0.75
    csel = np.nonzero(claw)[0]
    height[csel] = 0.2 * fbm(P[csel] / 0.015, 2, seed=6)
    tongue = part == PART["tongue"]
    height[tongue] = 0.35 * smoothstep(0.2, 0.8, fbm(P[tongue] / 0.012, 2, seed=8) * 0.5 + 0.5)

    # eyes: radial position in the almond
    eye = (part == PART["eye"]) | (part == PART["pupil"])
    Pm = Ph.copy()
    Pm[:, 0] = np.abs(Pm[:, 0])
    eu, ev, ew = DH._eye_local(Pm)
    er = np.sqrt((eu / DH.EYE["A"]) ** 2 + (ev / DH.EYE["B"]) ** 2)

    # frills: veins fanning from the base
    frill = part == PART["frill"]
    rel = Pm - np.array(DH.FRILL_BASE)
    th = np.arctan2(rel[:, 2], rel[:, 1])
    fv = np.abs(np.cos(th * 9 + 0.6 * fbm(Pm / 0.12, 2, seed=9)))
    vein_f = smoothstep(0.80, 0.98, fv) * frill
    height[frill] = 0.6 * vein_f[frill]

    F.update(skin=skin, headside=headside, leg=leg, toe=toe, arm=arm, crev=crev, tint=tint, k_belly=k_belly, kp=kp,
             groove=groove, height=height, dorsal=dorsal, horn=horn, claw=claw, ht=ht, eye=eye, er=er,
             pupil=part == PART["pupil"], tongue=tongue, tooth=part == PART["tooth"], mouth=mouth, frill=frill,
             vein_f=vein_f, Ph=Ph)
    return F


# ----------------------------------------------------------------------------------------- painting
def _mix(a, b, t):
    t = np.clip(np.asarray(t, float), 0, 1)[..., None]
    return a * (1 - t) + b * t


def paint_body(F, preset):
    """-> (colour (H, W, 3), smoothness (H, W), height (H, W)) for a preset (dict of hex colours)."""
    C = {k: _c(v) for k, v in preset.items()}
    n = len(F["P"])
    col = np.zeros((n, 3))
    sm = np.full(n, SMOOTH["skin"])
    skin = F["skin"]

    # skin: back to belly, each scale a little lighter or darker, darker in the crevices and down the top line
    base = _mix(C["back"], C["belly"], F["k_belly"])
    base = _mix(base, C["back_dark"], F["dorsal"] * 0.55)
    sc = 1 - F["kp"]                                        # the scales' shading fades out under the plates
    base = base * (1 + sc * (0.20 * F["tint"] - 0.10))[:, None]
    base = base * (1 - sc * 0.28 * (1 - F["crev"]))[:, None]
    base = _mix(base, C["belly_edge"], F["k_belly"] * F["groove"] * 0.8)
    col[skin] = base[skin]
    sm[skin] = (SMOOTH["skin"] * (1 - F["k_belly"]) + SMOOTH["belly"] * F["k_belly"])[skin]
    m = F["mouth"]
    col[m] = C["mouth"] * (0.85 + 0.15 * F["tint"][m, None])
    sm[m] = SMOOTH["mouth"]

    h = F["horn"]                                            # horns: lighter base to a dark tip
    col[h] = _mix(np.broadcast_to(C["horn_base"], (h.sum(), 3)), C["horn_tip"], F["ht"][h] ** 0.7)
    col[h] *= (0.85 + 0.3 * F["height"][h])[:, None]
    sm[h] = SMOOTH["horn"]
    c = F["claw"]
    col[c] = C["claw"] * (0.9 + 0.4 * F["height"][c, None])
    sm[c] = SMOOTH["claw"]
    t = F["tooth"]
    col[t] = C["tooth"]
    sm[t] = SMOOTH["tooth"]
    t = F["tongue"]
    col[t] = C["tongue"] * (0.85 + 0.3 * F["height"][t, None])
    sm[t] = SMOOTH["tongue"]

    e = F["eye"]                                             # amber iris, darker toward the rim, a slit pupil
    col[e] = _mix(np.broadcast_to(C["eye"], (e.sum(), 3)), C["eye_dark"], smoothstep(0.35, 1.0, F["er"][e]))
    col[F["pupil"]] = _c("0c0806")
    sm[e] = SMOOTH["eye"]

    f = F["frill"]
    col[f] = _mix(np.broadcast_to(C["membrane"], (f.sum(), 3)), C["vein"], F["vein_f"][f] * 0.8)
    sm[f] = SMOOTH["frill"]

    col *= (0.55 + 0.45 * np.clip(F["ao"], 0, 1))[:, None]
    H, W = F["shape"]
    out = np.zeros((H * W, 3))
    out[F["idx"]] = np.clip(col, 0, 1)
    s2 = np.zeros(H * W)
    s2[F["idx"]] = sm
    h2 = np.zeros(H * W)
    h2[F["idx"]] = F["height"]
    return out.reshape(H, W, 3), s2.reshape(H, W), h2.reshape(H, W)


def wing_fields(D):
    valid = D["valid"]
    idx = np.nonzero(valid.ravel())[0]
    P = D["P"].reshape(-1, 3)[idx].astype(np.float64)
    ao = D["ao"].ravel()[idx]
    side = np.sign(P[:, 0])
    X = np.abs(P[:, 0])
    W = DB.WING
    kn, el = np.array(W["knu"]), np.array(W["elb"])
    centre = np.where((X > kn[0] - 0.4)[:, None], kn, el)
    rel = np.stack([X, P[:, 1]], 1) - centre[:, :2]
    r = np.linalg.norm(rel, axis=1)
    th = np.arctan2(rel[:, 1], rel[:, 0])
    Q = np.stack([X, P[:, 1], P[:, 2]], 1)
    wob = 0.5 * fbm(Q / 0.45, 3, seed=21)
    main = np.abs(np.sin(th * 13 + wob))                       # veins fanning from the knuckle (and the elbow)
    vein = smoothstep(0.10, 0.0, main) * smoothstep(0.15, 0.6, r)
    fine = smoothstep(0.80, 0.97, np.abs(fbm(Q / 0.18, 3, seed=22)))  # finer branching network
    vein = np.maximum(vein, 0.45 * fine)
    wrinkle = fbm(Q / 0.08, 2, seed=23)
    height = 0.7 * vein + 0.08 * wrinkle
    return dict(idx=idx, ao=ao, vein=vein, height=height, shape=valid.shape, P=P)


def paint_wing(F, preset):
    C = {k: _c(v) for k, v in preset.items()}
    col = _mix(np.broadcast_to(C["membrane"] * 1.08, (len(F["idx"]), 3)), C["vein"], F["vein"])
    col *= (0.65 + 0.35 * np.clip(F["ao"], 0, 1))[:, None]
    H, W = F["shape"]
    out = np.zeros((H * W, 3))
    out[F["idx"]] = np.clip(col, 0, 1)
    s2 = np.zeros(H * W)
    s2[F["idx"]] = SMOOTH["membrane"]
    h2 = np.zeros(H * W)
    h2[F["idx"]] = F["height"]
    return out.reshape(H, W, 3), s2.reshape(H, W), h2.reshape(H, W)


# ----------------------------------------------------------------------------------------- build
def build(size=2048, wing_size=1024, presets=("rust", "ash", "bronze"), unwrap=True):
    """UVs, bakes, the presets' albedos and the normal maps into textures/; the game materials M_Dragon and
    M_DragonWing (the first preset) on DragonBody and DragonWingMembrane. -> report"""
    ob = bpy.data.objects["DragonBody"]
    om = bpy.data.objects["DragonWingMembrane"]
    rep = {}
    if unwrap:
        rep["islands"] = unwrap_body(ob)
        unwrap_membrane(om)
    D = BP.bake_data(ob, size=size)
    rep["coverage"] = float(D["valid"].mean())
    F = body_fields(D)
    nrm, paths = None, []
    for p in presets:
        col, sm, hgt = paint_body(F, PRESETS[p])
        if nrm is None:
            path, nrm = BP.write_normal_map(D, hgt, "T_Dragon_Normal", strength=RELIEF)
            paths.append(path)
        name = "T_Dragon" if p == presets[0] else "T_Dragon_" + p.title()
        paths.append(BP.write_texture(D, col, sm, name, ob if p == presets[0] else None, "M_Dragon", normal=nrm))
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
    for obn, mat, tex in (("DragonBody", "M_Dragon", "T_Dragon"), ("DragonWingMembrane", "M_DragonWing", "T_DragonWing")):
        fn = tex if name == "rust" else tex + "_" + name.title()
        path = os.path.join(beast_common.ROOT, "textures", fn + ".png")
        img = bpy.data.images.load(path, check_existing=True)
        m = bpy.data.materials[mat]
        node = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and
                    n.image.colorspace_settings.name != 'Non-Color')
        node.image = img
