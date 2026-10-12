"""The ooze's shell: one signed distance field (main mass, spreading skirt, pseudopods, trailing uroid) meshed with
openvdb, flattened onto the floor, decimated to the game budget.

The shape is an amoeba's: a lumpy dome that spreads into a thin skirt where it touches the floor, blunt lobose
pseudopods (round tubes ending in a slightly swollen tip, the hyaline cap), and a wrinkled knot at the rear (the
uroid, where a crawling amoeba's tail end bunches up). Coordinates as everywhere: metres, Z up, facing -Y, left +X.

POD lists the pseudopods by their control points (x, y, z, radius); the same points become the rig's bone chains
(3 bones per pod), so the pods can be extended, curled and retracted in clips.
"""
import math
import numpy as np
import bpy, bmesh

from beast_common import spline, fbm, mesh_obj, smoothstep

# ------------------------------------------------------------------ distance fields (numpy) -> mesh (openvdb)
# (from Humans/src/hum_skeleton.py)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def sd_capsule(P, a, b, ra, rb=None):
    """A capsule (a round cone when rb differs) from a to b."""
    rb = ra if rb is None else rb
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1) - (ra + (rb - ra) * t)


def sd_ellipsoid(P, c, radii):
    """Axis-aligned ellipsoid (iq's bound)."""
    q = P - np.asarray(c, float)
    r = np.asarray(radii, float)
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sdf_mesh(D, i0, voxel, adapt=0.0):
    """Mesh the zero set of the sampled distances D (grid origin index i0) with openvdb's polygoniser.
    Returns (V, faces) wound outward."""
    import openvdb
    g = openvdb.FloatGrid(float(voxel * 3))
    g.copyFromArray(np.asarray(D, np.float32), ijk=tuple(int(v) for v in i0), tolerance=0.0)
    g.transform = openvdb.createLinearTransform(voxelSize=voxel)
    pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=adapt)
    V = np.asarray(pts, float)
    F = [tuple(int(i) for i in t) for t in tris] + [tuple(int(i) for i in q) for q in quads]
    return V, F


# ------------------------------------------------------------------ the shape

# main mass: (centre, radii) ellipsoids, smooth-unioned with k
MASS = [
    ((0.00, 0.05, 0.28), (0.92, 0.86, 0.80)),      # the dome, top at ~1.08
    ((-0.25, 0.25, 0.55), (0.52, 0.50, 0.48)),     # a hump at the rear right, so the top isn't a bowl
    ((0.35, -0.25, 0.42), (0.45, 0.42, 0.40)),     # the front-left shoulder the reaching pod grows from
]
MASS_K = 0.25
SKIRT = ((0.0, 0.05, 0.0), (1.05, 0.98, 0.22))     # where it spreads on the floor
SKIRT_K = 0.30

# pseudopods: name -> control points (x, y, z, r), blend k, z squash (floor pods are flatter than round)
POD = {
    "Reach": dict(pts=[(0.30, -0.40, 0.60, 0.36), (0.42, -0.88, 0.76, 0.28), (0.50, -1.22, 0.70, 0.22),
                       (0.53, -1.40, 0.55, 0.22)], k=0.30, flat=1.0),          # front left, raised: the grab
    "Lead":  dict(pts=[(-0.35, -0.55, 0.16, 0.36), (-0.52, -1.00, 0.13, 0.31), (-0.62, -1.32, 0.11, 0.27),
                       (-0.66, -1.48, 0.10, 0.26)], k=0.34, flat=1.45),        # front right, flowing on the floor
    "Side":  dict(pts=[(-0.62, 0.05, 0.46, 0.33), (-1.00, 0.00, 0.55, 0.25), (-1.26, 0.07, 0.45, 0.19),
                       (-1.36, 0.18, 0.30, 0.19)], k=0.28, flat=1.0),          # right, raised and curling down
    "Back":  dict(pts=[(0.55, 0.45, 0.15, 0.32), (0.92, 0.70, 0.12, 0.26), (1.14, 0.86, 0.10, 0.22),
                       (1.25, 0.95, 0.09, 0.21)], k=0.34, flat=1.4),           # left rear, on the floor
    "Bud":   dict(pts=[(0.75, -0.05, 0.18, 0.26), (0.92, -0.10, 0.16, 0.23), (1.02, -0.13, 0.14, 0.21),
                       (1.08, -0.15, 0.13, 0.20)], k=0.30, flat=1.3),          # left: a young pod budding
    "Probe": dict(pts=[(-0.10, 0.10, 0.80, 0.32), (-0.13, -0.02, 1.08, 0.25), (-0.18, -0.18, 1.20, 0.20),
                       (-0.22, -0.30, 1.18, 0.20)], k=0.26, flat=1.0),         # a lobe rising off the top, leaning forward
}
UROID = [((0.00, 0.86, 0.14), 0.17), ((-0.16, 0.96, 0.10), 0.12), ((0.13, 1.01, 0.08), 0.10),
         ((-0.02, 1.08, 0.06), 0.08)]
UROID_K = (0.06, 0.16)                              # among the knots, onto the body

NOISE = dict(amp=0.042, freq=1.9, octaves=3, seed=7)
FOOT = (0.035, 0.10)           # the wall below 10 cm: no undercut, leaning out 3.5 cm at the floor (~70 deg)
FLOOR = 0.0


