"""Giant turtle (2026-10-23, a unit from Daniel's card game): body, shell, skeleton and skinning. Facing -Y, left
side +X.

My calls (Daniel gave no details): a huge, slow land and swamp turtle after the alligator snapping turtle: a 2.6 m
carapace standing 1.6 m high, domed, with three knobbed keels and a saw-toothed back rim, the marginal scutes flaring
over the legs; a small cross-shaped plastron joined by bridges; a big triangular head with a hooked beak; a thick
wrinkled neck; columnar, elephantine legs on round feet with blunt claws; a short thick tail with a crest. About 3.5 m
from beak to tail tip with the head out.

Pieces: one fused skin (beast_body.fuse_body: a core inside the shell, neck, head, four legs and feet, tail); the
carapace (a parametric dome over a squarish outline, a rolled lip under the rim and an inner dome: one closed
shell), the plastron and the bridges, the lower beak (Jaw), the eyes, the claws. The shell rides rigid on Spine1
(the spine never bends: a turtle's back is its shell). The skin gets heat weights solved on its own
(beast_rig.skin_with_pieces); the pieces carry their own weights.

build_body() -> TurtleBody; rest_bones() is the skeleton: the beasts' names (Hips, Spine1, Spine2, Chest, Neck1-3,
Head, Jaw, Tail1-3, Scapula / UpperArm / Forearm / FrontPaw / FrontToes, Thigh / Shin / HindFoot / HindToes), Root,
Motion, sockets Socket_Head, Socket_Mouth, Socket_Back (on the shell's top).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, smoothstep, fbm
import beast_body, beast_rig
from beast_body import PART, ellipsoid, _write_info
import dragon_body as DB

NAME, PREFIX = "Turtle", "TRT"
RIG = "TurtleRig"
BODY = "TurtleBody"
VOXEL, BODY_TRIS = 0.012, 2800
UP, FWD = (0, 0, 1), (0, -1, 0)
SIDES = ((1, "L"), (-1, "R"))

# ----------------------------------------------------------------------------------------- landmarks (left side)
J = dict(HIPS=(0, 0.60, 0.95), RUMP=(0, 0.95, 0.88), MID=(0, 0.00, 1.00), CHEST=(0, -0.50, 0.98),
         NECK=(0, -0.85, 0.90), N2=(0, -1.08, 0.885), N3=(0, -1.28, 0.875), POLL=(0, -1.48, 0.88),
         SNOUT=(0, -2.03, 0.83), HINGE=(0, -1.60, 0.775), CHIN=(0, -1.99, 0.770),
         SCAP=(0.36, -0.66, 0.98), SHO=(0.64, -0.86, 0.77), ELB=(0.97, -0.96, 0.55), WRI=(0.98, -1.00, 0.17),
         FPAW=(0.98, -1.05, 0.06), FTOE=(0.98, -1.20, 0.025),
         HIP=(0.55, 0.85, 0.80), KNEE=(0.92, 0.98, 0.52), HOCK=(0.93, 1.04, 0.17), HPAW=(0.93, 1.01, 0.06),
         HTOE=(0.93, 0.86, 0.025))
TAIL = [(0, 0.95, 0.86), (0, 1.25, 0.70), (0, 1.52, 0.55), (0, 1.80, 0.40)]

# the carapace: outline (front / back half-length, half-width, superellipse exponent), rim heights, apex
SHELL = dict(apex=(0.0, 0.05, 1.62), front=1.27, back=1.32, half_w=1.00, n=2.6, rim_side=0.62, rim_front=0.90,
             rim_back=0.78, thick=0.12, lip_out=0.05, lip_in=0.15)
KEELS = (0.0, 0.47, -0.47)
SCUTE_Y = (-0.86, -0.43, 0.02, 0.47, 0.90)          # the vertebral / costal scutes' rows (centres)
N_PHI, N_R = 48, 12


# ----------------------------------------------------------------------------------------- skeleton
def rest_bones():
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.5, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.3, None, True)
    b = lambda n, a, t, z, par: DB._bone(B, n, a, t, z, par)
    b("Hips", J['HIPS'], J['RUMP'], UP, "Root")
    b("Spine1", J['HIPS'], J['MID'], UP, "Hips")
    b("Spine2", J['MID'], J['CHEST'], UP, "Spine1")
    b("Chest", J['CHEST'], J['NECK'], UP, "Spine2")
    b("Neck1", J['NECK'], J['N2'], UP, "Chest")
    b("Neck2", J['N2'], J['N3'], UP, "Neck1")
    b("Neck3", J['N3'], J['POLL'], UP, "Neck2")
    b("Head", J['POLL'], J['SNOUT'], UP, "Neck3")
    b("Jaw", J['HINGE'], J['CHIN'], UP, "Head")
    par = "Hips"
    for i in range(len(TAIL) - 1):
        b(f"Tail{i + 1}", TAIL[i], TAIL[i + 1], UP, par)
        par = f"Tail{i + 1}"
    for s, sfx in SIDES:
        m = lambda p: DB._m(p, s)
        b(f"Scapula{sfx}", m(J['SCAP']), m(J['SHO']), FWD, "Chest")
        b(f"UpperArm{sfx}", m(J['SHO']), m(J['ELB']), FWD, f"Scapula{sfx}")
        b(f"Forearm{sfx}", m(J['ELB']), m(J['WRI']), FWD, f"UpperArm{sfx}")
        b(f"FrontPaw{sfx}", m(J['WRI']), m(J['FPAW']), FWD, f"Forearm{sfx}")
        b(f"FrontToes{sfx}", m(J['FPAW']), m(J['FTOE']), UP, f"FrontPaw{sfx}")
        b(f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
        b(f"Shin{sfx}", m(J['KNEE']), m(J['HOCK']), FWD, f"Thigh{sfx}")
        b(f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), FWD, f"Shin{sfx}")
        b(f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
    b("Socket_Head", (0, -1.62, 1.02), (0, -1.62, 1.12), FWD, "Head")
    b("Socket_Mouth", (0, -1.90, 0.80), (0, -1.90, 0.90), FWD, "Jaw")
    top = carapace_point(0.0, 0.0)
    b("Socket_Back", tuple(top), (top[0], top[1], top[2] + 0.2), FWD, "Spine1")
    return B


# ----------------------------------------------------------------------------------------- the carapace
def _rim_xy(phi):
    """The rim's outline at angle phi (0 = front, pi/2 = left side, pi = back): a superellipse, the back
    saw-toothed."""
    S = SHELL
    c, s = math.cos(phi), math.sin(phi)
    e = 2.0 / S['n']
    L = S['front'] if c > 0 else S['back']
    x = S['half_w'] * math.copysign(abs(s) ** e, s)
    y = -L * math.copysign(abs(c) ** e, c)
    if c < -0.25:                                   # the serrated back rim: 12 teeth across it
        k = (phi - math.pi) / (math.pi * 0.42) * 6.0
        tooth = abs((k % 1.0) - 0.5) * 2.0          # 1 at a tooth's point, 0 between
        f = 1.0 + 0.045 * tooth * smoothstep(-0.25, -0.5, c)
        x, y = x * f, y * f
    return x, y


# The openings (Daniel, 2026-10-23: "The head and limbs emerge right from the cask wall, there should be some space where
# they are inserted"): the rim arches up over the neck, each leg and the tail, so they leave the shell through a gap
# between the carapace's edge and the plastron, not through its wall. (angle, half-width, lift): the lift puts the edge
# ~0.07-0.1 m over the top of what passes under it (the leg at the rim: front 0.86 m, hind 0.82, neck 1.05, tail 0.80).
ARCHES = ((0.0, 0.42, 0.30), (0.85, 0.36, 0.26), (-0.85, 0.36, 0.26), (2.29, 0.34, 0.24), (-2.29, 0.34, 0.24),
          (math.pi, 0.26, 0.12))


def _arch(phi):
    """The rim's lift at angle phi: a smooth cos^2 bump per opening."""
    h = 0.0
    for a, w, lift in ARCHES:
        d = (phi - a + math.pi) % (2 * math.pi) - math.pi
        if abs(d) < w:
            h = max(h, lift * math.cos(0.5 * math.pi * d / w) ** 2)
    return h


