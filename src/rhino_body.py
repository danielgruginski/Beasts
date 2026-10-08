"""Woolly rhinoceros (the woods' solo boss): procedural body, built standing (the bind pose), facing -Y, left side +X.

A Coelodonta-style rhino the size of a big bull: a high shoulder hump falling to a lower rump, a long head carried
low, a long flattened front horn swept forward and up and a short second horn between the eyes, small furry ears,
short columnar legs on three-toed feet. A mammoth's coat: a mane and cape over the hump, a shaggy skirt hanging from
the flanks and belly, a bib and beard at the throat, sleeves and breeches on the upper legs, feathering over the feet.
A snapped boar spear stands out of the left shoulder.

build_body() -> RhinoBody, one mesh:
  - the furred body: lofted and ellipsoid parts plus ~90 flattened hair locks, fused by beast_body.fuse_body;
  - separate pieces: the lower jaw (on the Jaw bone), both horns, the eyes, and the spear (split into its own object
    "Spear" after painting, so the game can hide it once the corpse is looted).
No head warp: the head is already a third of the body; only the eyes are stylised (~1.7x a rhino's).
rest_bones() is the skeleton (Unity Generic rig, the wolf's bone names, 3 tail bones, no tongue).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, read_info, tri_report, _mx
from beast_coat import (coat_loft as _coat_loft, volume_bvh as _volume_bvh, loft_bvh as _loft_bvh, Snap as _Snap,
                        Drop as _Drop, clump as _clump, build_clumps, loop_anchors as _loop_anchors, fringe as _fringe,
                        write_hair_t)

# ------------------------------------------------------------------------------------------ landmarks (metres)
# Left-side joints; the right side mirrors x. Hump ~1.75 m (hair ~1.85 m), snout to rump ~3.0 m, horn +0.5 m.
J = dict(
    SCAP=(0.200, -0.56, 1.480),     # top of the shoulder blade, under the hump
    SHO=(0.300, -0.80, 1.060),      # shoulder joint (point of the shoulder)
    ELB=(0.320, -0.56, 0.730),      # elbow, at the belly line
    WRI=(0.310, -0.63, 0.300),      # carpus
    FPAW=(0.310, -0.645, 0.100),    # fetlock, over the toes
    FTOE=(0.310, -0.780, 0.030),    # front of the toes
    HIP=(0.300, 0.78, 1.220),       # hip joint
    KNEE=(0.350, 0.56, 0.780),      # stifle (forward, in the flank)
    HOCK=(0.330, 0.88, 0.420),      # hock (heel)
    HPAW=(0.320, 0.825, 0.100),
    HTOE=(0.320, 0.700, 0.030),
)
TAIL = [(0, 1.08, 1.34), (0, 1.17, 1.22), (0, 1.215, 1.07), (0, 1.230, 0.93)]

# The head is modelled in its own frame ("head space": horizontal, the muzzle toward -Y, the poll at the origin) and
# hung from the poll pitched down 45 degrees, as a rhino carries it. hx() maps head space to the body, hx_inv() back
# (sculpt masks, the painter and the rig's masks work in head space).
HEAD_PIVOT = np.array((0.0, -1.12, 1.40))
HEAD_PITCH = math.radians(45)


def hx(P):
    P = np.asarray(P, float)
    c, s_ = math.cos(HEAD_PITCH), math.sin(HEAD_PITCH)
    y, z = P[..., 1], P[..., 2]
    return np.stack([P[..., 0], y * c - z * s_, y * s_ + z * c], -1) + HEAD_PIVOT


def hx_inv(Q):
    Q = np.asarray(Q, float) - HEAD_PIVOT
    c, s_ = math.cos(HEAD_PITCH), math.sin(HEAD_PITCH)
    y, z = Q[..., 1], Q[..., 2]
    return np.stack([Q[..., 0], y * c + z * s_, -y * s_ + z * c], -1)


def hx_dir(v):
    return hx(v) - HEAD_PIVOT


HINGE_H = (0.0, -0.22, -0.26)                  # jaw hinge (head space), under the ear, hidden in the cheek
HINGE = tuple(hx(HINGE_H))
EYE0_H = np.array((0.174, -0.420, -0.130))      # eye (left, head space), before it is snapped onto its socket
EYE0 = hx(EYE0_H)
EYE_N = hx_dir(np.array((0.88, -0.25, 0.35)) / np.linalg.norm((0.88, -0.25, 0.35)))
EYE_R = 0.032                                   # stylised: ~2x a rhino's, so the eyes read in game


def _horn_rows(base, ang, L, curl, r0, side=0.66):
    """A horn in head space: from `base`, `ang` degrees above the head's forward axis, curling back toward its tip;
    flattened side to side. -> rows (x, y, z, half width, front radius, back radius) in body space."""
    t_ = np.array((0.0, 0.03, 0.14, 0.30, 0.47, 0.64, 0.80, 0.92, 1.0))
    d = np.array((0.0, -math.cos(math.radians(ang)), math.sin(math.radians(ang))))
    back = np.array((0.0, d[2], -d[1]))                  # perpendicular to d, toward the back of the head
    P = hx(np.asarray(base, float) + np.outer(t_ * L, d) + np.outer(curl * L * t_ ** 2, back))
    r = r0 * (1 - t_) ** 0.85 + 0.003
    return [tuple(float(c) for c in p) + (side * ri, ri, ri * 0.96) for p, ri in zip(P, r)]


# front horn: long, flattened side to side, from a broad base on the tip of the nose, swept forward and up (~33
# degrees above level when the head hangs), its tip curling up; the second horn short and upright between the eyes
HORN1 = _horn_rows((0, -0.740, -0.080), 78, 0.82, 0.12, 0.110)
HORN2 = _horn_rows((0, -0.500, -0.050), 100, 0.30, 0.05, 0.080, side=0.72)
# ears: funnels on the poll, standing up and out (a separate shell on Ear{L,R})
_EB = hx((0.125, -0.10, 0.05))
_ED = np.array((0.40, 0.05, 1.0)) / np.linalg.norm((0.40, 0.05, 1.0))
EAR = [tuple(float(c) for c in _EB + _ED * 0.22 * t) + r
       for t, r in ((0.0, (0.060, 0.042, 0.042)), (0.40, (0.062, 0.042, 0.042)), (0.75, (0.046, 0.032, 0.032)),
                    (1.0, (0.012, 0.010, 0.010)))]
# the spear: where it enters the left shoulder (snapped onto the surface) and the way it points out of it
SPEAR_AIM = np.array((0.42, -0.50, 1.42))
SPEAR_DIR = np.array((0.55, 0.62, 0.56)) / np.linalg.norm((0.55, 0.62, 0.56))
LM = {}


# ------------------------------------------------------------------------------------------ parts
# the coat's volumes: (y, z centre, half width, up radius, down radius), box section (shape)
SKIRT = dict(rows=[(-0.90, 0.95, 0.30, 0.25, 0.33), (-0.75, 0.90, 0.46, 0.30, 0.44), (-0.50, 0.88, 0.52, 0.30, 0.44),
                   (-0.20, 0.86, 0.55, 0.30, 0.42), (0.10, 0.86, 0.56, 0.30, 0.42), (0.40, 0.88, 0.54, 0.30, 0.42),
                   (0.65, 0.92, 0.48, 0.30, 0.40), (0.85, 0.98, 0.37, 0.28, 0.36)], cap0=0.5, cap1=0.5, shape=0.65)
CAPE = dict(rows=[(-0.98, 1.30, 0.30, 0.10, 0.30), (-0.86, 1.30, 0.50, 0.34, 0.30), (-0.70, 1.30, 0.58, 0.52, 0.20),
                  (-0.45, 1.30, 0.58, 0.52, 0.16), (-0.20, 1.30, 0.52, 0.42, 0.10), (0.00, 1.30, 0.40, 0.34, 0.05)],
            cap0=0.4, cap1=0.5, shape=0.85)   # a level centre line: a rising one tilts the rings (their tops lean)


def build_trunk(bm):
    rows = [  # y, z centre, half width, up radius, down radius: high shoulders, deep barrel, lower rump
        (-0.950, 1.150, 0.300, 0.320, 0.400),
        (-0.750, 1.180, 0.400, 0.470, 0.480),
        (-0.500, 1.180, 0.460, 0.510, 0.500),
        (-0.200, 1.150, 0.500, 0.410, 0.500),
        (0.100, 1.130, 0.520, 0.340, 0.500),
        (0.400, 1.120, 0.500, 0.330, 0.460),
        (0.700, 1.140, 0.450, 0.330, 0.400),
        (0.950, 1.120, 0.360, 0.290, 0.360),
        (1.120, 1.080, 0.220, 0.220, 0.280),
    ]
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in rows], up=(0, 0, 1), seg=28, cap0=0.6, cap1=0.6)
    ellipsoid(bm, (0, -0.55, 1.58), (0.32, 0.36, 0.26), seg=20, rings=12)            # the hump
    # the coat: a skirt hanging from the lower flanks (box section, hem ~0.47 m up) and a cape of the hump's long
    # hair over the shoulders (hem ~1.14 m up at the sides); fringes along their edges make the ragged hems
    loft(bm, *_coat_loft(SKIRT))
    loft(bm, *_coat_loft(CAPE))
    neck = [(0, -0.80, 1.22, 0.36, 0.38, 0.42), (0, -0.95, 1.22, 0.30, 0.28, 0.34),
            (0, -1.12, 1.24, 0.22, 0.18, 0.26)]
    loft(bm, neck, up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.5)
    ellipsoid(bm, (0, -1.00, 1.02), (0.20, 0.22, 0.18))                              # throat, dewlap
    for s in (1, -1):
        ellipsoid(bm, (s * 0.30, -0.80, 1.08), (0.16, 0.18, 0.22))                   # point of the shoulder
        ellipsoid(bm, (s * 0.30, 0.74, 1.00), (0.20, 0.30, 0.36),
                  rot=Matrix.Rotation(math.radians(-15), 3, 'X'))                     # thigh
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, (0.070, 0.060, 0.050, 0.040))]
    loft(bm, tail, up=(0, 1, 0), seg=14, cap0=0.4, cap1=0.8)


HEAD = [  # head space: (y, z centre, half width, up radius, down radius)
    (0.00, -0.12, 0.170, 0.180, 0.180), (-0.14, -0.21, 0.200, 0.250, 0.250), (-0.30, -0.24, 0.200, 0.240, 0.240),
    (-0.46, -0.235, 0.180, 0.205, 0.205), (-0.56, -0.215, 0.168, 0.180, 0.185), (-0.635, -0.200, 0.160, 0.150, 0.190),
    (-0.665, -0.190, 0.155, 0.140, 0.130), (-0.76, -0.185, 0.150, 0.125, 0.125), (-0.86, -0.200, 0.140, 0.100, 0.100)]


def _to_body(bm, before):
    """Move the vertices added since `before` from head space to the body."""
    new = [v for v in bm.verts if v not in before]
    for v in new:
        v.co = Vector(hx(v.co[:]))
    return new


def build_head(bm):
    # the head, a short deep wedge (head space): the poll and ears at the back, big cheeks over the angle of the
    # jaw, the forehead dipping between the horns, the horn bosses, a broad rounded lip. Behind the mouth corner
    # (y ~ -0.6) it goes down to the jaw line; in front its underside is the upper lip, and the chin and lower lip
    # are a separate piece (on the Jaw bone) tucked under it.
    before = set(bm.verts)
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in HEAD], up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.7, shape=0.75)
    ellipsoid(bm, (0, -0.74, -0.040), (0.110, 0.140, 0.070))                          # front horn boss
    ellipsoid(bm, (0, -0.50, -0.015), (0.080, 0.100, 0.050))                          # second horn boss
    ellipsoid(bm, (0, -0.86, -0.270), (0.130, 0.060, 0.050))                          # the broad upper lip
    for s in (1, -1):
        ellipsoid(bm, (s * 0.150, -0.24, -0.340), (0.070, 0.160, 0.140))              # the angle of the jaw
        ellipsoid(bm, (s * 0.150, -0.40, -0.060), (0.045, 0.075, 0.035))              # brow over the eye
        ellipsoid(bm, (s * 0.120, -0.10, 0.040), (0.070, 0.060, 0.060))               # the ear's root
    _to_body(bm, before)


FRONT_LEG = [(0.300, -0.66, 1.100, 0.170, 0.200, 0.180), (0.320, -0.62, 0.900, 0.170, 0.180, 0.180),
             (0.330, -0.58, 0.700, 0.160, 0.150, 0.170), (0.320, -0.60, 0.520, 0.140, 0.140, 0.130),
             (0.310, -0.62, 0.340, 0.120, 0.120, 0.110), (0.310, -0.63, 0.200, 0.115, 0.120, 0.110),
             (0.310, -0.64, 0.100, 0.125, 0.130, 0.120), (0.310, -0.65, 0.050, 0.135, 0.140, 0.130)]
HIND_LEG = [(0.340, 0.60, 0.880, 0.170, 0.200, 0.220), (0.350, 0.66, 0.700, 0.150, 0.150, 0.200),
            (0.340, 0.76, 0.550, 0.130, 0.110, 0.160), (0.330, 0.86, 0.420, 0.110, 0.090, 0.120),
            (0.320, 0.84, 0.280, 0.110, 0.110, 0.100), (0.320, 0.82, 0.160, 0.110, 0.115, 0.110),
            (0.320, 0.81, 0.080, 0.120, 0.130, 0.120), (0.320, 0.81, 0.050, 0.130, 0.135, 0.125)]


def _leg_loft(rows, s):
    return ([(s * r[0],) + r[1:] for r in rows], (0, -1, 0), 18, 4, 0.5, 0.4)


def build_leg_front(bm, s):
    loft(bm, *_leg_loft(FRONT_LEG, s))
    ellipsoid(bm, (s * 0.330, -0.48, 0.740), (0.100, 0.100, 0.100))                   # point of the elbow
    _foot(bm, s * 0.310, -0.660)


def build_leg_hind(bm, s):
    loft(bm, *_leg_loft(HIND_LEG, s))
    ellipsoid(bm, (s * 0.330, 0.93, 0.440), (0.070, 0.070, 0.080))                   # point of the hock
    _foot(bm, s * 0.320, 0.800)


def _foot(bm, x, y):
    """A round pad with three hoofed toes at the front (the middle one biggest). Soles are flattened later."""
    ellipsoid(bm, (x, y, 0.050), (0.140, 0.150, 0.065), seg=18, rings=10)
    ellipsoid(bm, (x, y - 0.130, 0.045), (0.065, 0.055, 0.048), seg=12, rings=8)
    for dx in (-0.088, 0.088):
        ellipsoid(bm, (x + dx, y - 0.100, 0.040), (0.052, 0.048, 0.042), seg=12, rings=8)


# ------------------------------------------------------------------------------------------ hair
# The coat's volumes (hump, cape, skirt) are part of the fused body. The hair on them is separate clumps: curved
# blades (a flattened diamond in section, wide along the skin) rooted a little under the surface, in overlapping
# rows like thatch, so the hems and the crest stay crisp at a low triangle count. Each clump is skinned rigidly to
# the skin at its root (rhino_rig). Left side and centre line; the left ones are mirrored.
# (anchor near the surface, direction, length, half width[, lift]); lift leans the clump out from the skin.
LOCKS = [
    # the beard under the throat
    ((0.000, -1.000, 0.840), (0.0, -0.2, -1.0), 0.22, 0.080),
    ((0.120, -0.990, 0.860), (0.3, -0.1, -1.0), 0.20, 0.070),
    # hind legs: breeches down the back of the thigh to the gaskin
    ((0.400, 0.950, 1.000), (0.4, 0.5, -1.0), 0.30, 0.095),
    ((0.220, 1.060, 0.980), (0.2, 0.6, -1.0), 0.28, 0.090),
    ((0.440, 0.880, 0.750), (0.4, 0.4, -1.0), 0.24, 0.080),
    ((0.380, 0.950, 0.580), (0.3, 0.5, -1.0), 0.18, 0.068),
    # tail tuft
    ((0.000, 1.230, 0.940), (0.0, 0.2, -1.0), 0.18, 0.055),
    ((0.030, 1.220, 0.980), (0.4, 0.3, -1.0), 0.15, 0.048),
]
# Fringes: thick curtains along the edges of the coat's volumes, folded into ridges and valleys like strands, their
# lower edge a zig-zag of uneven points. Loops run all the way round (centre y, half length, half width, hem z at
# the sides / front / back); strips run along y at one side (anchor x, z, y from, y to). Then: tooth pitch, hang
# direction, long and short lengths, thickness, lift.
FRINGE_LOOPS = [   # (volume, (centre x, centre y, half length, half width, hem z at the sides / front / back,
                   #  open gap round the front in degrees), pitch, outward lean, long and short lengths, thickness, lift)
    ('CAPE', (0.0, -0.48, 0.56, 0.62, 1.14, 1.14, 1.44, 70), 0.15, 0.35, (0.22, 0.38), (0.04, 0.08), 0.05, 0.12),
    ('SKIRT', (0.0, 0.00, 0.95, 0.60, 0.47, 0.64, 0.62, 0), 0.13, 0.25, (0.17, 0.32), (0.03, 0.07), 0.05, 0.12),
]
# feathering: a ring round each leg over the foot (leg, centre x, centre y, hem z)
FEATHER_LOOPS = [('FRONT_LEG', 0.310, -0.635, 0.250), ('HIND_LEG', 0.320, 0.815, 0.250)]
FRINGE_STRIPS = [  # anchors dropped straight down onto the body at (x, y from .. y to)
]


def coat_locks():
    """The hand-placed clumps and a few under the belly."""
    out = list(LOCKS)
    for y in (-0.30, 0.00, 0.30):
        out.append(((0.0, y, 0.40), (0.0, 0.0, -1.0), 0.14, 0.090, 0.2))
    return out


def build_fringes(bm, bvh, seed=5):
    rng = np.random.default_rng(seed)
    root = bm.verts.layers.float_vector["root"]
    vs = []
    for vol, spec, step, dout, longs, shorts, thick, lift in FRINGE_LOOPS:
        snap = _Snap(_volume_bvh(globals()[vol]))
        A, outs, closed = _loop_anchors(spec, step / 2)
        vs += _fringe(bm, snap, A, closed, dout, longs, shorts, thick, lift, rng, root, outs)
    for leg, x, y, z in FEATHER_LOOPS:
        for s in (1, -1):
            snap = _Snap(_loft_bvh(_leg_loft(globals()[leg], s)))
            A, outs, _ = _loop_anchors((s * x, y, 0.13, 0.13, z, z, z, 0), 0.085, reach=0.08)
            vs += _fringe(bm, snap, A, True, 0.35, (0.10, 0.15), (0.03, 0.05), 0.03, 0.25, rng, root, outs)
    drop = _Drop(bvh)
    for (x, y0, y1), step, d, longs, shorts, thick, lift in FRINGE_STRIPS:
        n = max(3, int(round((y1 - y0) / (step / 2)))) // 2 * 2 + 1
        for s in ((1,) if x == 0 else (1, -1)):
            anchors = [Vector((s * x, y, 2.0)) for y in np.linspace(y0, y1, n)]
            vs += _fringe(bm, drop, anchors, False, (s * d[0], d[1], d[2]), longs, shorts, thick, lift, rng, root)
    return vs


def fur_flow(P, N):
    """Direction the hair lies in at points P with normals N (unit, in the tangent plane): back along the top,
    hanging down the flanks and legs, back up the face, up the ears."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    one = np.ones_like(x)
    top = np.stack([0 * x, one, -0.15 * one], -1)
    hang = np.stack([0 * x, 0.25 * one, -one], -1)
    face = np.broadcast_to(hx_dir((0.0, 1.0, 0.25)), P.shape)
    w_top = smoothstep(0.30, 0.80, N[..., 2])
    F = top * w_top[..., None] + hang * (1 - w_top[..., None])
    H = hx_inv(P)
    w_face = smoothstep(0.02, -0.10, H[..., 1]) * smoothstep(-0.30, -0.20, H[..., 2])   # the face, not the jowls
    F = F * (1 - w_face[..., None]) + face * w_face[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def fur_amount(P, N):
    """How long the hair is (sculpted clump height, metres)."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    A = np.full(len(P), 0.006)
    A = A + 0.010 * _gauss(P, (0, -0.60, 1.60), (0.35, 0.40, 0.25))                        # hump
    A = A + 0.006 * smoothstep(1.25, 0.95, z) * smoothstep(0.45, 0.70, z) * (np.abs(x) > 0.25)   # skirt
    A = A * (1 - 0.6 * smoothstep(0.40, 0.22, z) * (np.abs(x) > 0.15))                    # shorter on the shins
    H = hx_inv(P)
    A = A * (1 - 0.6 * smoothstep(-0.05, -0.20, H[:, 1]))                                 # short on the face
    A = A * (1 - 0.8 * smoothstep(-0.64, -0.74, H[:, 1]))                                 # bare lips
    return A


def sculpt_fur(co, no, seed=11):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed, across=0.085, along_len=0.24)


def sculpt_face(co, no):
    """Deep-set eyes under a brow, the nostrils on the front corners of the muzzle."""
    out = co.copy()
    H = hx_inv(co)
    Pm = np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1)                               # head space, mirrored
    out -= no * (0.016 * _gauss(Pm, EYE0_H, (0.030, 0.030, 0.024)))[:, None]              # socket
    out -= no * (0.020 * _gauss(Pm, (0.085, -0.900, -0.170), (0.018, 0.016, 0.024)))[:, None]   # nostrils
    return out


# ------------------------------------------------------------------------------------------ body
def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face and lower legs keep relatively more."""
    h = hx_inv(co[:])
    face = h[1] < -0.10 and h[2] > -0.50 and abs(h[0]) < 0.26
    leg = co.z < 0.55 and abs(co.x) > 0.15 and (abs(co.y + 0.63) < 0.25 or abs(co.y - 0.82) < 0.25)
    return 1.0 - 0.35 * float(face) - 0.35 * float(leg)


def build_fur_body(voxel=0.008, target_tris=2000, fillet_iters=30):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    for s in (1, -1):
        build_leg_front(bm, s)
        build_leg_hind(bm, s)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return beast_body.fuse_body(bm, "RHN", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                dec_weight=_dec_weight, seam_x=0.02, flat_z=0.008, fillet_iters=fillet_iters)


def _snap(bvh, p, n, reach=0.25):
    """Ray from outside along -n onto the surface near p."""
    hit = bvh.ray_cast(Vector(p + n * reach), Vector(-n), reach * 2)[0]
    return np.array(hit) if hit is not None else np.array(p)


def _eye_centre(bvh, s):
    """Where the eye dome sits: on the game mesh's socket, a little sunk in (decimation fills the dense socket)."""
    n = EYE_N * np.array((s, 1, 1))
    c = _snap(bvh, EYE0 * np.array((s, 1, 1)), n, 0.08) - n * 0.004
    return c, n


def _orth(d):
    d = Vector(d).normalized()
    a = d.orthogonal().normalized()
    return a, d.cross(a)


def build_spear(bm, bvh):
    """A snapped boar spear in the left shoulder: crossbar lugs and the iron socket at the wound, ~60 cm of ash
    shaft, a splintered end. The blade is buried. Returns its BMVerts."""
    D = SPEAR_DIR
    e = _snap(bvh, SPEAR_AIM, D, 0.3)                              # entry point on the skin
    LM['spear_entry'] = e
    vs = []
    P = lambda t: tuple(e + D * t)
    up = tuple(_orth(D)[0])
    # iron socket (tapered), from under the skin out past the lugs
    vs += loft(bm, [P(-0.08) + (0.030, 0.030, 0.030), P(0.03) + (0.029, 0.029, 0.029),
                    P(0.13) + (0.022, 0.022, 0.022)], up=up, seg=8, per_seg=1, cap0=0.0, cap1=0.0)
    # crossbar lugs: two flat wings either side of the socket, just out of the skin
    side, flatv = _orth(D)
    for sg in (1, -1):
        a = e + D * 0.02 + side * sg * 0.020
        b = e + D * 0.03 + side * sg * 0.085
        vs += loft(bm, [tuple(a) + (0.022, 0.008, 0.008), tuple(b) + (0.012, 0.006, 0.006)],
                   up=tuple(flatv), seg=4, per_seg=1, cap0=0.0, cap1=0.5)
    # ash shaft with a leather binding over the socket's end
    vs += loft(bm, [P(0.12) + (0.020, 0.020, 0.020), P(0.40) + (0.020, 0.020, 0.020),
                    P(0.60) + (0.019, 0.019, 0.019)], up=up, seg=8, per_seg=1, cap0=0.0, cap1=0.0)
    vs += loft(bm, [P(0.125) + (0.025, 0.025, 0.025), P(0.175) + (0.025, 0.025, 0.025)], up=up, seg=8,
               per_seg=1, cap0=0.0, cap1=0.0)
    # the snapped end: splinters of uneven length
    for k, (ang, ln, r) in enumerate(((0.3, 0.075, 0.011), (2.4, 0.045, 0.010), (4.3, 0.060, 0.009))):
        off = (Vector(side) * math.cos(ang) + Vector(flatv) * math.sin(ang)) * 0.009
        base = Vector(P(0.595)) + off
        tip = base + Vector(D) * ln + off * 0.6
        vs += cone(bm, base, tip, r, seg=4)
    return vs


def build_ear(bm, s):
    """A rhino's ear: a cupped shell standing up from the poll, open toward the front and out. Its section is a
    crescent: the back wraps round from rim to rim, the front is a hollow sunk behind the rims. Rides on
    Ear{L,R}; UV cut down one rim and round the base."""
    base = np.array(EAR[0][:3]) * np.array((s, 1, 1))
    A = (np.array(EAR[-1][:3]) - np.array(EAR[0][:3])) * np.array((s, 1, 1))
    L = np.linalg.norm(A)
    A /= L
    F = np.array((0.5 * s, -1.0, 0.0))
    F = F - A * (F @ A)
    F /= np.linalg.norm(F)
    S = np.cross(A, F)
    rings = []
    for t, w, d in ((0.0, 0.050, 0.042), (0.35, 0.064, 0.048), (0.70, 0.050, 0.038), (0.92, 0.024, 0.018)):
        c = base + A * L * t
        pts = [c - F * math.cos(math.radians(th)) * d + S * math.sin(math.radians(th)) * w
               for th in (-100, -60, -20, 20, 60, 100)]                      # the back, rim to rim
        pts += [c - F * 0.55 * d + S * k * w for k in (0.55, 0.18, -0.18, -0.55)]   # the hollow, rim to rim
        rings.append([bm.verts.new(Vector(p)) for p in pts])
    apex = bm.verts.new(Vector(base + A * L))
    n = len(rings[0])
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for j in range(n):
            bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j]))
    for j in range(n):
        bm.faces.new((rings[-1][j], rings[-1][(j + 1) % n], apex))
    bm.faces.new(list(reversed(rings[0])))
    line = [r[5] for r in rings] + [apex]
    for p, q in zip(line[:-1], line[1:]):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    for j in range(n):
        e = bm.edges.get((rings[0][j], rings[0][(j + 1) % n]))
        if e is not None:
            e.seam = True
    return [v for r in rings for v in r] + [apex]


