"""Build the golden eagle (2026-10-24): body -> rig -> weights -> UVs -> two painted presets, the two judging poses
(eagle_pose: perched, spread), checks and review renders; then (the same day, Daniel: "Lets accept the issue and
animate it") the clips (eagle_anim), their checks and renders, the export. Its own file, blender/eagle.blend (scene
Eagle, cameras EGL_*), built headless:

    blender.exe -b --factory-startup --python tools/creature_run.py -- eagle build check review closeups game presets
    blender.exe -b --factory-startup blender/eagle.blend --python tools/creature_run.py -- eagle paint review
    blender.exe -b --factory-startup blender/eagle.blend --python tools/creature_run.py -- eagle clips cards lowest trace chains feet sheets gameclips gifs export
    blender.exe -b --factory-startup --python tools/creature_run.py -- eagle reimport nosave

Steps (tools/creature_run.py calls them by name): model (body, rig, weights; debug colours, no paint), build (model +
UVs + paint), paint (the presets again on the built model), check (the overlap test and weights in the bind, perched
and spread poses), quick (Workbench looks at the poses), review (EEVEE: both poses from front, side, back, 3/4, above,
and the spread one from below), closeups (head, foot, the folded wing, wing tip), game (the game camera at 22 and 13 m,
x1 and x2.5, beside the wolf), uv (the layout over both textures), presets (golden and bald side by side),
compare (2026-10-24: fixed views for the before/after sheets, renders/eagle_cmp_*.png; the first pass's are in
renders/eagle_before/, the sheets come from tools/before_after.py), qhead and qfold (Workbench looks at the head and
the folded wing, debug colours, for tuning). The clips' steps: clips (key every clip), cards (the overlap test on every
frame of every clip), lowest (the lowest vertex per clip), trace (root motion as Unity plays it), chains (the jumps
where the clips hand over and at the loops' seams), feet (Walk's planted feet in the world), sheets (frame strips from
the side and above), gameclips (the game camera on the flight clips beside the wolf), gifs (frames for
tools/frames_to_gif.py), export, reimport (the FBX read back in an empty file). bend (2026-10-24, the hinged cards):
the cards bent onto what lies under them in the folded wing again (eagle_drape: the shape keys FoldL / FoldR) on the
built model, its UVs and paint kept; build and model do it too.
"""
import bpy, math, os
import numpy as np
from mathutils import Vector, Matrix
from beast_common import ROOT
import beast_scene, beast_rig, beast_review as RV
import eagle_body as EB

NAME, RIG, BODY = EB.NAME, EB.RIG, EB.BODY
P = "EGL_"
GROUND_Z = 0.0


def blend_path():
    return os.path.join(ROOT, "blender", "eagle.blend")


def setup_scene():
    scn = RV.new_scene(NAME, P)
    scn.camera = None
    return scn


def cam(name, loc, tgt, **kw):
    return RV.cam(bpy.context.scene, P + name, loc, tgt, **kw)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get(P + "Work")
    if lc is not None:
        lc.exclude = not on


# ----------------------------------------------------------------------------------------- debug colours
DBG = dict(fur=(0.30, 0.20, 0.12), beak=(0.75, 0.75, 0.70), jaw=(0.6, 0.6, 0.55), eye=(0.9, 0.55, 0.1),
           foot=(0.85, 0.70, 0.15), claw=(0.05, 0.05, 0.05), wing=(0.45, 0.32, 0.20))
KIND_DBG = {8: (0.36, 0.26, 0.18), 1: (0.12, 0.10, 0.09), 2: (0.30, 0.24, 0.18), 3: (0.50, 0.40, 0.28), 4: (0.70, 0.55, 0.35),
            5: (0.62, 0.50, 0.40), 6: (0.85, 0.80, 0.70), 7: (0.42, 0.38, 0.34)}


def debug_colours(ob):
    from beast_body import read_info, PART
    names = {v: k for k, v in PART.items()}
    part, _ = read_info(ob)
    fc = _fc(ob)
    col = np.zeros((len(part), 4), np.float32)
    col[:, 3] = 1
    for i, p in enumerate(part):
        nm = names.get(int(p), 'fur')
        if nm == 'feather':
            k = int(math.floor(fc[i, 2] + 1e-3))
            c = np.array(KIND_DBG.get(k, (1, 0, 1)))
            idx = int(round((fc[i, 2] - k) * 100))
            c = c * (0.85 + 0.15 * (idx % 2))
        else:
            c = DBG.get(nm, (1, 0, 1))
        col[i, :3] = c
    me = ob.data
    if "dbg" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["dbg"])
    att = me.color_attributes.new("dbg", 'FLOAT_COLOR', 'POINT')
    att.data.foreach_set('color', col.ravel())
    me.color_attributes.active_color = att
    return att


def _fc(ob):
    att = ob.data.attributes.get("root")
    buf = np.zeros(len(ob.data.vertices) * 3, np.float32)
    if att is not None:
        att.data.foreach_get('vector', buf)
    return buf.reshape(-1, 3)


# ----------------------------------------------------------------------------------------- the model
def build_model():
    setup_scene()
    work_layer(True)
    ob = bpy.data.objects.get(BODY)
    if ob is not None:
        bpy.data.objects.remove(ob, do_unlink=True)
    import eagle_drape
    EB.HINGE_T.clear()
    EB.HINGE_T.update(eagle_drape.crease_hinges())     # the hinge rows where the cards cross the fold's creases
    EB._FE.clear()
    body, acc, hi = EB.build_body()
    rep = {"tris": EB.tri_report(body), "hinged_cards": len(EB.HINGE_T)}
    import zwolf_body
    rep["tidy"] = dict(zwolf_body.TIDY)
    rig = beast_rig.build_armature(EB.rest_bones(), name=RIG, coll_name=P + "Rig")
    _bone_collections(rig)
    rep["bones"] = len(rig.data.bones)
    rep["weights"] = EB.skin(body, rig, acc)
    rep["drape"] = _drape(body, rig)
    debug_colours(body)
    work_layer(False)
    rig.hide_render = True
    return body, rig, rep


def _bone_collections(rig):
    ad = rig.data
    cols = {}
    for nm in ("Wings", "Feathers", "TailFan", "Toes"):
        cols[nm] = ad.collections.get(nm) or ad.collections.new(nm)
    body = ad.collections.get("Body")
    for b in ad.bones:
        n = b.name
        key = None
        if n.startswith(("WingP", "WingSec", "WingTert", "WingAlula", "Scap")):
            key = "Feathers"
        elif n.startswith("Wing"):
            key = "Wings"
        elif n.startswith("TailF"):
            key = "TailFan"
        elif n.startswith(("Toe", "Tarsus")):
            key = "Toes"
        if key:
            for c in b.collections[:]:
                c.unassign(b)
            cols[key].assign(b)
            b.color.palette = 'THEME03' if n.endswith("L") else 'THEME04'