def _rim_z(phi):
    S = SHELL
    c = math.cos(phi)
    return (S['rim_side'] + (S['rim_front'] - S['rim_side']) * max(c, 0.0) ** 2 +
            (S['rim_back'] - S['rim_side']) * max(-c, 0.0) ** 2) + _arch(phi)


def _relief(x, y, r):
    """The keels and their knobs, the scutes' gentle bulge; 0 at the rim."""
    fade = 1.0 - float(smoothstep(0.78, 0.97, r))
    h = 0.0
    for xk in KEELS:
        w = 0.10 if xk == 0 else 0.13
        h += (0.050 if xk == 0 else 0.032) * math.exp(-((x - xk) / w) ** 2)
        for yc in SCUTE_Y:
            h += (0.090 if xk == 0 else 0.068) * math.exp(-((x - xk) / 0.075) ** 2 - ((y - yc - 0.12) / 0.10) ** 2)
    return h * fade


def relief_np(x, y, r):
    """_relief for arrays (the painter)."""
    fade = 1.0 - smoothstep(0.78, 0.97, r)
    h = np.zeros_like(x)
    for xk in KEELS:
        w = 0.10 if xk == 0 else 0.13
        h = h + (0.050 if xk == 0 else 0.032) * np.exp(-((x - xk) / w) ** 2)
        for yc in SCUTE_Y:
            h = h + (0.090 if xk == 0 else 0.068) * np.exp(-((x - xk) / 0.075) ** 2 - ((y - yc - 0.12) / 0.10) ** 2)
    return h * fade


