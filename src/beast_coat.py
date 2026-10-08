"""The shaggy coats (moved out of rhino_body.py, 2026-10-07): hair as separate low-poly shells on a fused body.

A coat's volumes (a cape, a skirt...) are lofts fused into the body like any other part. The hair on them is shells:
  - fringes: thick curtains along a volume's edge, folded into ridges and valleys like strands, the hem a zig-zag of
    uneven points (`fringe`); loops round a volume or a leg (`loop_anchors`), snapped to that loft alone (`Snap`), or
    strips dropped onto the body from above (`Drop`);
  - clumps: single curved blades for beards, breeches, tail tufts (`clump`, `build_clumps`).
Every hair vertex stores where its root is (the 'root' point attribute; create the layer before the bmesh has any
vertex) so the rig can skin it like the skin there (beast_rig.skin_hair_from_roots), and `write_hair_t` puts how far
along each vertex is (root 0 .. tip 1) in info.b for the painter.
"""
import bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from beast_common import loft


def coat_loft(v):
    """-> loft() arguments for a coat volume (bm goes first)."""
    return ([(0, y, z, a, b, c) for y, z, a, b, c in v['rows']], (0, 0, 1), 28, 4, v['cap0'], v['cap1'], 3,
            v['shape'])


def volume_bvh(v):
    bm = bmesh.new()
    loft(bm, *coat_loft(v))
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


class Snap:
    """find_nearest on one coat volume (no jumping between the mantle, trunk and legs), normals from it too."""
    def __init__(self, bvh):
        self.bvh = bvh

    def find_nearest(self, a):
        return self.bvh.find_nearest(a)


class Drop:
    """Anchors dropped straight down onto the body: the first surface under (x, y)."""
    def __init__(self, bvh):
        self.bvh = bvh

    def find_nearest(self, a):
        hit = self.bvh.ray_cast(Vector((a.x, a.y, 3.0)), Vector((0, 0, -1)), 4.0)
        return hit if hit[0] is not None else self.bvh.find_nearest(a)


def loft_bvh(args):
    bm = bmesh.new()
    loft(bm, *args)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


def clump(bm, base, dv, n, L, r, flat=0.35, seam_layer=None):
    """One clump: a curved blade from `base` along dv, sagging under its weight. Section: a flattened diamond (wide
    along the skin, thin outward, flatter underneath). Two inner rings when long, one when short. UV cut along the
    underside and round the base. Returns its BMVerts."""
    g = Vector((0, 0, -1))
    side = dv.cross(n)
    if side.length < 1e-4:
        side = dv.orthogonal()
    side.normalize()
    out = side.cross(dv).normalized()
    if out.dot(n) < 0:
        out = -out
    ts, ks = ((0.0, 0.42, 0.78), (1.0, 0.86, 0.55)) if L > 0.27 else ((0.0, 0.55), (1.0, 0.75))
    pos = lambda t: base + dv * (L * t) + g * (0.28 * L * t * t) + out * (0.06 * L * t * t)
    rings = []
    for t, k in zip(ts, ks):
        c = pos(t)
        w, h = r * k, r * k * flat
        rings.append([bm.verts.new(c + side * w), bm.verts.new(c + out * h), bm.verts.new(c - side * w),
                      bm.verts.new(c - out * h * 0.5)])
    apex = bm.verts.new(pos(1.0))
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(4):
            bm.faces.new((a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]))
    for j in range(4):
        bm.faces.new((rings[-1][j], rings[-1][(j + 1) % 4], apex))
    bm.faces.new(list(reversed(rings[0])))
    line = [r_[3] for r_ in rings] + [apex]                     # UV cut: along the underside, and round the base
    for p, q in zip(line[:-1], line[1:]):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    for j in range(4):
        e = bm.edges.get((rings[0][j], rings[0][(j + 1) % 4]))
        if e is not None:
            e.seam = True
    vs = [v for r_ in rings for v in r_] + [apex]
    if seam_layer is not None:
        for v in vs:
            v[seam_layer] = base
    return vs


def build_clumps(bm, bvh, locks):
    """The coat's clumps on the fused body (bvh): each rooted under the nearest surface to its anchor. The root
    position goes in the 'root' point attribute (the rig skins each clump like the skin there); the layer must
    exist before the bmesh has any vertex."""
    root = bm.verts.layers.float_vector["root"]
    vs = []
    for lk in locks:
        anchor, d, L, r = lk[:4]
        lift = lk[4] if len(lk) > 4 else 0.3
        sides = (1,) if abs(anchor[0]) < 1e-6 else (1, -1)
        for s in sides:
            p, n, _, _ = bvh.find_nearest(Vector((s * anchor[0], anchor[1], anchor[2])))
            if p is None:
                continue
            dv = Vector((s * d[0], d[1], d[2])).normalized()
            dv = dv - n * dv.dot(n)                              # along the skin, then leaning out by its lift
            dv = (dv.normalized() + lift * n).normalized()
            vs += clump(bm, p - n * r * 0.30, dv, n, L, r, seam_layer=root)
    return vs


