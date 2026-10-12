"""Red deer stag: procedural body, built standing (the bind pose), facing -Y, left side +X (2026-10-11).

Cervus elaphus, a mature stag in autumn, prey for the hunting grounds (hide and venison): 1.20 m at the withers,
about 2.0 m nose to rump, a deep chest, a slim waist and a rounded rump, long slender legs on cloven hooves (two
claws, small dewclaws behind the fetlock), a long thick neck carried up and forward with a shaggy rut mane under the
throat, a long narrow head with the muzzle tapering to a dark nose pad, big upright oval ears, large eyes, a short tail
over a pale rump patch, and branching antlers (each side a brow, bez and trez tine and a crown of three tips) about
0.9 m across.

build_body() -> DeerBody, one mesh:
  - the furred body: trunk, neck, head, shoulders, haunches, the legs' stumps (to mid forearm and mid gaskin) and
    tail fused by beast_body.fuse_body, the mane the neck's full throat side with a strong fur sculpt (the texture
    carries the rest); the lower legs are clean lofted tubes stitched onto the stumps (fused and decimated, legs this
    thin twist into diagonal facets, see the mammoth's trunk), one surface with the body (body["leg_verts"]);
  - separate pieces: the hooves' claws and dewclaws,
    the lower jaw (on the Jaw bone), the eyes, the ears (cupped shells on Ear{L,R}) and the antlers (clean lofted
    tubes, rigid on Head; the tines grow out of the beam with flared roots).
The head is built in its own frame (beast_body.HeadFrame), hung 42 degrees down from the poll.
rest_bones() is the skeleton (Unity Generic rig: the wolf's bone names with 3 neck bones, 2 tail bones, no tongue).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, spline, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, _mx, HeadFrame, cup_ear

# ------------------------------------------------------------------------------------------ landmarks (metres)
# Left-side joints; the right side mirrors x. Unguligrade: the "paws" are the fetlocks, the "toes" the hooves.
J = dict(
    SCAP=(0.090, -0.36, 1.130),     # top of the shoulder blade, under the withers
    SHO=(0.150, -0.56, 0.860),      # point of the shoulder
    ELB=(0.150, -0.40, 0.680),      # elbow (behind, at the bottom of the chest)
    WRI=(0.143, -0.445, 0.380),     # knee (carpus)
    FPAW=(0.138, -0.450, 0.130),    # fetlock
    FTOE=(0.135, -0.525, 0.008),    # hoof tip
    HIP=(0.120, 0.44, 0.980),
    KNEE=(0.145, 0.36, 0.730),      # stifle (forward, in the flank)
    HOCK=(0.132, 0.505, 0.455),     # hock (behind)
    HPAW=(0.127, 0.494, 0.130),     # fetlock
    HTOE=(0.125, 0.420, 0.008),
)
TAIL = [(0, 0.690, 1.040), (0, 0.790, 0.975), (0, 0.820, 0.860)]     # standing a little off the rump

HEAD = HeadFrame((0.0, -0.93, 1.47), 42.0)     # the poll; the head hangs 42 degrees down from it
hx, hx_inv, hx_dir = HEAD.hx, HEAD.hx_inv, HEAD.hx_dir
HINGE_H = (0.0, -0.08, -0.115)                  # jaw hinge (head space), hidden in the jowl
HINGE = tuple(hx(HINGE_H))
EYE0_H = np.array((0.082, -0.140, -0.010))      # eye (left, head space), where the face meets the cranium
EYE0 = hx(EYE0_H)
EYE_N = hx_dir(np.array((0.76, -0.50, 0.30)) / np.linalg.norm((0.76, -0.50, 0.30)))
EYE_R = 0.026                                   # stylised: ~1.5x a red deer's, so the eyes read in game
EYE_LONG, EYE_SHORT = 1.15, 0.86                # almond: long from the front corner to the back corner
NOSE_C, NOSE_R = (0.0, -0.432, -0.083), (0.046, 0.020, 0.042)      # the nose pad (head space): broad
# ears: big upright ovals behind the antlers, held up and out (cupped shells on Ear{L,R})
EAR_BASE_H = (0.064, -0.005, 0.042)
EAR_DIR = np.array((0.72, 0.22, 0.66)) / np.linalg.norm((0.72, 0.22, 0.66))     # body space
EAR_LEN = 0.19
EAR_PROFILE = ((0.0, 0.038, 0.026), (0.30, 0.056, 0.034), (0.62, 0.052, 0.030), (0.88, 0.030, 0.018))
EAR_FRONT = (0.20, -1.0, 0.10)                  # where the hollow faces (x mirrored): forward, open from the front
LM = {}


def ear_rows(s):
    base = hx(np.array(EAR_BASE_H) * np.array((s, 1, 1)))
    return base, base + EAR_DIR * np.array((s, 1, 1)) * EAR_LEN


def eye_axes(n):
    """The eye's long axis (front corner, low -> back corner, high) and its short axis, in the eye's plane."""
    t = hx_dir(np.array((0.0, 1.0, 0.30)))
    t = t - n * (t @ n)
    t /= np.linalg.norm(t)
    return t, np.cross(n, t)


# ------------------------------------------------------------------------------------------ parts
TRUNK_ROWS = [  # y, z centre, half width, up radius, down radius: a deep chest, the withers highest, a slim waist
                # behind the ribs, a rounded rump
    (-0.62, 0.95, 0.120, 0.150, 0.190),
    (-0.50, 0.96, 0.185, 0.230, 0.305),
    (-0.32, 0.95, 0.215, 0.235, 0.320),
    (-0.10, 0.94, 0.225, 0.210, 0.290),
    (0.10, 0.94, 0.210, 0.195, 0.230),
    (0.26, 0.95, 0.185, 0.190, 0.190),
    (0.42, 0.96, 0.190, 0.185, 0.195),
    (0.57, 0.95, 0.165, 0.170, 0.180),
    (0.68, 0.93, 0.100, 0.125, 0.135),
]
# the neck: long and thick (the rut), carried up and forward into the back of the skull: (x, y, z, half width,
# crest radius, throat radius). Its rings stay perpendicular to the rising centre line.
NECK = [(0, -0.42, 0.98, 0.165, 0.180, 0.240), (0, -0.57, 1.08, 0.150, 0.150, 0.250),
        (0, -0.70, 1.21, 0.128, 0.120, 0.215), (0, -0.80, 1.32, 0.104, 0.095, 0.170),
        (0, -0.88, 1.42, 0.084, 0.075, 0.110)]                     # the throat side deep and full: the mane's mass
NECK_UP = (0, 0, 1)


def neck_loft():
    return NECK, NECK_UP, 24, 4, 0.5, 0.5


def build_trunk(bm):
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in TRUNK_ROWS], up=(0, 0, 1), seg=28, cap0=0.6, cap1=0.6)
    loft(bm, *neck_loft())
    ellipsoid(bm, (0, -0.40, 1.13), (0.075, 0.20, 0.075))                            # the withers
    ellipsoid(bm, (0, -0.56, 0.80), (0.110, 0.10, 0.14))                             # the brisket
    for s in (1, -1):
        ellipsoid(bm, (s * 0.150, -0.47, 0.90), (0.070, 0.150, 0.230),
                  rot=Matrix.Rotation(math.radians(-36), 3, 'X'))                     # shoulder blade
        ellipsoid(bm, (s * 0.150, -0.45, 0.76), (0.065, 0.110, 0.110))               # upper arm, to the elbow
        ellipsoid(bm, (s * 0.135, 0.46, 0.86), (0.080, 0.190, 0.240))                # the haunch
        ellipsoid(bm, (s * 0.148, 0.30, 0.81), (0.050, 0.070, 0.070))                # flank fold to the stifle
        for rows in (FRONT_STUMP, HIND_STUMP):                                        # the legs' fused stumps
            loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.7)
    tail =[(p[0], p[1], p[2], a, b, c) for p, (a, b, c) in
            zip(TAIL, ((0.046, 0.030, 0.028), (0.042, 0.028, 0.026), (0.030, 0.020, 0.018)))]   # short, flat, hanging
    loft(bm, tail, up=(0, 1, 0), seg=12, cap0=0.4, cap1=0.8)


HEAD_ROWS = [  # head space: (y, z centre, half width, up radius, down radius); a wedge, broad and deep at the
               # cranium, the muzzle blunt and deep (a deer's, not a dog's); its underside is the upper lip, over the
               # separate lower jaw
    (0.03, -0.050, 0.068, 0.064, 0.090), (-0.05, -0.045, 0.086, 0.085, 0.105), (-0.13, -0.050, 0.080, 0.075, 0.098),
    (-0.22, -0.062, 0.066, 0.058, 0.080), (-0.31, -0.074, 0.056, 0.048, 0.070), (-0.38, -0.082, 0.052, 0.045, 0.066),
    (-0.42, -0.085, 0.049, 0.044, 0.062)]
PEDICLE_H = (0.048, -0.070, 0.080)              # where the antlers grow (left, head space)


def build_head(bm):
    before = set(bm.verts)
    loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in HEAD_ROWS], up=(0, 0, 1), seg=24, cap0=0.5, cap1=0.4,
         shape=0.9)
    ellipsoid(bm, (0, -0.05, 0.010), (0.075, 0.090, 0.070))                          # the cranium
    ellipsoid(bm, NOSE_C, NOSE_R)                                                    # nose pad
    ellipsoid(bm, (0, -0.03, -0.125), (0.052, 0.075, 0.062))                         # throat latch: hides the jaw's end
    for s in (1, -1):
        ellipsoid(bm, (s * 0.048, -0.070, 0.062), (0.028, 0.028, 0.030))             # pedicle
        ellipsoid(bm, (s * 0.064, -0.122, 0.014), (0.020, 0.034, 0.013))             # brow over the eye
        ellipsoid(bm, (s * 0.054, -0.110, -0.105), (0.042, 0.080, 0.062))            # cheek, over the jaw's back
        ellipsoid(bm, (s * 0.046, -0.200, -0.128), (0.036, 0.075, 0.040))            # ... to the mouth's corner
        ellipsoid(bm, (s * 0.024, -0.392, -0.136), (0.030, 0.045, 0.022))            # deep upper lip over the jaw
    HEAD.to_body(bm, before)


# Each leg is one surface in two parts. The stump is fused into the body, so the elbow and stifle bend in fused,
# heat-weighted skin: the upper arm to mid forearm, the stifle to mid gaskin. Below SEAM the fused stump is cut off
# and a clean lofted lower leg (fused and decimated, legs this thin twist into diagonal facets) is stitched onto its
# rim (_graft_legs): there is no crossing to show. A separate tube coming out of the body, then out of the stump's
# end, both left a ragged line where the two surfaces crossed. Rows: (x, y, z, side radius, front, back radius).
FRONT_STUMP = [(0.150, -0.42, 0.80, 0.057, 0.064, 0.064), (0.150, -0.41, 0.70, 0.055, 0.062, 0.066),
               (0.147, -0.43, 0.60, 0.046, 0.054, 0.048), (0.146, -0.434, 0.52, 0.041, 0.048, 0.042)]
HIND_STUMP = [(0.138, 0.38, 0.86, 0.062, 0.074, 0.082), (0.145, 0.36, 0.74, 0.060, 0.072, 0.088),
              (0.140, 0.41, 0.64, 0.048, 0.055, 0.077), (0.137, 0.44, 0.565, 0.043, 0.049, 0.066)]
# the lower legs, from just under the seam: thin cannons, bony knees and hocks, the fetlock a knob, the pastern
# sloping forward, the coronet inside the hoof
FRONT_LEG = [(0.145, -0.435, 0.525, 0.039, 0.045, 0.040), (0.144, -0.44, 0.44, 0.031, 0.036, 0.031),
             (0.143, -0.445, 0.375, 0.033, 0.037, 0.032), (0.141, -0.447, 0.270, 0.022, 0.024, 0.023),
             (0.138, -0.450, 0.130, 0.026, 0.028, 0.032), (0.136, -0.475, 0.075, 0.022, 0.024, 0.023),
             (0.135, -0.492, 0.048, 0.026, 0.030, 0.026)]
HIND_LEG = [(0.136, 0.45, 0.570, 0.039, 0.044, 0.058), (0.134, 0.475, 0.515, 0.030, 0.034, 0.042),
            (0.132, 0.505, 0.455, 0.029, 0.031, 0.040), (0.130, 0.500, 0.350, 0.022, 0.024, 0.024),
            (0.127, 0.494, 0.130, 0.026, 0.028, 0.032), (0.126, 0.472, 0.075, 0.022, 0.024, 0.023),
            (0.125, 0.455, 0.048, 0.026, 0.030, 0.026)]
SEAM = {'F': 0.565, 'H': 0.610}                 # where each stump is cut and its lower leg stitched on
FOOT = {'F': (0.135, -0.492), 'H': (0.125, 0.455)}       # the coronet's centre x, y


def leg_loft(rows, s):
    """loft() arguments for a lower leg (open at the top once its pole is removed, see _graft_legs)."""
    return ([(s * r[0],) + r[1:] for r in rows], (0, -1, 0), 8, 2, 0.0, 0.3, 2, 1.0, 0.0 if s > 0 else math.pi)


RIM_K = 1.10                                    # the stump's cut rim: the lower leg's first ring, this much wider


def _ellipse(c, rows, theta, k=RIM_K):
    """A point on the stump's rim (centre c; the lower leg's first ring's side / front / back radii, k wider) at
    angle theta."""
    a, b, cb = (r * k for r in rows[0][3:6])
    dx, dy = math.cos(theta), math.sin(theta)
    rf = b if dy < 0 else cb                        # -y is the front
    r = 1.0 / math.hypot(dx / a, dy / rf)
    return Vector((c.x + dx * r, c.y + dy * r, c.z))


def _zip(bm, A, B, c):
    """Stitch two loops round the axis through c (A the stump's rim, B the tube's top ring) with a strip of
    triangles, walking both by angle."""
    ang = lambda v: math.atan2(v.co.y - c.y, v.co.x - c.x)
    A = sorted(A, key=ang)
    base = ang(A[0])
    rel = lambda v: (ang(v) - base) % (2 * math.pi)
    B = sorted(B, key=rel)
    tA = [rel(v) for v in A] + [2 * math.pi]
    tB = [rel(v) for v in B]
    tB.append(tB[0] + 2 * math.pi)
    i = j = 0
    faces = []
    while i < len(A) or j < len(B):
        if j >= len(B) or (i < len(A) and tA[i + 1] <= tB[j + 1]):
            faces.append(bm.faces.new((A[i % len(A)], A[(i + 1) % len(A)], B[j % len(B)])))
            i += 1
        else:
            faces.append(bm.faces.new((A[i % len(A)], B[(j + 1) % len(B)], B[j % len(B)])))
            j += 1
    return faces


def _graft_legs(ob):
    """Cut each fused stump off at SEAM (its faces reaching below it, near the leg) and stitch its lower leg's clean
    tube onto the rim, the rim moved onto the tube's first ring shape at SEAM: one surface. -> the new vertices'
    indices."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    legs = []
    for kind, rows in (('F', FRONT_LEG), ('H', HIND_LEG)):
        zc = SEAM[kind]
        for s in (1, -1):
            c = Vector((s * rows[0][0], rows[0][1], zc))
            near = lambda p: math.hypot(p.x - c.x, p.y - c.y) < 0.11 and p.z < zc + 0.08
            dead = [f for f in bm.faces if any(v.co.z < zc for v in f.verts) and near(f.calc_center_median())]
            bmesh.ops.delete(bm, geom=dead, context='FACES')
            rim = {v for e in bm.edges if e.is_boundary for v in e.verts if near(v.co)}
            for v in rim:                                     # the rim onto the tube's first ring, a little above it
                v.co = _ellipse(c, rows, math.atan2(v.co.y - c.y, v.co.x - c.x))
            vs = loft(bm, *leg_loft(rows, s))
            pole = vs[-2]
            top = vs[:8]
            bmesh.ops.delete(bm, geom=[pole], context='VERTS')
            _zip(bm, list(rim), top, c)
            tube = set(vs) - {pole}
            legs += list(tube)
            # the stump's last triangles, squeezed onto the rim, are slivers (dark dashes in the bake): flip them to
            # better shapes and relax the rim zone into the tube
            zone = lambda p: near(p) and zc - 0.06 < p.z < zc + 0.08
            tris = [f for f in bm.faces if len(f.verts) == 3 and all(zone(v.co) for v in f.verts)]
            bmesh.ops.beautify_fill(bm, faces=tris, edges=list({e for f in tris for e in f.edges}))
            relax = [v for v in bm.verts if v not in tube and zone(v.co)]
            for _ in range(4):
                bmesh.ops.smooth_vert(bm, verts=relax, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    idx = [v.index for v in legs]
    bm.to_mesh(ob.data)
    bm.free()
    return np.array(idx)


def leg_centre(rows, z):
    """The leg tube's centre x (left side) and y at height z."""
    zs = np.array([r[2] for r in rows])[::-1]
    return (np.interp(z, zs, np.array([r[0] for r in rows])[::-1]),
            np.interp(z, zs, np.array([r[1] for r in rows])[::-1]))


def hoof_claws(kind, s):
    """The two claws of a cloven hoof (left side when s = 1): loft rows from the heel to the pointed tip, the tips
    pinched in toward the cleft, the soles flat on the ground."""
    x0, y0 = FOOT[kind]
    out = []
    for k in (1, -1):
        x, xi = s * (x0 + k * 0.0135), s * (x0 + k * 0.0080)
        out.append([(x, y0 + 0.020, 0.024, 0.012, 0.022, 0.024), (x, y0 - 0.010, 0.022, 0.0135, 0.024, 0.022),
                    (xi, y0 - 0.044, 0.007, 0.0065, 0.007, 0.007)])
    return out


def dewclaws(kind, s):
    """(base, tip) of the two dewclaws behind a fetlock."""
    fet = next(r for r in (FRONT_LEG if kind == 'F' else HIND_LEG) if abs(r[2] - 0.130) < 1e-6)
    fx, fy, fz = fet[:3]
    back = fy + fet[5]
    return [((s * (fx + k * 0.015), back - 0.006, 0.112), (s * (fx + k * 0.017), back + 0.018, 0.084)) for k in (1, -1)]


# ------------------------------------------------------------------------------------------ antlers
# Clean lofted tubes, rigid on Head (thin tubes through the voxel fuse twist into diagonal facets). Offsets from the
# pedicle in body axes (x out, +y back, z up), radius. The beam rises up, back and out and carries on into the
# crown's outer tip; the tines branch off its centre line.
BEAM = [(0.000, 0.000, -0.020, 0.027), (0.014, 0.012, 0.030, 0.034), (0.100, 0.080, 0.160, 0.025),
        (0.240, 0.200, 0.360, 0.021), (0.330, 0.280, 0.550, 0.018), (0.370, 0.280, 0.680, 0.015),
        (0.400, 0.230, 0.870, 0.006)]          # a lyre from the front: out, then up, the crown cupped
BEAM_PER_SEG = 2
TINES = [  # (name, height up the beam where it branches, mid and tip offsets, base and mid radius); they leave the
           # beam forward and up at ~30-45 degrees and curve upward (not out at right angles)
    ('brow', 0.050, (0.042, -0.110, 0.110), (0.068, -0.185, 0.245), 0.019, 0.014),     # forward over the face,
    ('bez', 0.110, (0.072, -0.068, 0.180), (0.098, -0.125, 0.290), 0.016, 0.012),      # just above it,
    ('trez', 0.360, (0.252, 0.115, 0.445), (0.242, 0.050, 0.565), 0.015, 0.011),       # mid beam,
    ('crownA', 0.640, (0.330, 0.215, 0.770), (0.290, 0.150, 0.880), 0.014, 0.010),     # the crown: forward,
    ('crownC', 0.660, (0.395, 0.335, 0.770), (0.415, 0.385, 0.870), 0.014, 0.010),     # back (and the beam's tip)
]


def pedicle(s):
    return hx(np.array(PEDICLE_H) * np.array((s, 1, 1)))


def antler_tubes(s):
    """The left (s = 1) or right antler: [(name, rows (x, y, z, r))] in body space, the beam first."""
    p = pedicle(s)
    m = np.array((s, 1, 1))
    beam = [tuple(p + np.array(r[:3]) * m) + (r[3],) for r in BEAM]
    S = spline(BEAM, BEAM_PER_SEG)
    out = [('beam', beam)]
    for name, h, mid, tip, r0, r1 in TINES:
        base = np.array([np.interp(h, S[:, 2], S[:, k]) for k in range(3)])    # on the beam's centre line, as lofted
        rb = float(np.interp(h, S[:, 2], S[:, 3]))                              # the beam's radius there
        C = spline([tuple(base) + (r0,), tuple(mid) + (r1,), tuple(tip) + (0.004,)], 8)
        cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C[:, :3], axis=0), axis=1))])
        at = lambda a: np.array([np.interp(a, cum, C[:, k]) for k in range(4)])
        # five rings: the root inside the beam; a flared ring just inside the beam's surface (the flat root's bent
        # normals stay hidden) and one just outside, narrowing, so the tine grows out of the beam with a soft root;
        # one where it curves up; the tip
        rows = [at(0.0), at(0.85 * rb), at(rb + 0.016), at(0.55 * cum[-1]), at(cum[-1])]
        rows[1][3], rows[2][3] = r0 * 1.60, r0 * 1.18
        out.append((name, [tuple(p + r[:3] * m) + (float(r[3]),) for r in rows]))
    return out


