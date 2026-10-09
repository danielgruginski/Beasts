"""Woolly mammoth: procedural body, built standing (the bind pose), facing -Y, left side +X.

Mammuthus primigenius, a big bull: 3.1 m at the shoulder hump, the back falling steeply to a low rump, a high domed
skull with a dip behind it and the forehead sloping in one line down and forward into a thick trunk root, small furry
ears, a long trunk hanging nearly to the ground, long tusks spiralling down,
out, forward and up with their tips turning in, columnar legs on round feet with toenails, and a short tail with a
tuft. The coat: a cape of long hair over the hump and shoulders, a skirt hanging from the flanks to the knees, a
long hair on the cheeks, a bib at the throat, and shaggy legs.

build_body() -> MammothBody, one mesh:
  - the furred body: lofts and ellipsoids fused by beast_body.fuse_body (head, trunk and the coat's volumes too);
  - separate pieces: the lower lip (on the Jaw bone), the tusks, the eyes, the ears (cupped shells on Ear{L,R}) and
    the coat's hair (beast_coat fringes and clumps).
The head is modelled straight in body space (it is carried high, the face nearly upright).
rest_bones() is the skeleton (Unity Generic rig, the wolf's bone names, 2 tail bones, Trunk1-6 down the trunk).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, dome, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, tri_report, _mx, cup_ear
from beast_coat import coat_loft, volume_bvh, loft_bvh, Snap, build_clumps, loop_anchors, fringe, write_hair_t

# ------------------------------------------------------------------------------------------ landmarks (metres)
# Left-side joints; the right side mirrors x.
J = dict(
    SCAP=(0.400, -0.95, 2.700),     # top of the shoulder blade, under the hump
    SHO=(0.560, -1.22, 2.000),      # shoulder joint
    ELB=(0.580, -0.98, 1.250),      # elbow (behind)
    WRI=(0.560, -1.15, 0.450),      # wrist
    FPAW=(0.560, -1.17, 0.160),     # over the foot pad
    FTOE=(0.560, -1.42, 0.040),     # front of the toenails
    HIP=(0.480, 0.85, 2.000),
    KNEE=(0.570, 0.57, 1.150),      # knee (forward, in the flank)
    HOCK=(0.550, 0.89, 0.450),      # ankle (behind)
    HPAW=(0.550, 0.81, 0.150),
    HTOE=(0.550, 0.57, 0.040),
)
TAIL = [(0, 1.20, 1.98), (0, 1.32, 1.70), (0, 1.37, 1.42)]

# the trunk: centre line top to tip (x, y, z, half width, front radius, back radius); thick at the root, it comes a
# little forward out of the face, hangs, and its tip curls forward. Trunk1-6 run from row to row. It is a separate
# tube with clean rings (fused and decimated, a tube this thin twisted into long diagonal facets). Its root is the
# fused stump: the lower face flaring down into it; below z ~1.98 the stump narrows inside the tube.
TRUNK_ROWS = [(0, -2.38, 2.12, 0.240, 0.215, 0.215), (0, -2.47, 1.74, 0.200, 0.180, 0.180),
              (0, -2.50, 1.32, 0.165, 0.150, 0.150), (0, -2.50, 0.90, 0.135, 0.125, 0.125),
              (0, -2.51, 0.54, 0.112, 0.105, 0.105), (0, -2.58, 0.32, 0.098, 0.092, 0.092),
              (0, -2.71, 0.26, 0.086, 0.078, 0.078)]
TRUNK_UP = (0.0, -0.6, 0.8)                     # the loft's N: the trunk's front (its back where the tip curls)
TRUNK_TOP = (0, -2.28, 2.38, 0.235, 0.210, 0.210)                    # the tube starts inside the face
TRUNK_STUMP = [(0, -2.20, 2.50, 0.320, 0.280, 0.280), (0, -2.32, 2.22, 0.290, 0.250, 0.250),
               (0, -2.40, 1.98, 0.225, 0.200, 0.200), (0, -2.42, 1.86, 0.190, 0.170, 0.170)]   # the flared root

# tusks (left): out of the sockets beside the trunk's root, down and forward, out, forward and up, the tips turning in
TUSK = [(0.200, -2.16, 2.05, 0.112), (0.330, -2.38, 1.66, 0.104), (0.450, -2.62, 1.34, 0.094),
        (0.640, -2.95, 1.20, 0.082), (0.810, -3.30, 1.32, 0.068), (0.800, -3.58, 1.62, 0.054),
        (0.630, -3.72, 1.90, 0.036), (0.430, -3.71, 2.04, 0.018)]
SHEATH = [(0.180, -2.12, 2.24, 0.160), (0.250, -2.27, 1.86, 0.140), (0.300, -2.35, 1.73, 0.126)]   # furry, round
                                                # the tusk's root; the tusk comes out of its lower end

EYE0 = np.array((0.330, -2.16, 2.400))          # eye (left), before it is snapped onto the head
EYE_N = np.array((0.75, -0.55, 0.15)) / np.linalg.norm((0.75, -0.55, 0.15))
EYE_R = 0.046                                   # stylised: ~2x a mammoth's, so the eyes read in game
EAR_BASE = np.array((0.400, -1.84, 2.640))      # small round furry flaps pressed to the side of the head, hanging back
EAR_TIP = np.array((0.470, -1.72, 2.390))       # (their hollow faces out: seen from the front they lie flat, not a blade)
EAR_PROFILE = ((0.0, 0.080, 0.050), (0.35, 0.110, 0.058), (0.70, 0.098, 0.050), (0.93, 0.052, 0.030))
HINGE = (0.0, -1.72, 2.02)                      # jaw hinge, hidden in the cheek
LM = {}


def ear_rows(s):
    m = np.array((s, 1, 1))
    return EAR_BASE * m, EAR_TIP * m


# ------------------------------------------------------------------------------------------ coat volumes
# (y, z centre, half width, up radius, down radius); keep the centre lines level (a rising one tilts the rings)
SKIRT = dict(rows=[(-1.30, 1.74, 0.66, 0.40, 0.40), (-1.00, 1.72, 0.86, 0.45, 0.48), (-0.50, 1.70, 0.92, 0.45, 0.50),
                   (0.05, 1.68, 0.90, 0.45, 0.48), (0.55, 1.68, 0.82, 0.45, 0.46), (0.95, 1.70, 0.70, 0.42, 0.42),
                   (1.20, 1.74, 0.50, 0.36, 0.36)], cap0=0.5, cap1=0.5, shape=0.80)   # hanging from the flanks


# ------------------------------------------------------------------------------------------ parts
def build_trunk(bm):
    rows = [  # y, z centre, half width, up radius, down radius: short and deep, a high narrow hump over the
              # shoulders, the back falling in one long slope to a low rump
        (-1.45, 2.05, 0.55, 0.62, 0.55),
        (-1.20, 2.05, 0.74, 0.86, 0.70),
        (-0.85, 2.02, 0.82, 1.10, 0.74),
        (-0.45, 1.98, 0.85, 0.98, 0.72),
        (-0.05, 1.94, 0.84, 0.84, 0.70),
        (0.35, 1.90, 0.80, 0.68, 0.66),
        (0.70, 1.86, 0.72, 0.52, 0.62),
        (1.00, 1.82, 0.60, 0.38, 0.54),
        (1.22, 1.78, 0.42, 0.24, 0.42),
    ]
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in rows], up=(0, 0, 1), seg=32, cap0=0.6, cap1=0.6)
    loft(bm, *coat_loft(SKIRT))
    neck = [(0, -1.45, 2.30, 0.50, 0.45, 0.55), (0, -1.65, 2.35, 0.45, 0.42, 0.50), (0, -1.80, 2.40, 0.40, 0.38, 0.45)]
    loft(bm, neck, up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.5)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.52, -1.20, 1.95), (0.30, 0.36, 0.45))                   # shoulder
        ellipsoid(bm, (s * 0.50, 0.85, 1.70), (0.32, 0.42, 0.52))                    # thigh
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, (0.075, 0.060, 0.040))]
    loft(bm, tail, up=(0, 1, 0), seg=12, cap0=0.4, cap1=0.8)


def build_head(bm):
    """The high domed skull, the face nearly upright, cheeks, the tusk sheaths either side of the trunk's root and
    the trunk itself, hanging."""
    ellipsoid(bm, (0, -1.92, 2.60), (0.42, 0.44, 0.46), seg=22, rings=14)            # cranium
    ellipsoid(bm, (0, -1.78, 2.92), (0.30, 0.32, 0.26))                               # the dome's peak, high at the back
    ellipsoid(bm, (0, -2.14, 2.44), (0.36, 0.26, 0.56), seg=20, rings=12,
              rot=Matrix.Rotation(math.radians(-35), 3, 'X'))                         # the forehead, sloping forward
    for s in (1, -1):
        ellipsoid(bm, (s * 0.27, -1.98, 2.06), (0.22, 0.32, 0.30))                   # cheek
        ellipsoid(bm, (s * 0.27, -2.12, 2.48), (0.10, 0.10, 0.06))                   # brow over the eye
        loft(bm, [(s * x, y, z, r, r, r) for x, y, z, r in SHEATH], up=(0, -1, 0), seg=14, cap0=0.4, cap1=0.25)
    loft(bm, TRUNK_STUMP, up=TRUNK_UP, seg=18, cap0=0.4, cap1=0.4)                   # the trunk's flared root


FRONT_LEG = [(0.55, -1.20, 2.05, 0.34, 0.36, 0.36), (0.57, -1.12, 1.60, 0.31, 0.32, 0.32),
             (0.58, -1.05, 1.25, 0.28, 0.27, 0.30), (0.57, -1.10, 0.90, 0.25, 0.24, 0.25),
             (0.56, -1.14, 0.55, 0.23, 0.23, 0.22), (0.56, -1.16, 0.30, 0.235, 0.24, 0.22),
             (0.56, -1.17, 0.12, 0.26, 0.27, 0.24), (0.56, -1.17, 0.04, 0.27, 0.28, 0.25)]
HIND_LEG = [(0.50, 0.88, 1.95, 0.34, 0.38, 0.40), (0.55, 0.75, 1.55, 0.31, 0.33, 0.33),
            (0.57, 0.63, 1.15, 0.27, 0.26, 0.28), (0.56, 0.75, 0.80, 0.23, 0.22, 0.24),
            (0.55, 0.85, 0.45, 0.21, 0.20, 0.22), (0.55, 0.83, 0.25, 0.215, 0.21, 0.21),
            (0.55, 0.81, 0.10, 0.235, 0.24, 0.22), (0.55, 0.81, 0.04, 0.245, 0.25, 0.23)]
FOOT = {'F': (0.56, -1.17, 0.27, 5), 'H': (0.55, 0.81, 0.245, 4)}      # centre x, y, pad radius, toenails


def leg_loft(rows, s):
    return ([(s * r[0],) + r[1:] for r in rows], (0, -1, 0), 18, 4, 0.5, 0.4)


def toenails(kind, s):
    """Toenail centres round the front of a foot (left side when s = 1)."""
    x, y, r, k = FOOT[kind]
    out = []
    for a in np.linspace(-62, 62, k):
        t = math.radians(a)
        out.append(np.array((s * x + r * 0.97 * math.sin(t), y - r * 0.97 * math.cos(t), 0.060)))
    return out


def build_leg(bm, rows, kind, s):
    loft(bm, *leg_loft(rows, s))
    x, y, r, _ = FOOT[kind]
    ellipsoid(bm, (s * x, y, 0.075), (r, r * 1.04, 0.095), seg=20, rings=10)         # the round foot
    for p in toenails(kind, s):
        ellipsoid(bm, tuple(p), (0.050, 0.034, 0.042), seg=10, rings=6)
    if kind == 'F':
        ellipsoid(bm, (s * 0.58, -0.88, 1.25), (0.18, 0.16, 0.18))                   # point of the elbow


# ------------------------------------------------------------------------------------------ hair
LOCKS = [
    # the bib hanging from the throat and chest
    ((0.000, -1.55, 1.62), (0.0, -0.2, -1.0), 0.50, 0.130),
    ((0.280, -1.48, 1.58), (0.3, -0.1, -1.0), 0.45, 0.120),
    # breeches down the backs of the thighs
    ((0.420, 1.18, 1.50), (0.3, 0.5, -1.0), 0.42, 0.120),
    ((0.200, 1.26, 1.58), (0.2, 0.6, -1.0), 0.40, 0.115),
    # the tail's tuft
    ((0.000, 1.38, 1.43), (0.0, 0.2, -1.0), 0.30, 0.070),
    ((0.030, 1.37, 1.48), (0.4, 0.3, -1.0), 0.24, 0.060),
]
FRINGE_LOOPS = [   # (volume, (centre x, centre y, half length, half width, hem z sides / front / back, open gap at
                   #  the front, deg), pitch, outward lean, long and short lengths, thickness, lift)
    (SKIRT, (0.0, -0.05, 1.28, 0.90, 1.70, 1.76, 1.80, 0), 0.22, 0.22, (0.32, 0.50), (0.08, 0.14), 0.065, 0.10),
    (SKIRT, (0.0, -0.05, 1.28, 0.90, 1.24, 1.36, 1.38, 0), 0.22, 0.22, (0.34, 0.56), (0.08, 0.14), 0.070, 0.10),
]                  # with HUMP_STRIPS: three tiers, the hump's hem, mid flank, the skirt's hem
HUMP_STRIPS = [  # the hump's long hair down each flank, rooted on the fused body: (y from .. y to, x, z from .. z to,
                 #  samples, direction, long and short lengths, thickness, lift)
    (-1.42, 0.40, 0.95, 2.02, 2.02, 17, (0.15, 0.15, -1.0), (0.38, 0.60), (0.08, 0.14), 0.065, 0.04),
    # (along the flank's widest line: higher up, where the back turns over, hanging hair stands off as fins)
    (-2.02, -1.58, 0.46, 2.20, 2.28, 9, (0.10, 0.10, -1.0), (0.24, 0.38), (0.05, 0.10), 0.050, 0.06),
    # (the long hair hanging from the cheeks, below the eyes)
]
LEG_STRIPS = [  # shaggy hair down the backs of the legs: (leg, z from .. z to, samples, direction, lengths)
    (FRONT_LEG, 1.10, 0.40, 9, (0.0, 1.0, -0.60), (0.22, 0.36)),          # forearm, elbow to wrist
    (HIND_LEG, 1.05, 0.40, 9, (0.0, 1.0, -0.70), (0.20, 0.32)),           # shin, knee to ankle
]


def _leg_at(rows, z):
    """The leg loft's centre x, y and back radius at height z."""
    zs = np.array([r[2] for r in rows])[::-1]
    return (float(np.interp(z, zs, np.array([r[0] for r in rows])[::-1])),
            float(np.interp(z, zs, np.array([r[1] for r in rows])[::-1])),
            float(np.interp(z, zs, np.array([r[5] for r in rows])[::-1])))