def carapace_point(phi, r):
    """Outer surface point at outline angle phi and radial fraction r (0 = apex, 1 = rim)."""
    S = SHELL
    ax, ay, az = S['apex']
    rx, ry = _rim_xy(phi)
    x, y = ax + (rx - ax) * r, ay + (ry - ay) * r
    zr = _rim_z(phi)
    z = zr + (az - zr) * (1.0 - min(r, 1.0) ** 2.1) ** 0.62 + _relief(x, y, r)
    return np.array((x, y, z))


def build_carapace(bm):
    """One closed shell: the outer dome (a pole at the apex, N_R rings), the rim rolled out and under (the lip), the
    inner dome back up to its own pole. UV seams: round the rim's outer edge and the lip's inner edge, and one cut
    across the lip and inner dome at the back, so the top unwraps as a disc."""
    S = SHELL
    phis = [2 * math.pi * j / N_PHI for j in range(N_PHI)]
    rings = []
    for i in range(1, N_R + 1):
        r = i / N_R
        rings.append([carapace_point(ph, r) for ph in phis])
    rim = rings[-1]
    out_dir = []
    for j, ph in enumerate(phis):
        d = np.array((rim[j][0] - S['apex'][0], rim[j][1] - S['apex'][1], 0.0))
        out_dir.append(d / max(np.linalg.norm(d), 1e-6))
    lip1 = [rim[j] + out_dir[j] * S['lip_out'] + np.array((0, 0, -0.05)) for j in range(N_PHI)]
    lip2 = [lip1[j] - out_dir[j] * S['lip_in'] + np.array((0, 0, 0.015)) for j in range(N_PHI)]
    inner = []
    for r in (0.85, 0.62, 0.35):
        inner.append([carapace_point(ph, r) + np.array((0, 0, -S['thick'] - 0.02 * (1 - r))) for ph in phis])
    pole_in = np.array(S['apex']) + np.array((0, 0, -S['thick'] - 0.03))
    all_rings = rings + [lip1, lip2] + inner
    V = [[bm.verts.new(Vector(p)) for p in ring] for ring in all_rings]
    top = bm.verts.new(Vector(carapace_point(0.0, 0.0)))
    bot = bm.verts.new(Vector(pole_in))
    for j in range(N_PHI):
        j1 = (j + 1) % N_PHI
        bm.faces.new((top, V[0][j], V[0][j1]))
        bm.faces.new((bot, V[-1][j1], V[-1][j]))
    for a, b in zip(V[:-1], V[1:]):
        for j in range(N_PHI):
            j1 = (j + 1) % N_PHI
            bm.faces.new((a[j], b[j], b[j1], a[j1]))
    nr = len(rings)

    def seam_ring(k):
        for j in range(N_PHI):
            e = bm.edges.get((V[k][j], V[k][(j + 1) % N_PHI]))
            if e is not None:
                e.seam = True
    seam_ring(nr - 1)                                # the rim's edge: the top is one disc
    seam_ring(nr + 1)                                # the lip's inner edge
    jb = N_PHI // 2                                  # a cut at the back across the lip and the inner dome
    line = [V[k][jb] for k in range(nr - 1, len(V))] + [bot]
    for p, q in zip(line[:-1], line[1:]):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    return [v for ring in V for v in ring] + [top, bot]


