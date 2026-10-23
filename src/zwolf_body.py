"""Zombie wolf (2026-10-23): the grey wolf dead and risen, a unit of Daniel's card game ("zombie wolf") in the undead
batch (the zombies, skeletons and the ghoul are in the Humans repo). Built standing (the bind pose), facing -Y, left
side +X, like the wolf.

It keeps the wolf's skeleton exactly: wolf_body's landmarks, head warp (hw) and rest_bones(), so every wolf clip plays
on it unchanged (zwolf_anim keys wolf_anim's clips onto it). Only the body round the bones is new:
  - starved: a narrow ribcage, the belly drawn up behind the last ribs, wasted shoulders, thighs and neck, thin legs
    with knobby joints, a thin tail. The spine's processes, the hip points, the pin bones and the shoulder blades'
    ridges stand out (ellipsoids fused in with the rest);
  - mangy: fewer, thinner, stringier tufts; bald patches (BALD, shared with the painter) get no fur sculpt and sink in
    a little;
  - wounds: the right flank torn open (WOUND: a cavity with a raised, torn rim and rib bars across it, separate
    shells), a torn patch over the left haunch (GASH, a shallow dent);
  - the right ear torn (its tip gone, a notch out of its outer edge), the lips drawn back off the teeth (the upper lip
    line raised, the upper teeth hanging outside the lower jaw), deep eye sockets and gaunt cheeks; the eyes a little
    bigger than the wolf's (milky, in the paint).
The wound and the torn ear make it one-sided: those sculpts run after the symmetrize, and the decimation is not
symmetric (beast_body.fuse_body(dec_symmetry=False)).

build_body() -> ZombieWolfBody, one mesh: the fused fur body (decimated; ZWF_BodyHi is the dense copy kept for
reference) + the lower jaw, tongue, teeth, eyes and rib bars as separate pieces. The point attribute "info" holds
(part / 255, on jaw, 0, 1) for the painter (PART; the rib bars are PART['bone']).
"""
import bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from beast_common import loft, cone, dome, smoothstep, fbm
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, tri_report
import wolf_body as W0
from wolf_body import J, HC, TAIL, EYE0, EYE_N, EAR, hw, hw_inv, _warp_verts, fur_flow, rest_bones

PREFIX = "ZWF"
BODY = "ZombieWolfBody"
EYE_R = W0.EYE_R * 1.12                       # a little bigger than the wolf's: milky, they must read in game
LM = {}


def _rx(deg):
    return Matrix.Rotation(math.radians(deg), 3, 'X')


# ------------------------------------------------------------------------------------------ the starved trunk
TRUNK = [  # y, z centre, half width, up radius, down radius: the wolf's rows (wolf_body.build_trunk), starved
    (-0.470, 0.600, 0.072, 0.095, 0.095),
    (-0.400, 0.610, 0.103, 0.148, 0.170),
    (-0.280, 0.612, 0.115, 0.158, 0.190),     # a narrow ribcage, still deep
    (-0.140, 0.622, 0.112, 0.138, 0.170),
    (-0.030, 0.636, 0.100, 0.120, 0.140),     # the last ribs
    (0.070, 0.648, 0.078, 0.102, 0.078),      # the belly drawn up behind them
    (0.170, 0.654, 0.075, 0.098, 0.070),
    (0.270, 0.658, 0.090, 0.098, 0.084),
    (0.370, 0.655, 0.097, 0.096, 0.108),
    (0.460, 0.640, 0.076, 0.082, 0.092),
]
NECK = [(0, -0.30, 0.660, 0.088, 0.108, 0.116), (0, -0.44, 0.720, 0.080, 0.097, 0.104),
        (0, -0.56, 0.790, 0.072, 0.084, 0.088), (0, -0.67, 0.850, 0.063, 0.068, 0.072)]
SPINE_STEP = 0.048                            # the spine's processes, withers to croup


def top_z(y):
    """The back's top line (the trunk loft's top) at y."""
    ys = [r[0] for r in TRUNK]
    return np.interp(y, ys, [r[1] + r[3] for r in TRUNK])


def half_width(y):
    ys = [r[0] for r in TRUNK]
    return np.interp(y, ys, [r[2] for r in TRUNK])


