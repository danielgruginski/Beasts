"""The hydra's head (2026-10-17), one design for all three necks. Daniel chose three heads and kept the blockout's
proportions ("Three heads is better, I think. The proportions are good"); the brief: "Like the dragon, but more
aquatic like, no spikes, no wings".

An eel's or a gharial's head more than the dragon's wedge: long and low, the snout tapering gently to a rounded tip,
a long gape (the corner of the mouth far back) lined with needle teeth, the eyes high on the sides and the nostrils
on top near the tip (a swimmer's), soft bulges over the eyes, a low smooth crest down the skull, round cheeks, and
rounded gill fins behind the jaw. No horns, no spikes.

Built like dragon_head: one distance field (every part melted into the next), the mouth a slit cut into it with the
upper lip hanging over the lower jaw, meshed at 1 cm and decimated, weights split along the slit and blended behind
its corners (the masseter). Generic pieces come from dragon_head (profiles, meshing, decimation).

Head space: metres, the poll (the neck's end) at the origin, the snout toward -Y, left +X -- hydra_body's local head
frame (head_matrix places it on each neck).
"""
import math
import numpy as np
import bmesh
from mathutils import Vector

from beast_common import cone, loft, smoothstep
from ooze_body import smin, smax, sd_capsule, sd_ellipsoid
import dragon_head as DH
from dragon_head import _profile, sd_profile, at

VOXEL = 0.010
TARGET_TRIS = 5000                  # per head; three of them

# ----------------------------------------------------------------------------------------- the upper head
CRANIUM = ((0.0, -0.10, 0.04), (0.24, 0.32, 0.20))
# the snout: y, half width, top, lip (its underside = the mouth line)
MUZZLE_KEYS = (
    (-0.10, 0.235, 0.205, -0.068),
    (-0.30, 0.225, 0.185, -0.074),
    (-0.50, 0.200, 0.158, -0.079),
    (-0.70, 0.170, 0.133, -0.080),
    (-0.85, 0.150, 0.114, -0.078),
    (-0.97, 0.128, 0.096, -0.073),
    (-1.05, 0.094, 0.077, -0.066),
    (-1.10, 0.040, 0.046, -0.056),       # a rounded tip
)
MUZZLE_ROUND = (0.85, 0.032)        # top: fraction of the section (round); the lip edge: metres (crisp)
BROW = ((0.15, -0.16, 0.19), (0.17, -0.42, 0.155), 0.050, 0.030)     # a soft bulge over each eye
CREST = ((0.0, -0.58, 0.15), (0.0, 0.10, 0.215), 0.022, 0.040)       # a low ridge down the middle of the skull
JOWL = ((0.18, -0.05, -0.02), (0.11, 0.18, 0.13))                   # round cheeks behind the mouth's corner
NOSTRIL = ((0.058, -0.97, 0.072), (0.034, 0.042, 0.026))            # a raised rim on top near the tip ...
NOSTRIL_HOLE = ((0.062, -0.99, 0.088), (0.015, 0.022, 0.013))       # ... and the hole, opening up and forward
STUB = ((0.0, 0.0, 0.0), (0.0, 0.25, -0.04), 0.22)                  # into the neck
EYE = dict(c=(0.198, -0.30, 0.118), axis=(0.0, 1.0, 0.15), n=(0.80, -0.28, 0.53), A=0.074, B=0.054,
           lid=(0.020, 0.015), socket=(0.068, 0.049, 0.058), ball=(0.068, 0.049, 0.040), ball_out=0.016)

# ----------------------------------------------------------------------------------------- the lower jaw
JAW_KEYS = (
    (0.05, 0.200, -0.060, -0.255),
    (-0.10, 0.215, -0.066, -0.275),
    (-0.30, 0.200, -0.074, -0.265),
    (-0.55, 0.175, -0.080, -0.238),
    (-0.80, 0.146, -0.080, -0.210),
    (-0.98, 0.116, -0.074, -0.188),
    (-1.06, 0.082, -0.066, -0.170),
    (-1.09, 0.040, -0.058, -0.150),
    (0.20, 0.150, -0.072, -0.220),       # behind the hinge it tapers into the throat
    (0.32, 0.070, -0.090, -0.180),
)
JAW_ROUND = (0.030, 0.60)
Y_CORNER = -0.16                    # a long gape: the slit ends far back
GAP = (0.016, 0.005)
LIP_HANG = 0.022
LIP_CLEAR = 0.012
HINGE = (0.0, -0.02, -0.08)         # the Jaw bone: hinge -> chin
CHIN_TIP = (0.0, -1.08, -0.15)
MOUTH = (0.0, -1.05, -0.07)         # Socket_Mouth (a bite, a spit)

