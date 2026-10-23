"""Leech (2026-10-23, a unit from Daniel's card game): a giant swamp leech, body, skeleton and skinning. Facing -Y.

My calls (Daniel gave no details): 1.8 m long lying stretched out, 0.25 m across at its widest (a third of the way
from the tail), flattened with a flat belly, ringed all along (the annuli: small ridges in the mesh, fine rings in the
paint); the front end narrows to a round oral sucker, a cup ringed inside with three rows of teeth (a lamprey's more
than a real leech's: it reads from the game camera); a broad rear sucker, a disc under the tail end.

It is a chain (the ooze and the insectoids' centipede are the other path bodies): the bones sit along the body's
centre line, so a pose is a curve. Sucker (the rear disc), Body1..Body10, Head (the oral sucker), rear to front; a
leaf Swell<k> on each body bone, scaled uniformly to swell that segment (the pulses that run down a feeding leech;
leaf bones only, the ooze's rule). Sockets Socket_Mouth, Socket_Rear.

The mesh is built ring by ring (no voxel fuse: it is one clean tube): rings every 2.5 cm along the length, each a
flattened section (the belly flatter), alternate rings a little fatter for the annuli; the front folds inward into the
sucker's cup; the rear closes in a round cap over the disc. Weights by arc length along the chain (2 neighbours), a
share of each moved onto its Swell bone (less on the belly, so a swollen segment doesn't sink).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
import beast_body, beast_rig
from beast_body import PART, ellipsoid, _write_info
from beast_common import cone, loft, mesh_obj, get_coll, remove_obj, smoothstep
import dragon_body as DB

NAME, PREFIX = "Leech", "LCH"
RIG = "LeechRig"
BODY = "LeechBody"
UP = (0, 0, 1)
L0 = 1.80                         # rest length, rear tip (u = 0) to the lip (u = L0)
Z0 = 0.068                        # the centre line's height lying flat
N_BODY = 10
SEG_U0, SEG_LEN = 0.12, 0.16      # Body1 starts at u 0.12; each body bone 0.16 long; Head 1.72 .. 1.80
N_SIDE = 14
DU = 0.025

# half width along the body (u from the rear tip); top and bottom as fractions of it
WIDTH = ((0.0, 0.070), (0.10, 0.096), (0.50, 0.125), (1.00, 0.117), (1.40, 0.094), (1.65, 0.073), (1.80, 0.068))
TOP, BOTTOM = 0.60, 0.42


def y_of(u):
    return 0.90 - u


def centre(u):
    return np.array((0.0, y_of(u), Z0))


def half_width(u):
    us, ws = zip(*WIDTH)
    return float(np.interp(u, us, ws))


def annulus(u):
    return 1.0 + 0.03 * math.cos(2 * math.pi * u / (2 * DU))


def section(u, th, k=None):
    """A point of the flattened section at arc u, angle th (0 = left side, pi/2 = top, -pi/2 = the belly)."""
    a = half_width(u) * (annulus(u) if k is None else k)
    s, c = math.sin(th), math.cos(th)
    z = TOP * a * s if s >= 0 else -BOTTOM * a * abs(s) ** 0.55
    return np.array((a * c, y_of(u), Z0 + z))


# ----------------------------------------------------------------------------------------- skeleton
def bone_spans():
    """[(name, u0, u1)] rear to front."""
    out = [("Sucker", 0.0, SEG_U0)]
    for k in range(N_BODY):
        u0 = SEG_U0 + k * SEG_LEN
        out.append((f"Body{k + 1}", u0, u0 + SEG_LEN))
    out.append(("Head", SEG_U0 + N_BODY * SEG_LEN, L0))
    return out


def rest_bones():
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.3, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.2, None, True)
    par = "Root"
    for n, u0, u1 in bone_spans():
        DB._bone(B, n, centre(u0), centre(u1), UP, par)
        par = n
    for k in range(N_BODY):
        u0 = SEG_U0 + k * SEG_LEN
        c = centre(u0 + SEG_LEN / 2)
        DB._bone(B, f"Swell{k + 1}", c, c + np.array((0, -0.04, 0)), UP, f"Body{k + 1}")
    lip = centre(L0)
    DB._bone(B, "Socket_Mouth", lip, lip + np.array((0, 0, 0.1)), (0, -1, 0), "Head")
    rear = np.array((0.0, y_of(0.06), 0.02))
    DB._bone(B, "Socket_Rear", rear, rear + np.array((0, 0, 0.1)), (0, -1, 0), "Sucker")
    return B


# ----------------------------------------------------------------------------------------- mesh
def _ring_faces(bm, a, b):
    n = len(a)
    for j in range(n):
        j1 = (j + 1) % n
        bm.faces.new((a[j], a[j1], b[j1], b[j]))


def build_tube(bm):
    """The body: the rear cap, the ringed body, the lip and the cup folding inward. -> (verts, u per vertex)."""
    ths = [-math.pi / 2 + 2 * math.pi * j / N_SIDE for j in range(N_SIDE)]       # j = 0 on the belly (the seam)
    rings, us = [], []
    for u, k in ((0.010, 0.45), (0.022, 0.78)):                                  # the rounded rear cap
        rings.append([section(0.03, t, k) * np.array((1, 1, 1)) + np.array((0, 0.03 - u, 0)) for t in ths])
        us.append(u)
    u = 0.035
    while u < L0 - 0.02:
        rings.append([section(u, t) for t in ths])
        us.append(u)
        u += DU
    lip_u = L0
    a = half_width(lip_u)
    rings.append([np.array((a * 1.02 * math.cos(t), y_of(lip_u), Z0 + 0.005 + 0.78 * a * math.sin(t))) for t in ths])
    us.append(lip_u)
    CUP = ((L0 - 0.012, 0.050), (L0 - 0.030, 0.036), (L0 - 0.050, 0.020))       # inside the cup, going back in
    for cu, r in CUP:
        rings.append([np.array((r * math.cos(t), y_of(cu), Z0 + 0.005 + r * math.sin(t))) for t in ths])
        us.append(cu)
    V = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    rear = bm.verts.new(Vector(centre(0.0) + np.array((0, 0, -0.01))))
    throat = bm.verts.new(Vector((0.0, y_of(L0 - 0.065), Z0 + 0.005)))
    for j in range(N_SIDE):
        j1 = (j + 1) % N_SIDE
        bm.faces.new((rear, V[0][j1], V[0][j]))
        bm.faces.new((throat, V[-1][j], V[-1][j1]))
    for r0, r1 in zip(V[:-1], V[1:]):
        _ring_faces(bm, r0, r1)
    # UV seams: down the belly (j = 0), and round the body at two rings so it unwraps as three short pieces;
    # round the lip (the cup is its own island)
    seam_rings = [i for i, uu in enumerate(us) if abs(uu - 0.62) < DU / 2 or abs(uu - 1.22) < DU / 2]
    lip_i = us.index(lip_u)
    for i in seam_rings + [lip_i]:
        for j in range(N_SIDE):
            e = bm.edges.get((V[i][j], V[i][(j + 1) % N_SIDE]))
            if e is not None:
                e.seam = True
    line = [rear] + [V[i][0] for i in range(lip_i + 1)]
    for p, q in zip(line[:-1], line[1:]):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    cupline = [V[i][0] for i in range(lip_i, len(V))] + [throat]
    for p, q in zip(cupline[:-1], cupline[1:]):
        e = bm.edges.get((p, q))
        if e is not None:
            e.seam = True
    verts = [v for ring in V for v in ring] + [rear, throat]
    uvals = [uu for uu, ring in zip(us, V) for _ in ring] + [0.0, L0 - 0.065]
    return verts, uvals


def build_teeth(bm):
    """Three rows of hooked teeth inside the cup, pointing in toward the throat."""
    vs = []
    for (u, r, n, L) in ((L0 - 0.010, 0.050, 12, 0.020), (L0 - 0.024, 0.040, 10, 0.017), (L0 - 0.040, 0.028, 8, 0.013)):
        for k in range(n):
            t = 2 * math.pi * (k + 0.5 * (n % 2)) / n
            base = np.array((r * math.cos(t), y_of(u), Z0 + 0.005 + r * math.sin(t)))
            inward = np.array((-math.cos(t), 0.6, -math.sin(t)))
            inward /= np.linalg.norm(inward)
            vs += cone(bm, base - inward * 0.003, base + inward * L, 0.0055, seg=3)
    return vs


def build_disc(bm):
    """The rear sucker: a broad disc under the tail end (a short upright loft: its seam unwraps it)."""
    y = y_of(0.07)
    rows = [(0, y, 0.002, 0.115, 0.105, 0.105), (0, y, 0.013, 0.132, 0.120, 0.120), (0, y, 0.027, 0.112, 0.100, 0.100),
            (0, y, 0.040, 0.070, 0.062, 0.062)]
    return loft(bm, rows, up=(0, -1, 0), seg=16, per_seg=1, cap0=0.0, cap1=0.5, capk=1)


def chain_weights(u):
    """Arc position -> {bone: w}: hat weights between the bones' middles, rear sucker and head held at the ends."""
    spans = bone_spans()
    mids = [((u0 + u1) / 2, n) for n, u0, u1 in spans]
    if u <= mids[0][0]:
        return {mids[0][1]: 1.0}
    if u >= mids[-1][0]:
        return {mids[-1][1]: 1.0}
    for (m0, n0), (m1, n1) in zip(mids[:-1], mids[1:]):
        if m0 <= u <= m1:
            t = (u - m0) / (m1 - m0)
            t = t * t * (3 - 2 * t)
            return {n0: 1 - t, n1: t}
    return {mids[-1][1]: 1.0}