def build_trunk(bm):
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in TRUNK], up=(0, 0, 1), seg=24, cap0=0.7, cap1=0.6)
    loft(bm, NECK, up=(0, 0, 1), seg=20, cap0=0.5, cap1=0.5)
    ruff = _rx(-30)                                            # a thin, mangy ruff
    ellipsoid(bm, (0, -0.49, 0.735), (0.088, 0.140, 0.098), rot=ruff)
    ellipsoid(bm, (0, -0.53, 0.672), (0.064, 0.076, 0.074), rot=ruff)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.078, 0.290, 0.565), (0.040, 0.086, 0.124), rot=_rx(-32))      # wasted thigh
        ellipsoid(bm, (s * 0.080, 0.205, 0.530), (0.036, 0.052, 0.044))                   # flank fold to the stifle
    # bones under the skin: the spine's processes, the hip points and pin bones, the shoulder blades' ridges
    for y in np.arange(-0.36, 0.43, SPINE_STEP):
        withers = smoothstep(-0.10, -0.30, y)                  # the thoracic spines are the tallest
        ellipsoid(bm, (0, y, float(top_z(y)) - 0.005), (0.011, 0.016, 0.012 + 0.003 * withers), seg=10, rings=6)
    for s in (1, -1):
        y = 0.285
        ellipsoid(bm, (s * 0.058, y, float(top_z(y)) - 0.012), (0.020, 0.026, 0.016), seg=12, rings=8)    # hip point
        ellipsoid(bm, (s * 0.040, 0.468, 0.650), (0.016, 0.018, 0.018), seg=12, rings=8)                 # pin bone
        rot = _rx(-38.7)                                        # along the blade (SCAP -> SHO)
        ellipsoid(bm, (s * 0.094, -0.325, 0.672), (0.012, 0.016, 0.070), rot=rot, seg=12, rings=8)       # scapula
    # a thin tail, carried low
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, (0.030, 0.036, 0.036, 0.032, 0.026, 0.016))]
    loft(bm, tail, up=(0, 1, 0), seg=16, cap0=0.4, cap1=0.9)


# ------------------------------------------------------------------------------------------ the head
# The wolf's muzzle with the lips drawn back: the upper lip line rises from the mouth's corner (0.785) to 0.796 along
# the teeth (the wolf's hangs at 0.772-0.776, over the lower jaw), so the teeth and the gum over them show.
MUZZLE = [(0, -0.770, 0.843, 0.056, 0.062, 0.058), (0, -0.820, 0.832, 0.048, 0.053, 0.040),
          (0, -0.870, 0.824, 0.040, 0.042, 0.028), (0, -0.910, 0.820, 0.034, 0.036, 0.024),
          (0, -0.935, 0.818, 0.030, 0.033, 0.022)]
LIP_UP = 0.796


def lip_z(y):
    """The drawn-back upper lip's edge (the muzzle loft's bottom) at y, unwarped."""
    return np.interp(y, [r[1] for r in MUZZLE[::-1]], [r[2] - r[5] for r in MUZZLE[::-1]])


def build_head(bm):
    ellipsoid(bm, HC, (0.068, 0.085, 0.068), seg=24, rings=16)               # the skull
    for s in (1, -1):
        ellipsoid(bm, (s * 0.046, -0.742, 0.832), (0.022, 0.040, 0.024))      # cheeks, wasted
        ellipsoid(bm, (s * 0.058, -0.695, 0.815), (0.022, 0.032, 0.050), rot=_rx(20))   # a thin cheek ruff
    ellipsoid(bm, (0, -0.740, 0.785), (0.045, 0.050, 0.047))                 # jowls: hide the back of the jaw
    loft(bm, MUZZLE, up=(0, 0, 1), seg=20, cap0=0.55, cap1=0.6, shape=0.6)
    ellipsoid(bm, (0, -0.950, 0.836), (0.022, 0.015, 0.017))                 # nose leather
    ellipsoid(bm, (0, -0.932, 0.803), (0.022, 0.014, 0.009))                 # front of the upper lip, drawn up
    for s in (1, -1):
        loft(bm, [(s * r[0], r[1], r[2], r[3], r[4], r[5]) for r in EAR], up=(0, -1, 0), seg=16, cap0=0.3,
             cap1=0.8, shape=0.9)


# ------------------------------------------------------------------------------------------ legs
LEG_K = (0.82, 0.95)       # the wolf's leg radii: wasted at the top, the lower legs (bone and tendon) nearly the same


def _leg_rows(rows, s):
    out = []
    for r in rows:
        kk = LEG_K[0] + (LEG_K[1] - LEG_K[0]) * smoothstep(0.45, 0.22, r[2])
        out.append((s * r[0], r[1], r[2], r[3] * kk, r[4] * kk, r[5] * kk))
    return out


