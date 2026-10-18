"""The warg's tack (2026-10-12): what the goblins ride theirs with; wild wargs go without. Daniel's reference: a goblin
on a saddle held by straps, a bridle and reins, and a bone war-mask plated over the brow and nose (the mask only for
the ridden ones). Two meshes on WargRig sharing one texture (T_WargTack, 512):

  - WargTack: the saddle (a cloth blanket draped over the back, a leather seat on it with a raised pommel and
    cantle), the girth under the chest behind the forelegs, the breast collar round the front of the chest, stirrup
    leathers with iron stirrups, the bridle (a noseband round the upper muzzle -- the jaw stays free -- cheek straps
    under the eyes, a crownpiece behind the ears), iron bit rings and the reins up to the pommel;
  - WargMask: the bone war-mask over the brow and down the nose, notched clear of the eyes under a heavy brow guard,
    a raised ridge down the middle, two horn spikes at the brow corners.

Laid out in the warg's (wolf) units through warg_body.hw, and fitted to the built body: every surface point is a ray
cast onto the fur (not the hair locks), lifted off it (lifts, widths and thicknesses are world metres). Weights: what
lies on the body copies the skin's weights where it was cast, so it moves with the back, chest and belly; the
bridle, rings and mask ride on Head; the reins blend from Head to Spine2 along their length.
The point attribute "info" holds (part / 255, along (m, or 0..1 down the mask), across (0..1), 1) for the painter
(TACK_PART).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from beast_common import mesh_obj, get_coll, remove_obj, smoothstep, fbm, vnoise, hexc
import warg_body as W

TACK_PART = dict(leather=1, cloth=2, iron=3, bone=4, rein=5, rope=6)      # rope: the mammoth's (mammoth_tack)
S = W.S
SKIN = 'skin'


def _w(p):
    """Wolf units -> world (the warg's warp)."""
    return Vector(W.hw(np.asarray(p, float)))


class _Build:
    """A bmesh and, per vertex, its info (part, along, across) and how it is weighted: (SKIN, surface point),
    ('rigid', bone) or ('blend', t) (Head -> Spine2)."""
    def __init__(self):
        self.bm = bmesh.new()
        self.info, self.bind = {}, {}

    def vert(self, co, part, along, across, bind):
        v = self.bm.verts.new(co)
        self.info[v] = (TACK_PART[part], along, across)
        self.bind[v] = bind
        return v

    def face(self, vs, out):
        """A face wound so that its normal points along out."""
        f = self.bm.faces.new(vs)
        f.normal_update()
        if f.normal.dot(out) < 0:
            f.normal_flip()
        return f


def _fur_bvh(body):
    """The fused fur body alone (no hair, mouth or eyes): what the tack lies on."""
    n = body["n_fur"]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index >= n], context='VERTS')
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


def _on(bvh, a, aim):
    """A ray from a toward aim (world): the first fur surface -> (point, normal), or (None, None)."""
    d = aim - a
    hit = bvh.ray_cast(a, d.normalized(), d.length)
    return (hit[0], hit[1]) if hit[0] is not None else (None, None)


def _ring_pt(bvh, centre, phi, reach=0.45):
    """The fur round an axis along y through centre (wolf units), phi degrees from the top toward the left (+x)."""
    t = math.radians(phi)
    d = np.array((math.sin(t), 0.0, math.cos(t)))
    return _on(bvh, _w(centre + reach * d), _w(centre))


def _smooth_path(pts, per=2):
    """Catmull-Rom through the points, per samples a segment."""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return out