def build_pieces(low):
    """Lower jaw, horns, eyes, the spear and the coat's clumps: separate shells (no remesh).
    Returns (bmesh, {part: verts})."""
    bml = bmesh.new()
    bml.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    bm = bmesh.new()
    bm.verts.layers.float_vector.new("root")      # before any vertex: adding a layer later orphans the BMVerts
    tags = {}
    # chin and lower lip (head space): the back end hides in the cheek, the top edge tucks inside the upper lip
    jaw = [(0, -0.60, -0.335, 0.115, 0.045, 0.055), (0, -0.70, -0.335, 0.120, 0.040, 0.055),
           (0, -0.82, -0.330, 0.115, 0.040, 0.050), (0, -0.89, -0.320, 0.100, 0.035, 0.045)]   # head space
    vs = loft(bm, jaw, up=(0, 0, 1), seg=10, per_seg=2, cap0=0.6, cap1=0.6, capk=2, shape=0.9)
    for v in vs:
        v.co = Vector(hx(v.co[:]))
    tags['jaw'] = vs
    fwd = tuple(float(c) for c in hx_dir((0, -1, 0)))
    tags['horn'] = (loft(bm, HORN1, up=fwd, seg=8, per_seg=1, cap0=0.3, cap1=0.5, capk=2) +
                    loft(bm, HORN2, up=fwd, seg=6, per_seg=1, cap0=0.3, cap1=0.5, capk=2))
    eyes = []
    for s in (1, -1):
        c, n = _eye_centre(bvh, s)
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        vs = dome(bm, c, n, EYE_R, 0.011, seg=12, rings=3)
        nv = Vector(n)                                             # a little almond: long front to back
        t = Vector(hx_dir((0, 1, 0.25)))
        t = (t - nv * t.dot(nv)).normalized()
        b = nv.cross(t)
        cv = Vector(c)
        for v in vs:
            d = v.co - cv
            v.co = cv + t * (d.dot(t) * 1.2) + b * (d.dot(b) * 0.85) + nv * d.dot(nv)
        eyes += vs
    tags['eye'] = eyes
    tags['ear'] = build_ear(bm, 1) + build_ear(bm, -1)
    tags['spear'] = build_spear(bm, bvh)
    tags['hair'] = build_clumps(bm, bvh, coat_locks()) + build_fringes(bm, bvh)
    return bm, tags


