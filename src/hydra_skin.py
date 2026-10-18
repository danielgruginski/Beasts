"""The hydra's real body (2026-10-17): one skin from the three snouts to the tail tip, after dragon_skin's recipe
(Daniel: a creature like an approved one starts from its finished parts).

As the dragon's: a signed distance field of melted primitives on a 2.5 cm grid (each primitive evaluated only inside
its own box), meshed with openvdb and decimated:
- the trunk and tail: a chain of overlapping ellipsoids along hydra_body.BODY_ROWS;
- each neck: its own chain along its blockout loft, from inside the chest's front to the poll;
- muscles (shoulders, upper arms, forearms, haunches, calves), the sprawled legs and the webbed feet's toes.
Each head (hydra_head: the dragon's head scaled the hydra's way) is meshed at 1 cm with its own neck melted in near
the seam; the body's grid holds the heads' backs too, so the cut loops lie on one surface. The seams: a plane square
to each neck CUT_ARC down from its poll -- cut only round that neck (one infinite plane, as the dragon's, would
slice the other necks), the rough heads beyond left as loose pieces and dropped -- and the loops zipped.

Weights: Blender's heat map on the skin; over the 30 cm before each seam the head's own weights (Head/Jaw, the
masseter blend) fade in. Shells: the heads' teeth, tongues and eyes, the claws seated on the skin. Fins (HydraFins,
two-sided): gill fans, the webs between the toes, the tail's fin and keel.
"""
import math
import numpy as np
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import dragon_body as DB
import dragon_head as DH
import dragon_skin as DS
import hydra_body as HB
import hydra_head as HH
import beast_rig
from beast_common import spline, cone, smoothstep, mesh_obj, get_coll, remove_obj
from ooze_body import smin, sdf_mesh
from dragon_skin import ell, rcone, axes_along, pad, _loops, zipper, _read, _write

VOXEL = 0.025
TARGET = 14000                   # the body's skin (10k left the three necks faceted, their colours blotchy)
HEAD_TRIS = 7000                 # each head's skin
CUT_ARC = 0.40                   # each seam: this far down its neck from the poll, square to it
K_JOIN = 0.06
BIG = 1.0
LO, HI = (-2.3, -3.70, -0.05), (2.3, 7.25, 4.50)
PART = dict(skin=1, mouth=2, claw=4, tooth=5, tongue=6, eye=7, pupil=8, fin=9)
COLL = "HYD_Body"
UP, FWD = (0, 0, 1), (0, -1, 0)
S = HH.SCALE
SMIN = float(np.min(S))


def _m(p, s):
    return np.array(DB._m(p, s), float)


# ----------------------------------------------------------------------------------------- the body's pieces
def rows_chain(rows, per_seg=16, start=0.0):
    """Overlapping ellipsoids along a loft's rows (x, y, z, a, b, c), each hanging below the axis like the loft's
    section, spaced a third of its size apart and melted over a third of it (dragon_skin.spine_chain)."""
    R = spline(rows, per_seg)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(R[:, :3], axis=0), axis=1))])
    out, at = [], start
    while at <= s[-1]:
        row = np.array([np.interp(at, s, R[:, j]) for j in range(6)])
        i = min(int(np.searchsorted(s, at)), len(R) - 1)
        ax = axes_along(R[min(i + 1, len(R) - 1), :3] - R[max(i - 1, 0), :3])
        a, b, c = row[3:] * 0.95
        h = (b + c) / 2
        centre = row[:3] - ax[:, 2] * (c - b) / 2
        m = min(a, h)
        out.append(ell(centre, (a, max(0.6 * m, 0.02), h), ax, k=max(0.3 * m, 0.008)))
        at += max(0.33 * m, 0.008)
    return out


def trunk_chain():
    return rows_chain(HB.BODY_ROWS)


def neck_chain(nid):
    return rows_chain(HB._neck_rows(nid, 3))


