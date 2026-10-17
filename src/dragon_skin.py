"""The dragon's real body (2026-10-17): after the blockout and the face, one skin from the snout to the tail tip.
Daniel's go-ahead: about 32k triangles for the whole dragon ("Go on").

Like the head, the body is a signed distance field of melted primitives, sampled on a grid at 2.5 cm (each
primitive evaluated only inside its own box), meshed with openvdb and decimated:
- the neck, trunk and tail: a chain of overlapping ellipsoids along the blockout's spine loft (BODY_ROWS), each
  hanging below the spine like the loft's cross-sections (thin over the spine, the chest deep);
- muscles melted on top: chest, shoulders, upper arms and forearms, haunches and calves, and the wings' root
  muscles on top of the shoulders (Daniel: the wings attach on the shoulders);
- the legs down to the toes and the wing arms out to the knuckles, as round cones per bone with knobs at the joints.
The head (dragon_head, 1 cm) and the body meet at a plane square to the neck, CUT_ARC down it from the poll (a plane
square to the head's axis sliced the curving neck obliquely, from the throat almost to the chest). Both fields hold
the neck's chain and the head near the seam, so the two meshes' cut loops lie on the same surface; they are zipped.

Shells on top: dorsal spikes from behind the crown to the tail tip and the claws, each seated where it leaves the
skin; the wing fingers (lofts: too thin for the grid); the head's spikes, teeth, eyes, frills and the horns. The
membranes are dragon_body's Coons patches.

Weights: Blender's heat map on the skin from the body bones; over the last 30 cm before the seam the head's own
weights (Head/Jaw, the masseter blend) fade into them; shells take the weights of the skin they sit on.
"""
import math
import numpy as np
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import dragon_body as DB
import dragon_head as DH
import beast_rig
from beast_common import spline, loft, cone, smoothstep, mesh_obj, get_coll, remove_obj
from ooze_body import smin, sd_capsule, sd_ellipsoid, sdf_mesh

VOXEL = 0.025
TARGET = 12500                   # the body's skin (the head's is dragon_head.TARGET_TRIS)
CUT_ARC = 0.45                   # the seam: this far down the neck's spine from the poll, square to it
K_JOIN = 0.06                    # how the head melts into the neck
BIG = 1.0
LO, HI = (-4.25, -3.45, -0.05), (4.25, 7.55, 5.25)
COLL = "DRG_Body"
UP, FWD = (0, 0, 1), (0, -1, 0)


# ----------------------------------------------------------------------------------------- primitives
def pad(k):
    """How far past its own extent a primitive is evaluated: beyond this it is too far to melt into anything."""
    return 1.5 * k + 2 * VOXEL


def ell(c, radii, axes=None, k=0.1):
    """An ellipsoid: centre, radii along the axes' columns (default world axes), melting width k."""
    c = np.asarray(c, float)
    R = np.eye(3) if axes is None else np.asarray(axes, float)
    r = np.asarray(radii, float)
    ext = np.abs(R) @ r
    return (lambda P: sd_ellipsoid((P - c) @ R, (0, 0, 0), r), c - ext, c + ext, k)


