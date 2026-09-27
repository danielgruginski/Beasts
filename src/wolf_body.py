"""Grey wolf for the colony sim: procedural body, built standing (the bind pose), facing -Y, left side +X.

build_body() -> WolfBody, one mesh:
  - the furred body: lofted and ellipsoid parts fused by a voxel remesh, symmetrised, fur tufts sculpted along the
    fur flow, decimated (a dense copy, WLF_BodyHi, is kept for the texture bake);
  - the lower jaw, tongue, teeth and eyes, built as separate pieces so the mouth can open.
The point attribute "info" holds (part / 255, 0, 0, 1) for the painter (PART).
rest_bones() is the skeleton (Unity Generic rig) in the same bind pose.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, mesh_obj, get_coll, remove_obj, smoothstep, fbm
import beast_body
from beast_body import (PART, ellipsoid, _gauss, _clean, _apply_mod, _arrays, _set_co, _edges, fillet, unfold,
                        _write_info, read_info, tri_report, _mx)

# info.g = 1 on pieces that ride on the lower jaw (jaw, tongue, lower teeth)

# ------------------------------------------------------------------------------------------ landmarks (metres)
# Left-side joints; the right side mirrors x. Shoulder (withers) ~0.78 m, nose to rump ~1.5 m.
J = dict(
    SCAP=(0.060, -0.26, 0.755),     # top of the shoulder blade
    SHO=(0.100, -0.40, 0.580),      # shoulder joint
    ELB=(0.105, -0.32, 0.400),      # elbow
    WRI=(0.095, -0.33, 0.125),      # wrist (carpus)
    FPAW=(0.090, -0.37, 0.035),     # front paw, over the pads
    FTOE=(0.090, -0.435, 0.020),
    HIP=(0.085, 0.33, 0.655),       # hip joint
    KNEE=(0.100, 0.21, 0.460),      # stifle
    HOCK=(0.095, 0.41, 0.215),      # hock (heel)
    HPAW=(0.090, 0.38, 0.035),
    HTOE=(0.090, 0.325, 0.020),
)
HC = np.array((0.0, -0.725, 0.875))          # cranium centre
HR = np.array((0.070, 0.085, 0.070))         # cranium radii
HINGE = (0.0, -0.700, 0.790)                 # jaw hinge (below and in front of the ear)
LIP_Z = 0.780                                # the lip line: the upper muzzle's lips hang over the lower jaw
TAIL = [(0, 0.44, 0.700), (0, 0.535, 0.640), (0, 0.595, 0.540), (0, 0.630, 0.430), (0, 0.648, 0.330),
        (0, 0.655, 0.255)]
EYE0 = np.array((0.045, -0.786, 0.882))       # eye (left), before it is snapped onto the sculpted socket
EYE_N = np.array((0.52, -0.80, 0.22)) / np.linalg.norm((0.52, -0.80, 0.22))
EYE_R = 0.0170                               # stylised: ~1.3x a real wolf's, so the eyes read in game
EAR = [(0.045, -0.690, 0.918, 0.040, 0.016, 0.024), (0.056, -0.687, 0.962, 0.032, 0.013, 0.018),
       (0.067, -0.684, 1.000, 0.020, 0.010, 0.012), (0.075, -0.682, 1.030, 0.008, 0.006, 0.006)]
LM = {}

# The head is modelled at natural size and then enlarged as a whole (a smooth warp that fades out along the neck),
# so it reads at the colony camera. Everything placed on the head goes through hw(): parts, tufts, jaw and teeth,
# bones. Sculpt masks and the painter work in unwarped coordinates (hw_inv).
HEAD_K = 1.12
HEAD_C = np.array((0.0, -0.63, 0.84))


def _hw_w(y):
    return smoothstep(-0.60, -0.70, y)


def hw(P):
    P = np.asarray(P, float)
    return P + (P - HEAD_C) * ((HEAD_K - 1) * _hw_w(P[..., 1]))[..., None]


def hw_inv(Q):
    Q = np.asarray(Q, float)
    P = Q.copy()
    for _ in range(10):
        P = Q - (P - HEAD_C) * ((HEAD_K - 1) * _hw_w(P[..., 1]))[..., None]
    return P


def _warp_verts(verts):
    for v in verts:
        v.co = Vector(hw(v.co[:]))


# ------------------------------------------------------------------------------------------ parts
def build_trunk(bm):
    rows = [  # y, z centre, half width, up radius, down radius
        (-0.470, 0.600, 0.080, 0.100, 0.100),
        (-0.400, 0.610, 0.118, 0.155, 0.175),
        (-0.280, 0.612, 0.135, 0.165, 0.195),
        (-0.140, 0.622, 0.133, 0.145, 0.175),
        (0.000, 0.642, 0.115, 0.118, 0.125),
        (0.130, 0.652, 0.110, 0.103, 0.105),
        (0.260, 0.658, 0.118, 0.103, 0.115),
        (0.370, 0.655, 0.116, 0.100, 0.128),
        (0.460, 0.640, 0.088, 0.085, 0.100),
    ]
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in rows], up=(0, 0, 1), seg=24, cap0=0.7, cap1=0.6)
    # neck, carried forward and up to the back of the skull
    neck = [(0, -0.30, 0.660, 0.100, 0.120, 0.130), (0, -0.44, 0.720, 0.095, 0.110, 0.120),
            (0, -0.56, 0.790, 0.085, 0.095, 0.100), (0, -0.67, 0.850, 0.070, 0.075, 0.080)]
    loft(bm, neck, up=(0, 0, 1), seg=20, cap0=0.5, cap1=0.5)
    # the ruff: a thick collar of fur round the neck and throat (tufted later)
    ruff = Matrix.Rotation(math.radians(-30), 3, 'X')           # long axis along the neck
    ellipsoid(bm, (0, -0.49, 0.735), (0.105, 0.165, 0.115), rot=ruff)
    ellipsoid(bm, (0, -0.53, 0.670), (0.080, 0.090, 0.090), rot=ruff)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.080, 0.290, 0.560), (0.050, 0.100, 0.140),
                  rot=Matrix.Rotation(math.radians(-32), 3, 'X'))                 # thigh
        ellipsoid(bm, (s * 0.085, 0.200, 0.520), (0.050, 0.070, 0.060))       # flank fold to the stifle
    # tail, carried low
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, (0.036, 0.050, 0.060, 0.062, 0.054, 0.034))]
    loft(bm, tail, up=(0, 1, 0), seg=16, cap0=0.4, cap1=0.9)


def build_head(bm):
    ellipsoid(bm, HC, HR, seg=24, rings=16)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.048, -0.740, 0.830), (0.028, 0.045, 0.030))        # cheeks
        ellipsoid(bm, (s * 0.062, -0.695, 0.815), (0.030, 0.038, 0.062),
                  rot=Matrix.Rotation(math.radians(20), 3, 'X'))              # cheek ruff framing the face
    ellipsoid(bm, (0, -0.740, 0.785), (0.045, 0.050, 0.047))                   # jowls: hide the back of the jaw
    # upper muzzle: box section; its lips hang below the lower jaw's upper edge (the jaw sits inside them)
    muzzle = [(0, -0.770, 0.843, 0.056, 0.062, 0.071), (0, -0.820, 0.832, 0.048, 0.053, 0.060),
              (0, -0.870, 0.824, 0.040, 0.042, 0.051), (0, -0.910, 0.820, 0.034, 0.036, 0.046),
              (0, -0.935, 0.818, 0.030, 0.033, 0.042)]
    loft(bm, muzzle, up=(0, 0, 1), seg=20, cap0=0.55, cap1=0.6, shape=0.6)
    ellipsoid(bm, (0, -0.950, 0.836), (0.022, 0.015, 0.017))                  # nose leather
    ellipsoid(bm, (0, -0.930, 0.782), (0.024, 0.016, 0.013))                  # front of the upper lip
    for s in (1, -1):
        loft(bm, [(s * r[0], r[1], r[2], r[3], r[4], r[5]) for r in EAR], up=(0, -1, 0), seg=16, cap0=0.3,
             cap1=0.8, shape=0.9)


def build_leg_front(bm, s):
    rows = [(0.090, -0.405, 0.640, 0.044, 0.072, 0.072), (0.097, -0.390, 0.550, 0.046, 0.064, 0.074),
            (0.105, -0.345, 0.450, 0.043, 0.050, 0.058), (0.101, -0.325, 0.350, 0.035, 0.040, 0.038),
            (0.098, -0.330, 0.220, 0.027, 0.029, 0.026), (0.095, -0.332, 0.130, 0.023, 0.025, 0.023),
            (0.092, -0.350, 0.070, 0.021, 0.022, 0.020), (0.090, -0.365, 0.045, 0.023, 0.021, 0.021)]
    loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.5)
    ellipsoid(bm, (s * 0.105, -0.300, 0.420), (0.024, 0.024, 0.030))          # point of the elbow
    _paw(bm, s, -0.385, 1.0)


def build_leg_hind(bm, s):
    rows = [(0.098, 0.215, 0.480, 0.046, 0.048, 0.054), (0.100, 0.270, 0.380, 0.038, 0.034, 0.056),
            (0.097, 0.340, 0.300, 0.029, 0.025, 0.043), (0.095, 0.400, 0.225, 0.022, 0.022, 0.030),
            (0.092, 0.405, 0.150, 0.020, 0.021, 0.022), (0.090, 0.392, 0.080, 0.020, 0.021, 0.021),
            (0.090, 0.385, 0.045, 0.022, 0.021, 0.021)]
    loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.5)
    ellipsoid(bm, (s * 0.096, 0.425, 0.225), (0.017, 0.020, 0.026))            # point of the hock
    _paw(bm, s, 0.365, 0.92)


def _paw(bm, s, y, k):
    """Oval paw with four toes in front (the middle pair ahead). Soles are flattened after the remesh."""
    x = s * 0.090
    ellipsoid(bm, (x, y, 0.030), (0.033 * k, 0.042 * k, 0.031), seg=16, rings=10)
    for dx, dy, r in ((-0.011, -0.037, 0.015), (0.011, -0.037, 0.015), (-0.028, -0.024, 0.0135), (0.028, -0.024, 0.0135)):
        ellipsoid(bm, (x + s * dx * k, y + dy * k, 0.020), (r * k, r * 1.25 * k, 0.018), seg=12, rings=8)


# ------------------------------------------------------------------------------------------ fur
# Stylised tufts that carry the silhouette (a noise sculpt alone decimates away). Left side and centre line; the
# left ones are mirrored. (anchor near the surface, direction, length, base radius)
TUFTS = [
    # cheek ruff framing the face, sweeping back and down
    ((0.075, -0.705, 0.850), (0.6, 0.6, -0.1), 0.040, 0.016),
    ((0.082, -0.700, 0.815), (0.7, 0.5, -0.45), 0.048, 0.018),
    ((0.072, -0.690, 0.778), (0.5, 0.3, -0.8), 0.048, 0.018),
    ((0.045, -0.700, 0.752), (0.25, 0.2, -1.0), 0.042, 0.017),
    # the ruff: a mane round the neck, back and down
    ((0.000, -0.620, 0.905), (0.0, 1.0, 0.35), 0.052, 0.024),
    ((0.052, -0.615, 0.885), (0.35, 1.0, 0.15), 0.052, 0.024),
    ((0.090, -0.600, 0.830), (0.65, 0.8, -0.15), 0.055, 0.024),
    ((0.102, -0.570, 0.760), (0.65, 0.6, -0.5), 0.055, 0.025),
    ((0.090, -0.560, 0.685), (0.5, 0.35, -0.8), 0.052, 0.024),
    ((0.050, -0.580, 0.630), (0.25, 0.25, -1.0), 0.050, 0.023),
    ((0.000, -0.585, 0.615), (0.0, 0.2, -1.0), 0.052, 0.024),
    ((0.060, -0.500, 0.845), (0.4, 1.0, 0.1), 0.045, 0.022),
    ((0.105, -0.480, 0.780), (0.7, 0.8, -0.3), 0.045, 0.022),
    ((0.100, -0.470, 0.690), (0.6, 0.5, -0.7), 0.040, 0.020),
    # hackles over the withers
    ((0.000, -0.470, 0.860), (0.0, 1.0, 0.25), 0.048, 0.022),
    ((0.000, -0.360, 0.820), (0.0, 1.0, 0.15), 0.042, 0.020),
    ((0.038, -0.400, 0.825), (0.35, 1.0, 0.0), 0.038, 0.018),
    ((0.000, -0.250, 0.795), (0.0, 1.0, 0.1), 0.034, 0.017),
    # brisket and belly fringe
    ((0.030, -0.470, 0.470), (0.15, 0.4, -1.0), 0.032, 0.016),
    ((0.000, -0.430, 0.435), (0.0, 0.4, -1.0), 0.032, 0.016),
    ((0.060, -0.200, 0.465), (0.2, 0.4, -1.0), 0.026, 0.014),
    ((0.050, -0.060, 0.530), (0.2, 0.5, -1.0), 0.024, 0.013),
    # elbows and breeches
    ((0.122, -0.285, 0.425), (0.25, 1.0, -0.5), 0.030, 0.013),
    ((0.100, 0.445, 0.560), (0.35, 0.7, -0.8), 0.042, 0.020),
    ((0.104, 0.420, 0.470), (0.35, 0.5, -1.0), 0.040, 0.019),
    ((0.080, 0.450, 0.630), (0.25, 1.0, -0.4), 0.036, 0.018),
    # tail: along both sides, and the tip
    ((0.055, 0.560, 0.610), (0.6, 0.8, -0.6), 0.040, 0.020),
    ((0.062, 0.600, 0.520), (0.6, 0.5, -0.9), 0.042, 0.021),
    ((0.058, 0.630, 0.420), (0.6, 0.3, -1.0), 0.040, 0.020),
    ((0.045, 0.648, 0.330), (0.4, 0.2, -1.0), 0.036, 0.018),
    ((0.000, 0.655, 0.260), (0.0, 0.15, -1.0), 0.050, 0.020),
    ((0.000, 0.600, 0.560), (0.0, 1.0, -0.4), 0.040, 0.020),
    ((0.000, 0.640, 0.440), (0.0, 1.0, -0.8), 0.040, 0.020),
]


def build_tufts(bm, bvh):
    beast_body.build_tufts(bm, bvh, TUFTS, warp=hw)


def fur_flow(P, N):
    """Direction the fur lies in at points P with normals N (unit, in the tangent plane). Back toward the tail on
    the body and head, back and down on the flanks, down the legs, along the tail, up the ears."""
    Pu = hw_inv(P)
    x, y, z = Pu[..., 0], Pu[..., 1], Pu[..., 2]
    body = np.stack([np.zeros_like(x), np.ones_like(x), -0.55 * (1 - np.clip(N[..., 2], 0, 1))], -1)
    cheek = np.stack([np.sign(x) * 0.6, np.ones_like(x), -0.25 * np.ones_like(x)], -1)
    down = np.stack([np.zeros_like(x), 0.15 * np.ones_like(x), -np.ones_like(x)], -1)
    tailf = np.stack([np.zeros_like(x), 0.35 * np.ones_like(x), -np.ones_like(x)], -1)
    up = np.stack([np.zeros_like(x), 0.1 * np.ones_like(x), np.ones_like(x)], -1)
    w_leg = smoothstep(0.46, 0.34, z) * (np.abs(x) > 0.045)
    w_tail = smoothstep(0.46, 0.50, y) * smoothstep(0.69, 0.64, z)
    w_cheek = smoothstep(-0.66, -0.72, y) * smoothstep(0.02, 0.05, np.abs(x)) * smoothstep(0.90, 0.86, z)
    w_ear = smoothstep(0.915, 0.94, z) * smoothstep(-0.64, -0.67, y)
    F = body
    for w, d in ((w_cheek, cheek), (w_leg, down), (w_tail, tailf), (w_ear, up)):
        F = F * (1 - w[..., None]) + d * w[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def fur_amount(P, N):
    """How long the fur is (tuft height, metres)."""
    P = hw_inv(P)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    ax = np.abs(x)
    A = np.full(len(P), 0.0022)
    A = A + 0.007 * _gauss(P, (0, -0.52, 0.72), (0.11, 0.09, 0.11))                        # ruff
    A = A + 0.006 * _gauss(np.stack([ax, y, z], -1), (0.085, -0.700, 0.810), (0.025, 0.035, 0.05))   # cheek ruff
    A = A + 0.005 * _gauss(P, (0, -0.30, 0.79), (0.07, 0.12, 0.05)) * (N[:, 2] > 0.2)     # hackles
    A = A + 0.008 * smoothstep(0.47, 0.53, y) * smoothstep(0.69, 0.64, z) * smoothstep(0.25, 0.33, z)   # tail
    A = A + 0.006 * _gauss(np.stack([ax, y, z], -1), (0.10, 0.40, 0.52), (0.05, 0.06, 0.08)) * (N[:, 1] > -0.1)  # breeches
    A = A + 0.007 * (N[:, 2] < -0.35) * smoothstep(-0.40, -0.30, y) * smoothstep(0.25, 0.10, y) * (z > 0.40)   # belly fringe
    A = A + 0.006 * _gauss(np.stack([ax, y, z], -1), (0.11, -0.30, 0.42), (0.03, 0.03, 0.04))            # elbow feathering
    A = A * (1 - 0.7 * smoothstep(0.34, 0.24, z) * (y < 0.47))                             # sleek lower legs
    A = A * (1 - 0.9 * smoothstep(-0.74, -0.78, y))                                          # short on the face
    A = A * (1 - smoothstep(0.915, 0.935, z) * smoothstep(-0.64, -0.67, y))                 # no tufts on the ears
    return A


def sculpt_fur(co, no, seed=5):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed)


# ------------------------------------------------------------------------------------------ helpers


def sculpt_face(co, no):
    """Eye sockets under a brow, nostrils, the lip line; ears cupped in front."""
    out = co.copy()
    co = hw_inv(co)
    ax = np.abs(co[:, 0])
    Pm = np.stack([ax, co[:, 1], co[:, 2]], -1)
    out -= no * (0.0070 * _gauss(Pm, EYE0, (0.015, 0.014, 0.011)))[:, None]                      # socket
    out += no * (0.0045 * _gauss(Pm, EYE0 + np.array((-0.004, 0.006, 0.014)), (0.016, 0.012, 0.006)))[:, None]   # brow
    out -= no * (0.0030 * _gauss(Pm, (0.032, -0.805, 0.874), (0.008, 0.02, 0.006)))[:, None]      # tear line groove
    out -= no * (0.0040 * _gauss(Pm, (0.0085, -0.957, 0.832), (0.004, 0.004, 0.004)))[:, None]    # nostrils
    # ears: cup the front face
    for s in (1, -1):
        b = np.array(_mx(EAR[0][:3]) if s < 0 else EAR[0][:3])
        t_ = np.array(_mx(EAR[-1][:3]) if s < 0 else EAR[-1][:3])
        axis = t_ - b
        L = np.linalg.norm(axis)
        axis /= L
        rel = co - b
        t = np.clip((rel @ axis) / L, 0, 1)
        side = rel - np.outer(rel @ axis, axis)
        half = 0.037 * (1 - t) + 0.006
        wide = np.linalg.norm(side * np.array([1, 0, 1]), axis=1)
        inside = (rel @ axis > -0.005) & (rel @ axis < L) & (np.linalg.norm(side, axis=1) < half + 0.01)
        front = no[:, 1] < -0.3
        cup = 0.0050 * np.sin(np.pi * np.clip(t * 1.25, 0, 1)) * np.clip(1 - (wide / half) ** 2, 0, 1)
        out[:, 1] += np.where(inside & front, cup, 0.0)
    return out


# ------------------------------------------------------------------------------------------ body
def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face and the legs keep relatively more."""
    face = co.y < -0.68 and co.z > 0.75
    leg = co.z < 0.42 and abs(co.x) > 0.05 and co.y < 0.47
    return 1.0 - 0.25 * float(face) - 0.35 * float(leg)