def _tube_up(rows):
    d = np.array(rows[-1][:3]) - np.array(rows[0][:3])
    d /= np.linalg.norm(d)
    return (0, 0, 1) if abs(d[2]) < 0.7 else (0, -1, 0)


def build_antlers(bm):
    vs = []
    for s in (1, -1):
        for name, rows in antler_tubes(s):
            R = [r[:3] + (r[3], r[3], r[3]) for r in rows]
            if name == 'beam':
                vs += loft(bm, R, up=_tube_up(rows), seg=8, per_seg=BEAM_PER_SEG, cap0=0.0, cap1=0.5, capk=2)
            else:                                  # its root inside the beam
                vs += loft(bm, R, up=_tube_up(rows), seg=8, per_seg=1, cap0=0.0, cap1=0.6, capk=1)
    return vs


# ------------------------------------------------------------------------------------------ fur
# The rut mane is the body itself: the neck's full throat side and a strong fur sculpt there (shaggy locks along the
# flow), the texture carrying the rest. Fused cone tufts decimated into shards here, and fringe strips read as a
# spiky collar with a dark gap down the chest.
def throat_line(k=1.0, n=40):
    """Points down the underside of the neck (the neck loft's throat side at k of its radius), from the jaw to the
    brisket."""
    rows = spline(NECK, 3)
    P = rows[:, :3]
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    U = np.array(NECK_UP, float)
    out = []
    for i in range(len(P)):
        N = U - (U @ T[i]) * T[i]
        N /= np.linalg.norm(N)
        out.append(P[i] - N * rows[i, 5] * k)
    out = np.array(out)[::-1]
    seg = np.linalg.norm(np.diff(out, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    u = np.linspace(0, cum[-1], n)
    return np.stack([np.interp(u, cum, out[:, j]) for j in range(3)], -1)


THROAT = throat_line()


def mane_mask(P):
    """1 on the mane: under the throat and down the neck's underside to the brisket, fading up the neck's sides."""
    Q = THROAT[(THROAT[:, 1] > -0.97) & (THROAT[:, 1] < -0.62)]
    d = np.full(len(P), 1e9)
    for a, b in zip(Q[:-1], Q[1:]):
        ab = b - a
        u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.linalg.norm(P - (a + np.outer(u, ab)), axis=1))
    return np.exp(-0.5 * (d / 0.090) ** 2)


def fur_flow(P, N):
    """Back along the top, down the flanks, the neck and the legs, back over the head from the nose."""
    x = P[..., 0]
    one = np.ones_like(x)
    top = np.stack([0 * x, one, -0.30 * one], -1)
    hang = np.stack([0 * x, 0.30 * one, -one], -1)
    w_top = smoothstep(0.30, 0.80, N[..., 2])
    F = top * w_top[..., None] + hang * (1 - w_top[..., None])
    H = hx_inv(P)
    face = np.broadcast_to(hx_dir((0.0, 1.0, 0.10)), P.shape)
    w_face = (smoothstep(0.08, -0.02, H[..., 1]) * smoothstep(-0.62, -0.55, H[..., 1]) *
              smoothstep(-0.26, -0.18, H[..., 2]) * smoothstep(0.20, 0.12, H[..., 2]) * smoothstep(0.20, 0.14, np.abs(x)))
    F = F * (1 - w_face[..., None]) + face * w_face[..., None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def face_mask(P):
    """1 on the face (head space, bounded on every side)."""
    H = hx_inv(P)
    return (smoothstep(0.02, -0.06, H[..., 1]) * smoothstep(-0.62, -0.55, H[..., 1]) *
            smoothstep(-0.26, -0.20, H[..., 2]) * smoothstep(0.20, 0.14, H[..., 2]) *
            smoothstep(0.16, 0.12, np.abs(P[..., 0])))


def fur_amount(P, N):
    """A short sleek coat; long shaggy hair in the mane, a little at the brisket, short on the face."""
    A = np.full(len(P), 0.0025)
    A = A + 0.045 * mane_mask(P)
    A = A + 0.005 * _gauss(P, (0, -0.60, 0.80), (0.08, 0.06, 0.08))                       # brisket
    A = A * (1 - 0.75 * face_mask(P))
    return A


def sculpt_fur(co, no, seed=23):
    return beast_body.sculpt_fur(co, no, fur_flow, fur_amount, seed=seed, across=0.045, along_len=0.13)


def sculpt_face(co, no):
    """Eye sockets under the brow, the preorbital gland's pit in front of the eye, nostrils."""
    out = co.copy()
    H = hx_inv(co)
    Pm = np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1)
    out -= no * (0.010 * _gauss(Pm, EYE0_H, (0.024, 0.024, 0.018)))[:, None]             # socket
    out -= no * (0.006 * _gauss(Pm, (0.062, -0.188, -0.034), (0.008, 0.020, 0.008)))[:, None]   # preorbital pit
    out -= no * (0.009 * _gauss(Pm, (0.026, -0.446, -0.090), (0.009, 0.008, 0.011)))[:, None]   # nostrils
    return out


def _dec_weight(co):
    """0 = keep, 1 = decimate freely: the face, the tail, the mane (its locks) and the legs' stumps (thin, they
    would twist) keep relatively more."""
    h = hx_inv(np.array(co[:]))
    face = h[1] < 0.06 and abs(h[0]) < 0.14 and -0.24 < h[2] < 0.16
    tail = co.y > 0.64 and co.z > 0.80 and abs(co.x) < 0.08
    mane = -0.99 < co.y < -0.60 and abs(co.x) < 0.15 and co.z < 1.10 + (-0.60 - co.y) * 1.05
    ax = abs(co.x)
    legs = ((math.hypot(ax - 0.148, co.y + 0.425) < 0.12 and 0.46 < co.z < 0.86) or
            (math.hypot(ax - 0.140, co.y - 0.400) < 0.14 and 0.50 < co.z < 0.88))
    return 1.0 - 0.45 * float(face) - 0.20 * float(tail) - 0.30 * float(mane) - 0.35 * float(legs)


def build_fur_body(voxel=0.006, target_tris=2600, fillet_iters=60):
    bm = bmesh.new()
    build_trunk(bm)
    build_head(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    body, hi = beast_body.fuse_body(bm, "DER", voxel, target_tris, sculpts=(sculpt_face, sculpt_fur),
                                    dec_weight=_dec_weight, seam_x=0.015, flat_z=-1.0, fillet_iters=fillet_iters)
    _relax_creases(body)
    return body, hi


def _relax_creases(ob, deg=55, passes=4):
    """Decimation leaves a few sharp creases on smooth skin (a slit down the back, folds at the brisket): move the
    vertices of edges sharper than `deg` toward their neighbours' mean. The face keeps its sculpted sockets."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(deg)
    for _ in range(passes):
        bm.normal_update()
        vs = set()
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > lim:
                vs.update(v for v in e.verts if face_mask(np.array([v.co[:]]))[0] < 0.5)
        if not vs:
            break
        for v in vs:
            ring = [e.other_vert(v).co for e in v.link_edges]
            v.co = v.co * 0.4 + sum(ring, Vector()) / len(ring) * 0.6
    bm.to_mesh(ob.data)
    bm.free()


# ------------------------------------------------------------------------------------------ separate pieces
def _snap(bvh, p, n, reach=0.25):
    hit = bvh.ray_cast(Vector(p + n * reach), Vector(-n), reach * 2)[0]
    return np.array(hit) if hit is not None else np.array(p)


JAW_H = [(0, -0.10, -0.150, 0.044, 0.032, 0.040), (0, -0.21, -0.152, 0.046, 0.030, 0.032),
         (0, -0.31, -0.154, 0.044, 0.028, 0.028), (0, -0.39, -0.154, 0.038, 0.024, 0.022)]   # head space: the bottom
                                                # line of the wedge, its top inside the muzzle, its back in the cheeks


def build_pieces(low):
    """Lower jaw, eyes, ears, hooves and antlers: separate shells (no remesh)."""
    bml = bmesh.new()
    bml.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    bm = bmesh.new()
    tags = {}
    before = set(bm.verts)
    tags['jaw'] = loft(bm, JAW_H, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.5, cap1=0.6, capk=2, shape=0.85)
    HEAD.to_body(bm, before)
    eyes = []
    for s in (1, -1):
        n = EYE_N * np.array((s, 1, 1))
        c = _snap(bvh, EYE0 * np.array((s, 1, 1)), n, 0.06) - n * 0.003
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        vs = dome(bm, c, n, EYE_R, 0.012, seg=12, rings=3)
        t, b = (Vector(v) for v in eye_axes(n))
        nv, cv = Vector(n), Vector(c)
        for v in vs:
            d = v.co - cv
            v.co = cv + t * (d.dot(t) * EYE_LONG) + b * (d.dot(b) * EYE_SHORT) + nv * d.dot(nv)
        eyes += vs
    tags['eye'] = eyes
    ears = []
    for s in (1, -1):
        base, tip = ear_rows(s)
        ears += cup_ear(bm, base, tip, (s * EAR_FRONT[0], EAR_FRONT[1], EAR_FRONT[2]), EAR_PROFILE, hollow=0.55)
    tags['ear'] = ears
    claws = []
    for s in (1, -1):
        for kind in ('F', 'H'):
            for R in hoof_claws(kind, s):
                claws += loft(bm, R, up=(0, 0, 1), seg=6, per_seg=1, cap0=0.5, cap1=0.5, capk=1, shape=0.8)
            for base, tip in dewclaws(kind, s):
                claws += cone(bm, base, tip, 0.008, seg=4)
    tags['claw'] = claws
    tags['antler'] = build_antlers(bm)
    return bm, tags


def tri_report(ob):
    """Triangles per part (beast_body.tri_report), the grafted lower legs counted apart from the fur."""
    out = beast_body.tri_report(ob)
    legs = set(ob.get("leg_verts", []))
    k = sum(len(p.vertices) - 2 for p in ob.data.polygons if all(v in legs for v in p.vertices))
    out['fur'] -= k
    out['leg'] = k
    return out


def build_body(voxel=0.006, target_tris=2600):
    """-> (DeerBody (fur body joined with the pieces, info attribute set), DER_BodyHi)."""
    fur, hi = build_fur_body(voxel, target_tris)
    legs = _graft_legs(fur)
    nfur = len(fur.data.vertices)
    co = np.array([v.co[:] for v in fur.data.vertices])
    H = hx_inv(co)
    nose = np.linalg.norm((np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1) - NOSE_C) / (np.array(NOSE_R) * 1.25),
                          axis=1) < 1.0
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, "DER", "DeerBody")
    part_fur = np.where(nose, PART['nose'], PART['fur'])
    body["leg_verts"] = [int(i) for i in legs]   # the grafted lower legs keep the fur's part id: the baked id is
                                                 # interpolated across faces, and the stitch between 1 and 17 came
                                                 # out as dashes of nose, eye and claw colours
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
    head, tail = Vector(head), Vector(tail)
    h, fr = _frame(head, tail - head, zhint)
    B[name] = (h, fr, (tail - head).length, parent, deform)


def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform); the wolf's conventions (Root and Motion point up with
    +Z toward the front, Motion carries the root motion; legs and spine bend about their local X). Three neck bones
    (beast_anim.Species(neck_n=3)): the neck is long and must bend for grazing and the roar."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.4, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.3, None, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    head_up = tuple(hx_dir((0, 0, 1)))
    _bone(B, "Hips", (0, 0.44, 1.000), (0, 0.70, 0.975), UP, "Root")
    _bone(B, "Spine1", (0, 0.44, 1.020), (0, 0.14, 1.050), UP, "Hips")
    _bone(B, "Spine2", (0, 0.14, 1.050), (0, -0.20, 1.070), UP, "Spine1")
    _bone(B, "Chest", (0, -0.20, 1.070), (0, -0.52, 1.050), UP, "Spine2")
    head0, head1 = hx((0, 0.0, -0.05)), hx((0, -0.43, -0.05))
    _bone(B, "Neck1", (0, -0.52, 1.050), (0, -0.66, 1.180), UP, "Chest")
    _bone(B, "Neck2", (0, -0.66, 1.180), (0, -0.78, 1.310), UP, "Neck1")
    _bone(B, "Neck3", (0, -0.78, 1.310), tuple(head0), UP, "Neck2")
    _bone(B, "Head", tuple(head0), tuple(head1), head_up, "Neck3")
    _bone(B, "Jaw", HINGE, tuple(hx((0, -0.39, -0.165))), head_up, "Head")
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
    top = hx((0, -0.08, 0.10))
    _bone(B, "Socket_Head", tuple(top), tuple(top + np.array((0, 0, 0.1))), FWD, "Head")
    mouth = hx((0, -0.31, -0.160))
    _bone(B, "Socket_Mouth", tuple(mouth), tuple(mouth + np.array((0, 0, 0.1))), FWD, "Jaw")
    _bone(B, "Socket_Back", (0, -0.15, 1.220), (0, -0.15, 1.320), FWD, "Spine2")
    for s, sfx in ((1, "L"), (-1, "R")):                                  # the beams' tips (trophies, effects)
        p = np.array(antler_tubes(s)[0][1][-1][:3])
        _bone(B, f"Socket_Antler{sfx}", tuple(p), tuple(p + np.array((0, 0, 0.1))), FWD, "Head")
    return B