def build_leg_front(bm, s):
    rows = [(0.090, -0.405, 0.640, 0.044, 0.072, 0.072), (0.097, -0.390, 0.550, 0.046, 0.064, 0.074),
            (0.105, -0.345, 0.450, 0.043, 0.050, 0.058), (0.101, -0.325, 0.350, 0.035, 0.040, 0.038),
            (0.098, -0.330, 0.220, 0.027, 0.029, 0.026), (0.095, -0.332, 0.130, 0.023, 0.025, 0.023),
            (0.092, -0.350, 0.070, 0.021, 0.022, 0.020), (0.090, -0.365, 0.045, 0.023, 0.021, 0.021)]
    loft(bm, _leg_rows(rows, s), up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.5)
    ellipsoid(bm, (s * 0.105, -0.300, 0.420), (0.024, 0.024, 0.030))          # point of the elbow
    ellipsoid(bm, (s * 0.096, -0.322, 0.132), (0.021, 0.020, 0.019))          # knobby wrist
    W0._paw(bm, s, -0.385, 1.0)


def build_leg_hind(bm, s):
    rows = [(0.098, 0.215, 0.480, 0.046, 0.048, 0.054), (0.100, 0.270, 0.380, 0.038, 0.034, 0.056),
            (0.097, 0.340, 0.300, 0.029, 0.025, 0.043), (0.095, 0.400, 0.225, 0.022, 0.022, 0.030),
            (0.092, 0.405, 0.150, 0.020, 0.021, 0.022), (0.090, 0.392, 0.080, 0.020, 0.021, 0.021),
            (0.090, 0.385, 0.045, 0.022, 0.021, 0.021)]
    loft(bm, _leg_rows(rows, s), up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.5)
    ellipsoid(bm, (s * 0.096, 0.425, 0.225), (0.017, 0.020, 0.026))            # point of the hock
    ellipsoid(bm, (s * 0.100, 0.200, 0.468), (0.020, 0.022, 0.020))            # the stifle
    W0._paw(bm, s, 0.365, 0.92)


# ------------------------------------------------------------------------------------------ mangy fur
# A few of the wolf's tufts (wolf_body.TUFTS), a little longer and thinner (matted): no hackles (the spine shows), no
# fringe along the tucked-up belly, only one pair at the tail's root. (Thinner still, at 0.62 of the wolf's radius,
# they collapsed in the decimation into fins and duplicate faces, and the heat-map weights failed outright.)
TUFTS = [
    ((0.082, -0.700, 0.815), (0.7, 0.5, -0.45), 0.048, 0.018),     # cheek ruff
    ((0.072, -0.690, 0.778), (0.5, 0.3, -0.8), 0.048, 0.018),
    ((0.090, -0.600, 0.830), (0.65, 0.8, -0.15), 0.055, 0.024),    # the ruff
    ((0.102, -0.570, 0.760), (0.65, 0.6, -0.5), 0.055, 0.025),
    ((0.090, -0.560, 0.685), (0.5, 0.35, -0.8), 0.052, 0.024),
    ((0.105, -0.480, 0.780), (0.7, 0.8, -0.3), 0.045, 0.022),
    ((0.122, -0.285, 0.425), (0.25, 1.0, -0.5), 0.030, 0.015),     # elbows
    ((0.104, 0.420, 0.470), (0.35, 0.5, -1.0), 0.040, 0.019),      # breeches
    ((0.055, 0.560, 0.610), (0.6, 0.8, -0.6), 0.040, 0.020),       # the tail's root
]
TUFT_K = (1.10, 0.85)                         # length, radius against the wolf's


def build_tufts(bm, bvh):
    tufts = [(a, d, L * TUFT_K[0], r * TUFT_K[1]) for a, d, L, r in TUFTS]
    beast_body.build_tufts(bm, bvh, tufts, warp=hw)