def rcone(a, b, ra, rb=None, k=0.06):
    """A round cone (capsule tapering from ra to rb) from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    rb = ra if rb is None else rb
    return (lambda P: sd_capsule(P, a, b, ra, rb), np.minimum(a - ra, b - rb), np.maximum(a + ra, b + rb), k)


def axes_along(d, up=UP):
    """Columns (side, along, up): `along` = d, `up` = the hint made perpendicular to it."""
    t = np.asarray(d, float)
    t = t / np.linalg.norm(t)
    u = np.asarray(up, float)
    n = u - (u @ t) * t
    n /= np.linalg.norm(n)
    return np.stack([np.cross(t, n), t, n], 1)


def _m(p, s):
    return np.array(DB._m(p, s), float)


# ----------------------------------------------------------------------------------------- the body's pieces
def spine_rows(per_seg=16):
    R = spline(DB.BODY_ROWS, per_seg)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(R[:, :3], axis=0), axis=1))])
    return R, s


def spine_chain():
    """Overlapping ellipsoids along the spine loft, poll to tail tip; each hangs below the spine like the loft's
    section (b above, c below), spaced a third of its size apart and melted over a third of it."""
    R, s = spine_rows()
    out, at = [], 0.0
    while at <= s[-1]:
        row = np.array([np.interp(at, s, R[:, j]) for j in range(6)])
        i = min(int(np.searchsorted(s, at)), len(R) - 1)
        ax = axes_along(R[min(i + 1, len(R) - 1), :3] - R[max(i - 1, 0), :3])
        a, b, c = row[3:] * 0.95                       # (melting adds a little volume back)
        h = (b + c) / 2
        centre = row[:3] - ax[:, 2] * (c - b) / 2
        m = min(a, h)
        out.append(ell(centre, (a, max(0.6 * m, 0.02), h), ax, k=max(0.3 * m, 0.008)))
        at += max(0.33 * m, 0.008)
    return out


def muscles(s):
    F, H, W = DB.FRONT, DB.HIND, DB.WING
    m = lambda p: _m(p, s)
    d = lambda a, b: m(b) - m(a)
    # no pectoral: the chest is the spine chain's own deep section. (A round ellipsoid read as a ball on the chest,
    # Daniel: "this bulge that I assume is muscle, but does not feel right"; a flat sheet stuck out like a shelf.)
    out = []
    sc = m(F["scap"]) + (m(F["sho"]) - m(F["scap"])) * 0.55
    out.append(ell(sc, (0.30, 0.52, 0.40), axes_along(d(F["scap"], F["sho"]), FWD), k=0.15))   # shoulder
    ua = (m(F["sho"]) + m(F["elb"])) / 2 + np.array((0, 0.05, 0))
    out.append(ell(ua, (0.27, 0.46, 0.30), axes_along(d(F["sho"], F["elb"]), FWD), k=0.14))     # upper arm
    fa = m(F["elb"]) + (m(F["wri"]) - m(F["elb"])) * 0.30
    out.append(ell(fa, (0.21, 0.32, 0.23), axes_along(d(F["elb"], F["wri"]), FWD), k=0.06))     # forearm
    hc = m((0.76, 1.00, 1.78))
    out.append(ell(hc, (0.44, 0.64, 0.56), axes_along(d(H["hip"], H["knee"]), FWD), k=0.18))    # haunch
    cf = m(H["knee"]) + (m(H["hock"]) - m(H["knee"])) * 0.35 + np.array((0, 0.06, 0))
    out.append(ell(cf, (0.20, 0.32, 0.22), axes_along(d(H["knee"], H["hock"]), FWD), k=0.06))   # calf
    wr = (m(W["root"]) + m(W["sho"])) / 2 + np.array((0, 0, 0.04))
    out.append(ell(wr, (0.30, 0.38, 0.26), axes_along(d(W["root"], W["sho"])), k=0.12))         # wing root
    wb = m(W["sho"]) + (m(W["elb"]) - m(W["sho"])) * 0.35
    out.append(ell(wb, (0.20, 0.50, 0.17), axes_along(d(W["sho"], W["elb"])), k=0.08))          # wing's biceps
    return out


def toes(s):
    """(base, knuckle, tip, radius, direction, bone) per toe: four forward on each foot, fanned, the knuckle raised."""
    out = []
    for paw, spread, L, r, bone in ((DB.FRONT["paw"], (-26, -9, 9, 26), 0.42, 0.075, "FrontToes"),
                                    (DB.HIND["paw"], (-24, -8, 8, 24), 0.46, 0.08, "HindToes")):
        for k, ang in enumerate(spread):
            a = math.radians(ang)
            dd = np.array((math.sin(a) * s, -math.cos(a), 0.0))
            base = _m(paw, s) + np.array((s * 0.05 * (k - 1.5), -0.06, -0.02))
            tip = base + dd * L
            tip[2] = r * 0.75
            knuckle = (base + tip) / 2 + np.array((0, 0, 0.045))
            out.append((base, knuckle, tip, r, dd, bone + ("L" if s > 0 else "R")))
    return out


def legs(s):
    F, H = DB.FRONT, DB.HIND
    m = lambda p: _m(p, s)
    out = [rcone(m(F["sho"]), m(F["elb"]), 0.27, 0.20, k=0.08), rcone(m(F["elb"]), m(F["wri"]), 0.20, 0.14, k=0.05),
           rcone(m(F["wri"]), m(F["paw"]), 0.14, 0.12, k=0.04),
           ell(m(F["elb"]) + np.array((0, 0.04, 0)), (0.16, 0.16, 0.16), k=0.06),
           ell(m(F["wri"]), (0.15, 0.15, 0.14), k=0.04),
           ell(m(F["paw"]) + np.array((0, -0.06, -0.02)), (0.18, 0.22, 0.09), k=0.05),
           rcone(m(H["hip"]), m(H["knee"]), 0.34, 0.19, k=0.10), rcone(m(H["knee"]), m(H["hock"]), 0.18, 0.13, k=0.05),
           rcone(m(H["hock"]), m(H["paw"]), 0.13, 0.11, k=0.04),
           ell(m(H["hock"]) + np.array((0, 0.05, 0)), (0.13, 0.14, 0.13), k=0.04),
           ell(m(H["paw"]) + np.array((0, -0.06, -0.02)), (0.19, 0.24, 0.09), k=0.05)]
    for base, knuckle, tip, r, dd, bone in toes(s):
        out += [rcone(base, knuckle, r, 0.9 * r, k=0.03), rcone(knuckle, tip, 0.9 * r, 0.65 * r, k=0.02)]
    return out


def wing_arm(s):
    W = DB.WING
    m = lambda p: _m(p, s)
    return [rcone(m(W["root"]), m(W["sho"]), 0.24, 0.23, k=0.12), rcone(m(W["sho"]), m(W["elb"]), 0.21, 0.14, k=0.06),
            rcone(m(W["elb"]), m(W["wri"]), 0.13, 0.10, k=0.04), rcone(m(W["wri"]), m(W["knu"]), 0.11, 0.10, k=0.03),
            rcone(m(W["wri"]), m(W["thumb"]), 0.075, 0.045, k=0.025),
            ell(m(W["elb"]), (0.15, 0.15, 0.15), k=0.04),
            ell((m(W["wri"]) + m(W["knu"])) / 2, (0.13, 0.12, 0.11), k=0.03)]


# ----------------------------------------------------------------------------------------- the fields
class Grid:
    """A distance grid filled primitive by primitive, each only inside its own box (plus its melting margin)."""

    def __init__(self, lo=LO, hi=HI, voxel=VOXEL):
        self.v = voxel
        self.i0 = np.floor(np.asarray(lo) / voxel).astype(int)
        self.i1 = np.ceil(np.asarray(hi) / voxel).astype(int)
        self.D = np.full(tuple(self.i1 - self.i0 + 1), BIG, np.float32)

    def union(self, prim):
        f, lo, hi, k = prim
        a = np.clip(np.floor((lo - pad(k)) / self.v).astype(int) - self.i0, 0, np.array(self.D.shape))
        b = np.clip(np.ceil((hi + pad(k)) / self.v).astype(int) - self.i0 + 1, 0, np.array(self.D.shape))
        if (b <= a).any():
            return
        sl = tuple(slice(x, y) for x, y in zip(a, b))
        idx = [np.arange(x, y) + i for x, y, i in zip(a, b, self.i0)]
        P = np.stack(np.meshgrid(*idx, indexing="ij"), -1).astype(np.float64) * self.v
        self.D[sl] = smin(self.D[sl].astype(np.float64), f(P), k).astype(np.float32)

    def mesh(self):
        D = self.D
        for ax in range(3):                          # close the grid's own faces
            sl = [slice(None)] * 3
            for end in (0, -1):
                sl[ax] = end
                D[tuple(sl)] = np.maximum(D[tuple(sl)], self.v)
        return sdf_mesh(D, self.i0, self.v)


def head_region():
    """The world box round the head's part behind the poll (where the head melts into the neck)."""
    corners = np.array([[x, y, z] for x in (-0.75, 0.75) for y in (0.05, 0.85) for z in (-0.85, 0.74)])
    W = DH.FRAME.hx(corners)
    return W.min(0), W.max(0)