# ----------------------------------------------------------------------------------------- shells
# needle teeth: (y, length, radius, shows) along the lips; the front ones hang outside the jaw and show shut
UPPER_TEETH = [(-1.03, 0.045, 0.012, True), (-0.97, 0.070, 0.016, True), (-0.90, 0.050, 0.013, True)] + \
    [(-0.83 + 0.065 * k, 0.040 - 0.002 * k, 0.011, False) for k in range(10)]
LOWER_TEETH = [(-1.01, 0.040, 0.011), (-0.94, 0.060, 0.015)] + [(-0.87 + 0.065 * k, 0.036 - 0.0018 * k, 0.010)
                                                                for k in range(10)]
# the gill fin behind each jaw: a rounded, pleated fan (a fish's, not a frill of spines): its root along the back of
# the cheek, opening back and out over an arc, the edge gently scalloped; sea green at the root, coral at the edge
GILL = dict(root=(0.19, 0.04, -0.03), back=(0.50, 0.87, 0.0), up=(0.0, 0.0, 1.0), radius=0.36,
            arc=(-75.0, 70.0), pleats=5, pleat=0.022)

COL = dict(back="1f4a44", belly="c9c08a", mouth="5a2a2a", tooth="e8e2cc", eye="e8d040", pupil="0c0a06",
           gill="c06a58", fin="2f6e66", tongue="8a4a44")

MUZZLE = _profile(MUZZLE_KEYS)
LIP = MUZZLE.copy()
LIP[:, 3] -= LIP_HANG
JAW = _profile(JAW_KEYS)
JAW[:, 2] = np.where(JAW[:, 0] <= Y_CORNER, np.interp(JAW[:, 0], MUZZLE[:, 0], MUZZLE[:, 3]) + 0.003, JAW[:, 2])


def lip(y):
    return at(MUZZLE, y, 3)


def gap(y):
    return GAP[1] + (GAP[0] - GAP[1]) * smoothstep(Y_CORNER, Y_CORNER - 0.12, y)


# ----------------------------------------------------------------------------------------- the field
def _eye_axes(side=1):
    n = np.array(EYE["n"], float) * (side, 1, 1)
    n /= np.linalg.norm(n)
    a = np.array(EYE["axis"], float) * (side, 1, 1)
    a -= n * (a @ n)
    a /= np.linalg.norm(a)
    return a, np.cross(n, a), n


def _eye_local(P, side=1):
    a, b, n = _eye_axes(side)
    q = P - np.array(EYE["c"], float) * (side, 1, 1)
    return q @ a, q @ b, q @ n


def _sd_lids(Pm):
    u, v, w = _eye_local(Pm)
    A, B = EYE["A"], EYE["B"]
    r = np.sqrt(u * u + v * v)
    e = np.sqrt((u / A) ** 2 + (v / B) ** 2)
    radial = r * (1 - 1 / np.maximum(e, 1e-6))
    t = np.where(v > 0, EYE["lid"][0], EYE["lid"][1])
    return np.sqrt(radial ** 2 + w ** 2) - t