# Bald, rotting skin: (centre, radii, strength), unwarped (wolf) coordinates, x signed (the patches are one-sided).
# bald() frays their edges with noise. The spine's strip follows the back's top line (SPINE_BALD).
BALD = [
    ((-0.098, -0.125, 0.585), (0.045, 0.130, 0.090), 1.0),    # round the torn right flank
    ((0.092, -0.205, 0.585), (0.045, 0.075, 0.065), 0.95),    # the left ribs
    ((0.092, 0.300, 0.615), (0.050, 0.065, 0.065), 1.0),      # the left haunch (the gash)
    ((-0.070, 0.290, 0.680), (0.035, 0.045, 0.035), 0.85),    # the right hip point
    ((-0.085, -0.335, 0.700), (0.030, 0.045, 0.040), 0.85),   # the right shoulder blade
    ((-0.080, -0.500, 0.730), (0.045, 0.065, 0.060), 0.9),    # the right side of the neck
    ((0.038, -0.845, 0.822), (0.026, 0.050, 0.024), 0.9),     # the left side of the muzzle
    ((-0.046, -0.748, 0.832), (0.026, 0.030, 0.030), 0.85),   # the right cheek
    ((0.124, -0.330, 0.270), (0.016, 0.030, 0.065), 0.95),    # the left forearm, outside only (a ring round
    ((-0.120, 0.372, 0.300), (0.016, 0.040, 0.055), 0.9),     # the leg read as a bandage); the right hind shin
    ((0.000, 0.130, 0.585), (0.050, 0.090, 0.035), 0.75),     # the tucked-up belly
]
SPINE_BALD = (-0.26, 0.40, 0.028, 0.024)      # y from, y to, half width, depth under the top line
TAIL_BALD = 0.45                              # the tail is mangy from this far along it


def bald(Pu, fray=0.30, edge=(0.42, 0.56)):
    """0..1: how bald the skin is at unwarped points Pu (N, 3). The spine's strip comes in broken stretches, the
    tail's end in patches (unbroken, both read as a stripe or a bandage). edge: the threshold band (the painter's is
    wider, for the fur's strands running into the skin)."""
    Pu = np.asarray(Pu, float)
    x, y, z = Pu[:, 0], Pu[:, 1], Pu[:, 2]
    s = np.zeros(len(Pu))
    Pw = Pu + 0.035 * np.stack([fbm(Pu * 7.0, 2, seed=s_) for s_ in (81, 82, 83)], -1)   # not round discs
    for c, r, k in BALD:
        s = np.maximum(s, k * _gauss(Pw, c, r))
    y0, y1, hw_, dz = SPINE_BALD
    along = smoothstep(y0 - 0.05, y0 + 0.05, y) * smoothstep(y1 + 0.05, y1 - 0.05, y)
    along = along * smoothstep(-0.20, 0.15, fbm(np.stack([y * 9.0, 0 * y + 3.1, 0 * y], -1), 2, seed=71))
    s = np.maximum(s, along * np.exp(-0.5 * ((x / hw_) ** 2 + ((z - top_z(y)) / dz) ** 2)))
    from beast_paint import polyline_t
    t, dist = polyline_t(Pu, TAIL)
    tail = smoothstep(TAIL_BALD - 0.06, TAIL_BALD + 0.06, t) * (dist < 0.06) * (y > 0.43)
    s = np.maximum(s, tail * smoothstep(-0.25, 0.10, fbm(Pu * 22.0, 2, seed=72)))
    n = 0.7 * fbm(Pu * 16.0, 3, seed=41) + 0.3 * fbm(Pu * 42.0, 2, seed=42)
    return smoothstep(edge[0], edge[1], s + fray * n)


# ------------------------------------------------------------------------------------------ wounds
# The right flank torn open behind the elbow: an elliptical hole (ry along the body, rz up) with a ragged edge, DEPTH
# deep, its torn rim raised; rib bars across it (build_ribs). The ribs follow RIB_* (the painter draws the same ribs
# on both flanks): rib k lies at u = k, u = (y - RIB_Y0 - RIB_SLANT * (RIB_Z0 - z)) / RIB_DY.
WOUND = dict(c=(-0.098, -0.125, 0.585), ry=0.095, rz=0.064, depth=0.034)   # high on the flank: the game camera
                                                                            # looks down at 50 degrees
GASH = dict(c=(0.118, 0.300, 0.596), ry=0.055, rz=0.028, angle=-35.0, depth=0.012)
RIB_Y0, RIB_Z0, RIB_DY, RIB_SLANT = -0.42, 0.66, 0.036, 0.30
RIB_DEPTH = 0.011                             # rib bars: how far under the skin's surface
_WOUND_SURF = {}                              # the flank's surface before the cavity (for the ribs)


def _ragged(th, k):
    return 1 + k * (0.55 * np.sin(5 * th + 0.7) + 0.38 * np.sin(9 * th + 2.1) + 0.25 * np.sin(14 * th + 0.3))