def body_prims():
    prims = spine_chain()
    for s in (1, -1):
        prims += muscles(s) + legs(s) + wing_arm(s)
    lo, hi = head_region()
    prims.append((lambda P: DH.head_field(DH.FRAME.hx_inv(P)), lo, hi, K_JOIN))
    return prims


NECK = []


def neck_prims():
    """The chain's ellipsoids near the head, in the same order as in the body's grid."""
    poll = np.array(DB.HEAD[0], float)
    return [p for p in spine_chain() if np.linalg.norm((p[1] + p[2]) / 2 - poll) < 1.4]


def head_field_with_neck(Ph):
    """The head's field (head space) with the neck's chain melted in, as the body's grid has it near the seam."""
    d = DH.head_field(Ph)
    mask = Ph[..., 1] > -0.25
    if mask.any():
        Pw = DH.FRAME.hx(Ph[mask])
        neck = np.full(len(Pw), BIG)
        for f, lo, hi, k in NECK:
            inb = np.all((Pw >= lo - pad(k)) & (Pw <= hi + pad(k)), axis=1)
            if inb.any():
                neck[inb] = smin(neck[inb], f(Pw[inb]), k)
        d[mask] = smin(neck, d[mask], K_JOIN)
    return d


def _bm(V, F):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in V]
    for f in F:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def _dec_weight(P):
    """Keep more on the toes and legs, the wing arms and round the seam (its loop meets the head's finer one)."""
    seam = (np.abs(cut_side(P)) < 0.3) & (np.linalg.norm(P - np.array(_plane()[0][:]), axis=1) < 1.0)
    toe = P[:, 2] < 0.30
    leg = (P[:, 2] < 1.5) & (np.abs(P[:, 0]) > 0.35)
    wing = np.abs(P[:, 0]) > 1.0
    return np.where(seam, 0.6, np.where(toe, 0.35, np.where(leg, 0.6, np.where(wing, 0.8, 1.0))))