def muscles(s):
    F, H = HB.FRONT, HB.HIND
    m = lambda p: _m(p, s)
    d = lambda a, b: m(b) - m(a)
    sc = m(F["scap"]) + (m(F["sho"]) - m(F["scap"])) * 0.55
    ua = (m(F["sho"]) + m(F["elb"])) / 2
    fa = m(F["elb"]) + (m(F["wri"]) - m(F["elb"])) * 0.30
    hc = m((0.70, 0.95, 1.38))
    cf = m(H["knee"]) + (m(H["hock"]) - m(H["knee"])) * 0.35
    return [ell(sc, (0.26, 0.42, 0.32), axes_along(d(F["scap"], F["sho"]), FWD), k=0.12),
            ell(ua, (0.22, 0.34, 0.24), axes_along(d(F["sho"], F["elb"]), FWD), k=0.10),
            ell(fa, (0.17, 0.26, 0.18), axes_along(d(F["elb"], F["wri"]), FWD), k=0.05),
            ell(hc, (0.36, 0.52, 0.44), axes_along(d(H["hip"], H["knee"]), FWD), k=0.15),
            ell(cf, (0.16, 0.25, 0.17), axes_along(d(H["knee"], H["hock"]), FWD), k=0.05)]


def toes(s):
    """(base, knuckle, tip, radius, direction, bone): four a foot, fanned wide (webbed)."""
    out = []
    for paw, spread, L, r, bone in ((HB.FRONT["paw"], (-34, -12, 10, 32), 0.38, 0.06, "FrontToes"),
                                    (HB.HIND["paw"], (-32, -11, 10, 31), 0.42, 0.065, "HindToes")):
        for k, ang in enumerate(spread):
            a = math.radians(ang)
            dd = np.array((math.sin(a) * s, -math.cos(a), 0.0))
            base = _m(paw, s) + np.array((s * 0.05 * (k - 1.5), -0.05, -0.02))
            tip = base + dd * L
            tip[2] = r * 0.75
            knuckle = (base + tip) / 2 + np.array((0, 0, 0.035))
            out.append((base, knuckle, tip, r, dd, bone + ("L" if s > 0 else "R")))
    return out


def legs(s):
    F, H = HB.FRONT, HB.HIND
    m = lambda p: _m(p, s)
    out = [rcone(m(F["sho"]), m(F["elb"]), 0.22, 0.16, k=0.07), rcone(m(F["elb"]), m(F["wri"]), 0.16, 0.11, k=0.04),
           rcone(m(F["wri"]), m(F["paw"]), 0.11, 0.10, k=0.03),
           ell(m(F["elb"]), (0.13, 0.13, 0.13), k=0.05), ell(m(F["wri"]), (0.12, 0.12, 0.11), k=0.03),
           ell(m(F["paw"]) + np.array((0, -0.05, -0.02)), (0.15, 0.18, 0.07), k=0.04),
           rcone(m(H["hip"]), m(H["knee"]), 0.28, 0.16, k=0.08), rcone(m(H["knee"]), m(H["hock"]), 0.15, 0.10, k=0.04),
           rcone(m(H["hock"]), m(H["paw"]), 0.10, 0.09, k=0.03),
           ell(m(H["knee"]), (0.14, 0.14, 0.14), k=0.05), ell(m(H["hock"]), (0.11, 0.12, 0.11), k=0.03),
           ell(m(H["paw"]) + np.array((0, -0.05, -0.02)), (0.16, 0.20, 0.07), k=0.04)]
    for base, knuckle, tip, r, dd, bone in toes(s):
        out += [rcone(base, knuckle, r, 0.9 * r, k=0.025), rcone(knuckle, tip, 0.9 * r, 0.65 * r, k=0.02)]
    return out


# ----------------------------------------------------------------------------------------- heads in the field
def _M(nid):
    return HB.head_matrix(nid, 3)


def to_head(nid, P):
    """World -> hydra head space for that neck's head."""
    M = _M(nid)
    R = np.array(M.to_3x3())
    return (np.asarray(P, float) - np.array(M.translation)) @ R