def wound_e(Pu):
    """-> (e, side): e < 1 inside the hole's ragged outline (elliptical distance), side: on the right flank."""
    Pu = np.asarray(Pu, float)
    c = WOUND['c']
    dy = (Pu[:, 1] - c[1]) / WOUND['ry']
    dz = (Pu[:, 2] - c[2]) / WOUND['rz']
    e = np.hypot(dy, dz) / _ragged(np.arctan2(dz, dy), 0.19)
    return e, Pu[:, 0] < -0.02


def gash_e(Pu):
    Pu = np.asarray(Pu, float)
    c, a = GASH['c'], math.radians(GASH['angle'])
    dy, dz = Pu[:, 1] - c[1], Pu[:, 2] - c[2]
    u = (dy * math.cos(a) + dz * math.sin(a)) / GASH['ry']
    v = (-dy * math.sin(a) + dz * math.cos(a)) / GASH['rz']
    e = np.hypot(u, v) / _ragged(np.arctan2(v, u) + 1.3, 0.16)
    return e, Pu[:, 0] > 0.04


def rib_u(y, z):
    return (y - RIB_Y0 - RIB_SLANT * (RIB_Z0 - z)) / RIB_DY


def sculpt_wound(co, no):
    """The cavity and its rim (right flank), and the haunch's shallow torn patch (left). Keeps the flank's surface
    before the cavity in _WOUND_SURF, for the ribs."""
    out = co.copy()
    Pu = hw_inv(co)
    e, side = wound_e(Pu)
    facing = smoothstep(-0.10, -0.40, no[:, 0])                  # facing out to the right
    m = side * facing
    keep = (e < 1.6) & side
    _WOUND_SURF['co'] = co[keep].copy()
    _WOUND_SURF['no'] = no[keep].copy()
    d = WOUND['depth'] * smoothstep(1.0, 0.70, e) - 0.0055 * np.exp(-((e - 1.07) / 0.09) ** 2)
    out -= no * (d * m)[:, None]
    g, gside = gash_e(Pu)
    gm = gside * smoothstep(0.10, 0.40, no[:, 0])
    gd = GASH['depth'] * smoothstep(1.0, 0.65, g) - 0.003 * np.exp(-((g - 1.08) / 0.10) ** 2)
    out -= no * (gd * gm)[:, None]
    return out


# The torn right ear: in its own frame (t along it, base 0 .. tip 1; s across it, + toward its outer edge), its tip is
# gone above EAR_TOP(s) and a V is bitten out of its outer edge (EAR_NOTCH: t centre, half length, depth left).
EAR_TOP = (0.70, 0.06)                         # t of the torn top, raggedness
EAR_NOTCH = (0.46, 0.13, 0.006)


def _ear_frame(s):
    b = np.array(EAR[0][:3]) * (s, 1, 1)
    tip = np.array(EAR[-1][:3]) * (s, 1, 1)
    T = tip - b
    L = np.linalg.norm(T)
    T /= L
    N = np.array((0.0, -1.0, 0.0))
    N = N - T * (N @ T)
    N /= np.linalg.norm(N)
    S = np.cross(T, N)
    if S[0] * s < 0:
        S = -S                                     # + toward the outer edge
    return b, T, N, S, L


def sculpt_ear(co, no):
    out = co.copy()
    Pu = hw_inv(co)
    b, T, N, S, L = _ear_frame(-1)
    rel = Pu - b
    t = (rel @ T) / L
    s = rel @ S
    nn = rel @ N
    width = np.interp(t, (0.0, 0.39, 0.73, 1.0), (0.040, 0.032, 0.020, 0.008))
    ear = (Pu[:, 0] < -0.015) & (t > 0.12) & (t < 1.15) & (np.abs(s) < width + 0.012) & (np.abs(nn) < 0.03)
    if not ear.any():
        return out
    tmax = EAR_TOP[0] + EAR_TOP[1] * (0.6 * np.sin(s / 0.0045 + 0.5) + 0.4 * np.sin(s / 0.0021 + 1.9))
    t2 = np.minimum(t, tmax)
    tc, th, dep = EAR_NOTCH
    smax = dep + (width - dep) * np.clip(np.abs(t2 - tc) / th, 0, 1) ** 1.4 + 0.004
    s2 = np.where(s > 0, np.minimum(s, smax), s)
    P2 = b + np.outer(t2 * L, T) + np.outer(s2, S) + np.outer(nn, N)
    Pu2 = np.where(ear[:, None], P2, Pu)
    return np.where(ear[:, None], hw(Pu2), out)