def _head_dec_weight(P):
    """The head's own map, keeping more toward the seam: its cut loop was 42 vertices against the body's 195, and
    the zip between them fanned into long slivers."""
    w = DH._dec_weight(P)
    return np.where(cut_side(DH.FRAME.hx(P)) > -0.30, np.minimum(w, 0.3), w)


def build_body_mesh(target=TARGET):
    g = Grid()
    for p in body_prims():
        g.union(p)
    V, F = g.mesh()
    bm = _bm(V, F)
    for _ in range(2):
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.3, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    return DH._decimate(bm, target, _dec_weight)


# ----------------------------------------------------------------------------------------- the seam
def _plane():
    """The seam's plane: through the neck's spine CUT_ARC from the poll, square to it, its normal toward the body."""
    R, s = spine_rows()
    i = int(np.searchsorted(s, CUT_ARC))
    co = np.array([np.interp(CUT_ARC, s, R[:, j]) for j in range(3)])
    T = R[min(i + 1, len(R) - 1), :3] - R[max(i - 1, 0), :3]
    return Vector(co), Vector(T / np.linalg.norm(T))


def cut_side(P):
    """Signed distance of world points from the seam's plane (negative: the head's side)."""
    co, no = _plane()
    return (np.asarray(P, float) - np.array(co[:])) @ np.array(no[:])