def model():
    body, rig, rep = build_model()
    return rep


def _drape(body, rig):
    """The folded wing creased (eagle_drape) -> the summary; it and every card's hinges -> renders/eagle_drape.json"""
    import json
    import eagle_drape
    rep = eagle_drape.drape(body, rig)
    rep["hinge_t"] = {k: list(v) for k, v in EB.HINGE_T.items()}
    with open(os.path.join(ROOT, "renders", "eagle_drape.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    return {k: v for k, v in rep.items() if k != "hinge_t"}


def _fill_hinges():
    import eagle_drape
    EB.HINGE_T.clear()
    EB.HINGE_T.update(eagle_drape.crease_hinges())     # as the model was built (the rows must be there already)
    EB._FE.clear()


def bend():
    """The drape again on the built model (UVs, paint and the undersides kept: they are dropped, the keys made on the
    top layer, and copied again)."""
    body, rig = bpy.data.objects[BODY], bpy.data.objects[RIG]
    _fill_hinges()
    work_layer(True)
    _one_layer(body)
    rep = _drape(body, rig)
    rep["layers"] = _two_layers(body)
    rep["tris"] = EB.tri_report(body)
    work_layer(False)
    return rep


# ----------------------------------------------------------------------------------------- checks
def _posed(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    M = np.array(ob.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return co, polys


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


def _card_names(ob, polys, comp):
    fc = _fc(ob)
    rest = np.array([v.co[:] for v in ob.data.vertices])
    inv = {v: k for k, v in EB.KIND.items()}
    letter = dict(primary="P", secondary="S", tertial="T", gcovert="G", pcovert="PC", alula="A", tail="F",
                  scapular="SC")
    names = {}
    for p, c in zip(polys, comp):
        if c in names:
            continue
        i = p[0]
        k = int(math.floor(fc[i, 2] + 1e-3))
        idx = int(round((fc[i, 2] - k) * 100))
        side = "L" if rest[list(p)].mean(0)[0] > 0 else "R"
        names[c] = f"{letter.get(inv.get(k, ''), '?')}{idx}{side}"
    return names


ROOT_T = {1: 0.14, 2: 0.14, 3: 0.16, 4: 0.45, 5: 0.45, 6: 0.35, 7: 0.30, 8: 0.25}    # by kind: the root part, inside flesh


def overlap_report(limit=12):
    """In the current pose: card faces (the upper layer only) beyond their root part (ROOT_T: the quills sit in the
    flesh or under the tail coverts) crossing the body (fused body, beak, eyes, feet) or the wing's flesh; cards
    crossing other cards; the closest approach of the cards beyond their roots to the fused body (negative = inside)."""
    from mathutils.bvhtree import BVHTree
    from beast_body import read_info, PART
    ob = bpy.data.objects[BODY]
    part, _ = read_info(ob)
    co, polys = _posed(ob)
    back = ob.data.attributes.get("back")
    bk = np.zeros(len(polys), bool)
    if back is not None:
        buf = np.zeros(len(polys), np.int32)
        back.data.foreach_get('value', buf)
        bk = buf > 0
    fc = _fc(ob)
    fpart = np.array([part[p[0]] for p in polys])
    card = (fpart == PART['feather']) & ~bk
    flesh = fpart == PART['wing']
    solid = ~card & ~flesh & ~bk & (fpart != PART['feather'])
    comp = np.array(_components(polys, len(co)))
    ci = np.nonzero(card)[0]
    names = _card_names(ob, [polys[i] for i in ci], comp[ci])
    V = [Vector(c) for c in co]

    def bvh(idx):
        return BVHTree.FromPolygons(V, [polys[i] for i in idx], all_triangles=False), idx
    bc, ic = bvh(ci)
    bs, is_ = bvh(np.nonzero(solid)[0])
    bf, if_ = bvh(np.nonzero(flesh)[0])
    tmax = np.array([fc[list(polys[i]), 1].max() for i in ci])
    kind = np.floor(fc[:, 2] + 1e-3).astype(int)
    rt = np.array([ROOT_T.get(int(kind[polys[i][0]]), 0.14) for i in ci])
    out = {}
    cen = lambda f: sum((V[v] for v in polys[f]), Vector()) / len(polys[f])
    t_at = lambda f, p: _t_on_card(V, polys[f], fc, p)
    for key, tree, idx in (("card_body", bs, is_), ("card_flesh", bf, if_)):
        hits, where, cnt = {}, [], 0
        for a, b in bc.overlap(tree):
            t = t_at(ic[a], cen(idx[b]))
            if t <= rt[a]:
                continue
            cnt += 1
            n = names[comp[ic[a]]]
            hits[n] = hits.get(n, 0) + 1
            if len(where) < 6:
                pn = {v_: k_ for k_, v_ in PART.items()}.get(int(fpart[idx[b]]), "?")
                where.append((n, round(t, 2), pn, [round(c, 3) for c in cen(idx[b])]))
        out[key] = (cnt, sorted(hits.items(), key=lambda kv: -kv[1])[:limit], where)
    hits, cnt, near_root = {}, 0, 0
    for a, b in bc.overlap(bc):
        ca, cb = comp[ic[a]], comp[ic[b]]
        if ca == cb or a > b:
            continue
        if t_at(ic[a], cen(ic[b])) <= rt[a] and t_at(ic[b], cen(ic[a])) <= rt[b]:
            near_root += 1
            continue
        cnt += 1
        k = tuple(sorted((names[ca], names[cb])))
        hits[k] = hits.get(k, 0) + 1
    out["card_card"] = (cnt, sorted(hits.items(), key=lambda kv: -kv[1])[:limit])
    out["card_card_roots"] = near_root
    # card vertices beyond their roots inside the fused body (ray parity, three rays voting): count, deepest
    fur = [i for i in range(len(polys)) if fpart[i] == PART['fur']]
    bb = BVHTree.FromPolygons(V, [polys[i] for i in fur])
    vname = {}
    for j, i in enumerate(ci):
        for v in polys[i]:
            if fc[v, 1] > rt[j]:
                vname[v] = names[comp[i]]
    inside, worst = {}, (0.0, None)
    for v in vname:
        if _inside(bb, V[v]):
            d = (V[v] - bb.find_nearest(V[v])[0]).length
            inside[vname[v]] = inside.get(vname[v], 0) + 1
            if d > worst[0]:
                worst = (d, v)
    v = worst[1]
    out["card_verts_inside"] = (sum(inside.values()), round(float(worst[0]), 4), vname.get(v),
                                sorted(inside.items(), key=lambda kv: -kv[1])[:limit])
    return out


def _t_on_card(V, face, fc, p):
    """The card's own t (0 root .. 1 tip) at the point of `face` nearest to p."""
    from mathutils.geometry import closest_point_on_tri
    best = (9.0, 0.0)
    for tri in ((0, 1, 2), (0, 2, 3))[:len(face) - 2]:
        A, B, C = (V[face[i]] for i in tri)
        q = closest_point_on_tri(p, A, B, C)
        d = (q - p).length
        if d < best[0]:
            v0, v1, v2 = B - A, C - A, q - A
            d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
            den = d00 * d11 - d01 * d01 or 1e-12
            w1 = (d11 * d20 - d01 * d21) / den
            w2 = (d00 * d21 - d01 * d20) / den
            ts = [fc[face[i], 1] for i in tri]
            best = (d, (1 - w1 - w2) * ts[0] + w1 * ts[1] + w2 * ts[2])
    return float(best[1])


_RAYS = (Vector((0.0, 0.0, 1.0)), Vector((0.577, 0.577, -0.577)), Vector((-0.6, -0.2, 0.775)).normalized())


def _inside(bvh, p):
    votes = 0
    for d in _RAYS:
        o, n = Vector(p), 0
        for _ in range(64):
            hit = bvh.ray_cast(o, d, 10.0)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-5
        votes += n % 2
    return votes >= 2


def check():
    import eagle_pose as EP
    out = {"weights": beast_rig.weight_report(bpy.data.objects[BODY]), "tris": EB.tri_report(bpy.data.objects[BODY])}
    for name in ("bind", "perched", "spread"):
        EP.use(name)
        out[name] = overlap_report()
        from beast_body import read_info, PART
        co = _posed(bpy.data.objects[BODY])[0]
        i = int(np.argmin(co[:, 2]))
        pn = {v: k for k, v in PART.items()}.get(int(read_info(bpy.data.objects[BODY])[0][i]), "?")
        out[name]["lowest"] = (round(float(co[i, 2]), 4), pn)
    EP.clear()
    return out


# ----------------------------------------------------------------------------------------- quick looks
def _posed_point(bone, local=(0, 0, 0)):
    rig = bpy.data.objects[RIG]
    pb = rig.pose.bones[bone]
    return rig.matrix_world @ (pb.matrix @ Vector(local))


def quick(res=700):
    """Workbench (debug colours) looks at bind, perched and spread from a few sides -> renders/eagle_q_<pose>.png"""
    import eagle_pose as EP
    scn = setup_scene()
    sh = scn.display.shading
    out = []
    views = {
        "bind": [("Top", (0, 0.05, 6), (0, 0.0501, 0.35), dict(ortho=2.3)),
                 ("34", (2.0, -2.6, 1.9), (0, 0.0, 0.38), dict(lens=40)),
                 ("Side", (6, 0.05, 0.38), (0, 0.05, 0.38), dict(ortho=1.1)),
                 ("Head", (3, -0.36, 0.39), (0, -0.36, 0.39), dict(ortho=0.24)),
                 ("Head34", (0.35, -0.62, 0.47), (0, -0.36, 0.395), dict(lens=60))],
        "folded": [("Side", (6, 0.05, 0.36), (0, 0.05, 0.36), dict(ortho=1.0)),
                   ("Top", (0, 0.05, 6), (0, 0.0501, 0.3), dict(ortho=1.0)),
                   ("Rear", (0, 4, 0.40), (0, 0, 0.36), dict(ortho=0.6)),
                   ("34", (1.2, -1.4, 1.0), (0, 0.02, 0.35), dict(lens=50))],
        "perched": [("Side", (6, -0.02, 0.36), (0, -0.02, 0.36), dict(ortho=0.95)),
                    ("34", (1.3, -1.6, 0.85), (0, 0.0, 0.33), dict(lens=50)),
                    ("Rear", (-1.0, 1.7, 1.0), (0, 0.05, 0.33), dict(lens=50)),
                    ("Top", (0, 0.0, 6), (0, 0.0001, 0.3), dict(ortho=0.95))],
        "spread": [("Top", (0, 0.05, 9), (0, 0.0501, 1.25), dict(ortho=2.3)),
                   ("34", (2.2, -2.8, 2.6), (0, 0.0, 1.25), dict(lens=40)),
                   ("Front", (0, -9, 1.3), (0, 0, 1.3), dict(ortho=2.3))],
    }
    for name, vs in views.items():
        EP.use(name)
        row = []
        for v, loc, tgt, kw in vs:
            cam("CAM_Q", loc, tgt, **kw)
            path = beast_scene.shot(P + "CAM_Q", "_eq_tile", res=res, color='VERTEX')
            row.append(RV.load(path))
        out.append(RV.save(np.concatenate(row, axis=1), f"eagle_q_{name}"))
    EP.clear()
    return out


def qfold(res=600):
    """Workbench (debug colours): the folded wing, perched (side, back, above, 3/4 back) and in the body's own axes
    (folded: side, above) -> renders/eagle_q_fold.png"""
    import eagle_pose as EP
    setup_scene()
    row = []
    views = {"perched": [((3, -0.02, 0.35), (0, 0.02, 0.35), dict(ortho=0.62)),
                         ((0, 3, 0.62), (0, 0.03, 0.36), dict(ortho=0.62)),
                         ((0, 0.06, 3), (0, 0.0, 0.33), dict(ortho=0.62)),
                         ((0.9, 0.9, 1.1), (0.0, 0.05, 0.36), dict(lens=50))],
             "folded": [((3, 0.05, 0.36), (0, 0.05, 0.36), dict(ortho=0.8)),
                        ((0, 0.05, 3), (0, 0.0501, 0.33), dict(ortho=0.8))]}
    for pose, vs in views.items():
        EP.use(pose)
        for loc, tgt, kw in vs:
            cam("CAM_Q", loc, tgt, **kw)
            row.append(RV.load(beast_scene.shot(P + "CAM_Q", "_eq_tile", res=res, color='VERTEX')))
    EP.clear()
    return RV.save(np.concatenate(row, axis=1), "eagle_q_fold")


def qhead(res=600):
    """Workbench (debug colours): the head in the bind pose (profile, front, 3/4, above) and perched (profile) ->
    renders/eagle_q_head.png"""
    import eagle_pose as EP
    scn = setup_scene()
    row = []
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))
    for pose in ("bind", "perched"):
        EP.use(pose)
        c, fw = _head_centre()
        views = [(c + X * 2.0, dict(ortho=0.17))]
        if pose == "bind":
            views += [(c + fw * 2.0 + Z * 0.2, dict(ortho=0.17)),
                      (c + (X * 0.75 + fw * 0.85 + Z * 0.35).normalized() * 0.6, dict(lens=70)),
                      (c + Z * 2.0 - fw * 0.05, dict(ortho=0.17))]
        for loc, kw in views:
            cam("CAM_Q", tuple(loc), tuple(c), **kw)
            row.append(RV.load(beast_scene.shot(P + "CAM_Q", "_eq_tile", res=res, color='VERTEX')))
    EP.clear()
    return RV.save(np.concatenate(row, axis=1), "eagle_q_head")


# ----------------------------------------------------------------------------------------- paint and the undersides
BACK = "back"          # int face attribute: 1 on the cards' undersides (copied, flipped faces)
# (2026-10-24) no underside for the cards whose undersides are never seen: the greater and primary coverts (the
# remiges under them, spread or folded) and the scapulars (on the back, over the wing's root): 280 triangles
NO_UNDERSIDE = (4, 5, 8)


def _one_layer(ob):
    """Drop the undersides (faces with BACK = 1 and their vertices): back to one sheet per card for the bakes."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get(BACK)
    if lay is not None:
        back = [f for f in bm.faces if f[lay]]
        verts = {v for f in back for v in f.verts}
        bmesh.ops.delete(bm, geom=back, context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[v for v in verts if not v.link_faces], context='VERTS')
        bm.faces.layers.int.remove(lay)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _two_layers(ob):
    """Every card gets an underside of its own (the bat's fix, HANDOFF "Bat wing underside"): its faces copied onto
    new vertices (same UVs, weights, info, feather coordinates), flipped and tagged BACK; the material culls back
    faces, so each side is lit with its own normal in any shader (URP Lit drawn two-sided lights the underside with
    the top's normal)."""
    import bmesh
    from beast_body import read_info, PART
    _one_layer(ob)
    part, _ = read_info(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.new(BACK)
    kind = np.floor(_fc(ob)[:, 2] + 1e-3).astype(int)
    faces = [f for f in bm.faces if part[f.verts[0].index] == PART['feather']
             and kind[f.verts[0].index] not in NO_UNDERSIDE]
    edges = {e for f in faces for e in f.edges}
    verts = {v for f in faces for v in f.verts}
    ret = bmesh.ops.duplicate(bm, geom=list(verts) + list(edges) + faces)
    new = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.reverse_faces(bm, faces=new)
    for f in new:
        f[lay] = 1
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return {"faces": len(ob.data.polygons), "back": len(new)}


def _drop_debug(ob):
    me = ob.data
    if "dbg" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["dbg"])


def build():
    """Model, UVs, both presets painted, the undersides; M_Eagle on the body."""
    import eagle_paint as EPt
    body, rig, rep = build_model()
    work_layer(True)
    _drop_debug(body)
    EPt.unwrap(body)
    rep["textures"], rep["coverage"] = EPt.build_textures(body)
    rep["uv_overlap"] = RV.uv_overlap([body])[0]
    rep["layers"] = _two_layers(body)
    rep["tris"] = EB.tri_report(body)
    rep["weights"] = beast_rig.weight_report(body)
    work_layer(False)
    uv()
    return rep


def paint():
    """Both presets again on the built model (same UVs)."""
    import eagle_paint as EPt
    body = bpy.data.objects[BODY]
    work_layer(True)
    _one_layer(body)
    paths, cov = EPt.build_textures(body)
    _two_layers(body)
    work_layer(False)
    uv()
    return paths


def uv():
    import eagle_paint as EPt
    from beast_paint import TEX_DIR
    body = bpy.data.objects[BODY]
    out = []
    for name, tex in EPt.TEX.items():
        out.append(RV.uv_png(body, f"eagle_uv_{name}", tex=os.path.join(TEX_DIR, tex + ".png")))
    out.append(RV.uv_png(body, "eagle_uv_plain"))
    a = [RV.load(os.path.join(TEX_DIR, EPt.TEX[k] + ".png")) for k in ('golden', 'bald')]
    out.append(RV.save(np.concatenate(a, axis=1), "eagle_textures"))
    return out


# ----------------------------------------------------------------------------------------- review renders
PERCHED_VIEWS = {"front": ((0, -6, 0.33), (0, 0, 0.33), dict(ortho=0.85)),
                 "side": ((6, -0.02, 0.33), (0, -0.02, 0.33), dict(ortho=0.85)),
                 "back": ((0, 6, 0.36), (0, 0, 0.36), dict(ortho=0.85)),
                 "34": ((1.25, -1.55, 0.85), (0, -0.02, 0.32), dict(lens=50)),
                 "34back": ((-1.2, 1.5, 1.0), (0, 0.02, 0.33), dict(lens=50)),
                 "above": ((0, -0.02, 6), (0, -0.0199, 0.3), dict(ortho=0.85))}
SPREAD_VIEWS = {"front": ((0, -9, 1.27), (0, 0, 1.27), dict(ortho=2.3)),
                "side": ((9, 0.02, 1.25), (0, 0.02, 1.25), dict(ortho=1.2)),
                "back": ((0, 9, 1.35), (0, 0, 1.30), dict(ortho=2.3)),
                "34": ((2.4, -3.0, 2.5), (0, 0.03, 1.22), dict(lens=40)),
                "above": ((0, 0.02, 9), (0, 0.0201, 1.25), dict(ortho=2.3)),
                "below": ((0, 0.02, -9), (0, 0.0201, 1.25), dict(ortho=2.3))}


def _ground(on):
    g = bpy.data.objects.get("Ground")
    if g is not None:
        g.hide_render = not on


def review(res=900):
    """EEVEE: perched and spread from every side -> renders/eagle_<pose>_<view>.png and one sheet per pose."""
    import eagle_pose as EP
    setup_scene()
    RV.show_wolf(False)
    out = []
    for pose, views in (("perched", PERCHED_VIEWS), ("spread", SPREAD_VIEWS)):
        EP.use(pose)
        tiles = []
        for v, (loc, tgt, kw) in views.items():
            cam("CAM_R", loc, tgt, **kw)
            _ground(v != "below")
            p = RV.shot(P + "CAM_R", f"eagle_{pose}_{v}", res=res)
            out.append(p)
            tiles.append(RV.load(p)[::2, ::2])
        _ground(True)
        out.append(RV.save(np.concatenate(tiles, axis=1), f"eagle_{pose}"))
    EP.clear()
    return out


def _head_cam(name, side, lens=None, ortho=None, dist=1.2, up=0.0, fwd=0.0):
    """A camera on the posed head: from its left side (+X), or 3/4 from the front-left and above."""
    rig = bpy.data.objects[RIG]
    pb = rig.pose.bones["Head"]
    M = rig.matrix_world @ pb.matrix
    c = M @ Vector((0, 0.07, 0.008))                  # bone space: Y along the head toward the beak
    fw = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    left = Vector((1, 0, 0))
    if side == "profile":
        loc = c + left * dist
    else:
        loc = c + (left * 0.75 + fw * 0.85 + Vector((0, 0, 0.35))).normalized() * dist
    kw = dict(ortho=ortho) if ortho else dict(lens=lens or 60)
    return cam(name, tuple(loc), tuple(c + Vector((0, 0, up)) + fw * fwd), **kw)


def closeups(res=900):
    """The head (profile and 3/4, perched), the left foot and talons, the folded wing (perched: side, back 3/4), the
    wing tip's fingers from above and below (spread)."""
    import eagle_pose as EP
    setup_scene()
    RV.show_wolf(False)
    out = []
    EP.use("perched")
    _head_cam("CAM_HeadSide", "profile", ortho=0.22, dist=2.0)
    out.append(RV.shot(P + "CAM_HeadSide", "eagle_head_profile", res=res))
    _head_cam("CAM_Head34", "34", lens=70, dist=0.75)
    out.append(RV.shot(P + "CAM_Head34", "eagle_head_34", res=res))
    cam("CAM_Foot", (0.34, -0.36, 0.16), (0.078, -0.035, 0.03), lens=55)
    out.append(RV.shot(P + "CAM_Foot", "eagle_foot", res=res))
    cam("CAM_Foot2", (0.30, 0.05, 0.05), (0.075, -0.025, 0.025), lens=60)
    out.append(RV.shot(P + "CAM_Foot2", "eagle_foot_side", res=res))
    cam("CAM_Fold", (3, -0.02, 0.35), (0, 0.02, 0.35), ortho=0.62)
    out.append(RV.shot(P + "CAM_Fold", "eagle_fold_side", res=res))
    cam("CAM_Fold34", (0.9, 0.9, 1.1), (0.0, 0.05, 0.36), lens=50)
    out.append(RV.shot(P + "CAM_Fold34", "eagle_fold_back34", res=res))
    EP.use("spread")
    tip = (0.80, -0.06, 0.43 + EP.LIFT)
    cam("CAM_TipTop", (tip[0], tip[1], tip[2] + 3), (tip[0], tip[1] + 0.0001, tip[2]), ortho=0.75)
    out.append(RV.shot(P + "CAM_TipTop", "eagle_wingtip_above", res=res))
    _ground(False)
    cam("CAM_TipBelow", (tip[0], tip[1], tip[2] - 3), (tip[0], tip[1] + 0.0001, tip[2]), ortho=0.75)
    out.append(RV.shot(P + "CAM_TipBelow", "eagle_wingtip_below", res=res))
    _ground(True)
    EP.clear()
    return out


# ----------------------------------------------------------------------------------------- before / after views
def _head_centre():
    """The middle of the posed head bone (poll -> beak tip) and the head's level forward direction."""
    rig = bpy.data.objects[RIG]
    pb = rig.pose.bones["Head"]
    M = rig.matrix_world @ pb.matrix
    c = M @ Vector((0, pb.bone.length * 0.5, 0.004))
    fw = M.to_3x3() @ Vector((0, 1, 0))
    return c, Vector((fw.x, fw.y, 0.0)).normalized()


def compare(res=900):
    """Fixed views for the before/after sheets (2026-10-24 revision) -> renders/eagle_cmp_<view>.png: the head
    (perched; profile, 3/4, front, above, golden and bald), the spread wing (above, the tip, below), the folded wing
    (perched; side, back, above, 3/4 back) and the legs (perched; side, 3/4 front)."""
    import eagle_pose as EP
    import eagle_paint as EPt
    setup_scene()
    RV.show_wolf(False)
    out = []
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))

    def shoot(name, loc, tgt, **kw):
        cam("CAM_C", tuple(loc), tuple(tgt), **kw)
        out.append(RV.shot(P + "CAM_C", "eagle_cmp_" + name, res=res))

    EP.use("perched")
    c, fw = _head_centre()
    for preset in ('golden', 'bald'):
        EPt.use_preset(preset)
        sfx = "" if preset == 'golden' else "_bald"
        shoot("head_profile" + sfx, c + X * 2.0, c, ortho=0.20)
        shoot("head_34" + sfx, c + (X * 0.75 + fw * 0.85 + Z * 0.35).normalized() * 0.75, c, lens=70)
        if preset == 'golden':
            shoot("head_front", c + fw * 2.0 + Z * 0.30, c, ortho=0.20)
            shoot("head_above", c + Z * 2.0 - fw * 0.05, c, ortho=0.20)
    EPt.use_preset('golden')
    shoot("fold_side", (3, -0.02, 0.35), (0, 0.02, 0.35), ortho=0.62)
    shoot("fold_back", (0, 3, 0.62), (0, 0.03, 0.36), ortho=0.62)
    shoot("fold_above", (0, 0.06, 3), (0, -0.0, 0.33), ortho=0.62)
    shoot("fold_34back", (0.9, 0.9, 1.1), (0.0, 0.05, 0.36), lens=50)
    shoot("legs_side", (2, -0.02, 0.15), (0, -0.02, 0.15), ortho=0.36)
    shoot("legs_34", (0.55, -0.75, 0.32), (0.0, -0.02, 0.13), lens=50)
    EP.use("spread")
    loc, tgt, kw = SPREAD_VIEWS["above"]
    shoot("spread_above", loc, tgt, **kw)
    tip = (0.80, -0.06, 0.43 + EP.LIFT)
    shoot("wingtip_above", (tip[0], tip[1], tip[2] + 3), (tip[0], tip[1] + 0.0001, tip[2]), ortho=0.75)
    _ground(False)
    loc, tgt, kw = SPREAD_VIEWS["below"]
    shoot("spread_below", loc, tgt, **kw)
    shoot("wingtip_below", (tip[0], tip[1], tip[2] - 3), (tip[0], tip[1] + 0.0001, tip[2]), ortho=0.75)
    _ground(True)
    EP.clear()
    return out


# ----------------------------------------------------------------------------------------- the game camera
def _game_cam(name, az, target, dist):
    a, p = math.radians(az), math.radians(RV.GAME['pitch'])
    t = Vector(target)
    loc = t + Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * dist
    c = beast_scene._cam(bpy.context.scene, P + name, tuple(loc), tuple(t))
    c.data.sensor_fit = 'VERTICAL'
    c.data.lens = c.data.sensor_height / 2 / math.tan(math.radians(RV.GAME['fov']) / 2)
    return c


def game(res=620, crop=220, k=3):
    """The game camera (50 deg pitch, fov 30) at 22 m and 13 m, from the front-left (az 30) and the back-right
    (az 210), the eagle at x1 and x2.5 beside the grey wolf (appended from blender/beasts.blend): one sheet per pose
    and scale (top row 22 m, bottom row 13 m), each tile the middle of the game frame blown up x3 ->
    renders/eagle_game_<pose>_x<s>.png; the whole 22 m frames side by side -> renders/eagle_game_frames.png."""
    import eagle_pose as EP
    setup_scene()
    RV.add_wolf(P)
    RV.show_wolf(True)
    ground = bpy.data.objects.get("Ground")
    if ground is not None:
        ground.scale = (5, 5, 1)                       # the 12 m disc's edge showed in the x2.5 frames
    rig = bpy.data.objects[RIG]
    wolf = bpy.data.objects.get("WolfRig")
    out, frames = [], []
    for pose in ("perched", "spread"):
        EP.use(pose)
        for sc in (1.0, 2.5):
            rig.scale = (sc, sc, sc)
            wx = (1.25 if pose == "perched" else 1.6) * (1.0 if sc == 1.0 else 2.0)
            if wolf is not None:
                wolf.location = (wx, 0.35, 0.0)
            bpy.context.view_layer.update()
            body_z = _posed_point("Spine1").z
            tgt = (wx * 0.5, 0.1, 0.5 * (body_z + 0.45))       # between the eagle's body and the wolf's back
            cr = int(crop * (1.0 if sc == 1.0 else 1.9)) // 2 * 2
            kk = k * crop / cr
            rows = []
            for dist in (22.0, 13.0):
                row = []
                for az in (30, 210):
                    _game_cam("CAM_G", az, tgt, dist)
                    p = RV.shot(P + "CAM_G", f"_eg_{pose}_{sc:g}_{int(dist)}_{az}", res=res)
                    a = RV.load(p)
                    if dist == 22.0 and az == 30:
                        frames.append(a)
                    c0 = (res - cr) // 2
                    a = a[c0:c0 + cr, c0:c0 + cr]
                    ii = np.minimum((np.arange(crop * k) / kk).astype(int), cr - 1)
                    row.append(a[ii][:, ii])
                rows.append(np.concatenate(row, axis=1))
            out.append(RV.save(np.concatenate(rows[::-1], axis=0), f"eagle_game_{pose}_x{sc:g}"))
    rig.scale = (1, 1, 1)
    if ground is not None:
        ground.scale = (1, 1, 1)
    RV.show_wolf(False)
    EP.clear()
    out.append(RV.save(np.concatenate(frames, axis=1), "eagle_game_frames"))
    return out


def presets(res=700):
    """Both paint presets side by side: perched 3/4, the head, spread from above -> renders/eagle_presets.png"""
    import eagle_pose as EP
    import eagle_paint as EPt
    setup_scene()
    RV.show_wolf(False)
    rows = []
    for name in ('golden', 'bald'):
        EPt.use_preset(name)
        row = []
        EP.use("perched")
        loc, tgt, kw = PERCHED_VIEWS["34"]
        cam("CAM_P", loc, tgt, **kw)
        row.append(RV.load(RV.shot(P + "CAM_P", "_ep_tile", res=res)))
        _head_cam("CAM_PH", "34", lens=70, dist=0.75)
        row.append(RV.load(RV.shot(P + "CAM_PH", "_ep_tile", res=res)))
        EP.use("spread")
        loc, tgt, kw = SPREAD_VIEWS["above"]
        cam("CAM_P", loc, tgt, **kw)
        row.append(RV.load(RV.shot(P + "CAM_P", "_ep_tile", res=res)))
        rows.append(np.concatenate(row, axis=1))
    EPt.use_preset('golden')
    EP.clear()
    return RV.save(np.concatenate(rows[::-1], axis=0), "eagle_presets")


# ----------------------------------------------------------------------------------------- clips (2026-10-24)
def anim():
    import eagle_anim
    return eagle_anim


def clips():
    A = anim()
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


GROUND_CLIPS = ("Idle", "Walk", "Screech", "Hit", "Death", "TakeOff", "Land")
FEATHER_SINK = 0.003            # a clip's lowest card may go this far under the ground with the creases


def _feather_low(names):
    """The lowest card vertex (world z) over every frame of each clip named -> {clip: (z, frame)}."""
    from beast_body import read_info, PART
    A = anim()
    scn = bpy.context.scene
    ob = bpy.data.objects[BODY]
    card = read_info(ob)[0] == PART['feather']
    out = {}
    for n in names:
        A.use(n)
        lo = (9.0, 0)
        for f in range(int(bpy.data.actions[A.action_name(n)]["frames"]) + 1):
            scn.frame_set(f)
            z = float(_posed(ob)[0][card, 2].min())
            if z < lo[0]:
                lo = (round(z, 4), f)
        out[n] = lo
    A.clear()
    return out


def fold_fit(steps=5):
    """The creases at the largest turns the perched pose allows (eagle_drape), then, per clip that folds the wing, the
    largest share of them (eagle_anim.GAUGE: the gauge slides that much of the lay) for which every frame is clean: no
    card through the body or another card, none inside the body, no clip's lowest card more than FEATHER_SINK under
    the ground (or under where it was without the creases, if lower). 2026-10-24: one share for the whole model came to
    nothing (the legs meet the curled wing in Walk at an eighth of the first crease, and the wingtips skim the ground in
    the crouch, the touchdown and the fall). Re-keys the clips. -> the turns, the shares, what was tried."""
    import eagle_drape
    A = anim()
    body, rig = bpy.data.objects[BODY], bpy.data.objects[RIG]
    _fill_hinges()
    work_layer(True)
    _one_layer(body)
    rep = eagle_drape.drape(body, rig)
    A.GAUGE.clear()
    tried, share = {}, {}
    for n in GROUND_CLIPS:
        A.GAUGE[n] = 0.0
        A.build_clip(n)
        z0 = _feather_low([n])[n][0]
        floor = min(z0, 0.0) - FEATHER_SINK
        tried[n] = []

        def clean(k):
            A.GAUGE[n] = round(k, 4)
            A.build_clip(n)
            bad = cards([n])[n]["bad"]
            low = _feather_low([n])[n]
            tried[n].append((round(k, 4), bad, low))
            return not bad and low[0] >= floor
        if clean(1.0):
            k = 1.0
        else:
            lo, hi = 0.0, 1.0
            for _ in range(steps):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if clean(mid) else (lo, mid)
            k = lo
        A.GAUGE[n] = round(k, 4)
        A.build_clip(n)
        share[n] = A.GAUGE[n]
    A.clear()
    rep.update(share=share, tried=tried)
    import json
    with open(os.path.join(ROOT, "renders", "eagle_fold_fit.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    rep["layers"] = _two_layers(body)
    work_layer(False)
    return rep


def cards(names=None):
    """Every frame of every clip through overlap_report: frames with a card through the body, through another card,
    or with card vertices inside the body (all must be 0), and the largest count of cards against the wing's own
    flesh (hidden under the cards when folded: 296 perched)."""
    A = anim()
    scn = bpy.context.scene
    out = {}
    for n in names or A.CLIPS:
        A.use(n)
        N = int(bpy.data.actions[A.action_name(n)]["frames"])
        bad, flesh = [], (0, 0)
        for f in range(N + 1):
            scn.frame_set(f)
            r = overlap_report(limit=3)
            b, c, i = r["card_body"][0], r["card_card"][0], r["card_verts_inside"][0]
            if r["card_flesh"][0] > flesh[0]:
                flesh = (r["card_flesh"][0], f)
            if b or c or i:
                bad.append((f, b, c, i, r["card_body"][1][:2], r["card_card"][1][:2], r["card_body"][2][:2]))
        out[n] = dict(frames=N + 1, bad=len(bad), flesh_max=flesh, first=bad[:5])
    A.clear()
    return out


def lowest():
    """The lowest vertex (world z) per clip, every frame, and the part it belongs to; the ground clips' feet must not
    sink in."""
    from beast_body import read_info, PART
    A = anim()
    scn = bpy.context.scene
    ob = bpy.data.objects[BODY]
    part = read_info(ob)[0]
    names = {v: k for k, v in PART.items()}
    out = {}
    for n in A.CLIPS:
        A.use(n)
        N = int(bpy.data.actions[A.action_name(n)]["frames"])
        lo = (9.0, 0, "")
        for f in range(N + 1):
            scn.frame_set(f)
            co = _posed(ob)[0]
            i = int(np.argmin(co[:, 2]))
            if co[i, 2] < lo[0]:
                lo = (round(float(co[i, 2]), 4), f, names.get(int(part[i]), "?"))
        out[n] = lo
    A.clear()
    return out


def trace():
    """The moving clips as Unity plays them (beast_review.motion_trace): the loops over three loops (the seam's step
    against the steps inside), the one-shots' travel."""
    A = anim()
    out = {}
    for c in ("Walk", "Fly", "Glide", "TakeOff", "Dive", "Land"):
        loop = bpy.data.actions[A.action_name(c)]["loop"]
        r = RV.motion_trace(A, RIG, c, bones=("Head", "WingP9L", "TarsusR"), loops=3 if loop else 2)
        out[c] = r if loop else {k: r[k] for k in ("frames", "travel", "speed", "motion_turn_deg")}
    return out


def chains():
    """The clips that hand over to each other (eagle_anim.CHAINS) and the loops' seams: the largest jump of a bone's
    head (mm) and turn (deg) between the last frame of one and the first of the next (root space), and the root's
    speed on both sides (m/s)."""
    A = anim()
    out = {}
    cache = {}

    def frames(n):
        if n not in cache:
            N, fn, loop = A.CLIPS[n]()
            cache[n] = (N, fn)
        return cache[n]
    pairs = list(A.CHAINS) + [(n, n) for n in ("Idle", "Walk", "Fly", "Glide")]
    for a, b in pairs:
        Na, fa = frames(a)
        Nb, fb = frames(b)
        pa, pb = fa(Na), fb(0)
        ma, mb = A.pose_matrices(pa), A.pose_matrices(pb)
        dpos = max((ma[k].to_translation() - mb[k].to_translation()).length for k in ma if k != "Motion")
        ang = lambda q: min(math.degrees(q.angle), 360 - math.degrees(q.angle))
        drot = max(ang(ma[k].to_quaternion().rotation_difference(mb[k].to_quaternion())) for k in ma if k != "Motion")
        va = (fa(Na).root - fa(Na - 1).root).length * A.FPS
        vb = (fb(1).root - fb(0).root).length * A.FPS
        worst = max(((ma[k].to_translation() - mb[k].to_translation()).length, k) for k in ma if k != "Motion")[1]
        out[f"{a}->{b}"] = dict(mm=round(dpos * 1000, 2), deg=round(drot, 2), bone=worst, speed=(round(va, 2),
                                                                                              round(vb, 2)))
    return out


def feet():
    """Walk: the planted feet's drift in the world between two frames of a stance (mm; the root's travel plus the
    root-space toe)."""
    A = anim()
    N, fn, loop = A.CLIPS["Walk"]()
    out = {}
    for s, sfx in EB.SIDES:
        drift, prev = 0.0, None
        for f in range(N + 1):
            p = fn(f)
            m = A.pose_matrices(p)
            w = Vector(p.root) + m[f"Toe3_2{sfx}"].to_translation()
            on = p.stance[s]
            if on and prev is not None and prev[1]:
                drift = max(drift, (w - prev[0]).length)
            prev = (w, on)
        out[sfx] = round(drift * 1000, 2)
    return out


# ----------------------------------------------------------------------------------------- clip renders
FLIGHT = ("TakeOff", "Fly", "Glide", "Dive", "Land")


def _clip_cams(n):
    """(side, above) cameras for a clip's frame sheet; the flight clips' follow the trunk (Spine1)."""
    if n in FLIGHT:
        z = 0.36 + (0.0 if n == "TakeOff" else anim().FLY_H)       # where the trunk is in the clip's first frame
        cam("CAM_ClipSide", (9, -0.05, z), (0, -0.05, z), ortho=1.7)
        cam("CAM_ClipTop", (0, -0.02, z + 9), (0, -0.0199, z), ortho=2.3)
    elif n == "Death":
        cam("CAM_ClipSide", (9, -0.02, 0.32), (0, -0.02, 0.32), ortho=1.25)
        cam("CAM_ClipTop", (0, -0.05, 9), (0, -0.0499, 0.2), ortho=2.2)
    else:
        cam("CAM_ClipSide", (9, -0.02, 0.33), (0, -0.02, 0.33), ortho=0.9)
        cam("CAM_ClipTop", (0, -0.02, 9), (0, -0.0199, 0.3), ortho=0.9)
    return P + "CAM_ClipSide", P + "CAM_ClipTop"


def sheets(res=420):
    """EEVEE frame strips per clip, from the side (top row) and from above (bottom row):
    renders/eagle_clip_<Clip>.png. The skeleton plays in place (Motion carries the travel); the flight clips' cameras
    follow the trunk up and down (Spine1), so the bird stays in the middle of the frame."""
    setup_scene()
    RV.show_wolf(False)
    A = anim()
    out = []
    for n in A.CLIPS:
        side, top = _clip_cams(n)
        out.append(RV.frames_sheet(A, RIG, n, A.SHEET_FRAMES[n], (side, top), f"eagle_clip_{n}", res=res,
                                   follow="Spine1" if n in FLIGHT else True))
    return out


GAME_FRAMES = {"Fly": (0, 6, 12, 18), "Glide": (0, 22, 45, 67), "Dive": (14, 26, 38, 52), "TakeOff": (10, 18, 30, 50)}


def gameclips(res=620, crop=220, k=3):
    """The game camera (22 m, 50 deg, fov 30) on Fly, Glide, Dive and TakeOff at x1 and x2.5 beside the grey wolf:
    per clip and scale a sheet (columns: GAME_FRAMES, top row azimuth 30, bottom row 210), each tile the middle of the
    game frame blown up x3 -> renders/eagle_game_<Clip>_x<s>.png; and one whole 22 m frame per scale."""
    setup_scene()
    RV.add_wolf(P)
    RV.show_wolf(True)
    A = anim()
    scn = bpy.context.scene
    ground = bpy.data.objects.get("Ground")
    if ground is not None:
        ground.scale = (5, 5, 1)
    rig = bpy.data.objects[RIG]
    wolf = bpy.data.objects.get("WolfRig")
    out = []
    for sc in (1.0, 2.5):
        rig.scale = (sc, sc, sc)
        wx = 1.6 * (1.0 if sc == 1.0 else 2.0)
        if wolf is not None:
            wolf.location = (wx, 0.35, 0.0)
        cr = int(crop * (1.0 if sc == 1.0 else 1.9)) // 2 * 2
        kk = k * crop / cr
        for n, frs in GAME_FRAMES.items():
            A.use(n)
            rows = []
            for az in (30, 210):
                row = []
                for f in frs:
                    scn.frame_set(f)
                    bz = _posed_point("Spine1").z
                    tgt = (wx * 0.5, 0.1, 0.5 * (bz + 0.45))
                    _game_cam("CAM_G", az, tgt, 22.0)
                    p = RV.shot(P + "CAM_G", f"_egc_{n}_{sc:g}_{az}_{f}", res=res)
                    a = RV.load(p)
                    if n == "Fly" and az == 30 and f == frs[0]:
                        out.append(RV.save(a, f"eagle_game_frame_x{sc:g}"))
                    c0 = (res - cr) // 2
                    a = a[c0:c0 + cr, c0:c0 + cr]
                    ii = np.minimum((np.arange(crop * k) / kk).astype(int), cr - 1)
                    row.append(a[ii][:, ii])
                rows.append(np.concatenate(row, axis=1))
            out.append(RV.save(np.concatenate(rows[::-1], axis=0), f"eagle_game_{n}_x{sc:g}"))
    A.clear()
    rig.scale = (1, 1, 1)
    if ground is not None:
        ground.scale = (1, 1, 1)
    RV.show_wolf(False)
    return out


def gifs(res=420, step=2):
    """Every clip's frames from a 3/4 camera (in place) into renders/eagle_gif_<Clip>/; tools/frames_to_gif.py makes
    renders/eagle_<Clip>.gif from them (system Python)."""
    setup_scene()
    RV.show_wolf(False)
    A = anim()
    scn = bpy.context.scene
    ground = bpy.data.objects.get("Ground")
    if ground is not None:
        ground.scale = (5, 5, 1)                       # no disc edge on the horizon
    out = {}
    for n in A.CLIPS:
        if n in FLIGHT:
            cam("CAM_Gif", (2.5, -2.9, 2.0), (0, -0.05, 1.05), lens=40)
        elif n == "Death":
            cam("CAM_Gif", (1.45, -1.7, 1.15), (0, -0.05, 0.18), lens=40)
        else:
            cam("CAM_Gif", (1.25, -1.5, 0.85), (0, -0.02, 0.30), lens=45)
        folder = os.path.join(RV.RENDERS, f"eagle_gif_{n}")
        os.makedirs(folder, exist_ok=True)
        for fn in os.listdir(folder):
            os.remove(os.path.join(folder, fn))
        A.use(n)
        act = bpy.data.actions[A.action_name(n)]
        N = int(act["frames"])
        k = 0
        for f in range(0, N + (0 if act["loop"] else 1), step):
            scn.frame_set(f)
            RV.shot(P + "CAM_Gif", f"eagle_gif_{n}/{k:04d}", res=res)
            k += 1
        out[n] = k
    A.clear()
    if ground is not None:
        ground.scale = (1, 1, 1)
    return out


def export():
    """export/Eagle.fbx (EagleRig + EagleBody in the bind pose, M_Eagle), export/Textures/T_Eagle*.png (both presets),
    export/Anims/Eagle@<Clip>.fbx and eagle_clips.json (loop, root motion, events)."""
    import beast_export
    A = anim()
    A.build_clips()
    A.clear()
    return (beast_export.export_model(RIG, (BODY,), NAME, "T_Eagle") +
            beast_export.export_clips(A, RIG, NAME))


def reimport():
    """The export read back into an empty file (run it without eagle.blend, with 'nosave'): bones, meshes, UV layers,
    vertex groups, materials; Fly's and Walk's Motion travel and the head's height over a loop; the clips JSON."""
    import json
    from beast_export import EXPORT
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = {}
    bpy.ops.import_scene.fbx(filepath=os.path.join(EXPORT, NAME + ".fbx"))
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    a = arm[0]
    out["model"] = dict(armatures=len(arm), bones=len(a.data.bones),
                        roots=sorted(b.name for b in a.data.bones if b.parent is None),
                        motion_parent=a.data.bones["Motion"].parent.name if a.data.bones["Motion"].parent else None,
                        meshes=[(m.name, len(m.data.vertices), sum(len(p.vertices) - 2 for p in m.data.polygons),
                                 len(m.data.uv_layers), len(m.vertex_groups),
                                 [s.material.name if s.material else None for s in m.material_slots]) for m in meshes])
    with open(os.path.join(EXPORT, "Anims", NAME.lower() + "_clips.json"), encoding="utf-8") as f:
        out["json"] = json.load(f)["clips"]
    for clip in ("Fly", "Walk"):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.ops.import_scene.fbx(filepath=os.path.join(EXPORT, "Anims", f"{NAME}@{clip}.fbx"))
        a = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
        act = a.animation_data.action if a.animation_data else None
        scn = bpy.context.scene
        f0, f1 = (int(act.frame_range[0]), int(act.frame_range[1])) if act else (0, 0)
        pos = {}
        for f in (f0, f1):
            scn.frame_set(f)
            pos[f] = ((a.matrix_world @ a.pose.bones["Motion"].head).copy(),
                      (a.matrix_world @ a.pose.bones["Head"].head).copy())
        out[clip] = dict(frames=(f0, f1), bones=len(a.data.bones),
                         motion=[round(c, 3) for c in (pos[f1][0] - pos[f0][0])],
                         head_z=(round(pos[f0][1].z, 3), round(pos[f1][1].z, 3)),
                         head_step=[round(c, 3) for c in (pos[f1][1] - pos[f0][1])])
    return out