def sculpt_face(co, no):
    """The wolf's face sculpt (sockets, brow, nostrils, cupped ears), the sockets deeper, the brow and cheekbone sharper,
    the cheeks and temples sunk."""
    out = W0.sculpt_face(co, no)
    Pu = hw_inv(co)
    ax = np.abs(Pu[:, 0])
    Pm = np.stack([ax, Pu[:, 1], Pu[:, 2]], -1)
    out -= no * (0.0045 * _gauss(Pm, EYE0, (0.016, 0.015, 0.012)))[:, None]                      # deeper socket
    out += no * (0.0020 * _gauss(Pm, EYE0 + np.array((-0.004, 0.006, 0.014)), (0.016, 0.012, 0.005)))[:, None]
    out += no * (0.0030 * _gauss(Pm, (0.050, -0.776, 0.857), (0.008, 0.026, 0.005)))[:, None]      # cheekbone
    out -= no * (0.0045 * _gauss(Pm, (0.046, -0.760, 0.832), (0.012, 0.022, 0.012)))[:, None]      # gaunt cheek
    out -= no * (0.0035 * _gauss(Pm, (0.058, -0.728, 0.902), (0.012, 0.018, 0.012)))[:, None]      # temple
    return out


def fur_amount(P, N):
    """The wolf's fur length, thin and matted, none where the skin is bald."""
    return W0.fur_amount(P, N) * 0.72 * (1 - bald(hw_inv(P)))


def sculpt_fur(co, no, seed=5):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed)


def sculpt_bald(co, no):
    """Bald skin shrinks onto the bones a little (2.5 mm)."""
    return co - no * (0.0025 * bald(hw_inv(co), fray=0.0))[:, None]


# ------------------------------------------------------------------------------------------ body
def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face, legs, the wound and the spine keep relatively more."""
    c = np.array(co[:])
    face = c[1] < -0.68 and c[2] > 0.75
    leg = c[2] < 0.42 and abs(c[0]) > 0.05 and c[1] < 0.47
    e, side = wound_e(c[None])
    wound = bool(side[0]) and e[0] < 1.35
    g, gs = gash_e(c[None])
    gash = bool(gs[0]) and g[0] < 1.3
    spine = abs(c[0]) < 0.03 and -0.40 < c[1] < 0.45 and c[2] > float(top_z(c[1])) - 0.025
    if wound:
        return 0.35
    return 1.0 - 0.25 * float(face) - 0.35 * float(leg) - 0.25 * float(gash) - 0.2 * float(spine)


def build_fur_body(voxel=0.004, target_tris=3900):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    for s in (1, -1):
        build_leg_front(bm, s)
        build_leg_hind(bm, s)
    _warp_verts(bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    build_tufts(bm, BVHTree.FromBMesh(bm))
    body, hi = beast_body.fuse_body(bm, PREFIX, voxel, target_tris,
                                    sculpts=(sculpt_face, sculpt_ear, sculpt_wound, sculpt_fur, sculpt_bald),
                                    dec_weight=_dec_weight, dec_symmetry=False)
    tidy(body)
    return body, hi


def tidy(ob):
    """After the decimation: drop "pillows" (two faces on the same vertices, zero area) and other degenerate faces.
    One left in the mesh and Blender's heat-map solve fails for every bone. -> {pillows, nonmanifold}"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    from collections import defaultdict
    bm.verts.index_update()
    groups = defaultdict(list)
    for f in bm.faces:
        groups[frozenset(v.index for v in f.verts)].append(f)
    dup = [f for fs in groups.values() if len(fs) > 1 for f in fs]
    dup += [f for f in bm.faces if f.calc_area() < 1e-9 and f not in dup]
    if dup:
        bmesh.ops.delete(bm, geom=dup, context='FACES_ONLY')
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-5)
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context='VERTS')
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=4)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.to_mesh(ob.data)
    bm.free()
    TIDY.update(pillows=len(dup), nonmanifold=nm)
    return TIDY


TIDY = {}


def _eye_centre(low, s):
    """On the game mesh's socket, a little sunk in (the wolf's way)."""
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    e = hw(EYE0 * np.array((s, 1, 1)))
    n = EYE_N * np.array((s, 1, 1))
    hit = bvh.ray_cast(Vector(e + n * 0.04), Vector(-n), 0.08)[0]
    c = np.array(hit if hit is not None else e) - n * 0.0025
    return c, n


