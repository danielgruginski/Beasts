"""The folded wing creased round the body (2026-10-24, Daniel: "The feathers are all quads, what if each individual
feather could be folded in 2 places, so we make things fit. Yes, much more polygons, we would go over budget, but that
is how real feathers work").

The folded wing is a stack of cards 1.1 mm apart (eagle_body.DL), every one a flat card: from behind and above it read
as boards standing beside the body. Bending each card about a hinge of its own does not work in so tight a stack (a
card turned about its own hinge meets the one under it at once: the first try, 2026-10-24, bent P9 and P10 and stopped
everything above them; a smooth bend of the space fails too, the cards being straight between their rows). So the wing
creases along two lines across it, the same for every layer: CREASES, planes across the fold's long axis (eagle_pose's
fold frame: x back along the stack; each crease's axis runs along the stack's up, on its inner face at Z_AXIS).

Every card whose shaft crosses a crease gets a crease row there (crease_hinges -> eagle_body.HINGE_T, before the body
is made): a row slanted across the card, its shaft and both edges where each crosses the crease's plane, so the row
lies on the crease however the card runs across it (the secondaries' edges cross it up to 2.6 cm apart). Folded, everything of those cards
beyond a crease turns about its axis toward the body as one piece (the rows past the crease row by the whole turn, the
crease row by half: it lies on the bisector), so the layers keep their order and their gaps, and each card is folded in
up to two places. A card that would cross a crease in its rounded tip (the tip's edges lie behind the shaft) gets no row
there and does not turn on it; the second crease takes only the primaries (CREASE_KINDS): the innermost layers, they run
on past the secondaries' tips toward the tail, and the secondaries over them would have to turn onto S4's and S5's
unturned tips (the first takes only the primaries and the secondaries: the tertials over them came down onto the tail
as the clips lift and fan it, and the coverts and the scapulars over those cannot turn if they do not). Each turn is as
large as TURN allows, less where the turned part would come nearer than BODY_GAP to the body (fused body, the wing's
flesh, the feet) or CARD_GAP to the tail, the other wing or the side's cards that do not turn (what they already touch
unturned -- the hidden crossings the model has -- is left out of the test). The axes lean AXIS_TILT from the stack's up
toward its outer side: about the up itself the tips came in and down, 8 mm lower perched, and the perched clips put
them on the ground. As built (2026-10-24): 18 and 15 deg perched, 22 cards a side creased (P1-P10, S1-S12); the clips
take a share of it (eagle_anim.GAUGE, fitted by eagle_build.fold_fit).

The turns are kept as two shape keys on EagleBody, FoldL and FoldR: each card vertex's offset in the pose taken back to
the bind through its skinning (linear blend skinning is linear in the rest position: offset_bind = A^-1 offset_posed, A
the weighted sum of its bones' turns), so the key bends the card wherever its bones put it. A key follows its gauge bone
(WingFoldL/R, eagle_pose.gauge: slid FOLD_GAUGE x the wing's lay, so 1 folded, 0 spread or flexed): a driver here,
EagleFeatherFold in Unity.
"""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import eagle_body as EB

CREASES = (0.07, 0.19)        # along the fold's long axis (m, eagle_pose's fold frame; every long card's root before)
Z_AXIS = 0.235                # the creases' axes, on the stack's inner face (m along the fold's outward normal)
TURN = (18.0, 18.0)           # the most each crease turns (deg)
# the cards that may crease on each, from the inside of the stack out: the first the primaries and the secondaries (the
# tertials over them came down onto the tail as the clips lift and fan it, and the coverts and scapulars over the
# tertials cannot turn if they do not), the second only the primaries, which run on past the secondaries' tips toward
# the tail (the secondaries over them would turn onto S4's and S5's tips, which cross it too near their ends to crease)
CREASE_KINDS = (('primary', 'secondary'), ('primary',))
BODY_GAP, CARD_GAP = 0.0025, 0.0006
AXIS_TILT = [15.0, 15.0]       # each crease's axis tilted from the stack's up toward its outward normal (deg)
EPS = 0.0015                  # within this of a crease's plane a vertex is on the crease: it turns half
STEP = 0.5
KEYS = {1: "FoldL", -1: "FoldR"}
SOLID = ('fur', 'wing', 'foot', 'claw')


def _fold_axes():
    import eagle_pose as EP
    return tuple(np.array(v) for v in EP._fold_basis())          # outward normal, back, up (left, rest body frame)