def parts(P):
    Pm = P.copy()
    Pm[..., 0] = np.abs(Pm[..., 0])
    up = sd_ellipsoid(P, *CRANIUM)
    up = smin(up, sd_profile(P, MUZZLE, *MUZZLE_ROUND), 0.10)
    a, b, ra, rb = BROW
    up = smin(up, sd_capsule(Pm, np.array(a), np.array(b), ra, rb), 0.07)
    a, b, ra, rb = CREST
    up = smin(up, sd_capsule(P, np.array(a), np.array(b), ra, rb), 0.06)
    up = smin(up, sd_ellipsoid(Pm, *JOWL), 0.08)
    up = smin(up, sd_ellipsoid(Pm, *NOSTRIL), 0.03)
    up = smin(up, sd_capsule(P, np.array(STUB[0]), np.array(STUB[1]), STUB[2]), 0.10)
    y = P[..., 1]
    outside = at(JAW, y, 1) + LIP_CLEAR - np.abs(P[..., 0])
    flap = smax(sd_profile(P, LIP, *MUZZLE_ROUND), outside, 0.005)
    flap = smax(flap, y - Y_CORNER, 0.03)
    up = smin(up, flap, 0.015)
    lo = sd_profile(P, JAW, *JAW_ROUND)
    lids = _sd_lids(Pm)
    z = P[..., 2]
    slit = np.maximum(np.abs(z - lip(y)) - gap(y) / 2, y - Y_CORNER)
    slit = np.maximum(slit, np.abs(P[..., 0]) - (at(JAW, y, 1) + LIP_CLEAR - 0.004))
    nostril = sd_ellipsoid(Pm, *NOSTRIL_HOLE)
    socket = sd_ellipsoid(np.stack(_eye_local(Pm), -1), (0, 0, 0), EYE["socket"])
    k_ul = 0.004 + 0.020 * smoothstep(Y_CORNER - 0.05, Y_CORNER + 0.05, y) + 0.05 * smoothstep(-0.02, 0.18, y)
    return dict(up=up, lo=lo, lids=lids, slit=slit, nostril=nostril, socket=socket, k_ul=k_ul)


def combine(p):
    skin = smin(p["up"], p["lo"], p["k_ul"])
    skin = smin(skin, p["lids"], 0.018)
    d = smax(skin, -p["nostril"], 0.012)
    d = smax(d, -p["socket"], 0.015)
    return smax(d, -p["slit"], 0.005)


def head_field(P):
    return combine(parts(P))


# ----------------------------------------------------------------------------------------- mesh
def _dec_weight(P):
    """Keep the lips' edges (a collapse across the slit stretches into a curtain when the jaw opens), and a little
    more round the eyes and nostrils."""
    y, z = P[:, 1], P[:, 2]
    near_slit = (y < Y_CORNER + 0.04) & (np.abs(z - lip(y)) < gap(y) / 2 + LIP_HANG + 0.015)
    jaw = (z < lip(y)) & (y < 0.05)
    Pm = np.abs(P) * (1, 0, 0) + P * (0, 1, 1)
    u, v, w = _eye_local(Pm)
    near_eye = np.sqrt((u / (EYE["A"] * 1.6)) ** 2 + (v / (EYE["B"] * 2.2)) ** 2 + (w / 0.06) ** 2) < 1
    near_nose = np.linalg.norm((Pm - np.array(NOSTRIL[0])) / 0.08, axis=1) < 1
    hw = at(JAW, y, 1)
    slit_end = (y < Y_CORNER) & (np.abs(z - lip(y)) < gap(y) / 2 + 0.015) & \
        (np.abs(P[:, 0]) > hw - 0.02) & (np.abs(P[:, 0]) < hw + LIP_CLEAR + 0.010)
    return np.where(slit_end, 0.0, np.where(near_slit, 0.15, np.where(near_eye | near_nose | jaw, 0.4, 1.0)))


def build_head_mesh(target=TARGET_TRIS, field=None):
    """The melted head in head space: sampled at 1 cm, meshed, smoothed a little, decimated. -> (bmesh, dense tris)"""
    V, F = DH._mesh_field(field or head_field, (-0.40, -1.20, -0.36), (0.40, 0.42, 0.34), voxel=VOXEL)
    bm = DH._bm_from(V, F)
    for _ in range(2):
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.3, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    return DH._decimate(bm, target, _dec_weight)


def bridges(bm):
    """Faces in front of the mouth's corner with corners on both lips (should be none)."""
    out = 0
    for f in bm.faces:
        P = np.array([v.co[:] for v in f.verts])
        if (P[:, 1] < Y_CORNER - 0.06).all() and np.abs(P[:, 0]).mean() < at(JAW, P[:, 1], 1).mean():
            side = P[:, 2] - lip(P[:, 1])
            if side.max() > 0.25 * gap(P[:, 1]).min() and side.min() < -0.25 * gap(P[:, 1]).min():
                out += 1
    return out