PLASTRON = [(0, -0.98, 0.535, 0.40, 0.035, 0.035), (0, -0.70, 0.510, 0.64, 0.040, 0.045),
            (0, -0.20, 0.500, 0.74, 0.045, 0.050), (0, 0.40, 0.505, 0.72, 0.045, 0.050),
            (0, 0.85, 0.520, 0.58, 0.040, 0.045), (0, 1.05, 0.540, 0.36, 0.035, 0.035)]


def build_plastron(bm):
    vs = loft(bm, PLASTRON, up=UP, seg=16, per_seg=2, cap0=0.5, cap1=0.5, capk=2, shape=0.55, split=True)
    for s in (1, -1):                                # the bridges up to the carapace between the legs
        vs += loft(bm, [(s * 0.86, -0.44, 0.565, 0.13, 0.065, 0.065), (s * 0.90, 0.02, 0.565, 0.14, 0.075, 0.075),
                        (s * 0.86, 0.48, 0.565, 0.13, 0.065, 0.065)], up=UP, seg=8, per_seg=2, cap0=0.6, cap1=0.6,
                   capk=1, shape=0.7)
    return vs


# ----------------------------------------------------------------------------------------- the fused skin
NECK = [(0, -0.55, 0.92, 0.24, 0.22, 0.22), (0, -0.95, 0.90, 0.21, 0.19, 0.20), (0, -1.25, 0.88, 0.18, 0.15, 0.17),
        (0, -1.45, 0.87, 0.165, 0.13, 0.14)]
SNOUT = [(0, -1.70, 0.885, 0.17, 0.105, 0.105), (0, -1.86, 0.865, 0.12, 0.090, 0.105),
         (0, -1.97, 0.835, 0.075, 0.068, 0.095), (0, -2.05, 0.765, 0.030, 0.035, 0.050)]
FLEG = [(0.42, -0.72, 0.86, 0.20), (0.66, -0.86, 0.76, 0.20), (0.98, -0.96, 0.55, 0.175), (0.99, -0.99, 0.34, 0.165),
        (0.98, -1.00, 0.16, 0.165), (0.98, -1.02, 0.08, 0.17)]
HLEG = [(0.38, 0.72, 0.86, 0.22), (0.62, 0.88, 0.75, 0.21), (0.92, 0.98, 0.52, 0.20), (0.93, 1.02, 0.32, 0.185),
        (0.93, 1.04, 0.16, 0.175), (0.93, 1.02, 0.08, 0.18)]
TAIL_ROWS = [(0, 0.92, 0.85, 0.20, 0.18, 0.18), (0, 1.25, 0.70, 0.15, 0.13, 0.13), (0, 1.52, 0.55, 0.095, 0.085, 0.085),
             (0, 1.80, 0.40, 0.035, 0.03, 0.03)]
BLOBS = [  # centre, radii, mirrored
    ((0, 0.00, 0.88), (0.78, 1.05, 0.40), False),        # the core under the shell
    ((0, -1.62, 0.905), (0.22, 0.26, 0.16), False),      # the cranium: broad and flat
    ((0.15, -1.55, 0.845), (0.15, 0.18, 0.13), True),     # the jaw muscles behind the eyes: a wedge from above
    ((0.10, -1.775, 0.975), (0.065, 0.080, 0.038), True),  # brows over the eyes
    ((0, -1.55, 0.745), (0.15, 0.20, 0.085), False),     # the throat
    ((0.98, -1.05, 0.075), (0.19, 0.22, 0.085), True),   # front feet
    ((0.93, 1.00, 0.075), (0.20, 0.23, 0.085), True),    # hind feet
    ((0, 1.30, 0.830), (0.030, 0.06, 0.05), False),      # the tail's crest
    ((0, 1.46, 0.700), (0.026, 0.05, 0.045), False),
    ((0, 1.61, 0.600), (0.020, 0.04, 0.035), False),
]
EYE_C, EYE_N, EYE_R = (0.128, -1.80, 0.945), (0.70, -0.45, 0.55), 0.034


