"""Mesh helpers and the body pipeline shared by the beasts (moved out of wolf_body.py).

fuse_body(): parts (lofts, ellipsoids, tufts) in one bmesh -> voxel remesh -> symmetrise -> smooth -> crease fillet
-> the creature's sculpts -> smooth -> flat pads -> dense copy for the bake -> decimate (weighted) -> edge flips and
fold relaxing. build_tufts(): stylised fur tufts (curved cones). sculpt_fur(): noise clumps along a fur flow.
join_pieces(): the separate pieces (jaw, teeth, eyes, tail) onto the fur body, with the info attribute.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from beast_common import loft, mesh_obj, get_coll, remove_obj, smoothstep, fbm

# part ids in the "info" attribute (info.g = 1 on pieces that ride on the lower jaw)
PART = dict(fur=1, nose=2, eye=3, tooth=4, jaw=5, tongue=6, tail=7, whisker=8)


def ellipsoid(bm, center, radii, rot=None, seg=16, rings=10):
    m = Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
    if rot is not None:
        m = rot.to_4x4() @ m
    m = Matrix.Translation(Vector(center)) @ m
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0, matrix=m)


def _gauss(P, c, r):
    d = (P - np.asarray(c)) / np.asarray(r)
    return np.exp(-0.5 * (d * d).sum(-1))


def _clean(bm):
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-5)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


def _apply_mod(ob, mod):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _arrays(bm):
    bm.normal_update()
    co = np.array([v.co[:] for v in bm.verts])
    no = np.array([v.normal[:] for v in bm.verts])
    return co, no


def _set_co(bm, co):
    for v, p in zip(bm.verts, co):
        v.co = Vector(p)


def _edges(bm):
    return np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges])


def fillet(co, no, e, iters=40, f=0.5):
    """Round off the creases where fused parts meet: concave vertices move toward their neighbours' average,
    convex ones stay, so the valleys fill like a fillet and silhouettes keep their shape."""
    V = len(co)
    deg = np.maximum(np.bincount(e.ravel(), minlength=V), 1).astype(float)[:, None]
    el = np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1).mean()
    for _ in range(iters):
        acc = np.zeros_like(co)
        np.add.at(acc, e[:, 0], co[e[:, 1]])
        np.add.at(acc, e[:, 1], co[e[:, 0]])
        L = acc / deg - co
        c = (L * no).sum(1)
        m = np.clip(c / (0.15 * el), 0, 1)
        co = co + f * L * m[:, None]
    return co


def unfold(bm, passes=6):
    """Relax vertices where the decimated surface folds over (a face turned against its neighbours shows as a dark
    notch): move them to their neighbours' mean until every face agrees with the faces around it."""
    moved = 0
    for _ in range(passes):
        bm.normal_update()
        bad = set()
        for f in bm.faces:
            nb = [g for e in f.edges for g in e.link_faces if g is not f]
            if nb and sum(f.normal.dot(g.normal) for g in nb) / len(nb) < -0.1:
                bad.update(f.verts)
        if not bad:
            break
        for v in bad:
            ring = [e.other_vert(v) for e in v.link_edges]
            v.co = v.co * 0.3 + sum((u.co for u in ring), Vector()) / len(ring) * 0.7
        moved += len(bad)
    return moved


def _write_info(me, part_per_vertex, on_jaw):
    if "info" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["info"])
    att = me.color_attributes.new("info", 'FLOAT_COLOR', 'POINT')
    rgba = np.zeros((len(me.vertices), 4), np.float32)
    rgba[:, 0] = np.asarray(part_per_vertex) / 255.0
    rgba[:, 1] = on_jaw
    rgba[:, 3] = 1
    att.data.foreach_set('color', rgba.ravel())