# ----------------------------------------------------------------------------------------- weights, colours
def jaw_weight(P):
    """In front of the corner: whichever half of the field the point is on; behind it the cheek (masseter) follows
    the jaw more toward its lower edge, fading out toward the hinge (dragon_head.jaw_weight)."""
    y, z = P[:, 1], P[:, 2]
    front = smoothstep(Y_CORNER + 0.08, Y_CORNER - 0.02, y)
    p = parts(P)
    on_jaw = smoothstep(-0.006, 0.006, p["up"] - p["lo"])
    mouth_line = lip(np.minimum(y, Y_CORNER))
    cheek = smoothstep(mouth_line - 0.015, at(JAW, y, 3) + 0.04, z)
    fade = smoothstep(HINGE[1] + 0.05, HINGE[1] - 0.12, y)
    return np.clip(front * on_jaw + (1 - front) * cheek * fade, 0, 1)


def head_colors(P, rgb):
    y, z = P[:, 1], P[:, 2]
    mouth = (y < Y_CORNER + 0.02) & (np.abs(np.abs(z - lip(y)) - gap(y) / 2) < 0.006) & \
        (np.abs(P[:, 0]) < at(JAW, y, 1) - 0.02)
    k = smoothstep(at(JAW, y, 3) + 0.08, at(JAW, y, 3) + 0.02, z) * (z < lip(y) - 0.03)
    k = np.maximum(k, smoothstep(0.02, -0.12, z) * (y > Y_CORNER))          # the throat behind the jaw
    back, belly = np.array(rgb(COL["back"])), np.array(rgb(COL["belly"]))
    return [rgb(COL["mouth"]) if mouth[i] else tuple(back * (1 - k[i]) + belly * k[i]) for i in range(len(P))]


# ----------------------------------------------------------------------------------------- shells
def build_teeth(bm, upper=True):
    teeth = UPPER_TEETH if upper else [(y, L, r, False) for y, L, r in LOWER_TEETH]
    for s in (1, -1):
        for y, L, r, shows in teeth:
            lz, g = float(lip(y)), float(gap(y)) / 2
            if upper:
                x = s * ((float(at(MUZZLE, y, 1)) - 0.016) if shows else (float(at(JAW, y, 1)) - 0.045))
                base, tip = (x, y, lz + g + 0.02), (x * 1.01, y + 0.008, lz - L)
            else:
                x = s * (float(at(JAW, y, 1)) - 0.040)
                base, tip = (x, y, lz - g - 0.02), (x, y - 0.006, lz + L)
            cone(bm, base, tip, r, seg=5, bend=(0, 0.25 * L, 0))


def build_tongue(bm):
    def z(y):
        return float(lip(y) - gap(y) / 2) - 0.015
    rows = [(0, -0.20, z(-0.20), 0.09, 0.02, 0.02), (0, -0.55, z(-0.55), 0.07, 0.02, 0.02),
            (0, -0.85, z(-0.85), 0.05, 0.018, 0.018)]
    loft(bm, rows, up=(0, 0, 1), seg=8, per_seg=3, cap0=0.4, cap1=0.9)


def build_gill(bm, s, n_r=6, n_a=36):
    """The gill fin: a fan from its root over GILL's arc, pleated (waves across the fan, growing outward), the edge
    rounded and gently scalloped between the pleats. -> per-vertex 0 (root) .. 1 (edge), for the colour"""
    G = GILL
    root = np.array(G["root"]) * (s, 1, 1)
    d1 = np.array(G["back"], float) * (s, 1, 1)
    d1 /= np.linalg.norm(d1)
    d2 = np.array(G["up"], float)
    d2 -= d1 * (d1 @ d2)
    d2 /= np.linalg.norm(d2)
    nrm = np.cross(d1, d2)
    a0, a1 = (math.radians(a) for a in G["arc"])
    out, rings = [], []
    vr = bm.verts.new(Vector(root))
    out.append(0.0)
    for i in range(1, n_r + 1):
        u = i / n_r
        ring = []
        for j in range(n_a + 1):
            v = j / n_a
            th = a0 + (a1 - a0) * v
            wave = math.sin(v * math.pi * 2 * G["pleats"])
            R = G["radius"] * (0.92 + 0.08 * abs(math.cos(v * math.pi * G["pleats"]))) * (0.75 + 0.25 * math.sin(math.pi * v))
            p = root + R * u * (math.cos(th) * d1 + math.sin(th) * d2) + nrm * G["pleat"] * wave * u ** 1.3
            ring.append(bm.verts.new(Vector(p)))
            out.append(u)
        rings.append(ring)
    for j in range(n_a):
        bm.faces.new((vr, rings[0][j], rings[0][j + 1]))
    for i in range(n_r - 1):
        for j in range(n_a):
            bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]))
    return out