def crease_hinges():
    """-> {card name: (t, ...)}: where each card's shaft crosses the creases in the perched pose (the cards as they
    are without hinges; the left side, the right mirrors it)."""
    import eagle_pose as EP
    keep = dict(EB.HINGE_T)
    EB.HINGE_T.clear()
    EB._FE.clear()
    EP._REST.clear()
    try:
        R = EP.rest()['R']
        W = EP.pose_matrices(EP.perched())
        to_body = (W["Chest"] @ R["Chest"].inverted()).inverted()
        n, a, u = _fold_axes()
        ts = np.linspace(0.0, 1.0, 801)
        out = {}
        for name, f in EB.fe_table().items():
            if f.kind == 'tail':
                continue
            M = Matrix(((0,) * 4,) * 4)
            for b, w in f.bones.items():
                M = M + (W[b + "L"] @ R[b + "L"].inverted()) * w
            M = np.array(to_body @ M)
            xs = {u: (f.line(ts, u) @ M[:3, :3].T + M[:3, 3]) @ a for u in (0, -1, 1)}

            def cross(u, xc):
                i = np.nonzero(xs[u] >= xc)[0]
                if len(i) == 0 or i[0] == 0:
                    return None
                i = i[0]
                return float(ts[i - 1] + (ts[i] - ts[i - 1]) * (xc - xs[u][i - 1]) / (xs[u][i] - xs[u][i - 1]))
            k_tip = f.rows[-1][1]
            tip = {u: 1.0 - f.chev * (f.wl if u < 0 else f.wt) * k_tip / f.L for u in (-1, 1)}   # the tip's edges
            hinges = []
            for xc in CREASES:
                t = cross(0, xc)
                tl, tt = (cross(u, xc) for u in (-1, 1))
                if f.kind not in CREASE_KINDS[len(hinges)] or t is None or tl is None or tt is None or t > 0.97                         or tl > tip[-1] - 0.01 or tt > tip[1] - 0.01:
                    break                                  # no crease row this near the tip: the card stays flat
                hinges.append(tuple(round(v, 4) for v in (t, tl, tt)))
            if hinges:
                out[name] = tuple(hinges)
        return out
    finally:
        EB.HINGE_T.clear()
        EB.HINGE_T.update(keep)
        EB._FE.clear()
        EP._REST.clear()