def _jaw_half(y):
    """The lower jaw's half width at y (its loft rows)."""
    return float(np.interp(y, (-0.915, -0.870, -0.800, -0.720), (0.020, 0.028, 0.035, 0.040)))


def build_ribs(bm):
    """Rib bars across the hole: lofts following the flank's surface (from before the cavity) RIB_DEPTH under it, from
    beyond the rim at the top to beyond it at the bottom (the ends buried in the walls). -> BMVerts."""
    co, no = _WOUND_SURF.get('co'), _WOUND_SURF.get('no')
    if co is None or not len(co):
        return []
    kd = KDTree(len(co))
    for i, p in enumerate(co):
        kd.insert(Vector((0.0, p[1], p[2])), i)
    kd.balance()
    c = WOUND['c']
    vs = []
    u0 = rib_u(c[1] - WOUND['ry'] * 1.3, c[2])
    u1 = rib_u(c[1] + WOUND['ry'] * 1.3, c[2])
    rng = np.random.default_rng(7)
    n_rib = 0
    for k in range(int(math.ceil(u0)), int(math.floor(u1)) + 1):
        rows, ups = [], []
        w = 0.0068 * rng.uniform(0.85, 1.15)                  # not a grille: each rib its own width and depth
        dep = RIB_DEPTH * rng.uniform(0.8, 1.25)
        for z in np.linspace(c[2] - 1.25 * WOUND['rz'], c[2] + 1.25 * WOUND['rz'], 6):
            y = RIB_Y0 + k * RIB_DY + RIB_SLANT * (RIB_Z0 - z)
            near = kd.find_n(Vector((0.0, y, z)), 4)
            p = np.mean([co[i] for _, i, _ in near], axis=0)
            n = np.mean([no[i] for _, i, _ in near], axis=0)
            n /= np.linalg.norm(n)
            q = np.array((p[0], y, z)) - n * dep
            rows.append((q[0], q[1], q[2], w, 0.0045, 0.0045))
            ups.append(n)
        # a rib only where it crosses the hole
        mid = np.array([[c[0], r[1], r[2]] for r in rows])
        if wound_e(mid)[0].min() > 0.92:
            continue
        up = tuple(np.mean(ups, axis=0))
        if n_rib == RIB_BROKEN:                                # one rib snapped: an upper piece and a lower stub
            top, bot = rows[3:], rows[:2]
            a, b_ = np.array(rows[3][:3]), np.array(rows[2][:3])
            top = [tuple(a + (b_ - a) * 0.55) + rows[2][3:]] + top
            vs += loft(bm, top, up=up, seg=6, per_seg=1, cap0=0.0, cap1=0.0)
            a, b_ = np.array(rows[1][:3]), np.array(rows[2][:3])
            vs += loft(bm, bot + [tuple(a + (b_ - a) * 0.35) + rows[2][3:]], up=up, seg=6, per_seg=1, cap0=0.0,
                       cap1=0.0)
        else:
            vs += loft(bm, rows, up=up, seg=6, per_seg=1, cap0=0.0, cap1=0.0)
        n_rib += 1
    return vs


RIB_BROKEN = 2                                # which rib across the hole is snapped (counted from the front)


def wound_dent(co):
    """How far each game-mesh vertex lies under the flank's surface from before the cavity, 0..1 of WOUND['depth']
    (the painter's "inside the hole": the outline alone painted a red face where the sculpt had not dented, on skin
    facing up)."""
    out = np.zeros(len(co))
    sc, sn = _WOUND_SURF.get('co'), _WOUND_SURF.get('no')
    if sc is None or not len(sc):
        return out
    e, side = wound_e(hw_inv(co))
    sel = np.nonzero(side & (e < 1.6))[0]
    kd = KDTree(len(sc))
    for i, p in enumerate(sc):
        kd.insert(Vector(p), i)
    kd.balance()
    for i in sel:
        _, j, _ = kd.find(Vector(co[i]))
        out[i] = (sc[j] - co[i]) @ sn[j]
    return np.clip(out / WOUND['depth'], 0, 1)