# ----------------------------------------------------------------------------------------- shapes
def band(B, pts, nrms, width, thick, lift, part, bind, closed=False, bottom=False, along0=0.0):
    """A strap through surface points (and their normals): its top face lifted off the surface by lift + thick,
    its two edges down to lift (and its underside, for straps that hang free). along = arc length (m), across
    0..1. bind(k, point) or a fixed bind."""
    M = len(pts)
    rows, sides, s = [], [], along0
    for k in range(M):
        p, n = pts[k], nrms[k]
        a = pts[(k + 1) % M] if closed else pts[min(k + 1, M - 1)]
        b = pts[k - 1] if closed else pts[max(k - 1, 0)]
        t = (a - b).normalized()
        side = t.cross(n).normalized()
        if k:
            s += (pts[k] - pts[k - 1]).length
        bd = bind(k, p) if callable(bind) else bind
        c0, c1 = p + n * lift, p + n * (lift + thick)
        rows.append([B.vert(c0 + side * width / 2, part, s, 0.0, bd), B.vert(c1 + side * width / 2, part, s, 0.0, bd),
                     B.vert(c1 - side * width / 2, part, s, 1.0, bd), B.vert(c0 - side * width / 2, part, s, 1.0, bd)])
        sides.append(side)
    for k in range(M if closed else M - 1):
        A, C = rows[k], rows[(k + 1) % M]
        n, sd = (nrms[k] + nrms[(k + 1) % M]).normalized(), (sides[k] + sides[(k + 1) % M]).normalized()
        B.face((A[1], C[1], C[2], A[2]), n)
        B.face((A[0], C[0], C[1], A[1]), sd)
        B.face((A[2], C[2], C[3], A[3]), -sd)
        if bottom:
            B.face((A[3], C[3], C[0], A[0]), -n)
    if not closed:
        t0 = (pts[1] - pts[0]).normalized()
        t1 = (pts[-1] - pts[-2]).normalized()
        B.face(rows[0], -t0)
        B.face(rows[-1], t1)
    return rows


def patch(B, grid, height, part, bind, base=0.003):
    """A plate over a grid of surface points (rows along, columns across; each (point, normal)): its top at
    height(i, j) off the surface, its rim down to base. along = arc length down the middle column (m), across
    0..1."""
    R, C = len(grid), len(grid[0])
    mid = C // 2
    along = [0.0]
    for i in range(1, R):
        along.append(along[-1] + (grid[i][mid][0] - grid[i - 1][mid][0]).length)
    top = [[B.vert(grid[i][j][0] + grid[i][j][1] * float(height(i, j)), part, along[i], j / (C - 1), bind(grid[i][j][0]))
            for j in range(C)] for i in range(R)]
    centre = sum((grid[i][j][0] for i in range(R) for j in range(C)), Vector()) / (R * C)
    for i in range(R - 1):
        for j in range(C - 1):
            n = grid[i][j][1] + grid[i + 1][j + 1][1]
            B.face((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]), n)
    ring = ([(0, j) for j in range(C)] + [(i, C - 1) for i in range(1, R)] +
            [(R - 1, j) for j in range(C - 2, -1, -1)] + [(i, 0) for i in range(R - 2, 0, -1)])
    low = {}
    for (i, j) in ring:
        p, n = grid[i][j]
        low[(i, j)] = B.vert(p + n * base, part, along[i], j / (C - 1), bind(p))
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        mid_pt = (grid[a[0]][a[1]][0] + grid[b[0]][b[1]][0]) * 0.5
        B.face((top[a[0]][a[1]], top[b[0]][b[1]], low[b], low[a]), mid_pt - centre)
    return top