def _pod_field(P, pod, per_seg=5):
    """Distance to one pod: round cones along a Catmull-Rom spline through its control points."""
    c = spline(pod["pts"], per_seg)
    Q = P
    if pod["flat"] != 1.0:
        Q = P.copy()
        Q[..., 2] = (Q[..., 2] - FLOOR) * pod["flat"] + FLOOR
        c = c.copy()
        c[:, 2] = (c[:, 2] - FLOOR) * pod["flat"] + FLOOR
    d = None
    for a, b in zip(c[:-1], c[1:]):
        s = sd_capsule(Q, a[:3], b[:3], a[3], b[3])
        d = s if d is None else np.minimum(d, s)
    return d


def _bbox(pts, margin):
    p = np.asarray(pts, float)
    r = p[:, 3].max() if p.shape[1] > 3 else 0.0
    return p[:, :3].min(0) - r - margin, p[:, :3].max(0) + r + margin


def field(P, noise=True, floor=True):
    """Signed distance of the ooze at points P (..., 3)."""
    Z = P[..., 2]
    P = P.copy()
    P[..., 2] = np.maximum(Z, FLOOR + FOOT[1])       # below FOOT[1]: the cross-section there, carried down
    d = None
    for c, r in MASS:
        s = sd_ellipsoid(P, c, r)
        d = s if d is None else smin(d, s, MASS_K)
    d = smin(d, sd_ellipsoid(P, *SKIRT), SKIRT_K)
    for name, pod in POD.items():
        lo, hi = _bbox(pod["pts"], pod["k"] + 0.08)
        m = np.all((P >= lo) & (P <= hi), axis=-1)
        if not m.any():
            continue
        s = np.full(P.shape[:-1], 10.0)
        s[m] = _pod_field(P[m], pod)
        d = smin(d, s, pod["k"])
    u = None
    for c, r in UROID:
        s = np.linalg.norm(P - np.asarray(c), axis=-1) - r
        u = s if u is None else smin(u, s, UROID_K[0])
    d = smin(d, u, UROID_K[1])
    d = d - FOOT[0] * np.clip(FLOOR + FOOT[1] - Z, 0, None) / FOOT[1]       # ...leaning out toward the floor
    if noise:
        d = d + NOISE["amp"] * fbm(P * NOISE["freq"], NOISE["octaves"], NOISE["seed"])
    return np.maximum(d, FLOOR - Z) if floor else d          # the floor: a flat sole (cut away later)


def parts(P):
    """Distances to the shape's pieces at P (N, 3), no noise: {"mass": dome + skirt + uroid, pod name: pod}.
    For charting UVs and skin weights."""
    d = None
    for c, r in MASS:
        s = sd_ellipsoid(P, c, r)
        d = s if d is None else smin(d, s, MASS_K)
    d = smin(d, sd_ellipsoid(P, *SKIRT), SKIRT_K)
    u = None
    for c, r in UROID:
        s = np.linalg.norm(P - np.asarray(c), axis=-1) - r
        u = s if u is None else smin(u, s, UROID_K[0])
    out = {"mass": smin(d, u, UROID_K[1])}
    for name, pod in POD.items():
        out[name] = _pod_field(P, pod)
    return out


def build_shell(coll, voxel=0.02, target=3200, name="OozeBody"):
    """Sample the field, mesh it, flatten the sole onto the floor, decimate. -> (object, report)."""
    lo = np.array([-1.85, -2.0, -0.06])
    hi = np.array([1.75, 1.45, 1.70])
    i0 = np.floor(lo / voxel).astype(int)
    i1 = np.ceil(hi / voxel).astype(int)
    idx = np.stack(np.meshgrid(*[np.arange(a, b + 1) for a, b in zip(i0, i1)], indexing="ij"), -1)
    P = idx.astype(np.float64) * voxel
    D = field(P)
    D[..., 0] = np.maximum(D[..., 0], voxel)        # close the grid's own faces
    D[..., -1] = np.maximum(D[..., -1], voxel)
    D[:, 0], D[:, -1], D[0], D[-1] = [np.maximum(x, voxel) for x in (D[:, 0], D[:, -1], D[0], D[-1])]
    V, F = sdf_mesh(D, i0, voxel)
    dense = sum(len(f) - 2 for f in F)

    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in V]
    for f in F:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    for v in bm.verts:                              # the sole sits on the floor
        if v.co.z < FLOOR + 0.25 * voxel:
            v.co.z = FLOOR
    ob = mesh_obj(name, bm, coll)
    _decimate(ob, target)
    _clean(ob)
    me = ob.data
    rep = dict(dense_tris=dense, tris=sum(len(p.vertices) - 2 for p in me.polygons), verts=len(me.vertices))
    return ob, rep


def _decimate(ob, target):
    """Collapse to the budget. (A first try spared the pods with a vertex group; once they were fat that left them
    with a third of the triangles and the dome faceted, so it is uniform: the quadric error keeps the tips anyway.)"""
    me = ob.data
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    mod = ob.modifiers.new("Decimate", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = min(1.0, target / n)
    mod.use_collapse_triangulate = True
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def _clean(ob):
    """Triangulate, even out slivers, smooth-shade, and cut the sole away: the shell is open at the floor. (A flat
    sole lay in the floor's plane and shadow-acned into dark wedges seen through the jelly; nothing ever sees it.)
    The decimation leaves the rim a hair off the floor: snap it back."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for _ in range(6):
        # the sole and the slivers left along its rim (a 0.6 m one facing down showed as a dark wedge); each pass
        # snaps the new rim to the floor, which can tip the next row of slivers downward
        sole = [f for f in bm.faces if f.normal.z < -0.3 and f.calc_center_median().z < FLOOR + 0.05]
        if not sole:
            break
        rim = {v for f in sole for v in f.verts}
        bmesh.ops.delete(bm, geom=sole, context='FACES_ONLY')
        for v in rim:
            if v.co.z < FLOOR + 0.035:
                v.co.z = FLOOR
        bm.normal_update()
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