def read_info(ob):
    """-> (part id per vertex, on-jaw flag per vertex)."""
    att = ob.data.color_attributes["info"]
    buf = np.empty(len(ob.data.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    buf = buf.reshape(-1, 4)
    return np.rint(buf[:, 0] * 255).astype(int), buf[:, 1] > 0.5


def tri_report(ob):
    info = ob.data.color_attributes["info"]
    buf = np.empty(len(ob.data.vertices) * 4, np.float32)
    info.data.foreach_get('color', buf)
    part = np.rint(buf.reshape(-1, 4)[:, 0] * 255).astype(int)
    names = {v: k for k, v in PART.items()}
    out = {}
    for p in ob.data.polygons:
        k = names.get(int(part[p.vertices[0]]), '?')
        out[k] = out.get(k, 0) + len(p.vertices) - 2
    out['total'] = sum(out.values())
    return out


def _mx(p):
    return (-p[0], p[1], p[2])


def build_tufts(bm, bvh, tufts, warp=None):
    """Each tuft: a curved cone rooted a little under the surface, pointing along its direction (bent by gravity).
    tufts: (anchor near the surface (left side or centre line; left ones are mirrored), direction, length, radius)."""
    for anchor, d, L, r in tufts:
        sides = (1,) if abs(anchor[0]) < 1e-6 else (1, -1)
        for s in sides:
            a = (s * anchor[0], anchor[1], anchor[2])
            a = Vector(warp(a) if warp is not None else a)
            hit = bvh.find_nearest(a)
            if hit[0] is None:
                continue
            p, n = hit[0], hit[1]
            dv = Vector((s * d[0], d[1], d[2])).normalized()
            dv = (dv + 0.25 * n).normalized()
            base = p - n * r * 0.7
            mid = base + dv * L * 0.55 + Vector((0, 0, -0.12 * L))
            tip = base + dv * L + Vector((0, 0, -0.30 * L))
            rows = [tuple(base) + (r, r, r), tuple(mid) + (0.62 * r,) * 3, tuple(tip) + (0.16 * r,) * 3]
            loft(bm, rows, up=tuple(n), seg=10, per_seg=3, cap0=0.5, cap1=0.9)


def sculpt_fur(co, no, flow, amount, seed=5, across=0.040, along_len=0.110):
    F = flow(co, no)
    A = amount(co, no)
    along = (co * F).sum(-1)[:, None] * F
    q = (co - along) / across + along / along_len        # clumps: narrow across the flow, long along it
    c = fbm(q, 3, seed=seed)
    tuft = smoothstep(-0.15, 0.65, c) ** 1.6
    d = A * (0.30 + 0.85 * tuft)
    D = no + 0.4 * F
    D /= np.linalg.norm(D, axis=-1, keepdims=True)
    return co + D * d[:, None]


def fuse_body(bm, prefix, voxel, target_tris, sculpts=(), dec_weight=None, seam_x=0.012, flat_z=0.004,
              fillet_iters=80):
    """-> (decimated body `<prefix>_Fur` in <prefix>_Body, dense copy `<prefix>_BodyHi` in <prefix>_Work).
    sculpts: functions (co, no) -> co applied in turn on the dense mesh. dec_weight(co) -> 0..1 (lower keeps more)."""
    coll = get_coll(prefix + "_Body")
    work = get_coll(prefix + "_Work")
    remove_obj(prefix + "_Parts")
    parts = mesh_obj(prefix + "_Parts", bm, work)
    parts.hide_render = True
    remove_obj(prefix + "_Fur")
    body = bpy.data.objects.new(prefix + "_Fur", parts.data.copy())
    coll.objects.link(body)
    mod = body.modifiers.new("remesh", 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = voxel
    mod.adaptivity = 0.0
    _apply_mod(body, mod)

    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction='X', dist=voxel * 0.25)
    _clean(bm)
    for _ in range(2):
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.4, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    bm.verts.index_update()
    co, no = _arrays(bm)
    co = fillet(co, no, _edges(bm), iters=fillet_iters)
    _set_co(bm, co)
    for fn in sculpts:
        co, no = _arrays(bm)
        _set_co(bm, fn(co, no))
    co, no = _arrays(bm)
    co[:, 2] = np.maximum(co[:, 2], 0.0)
    _set_co(bm, co)
    for _ in range(2):                                            # voxel stair-steps left by the sculpt
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.5, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    seam = [v for v in bm.verts if abs(v.co.x) < seam_x]          # hide the symmetrize crease
    for _ in range(4):
        bmesh.ops.smooth_vert(bm, verts=seam, factor=0.5, use_axis_x=False, use_axis_y=True, use_axis_z=True)
    for v in bm.verts:                                            # flat pads
        if v.co.z < flat_z:
            v.co.z = 0.0
    bm.to_mesh(body.data)
    bm.free()

    remove_obj(prefix + "_BodyHi")
    hi = bpy.data.objects.new(prefix + "_BodyHi", body.data.copy())
    work.objects.link(hi)
    hi.hide_render = True

    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    dec = body.modifiers.new("decimate", 'DECIMATE')
    dec.decimate_type = 'COLLAPSE'
    dec.ratio = min(1.0, target_tris / tris)
    dec.use_symmetry = True
    dec.symmetry_axis = 'X'
    if dec_weight is not None:
        g = body.vertex_groups.new(name="_decimate")
        for v in body.data.vertices:
            g.add([v.index], float(dec_weight(v.co)), 'REPLACE')
        dec.vertex_group = "_decimate"
    _apply_mod(body, dec)
    if "_decimate" in body.vertex_groups:
        body.vertex_groups.remove(body.vertex_groups["_decimate"])
    bm = bmesh.new()
    bm.from_mesh(body.data)
    _clean(bm)
    # collapse leaves long slivers on flat areas (dark slits once smooth shaded): flip edges to better triangles
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    unfold(bm)
    bm.to_mesh(body.data)
    bm.free()
    parts.hide_set(True)
    parts.hide_viewport = True
    hi.hide_set(True)
    return body, hi


def join_pieces(fur, pieces_bm, tags, prefix, body_name):
    """Join the separate pieces (jaw, teeth, eyes, tail...) onto the fur body (the fur keeps its vertex order) and
    write the info attribute. tags: {part name: [BMVerts]}; 'tooth_low' = lower teeth. Jaw, tongue and lower teeth
    ride on the jaw (info.g = 1). Returns (body, number of fur vertices)."""
    nfur = len(fur.data.vertices)
    co = np.array([v.co[:] for v in fur.data.vertices])
    extra = {}
    for k, vs in tags.items():
        for v in vs:
            extra[v] = (PART['tooth'], 1) if k == 'tooth_low' else (PART[k], int(k in ('jaw', 'tongue')))
    pieces_bm.verts.index_update()
    part_extra = np.array([extra.get(v, (PART['jaw'], 1)) for v in pieces_bm.verts]).reshape(-1, 2)
    remove_obj(prefix + "_Pieces")
    pieces = mesh_obj(prefix + "_Pieces", pieces_bm, get_coll(prefix + "_Body"))
    remove_obj(body_name)
    body = fur
    body.name = body_name
    body.data.name = body_name
    for o in bpy.context.selected_objects:
        o.select_set(False)
    pieces.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body["n_fur"] = nfur
    for p in body.data.polygons:
        p.use_smooth = True
    return body, nfur, part_extra