def ring(B, centre, axis, R, r, part, bind, seg=8, sides=4):
    """A small iron ring (a coarse torus) round centre, axis its normal."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    rows = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        c = Vector(centre) + (u * math.cos(a) + v * math.sin(a)) * R
        o = (u * math.cos(a) + v * math.sin(a))
        rows.append([B.vert(c + (o * math.cos(2 * math.pi * k / sides) + axis * math.sin(2 * math.pi * k / sides)) * r,
                            part, 0.0, k / sides, bind) for k in range(sides)])
    for i in range(seg):
        A, Cr = rows[i], rows[(i + 1) % seg]
        a = 2 * math.pi * (i + 0.5) / seg
        o = (u * math.cos(a) + v * math.sin(a))
        for k in range(sides):
            ang = 2 * math.pi * (k + 0.5) / sides
            B.face((A[k], Cr[k], Cr[(k + 1) % sides], A[(k + 1) % sides]), o * math.cos(ang) + axis * math.sin(ang))


def spike(B, base, tip, r0, part, bind, seg=6):
    base, tip = Vector(base), Vector(tip)
    z = (tip - base).normalized()
    x = z.orthogonal().normalized()
    y = z.cross(x)
    rim = [B.vert(base + (x * math.cos(2 * math.pi * k / seg) + y * math.sin(2 * math.pi * k / seg)) * r0, part,
                  0.0, k / seg, bind) for k in range(seg)]
    apex = B.vert(tip, part, 1.0, 0.5, bind)
    for k in range(seg):
        a = 2 * math.pi * (k + 0.5) / seg
        B.face((rim[k], rim[(k + 1) % seg], apex), x * math.cos(a) + y * math.sin(a) + z * 0.3)


# ----------------------------------------------------------------------------------------- the pieces
BLANKET = dict(y=(-0.200, 0.130), phi=62, rows=8, cols=9, top=0.024)      # draped over the back (wolf y, deg round)
SEAT_SPAN = dict(y=(-0.160, 0.070), phi=32, rows=14, cols=7)               # the leather seat on it
GIRTH_Y = -0.165
BREAST = [(0.150, -0.215, 0.735), (0.170, -0.300, 0.680), (0.160, -0.390, 0.620), (0.125, -0.460, 0.585),
          (0.065, -0.505, 0.565), (0.0, -0.518, 0.560)]                   # left half, round the front of the chest
BREAST_AIM = (0.0, -0.40, 0.63)
NOSE_Y, NOSE_C, NOSE_PHI = -0.865, (0.0, -0.865, 0.810), 112             # noseband round the upper muzzle
CHEEK = [(0.050, -0.835, 0.805), (0.066, -0.790, 0.822), (0.074, -0.735, 0.843), (0.070, -0.685, 0.873),
         (0.060, -0.640, 0.900)]                                          # under the eye, up behind the ear
CROWN_C, CROWN_PHI = (0.0, -0.630, 0.850), 64                             # crownpiece behind the ears
REIN = [(0.052, -0.858, 0.792), (0.074, -0.775, 0.828), (0.088, -0.640, 0.872), (0.084, -0.480, 0.898),
        (0.062, -0.330, 0.912), (0.034, -0.215, 0.912), (0.010, -0.160, 0.905)]   # bit ring, draped over the mane, to
                                                                                # the pommel
STIRRUP_Y = -0.040
STIRRUP_PHI = 66                  # how far round from the top the leathers end (88 hung the irons at the belly line,
                                  # leaving a goblin rider's legs straight; short leathers bend its knees)
MASK_AXIS = ((0.0, -0.690, 0.860), (0.0, -0.785, 0.845), (0.0, -0.930, 0.805))   # back of the brow .. nose
MASK_S = (0.0, 0.35, 1.0)
MASK_W = ((0.0, 40), (0.08, 50), (0.18, 68), (0.24, 62), (0.28, 38), (0.36, 33), (0.45, 34), (0.70, 30),
          (1.0, 12))                                                      # half-width (deg) down the mask: a brow
                                                                          # guard, notched clear of the eyes


def _axis_pt(s):
    ss = np.array(MASK_S)
    A = np.array(MASK_AXIS)
    return np.array([np.interp(s, ss, A[:, k]) for k in range(3)])


def build_saddle(B, bvh):
    skin = lambda p: (SKIN, p)
    # the blanket: draped over the back and down the flanks, a thick felt clear of the fur's bumps
    by, bp = BLANKET['y'], BLANKET['phi']
    grid = []
    for y in np.linspace(by[0], by[1], BLANKET['rows']):
        row = []
        for phi in np.linspace(-bp, bp, BLANKET['cols']):
            p, n = _ring_pt(bvh, W._axis_centre('trunk', y), phi)
            row.append((p, n))
        grid.append(row)
    patch(B, grid, lambda i, j: BLANKET['top'], 'cloth', skin)
    # the seat on it, with a pommel in front and a cantle behind
    sy, sp = SEAT_SPAN['y'], SEAT_SPAN['phi']
    R, C = SEAT_SPAN['rows'], SEAT_SPAN['cols']
    grid = []
    for y in np.linspace(sy[0], sy[1], R):
        row = []
        for phi in np.linspace(-sp, sp, C):
            p, n = _ring_pt(bvh, W._axis_centre('trunk', y), phi)
            row.append((p, n))
        grid.append(row)

    def seat_h(i, j):
        v, u = i / (R - 1), 2 * j / (C - 1) - 1
        edge = float(smoothstep(0.0, 0.09, v) * smoothstep(1.0, 0.91, v))                 # the ends roll over
        h = 0.016 - 0.006 * (1 - u * u) * math.sin(math.pi * v)                           # a dished seat
        h += 0.036 * math.exp(-((v - 0.14) / 0.09) ** 2) * (1 - 0.55 * u * u)          # pommel
        h += 0.046 * math.exp(-((v - 0.86) / 0.09) ** 2) * (1 - 0.45 * u * u)          # cantle
        return BLANKET['top'] + 0.004 + (h - 0.004) * (0.35 + 0.65 * edge)
    patch(B, grid, seat_h, 'leather', skin, base=BLANKET['top'] - 0.002)
    # the girth: from the blanket's edge round under the chest to the other side
    pts, nrm = [], []
    for phi in np.linspace(BLANKET['phi'] - 4, 360 - BLANKET['phi'] + 4, 25):
        p, n = _ring_pt(bvh, W._axis_centre('trunk', GIRTH_Y), phi)
        if p is not None:
            pts.append(p)
            nrm.append(n)
    band(B, pts, nrm, 0.060, 0.007, 0.006, 'leather', lambda k, p: (SKIN, p))
    # the breast collar: round the front of the chest from one side of the blanket to the other
    half = BREAST
    path = half + [(-x, y, z) for x, y, z in reversed(half[:-1])]
    aim = np.array(BREAST_AIM)
    pts, nrm = [], []
    for q in _smooth_path(path, 2):
        q = np.array(q)
        out = (q - aim) / np.linalg.norm(q - aim)
        p, n = _on(bvh, _w(q + 0.25 * out), _w(aim))
        if p is not None:
            pts.append(p)
            nrm.append(n)
    band(B, pts, nrm, 0.050, 0.006, 0.010, 'leather', lambda k, p: (SKIN, p))
    # stirrup leathers down each flank from under the seat, an iron stirrup at the end
    for s in (1, -1):
        pts, nrm = [], []
        for phi in np.linspace(sp - 4, STIRRUP_PHI, 7):
            p, n = _ring_pt(bvh, W._axis_centre('trunk', STIRRUP_Y), s * phi)
            if p is not None:
                pts.append(p)
                nrm.append(n)
        band(B, pts, nrm, 0.035, 0.005, BLANKET['top'] + 0.004, 'leather', lambda k, p: (SKIN, p))
        end, n_end = pts[-1], nrm[-1]
        down = (pts[-1] - pts[-2]).normalized()
        c = end + n_end * (BLANKET['top'] + 0.012) + down * 0.045
        ring(B, c, down.cross(n_end), 0.040, 0.008, 'iron', (SKIN, end), seg=8, sides=4)


def build_bridle(B, bvh):
    head = ('rigid', 'Head')
    # noseband round the upper muzzle (the jaw stays free), its ends at the corners of the mouth
    pts, nrm = [], []
    for phi in np.linspace(-NOSE_PHI, NOSE_PHI, 15):
        p, n = _ring_pt(bvh, np.array(NOSE_C), phi, reach=0.25)
        if p is not None:
            pts.append(p)
            nrm.append(n)
    band(B, pts, nrm, 0.030, 0.005, 0.004, 'leather', head)
    rings = []
    for k in (0, -1):
        c = pts[k] + nrm[k] * 0.012
        ring(B, c, nrm[k], 0.024, 0.0055, 'iron', head, seg=8, sides=4)
        rings.append(c)
    # cheek straps, under the eyes and up behind the ears, and the crownpiece over the poll
    for s in (1, -1):
        pts, nrm = [], []
        for q in _smooth_path([(s * x, y, z) for x, y, z in CHEEK], 2):
            q = np.array(q)
            ax_z = np.interp(q[1], (-0.87, -0.72), (0.81, 0.875))
            aim = np.array((0.0, q[1], ax_z))
            out = (q - aim) / np.linalg.norm(q - aim)
            p, n = _on(bvh, _w(q + 0.20 * out), _w(aim))
            if p is not None:
                pts.append(p)
                nrm.append(n)
        band(B, pts, nrm, 0.026, 0.005, 0.004, 'leather', head)
    pts, nrm = [], []
    for phi in np.linspace(-CROWN_PHI, CROWN_PHI, 11):
        p, n = _ring_pt(bvh, np.array(CROWN_C), phi, reach=0.25)
        if p is not None:
            pts.append(p)
            nrm.append(n)
    band(B, pts, nrm, 0.030, 0.005, 0.004, 'leather', head)
    # the reins: from each bit ring up along the neck to the pommel, hanging free
    for s, c in zip((1, -1), rings):
        path = [c] + [_w((s * x, y, z)) for x, y, z in REIN[1:]]
        pts = _smooth_path(path, 3)
        nrm = []
        for k in range(len(pts)):
            t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
            up = Vector((0, 0, 1))
            nrm.append((up - t * up.dot(t)).normalized())
        L = len(pts) - 1
        band(B, pts, nrm, 0.018, 0.005, 0.0, 'rein', lambda k, p, L=L: ('blend', k / L), bottom=True)


def build_mask(B, bvh):
    """The bone war-mask: rows down the head (s 0 at the back of the brow, 1 at the nose), columns across."""
    head = ('rigid', 'Head')
    R, C = 14, 9
    ss = np.linspace(0, 1, R)
    wt = np.array(MASK_W)
    grid, uvs = [], []
    for s in ss:
        amax = float(np.interp(s, wt[:, 0], wt[:, 1]))
        c = _axis_pt(s)
        row = []
        for u in np.linspace(-1, 1, C):
            p, n = _ring_pt(bvh, c, u * amax, reach=0.20)
            row.append((p, n))
        grid.append(row)
    for i in range(R):                                  # misses (past the head's edge) take their neighbour's
        for j in range(C):
            if grid[i][j][0] is None:
                k = min(range(C), key=lambda jj: abs(jj - j) if grid[i][jj][0] is not None else 99)
                grid[i][j] = grid[i][k]

    def mask_h(i, j):
        s, u = ss[i], 2 * j / (C - 1) - 1
        h = 0.010 + 0.010 * (1 - abs(u)) ** 2                                        # a ridge down the middle
        h += 0.012 * smoothstep(0.10, 0.20, s) * smoothstep(0.30, 0.22, s) * smoothstep(0.4, 0.9, abs(u))   # brow guard
        return h * (1 - 0.35 * smoothstep(0.75, 1.0, s))
    top = patch(B, grid, mask_h, 'bone', lambda p: head, base=0.002)
    # mask coordinates for the painter: along = s down the mask (not metres)
    for i in range(R):
        for j in range(C):
            v = top[i][j]
            B.info[v] = (TACK_PART['bone'], float(ss[i]), j / (C - 1))
    # horn spikes at the brow corners, swept back and out
    i = int(np.argmin(np.abs(ss - 0.20)))
    for j in (1, C - 2):
        p, n = grid[i][j]
        base = p + n * float(mask_h(i, j) - 0.004)
        side = Vector((1 if p.x > 0 else -1, 0, 0))
        d = (n * 0.65 + Vector((0, 1, 0)) * 0.75 + side * 0.25).normalized()
        spike(B, base, base + d * 0.085, 0.016, 'bone', head)


# ----------------------------------------------------------------------------------------- object, weights
def _skin(ob, body, rig, bind):
    """Vertex groups: SKIN copies the nearest fur vertex's weights; rigid; blend Head -> Spine2."""
    n = body["n_fur"]
    names = {g.index: g.name for g in body.vertex_groups}
    kd = KDTree(n)
    for i in range(n):
        kd.insert(body.data.vertices[i].co, i)
    kd.balance()
    ob.vertex_groups.clear()
    groups = {}

    def g(name):
        if name not in groups:
            groups[name] = ob.vertex_groups.new(name=name)
        return groups[name]
    for i, bd in enumerate(bind):
        if bd[0] == SKIN:
            j = kd.find(bd[1])[1]
            for e in body.data.vertices[j].groups:
                g(names[e.group]).add([i], e.weight, 'REPLACE')
        elif bd[0] == 'rigid':
            g(bd[1]).add([i], 1.0, 'REPLACE')
        else:                                            # the reins: Head, then the neck, then the saddle's Spine2
            t = float(np.clip(bd[1], 0, 1))
            wh, ws = float(smoothstep(0.5, 0.0, t)), float(smoothstep(0.5, 1.0, t))
            for name, wgt in (("Head", wh), ("Neck1", 1 - wh - ws), ("Spine2", ws)):
                if wgt > 1e-4:
                    g(name).add([i], wgt, 'REPLACE')
    for m in [m for m in ob.modifiers if m.type == 'ARMATURE']:
        ob.modifiers.remove(m)
    mod = ob.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    ob.parent = rig