def loop_anchors(spec, step, reach=0.3):
    """Anchor points round a loop, evenly spaced by arc length: an ellipse (centre x, y, half length, half width) a
    little outside the coat, its height blending from the sides to the front and back; `gap` degrees round the
    front are left open. -> (anchors, outward directions, closed)."""
    cx, cy, b, a, zs, zf, zb, gap = spec
    th = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    P = np.stack([(a + reach) * np.cos(th), cy + (b + reach) * np.sin(th)], -1)
    seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
    s = np.concatenate([[0], np.cumsum(seg)[:-1]])
    n = max(8, int(round(s[-1] / step)) // 2 * 2)
    u = np.linspace(0, s[-1] + seg[-1], n, endpoint=False)
    u = u + np.random.default_rng(int(n)).uniform(-0.3, 0.3, n) * step     # uneven spacing
    idx = np.searchsorted(s, np.mod(u, s[-1] + seg[-1]))
    t = np.sort(th[np.clip(idx, 0, len(th) - 1)])
    if gap > 0:                                         # open at the front (toward -y, theta = -90 deg)
        dfront = np.abs((t + np.pi / 2 + np.pi) % (2 * np.pi) - np.pi)
        t = t[dfront > np.radians(gap)]
        t = np.roll(t, -int(np.argmax(np.diff(t))) - 1)  # start just after the gap
    fb = np.sin(t)                                      # -1 front (toward -y), +1 back
    z = zs + (zf - zs) * np.clip(-fb, 0, 1) ** 2 + (zb - zs) * np.clip(fb, 0, 1) ** 2
    z = z + (0.035 * np.sin(3.0 * t + 0.7) + 0.02 * np.sin(7.0 * t)) * min(1.0, a / 0.4)   # the hem undulates
    A = [Vector((float(cx + (a + reach) * np.cos(q)), float(cy + (b + reach) * np.sin(q)), float(zz)))
         for q, zz in zip(t, z)]
    out = [Vector((float(np.cos(q) / a), float(np.sin(q) / b), 0.0)).normalized() for q in t]
    return A, out, gap == 0


def fringe(bm, bvh, anchors, closed, d, longs, shorts, thick, lift, rng, root_layer, outs=None):
    """A curtain rooted along the anchors (snapped to the surface): samples alternate tooth centres (long, ridged
    outward) and gaps (short, a valley). Four vertices per sample: outer root, outer middle, tip, inner root.
    UV cut along the inner root line, and across the strip every 16 samples. Returns its BMVerts."""
    g = Vector((0, 0, -1))
    hits = [bvh.find_nearest(a) for a in anchors]
    P = [h[0] for h in hits]
    Nn = [h[1] for h in hits]
    M = len(P)
    cols = []
    for k in range(M):
        p, n = P[k], Nn[k]
        a_, b_ = (P[(k + 1) % M], P[k - 1]) if closed else (P[min(k + 1, M - 1)], P[max(k - 1, 0)])
        t = (a_ - b_).normalized()
        D = Vector(d) if outs is None else outs[k] * d + Vector((0, 0, -1))   # loops: outward from their centre
        D = D - n * D.dot(n)
        D = (D.normalized() + lift * n)
        D = (D - t * D.dot(t)).normalized()
        W = t.cross(D).normalized()
        if W.dot(n) < 0 or (abs(W.dot(n)) < 0.2 and W.x < 0):
            W = -W
        centre = k % 2 == 0
        if centre:                                       # mostly middling, now and then a long lock
            L = longs[0] + (longs[1] - longs[0]) * rng.beta(1.4, 2.2) + (0.10 if rng.random() < 0.12 else 0.0)
        else:
            L = rng.uniform(*shorts)
        if not closed:                                   # strips taper at their ends
            L *= 0.55 + 0.45 * min(1.0, k / 2.0, (M - 1 - k) / 2.0)
        ridge = 0.45 * thick if centre else -0.30 * thick
        root = p - n * 0.03
        ro = bm.verts.new(root + W * thick * 0.5)
        mo = bm.verts.new(p + D * L * 0.5 + W * (thick * 0.5 + ridge) + g * 0.03 * L)
        tip = bm.verts.new(p + D * L + g * 0.08 * L + W * 0.2 * thick + t * rng.uniform(-0.25, 0.25) * L * centre)
        ri = bm.verts.new(root - W * thick * 0.5)
        col = [ro, mo, tip, ri]
        for v in col:
            v[root_layer] = p
        cols.append(col)
    pairs = [(k, (k + 1) % M) for k in range(M if closed else M - 1)]
    for i, j in pairs:
        A, B = cols[i], cols[j]
        for q in range(4):
            bm.faces.new((A[q], B[q], B[(q + 1) % 4], A[(q + 1) % 4]))
    if not closed:
        bm.faces.new(cols[0])
        bm.faces.new(list(reversed(cols[-1])))
    for i, j in pairs:                                   # UV cut: the inner root line ...
        e = bm.edges.get((cols[i][3], cols[j][3]))
        if e is not None:
            e.seam = True
    cuts = [cols[k] for k in range(0, M, 16)]            # ... and across it every 8 teeth, so it packs
    if not closed:
        cuts.append(cols[-1])
    for q in range(4):
        for c in cuts:
            e = bm.edges.get((c[q], c[(q + 1) % 4]))
            if e is not None:
                e.seam = True
    return [v for c in cols for v in c]


def write_hair_t(body, hair_part, reach=0.36):
    """info.b on the clumps and fringes: how far along from the root (0) to the tip (1), for the painter."""
    me = body.data
    att = me.color_attributes["info"]
    rgba = np.empty(len(me.vertices) * 4, np.float32)
    att.data.foreach_get('color', rgba)
    rgba = rgba.reshape(-1, 4)
    root = np.zeros(len(me.vertices) * 3, np.float32)
    me.attributes["root"].data.foreach_get('vector', root)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    hair = np.rint(rgba[:, 0] * 255).astype(int) == hair_part
    d = np.linalg.norm(co.reshape(-1, 3) - root.reshape(-1, 3), axis=1)
    rgba[:, 2] = np.where(hair, np.clip(d / reach, 0, 1), 0.0)
    att.data.foreach_set('color', rgba.ravel())
