"""Giant rat for the colony sim / RPG: procedural body, built standing (the bind pose), facing -Y, left side +X.

A sewer rat the size of a dog: arched back, big haunches, pointed snout with orange incisors that always show, round
thin ears, beady bulging eyes, pink hands and plantigrade feet, a long naked tail lying on the ground.

build_body() -> RatBody, one mesh:
  - the furred body: parts fused and decimated by beast_body.fuse_body, mangy tufts along the spine and flanks;
  - separate pieces: lower jaw, incisors, whiskers, eyes, and the tail (clean rings, so it bends smoothly).
rest_bones() is the skeleton (Unity Generic rig, the same bone names as the wolf, 8 tail bones, no tongue).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, mesh_obj, get_coll, remove_obj, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, read_info, tri_report, _mx

# ------------------------------------------------------------------------------------------ landmarks (metres)
J = dict(
    SCAP=(0.045, -0.13, 0.340),     # top of the shoulder blade
    SHO=(0.065, -0.21, 0.220),      # shoulder joint
    ELB=(0.070, -0.16, 0.130),      # elbow
    WRI=(0.068, -0.225, 0.045),     # wrist
    FPAW=(0.068, -0.255, 0.018),    # knuckles
    FTOE=(0.068, -0.300, 0.012),    # finger tips
    HIP=(0.075, 0.20, 0.270),       # hip joint
    KNEE=(0.095, 0.09, 0.180),      # knee (forward, hidden in the haunch)
    HOCK=(0.085, 0.22, 0.030),      # heel: the foot is flat on the ground (plantigrade)
    HPAW=(0.085, 0.10, 0.015),      # ball of the foot
    HTOE=(0.085, 0.05, 0.012),
)
HC = np.array((0.0, -0.41, 0.310))           # cranium centre
HR = np.array((0.058, 0.075, 0.052))
HINGE = (0.0, -0.410, 0.262)
TAIL = [(0, 0.28, 0.240), (0, 0.36, 0.200), (0, 0.46, 0.130), (0.00, 0.56, 0.072), (0.02, 0.66, 0.040),
        (0.06, 0.76, 0.026), (0.12, 0.85, 0.022), (0.20, 0.92, 0.020), (0.28, 0.97, 0.019)]
TAIL_R = (0.030, 0.026, 0.021, 0.017, 0.014, 0.011, 0.009, 0.007, 0.004)
EYE0 = np.array((0.046, -0.462, 0.330))
EYE_N = np.array((0.78, -0.42, 0.46)) / np.linalg.norm((0.78, -0.42, 0.46))
EYE_R = 0.0155                               # stylised (about 1.5x a rat's): beady, bulging, reads in game
EAR = [(0.040, -0.385, 0.340, 0.026, 0.009, 0.012), (0.052, -0.383, 0.378, 0.040, 0.008, 0.009),
       (0.062, -0.381, 0.412, 0.038, 0.007, 0.008), (0.069, -0.379, 0.436, 0.024, 0.006, 0.007)]
LM = {}

HEAD_K = 1.12                                # the head is enlarged as a whole so it reads (see wolf_body.hw)
HEAD_C = np.array((0.0, -0.30, 0.28))


def _hw_w(y):
    return smoothstep(-0.28, -0.36, y)


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
    rows = [  # y, z centre, half width, up radius, down radius: narrow chest, arched back, big haunches
        (-0.300, 0.240, 0.070, 0.085, 0.085),
        (-0.220, 0.258, 0.095, 0.110, 0.108),
        (-0.100, 0.280, 0.115, 0.130, 0.122),
        (0.020, 0.300, 0.135, 0.150, 0.133),
        (0.130, 0.300, 0.145, 0.150, 0.138),
        (0.230, 0.270, 0.130, 0.130, 0.128),
        (0.310, 0.230, 0.090, 0.090, 0.095),
    ]
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in rows], up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.6)
    neck = [(0, -0.270, 0.270, 0.075, 0.080, 0.085), (0, -0.345, 0.292, 0.065, 0.068, 0.070)]
    loft(bm, neck, up=(0, 0, 1), seg=20, per_seg=3, cap0=0.5, cap1=0.5)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.080, 0.170, 0.215), (0.068, 0.115, 0.100),
                  rot=Matrix.Rotation(math.radians(-20), 3, 'X'))                 # haunch
        ellipsoid(bm, (s * 0.060, -0.200, 0.200), (0.040, 0.050, 0.060))       # shoulder


def build_head(bm):
    ellipsoid(bm, HC, HR, seg=24, rings=16)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.040, -0.440, 0.292), (0.030, 0.045, 0.033))        # cheeks
    ellipsoid(bm, (0, -0.430, 0.258), (0.040, 0.045, 0.034))                   # jowls: hide the back of the jaw
    snout = [(0, -0.440, 0.305, 0.050, 0.045, 0.060), (0, -0.500, 0.290, 0.038, 0.035, 0.045),
             (0, -0.555, 0.279, 0.026, 0.025, 0.033), (0, -0.590, 0.273, 0.017, 0.017, 0.024)]
    loft(bm, snout, up=(0, 0, 1), seg=20, cap0=0.5, cap1=0.7, shape=0.85)
    ellipsoid(bm, (0, -0.600, 0.277), (0.013, 0.009, 0.011))                  # nose
    for s in (1, -1):
        ellipsoid(bm, (s * 0.017, -0.572, 0.268), (0.012, 0.018, 0.012))       # whisker pads
        loft(bm, [(s * r[0], r[1], r[2], r[3], r[4], r[5]) for r in EAR], up=(0, -1, 0), seg=16, cap0=0.3,
             cap1=0.9, shape=0.9)


def build_leg_front(bm, s):
    rows = [(0.060, -0.210, 0.250, 0.035, 0.045, 0.045), (0.068, -0.190, 0.170, 0.030, 0.030, 0.035),
            (0.070, -0.170, 0.120, 0.022, 0.022, 0.025), (0.069, -0.200, 0.080, 0.016, 0.016, 0.016),
            (0.068, -0.222, 0.045, 0.013, 0.013, 0.013), (0.068, -0.236, 0.026, 0.013, 0.013, 0.013)]
    loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=14, cap0=0.5, cap1=0.5)
    x = s * 0.068
    ellipsoid(bm, (x, -0.246, 0.018), (0.019, 0.024, 0.013), seg=14, rings=8)      # hand
    for dx, ang in ((-0.012, -18), (-0.004, -6), (0.004, 6), (0.012, 18)):
        a = math.radians(ang) * s
        base = Vector((x + s * dx, -0.258, 0.014))
        d = Vector((math.sin(a), -math.cos(a), -0.08)).normalized()
        rows = [tuple(base) + (0.0055,) * 3, tuple(base + d * 0.022) + (0.0048,) * 3, tuple(base + d * 0.038) + (0.004,) * 3]
        loft(bm, rows, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.4, cap1=0.9)
    ellipsoid(bm, (x - s * 0.017, -0.238, 0.020), (0.006, 0.008, 0.006), seg=8, rings=6)   # thumb nub


def build_leg_hind(bm, s):
    rows = [(0.090, 0.110, 0.190, 0.035, 0.035, 0.040), (0.090, 0.160, 0.120, 0.026, 0.024, 0.030),
            (0.087, 0.200, 0.060, 0.018, 0.018, 0.020), (0.085, 0.215, 0.035, 0.016, 0.016, 0.016)]
    loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=14, cap0=0.5, cap1=0.5)
    foot = [(0.085, 0.228, 0.020, 0.015, 0.012, 0.014), (0.085, 0.165, 0.017, 0.020, 0.011, 0.013),
            (0.085, 0.100, 0.015, 0.023, 0.010, 0.011)]
    loft(bm, [(s * r[0],) + r[1:] for r in foot], up=(0, 0, 1), seg=14, cap0=0.8, cap1=0.5)
    x = s * 0.085
    for dx, ang, ln in ((-0.018, -22, 0.034), (-0.009, -8, 0.046), (0.0, 0, 0.050), (0.009, 8, 0.046), (0.018, 24, 0.032)):
        a = math.radians(ang) * s
        base = Vector((x + s * dx, 0.098, 0.013))
        d = Vector((math.sin(a), -math.cos(a), -0.05)).normalized()
        rows = [tuple(base) + (0.0058,) * 3, tuple(base + d * ln * 0.6) + (0.005,) * 3, tuple(base + d * ln) + (0.0042,) * 3]
        loft(bm, rows, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.4, cap1=0.9)


# ------------------------------------------------------------------------------------------ fur
TUFTS = [
    # a mangy crest down the spine, staggered in two rows
    ((0.000, -0.290, 0.360), (0.0, 1.0, 0.80), 0.075, 0.024),
    ((0.000, -0.170, 0.395), (0.0, 1.0, 0.85), 0.090, 0.027),
    ((0.000, -0.050, 0.435), (0.0, 1.0, 0.85), 0.095, 0.028),
    ((0.000, 0.070, 0.455), (0.0, 1.0, 0.80), 0.095, 0.028),
    ((0.000, 0.190, 0.425), (0.0, 1.0, 0.60), 0.085, 0.026),
    ((0.035, -0.230, 0.375), (0.5, 1.0, 0.70), 0.070, 0.022),
    ((0.045, -0.110, 0.415), (0.5, 1.0, 0.75), 0.080, 0.024),
    ((0.050, 0.010, 0.445), (0.5, 1.0, 0.70), 0.082, 0.025),
    ((0.050, 0.130, 0.445), (0.5, 1.0, 0.60), 0.078, 0.024),
    # belly fringe
    ((0.080, -0.050, 0.172), (0.25, 0.40, -1.0), 0.045, 0.016),
    ((0.090, 0.100, 0.168), (0.25, 0.40, -1.0), 0.045, 0.016),
    # cheeks, neck, haunches
    ((0.058, -0.430, 0.285), (0.75, 0.60, -0.25), 0.040, 0.014),
    ((0.035, -0.330, 0.200), (0.25, 0.40, -1.0), 0.042, 0.015),
]


def fur_flow(P, N):
    """Fur lies back toward the tail on the body and head, back and down on the flanks, down the legs."""
    Pu = hw_inv(P)
    x, y, z = Pu[..., 0], Pu[..., 1], Pu[..., 2]
    body = np.stack([np.zeros_like(x), np.ones_like(x), -0.55 * (1 - np.clip(N[..., 2], 0, 1))], -1)
    down = np.stack([np.zeros_like(x), 0.15 * np.ones_like(x), -np.ones_like(x)], -1)
    w_leg = smoothstep(0.16, 0.10, z) * (np.abs(x) > 0.035)
    F = body * (1 - w_leg[..., None]) + down * w_leg[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def fur_amount(P, N):
    Pu = hw_inv(P)
    x, y, z = Pu[..., 0], Pu[..., 1], Pu[..., 2]
    A = np.full(len(P), 0.0022)
    A = A + 0.004 * smoothstep(0.2, 0.7, N[:, 2]) * smoothstep(-0.30, -0.20, y) * smoothstep(0.30, 0.22, y)   # back
    A = A * (1 - 0.8 * smoothstep(0.10, 0.06, z))                                            # sleek hands, feet
    A = A * (1 - 0.9 * smoothstep(-0.44, -0.50, y))                                          # short on the snout
    A = A * (1 - smoothstep(0.34, 0.36, z) * smoothstep(-0.34, -0.36, y) * (np.abs(x) > 0.03))   # no fur on the ears
    return A


def sculpt_fur(co, no, seed=7):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed, across=0.030, along_len=0.080)


def sculpt_face(co, no):
    """Eye sockets, nostrils; ears cupped in front."""
    out = co.copy()
    co = hw_inv(co)
    ax = np.abs(co[:, 0])
    Pm = np.stack([ax, co[:, 1], co[:, 2]], -1)
    out -= no * (0.0050 * _gauss(Pm, EYE0, (0.012, 0.012, 0.010)))[:, None]
    out -= no * (0.0025 * _gauss(Pm, (0.006, -0.607, 0.279), (0.003, 0.003, 0.003)))[:, None]
    for s in (1, -1):
        b = np.array(_mx(EAR[0][:3]) if s < 0 else EAR[0][:3])
        t_ = np.array(_mx(EAR[-1][:3]) if s < 0 else EAR[-1][:3])
        axis = t_ - b
        L = np.linalg.norm(axis)
        axis /= L
        rel = co - b
        t = np.clip((rel @ axis) / L, 0, 1)
        side = rel - np.outer(rel @ axis, axis)
        half = 0.033 * np.sin(np.pi * np.clip(0.25 + 0.75 * t, 0, 1)) + 0.006
        wide = np.linalg.norm(side * np.array([1, 0, 1]), axis=1)
        inside = (rel @ axis > -0.005) & (rel @ axis < L + 0.01) & (np.linalg.norm(side, axis=1) < half + 0.008)
        front = no[:, 1] < -0.3
        cup = 0.0035 * np.sin(np.pi * np.clip(t * 1.1, 0, 1)) * np.clip(1 - (wide / half) ** 2, 0, 1)
        out[:, 1] += np.where(inside & front, cup, 0.0)
    return out


def _dec_weight(co):
    face = co.y < -0.38 and co.z > 0.20
    limb = co.z < 0.10 and abs(co.x) > 0.035
    ear = co.z > 0.34 and co.y < -0.33
    return 1.0 - 0.25 * float(face) - 0.40 * float(limb) - 0.45 * float(ear)


def build_fur_body(voxel=0.003, target_tris=2100):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    for s in (1, -1):
        build_leg_front(bm, s)
        build_leg_hind(bm, s)
    _warp_verts(bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    beast_body.build_tufts(bm, BVHTree.FromBMesh(bm), TUFTS, warp=hw)
    return beast_body.fuse_body(bm, "RAT", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                dec_weight=_dec_weight, seam_x=0.009, flat_z=0.003)


# ------------------------------------------------------------------------------------------ separate pieces
def _eye_centre(low, s):
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    e = hw(EYE0 * np.array((s, 1, 1)))
    n = EYE_N * np.array((s, 1, 1))
    hit = bvh.ray_cast(Vector(e + n * 0.04), Vector(-n), 0.08)[0]
    c = np.array(hit if hit is not None else e) - n * 0.004
    return c, n


def build_pieces(low):
    """Lower jaw, incisors, whiskers (all warped with the head), eyes, tail."""
    bm = bmesh.new()
    tags = {}
    jaw = [(0, -0.425, 0.246, 0.030, 0.010, 0.019), (0, -0.490, 0.245, 0.022, 0.010, 0.013),
           (0, -0.525, 0.248, 0.015, 0.008, 0.009)]
    tags['jaw'] = loft(bm, jaw, up=(0, 0, 1), seg=12, per_seg=3, cap0=0.5, cap1=0.8)
    upper, lower, whisk = [], [], []
    for s in (1, -1):
        # chisel incisors: four-sided cones; the uppers hang in front, the long lowers rise behind them
        upper += cone(bm, (s * 0.0048, -0.586, 0.264), (s * 0.0048, -0.591, 0.236), 0.0048, seg=4,
                      bend=(0, 0.002, 0))
        lower += cone(bm, (s * 0.0042, -0.527, 0.240), (s * 0.0042, -0.578, 0.258), 0.0042, seg=4,
                      bend=(0, -0.002, 0))
        for k in range(4):
            base = Vector((s * 0.020, -0.574 + 0.006 * k, 0.270 - 0.004 * k))
            d = Vector((s * 1.0, 0.35 + 0.12 * k, 0.12 - 0.09 * k)).normalized()
            whisk += cone(bm, base, base + d * (0.085 + 0.012 * k), 0.0014, seg=3, bend=(0, 0.012, -0.010))
    tags['tooth'] = upper
    tags['tooth_low'] = lower
    tags['whisker'] = whisk
    _warp = lambda vs: [setattr(v, "co", Vector(hw(v.co[:]))) for v in vs]
    _warp(bm.verts)
    eyes = []
    for s in (1, -1):
        c, n = _eye_centre(low, s)
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        eyes += dome(bm, c, n, EYE_R, 0.0105, seg=12, rings=3)
    tags['eye'] = eyes
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, TAIL_R)]
    tags['tail'] = loft(bm, tail, up=(0, 0, 1), seg=8, per_seg=3, cap0=0.3, cap1=0.9)
    return bm, tags


def build_body(voxel=0.003, target_tris=2100):
    """-> (RatBody (fur body joined with the pieces, info attribute set), RAT_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    co = np.array([v.co[:] for v in fur.data.vertices])
    nose = np.linalg.norm((hw_inv(co) - (0, -0.600, 0.277)) / (0.016, 0.012, 0.014), axis=1) < 1.0
    part_fur = np.where(nose, PART['nose'], PART['fur'])
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "RAT", "RatBody")
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
    """name -> (head, Matrix3 frame, length, parent, deform); the wolf's conventions (Root/Motion point up, +Z to the
    front; legs and spine bend about their local X)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.15, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.12, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    _bone(B, "Hips", (0, 0.18, 0.300), (0, 0.28, 0.255), UP, "Root")
    _bone(B, "Spine1", (0, 0.18, 0.310), (0, 0.04, 0.330), UP, "Hips")
    _bone(B, "Spine2", (0, 0.04, 0.330), (0, -0.10, 0.310), UP, "Spine1")
    _bone(B, "Chest", (0, -0.10, 0.310), (0, -0.24, 0.280), UP, "Spine2")
    _bone(B, "Neck1", (0, -0.24, 0.280), (0, -0.30, 0.290), UP, "Chest")
    _bone(B, "Neck2", (0, -0.30, 0.290), (0, -0.36, 0.300), UP, "Neck1")
    _bone(B, "Head", (0, -0.36, 0.300), (0, -0.58, 0.280), UP, "Neck2")
    _bone(B, "Jaw", HINGE, (0, -0.530, 0.238), UP, "Head")
    par = "Hips"
    for i in range(len(TAIL) - 1):
        _bone(B, f"Tail{i + 1}", TAIL[i], TAIL[i + 1], (0, 0.3, 1.0), par)
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
        _bone(B, f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), UP, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
    # sockets (head = attach point; +Y up, +Z forward)
    _bone(B, "Socket_Back", (0, 0.00, 0.455), (0, 0.00, 0.535), FWD, "Spine2")
    _bone(B, "Socket_Head", (0, -0.40, 0.362), (0, -0.40, 0.442), FWD, "Head")
    _bone(B, "Socket_Mouth", (0, -0.510, 0.250), (0, -0.510, 0.330), FWD, "Jaw")
    return B