def build_eye(bm, s):
    """The eyeball under the lids. -> pupil flags (a round-ish pupil, a little upright)"""
    a, b, n = _eye_axes(s)
    ra, rb, rn = EYE["ball"]
    centre = np.array(EYE["c"], float) * (s, 1, 1) + n * (EYE["ball_out"] - rn)
    tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=20, v_segments=12, radius=1.0)
    M = np.stack([a * ra, b * rb, n * rn], 1)
    pupil, vmap = [], {}
    for v in tmp.verts:
        p = np.array(v.co[:])
        vmap[v] = bm.verts.new(Vector(centre + M @ p))
        pupil.append(abs(p[0]) < 0.22 and abs(p[1]) < 0.42 and p[2] > 0.3)
    for f in tmp.faces:
        bm.faces.new([vmap[v] for v in f.verts])
    tmp.free()
    return pupil


# ----------------------------------------------------------------------------------------- assembly
_SKIN = {}


def skin(rgb, rebuild=False):
    """The melted head (head space), built once and shared by every neck. -> dict(V, F, jaw, colours, report)"""
    if rebuild or not _SKIN:
        bm, dense = build_head_mesh()
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        V = np.array([v.co[:] for v in bm.verts])
        F = [[v.index for v in f.verts] for f in bm.faces]
        _SKIN.update(V=V, F=F, jaw=jaw_weight(V), cols=head_colors(V, rgb),
                     rep=dict(dense_tris=dense, tris=len(F), bridges=bridges(bm)))
        bm.free()
    return _SKIN


def build(acc, fins, M, nid, rgb):
    """One head into the body's Acc (and its gill fins into `fins`), placed by M (head space -> body), weighted to
    Head<nid> / Jaw<nid>. -> report"""
    S = skin(rgb)
    hb, jb = f"Head{nid}", f"Jaw{nid}"
    W = [{jb: float(w), hb: 1.0 - float(w)} if 0.0 < w < 1.0 else {(jb if w >= 1.0 else hb): 1.0} for w in S["jaw"]]
    _add_arrays(acc, M, S["V"], S["F"], W, S["cols"])

    def shell(target, fn, bone, color):
        tmp = bmesh.new()
        out = fn(tmp)
        n = len(tmp.verts)
        if color == "eye":
            cols = [rgb(COL["pupil"]) if p else rgb(COL["eye"]) for p in out]
        elif color == "gill":                                   # sea green at the root to coral at the edge
            a, b = np.array(rgb(COL["fin"])), np.array(rgb(COL["gill"]))
            cols = [tuple(a * (1 - t) + b * t) for t in (smoothstep(0.35, 1.0, np.array(out)))]
        else:
            cols = [rgb(color)] * n
        _add_bm(target, M, tmp, [{bone: 1.0}] * n, cols)

    shell(acc, lambda bm: build_teeth(bm, True), hb, COL["tooth"])
    shell(acc, lambda bm: build_teeth(bm, False), jb, COL["tooth"])
    shell(acc, build_tongue, jb, COL["tongue"])
    for s in (1, -1):
        shell(acc, lambda bm, s=s: build_eye(bm, s), hb, "eye")
        shell(fins, lambda bm, s=s: build_gill(bm, s), hb, "gill")
    return dict(S["rep"])


def _xf(M, P):
    R = np.array(M.to_3x3())
    t = np.array(M.translation)
    return P @ R.T + t


def _add_arrays(acc, M, V, F, weights, cols):
    Q = _xf(M, V)

    def build(target):
        vmap = [target.verts.new(Vector(q)) for q in Q]
        for f in F:
            try:
                target.faces.new([vmap[i] for i in f])
            except ValueError:
                pass
        return weights
    acc.add(build, None, cols)


def _add_bm(acc, M, bm, weights, cols):
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    V = np.array([v.co[:] for v in bm.verts]).reshape(-1, 3)
    F = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    _add_arrays(acc, M, V, F, weights, cols)