def build_tack(body=None, rig=None):
    """-> (WargTack, WargMask), skinned to the rig, info written; UVs and texture by paint_tack()."""
    body = body or bpy.data.objects["WargBody"]
    rig = rig or bpy.data.objects.get("WargRig")
    bvh = _fur_bvh(body)
    B = _Build()
    build_saddle(B, bvh)
    build_bridle(B, bvh)
    build_mask(B, bvh)
    B.bm.verts.index_update()
    bind = [B.bind[v] for v in sorted(B.bind, key=lambda v: v.index)]
    for nm in ("WargMask", "WargTack"):
        remove_obj(nm)
    coll = get_coll("WRG_Body")
    bm = B.bm
    bm.verts.ensure_lookup_table()
    info = {v.index: B.info[v] for v in bm.verts}
    ob = mesh_obj("WargTack", bm, coll, recalc=False)
    att = ob.data.color_attributes.new("info", 'FLOAT_COLOR', 'POINT')
    rgba = np.zeros((len(ob.data.vertices), 4), np.float32)
    for i, (part, along, across) in info.items():
        rgba[i] = (part / 255.0, along, across, 1.0)
    att.data.foreach_set('color', rgba.ravel())
    for p in ob.data.polygons:
        p.use_smooth = True
    if rig is not None:
        _skin(ob, body, rig, bind)
    return ob