def build_fringes(bm, bvh, seed=9):
    rng = np.random.default_rng(seed)
    root = bm.verts.layers.float_vector["root"]
    vs = []
    for vol, spec, step, dout, longs, shorts, thick, lift in FRINGE_LOOPS:
        A, outs, closed = loop_anchors(spec, step / 2)
        snap = Snap(bvh if vol is None else volume_bvh(vol))
        vs += fringe(bm, snap, A, closed, dout, longs, shorts, thick, lift, rng, root, outs)
    for y0, y1, x, z0, z1, n, d, longs, shorts, thick, lift in HUMP_STRIPS:
        for s in (1, -1):
            A = [Vector((s * x, y, z)) for y, z in zip(np.linspace(y0, y1, n), np.linspace(z0, z1, n))]
            vs += fringe(bm, Snap(bvh), A, False, (s * d[0], d[1], d[2]), longs, shorts, thick, lift, rng, root)
    for rows, z0, z1, n, d, longs in LEG_STRIPS:
        for s in (1, -1):
            A = []
            for z in np.linspace(z0, z1, n):
                x, y, r = _leg_at(rows, z)
                A.append(Vector((s * x, y + r + 0.12, z)))
            vs += fringe(bm, Snap(loft_bvh(leg_loft(rows, s))), A, False, d, longs, (0.05, 0.09), 0.050, 0.20, rng,
                         root)
    return vs