def _leg_rows(rows, s):
    return [(s * x, y, z, r, r, r) for x, y, z, r in rows]


def _sculpt(co, no):
    """Rough skin everywhere (tubercles), folds across the neck."""
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    bumps = 0.006 * smoothstep(0.1, 0.7, fbm(co * 14.0, 2, seed=71))
    neck = smoothstep(-0.70, -0.80, y) * smoothstep(-1.50, -1.40, y) * (np.abs(x) < 0.30)
    folds = 0.012 * neck * (0.5 + 0.5 * np.sin((y + 0.03 * fbm(co * 6, 2, seed=72)) * 2 * np.pi / 0.085))
    return co + no * (bumps - folds)[:, None]


def _dec_weight(co):
    x, y, z = co
    if y < -1.45:
        return 0.35                                  # the head keeps the most
    if abs(x) > 0.55 and z < 0.75:
        return 0.55                                  # the legs and feet
    if abs(x) < 0.80 and -0.75 < y < 0.80 and z > 0.55:
        return 1.0                                   # the core, under the shell
    return 0.7


def build_skin():
    bm = bmesh.new()
    loft(bm, NECK, up=UP, seg=16, per_seg=3, cap0=0.6, cap1=0.6)
    loft(bm, SNOUT, up=UP, seg=16, per_seg=3, cap0=0.4, cap1=0.6, shape=0.9)
    loft(bm, TAIL_ROWS, up=UP, seg=12, per_seg=3, cap0=0.6, cap1=0.8)
    for s in (1, -1):
        loft(bm, _leg_rows(FLEG, s), up=FWD, seg=14, per_seg=3, cap0=0.6, cap1=0.6)
        loft(bm, _leg_rows(HLEG, s), up=FWD, seg=14, per_seg=3, cap0=0.6, cap1=0.6)
    for c, r, mirror in BLOBS:
        for s in ((1, -1) if mirror else (1,)):
            ellipsoid(bm, (s * c[0], c[1], c[2]), r, seg=24, rings=16)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    body, hi = beast_body.fuse_body(bm, PREFIX, VOXEL, BODY_TRIS, sculpts=(_sculpt,), dec_weight=_dec_weight,
                                    seam_x=0.02, flat_z=0.012, fillet_iters=60)
    import zwolf_body
    zwolf_body.tidy(body)
    return body, hi