SWELL = 0.6                       # how much of a body bone's weight its Swell bone takes (top and sides)


def with_swell(w, top):
    """Move a share of each Body<k> weight onto Swell<k>; less on the belly (top: -1 belly .. 1 back)."""
    out = {}
    k = SWELL * float(0.35 + 0.65 * smoothstep(-0.6, 0.2, top))
    for b, x in w.items():
        if b.startswith("Body"):
            out[b] = out.get(b, 0) + x * (1 - k)
            sb = "Swell" + b[4:]
            out[sb] = out.get(sb, 0) + x * k
        else:
            out[b] = out.get(b, 0) + x
    return out


def build_body():
    """-> LeechBody (one object: tube, teeth, disc) with its weights; info: part (tube 'fur', teeth 'tooth', disc
    'sucker'), and info.b = the vertex's arc position u / L0 (the painter's)."""
    bm = bmesh.new()
    tube, uvals = build_tube(bm)
    teeth = build_teeth(bm)
    disc = build_disc(bm)
    bm.verts.index_update()
    part = np.zeros(len(bm.verts), int)
    aux = np.zeros(len(bm.verts))
    W = [None] * len(bm.verts)
    for v, u in zip(tube, uvals):
        top = (v.co.z - Z0) / max(TOP * half_width(u), 1e-3)
        part[v.index] = PART['fur']
        aux[v.index] = u / L0
        W[v.index] = with_swell(chain_weights(u), max(-1.0, min(1.0, top)))
    for v in teeth:
        part[v.index] = PART['tooth']
        aux[v.index] = 1.0
        W[v.index] = {"Head": 1.0}
    for v in disc:
        part[v.index] = PART['sucker']
        aux[v.index] = 0.0
        W[v.index] = {"Sucker": 1.0}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    tube_set = set(tube)                             # the tube folds into its cup, which can fool the outside test:
    mid = [f for f in bm.faces if all(v in tube_set for v in f.verts) and abs(f.calc_center_median().y) < 0.4]
    bm.normal_update()
    out = sum(1 for f in mid if f.normal.dot(f.calc_center_median() - Vector((0, f.calc_center_median().y, Z0))) > 0)
    if out < len(mid) / 2:                           # it came out inside out: turn the tube's faces
        bmesh.ops.reverse_faces(bm, faces=[f for f in bm.faces if all(v in tube_set for v in f.verts)])
    remove_obj(BODY)
    coll = get_coll(PREFIX + "_Body")
    ob = mesh_obj(BODY, bm, coll, recalc=False)
    ob.data.shade_smooth()
    _write_info(ob.data, part, np.zeros(len(part)))
    att = ob.data.color_attributes["info"]
    buf = np.empty(len(ob.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    buf = buf.reshape(-1, 4)
    buf[:, 2] = aux
    att.data.foreach_set('color', buf.ravel())
    ob["n_fur"] = 0                              # no fused, heat-weighted part: the builder's seams all stay
    return ob, W


def tri_report(ob):
    return beast_body.tri_report(ob)


def skin(body, rig, W):
    body.vertex_groups.clear()
    groups = {}
    for i, w in enumerate(W):
        for b, x in w.items():
            g = groups.get(b) or body.vertex_groups.new(name=b)
            groups[b] = g
            g.add([i], float(x), 'REPLACE')
    beast_rig.clean_weights(body)
    return beast_rig.bind(body, rig)
