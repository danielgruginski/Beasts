"""What floats inside the ooze, seen through its shell: the nucleus, food vacuoles, and the half-digested remains
of an adventurer (skull, two long bones, a helmet, a few coins, and a rusty sword whose hilt still sticks out of the
ooze's back).

One mesh, `OozeContents`, with a face attribute `part` (PART ids) the painter reads. Every piece is checked against
the shell's distance field: all of it sits at least `MARGIN` inside, except the sword's grip and pommel (and its
guard, just outside the surface).
"""
import math
import numpy as np
import bpy, bmesh
from mathutils import Matrix, Euler, Vector

from beast_common import fbm, mesh_obj
import ooze_body as OB

PART = dict(nucleus=1, bone=2, blade=3, grip=4, brass=5, helm=6, coin=7, vacuole=8)
MARGIN = 0.07
NUCLEUS2 = 0.84                     # the twin nucleus's size (Split grows it to 1)


# ------------------------------------------------------------------ small mesh builders (local space, numpy)

def _sdf_piece(fn, lo, hi, voxel, target):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    i0 = np.floor(lo / voxel).astype(int) - 2
    i1 = np.ceil(hi / voxel).astype(int) + 2
    idx = np.stack(np.meshgrid(*[np.arange(a, b + 1) for a, b in zip(i0, i1)], indexing="ij"), -1)
    P = idx.astype(np.float64) * voxel
    V, F = OB.sdf_mesh(fn(P), i0, voxel)
    return _decimate(V, F, target)