def build_body(voxel=0.008, target_tris=2000):
    """-> (RhinoBody (fur body joined with the pieces, info attribute set), RHN_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    nfur = len(fur.data.vertices)
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "RHN", "RhinoBody")
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    write_hair_t(body, PART['hair'])
    for k, v in LM.items():                      # the painter reads the eyes and the wound from here
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
    """name -> (head, Matrix3 frame (columns = bone X, Y, Z; Y along the bone), length, parent, deform); the wolf's
    conventions: Root and Motion point up with +Z toward the front (world -Y), Motion carries the root motion and
    nothing hangs from it; legs and spine bend about their local X (Z forward on the legs, up on the spine)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.5, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.4, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    _bone(B, "Hips", (0, 0.75, 1.300), (0, 1.05, 1.250), UP, "Root")
    _bone(B, "Spine1", (0, 0.75, 1.320), (0, 0.30, 1.360), UP, "Hips")
    _bone(B, "Spine2", (0, 0.30, 1.360), (0, -0.15, 1.380), UP, "Spine1")
    _bone(B, "Chest", (0, -0.15, 1.380), (0, -0.75, 1.320), UP, "Spine2")
    head0, head1 = hx((0, 0.02, -0.14)), hx((0, -0.70, -0.14))                         # along the hanging head
    _bone(B, "Neck1", (0, -0.75, 1.320), (0, -0.95, 1.300), UP, "Chest")
    _bone(B, "Neck2", (0, -0.95, 1.300), tuple(head0), UP, "Neck1")
    _bone(B, "Head", tuple(head0), tuple(head1), tuple(hx_dir((0, 0, 1))), "Neck2")
    _bone(B, "Jaw", HINGE, tuple(hx((0, -0.86, -0.36))), tuple(hx_dir((0, 0, 1))), "Head")
    par = "Hips"
    for i in range(len(TAIL) - 1):
        _bone(B, f"Tail{i + 1}", TAIL[i], TAIL[i + 1], (0, 1, 0.3), par)
        par = f"Tail{i + 1}"
    for s, sfx in ((1, "L"), (-1, "R")):
        m = (lambda p: p) if s > 0 else _mx
        _bone(B, f"Ear{sfx}", m(EAR[0][:3]), m(EAR[-1][:3]), FWD, "Head")
        _bone(B, f"Scapula{sfx}", m(J['SCAP']), m(J['SHO']), FWD, "Chest")
        _bone(B, f"UpperArm{sfx}", m(J['SHO']), m(J['ELB']), FWD, f"Scapula{sfx}")
        _bone(B, f"Forearm{sfx}", m(J['ELB']), m(J['WRI']), FWD, f"UpperArm{sfx}")
        _bone(B, f"FrontPaw{sfx}", m(J['WRI']), m(J['FPAW']), FWD, f"Forearm{sfx}")
        _bone(B, f"FrontToes{sfx}", m(J['FPAW']), m(J['FTOE']), UP, f"FrontPaw{sfx}")
        _bone(B, f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
        _bone(B, f"Shin{sfx}", m(J['KNEE']), m(J['HOCK']), FWD, f"Thigh{sfx}")
        _bone(B, f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), FWD, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
    # sockets (head = attach point; +Y up, +Z forward unless noted)
    top = hx((0, -0.28, 0.02))
    _bone(B, "Socket_Head", tuple(top), tuple(top + np.array((0, 0, 0.1))), FWD, "Head")
    tip = np.array(HORN1[-1][:3])
    _bone(B, "Socket_Horn", tuple(tip), tuple(tip + np.array((0, 0, 0.1))), FWD, "Head")   # the horn tip (gore FX)
    mouth = hx((0, -0.74, -0.30))
    _bone(B, "Socket_Mouth", tuple(mouth), tuple(mouth + np.array((0, 0, 0.1))), FWD, "Jaw")
    _bone(B, "Socket_Back", (0, -0.30, 1.760), (0, -0.30, 1.860), FWD, "Chest")
    e = LM.get('spear_entry', SPEAR_AIM)
    _bone(B, "Socket_Spear", tuple(e), tuple(np.asarray(e) + SPEAR_DIR * 0.1), FWD, "Chest")  # +Y out of the wound
    return B