def to_world(nid, Q):
    M = _M(nid)
    return np.asarray(Q, float) @ np.array(M.to_3x3()).T + np.array(M.translation)


def head_field_h(Q):
    """The hydra's head field in its head space: the dragon's, scaled per axis (distances in the smallest axis's
    metres: the zero set is exact, the blends match the body grid's)."""
    return DH.head_field(Q / S) * SMIN


def head_region(nid):
    """World box round the head's back (behind the poll, where it melts into the neck)."""
    corners = np.array([[x, y, z] for x in (-0.75, 0.75) for y in (0.05, 0.85) for z in (-0.85, 0.74)]) * S
    W = to_world(nid, corners)
    return W.min(0), W.max(0)


def body_prims():
    prims = trunk_chain()
    for nid in HB.neck_ids(3):
        prims += neck_chain(nid)
    for s in (1, -1):
        prims += muscles(s) + legs(s)
    for nid in HB.neck_ids(3):
        lo, hi = head_region(nid)
        prims.append((lambda P, n=nid: head_field_h(to_head(n, P)), lo, hi, K_JOIN))
    return prims


def neck_near(nid):
    """That neck's ellipsoids near its poll (as the body's grid has them by the seam)."""
    poll = np.array(_M(nid).translation)
    return [p for p in neck_chain(nid) if np.linalg.norm((p[1] + p[2]) / 2 - poll) < 1.2]


def head_field_dragon(nid, near):
    """For DH.build_head_mesh (dragon head space): the head's field with its neck's chain melted in near the
    seam, in the dragon's units (everything divided by SMIN: the same zero set as the body grid's)."""
    def f(Pd):
        d = DH.head_field(Pd)
        mask = Pd[..., 1] > -0.25
        if mask.any():
            Pw = to_world(nid, Pd[mask] * S)
            neck = np.full(len(Pw), BIG)
            for fn, lo, hi, k in near:
                inb = np.all((Pw >= lo - pad(k)) & (Pw <= hi + pad(k)), axis=1)
                if inb.any():
                    neck[inb] = smin(neck[inb], fn(Pw[inb]), k)
            d[mask] = smin(neck / SMIN, d[mask], K_JOIN / SMIN)
        return d
    return f


# ----------------------------------------------------------------------------------------- the seams
def _neck_curve(nid):
    P = spline([(*p, 0, 0, 0) for p in HB.neck_pts(nid, 3)], 16)[:, :3]
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    return P, s


def plane(nid):
    """That neck's seam: through its spine CUT_ARC down from the poll, square to it, normal toward the body."""
    P, s = _neck_curve(nid)
    at = s[-1] - CUT_ARC
    i = int(np.searchsorted(s, at))
    co = np.array([np.interp(at, s, P[:, j]) for j in range(3)])
    T = P[max(i - 1, 0)] - P[min(i + 1, len(P) - 1)]               # toward the body
    return co, T / np.linalg.norm(T)


def cut_side(nid, P):
    co, no = plane(nid)
    return (np.asarray(P, float) - co) @ no


def _cut_local(bm, nid, keep_back, radius=0.7):
    """Bisect only the faces round that neck's seam; keep the body side (keep_back) or the head side."""
    co, no = plane(nid)
    faces = [f for f in bm.faces if all(np.linalg.norm(np.array(v.co[:]) - co) < radius for v in f.verts)]
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=Vector(co), plane_no=Vector(no),
                           clear_inner=keep_back, clear_outer=not keep_back)


def _keep_largest(bm):
    """Drop every loose piece but the biggest (the rough heads beyond the seams)."""
    bm.verts.ensure_lookup_table()
    seen, comps = set(), []
    for v0 in bm.verts:
        if v0 in seen:
            continue
        stack, comp = [v0], []
        seen.add(v0)
        while stack:
            v = stack.pop()
            comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    drop = [v for c in comps[1:] for v in c]
    if drop:
        bmesh.ops.delete(bm, geom=drop, context='VERTS')
    return len(comps) - 1