def fur_flow(P, N):
    """Back along the top, hanging down the flanks and legs, down the trunk, back and down off the crown."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    one = np.ones_like(x)
    top = np.stack([0 * x, one, -0.20 * one], -1)
    hang = np.stack([0 * x, 0.20 * one, -one], -1)
    w_top = smoothstep(0.30, 0.80, N[..., 2])
    F = top * w_top[..., None] + hang * (1 - w_top[..., None])
    head = smoothstep(-1.60, -1.75, y)                              # the head: out and down from the crown
    crown = np.stack([x, y + 1.85, z - 3.10], -1)
    crown = crown / np.maximum(np.linalg.norm(crown, axis=-1, keepdims=True), 1e-6)
    F = F * (1 - head[..., None]) + crown * head[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def trunk_t(P):
    """How far down the trunk (0 at its root, 1 at the tip) for points near it; -1 elsewhere."""
    C = np.array([r[:3] for r in TRUNK_ROWS])
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()
    best_d = np.full(len(P), 1e9)
    best_t = np.full(len(P), -1.0)
    for i in range(len(C) - 1):
        a, b = C[i], C[i + 1]
        ab = b - a
        u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(P - (a + np.outer(u, ab)), axis=1)
        better = d < best_d
        best_d = np.where(better, d, best_d)
        best_t = np.where(better, cum[i] + u * (cum[i + 1] - cum[i]), best_t)
    r = np.interp(best_t, cum, np.array([r[3] for r in TRUNK_ROWS]))
    return np.where((best_d < r * 1.6) & (P[:, 2] < 2.10) & (P[:, 1] < -2.15), best_t, -1.0)


def fur_amount(P, N):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    A = np.full(len(P), 0.010)
    A = A + 0.020 * _gauss(P, (0, -0.85, 3.00), (0.60, 0.80, 0.35))                       # hump
    A = A + 0.014 * _gauss(P, (0, -1.90, 3.00), (0.35, 0.35, 0.20))                       # crown
    A = A * (1 - 0.5 * smoothstep(0.35, 0.10, z) * (np.abs(x) > 0.25))                    # shorter on the feet
    tt = trunk_t(P)
    A = np.where(tt >= 0, 0.004 * (1 - tt), A)                                             # short on the trunk
    face = smoothstep(-2.00, -2.20, y) * smoothstep(2.65, 2.40, z) * (tt < 0)
    A = A * (1 - 0.7 * face)
    return A


def sculpt_fur(co, no, seed=17):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed, across=0.11, along_len=0.34)


def sculpt_face(co, no):
    """Eye sockets under the brow."""
    out = co.copy()
    Pm = np.stack([np.abs(co[:, 0]), co[:, 1], co[:, 2]], -1)
    out -= no * (0.020 * _gauss(Pm, EYE0, (0.040, 0.040, 0.032)))[:, None]
    return out


def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face, the trunk and the legs keep relatively more (thinned out, the
    leg cylinders lose their rings and twist into long diagonal facets)."""
    face = co.y < -1.75 and co.z > 1.60
    trunk = co.y < -2.15 and abs(co.x) < 0.25
    leg = co.z < 1.25 and abs(co.x) > 0.28
    foot = co.z < 0.25 and abs(co.x) > 0.25
    return 1.0 - 0.40 * float(face) - 0.30 * float(trunk) - 0.35 * float(leg) - 0.15 * float(foot)