def _decimate(V, F, target):
    n = sum(len(f) - 2 for f in F)
    me = bpy.data.meshes.new("_ooze_dec")
    me.from_pydata(np.asarray(V).tolist(), [], [list(f) for f in F])
    ob = bpy.data.objects.new("_ooze_dec", me)
    bpy.context.scene.collection.objects.link(ob)
    if n > target:
        mod = ob.modifiers.new("D", 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = target / n
        mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    m2 = ev.to_mesh()
    V2 = np.array([v.co[:] for v in m2.vertices])
    F2 = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return V2, F2


def _ball(r, seg=6, rings=4, scale=(1, 1, 1)):
    V = [np.array([0, 0, -1.0])]
    for i in range(1, rings):
        th = np.pi * i / rings - np.pi / 2
        for j in range(seg):
            ph = 2 * np.pi * (j + 0.5 * (i % 2)) / seg
            V.append(np.array([np.cos(th) * np.cos(ph), np.cos(th) * np.sin(ph), np.sin(th)]))
    V.append(np.array([0, 0, 1.0]))
    V = np.array(V) * np.asarray(scale, float) * r
    F = [(0, 1 + (j + 1) % seg, 1 + j) for j in range(seg)]
    for i in range(rings - 2):
        for j in range(seg):
            a, b = 1 + i * seg + j, 1 + i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    top = len(V) - 1
    base = 1 + (rings - 2) * seg
    F += [(top, base + j, base + (j + 1) % seg) for j in range(seg)]
    return V, F


def _lathe(profile, seg):
    """Surface of revolution about Z through profile [(r, z)...] (r = 0 ends become poles). Open where the
    profile is open."""
    V, rings = [], []
    for r, z in profile:
        if r < 1e-6:
            rings.append([len(V)])
            V.append((0, 0, z))
        else:
            rings.append(list(range(len(V), len(V) + seg)))
            V += [(r * math.cos(2 * math.pi * j / seg), r * math.sin(2 * math.pi * j / seg), z) for j in range(seg)]
    F = []
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1:
            F += [(a[0], b[j], b[(j + 1) % seg]) for j in range(seg)]
        elif len(b) == 1:
            F += [(a[j], a[(j + 1) % seg], b[0])[::-1] for j in range(seg)]
        else:
            F += [(a[j], a[(j + 1) % seg], b[(j + 1) % seg], b[j]) for j in range(seg)]
    return np.array(V, float), F


def _box(half, c=(0, 0, 0)):
    s = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                  [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float) * np.asarray(half, float)
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return s + np.asarray(c, float), F


def _skull():
    """A stylised skull facing -Y (no jaw: it came off), ~0.19 x 0.25 x 0.2 m after the 1.25 scale."""
    def fn(P):
        d = OB.sd_ellipsoid(P, (0, 0.015, 0.03), (0.072, 0.095, 0.082))                 # cranium
        d = OB.smin(d, OB.sd_ellipsoid(P, (0, -0.066, -0.034), (0.052, 0.05, 0.05)), 0.03)   # face, maxilla
        for s in (-1, 1):
            d = OB.smin(d, OB.sd_ellipsoid(P, (s * 0.053, -0.058, -0.022), (0.022, 0.032, 0.018)), 0.015)
        d = OB.smax(d, -0.075 - P[..., 2], 0.01)                                         # the base
        for s in (-1, 1):                                                                # orbits
            d = OB.smax(d, -(np.linalg.norm(P - np.array([s * 0.031, -0.099, -0.002]), axis=-1) - 0.025), 0.008)
        d = OB.smax(d, -OB.sd_ellipsoid(P, (0, -0.113, -0.042), (0.012, 0.02, 0.019)), 0.005)   # nose
        return d
    V, F = _sdf_piece(fn, (-0.1, -0.13, -0.09), (0.1, 0.12, 0.12), 0.0045, 380)
    return V * 1.25, F


def _long_bone(length=0.46, r=0.017):
    h = length / 2 - 0.03

    def fn(P):
        d = OB.sd_capsule(P, np.array([0, -h, 0.0]), np.array([0, h, 0.0]), r, r * 0.95)
        d = OB.smin(d, np.linalg.norm(P - np.array([0.012, h + 0.035, 0.012]), axis=-1) - 0.029, 0.02)   # head
        d = OB.smin(d, OB.sd_ellipsoid(P, (0, h + 0.012, -0.016), (0.02, 0.03, 0.02)), 0.015)          # trochanter
        for s in (-1, 1):
            d = OB.smin(d, np.linalg.norm(P - np.array([s * 0.021, -h - 0.02, 0.004]), axis=-1) - 0.025, 0.02)
        return d
    return _sdf_piece(fn, (-0.06, -h - 0.06, -0.05), (0.06, h + 0.07, 0.06), 0.006, 150)


def _nucleus():
    def fn(P):
        d = OB.sd_ellipsoid(P, (0, 0, 0), (0.21, 0.19, 0.17))
        return d + 0.014 * fbm(P * 9.0, 2, 3)
    return _sdf_piece(fn, (-0.24, -0.22, -0.2), (0.24, 0.22, 0.2), 0.014, 220)


def _sword():
    """Arming sword along -Y from the guard (y 0) to the tip (y -0.64); grip and pommel at +Y.
    -> list of (V, F, part)."""
    out = []
    secs = [(0.0, 0.026, 0.0045), (-0.32, 0.022, 0.004), (-0.56, 0.014, 0.0035), (-0.64, 0.0, 0.0)]
    V, F = [], []
    for y, w, t in secs:
        if w == 0:
            V.append((0, y, 0))
        else:
            V += [(w, y, 0), (0, y, t), (-w, y, 0), (0, y, -t)]
    for k in range(len(secs) - 2):
        a, b = 4 * k, 4 * (k + 1)
        F += [(a + j, b + j, b + (j + 1) % 4, a + (j + 1) % 4) for j in range(4)]
    tip, last = len(V) - 1, 4 * (len(secs) - 2)
    F += [(last + j, tip, last + (j + 1) % 4) for j in range(4)]
    F.append((3, 2, 1, 0))
    out.append((np.array(V, float), F, PART["blade"]))
    gV, gF = _box((0.085, 0.012, 0.013), (0, 0.012, 0))                                  # crossguard
    out.append((gV, gF, PART["brass"]))
    pr = [(0.0, 0.024), (0.012, 0.024), (0.014, 0.06), (0.013, 0.118), (0.0, 0.118)]
    lV, lF = _lathe([(r, z) for r, z in pr], 6)                                          # grip along +Z
    lV = lV[:, [0, 2, 1]]                                                                # Z -> Y
    lF = [f[::-1] for f in lF]
    out.append((lV, lF, PART["grip"]))
    bV, bF = _ball(0.022, 6, 4, (1, 0.8, 1))
    out.append((bV + np.array([0, 0.135, 0]), bF, PART["brass"]))
    return out


def _helm():
    """A battered nasal helm (open bowl, rim, nose guard), crown up +Z."""
    prof = [(0.112, 0.0), (0.110, 0.05), (0.095, 0.10), (0.055, 0.137), (0.0, 0.148)]
    inner = [(0.0, 0.140), (0.05, 0.13), (0.088, 0.095), (0.102, 0.05), (0.104, 0.006)]
    V, F = _lathe(prof[::-1], 10)                                      # outer, pole first
    V2, F2 = _lathe(inner, 10)
    n = len(V)
    F = [f for f in F] + [tuple(i + n for i in f[::-1]) for f in F2]
    V = np.vstack([V, V2])
    # rim: join the outer lip (last ring of the outer) to the inner lip (last ring of the inner)
    o = list(range(n - 10, n))
    i = list(range(n + len(V2) - 10, n + len(V2)))
    F += [(o[j], i[j], i[(j + 1) % 10], o[(j + 1) % 10]) for j in range(10)]
    nV, nF = _box((0.012, 0.006, 0.045), (0, -0.112, -0.02))                            # nasal guard
    F += [tuple(x + len(V) for x in f) for f in nF]
    V = np.vstack([V, nV])
    return V, F


def _coin():
    V, F = _lathe([(0.0, 0.002), (0.022, 0.002), (0.022, -0.002), (0.0, -0.002)], 8)
    return V, F


# ------------------------------------------------------------------ placement

def _xf(loc, rot_deg, scale=1.0):
    return Matrix.Translation(loc) @ Euler([math.radians(a) for a in rot_deg], 'XYZ').to_matrix().to_4x4() @ \
        Matrix.Scale(scale, 4)


def _apply(V, M):
    V = np.asarray(V, float)
    A = np.array(M)
    return V @ A[:3, :3].T + A[:3, 3]


def _sword_pose():
    """Aim the sword so it went in through the ooze's back: the guard sits just outside the surface, the blade
    runs 0.6 m inward and down toward the middle."""
    c = np.array([-0.08, 0.22, 0.48])
    out = np.array([-0.35, 0.60, 0.72])
    out /= np.linalg.norm(out)
    s = np.linspace(0, 1.4, 281)
    d = OB.field(c + s[:, None] * out)
    exit_s = s[np.argmax(d > 0)]
    guard = c + out * (exit_s + 0.02)
    # local -Y (the blade) points inward: build a frame with y = out
    y = out
    x = np.cross(y, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    R = Matrix(np.stack([x, y, z], 1).tolist()).to_4x4()
    R = R @ Euler((0, math.radians(35), 0)).to_matrix().to_4x4()          # twist the blade's flat a little
    return Matrix.Translation(Vector(guard)) @ R


def placements():
    """name -> (V, F, part, matrix)."""
    rng = np.random.default_rng(11)
    items = []
    V, F = _nucleus()
    items.append(("nucleus", V, F, PART["nucleus"], _xf((0.10, 0.22, 0.52), (0, 0, 20))))
    # its twin, a little smaller and hidden inside it: it grows out when the ooze divides (Split, on its own bone)
    items.append(("nucleus2", V * NUCLEUS2, F, PART["nucleus"], _xf((0.10, 0.22, 0.52), (0, 0, 200))))
    V, F = _skull()
    items.append(("skull", V, F, PART["bone"], _xf((-0.30, -0.26, 0.40), (18, -22, 38))))
    V, F = _long_bone(0.46)
    items.append(("femur", V, F, PART["bone"], _xf((0.32, -0.05, 0.20), (12, 8, -55))))
    V, F = _long_bone(0.38, 0.015)
    items.append(("shin", V, F, PART["bone"], _xf((-0.22, 0.38, 0.16), (-8, 82, 20))))
    M = _sword_pose()
    for k, (V, F, part) in enumerate(_sword()):
        items.append((f"sword{k}", V, F, part, M))
    V, F = _helm()
    items.append(("helm", V, F, PART["helm"], _xf((0.40, -0.48, 0.26), (75, 15, -30))))
    coins = [(0.05, -0.30, 0.07), (0.18, -0.38, 0.09), (-0.05, -0.12, 0.06), (0.30, 0.25, 0.08),
             (-0.40, 0.05, 0.10), (0.10, 0.48, 0.07), (-0.12, -0.50, 0.08)]
    for k, c in enumerate(coins):
        V, F = _coin()
        rot = rng.uniform(-60, 60, 3)
        items.append((f"coin{k}", V, F, PART["coin"], _xf(c, rot)))
    vac = [((0.42, 0.30, 0.55), 0.07), ((-0.45, -0.05, 0.62), 0.06), ((0.05, -0.15, 0.78), 0.05),
           ((-0.10, 0.55, 0.40), 0.065), ((0.48, -0.20, 0.62), 0.045), ((-0.55, 0.30, 0.35), 0.05),
           ((0.20, 0.05, 0.86), 0.04)]
    for k, (c, r) in enumerate(vac):
        V, F = _ball(r, 8, 5)
        items.append((f"vac{k}", V, F, PART["vacuole"], _xf(c, (0, 0, 0))))
    return items


def build_contents(coll, name="OozeContents"):
    """Build the contents mesh. -> (object, report with the depth check)."""
    bm = bmesh.new()
    lay = bm.faces.layers.int.new("part")
    piece = bm.faces.layers.int.new("piece")
    report = dict(pieces={}, outside=[])
    for k, (nm, V, F, part, M) in enumerate(placements()):
        W = _apply(V, M)
        d = OB.field(W, floor=False)              # things on the bottom lie on the floor, not in the sole
        report["pieces"][nm] = (len(F), round(float(d.max()), 3))
        sticking_out = nm.startswith("sword")     # it went in through the back: the blade comes out there
        if not sticking_out and d.max() > -MARGIN:
            report["outside"].append((nm, round(float(d.max()), 3)))
        vs = [bm.verts.new(p) for p in W]
        for f in F:
            try:
                face = bm.faces.new([vs[i] for i in f])
            except ValueError:
                continue
            face[lay] = part
            face[piece] = k
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    smooth_parts = {PART["nucleus"], PART["bone"], PART["vacuole"], PART["helm"], PART["grip"]}
    for f in bm.faces:
        f.smooth = f[lay] in smooth_parts
    ob = mesh_obj(name, bm, coll, recalc=False)
    ob["pieces"] = list(report["pieces"])                         # face attribute `piece` indexes this list
    report["tris"] = len(ob.data.polygons)
    return ob, report
