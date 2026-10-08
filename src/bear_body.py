"""Cave bear: procedural body, built standing on all fours (the bind pose), facing -Y, left side +X.

Ursus spelaeus, bigger than any living bear: 1.45 m at the shoulder hump, about 2.65 m nose to rump, a head carried a
little below the hump with the cave bear's steep domed forehead over a long muzzle, small round ears, big jaws with
fangs that show when it roars, flat-footed (plantigrade) legs on broad paws with long pale claws. A shaggy coat: a
mane over the neck and shoulders, a short fringe under the belly, fringed sleeves on the forearms and breeches on the
hind legs, ruffs on the cheeks.

build_body() -> BearBody, one mesh:
  - the furred body: lofts and ellipsoids fused by beast_body.fuse_body (the coat's volumes, cape and skirt, too);
  - separate pieces: the lower jaw with its tongue and teeth (on the Jaw bone), the upper teeth, the eyes, the ears
    (cupped shells on Ear{L,R}), the claws (on the toes), and the coat's hair (beast_coat fringes and clumps).
The head is built in its own frame (beast_body.HeadFrame), pitched 20 degrees down from the poll.
rest_bones() is the skeleton (Unity Generic rig, the wolf's bone names, 2 tail bones, no tongue bones).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, read_info, tri_report, _mx, HeadFrame, cup_ear
from beast_coat import coat_loft, volume_bvh, loft_bvh, Snap, Drop, build_clumps, loop_anchors, fringe, write_hair_t

# ------------------------------------------------------------------------------------------ landmarks (metres)
# Left-side joints; the right side mirrors x. Plantigrade: the wrist and the heel sit near the ground.
J = dict(
    SCAP=(0.200, -0.40, 1.260),     # top of the shoulder blade, under the hump
    SHO=(0.300, -0.58, 0.980),      # shoulder joint
    ELB=(0.310, -0.36, 0.600),      # elbow (behind)
    WRI=(0.310, -0.50, 0.160),      # wrist
    FPAW=(0.310, -0.61, 0.055),     # ball of the forepaw
    FTOE=(0.310, -0.76, 0.035),     # toe tips (the claws carry on past them)
    HIP=(0.270, 0.58, 0.980),
    KNEE=(0.320, 0.40, 0.600),      # knee (forward)
    HOCK=(0.300, 0.74, 0.110),      # heel, near the ground
    HPAW=(0.300, 0.48, 0.050),      # ball of the hind foot
    HTOE=(0.300, 0.34, 0.035),
)
TAIL = [(0, 0.86, 1.02), (0, 0.93, 0.95), (0, 0.97, 0.86)]

HEAD = HeadFrame((0.0, -1.00, 1.16), 25.0)       # the poll; the head hangs 25 degrees down from it
hx, hx_inv, hx_dir = HEAD.hx, HEAD.hx_inv, HEAD.hx_dir
HINGE_H = (0.0, -0.12, -0.20)                   # jaw hinge (head space), under the ear, hidden in the jowl
HINGE = tuple(hx(HINGE_H))
EYE0_H = np.array((0.122, -0.275, 0.000))       # eye (left, head space), at the foot of the domed forehead
EYE0 = hx(EYE0_H)
EYE_N = hx_dir(np.array((0.62, -0.70, 0.30)) / np.linalg.norm((0.62, -0.70, 0.30)))
EYE_R = 0.022                                   # stylised: ~2x a bear's, so the eyes read in game
# ears: small round cups on the top corners of the skull, standing up and out (a separate shell on Ear{L,R})
EAR_BASE_H = (0.140, -0.07, 0.115)
EAR_DIR = np.array((0.38, 0.12, 1.0)) / np.linalg.norm((0.38, 0.12, 1.0))
EAR_LEN = 0.115
EAR_PROFILE = ((0.0, 0.040, 0.032), (0.35, 0.054, 0.038), (0.70, 0.048, 0.032), (0.93, 0.026, 0.018))
LM = {}


def ear_rows(s):
    base = hx(np.array(EAR_BASE_H) * np.array((s, 1, 1)))
    d = EAR_DIR * np.array((s, 1, 1))
    return base, base + d * EAR_LEN


# ------------------------------------------------------------------------------------------ coat volumes
# (y, z centre, half width, up radius, down radius); keep the centre lines level (a rising one tilts the rings)
CAPE = dict(rows=[(-1.02, 1.12, 0.24, 0.20, 0.20), (-0.88, 1.12, 0.36, 0.30, 0.28), (-0.70, 1.12, 0.46, 0.34, 0.30),
                  (-0.50, 1.12, 0.50, 0.34, 0.24), (-0.30, 1.12, 0.48, 0.28, 0.14), (-0.12, 1.12, 0.40, 0.22, 0.06)],
            cap0=0.4, cap1=0.5, shape=0.85)            # a mane over the neck and shoulders
SKIRT = dict(rows=[(-0.62, 0.78, 0.30, 0.18, 0.20), (-0.40, 0.78, 0.42, 0.20, 0.22), (-0.10, 0.78, 0.46, 0.20, 0.22),
                   (0.20, 0.78, 0.47, 0.20, 0.22), (0.45, 0.78, 0.44, 0.20, 0.20), (0.66, 0.80, 0.36, 0.18, 0.18)],
             cap0=0.5, cap1=0.5, shape=0.70)           # the shaggy underside


# ------------------------------------------------------------------------------------------ parts
def build_trunk(bm):
    rows = [  # y, z centre, half width, up radius, down radius: deep chest, hump over the shoulders, lower rump
        (-0.680, 0.980, 0.280, 0.260, 0.300),
        (-0.550, 1.000, 0.400, 0.380, 0.360),
        (-0.350, 1.000, 0.460, 0.420, 0.360),
        (-0.100, 0.980, 0.480, 0.360, 0.360),
        (0.180, 0.970, 0.480, 0.330, 0.350),
        (0.450, 0.960, 0.450, 0.290, 0.330),
        (0.660, 0.940, 0.380, 0.280, 0.300),
        (0.820, 0.900, 0.260, 0.220, 0.240),
    ]
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in rows], up=(0, 0, 1), seg=28, cap0=0.6, cap1=0.6)
    ellipsoid(bm, (0, -0.40, 1.33), (0.32, 0.34, 0.20), seg=20, rings=12)            # the hump
    ellipsoid(bm, (0, -0.06, 1.24), (0.28, 0.30, 0.12), seg=20, rings=10)            # the hump's slope to the back
    loft(bm, *coat_loft(CAPE))
    loft(bm, *coat_loft(SKIRT))
    neck = [(0, -0.68, 1.06, 0.28, 0.30, 0.32), (0, -0.86, 1.07, 0.25, 0.26, 0.28), (0, -1.00, 1.08, 0.21, 0.22, 0.24)]
    loft(bm, neck, up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.5)
    for s in (1, -1):
        ellipsoid(bm, (s * 0.30, -0.50, 1.00), (0.18, 0.22, 0.26))                   # shoulder
        ellipsoid(bm, (s * 0.28, 0.58, 0.92), (0.19, 0.26, 0.30),
                  rot=Matrix.Rotation(math.radians(-15), 3, 'X'))                     # thigh
    tail = [(p[0], p[1], p[2], r, r, r) for p, r in zip(TAIL, (0.065, 0.055, 0.038))]
    loft(bm, tail, up=(0, 1, 0), seg=12, cap0=0.4, cap1=0.8)


HEAD_ROWS = [  # head space: (y, z centre, half width, up radius, down radius); the underside in front of the mouth
               # corner (y ~ -0.22) is the upper lip, the lower jaw is a separate piece under it
    (0.00, -0.060, 0.170, 0.170, 0.200), (-0.10, -0.050, 0.200, 0.190, 0.220), (-0.20, -0.060, 0.190, 0.180, 0.170),
    (-0.28, -0.090, 0.150, 0.100, 0.135), (-0.40, -0.110, 0.115, 0.080, 0.115), (-0.52, -0.115, 0.095, 0.075, 0.105),
    (-0.58, -0.120, 0.085, 0.065, 0.095)]


def build_head(bm):
    # head space: the domed forehead rising steeply behind the eyes (the cave bear's mark), the long muzzle, the
    # black nose pad, jowls over the back of the jaw
    before = set(bm.verts)
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in HEAD_ROWS], up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.5,
         shape=0.85)
    ellipsoid(bm, (0, -0.16, 0.080), (0.130, 0.130, 0.080))                          # the dome of the forehead
    ellipsoid(bm, (0, -0.600, -0.070), (0.060, 0.035, 0.045))                        # nose pad
    for s in (1, -1):
        ellipsoid(bm, (s * 0.130, -0.15, -0.200), (0.080, 0.110, 0.090))             # jowl
        ellipsoid(bm, (s * 0.110, -0.26, 0.030), (0.045, 0.055, 0.028))              # brow over the eye
        ellipsoid(bm, (s * 0.125, -0.07, 0.090), (0.060, 0.050, 0.050))              # the ear's root
        for yy, k in ((-0.30, 1.0), (-0.41, 0.95), (-0.51, 0.85)):                    # lips hanging over the jaw
            ellipsoid(bm, (s * 0.072 * k, yy, -0.212), (0.036 * k, 0.065, 0.034))
    HEAD.to_body(bm, before)


FRONT_LEG = [(0.300, -0.50, 1.000, 0.170, 0.200, 0.200), (0.310, -0.46, 0.800, 0.170, 0.180, 0.190),
             (0.310, -0.42, 0.620, 0.160, 0.160, 0.170), (0.310, -0.44, 0.450, 0.145, 0.140, 0.140),
             (0.310, -0.47, 0.300, 0.130, 0.125, 0.120), (0.310, -0.50, 0.170, 0.120, 0.120, 0.110),
             (0.310, -0.55, 0.090, 0.125, 0.130, 0.100)]
HIND_LEG = [(0.280, 0.48, 0.840, 0.170, 0.210, 0.230), (0.310, 0.46, 0.640, 0.155, 0.150, 0.180),
            (0.310, 0.56, 0.460, 0.135, 0.120, 0.140), (0.300, 0.66, 0.290, 0.120, 0.110, 0.120),
            (0.300, 0.72, 0.170, 0.110, 0.110, 0.110), (0.300, 0.74, 0.090, 0.105, 0.105, 0.100)]


def leg_loft(rows, s):
    return ([(s * r[0],) + r[1:] for r in rows], (0, -1, 0), 18, 4, 0.5, 0.4)


def build_leg_front(bm, s):
    loft(bm, *leg_loft(FRONT_LEG, s))
    ellipsoid(bm, (s * 0.310, -0.31, 0.620), (0.110, 0.100, 0.110))                  # point of the elbow
    x = s * 0.310
    ellipsoid(bm, (x, -0.610, 0.060), (0.130, 0.160, 0.065), seg=18, rings=10)       # the forepaw, flat
    _toes(bm, x, -0.735, 0.048, 0.029, s)


def build_leg_hind(bm, s):
    loft(bm, *leg_loft(HIND_LEG, s))
    x = s * 0.300
    foot = [(x, 0.770, 0.070, 0.090, 0.065, 0.065), (x, 0.620, 0.065, 0.110, 0.065, 0.065),
            (x, 0.480, 0.058, 0.125, 0.058, 0.058), (x, 0.400, 0.050, 0.120, 0.048, 0.048)]
    loft(bm, foot, up=(0, 0, 1), seg=16, cap0=0.7, cap1=0.5)                         # heel to ball, flat
    _toes(bm, x, 0.355, 0.042, 0.027, s)


def _toes(bm, x, y, z, r, s):
    """Five toes in an arc across the front of a paw (the inner one smallest)."""
    for dx, dy, k in ((-0.080, 0.030, 0.80), (-0.042, 0.008, 0.95), (0.0, 0.0, 1.0), (0.042, 0.008, 0.95),
                      (0.078, 0.028, 0.90)):
        ellipsoid(bm, (x + s * dx, y + dy, z), (r * k, r * 1.2 * k, r * 0.9), seg=10, rings=6)


def toe_tips(kind, s):
    """Where the claws root (front of each toe) for a paw, left side when s = 1."""
    x = s * (0.310 if kind == 'F' else 0.300)
    y, z = (-0.735, 0.052) if kind == 'F' else (0.355, 0.047)
    out = []
    for dx, dy in ((-0.080, 0.030), (-0.042, 0.008), (0.0, 0.0), (0.042, 0.008), (0.078, 0.028)):
        out.append(np.array((x + s * dx, y + dy - 0.022, z)))
    return out


# ------------------------------------------------------------------------------------------ hair
LOCKS = [
    # elbow tufts behind the forearms
    ((0.330, -0.280, 0.620), (0.2, 0.7, -0.8), 0.17, 0.065),
    # breeches down the back of the thighs
    ((0.320, 0.760, 0.880), (0.4, 0.5, -1.0), 0.22, 0.075),
    ((0.200, 0.840, 0.840), (0.2, 0.6, -1.0), 0.20, 0.070),
    ((0.360, 0.700, 0.660), (0.4, 0.4, -1.0), 0.16, 0.060),
    # tail tuft
    ((0.000, 0.980, 0.880), (0.0, 0.3, -1.0), 0.12, 0.045),
]
FRINGE_LOOPS = [   # (volume, (centre x, centre y, half length, half width, hem z sides / front / back, open gap at
                   #  the front, deg), pitch, outward lean, long and short lengths, thickness, lift)
    (CAPE, (0.0, -0.58, 0.46, 0.52, 0.92, 0.90, 1.26, 80), 0.11, 0.20, (0.16, 0.28), (0.03, 0.06), 0.045, 0.05),
    (SKIRT, (0.0, 0.02, 0.66, 0.48, 0.58, 0.62, 0.64, 0), 0.11, 0.18, (0.12, 0.22), (0.03, 0.05), 0.040, 0.06),
]
LEG_STRIPS = [  # shaggy hair down the backs of the legs: (leg, x, z from .. z to, samples, direction, lengths)
    (FRONT_LEG, 0.310, 0.66, 0.24, 9, (0.0, 1.0, -0.55), (0.12, 0.20)),          # forearm, elbow to wrist
    (HIND_LEG, 0.300, 0.72, 0.26, 9, (0.0, 1.0, -0.70), (0.10, 0.18)),           # shin, knee to heel
]


def _leg_back(rows, z):
    """The back of a leg loft (y of its centre plus its back radius) at height z."""
    zs = np.array([r[2] for r in rows])[::-1]
    yc = np.interp(z, zs, np.array([r[1] for r in rows])[::-1])
    rc = np.interp(z, zs, np.array([r[5] for r in rows])[::-1])
    return yc + rc


def build_fringes(bm, bvh, seed=7):
    rng = np.random.default_rng(seed)
    root = bm.verts.layers.float_vector["root"]
    vs = []
    for vol, spec, step, dout, longs, shorts, thick, lift in FRINGE_LOOPS:
        A, outs, closed = loop_anchors(spec, step / 2)
        vs += fringe(bm, Snap(volume_bvh(vol)), A, closed, dout, longs, shorts, thick, lift, rng, root, outs)
    for rows, x, z0, z1, n, d, longs in LEG_STRIPS:
        for s in (1, -1):
            A = [Vector((s * x, _leg_back(rows, z) + 0.10, z)) for z in np.linspace(z0, z1, n)]
            vs += fringe(bm, Snap(loft_bvh(leg_loft(rows, s))), A, False, d, longs, (0.03, 0.05), 0.035, 0.20, rng,
                         root)
    return vs


def fur_flow(P, N):
    """Back along the top, hanging down the flanks and legs, back over the head from the muzzle."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    one = np.ones_like(x)
    top = np.stack([0 * x, one, -0.15 * one], -1)
    hang = np.stack([0 * x, 0.25 * one, -one], -1)
    face = np.broadcast_to(hx_dir((0.0, 1.0, 0.15)), P.shape)
    w_top = smoothstep(0.30, 0.80, N[..., 2])
    F = top * w_top[..., None] + hang * (1 - w_top[..., None])
    H = hx_inv(P)
    w_face = smoothstep(0.02, -0.08, H[..., 1]) * smoothstep(-0.30, -0.22, H[..., 2])
    F = F * (1 - w_face[..., None]) + face * w_face[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def fur_amount(P, N):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    A = np.full(len(P), 0.005)
    A = A + 0.016 * _gauss(P, (0, -0.45, 1.32), (0.40, 0.45, 0.26))                       # hump
    A = A * (1 - 0.5 * smoothstep(0.30, 0.15, z) * (np.abs(x) > 0.15))                    # shorter on the paws
    H = hx_inv(P)
    A = A * (1 - 0.6 * smoothstep(-0.20, -0.32, H[:, 1]))                                 # short on the muzzle
    return A


def sculpt_fur(co, no, seed=13):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed, across=0.070, along_len=0.20)