# ----------------------------------------------------------------------------------------- meshes
def _dec_weight(P):
    """Keep more on the toes and legs, round each seam (its loop meets the head's finer one), and the thinner the
    tail's section the more (dragon_skin: too few triangles twisted the dragon's tail into a ribbon)."""
    w = np.ones(len(P))
    w = np.where(P[:, 2] < 0.30, 0.35, np.where((P[:, 2] < 1.1) & (np.abs(P[:, 0]) > 0.6), 0.6, w))
    for nid in HB.neck_ids(3):
        co, no = plane(nid)
        near = (np.abs((P - co) @ no) < 0.3) & (np.linalg.norm(P - co, axis=1) < 0.7)
        w = np.where(near, np.minimum(w, 0.6), w)
    R = spline(HB.BODY_ROWS, 6)
    i = np.argmin(np.abs(R[:, 1][None, :] - P[:, 1][:, None]), axis=1)
    thin_tail = (P[:, 1] > 2.0) & (np.abs(P[:, 0]) < 0.6) & (P[:, 2] < 1.6)
    keep = np.clip(0.25 + 1.6 * R[i, 3], 0.25, 1.0)
    return np.where(thin_tail, np.minimum(w, keep), w)


def build_body_mesh(target=TARGET):
    g = DS.Grid(LO, HI, VOXEL)
    for p in body_prims():
        g.union(p)
    V, F = g.mesh()
    bm = DS._bm(V, F)
    for _ in range(2):
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.3, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    return DH._decimate(bm, target, _dec_weight)


def build_head_mesh(nid):
    """That neck's head (with its neck melted in), meshed in the dragon's head space, moved into the body."""
    near = neck_near(nid)

    def dw(Pd):
        w = DH._dec_weight(Pd)
        return np.where(cut_side(nid, to_world(nid, Pd * S)) > -0.30, np.minimum(w, 0.3), w)
    bm, dense = DH.build_head_mesh(target=HEAD_TRIS, field=head_field_dragon(nid, near), dec_weight=dw)
    bvh_d = BVHTree.FromBMesh(bm)                                  # (dragon space, for the shells)
    bridges = DH.bridges(bm)
    for v in bm.verts:
        v.co = Vector(to_world(nid, np.array(v.co[:]) * S))
    return bm, dict(dense_tris=dense, bridges=bridges), bvh_d