def _cut(bm, keep_back):
    co, no = _plane()
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=co, plane_no=no,
                           clear_inner=keep_back, clear_outer=not keep_back)
    bm.verts.index_update()


def _loops(bm):
    """The boundary loops (vertex lists), longest first."""
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in bnd:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    seen, loops = set(), []
    for e0 in bnd:
        if e0 in seen:
            continue
        loop, v, e = [e0.verts[0]], e0.verts[1], e0
        seen.add(e0)
        while v is not loop[0]:
            loop.append(v)
            nxt = [x for x in adj[v] if x is not e and x not in seen]
            if not nxt:
                break
            e = nxt[0]
            seen.add(e)
            v = e.other_vert(v)
        loops.append(loop)
    return sorted(loops, key=len, reverse=True)


def zipper(bm, A, B, no):
    """Faces between two closed loops of vertices lying on one plane (normal no): both run the same way round,
    start at the closest pair, and each step advances the loop whose new edge is shorter."""
    def area(L):
        P = np.array([v.co[:] for v in L])
        c = P.mean(0)
        return sum(np.dot(np.cross(P[i] - c, P[(i + 1) % len(P)] - c), no) for i in range(len(P)))
    if area(A) < 0:
        A = A[::-1]
    if area(B) < 0:
        B = B[::-1]
    j0 = int(np.argmin([(v.co - A[0].co).length for v in B]))
    B = B[j0:] + B[:j0]
    nA, nB = len(A), len(B)
    i = j = 0
    made = 0
    while i < nA or j < nB:
        a0, b0 = A[i % nA], B[j % nB]
        a1, b1 = A[(i + 1) % nA], B[(j + 1) % nB]
        if j >= nB or (i < nA and (a1.co - b0.co).length <= (a0.co - b1.co).length):
            f = (a0, a1, b0)
            i += 1
        else:
            f = (a0, b1, b0)
            j += 1
        try:
            bm.faces.new(f)
            made += 1
        except ValueError:
            pass
    return made


# ----------------------------------------------------------------------------------------- colours
def body_colors(P, rgb):
    """Rust back, golden belly plates along the trunk's, neck's and tail's undersides (not down the legs)."""
    R, s = spine_rows(6)
    C = R[:, :3]
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.array(UP) - (T @ np.array(UP))[:, None] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    S = np.cross(T, N)
    idx = np.empty(len(P), int)
    for k in range(0, len(P), 4000):
        idx[k:k + 4000] = np.argmin(((P[k:k + 4000, None, :] - C[None]) ** 2).sum(-1), axis=1)
    d = P - C[idx]
    u, v = (d * S[idx]).sum(1), (d * N[idx]).sum(1)
    a, b, c = R[idx, 3], R[idx, 4], R[idx, 5]
    e = np.sqrt((u / a) ** 2 + (v / np.where(v > 0, b, c)) ** 2)
    ventral = -v / np.maximum(np.linalg.norm(d, axis=1), 1e-6)
    # how far out from the section the gold may reach: wide at the throat (the jowls widen it), tight along the
    # trunk so it stops at the legs (the hind knee lit up as a gold ball behind the front leg)
    lim = np.interp(s[idx], (0.0, 1.8, 2.6, s[-1]), (1.8, 1.8, 1.2, 1.3))
    k = smoothstep(0.45, 0.80, ventral) * smoothstep(lim, lim - 0.3, e)
    back, belly = np.array(rgb(DB.COL["back"])), np.array(rgb(DB.COL["belly"]))
    return [tuple(back * (1 - x) + belly * x) for x in k]


# ----------------------------------------------------------------------------------------- weights
def _exclude(n):
    return n in ("Root", "Motion", "Jaw") or n.startswith("Socket_") or (n.startswith("WingF") and n[5].isdigit())