def sculpt_face(co, no):
    """Eye sockets under the brow, nostrils on the nose pad."""
    out = co.copy()
    H = hx_inv(co)
    Pm = np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1)
    out -= no * (0.012 * _gauss(Pm, EYE0_H, (0.022, 0.022, 0.018)))[:, None]              # socket
    out -= no * (0.012 * _gauss(Pm, (0.022, -0.585, -0.090), (0.012, 0.010, 0.012)))[:, None]   # nostrils
    return out


def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face and the paws keep relatively more."""
    h = hx_inv(co[:])
    face = h[1] < -0.05 and h[2] > -0.35 and abs(h[0]) < 0.22
    paw = co.z < 0.20 and abs(co.x) > 0.15
    return 1.0 - 0.40 * float(face) - 0.35 * float(paw)


def build_fur_body(voxel=0.007, target_tris=2300, fillet_iters=45):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    for s in (1, -1):
        build_leg_front(bm, s)
        build_leg_hind(bm, s)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return beast_body.fuse_body(bm, "BER", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                dec_weight=_dec_weight, seam_x=0.018, flat_z=0.007, fillet_iters=fillet_iters)


# ------------------------------------------------------------------------------------------ separate pieces
def _snap(bvh, p, n, reach=0.25):
    hit = bvh.ray_cast(Vector(p + n * reach), Vector(-n), reach * 2)[0]
    return np.array(hit) if hit is not None else np.array(p)


def _claw(bm, base, d, L, r):
    """A curved claw: a three-sided blade from `base` along d, hooking down toward its tip (10 triangles)."""
    d = Vector(d).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = d.orthogonal()
    side.normalize()
    up = side.cross(d).normalized()
    base = Vector(base)
    mid = base + d * (L * 0.5) - up * (0.08 * L)
    tip = base + d * L - up * (0.28 * L)
    rings = []
    for c, k in ((base, 1.0), (mid, 0.62)):
        rr = r * k
        rings.append([bm.verts.new(c + up * rr), bm.verts.new(c - up * rr * 0.6 + side * rr * 0.75),
                      bm.verts.new(c - up * rr * 0.6 - side * rr * 0.75)])
    apex = bm.verts.new(tip)
    for j in range(3):
        bm.faces.new((rings[0][j], rings[0][(j + 1) % 3], rings[1][(j + 1) % 3], rings[1][j]))
        bm.faces.new((rings[1][j], rings[1][(j + 1) % 3], apex))
    bm.faces.new(list(reversed(rings[0])))
    for p, q in ((rings[0][1], rings[1][1]), (rings[1][1], apex)):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    for j in range(3):
        e = bm.edges.get((rings[0][j], rings[0][(j + 1) % 3]))
        if e is not None:
            e.seam = True
    return [v for r_ in rings for v in r_] + [apex]


def build_pieces(low):
    """Jaw, tongue, teeth, eyes, ears, claws and the coat's hair: separate shells (no remesh)."""
    bml = bmesh.new()
    bml.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    bm = bmesh.new()
    bm.verts.layers.float_vector.new("root")      # before any vertex: adding a layer later orphans the BMVerts
    tags = {}
    # head space: the lower jaw (its back end in the jowls, its top edge tucked inside the lips), the tongue on it
    before = set(bm.verts)
    jaw = [(0, -0.14, -0.235, 0.110, 0.035, 0.060), (0, -0.30, -0.240, 0.090, 0.035, 0.055),
           (0, -0.45, -0.240, 0.075, 0.035, 0.050), (0, -0.56, -0.235, 0.060, 0.030, 0.040)]
    tags['jaw'] = loft(bm, jaw, up=(0, 0, 1), seg=10, per_seg=2, cap0=0.5, cap1=0.6, capk=2, shape=0.85)
    tongue = [(0, -0.20, -0.214, 0.042, 0.010, 0.010), (0, -0.40, -0.217, 0.038, 0.010, 0.010),
              (0, -0.50, -0.215, 0.026, 0.008, 0.008)]                       # narrower than the jaw: gums show
    tags['tongue'] = loft(bm, tongue, up=(0, 0, 1), seg=6, per_seg=1, cap0=0.4, cap1=0.9, capk=2)
    upper, lower = [], []
    for s in (1, -1):
        # fangs: long enough to show past the lips when it roars; shut, the lower jaw and the snout hide them
        upper += cone(bm, (s * 0.048, -0.480, -0.195), (s * 0.051, -0.488, -0.274), 0.015, seg=4, bend=(0, -0.006, 0))
        lower += cone(bm, (s * 0.040, -0.500, -0.222), (s * 0.044, -0.505, -0.162), 0.013, seg=4, bend=(0, -0.004, 0))
        for k in range(2):                                                         # incisors
            xx = s * (0.012 + 0.013 * k)
            upper += cone(bm, (xx, -0.565, -0.200), (xx, -0.568, -0.228), 0.006, seg=3)
            xx = s * (0.010 + 0.011 * k)
            lower += cone(bm, (xx, -0.548, -0.218), (xx, -0.552, -0.194), 0.0055, seg=3)
    tags['tooth'] = upper
    tags['tooth_low'] = lower
    HEAD.to_body(bm, before)
    eyes = []
    for s in (1, -1):
        n = EYE_N * np.array((s, 1, 1))
        c = _snap(bvh, EYE0 * np.array((s, 1, 1)), n, 0.06) - n * 0.003
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        eyes += dome(bm, c, n, EYE_R, 0.009, seg=10, rings=3)
    tags['eye'] = eyes
    ears = []
    for s in (1, -1):
        base, tip = ear_rows(s)
        ears += cup_ear(bm, base, tip, hx_dir((0.45 * s, -1.0, 0.1)), EAR_PROFILE)
    tags['ear'] = ears
    claws = []
    for kind, L, r in (('F', 0.120, 0.017), ('H', 0.070, 0.014)):
        for s in (1, -1):
            for p in toe_tips(kind, s):
                d = np.array((0.08 * s * np.sign(p[0] - s * (0.310 if kind == 'F' else 0.300)), -1.0, -0.22))
                claws += _claw(bm, p, d, L, r)
    tags['claw'] = claws
    tags['hair'] = build_clumps(bm, bvh, LOCKS) + build_fringes(bm, bvh)
    return bm, tags