def split_mask(ob):
    """The bone faces into their own object, WargMask (same UVs, material, weights)."""
    part = _parts(ob)
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(ob.data)
    for f in bm.faces:
        if part[f.verts[0].index] == TACK_PART['bone']:
            f.select_set(True)
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    mask = [o for o in bpy.context.selected_objects if o is not ob][0]
    mask.name = mask.data.name = "WargMask"
    for g in list(mask.vertex_groups):
        if g.name != "Head":
            mask.vertex_groups.remove(g)
    return mask


def _parts(ob):
    att = ob.data.color_attributes["info"]
    buf = np.empty(len(ob.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    return np.rint(buf.reshape(-1, 4)[:, 0] * 255).astype(int)


def tri_count(*obs):
    return sum(len(p.vertices) - 2 for o in obs for p in o.data.polygons)


# ----------------------------------------------------------------------------------------- UVs, painting
def unwrap(ob, margin=0.008):
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0,
                             scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


TACK_COL = dict(leather='#46301f', leather_dark='#24170f', leather_worn='#7a5a3c', thread='#a08a62',
                cloth='#6e2a1f', cloth_band='#a07a38', cloth_dark='#2e1410', iron='#3d3a37', rust='#6e3b1e',
                bone='#c9bb98', bone_dark='#7d6c4e', grime='#3a2e22', paint='#8a1c14', rein='#3a281b',
                rope='#8a7550', rope_dark='#4a3c26')


def paint_tack(D):
    import beast_paint as BP
    C = {k: hexc(v) for k, v in TACK_COL.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    info = D['info'].reshape(-1, 4)[idx]
    part = np.rint(info[:, 0] * 255).astype(int)
    along, across = info[:, 1], info[:, 2]
    ao = D['ao'].ravel()[idx]
    n = len(P)
    nb = fbm(P * 9.0, 3, seed=51)
    nf = fbm(P * 40.0, 3, seed=52)
    col = np.zeros((n, 3))
    smooth = np.full(n, 0.2)
    hgt = np.zeros(n)
    # leather straps and seat: worn lighter along the edges, a stitch line inside each edge
    lea = (part == TACK_PART['leather']) | (part == TACK_PART['rein'])
    edge = np.minimum(across, 1 - across)
    lc = BP._mix(np.tile(C['leather'], (n, 1)), C['leather_dark'], 0.35 + 0.3 * nb)
    lc = np.where((part == TACK_PART['rein'])[:, None], BP._mix(lc, C['rein'], 0.5), lc)
    lc = BP._mix(lc, C['leather_worn'], 0.45 * smoothstep(0.10, 0.0, edge) + 0.25 * smoothstep(0.3, 0.7, nf))
    stitch = smoothstep(0.03, 0.0, np.abs(edge - 0.16)) * (np.mod(along * 90.0, 1.0) < 0.55)
    lc = BP._mix(lc, C['thread'], 0.8 * stitch)
    col = np.where(lea[:, None], lc, col)
    smooth = np.where(lea, 0.28 - 0.12 * smoothstep(0.2, 0.7, nf), smooth)
    hgt = np.where(lea, 0.3 * nf - 0.5 * stitch, hgt)
    # the blanket: coarse red felt, an ochre band round its edge, frayed and dirty toward the hem
    clo = part == TACK_PART['cloth']
    weave = 0.5 + 0.5 * np.sin(along * 900.0) * np.sin(across * 260.0)
    cc = BP._mix(np.tile(C['cloth'], (n, 1)), C['cloth_dark'], 0.25 + 0.25 * nb + 0.15 * weave)
    border = smoothstep(0.10, 0.07, edge) * smoothstep(0.02, 0.04, edge)
    cc = BP._mix(cc, C['cloth_band'], 0.85 * border)
    cc = BP._mix(cc, C['cloth_dark'], 0.5 * smoothstep(0.03, 0.0, edge))
    col = np.where(clo[:, None], cc, col)
    smooth = np.where(clo, 0.04, smooth)
    hgt = np.where(clo, 0.25 * weave + 0.3 * nf, hgt)
    # iron: dark, rust in patches
    iro = part == TACK_PART['iron']
    ic = BP._mix(np.tile(C['iron'], (n, 1)), C['rust'], 0.6 * smoothstep(0.1, 0.6, nb + 0.4 * nf))
    col = np.where(iro[:, None], ic, col)
    smooth = np.where(iro, 0.45 - 0.3 * smoothstep(0.1, 0.6, nb), smooth)
    # the bone mask: old yellowed bone, grime in the cracks and hollows, the goblins' red war paint
    bon = part == TACK_PART['bone']
    s, u = along, 2 * across - 1
    crack = smoothstep(0.06, 0.0, np.abs(vnoise(P * 55.0, seed=53))) * smoothstep(0.0, 0.4, nb + 0.3)
    bc = BP._mix(np.tile(C['bone'], (n, 1)), C['bone_dark'], 0.25 + 0.25 * nb)
    bc = BP._mix(bc, C['grime'], 0.45 * smoothstep(0.75, 0.35, ao) + 0.25 * smoothstep(0.85, 1.0, np.abs(u)))   # grime in
                                                                                  # the hollows, round the edge
    bc = BP._mix(bc, C['grime'], 0.75 * crack)
    stripes = (smoothstep(0.08, 0.03, np.abs(np.abs(u) - 0.45 - 0.35 * (s - 0.35))) *
               smoothstep(0.30, 0.36, s) * smoothstep(0.80, 0.70, s))               # two slanting streaks
    zig = smoothstep(0.05, 0.0, np.abs(u - 0.18 * np.sin(s * 40.0))) * smoothstep(0.50, 0.56, s) * smoothstep(0.95, 0.88, s)
    paint = np.clip(stripes + zig, 0, 1) * (0.75 + 0.25 * smoothstep(-0.2, 0.4, nf))       # chipped
    bc = BP._mix(bc, C['paint'], 0.9 * paint)
    col = np.where(bon[:, None], bc, col)
    smooth = np.where(bon, 0.30 - 0.15 * crack, smooth)
    hgt = np.where(bon, 0.35 * nf - 0.9 * crack, hgt)
    # hemp rope: twisted strands slanting round it, darker in the grooves
    rop = part == TACK_PART['rope']
    twist = 0.5 + 0.5 * np.sin((along * 55.0 + across * 3.0) * 2 * math.pi)
    rc = BP._mix(np.tile(C['rope'], (n, 1)), C['rope_dark'], 0.55 * (1 - twist) + 0.2 * nb)
    col = np.where(rop[:, None], rc, col)
    smooth = np.where(rop, 0.06, smooth)
    hgt = np.where(rop, 0.8 * twist + 0.2 * nf, hgt)
    # painted light, as the beasts'
    light = 0.80 + 0.30 * (N[:, 2] * 0.5 + 0.5)
    aot = 0.45 + 0.55 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None]
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    hh = np.zeros(H * Wd)
    hh[idx] = hgt
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd), hh.reshape(H, Wd)


def build_texture(ob, size=512):
    import beast_paint as BP
    D = BP.bake_data(ob, size=size, ao_dist=0.12)
    col, smooth, hgt = paint_tack(D)
    p_n, nrm = BP.write_normal_map(D, hgt, "T_WargTack_Normal", strength=3.0)
    p = BP.write_texture(D, col, smooth, "T_WargTack", ob, "M_WargTack", normal=nrm)
    return [p, p_n]


def build(body=None, rig=None, size=512):
    """Tack -> UVs -> texture -> the mask split off. -> (WargTack, WargMask, report)"""
    ob = build_tack(body, rig)
    unwrap(ob)
    tex = build_texture(ob, size)
    mask = split_mask(ob)
    return ob, mask, dict(tris_tack=tri_count(ob), tris_mask=tri_count(mask), textures=tex)