def heat(ob, rig):
    """Blender's automatic (bone heat) weights from the body bones."""
    ad = rig.data
    keep = {b.name: b.use_deform for b in ad.bones}
    for b in ad.bones:
        b.use_deform = keep[b.name] and not _exclude(b.name)
    ob.vertex_groups.clear()
    for md in [md for md in ob.modifiers if md.type == 'ARMATURE']:
        ob.modifiers.remove(md)
    ob.parent = None
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for nm, dfm in keep.items():
        ad.bones[nm].use_deform = dfm


def _read(ob):
    names = [g.name for g in ob.vertex_groups]
    W = np.zeros((len(ob.data.vertices), len(names)))
    for v in ob.data.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    return names, W


def _write(ob, names, W, rows):
    for n in names:
        if ob.vertex_groups.get(n) is None:
            ob.vertex_groups.new(name=n)
    groups = {n: ob.vertex_groups[n] for n in names}
    for gi, n in enumerate(names):
        g = groups[n]
        g.remove([int(i) for i in rows])
        for i in rows:
            if W[i, gi] > 1e-4:
                g.add([int(i)], float(W[i, gi]), 'REPLACE')


def skin_weights(ob, rig, n_head):
    """Heat weights everywhere, then the head's own weights fading into them over the 30 cm before the seam; any
    vertex the heat solve left empty takes the nearest bones' weights."""
    heat(ob, rig)
    names, W = _read(ob)
    for n in ("Head", "Jaw"):
        if n not in names:
            names.append(n)
            W = np.hstack([W, np.zeros((len(W), 1))])
    co = np.array([v.co[:] for v in ob.data.vertices])
    empty = np.nonzero(W.sum(1) < 1e-4)[0]
    if len(empty):
        B = DB.rest_bones()
        bones = DB._bones_of(B, [b.name for b in rig.data.bones if b.use_deform and not _exclude(b.name)])
        for i, w in zip(empty, DB.chain_weights(co[empty], bones, falloff=0.15)):
            for n, x in w.items():
                if n not in names:
                    names.append(n)
                    W = np.hstack([W, np.zeros((len(W), 1))])
                W[i, names.index(n)] = x
    rows = np.arange(n_head)
    Ph = DH.FRAME.hx_inv(co[rows])
    r = smoothstep(0.0, -0.30, cut_side(co[rows]))
    Hw = np.zeros((len(rows), len(names)))
    for i, w in enumerate(DH.head_weights(Ph)):
        for n, x in w.items():
            Hw[i, names.index(n)] = x
    W[rows] = r[:, None] * Hw + (1 - r[:, None]) * W[rows]
    W /= np.maximum(W.sum(1), 1e-9)[:, None]
    _write(ob, names, W, np.arange(len(W)))
    body_rows = np.arange(n_head, len(W))
    beast_rig.smooth_weights(ob, body_rows, iterations=2, factor=0.5)
    beast_rig.clean_weights(ob)
    return {"empty_after_heat": int(len(empty))}


# ----------------------------------------------------------------------------------------- shells
def _skin_lookup(ob):
    """-> (kd tree over the skin's vertices, per-vertex weight dicts, BVH of the skin)"""
    me = ob.data
    kd = KDTree(len(me.vertices))
    for v in me.vertices:
        kd.insert(v.co, v.index)
    kd.balance()
    gn = {g.index: g.name for g in ob.vertex_groups}
    Wd = [{gn[g.group]: g.weight for g in v.groups} for v in me.vertices]
    bm = bmesh.new()
    bm.from_mesh(me)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return kd, Wd, bvh