def build_fur_body(voxel=0.004, target_tris=4000):
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
    return beast_body.fuse_body(bm, "WLF", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                dec_weight=_dec_weight)


def _eye_centre(low, s):
    """Where the eye dome sits: on the game mesh's socket, a little sunk in (decimation fills the dense socket)."""
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    e = hw(EYE0 * np.array((s, 1, 1)))
    n = EYE_N * np.array((s, 1, 1))
    hit = bvh.ray_cast(Vector(e + n * 0.04), Vector(-n), 0.08)[0]
    c = np.array(hit if hit is not None else e) - n * 0.0025
    return c, n


def build_mouth_and_eyes(low):
    """Lower jaw, tongue, teeth, eyes: separate shells (no remesh). Returns {part: bmesh verts} in one bmesh."""
    bm = bmesh.new()
    tags = {}
    # lower jaw: the back end stays hidden in the jowls; it tucks inside the upper lip
    jaw = [(0, -0.720, 0.775, 0.040, 0.015, 0.030), (0, -0.800, 0.772, 0.035, 0.018, 0.025),
           (0, -0.870, 0.774, 0.028, 0.016, 0.020), (0, -0.915, 0.776, 0.020, 0.013, 0.016)]
    tags['jaw'] = loft(bm, jaw, up=(0, 0, 1), seg=14, per_seg=3, cap0=0.5, cap1=0.7)
    tongue = [(0, -0.765, 0.785, 0.017, 0.005, 0.005), (0, -0.850, 0.786, 0.016, 0.005, 0.005),
              (0, -0.900, 0.785, 0.012, 0.004, 0.004)]
    tags['tongue'] = loft(bm, tongue, up=(0, 0, 1), seg=6, per_seg=2, cap0=0.4, cap1=0.9)
    teeth, lower = [], []
    # upper teeth hang from the palate (the muzzle's underside, z ~0.775) into the closed jaw; lower teeth rise from
    # the jaw into the muzzle. Closed, only the tips of the upper canines show over the lower lip.
    for s in (1, -1):
        teeth += cone(bm, (s * 0.021, -0.905, 0.782), (s * 0.022, -0.900, 0.760), 0.0045, seg=5,
                      bend=(0, 0.003, 0))
        lower += cone(bm, (s * 0.017, -0.915, 0.774), (s * 0.018, -0.918, 0.795), 0.0038, seg=5,
                    bend=(0, 0.002, 0))
        for k in range(3):            # upper cheek teeth (premolars, carnassial), smaller lower ones
            y = -0.875 + 0.030 * k
            x = 0.022 + 0.004 * k
            teeth += cone(bm, (s * x, y, 0.782), (s * x, y + 0.004, 0.766 - 0.002 * k), 0.0035 + 0.0008 * k, seg=4)
            lower += cone(bm, (s * (x - 0.003), y + 0.012, 0.776), (s * (x - 0.003), y + 0.014, 0.788), 0.003, seg=4)
        for k in range(2):            # incisors
            x = 0.004 + 0.007 * k
            teeth += cone(bm, (s * x, -0.930, 0.782), (s * x, -0.930, 0.770), 0.0028, seg=4)
            lower += cone(bm, (s * x, -0.922, 0.774), (s * x, -0.923, 0.786), 0.0024, seg=4)
    tags['tooth'] = teeth
    tags["tooth_low"] = lower
    _warp_verts(bm.verts)
    eyes = []
    for s in (1, -1):
        c, n = _eye_centre(low, s)
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        vs = dome(bm, c, n, EYE_R, 0.0085, seg=12, rings=3)
        # almond: long from the inner corner (front, low) to the outer corner (back, high)
        nv = Vector(n)
        t = Vector((0, 1, 0.35))
        t = (t - nv * t.dot(nv)).normalized()
        b = nv.cross(t)
        cv = Vector(c)
        for v in vs:
            d = v.co - cv
            v.co = cv + t * (d.dot(t) * 1.35) + b * (d.dot(b) * 0.72) + nv * d.dot(nv)
        eyes += vs
    tags['eye'] = eyes
    return bm, tags