def _posed_coords(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


def _components(polys, nv):
    parent = list(range(nv))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for p in polys:
        r = find(p[0])
        for v in p[1:]:
            parent[find(v)] = r
    return [find(p[0]) for p in polys]


def clear_keys(ob):
    """Drop FoldL / FoldR (and the basis when nothing else is left)."""
    key = ob.data.shape_keys
    if key is None:
        return
    for nm in KEYS.values():
        kb = key.key_blocks.get(nm)
        if kb is not None:
            try:
                kb.driver_remove("value")
            except TypeError:
                pass
            ob.shape_key_remove(kb)
    key = ob.data.shape_keys
    if key is not None and len(key.key_blocks) == 1:
        ob.shape_key_remove(key.key_blocks[0])


class Card:
    def __init__(self, name, side, fe, verts, faces, fc):
        self.name, self.side, self.fe = name, side, fe
        self.verts = verts                                  # creation order: rows of (lead, shaft, trail)
        self.rows = [verts[i:i + 3] for i in range(0, len(verts), 3)]
        t = [float(fc[r[1], 1]) for r in self.rows]
        local = {v: i // 3 for i, v in enumerate(verts)}
        self.faces = [(f, min(local[v] for v in f), max(local[v] for v in f)) for f in faces]
        self.hinge_rows = [int(np.argmin([abs(x - h) for x in t])) for h in fe.hinges]     # one per crease crossed

    @property
    def label(self):
        return self.name + ("L" if self.side > 0 else "R")


def cards(ob):
    """The cards of the top layer (no undersides) -> [Card], the solid faces."""
    from beast_body import read_info, PART
    part, _ = read_info(ob)
    polys = [tuple(p.vertices) for p in ob.data.polygons]
    back = ob.data.attributes.get("back")
    bk = np.zeros(len(polys), bool)
    if back is not None:
        buf = np.zeros(len(polys), np.int32)
        back.data.foreach_get('value', buf)
        bk = buf > 0
    fpart = np.array([part[p[0]] for p in polys])
    solid_ids = {PART[k] for k in SOLID}
    solid = [p for p, fp, b in zip(polys, fpart, bk) if fp in solid_ids and not b]
    ci = [i for i in range(len(polys)) if fpart[i] == PART['feather'] and not bk[i]]
    comp = _components([polys[i] for i in ci], len(ob.data.vertices))
    fc = np.zeros(len(ob.data.vertices) * 3, np.float32)
    ob.data.attributes["root"].data.foreach_get('vector', fc)
    fc = fc.reshape(-1, 3)
    rest = np.array([v.co[:] for v in ob.data.vertices])
    inv = {v: k for k, v in EB.KIND.items()}
    letter = dict(primary="P", secondary="S", tertial="T", gcovert="G", pcovert="PC", alula="A", tail="F",
                  scapular="SC")
    groups = {}
    for i, c in zip(ci, comp):
        groups.setdefault(c, []).append(polys[i])
    FE = EB.fe_table()
    out = []
    for c, faces in groups.items():
        verts = sorted({v for f in faces for v in f})
        assert len(verts) % 3 == 0 and all(abs(fc[verts[i], 0] - (-1, 0, 1)[i % 3]) < 1e-4 for i in range(len(verts))), \
            "card rows are not (lead, shaft, trail) triples"
        k = int(math.floor(fc[verts[0], 2] + 1e-3))
        idx = int(round((fc[verts[0], 2] - k) * 100))
        name = f"{letter[inv[k]]}{idx}"
        side = 1 if rest[verts[1], 0] > 0 else -1
        out.append(Card(name, side, FE[name], verts, faces, fc))
    return out, solid


def _rot(axis, ang, P, pivot):
    R = np.array(Matrix.Rotation(math.radians(ang), 3, Vector(axis)))
    return (P - pivot) @ R.T + pivot


def _rot_each(axis, ang, P, pivot):
    """P (n, 3) turned about the line (pivot, axis) by ang[i] degrees each (Rodrigues)."""
    k = np.asarray(axis, float)
    k = k / np.linalg.norm(k)
    v = P - pivot
    a = np.radians(ang)[:, None]
    return pivot + v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * (v @ k)[:, None] * (1 - np.cos(a))


def _tree(P, faces):
    return BVHTree.FromPolygons([Vector(p) for p in P], [tuple(f) for f in faces], all_triangles=False)


def drape(ob=None, rig=None, fixed=None):
    """-> report; writes FoldL / FoldR and their drivers. fixed: {"L1": deg, ...} turns to use instead of the search
    (eagle_build.fold_fit scales them down for the clips). The rig is left in its rest pose."""
    import eagle_pose as EP
    ob = ob or bpy.data.objects[EB.BODY]
    rig = rig or bpy.data.objects[EB.RIG]
    assert ob.matrix_world == Matrix.Identity(4) and rig.matrix_world == Matrix.Identity(4)
    clear_keys(ob)
    EP.use("perched", rig)
    P0 = _posed_coords(ob)
    P = P0.copy()
    cs, solid = cards(ob)
    body_tree = _tree(P0, solid)
    pb = rig.pose.bones["Chest"]
    Tc = np.array(pb.matrix @ pb.bone.matrix_local.inverted())
    n0, a0, u0 = _fold_axes()
    rep = {"turns": {}, "hinged": {}, "ignored": {}, "stopped_by": {}}
    owner_of = {}
    for c in cs:
        for f, _, _ in c.faces:
            owner_of[f] = c.label
    for s in (1, -1):
        mx = np.array((s, 1.0, 1.0))
        side = "L" if s > 0 else "R"
        mine = [c for c in cs if c.side == s and c.hinge_rows]                 # the cards with crease rows
        rest_of = [c for c in cs if c.side != s or not c.hinge_rows]
        rep["hinged"][side] = sum(1 for c in mine if c.hinge_rows)
        N = Tc[:3, :3] @ (n0 * mx)
        U = Tc[:3, :3] @ (u0 * mx)
        A = Tc[:3, :3] @ (a0 * mx)
        vs = sorted({v for c in mine for v in c.verts})
        loc = {v: i for i, v in enumerate(vs)}
        Ti = np.linalg.inv(Tc)
        x = (P[vs] @ Ti[:3, :3].T + Ti[:3, 3]) @ (a0 * mx)          # along the fold's long axis, as folded
        nrm = {}
        for c in mine:
            f0 = c.faces[0][0]
            m = np.cross(P[f0[1]] - P[f0[0]], P[f0[2]] - P[f0[0]])
            for v in c.verts:
                nrm[v] = m / np.linalg.norm(m)             # each card's dorsal side
        nv = np.array([nrm[v] for v in vs])
        faces = [f for c in mine for f, _, _ in c.faces]
        other_tree = _tree(P, [f for c in rest_of for f, _, _ in c.faces])
        crease = []                                        # (pivot, axis, weight per vertex) at rest
        for xc in CREASES:
            O = Tc[:3, :3] @ ((xc * a0 + Z_AXIS * n0) * mx) + Tc[:3, 3]
            tilt = math.radians(AXIS_TILT[len(crease)])
            axis = U * math.cos(tilt) + N * math.sin(tilt)
            far = O + A * 0.1
            if (_rot(axis, 1.0, far[None], O)[0] - far) @ N > 0:
                axis = -axis                               # + turns the part beyond toward the body
            k = len(crease)
            on = np.where(x > xc + EPS, 1.0, np.where(x < xc - EPS, 0.0, 0.5))
            w = np.zeros(len(vs))
            for c in mine:                                 # only the cards with a row on this crease turn on it
                if len(c.hinge_rows) <= k:
                    continue
                hr = c.hinge_rows[k]
                for i, r in enumerate(c.rows):
                    for v in r:
                        w[loc[v]] = 1.0 if i > hr else (on[loc[v]] if i == hr else 0.0)
            crease.append((O, axis, w))
        base = P[vs].copy()

        def placed(angles):
            Q = base.copy()
            carry = []
            for (O, axis, w), ang in zip(crease, angles):
                for piv, ax, a in carry:                   # a later crease lies beyond the earlier: carried by them
                    O = _rot(ax, a, O[None], piv)[0]
                    axis = _rot(ax, a, axis[None], np.zeros(3))[0]
                Q = _rot_each(axis, ang * w, Q, O)
                carry.append((O, axis, ang))
            return Q

        others = [f for c in rest_of for f, _, _ in c.faces]

        def _owner(key, a):
            if key == "b":
                return "body"
            return owner_of[(others if key == "c" else still_of[0])[a]]

        still_of = [None]

        def touched(Q, k, gaps=True, skip=frozenset()):
            w = crease[k][2]
            faces_ff = [f for f in faces if max(w[loc[v]] for v in f) > 0]
            ff = [tuple(loc[v] for v in f) for f in faces_ff]
            still = [f for f in faces if max(w[loc[v]] for v in f) == 0]
            still_of[0] = still
            if still:                                      # the side's cards not turning on this crease
                Pq = P.copy()
                Pq[vs] = Q
                still_tree = _tree(Pq, still)
            found = set()
            for key, tree, gap in (("b", body_tree, BODY_GAP), ("c", other_tree, CARD_GAP),
                                   ("s", still_tree if still else None, CARD_GAP)):
                if tree is None:
                    continue
                for off in ((0.0, gap) if gaps else (0.0,)):
                    for a, b in tree.overlap(_tree(Q - nv * off, ff)):
                        if (key, a) in skip or (key == "s" and owner_of[still[a]] == owner_of[faces_ff[b]]):
                            continue                       # a card's own faces meet at its crease row
                        found.add((key, a))
            return found

        angles = [0.0] * len(CREASES)
        for k in range(len(CREASES)):
            if fixed is not None:
                angles[k] = fixed[f"{side}{k + 1}"]
                rep["turns"][f"{side}{k + 1}"] = angles[k]
                continue
            pre = frozenset(touched(base, k))
            rep["ignored"][f"{side}{k + 1}"] = len(pre)
            while angles[k] + STEP <= TURN[k] + 1e-6:
                tr = list(angles)
                tr[k] += STEP
                hit = touched(placed(tr), k, skip=pre)
                if hit:
                    rep["stopped_by"][f"{side}{k + 1}"] = sorted({_owner(key, a) for key, a in hit})[:12]
                    break
                angles = tr
            rep["turns"][f"{side}{k + 1}"] = angles[k]
        P[vs] = placed(angles)
    # the offsets back to the bind
    D = P - P0
    rest = np.array([v.co[:] for v in ob.data.vertices])
    vg = {g.index: g.name for g in ob.vertex_groups}
    turn = {pb.name: np.array((pb.matrix @ pb.bone.matrix_local.inverted()).to_3x3()) for pb in rig.pose.bones}
    delta = np.zeros_like(rest)
    moved = np.nonzero(np.abs(D).sum(1) > 1e-9)[0]
    for i in moved:
        A3 = np.zeros((3, 3))
        for g in ob.data.vertices[i].groups:
            if g.weight > 0 and vg[g.group] in turn:
                A3 += g.weight * turn[vg[g.group]]
        delta[i] = np.linalg.solve(A3, D[i])
    EP.clear(rig)
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    side_of = np.where(rest[:, 0] > 0, 1, -1)
    for s, nm in KEYS.items():
        kb = ob.shape_key_add(name=nm, from_mix=False)
        co = rest + delta * (side_of == s)[:, None]
        kb.data.foreach_set('co', co.ravel())
        kb.slider_min, kb.slider_max = 0.0, 1.0
        drv = kb.driver_add("value").driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name, var.type = "g", 'TRANSFORMS'
        tg = var.targets[0]
        tg.id = rig
        tg.bone_target = "WingFold" + ("L" if s > 0 else "R")
        tg.transform_type = 'LOC_Y'
        tg.transform_space = 'LOCAL_SPACE'
        drv.expression = f"g * {1.0 / EB.FOLD_GAUGE:g}"
    bpy.context.view_layer.update()
    rep["moved_verts"] = int(len(moved))
    rep["max_offset"] = round(float(np.linalg.norm(D, axis=1).max()), 4)
    return rep