def build_mouth_and_eyes(low):
    """Lower jaw, tongue, teeth, eyes and the rib bars: separate shells (no remesh). -> (bmesh, {part: BMVerts})"""
    bm = bmesh.new()
    tags = {}
    # lower jaw and tongue: the wolf's
    jaw = [(0, -0.720, 0.775, 0.040, 0.015, 0.030), (0, -0.800, 0.772, 0.035, 0.018, 0.025),
           (0, -0.870, 0.774, 0.028, 0.016, 0.020), (0, -0.915, 0.776, 0.020, 0.013, 0.016)]
    tags['jaw'] = loft(bm, jaw, up=(0, 0, 1), seg=14, per_seg=3, cap0=0.5, cap1=0.7)
    tongue = [(0, -0.765, 0.785, 0.017, 0.005, 0.005), (0, -0.850, 0.786, 0.016, 0.005, 0.005),
              (0, -0.900, 0.785, 0.012, 0.004, 0.004)]
    tags['tongue'] = loft(bm, tongue, up=(0, 0, 1), seg=6, per_seg=2, cap0=0.4, cap1=0.9)
    # bared teeth: the upper ones rooted in the gum under the drawn-back lip (LIP_UP), hanging outside the lower jaw;
    # the lower ones rise from the jaw inside them
    teeth, lower = [], []
    for s in (1, -1):
        teeth += cone(bm, (s * 0.0275, -0.903, 0.803), (s * 0.0292, -0.897, 0.766), 0.0058, seg=5,
                      bend=(s * 0.0015, 0.004, 0))                                   # canines
        lower += cone(bm, (s * 0.0172, -0.914, 0.780), (s * 0.0186, -0.919, 0.809), 0.0046, seg=5,
                      bend=(0, -0.002, 0))
        for k in range(3):                          # premolars and carnassial: a jagged row along the gum
            y = -0.873 + 0.031 * k
            x = _jaw_half(y) + 0.0045
            teeth += cone(bm, (s * x, y, 0.801), (s * (x + 0.001), y + 0.003, 0.777 - 0.002 * k),
                          0.0050 + 0.0009 * k, seg=5)
            xl = _jaw_half(y + 0.015) - 0.006
            lower += cone(bm, (s * xl, y + 0.015, 0.783), (s * xl, y + 0.017, 0.799), 0.0034, seg=4)
        for k in range(3):                          # incisors, the front row bared too
            x = 0.0045 + 0.0072 * k
            teeth += cone(bm, (s * x, -0.929 + 0.002 * k, 0.802), (s * x, -0.930 + 0.002 * k, 0.783), 0.0029, seg=4)
            if k < 2:
                xl = 0.004 + 0.007 * k
                lower += cone(bm, (s * xl, -0.921, 0.781), (s * xl, -0.923, 0.797), 0.0026, seg=4)
    tags['tooth'] = teeth
    tags['tooth_low'] = lower
    _warp_verts(bm.verts)
    eyes = []
    for s in (1, -1):
        c, n = _eye_centre(low, s)
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        vs = dome(bm, c, n, EYE_R, 0.0085, seg=12, rings=3)
        nv = Vector(n)
        t = Vector((0, 1, 0.35))
        t = (t - nv * t.dot(nv)).normalized()
        b = nv.cross(t)
        cv = Vector(c)
        for v in vs:                                # the wolf's almond, a little rounder (lids slack)
            d = v.co - cv
            v.co = cv + t * (d.dot(t) * 1.30) + b * (d.dot(b) * 0.80) + nv * d.dot(nv)
        eyes += vs
    tags['eye'] = eyes
    tags['bone'] = build_ribs(bm)
    return bm, tags


def build_body(voxel=0.004, target_tris=3900):
    """-> (ZombieWolfBody (fur body joined with the mouth, eyes and ribs, info attribute set), ZWF_BodyHi)."""
    _WOUND_SURF.clear()
    fur, hi = build_fur_body(voxel, target_tris)
    nfur = len(fur.data.vertices)
    co = np.array([v.co[:] for v in fur.data.vertices])
    nose = np.linalg.norm((hw_inv(co) - (0, -0.950, 0.836)) / (0.025, 0.02, 0.021), axis=1) < 1.0
    part_fur = np.where(nose, PART['nose'], PART['fur'])
    dent = wound_dent(co)
    bm, tags = build_mouth_and_eyes(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, PREFIX, BODY)
    _write_info(body.data, np.concatenate([part_fur, part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    att = body.data.color_attributes["info"]                 # info.b: how deep the hole is here (0..1 of DEPTH)
    buf = np.empty(len(body.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    buf = buf.reshape(-1, 4)
    buf[:nfur, 2] = dent
    att.data.foreach_set('color', buf.ravel())
    for k, v in LM.items():                       # the painter reads the eyes from here
        body[k] = [float(c) for c in v]
    return body, hi