def build_body(voxel=0.004, target_tris=4000):
    """-> (WolfBody (fur body joined with the mouth and eyes, info attribute set), WLF_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    nfur = len(fur.data.vertices)
    co = np.array([v.co[:] for v in fur.data.vertices])
    nose = np.linalg.norm((hw_inv(co) - (0, -0.950, 0.836)) / (0.025, 0.02, 0.021), axis=1) < 1.0
    part_fur = np.where(nose, PART['nose'], PART['fur'])

    bm, tags = build_mouth_and_eyes(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "WLF", "WolfBody")
    _write_info(body.data, np.concatenate([part_fur, part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
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
    head, tail = Vector(hw(head)), Vector(hw(tail))
    h, fr = _frame(head, Vector(tail) - Vector(head), zhint)
    B[name] = (h, fr, (Vector(tail) - Vector(head)).length, parent, deform)


def rest_bones():
    """name -> (head, Matrix3 frame (columns = bone X, Y, Z; Y along the bone), length, parent, deform).

    Root and Motion point up with +Z toward the wolf's front (world -Y), so they import into Unity with identity
    orientation. Motion (root motion) is a sibling of Root; nothing hangs from it (see Insectoids/HANDOFF.md).
    Legs and spine bend about their local X (Z points forward on the legs, up on the spine)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.25, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.20, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    _bone(B, "Hips", (0, 0.30, 0.665), (0, 0.46, 0.650), UP, "Root")
    _bone(B, "Spine1", (0, 0.30, 0.675), (0, 0.12, 0.690), UP, "Hips")
    _bone(B, "Spine2", (0, 0.12, 0.690), (0, -0.08, 0.700), UP, "Spine1")
    _bone(B, "Chest", (0, -0.08, 0.700), (0, -0.30, 0.690), UP, "Spine2")
    _bone(B, "Neck1", (0, -0.30, 0.690), (0, -0.50, 0.760), UP, "Chest")
    _bone(B, "Neck2", (0, -0.50, 0.760), (0, -0.66, 0.840), UP, "Neck1")
    _bone(B, "Head", (0, -0.66, 0.840), (0, -0.96, 0.840), UP, "Neck2")
    _bone(B, "Jaw", HINGE, (0, -0.925, 0.770), UP, "Head")
    _bone(B, "Tongue1", (0, -0.765, 0.785), (0, -0.850, 0.786), UP, "Jaw")
    _bone(B, "Tongue2", (0, -0.850, 0.786), (0, -0.910, 0.785), UP, "Tongue1")
    par = "Hips"
    for i in range(len(TAIL) - 1):
        _bone(B, f"Tail{i + 1}", TAIL[i], TAIL[i + 1], (0, 0.7, 0.7), par)
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
    _bone(B, "Socket_Saddle", (0, -0.10, 0.775), (0, -0.10, 0.855), FWD, "Spine2")
    _bone(B, "Socket_Head", (0, -0.71, 0.940), (0, -0.71, 1.020), FWD, "Head")
    _bone(B, "Socket_Mouth", (0, -0.870, 0.785), (0, -0.870, 0.865), FWD, "Jaw")
    _bone(B, "Socket_Collar", (0, -0.50, 0.740), (0, -0.58, 0.800), UP, "Neck1")   # +Y along the neck, +Z up
    return B