# ----------------------------------------------------------------------------------------- pieces
def build_pieces(skin):
    bml = bmesh.new()
    bml.from_mesh(skin.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    acc = DB.Acc()
    LM = {}
    n_out = N_PHI * (N_R + 2)                        # outer rings, lip; then the inner rings; the two poles
    acc.add(build_carapace, "Spine1", ['shell'] * n_out + ['shell_in'] * (N_PHI * 3) + ['shell', 'shell_in'])
    acc.add(build_plastron, "Spine1", 'shell_low')
    # the lower beak: a U under the hooked upper beak, its tip rising into the hook
    acc.add(lambda bm: loft(bm, [(0, -1.47, 0.750, 0.120, 0.050, 0.060), (0, -1.56, 0.738, 0.168, 0.062, 0.080),
                                 (0, -1.74, 0.722, 0.142, 0.058, 0.068),
                                 (0, -1.90, 0.726, 0.088, 0.050, 0.050), (0, -1.985, 0.745, 0.034, 0.030, 0.030)],
                            up=UP, seg=12, per_seg=2, cap0=0.6, cap1=0.6, shape=0.85), "Jaw", 'jaw')
    for s, sfx in SIDES:
        m = lambda p: np.array(DB._m(p, s))
        n = np.array(EYE_N) * np.array((s, 1, 1))
        n /= np.linalg.norm(n)
        e = m(EYE_C)
        hit = bvh.ray_cast(Vector(e + n * 0.08), Vector(-n), 0.16)[0]
        c = (np.array(hit) if hit is not None else e) - n * 0.008
        LM['eye_' + sfx] = c
        acc.add(lambda bm: dome(bm, c, n, EYE_R, 0.016, seg=12, rings=3), "Head", 'eye')
        # blunt claws: five on a front foot, four on a hind foot
        for k in range(5):
            dx = (k - 2) * 0.07
            base = m((0.98 + dx, -1.17 + 0.012 * abs(k - 2) ** 2, 0.055))
            tip = base + np.array((s * dx * 0.25, -0.085, -0.040))
            acc.add(lambda bm: cone(bm, base, tip, 0.036, seg=4, bend=(0, -0.006, -0.012)), f"FrontToes{sfx}", 'claw')
        for k in range(4):
            dx = (k - 1.5) * 0.075
            base = m((0.93 + dx, 0.85 + 0.012 * abs(k - 1.5) ** 2, 0.055))
            tip = base + np.array((s * dx * 0.25, -0.080, -0.040))
            acc.add(lambda bm: cone(bm, base, tip, 0.038, seg=4, bend=(0, -0.006, -0.012)), f"HindToes{sfx}", 'claw')
    return acc, LM


def build_body():
    """-> (TurtleBody: the fused skin first, then the pieces), the Acc (the pieces' weights), TRT_BodyHi."""
    skin, hi = build_skin()
    acc, LM = build_pieces(skin)
    acc.bm.verts.index_update()
    tags = {}
    for v, part in zip(acc.bm.verts, acc.C):
        tags.setdefault('shell' if part.startswith('shell') else part, []).append(v)
    body, nfur, part_extra = beast_body.join_pieces(skin, acc.bm, tags, PREFIX, BODY)
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    aux = np.concatenate([np.zeros(nfur), [SHELL_AUX.get(c, 0.0) for c in acc.C]])
    att = body.data.color_attributes["info"]
    buf = np.empty(len(body.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    buf = buf.reshape(-1, 4)
    buf[:, 2] = aux
    att.data.foreach_set('color', buf.ravel())
    for k, v in LM.items():
        body[k] = [float(c) for c in v]
    return body, acc, hi


SHELL_AUX = {'shell_in': 0.25, 'shell_low': 0.5}     # info.b: the hidden inner dome, the plastron and bridges


def shell_aux(ob):
    """info.b per vertex (0 = the carapace's top and lip, 0.25 = its hidden inner dome, 0.5 = plastron and
    bridges)."""
    att = ob.data.color_attributes["info"]
    buf = np.empty(len(ob.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    return buf.reshape(-1, 4)[:, 2]


def tri_report(ob):
    return beast_body.tri_report(ob)


# ----------------------------------------------------------------------------------------- skinning
HEAT = ("Hips", "Spine1", "Spine2", "Chest", "Neck1", "Neck2", "Neck3", "Head", "Tail1", "Tail2", "Tail3",
        "ScapulaL", "ScapulaR", "UpperArmL", "UpperArmR", "ForearmL", "ForearmR", "FrontPawL", "FrontPawR",
        "ThighL", "ThighR", "ShinL", "ShinR", "HindFootL", "HindFootR")


def jaw_weight(P):
    """How much the skin under the head follows the lower beak (bounded on every side: the rhino's lesson)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    return (0.75 * smoothstep(0.78, 0.72, z) * smoothstep(-1.48, -1.58, y) * smoothstep(-1.98, -1.90, y) *
            smoothstep(0.21, 0.15, np.abs(x)) * smoothstep(0.60, 0.66, z))


def skin(body, rig, acc):
    rep = beast_rig.skin_with_pieces(body, rig, acc.W, HEAT)
    n = body["n_fur"]
    co = np.array([v.co[:] for v in body.data.vertices[:n]])
    wj = jaw_weight(co)
    sel = np.nonzero(wj > 0.01)[0]
    jaw = body.vertex_groups.get("Jaw") or body.vertex_groups.new(name="Jaw")
    for i in sel:
        v = body.data.vertices[int(i)]
        for g in list(v.groups):
            body.vertex_groups[g.group].add([int(i)], g.weight * (1 - wj[i]), 'REPLACE')
        jaw.add([int(i)], float(wj[i]), 'REPLACE')
    beast_rig.clean_weights(body)
    rep.update(beast_rig.weight_report(body))
    rep["jaw_skin"] = int(len(sel))
    return rep