def _seat(bvh, a, b, r):
    """Where a spike from a to b leaves the skin (ray from the tip back along it), sunk in by most of its radius."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    hit = bvh.ray_cast(Vector(b), Vector(-u), float(np.linalg.norm(b - a)) * 1.6)[0]
    seat = np.array(hit) if hit is not None else a
    return seat, seat - u * r * 0.8


def dorsal_spikes():
    """(base, tip, radius) along the back from behind the crown to the tail tip, tallest over the shoulders."""
    R, s = spine_rows(16)
    out = []
    for at in np.arange(0.62, s[-1] - 0.3, 0.34):
        i = int(np.searchsorted(s, at))
        p, row = R[i, :3], R[i]
        T = R[min(i + 1, len(R) - 1), :3] - R[max(i - 1, 0), :3]
        T /= np.linalg.norm(T)
        N = np.array(UP) - np.dot(UP, T) * T
        N /= np.linalg.norm(N)
        f = at / s[-1]
        h = float(np.interp(f, (0.0, 0.18, 0.27, 0.42, 0.55, 1.0), (0.16, 0.26, 0.40, 0.30, 0.28, 0.07)))
        base = p + N * row[4] * 0.85
        tip = base + (N * 0.85 + T * 0.55) / np.linalg.norm(N * 0.85 + T * 0.55) * h
        out.append((base, tip, h * 0.30))
    return out


def build_shells(acc, ob, rgb, head_bvh):
    """Into an Acc (body space): the head's shells, the horns, dorsal spikes, claws, the wing fingers."""
    rep = DH.head_shells(acc, rgb, head_bvh)
    kd, Wd, bvh = _skin_lookup(ob)
    horn, claw, back = rgb(DB.COL["horn"]), rgb(DB.COL["claw"]), rgb(DB.COL["back"])

    def at_skin(p):
        return Wd[kd.find(Vector(p))[1]]

    for s_, sfx in DB.SIDES:                                   # the horns (Daniel loves them: unchanged)
        m = lambda p: DB._m(p, s_)
        acc.add(lambda bm: DB._tube(bm, [(*m(DB.hk(p)), p[3] * DB.HEAD_K) for p in DB.HORN], seg=12), "Head", horn)
    n = 0
    for base, tip, r in dorsal_spikes():
        seat, b0 = _seat(bvh, base, tip, r)
        w = at_skin(seat)
        acc.add(lambda bm: cone(bm, b0, tip, r, seg=5), lambda P, w=w: [w] * len(P), horn)
        n += 1
    for s_, sfx in DB.SIDES:
        for base, knuckle, tip, r, dd, bone in toes(s_):           # claws, hooked down at the toe tips
            a = tip - dd * 0.02
            b = tip + dd * 0.20 + np.array((0, 0, -0.03))
            seat, b0 = _seat(bvh, a, b, r * 0.6)
            acc.add(lambda bm: cone(bm, b0, b, r * 0.6, seg=6, bend=(0, 0, -0.06)), bone, claw)
            n += 1
        W = DB.WING
        th0, th1 = _m(W["wri"], s_), _m(W["thumb"], s_)
        dd = (th1 - th0) / np.linalg.norm(th1 - th0)
        b = th1 + dd * 0.24
        seat, b0 = _seat(bvh, th1 - dd * 0.02, b, 0.05)
        acc.add(lambda bm: cone(bm, b0, b, 0.05, seg=6, bend=(0, 0, -0.07)), f"WingThumb{sfx}", claw)
        n += 1
        B = DB.rest_bones()
        for i in range(4):                                      # the wing fingers: tapering tubes, knuckle bumps
            P = np.array([DB._m(p, s_) for p in DB.finger_pts(i)])
            dd = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])
            P = np.vstack([P[:1] - dd * 0.08, P])
            rr = np.linspace(0.068, 0.022, len(P))
            rows = [(*p, r_, r_, r_) for p, r_ in zip(P, rr)]
            bones = DB._bones_of(B, [f"WingHand{sfx}"] + [f"WingF{i + 1}_{k + 1}{sfx}" for k in range(DB.FINGER_SEGS[i])])
            acc.add(lambda bm: loft(bm, rows, up=UP, seg=8, per_seg=3, cap0=0.5, cap1=0.6),
                    lambda Q, bones=bones: DB.chain_weights(Q, bones, falloff=0.08), back)
    rep["body_shells"] = n
    return rep