def build_fur_body(voxel=0.012, target_tris=2600, fillet_iters=45):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    for s in (1, -1):
        build_leg(bm, FRONT_LEG, 'F', s)
        build_leg(bm, HIND_LEG, 'H', s)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return beast_body.fuse_body(bm, "MAM", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                dec_weight=_dec_weight, seam_x=0.025, flat_z=0.012, fillet_iters=fillet_iters)


# ------------------------------------------------------------------------------------------ separate pieces
def _snap(bvh, p, n, reach=0.25):
    hit = bvh.ray_cast(Vector(p + n * reach), Vector(-n), reach * 2)[0]
    return np.array(hit) if hit is not None else np.array(p)


def tusk_rows(s):
    return [(s * x, y, z, r, r, r) for x, y, z, r in TUSK]


def build_pieces(low):
    """Lower lip, tusks, eyes, ears and the coat's hair: separate shells (no remesh)."""
    bml = bmesh.new()
    bml.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    bm = bmesh.new()
    bm.verts.layers.float_vector.new("root")      # before any vertex: adding a layer later orphans the BMVerts
    tags = {}
    # the lower lip: pointed, under the trunk's root, its back end in the cheeks
    jaw = [(0, -1.78, 1.88, 0.170, 0.060, 0.100), (0, -1.95, 1.81, 0.145, 0.060, 0.090),
           (0, -2.06, 1.76, 0.110, 0.055, 0.075), (0, -2.12, 1.73, 0.080, 0.045, 0.060)]
    tags['jaw'] = loft(bm, jaw, up=(0, 0, 1), seg=10, per_seg=2, cap0=0.5, cap1=0.6, capk=2, shape=0.85)
    tusks = []
    for s in (1, -1):
        tusks += loft(bm, tusk_rows(s), up=(0, -0.3, 1.0), seg=8, per_seg=3, cap0=0.0, cap1=0.5, capk=2)
    tags['tusk'] = tusks
    tags['proboscis'] = loft(bm, [TRUNK_TOP] + TRUNK_ROWS, up=TRUNK_UP, seg=10, per_seg=2, cap0=0.3, cap1=0.6,
                             capk=2)          # seam (the loft's) down the back
    eyes = []
    for s in (1, -1):
        n = EYE_N * np.array((s, 1, 1))
        c = _snap(bvh, EYE0 * np.array((s, 1, 1)), n, 0.10) - n * 0.004
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        eyes += dome(bm, c, n, EYE_R, 0.012, seg=10, rings=3)
    tags['eye'] = eyes
    ears = []
    for s in (1, -1):
        base, tip = ear_rows(s)
        ears += cup_ear(bm, base, tip, (s * 1.0, -0.35, 0.0), EAR_PROFILE, hollow=0.30)
    tags['ear'] = ears
    tags['hair'] = build_clumps(bm, bvh, LOCKS) + build_fringes(bm, bvh)
    return bm, tags