# ----------------------------------------------------------------------------------------- colours
def _axes():
    """The trunk's and each neck's axis, with frames and sections, for back / belly: a list of (n, 12) arrays."""
    out = []
    for rows in [HB.BODY_ROWS] + [HB._neck_rows(n, 3) for n in HB.neck_ids(3)]:
        R = spline(rows, 6)
        C = R[:, :3]
        T = np.gradient(C, axis=0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        N = np.array(UP) - (T @ np.array(UP))[:, None] * T
        N /= np.linalg.norm(N, axis=1)[:, None]
        out.append(np.hstack([C, T, N, R[:, 3:6]]))
    return out


def body_colors(P, rgb):
    """Sea-green back, pale belly along the trunk's, the necks' and the tail's undersides (not down the legs).
    Each axis (the trunk, every neck) gives its own belly share, measured within its cross-section; they blend by
    how near the point is to each. (Taking only the nearest axis flipped at the necks' roots: dark patches on the
    chest and the necks' fronts.)"""
    ks, ds = [], []
    for A in _axes():
        C, T, N, abc = A[:, :3], A[:, 3:6], A[:, 6:9], A[:, 9:12]
        idx = np.empty(len(P), int)
        dist = np.empty(len(P))
        for k in range(0, len(P), 4000):
            D2 = ((P[k:k + 4000, None, :] - C[None]) ** 2).sum(-1)
            idx[k:k + 4000] = np.argmin(D2, axis=1)
            dist[k:k + 4000] = np.sqrt(D2.min(1))
        d = P - C[idx]
        Sx = np.cross(T[idx], N[idx])
        u, v = (d * Sx).sum(1), (d * N[idx]).sum(1)
        a, b, c = abc[idx, 0], abc[idx, 1], abc[idx, 2]
        e = np.sqrt((u / a) ** 2 + (v / np.where(v > 0, b, c)) ** 2)
        ventral = -v / np.maximum(np.hypot(u, v), 1e-6)
        ks.append(smoothstep(0.40, 0.78, ventral) * smoothstep(1.5, 1.2, e))
        ds.append(dist - np.minimum(a, c))                          # how far outside that axis's own section
    ks, ds = np.array(ks), np.array(ds)
    w = np.exp(-((ds - ds.min(0)) / 0.12) ** 2)
    k = (w * ks).sum(0) / w.sum(0)
    back, belly = np.array(rgb(HB.COL["back"])), np.array(rgb(HB.COL["belly"]))
    return [tuple(back * (1 - x) + belly * x) for x in k]


# ----------------------------------------------------------------------------------------- weights
def _exclude(n):
    return n in ("Root", "Motion") or n.startswith(("Socket_", "Jaw"))


def skin_weights(ob, rig, head_rows):
    """Heat weights everywhere, then each head's own weights fading in over the 30 cm before its seam; vertices the
    heat solve left empty take the nearest bones'. head_rows: {nid: vertex indices}."""
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
    names, W = _read(ob)
    co = np.array([v.co[:] for v in ob.data.vertices])
    empty = np.nonzero(W.sum(1) < 1e-4)[0]
    B = HB.rest_bones(3)
    if len(empty):
        bones = DB._bones_of(B, [b.name for b in ad.bones if b.use_deform and not _exclude(b.name)])
        for i, w in zip(empty, DB.chain_weights(co[empty], bones, falloff=0.15)):
            for n, x in w.items():
                if n not in names:
                    names.append(n)
                    W = np.hstack([W, np.zeros((len(W), 1))])
                W[i, names.index(n)] = x
    for nid, rows in head_rows.items():
        for n in (f"Head{nid}", f"Jaw{nid}"):
            if n not in names:
                names.append(n)
                W = np.hstack([W, np.zeros((len(W), 1))])
        Pd = to_head(nid, co[rows]) / S
        wj = DH.jaw_weight(Pd)
        r = smoothstep(0.0, -0.30, cut_side(nid, co[rows]))
        Hw = np.zeros((len(rows), len(names)))
        Hw[:, names.index(f"Jaw{nid}")] = wj
        Hw[:, names.index(f"Head{nid}")] = 1 - wj
        W[rows] = r[:, None] * Hw + (1 - r[:, None]) * W[rows]
    W /= np.maximum(W.sum(1), 1e-9)[:, None]
    _write(ob, names, W, np.arange(len(W)))
    head_set = np.concatenate(list(head_rows.values()))
    body_rows = np.setdiff1d(np.arange(len(W)), head_set)
    beast_rig.smooth_weights(ob, body_rows, iterations=2, factor=0.5)
    beast_rig.clean_weights(ob)
    return {"empty_after_heat": int(len(empty))}


# ----------------------------------------------------------------------------------------- shells and fins
def _skin_lookup(ob):
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


def build_shells(acc, fins, ob, rgb):
    """Into Accs (body space): each head's teeth, tongue and eyes; the claws, seated on the skin. Fins: gill fans,
    the webs between the toes, the tail's fin and keel."""
    rep = {}
    for nid in HB.neck_ids(3):
        M = _M(nid)
        hb, jb = f"Head{nid}", f"Jaw{nid}"

        def shell(target, fn, bone, color, scale=S):
            tmp = bmesh.new()
            out = fn(tmp)
            n = len(tmp.verts)
            if color == "eye":
                cols = [rgb(HH.COL["pupil"]) if p else rgb(HH.COL["eye"]) for p in out]
            elif color == "gill":
                a, b = np.array(rgb(HH.COL["fin"])), np.array(rgb(HH.COL["gill"]))
                cols = [tuple(a * (1 - t) + b * t) for t in smoothstep(0.35, 1.0, np.array(out))]
            else:
                cols = [rgb(color)] * n
            HH._add_bm(target, M, tmp, [{bone: 1.0}] * n, cols, scale)

        shell(acc, lambda bm: HH.build_teeth(bm, True), hb, HH.COL["tooth"])
        shell(acc, lambda bm: HH.build_teeth(bm, False), jb, HH.COL["tooth"])
        shell(acc, DH.build_tongue, jb, HH.COL["tongue"])
        for s_ in (1, -1):
            shell(acc, lambda bm, s_=s_: HH.build_eye(bm, s_), hb, "eye")
            shell(fins, lambda bm, s_=s_: HH.build_gill(bm, s_), hb, "gill", scale=1.0)

    kd, Wd, bvh = _skin_lookup(ob)
    claw, fin = rgb(HB.COL["claw"]), rgb(HB.COL["fin"])
    n = 0
    for s_, sfx in DB.SIDES:
        by_bone = {}
        for base, knuckle, tip, r, dd, bone in toes(s_):           # claws, short and hooked
            a = tip - dd * 0.02
            b = tip + dd * 0.12 + np.array((0, 0, -0.02))
            seat, b0 = DS._seat(bvh, a, b, r * 0.55)
            acc.add(lambda bm, b0=b0, b=b, r=r: cone(bm, b0, b, r * 0.55, seg=6, bend=(0, 0, -0.04)), bone, claw)
            by_bone.setdefault(bone, []).append((base, tip))
            n += 1
        for bone, tl in by_bone.items():                            # the web: a fan from the paw, sagging between
            p0 = np.mean([t[0] for t in tl], axis=0) + np.array((0, 0, 0.01))          # the toe tips
            edge = []
            for (b0_, t0), (b1_, t1) in zip(tl[:-1], tl[1:]):         # (out near the tips: sagging a third of
                edge += [t0 * 0.95 + p0 * 0.05, (t0 + t1) / 2 * 0.85 + p0 * 0.15]   # the way, they hid between
            edge.append(tl[-1][1] * 0.95 + p0 * 0.05)                            # the toes' bases)
            edge = [np.array((e[0], e[1], max(e[2], 0.03))) for e in edge]

            def web(bm, p0=p0, edge=edge):
                v0 = bm.verts.new(Vector(p0))
                ve = [bm.verts.new(Vector(e)) for e in edge]
                for a_, b_ in zip(ve[:-1], ve[1:]):
                    bm.faces.new((v0, a_, b_))
            fins.add(web, bone, fin)
    trunk = ["Chest", "Spine2", "Spine1", "Hips"] + [f"Tail{i + 1}" for i in range(HB.TAIL_N)]
    tb = DB._bones_of(HB.rest_bones(3), trunk)
    for sign, table in ((1, HB.TAIL_FIN), (-1, HB.TAIL_KEEL)):
        base, top = HB._tail_fins(sign, table)
        fins.add(lambda bm, b=base, t=top: HB._fin(bm, b, t), lambda P: DB.chain_weights(P, tb), fin)
    rep["claws"] = n
    return rep


def shell_parts(colors, rgb):
    key = lambda c: tuple(round(float(x), 5) for x in c)
    table = {key(rgb(HB.COL["claw"])): PART["claw"], key(rgb(HH.COL["tooth"])): PART["tooth"],
             key(rgb(HH.COL["tongue"])): PART["tongue"], key(rgb(HH.COL["eye"])): PART["eye"],
             key(rgb(HH.COL["pupil"])): PART["pupil"]}
    return [table.get(key(c), PART["skin"]) for c in colors]


# ----------------------------------------------------------------------------------------- assembly
def build(rig):
    """The real body: skin (three heads + body, one mesh), shells joined onto it, fins. -> (objects, report)"""
    rep = {"heads": {}}
    rgb = HB._rgb
    heads = {}
    for nid in HB.neck_ids(3):
        bm, rep["heads"][nid or "M"], _ = build_head_mesh(nid)
        _cut_local(bm, nid, keep_back=False, radius=1e3)            # (the head mesh holds only its own neck)
        heads[nid] = bm
    body, rep["body_dense_tris"] = build_body_mesh()
    for nid in HB.neck_ids(3):
        _cut_local(body, nid, keep_back=True)
    rep["loose_dropped"] = _keep_largest(body)
    lb = _loops(body)
    rep["body_loops"] = [len(l) for l in lb]

    skin = bmesh.new()
    head_rows, start = {}, 0
    order = list(HB.neck_ids(3))
    vmaps = {}
    for nid in order:
        src = heads[nid]
        vm = {}
        for v in src.verts:
            vm[v] = skin.verts.new(v.co)
        for f in src.faces:
            try:
                skin.faces.new([vm[v] for v in f.verts])
            except ValueError:
                pass
        head_rows[nid] = np.arange(start, start + len(src.verts))
        start += len(src.verts)
        vmaps[nid] = vm
    vb = {}
    for v in body.verts:
        vb[v] = skin.verts.new(v.co)
    for f in body.faces:
        try:
            skin.faces.new([vb[v] for v in f.verts])
        except ValueError:
            pass
    n_heads = start
    rep["seam_faces"] = {}
    for nid in order:                                             # zip each head to its neck's loop
        co, no = plane(nid)
        la = _loops(heads[nid])
        loop_b = min(lb, key=lambda L: np.linalg.norm(np.mean([v.co[:] for v in L], axis=0) - co))
        rep["seam_faces"][nid or "M"] = zipper(skin, [vmaps[nid][v] for v in la[0]], [vb[v] for v in loop_b], no)
        heads[nid].free()
    body.free()
    bmesh.ops.recalc_face_normals(skin, faces=skin.faces[:])
    skin.normal_update()
    P = np.array([v.co[:] for v in skin.verts])

    bc = np.array(body_colors(P, rgb))
    cols = bc.copy()
    for nid, rows in head_rows.items():                           # the heads' colours fade into the body's
        hc = np.array(HH.head_colors(to_head(nid, P[rows]) / S, rgb))
        r = smoothstep(-0.45, 0.0, cut_side(nid, P[rows]))[:, None]
        cols[rows] = hc * (1 - r) + bc[rows] * r
    cols = [tuple(c) for c in cols]

    coll = get_coll(COLL)
    mat = DB.blockout_material()
    remove_obj("HydraBody")
    ob = mesh_obj("HydraBody", skin, coll)
    me = ob.data
    att = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    att.data.foreach_set('color', [c for col in cols for c in (*col, 1.0)])
    me.materials.clear()
    me.materials.append(mat)
    me.shade_smooth()
    rep["skin_tris"] = sum(len(p.vertices) - 2 for p in me.polygons)
    rep["weights"] = skin_weights(ob, rig, head_rows)

    mouth = np.array(rgb(HH.COL["mouth"]))
    DS.write_info(ob, [PART["mouth"] if np.abs(np.array(c) - mouth).max() < 1e-4 else PART["skin"] for c in cols])
    acc, fins = DB.Acc(), DB.Acc()
    rep["shells"] = build_shells(acc, fins, ob, rgb)
    remove_obj("HYD_Shells")
    shells = acc.finish("HYD_Shells", coll, mat)
    DS.write_info(shells, shell_parts(acc.C, rgb))
    rep["shell_tris"] = sum(len(p.vertices) - 2 for p in shells.data.polygons)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    shells.select_set(True)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.join()
    rep["body"] = beast_rig.weight_report(ob)

    remove_obj("HydraFins")
    ob_fins = fins.finish("HydraFins", coll, mat)
    DS.write_info(ob_fins, [PART["fin"]] * len(ob_fins.data.vertices))
    rep["fins"] = beast_rig.bind(ob_fins, rig)
    rep["tris"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (ob, ob_fins)}
    lc = bpy.context.view_layer.layer_collection.children.get(HB.COLL)    # the blockout steps aside
    if lc is not None:
        lc.exclude = True
    return (ob, ob_fins), rep