# ----------------------------------------------------------------------------------------- assembly
def build(rig):
    """The real body: skin (head + body, one mesh), shells joined onto it, membranes. -> (objects, report)"""
    global NECK
    rep = {}
    NECK = neck_prims()
    rgb = DB._rgb
    head, _, _, head_bvh, rep["head"] = DH.head_skin(rgb, field=head_field_with_neck, dec_weight=_head_dec_weight)
    body, rep["body_dense_tris"] = build_body_mesh()
    for v in head.verts:                                         # into body space
        v.co = Vector(DH.FRAME.hx(np.array(v.co[:])))
    _cut(head, keep_back=False)
    _cut(body, keep_back=True)
    la, lb = _loops(head), _loops(body)
    rep["loops"] = (len(la), len(lb), len(la[0]), len(lb[0]))

    skin = bmesh.new()
    vmap = {}
    for src in (head, body):
        for v in src.verts:
            vmap[v] = skin.verts.new(v.co)
        for f in src.faces:
            try:
                skin.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                pass
    n_head = len(head.verts)
    co, no = _plane()
    rep["seam_faces"] = zipper(skin, [vmap[v] for v in la[0]], [vmap[v] for v in lb[0]], np.array(no[:]))
    head.free()
    body.free()
    bmesh.ops.recalc_face_normals(skin, faces=skin.faces[:])
    skin.normal_update()
    P = np.array([v.co[:] for v in skin.verts])
    N = np.array([v.normal[:] for v in skin.verts])
    Ph = DH.FRAME.hx_inv(P[:n_head])
    Nh = DH.FRAME.hx_inv(P[:n_head] + N[:n_head]) - Ph
    hc = np.array(DH.head_colors(Ph, Nh, rgb))                 # the head's colours fade into the body's before
    bc = np.array(body_colors(P[:n_head], rgb))                 # the seam (each had its own gold rule)
    r = smoothstep(-0.55, 0.0, cut_side(P[:n_head]))[:, None]
    cols = [tuple(c) for c in hc * (1 - r) + bc * r] + body_colors(P[n_head:], rgb)

    coll = get_coll(COLL)
    mat = DB.blockout_material()
    remove_obj("DragonBody")
    ob = mesh_obj("DragonBody", skin, coll)
    me = ob.data
    att = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    att.data.foreach_set('color', [c for col in cols for c in (*col, 1.0)])
    me.materials.clear()
    me.materials.append(mat)
    me.shade_smooth()
    rep["skin_tris"] = sum(len(p.vertices) - 2 for p in me.polygons)
    rep["weights"] = skin_weights(ob, rig, n_head)

    acc = DB.Acc()
    rep["shells"] = build_shells(acc, ob, rgb, head_bvh)
    remove_obj("DRG_Shells")
    shells = acc.finish("DRG_Shells", coll, mat)
    rep["shell_tris"] = sum(len(p.vertices) - 2 for p in shells.data.polygons)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    shells.select_set(True)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.join()
    rep["body"] = beast_rig.weight_report(ob)

    mem = DB.Acc()
    B = DB.rest_bones()
    for s_, sfx in DB.SIDES:
        DB.build_membranes(mem, B, s_, sfx)
    mem.C = [c if c is not None else DB._rgb(DB.COL["membrane"]) for c in mem.C]
    remove_obj("DragonWingMembrane")
    ob_mem = mem.finish("DragonWingMembrane", coll, mat)
    rep["membrane"] = beast_rig.bind(ob_mem, rig)
    rep["tris"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (ob, ob_mem)}
    lc = bpy.context.view_layer.layer_collection.children.get(DB.COLL)    # the blockout steps aside
    if lc is not None:
        lc.exclude = True
    return (ob, ob_mem), rep