def build_body(voxel=0.012, target_tris=2600):
    """-> (MammothBody (fur body joined with the pieces, info attribute set), MAM_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    nfur = len(fur.data.vertices)
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "MAM", "MammothBody")
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    write_hair_t(body, PART['hair'], reach=0.55)
    for k, v in LM.items():                      # the painter reads the eyes from here
        body[k] = [float(c) for c in v]
    return body, hi


# ------------------------------------------------------------------------------------------ skeleton
def _frame(head, ydir, zhint):
    y = Vector(ydir).normalized()
    z = Vector(zhint)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    return Vector(head), Matrix((x, y, z)).transposed()


def _bone(B, name, head, tail, zhint, parent, deform=True):
    head, tail = Vector(head), Vector(tail)
    h, fr = _frame(head, tail - head, zhint)
    B[name] = (h, fr, (tail - head).length, parent, deform)


def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform); the wolf's conventions (Root and Motion point up with
    +Z toward the front, Motion carries the root motion; legs and spine bend about their local X). The trunk's
    bones bend about their local X too, +Z toward its front."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.8, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.6, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    _bone(B, "Hips", (0, 0.85, 2.100), (0, 1.20, 1.950), UP, "Root")
    _bone(B, "Spine1", (0, 0.85, 2.150), (0, 0.20, 2.300), UP, "Hips")
    _bone(B, "Spine2", (0, 0.20, 2.300), (0, -0.45, 2.420), UP, "Spine1")
    _bone(B, "Chest", (0, -0.45, 2.420), (0, -1.25, 2.420), UP, "Spine2")
    _bone(B, "Neck1", (0, -1.25, 2.420), (0, -1.50, 2.450), UP, "Chest")
    _bone(B, "Neck2", (0, -1.50, 2.450), (0, -1.68, 2.500), UP, "Neck1")
    _bone(B, "Head", (0, -1.68, 2.500), (0, -2.25, 2.420), UP, "Neck2")
    _bone(B, "Jaw", HINGE, (0, -2.15, 1.710), UP, "Head")
    par = "Head"
    for i in range(len(TRUNK_ROWS) - 1):
        a, b = np.array(TRUNK_ROWS[i][:3]), np.array(TRUNK_ROWS[i + 1][:3])
        t = (b - a) / np.linalg.norm(b - a)
        up = np.array(TRUNK_UP) - t * (np.array(TRUNK_UP) @ t)
        _bone(B, f"Trunk{i + 1}", tuple(a), tuple(b), tuple(up), par)
        par = f"Trunk{i + 1}"
    par = "Hips"
    for i in range(len(TAIL) - 1):
        _bone(B, f"Tail{i + 1}", TAIL[i], TAIL[i + 1], (0, 1, 0.3), par)
        par = f"Tail{i + 1}"
    for s, sfx in ((1, "L"), (-1, "R")):
        m = (lambda p: p) if s > 0 else _mx
        base, tip = ear_rows(s)
        _bone(B, f"Ear{sfx}", tuple(base), tuple(tip), FWD, "Head")
        _bone(B, f"Scapula{sfx}", m(J['SCAP']), m(J['SHO']), FWD, "Chest")
        _bone(B, f"UpperArm{sfx}", m(J['SHO']), m(J['ELB']), FWD, f"Scapula{sfx}")
        _bone(B, f"Forearm{sfx}", m(J['ELB']), m(J['WRI']), FWD, f"UpperArm{sfx}")
        _bone(B, f"FrontPaw{sfx}", m(J['WRI']), m(J['FPAW']), FWD, f"Forearm{sfx}")
        _bone(B, f"FrontToes{sfx}", m(J['FPAW']), m(J['FTOE']), UP, f"FrontPaw{sfx}")
        _bone(B, f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
        _bone(B, f"Shin{sfx}", m(J['KNEE']), m(J['HOCK']), FWD, f"Thigh{sfx}")
        _bone(B, f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), FWD, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
    # sockets (head = attach point; +Y up, +Z forward)
    _bone(B, "Socket_Head", (0, -1.90, 3.080), (0, -1.90, 3.180), FWD, "Head")
    _bone(B, "Socket_Mouth", (0, -2.05, 1.760), (0, -2.05, 1.860), FWD, "Jaw")
    _bone(B, "Socket_Back", (0, -0.70, 3.150), (0, -0.70, 3.250), FWD, "Chest")       # a howdah, a rider
    tip = np.array(TRUNK_ROWS[-1][:3])
    _bone(B, "Socket_Trunk", tuple(tip), tuple(tip + np.array((0, 0, 0.1))), FWD, f"Trunk{len(TRUNK_ROWS) - 1}")
    for s, sfx in ((1, "L"), (-1, "R")):
        p = np.array(TUSK[-1][:3]) * np.array((s, 1, 1))
        _bone(B, f"Socket_Tusk{sfx}", tuple(p), tuple(p + np.array((0, 0, 0.1))), FWD, "Head")
    return B