def build_body(voxel=0.007, target_tris=2300):
    """-> (BearBody (fur body joined with the pieces, info attribute set), BER_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    nfur = len(fur.data.vertices)
    co = np.array([v.co[:] for v in fur.data.vertices])
    H = hx_inv(co)
    nose = np.linalg.norm((np.abs(H) - (0, 0.600, 0.070)) / (0.068, 0.045, 0.055), axis=1) < 1.0
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "BER", "BearBody")
    part_fur = np.where(nose, PART['nose'], PART['fur'])
    _write_info(body.data, np.concatenate([part_fur, part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    write_hair_t(body, PART['hair'], reach=0.30)
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
    +Z toward the front, Motion carries the root motion; legs and spine bend about their local X)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.4, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.3, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    head_up = tuple(hx_dir((0, 0, 1)))
    _bone(B, "Hips", (0, 0.58, 1.020), (0, 0.86, 0.980), UP, "Root")
    _bone(B, "Spine1", (0, 0.58, 1.040), (0, 0.18, 1.080), UP, "Hips")
    _bone(B, "Spine2", (0, 0.18, 1.080), (0, -0.22, 1.120), UP, "Spine1")
    _bone(B, "Chest", (0, -0.22, 1.120), (0, -0.66, 1.100), UP, "Spine2")
    head0, head1 = hx((0, 0.02, -0.08)), hx((0, -0.55, -0.08))
    _bone(B, "Neck1", (0, -0.66, 1.100), (0, -0.84, 1.110), UP, "Chest")
    _bone(B, "Neck2", (0, -0.84, 1.110), tuple(head0), UP, "Neck1")
    _bone(B, "Head", tuple(head0), tuple(head1), head_up, "Neck2")
    _bone(B, "Jaw", HINGE, tuple(hx((0, -0.55, -0.250))), head_up, "Head")
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
        _bone(B, f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), UP, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
    # sockets (head = attach point; +Y up, +Z forward)
    top = hx((0, -0.16, 0.16))
    _bone(B, "Socket_Head", tuple(top), tuple(top + np.array((0, 0, 0.1))), FWD, "Head")
    mouth = hx((0, -0.45, -0.23))
    _bone(B, "Socket_Mouth", tuple(mouth), tuple(mouth + np.array((0, 0, 0.1))), FWD, "Jaw")
    _bone(B, "Socket_Back", (0, -0.30, 1.500), (0, -0.30, 1.600), FWD, "Chest")
    for s, sfx in ((1, "L"), (-1, "R")):                                  # the forepaws (swipe effects)
        p = np.array(J['FTOE']) * np.array((s, 1, 1))
        _bone(B, f"Socket_Paw{sfx}", tuple(p), tuple(p + np.array((0, 0, 0.1))), FWD, f"FrontToes{sfx}")
    return B
