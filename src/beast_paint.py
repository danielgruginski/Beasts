"""UV and texture framework shared by the beasts (moved out of wolf_paint.py).

UVs: the fur body is cut along hidden lines, which the creature provides as cut(region, centre); islands come from
the skin weights (head, trunk, each leg, tail, ears split front/back, paw soles). The separate pieces (jaw, tongue,
teeth, eyes, tail shells) carry the seams their builders marked. Angle-based unwrap, one texel density, then per-region
scales, packed.

Texture: painted per texel. Cycles bakes rest position, normal, part id and AO into float images (bake_data); the
creature's painter works on those. _streaks gives fur strokes along a flow field, continuous across UV seams. Alpha
holds smoothness (URP Lit: Smoothness Source = Albedo Alpha).
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector
from beast_common import ROOT, smoothstep, fill_gutters, fbm, vnoise, hexc
from beast_body import PART, read_info

TEX_DIR = os.path.join(ROOT, "textures")

# ----------------------------------------------------------------------------------------- seams
LEG_BONES = {"UpperArm": "fleg", "Forearm": "fleg", "FrontPaw": "fleg", "FrontToes": "fleg",
             "Thigh": "hleg", "Shin": "hleg", "HindFoot": "hleg", "HindToes": "hleg"}

def _region(bone):
    if not bone:
        return 'trunk'
    if bone in ("Head", "Jaw") or bone.startswith("Tongue"):
        return 'head'
    if bone.startswith("Ear"):
        return 'ear' + bone[-1]
    if bone.startswith("Tail"):
        return 'tail'
    for k, r in LEG_BONES.items():
        if bone.startswith(k):
            return r + bone[-1]
    return 'trunk'


def _interp_axis(z, pts):
    """y of a leg or tail axis at height z (pts: joints, top to bottom)."""
    zs = np.array([p[2] for p in pts])[::-1]
    ys = np.array([p[1] for p in pts])[::-1]
    return float(np.interp(z, zs, ys))


def mark_seams(ob, part, vbone, cut, unwarp=None, min_piece=8):
    """Seams on the fur body (call in edit mode). Returns the label per face (the mouth pieces are 'jaw', 'tongue',
    'tooth', 'eye' and keep their builders' seams). cut(region, unwarped face centre) -> (on the slit side, which
    side) or None; unwarp: the creature's position unwarp (hw_inv) or None."""
    unwarp = unwarp or (lambda c: c)
    me = ob.data
    n = ob["n_fur"]
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    pname = {v: k for k, v in PART.items()}
    label = {}
    fur_faces = [f for f in bm.faces if f.verts[0].index < n]
    for f in bm.faces:
        if f.verts[0].index >= n:
            label[f] = pname[int(part[f.verts[0].index])]
    for f in fur_faces:
        votes = [_region(vbone[v.index]) for v in f.verts]
        label[f] = max(set(votes), key=votes.count)
    for _ in range(3):                                 # no stray faces of another region
        new = {}
        for f in fur_faces:
            nb = [label[g] for e in f.edges for g in e.link_faces if g is not f]
            top = max(set(nb), key=nb.count) if nb else label[f]
            new[f] = top if nb.count(top) >= 2 and top != label[f] else label[f]
        label.update(new)
    for f in fur_faces:
        r = label[f]
        c = unwarp(np.array(f.calc_center_median()[:]))
        nz = f.normal.z
        if r.startswith(('fleg', 'hleg')) and nz < -0.6 and c[2] < 0.02:
            label[f] = r + '_sole'
        elif r.startswith('ear'):
            label[f] = r + ('_front' if f.normal.y < 0 else '_back')
    for _ in range(4):                                 # fold ragged fragments into their neighbours
        seen, changed = set(), False
        for f in fur_faces:
            if f in seen:
                continue
            comp, stack = {f}, [f]
            while stack:
                h = stack.pop()
                for e in h.edges:
                    for g in e.link_faces:
                        if g not in comp and label[g] == label[f]:
                            comp.add(g)
                            stack.append(g)
            seen |= comp
            if len(comp) < min_piece:
                around = [label[g] for h in comp for e in h.edges for g in e.link_faces if g not in comp]
                if around:
                    new = max(set(around), key=around.count)
                    for h in comp:
                        label[h] = new
                    changed = True
        if not changed:
            break
    cuts = {f: cut(label[f].split('_')[0], unwarp(np.array(f.calc_center_median()[:]))) for f in fur_faces}
    for e in bm.edges:
        if e.verts[0].index >= n:
            continue                                   # mouth pieces keep their seams
        e.seam = False
        if len(e.link_faces) != 2:
            continue
        a, b = e.link_faces
        if label[a] != label[b]:
            e.seam = True
        elif cuts.get(a) is not None and cuts.get(b) is not None and cuts[a][0] and cuts[b][0] and cuts[a][1] != cuts[b][1]:
            e.seam = True
    bmesh.update_edit_mesh(me)
    return {f.index: label[f] for f in bm.faces}


def unwrap(ob, cut, scales, unwarp=None, margin=0.003, relax=40):
    """Seams (mark_seams), angle-based unwrap, one density, then per-region scales ({region: k}, 'sole' for soles)."""
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.hide_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    part, _ = read_info(ob)                  # attributes and weights read in object mode
    names = {g.index: g.name for g in ob.vertex_groups}
    vbone = []
    for v in ob.data.vertices:
        best = max(v.groups, key=lambda g: g.weight, default=None)
        vbone.append(names.get(best.group) if best else None)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    labels = mark_seams(ob, part, vbone, cut, unwarp)
    bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.minimize_stretch(iterations=relax)
    bpy.ops.uv.average_islands_scale()
    bm = bmesh.from_edit_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        lab = labels[f.index]
        k = scales.get(lab.split('_')[0], 1.0)
        if lab.endswith('_sole'):
            k = scales.get('sole', 1.0)
        if k != 1.0:
            for l in f.loops:
                l[uv].uv *= k
    _tame_islands(bm, uv)
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return labels


def _tame_islands(bm, uv, limit=8.0):
    """Islands of a few near-zero-area faces (decimation leftovers) come out of average_islands_scale hugely
    enlarged; shrink any island whose UV/surface ratio is far above the median back to the median."""
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        if len(e.link_faces) == 2 and not e.seam:
            a, b = e.link_faces
            parent[find(a.index)] = find(b.index)
    islands = {}
    for f in bm.faces:
        islands.setdefault(find(f.index), []).append(f)
    stats = []
    for fs in islands.values():
        a3 = sum(f.calc_area() for f in fs)
        a2 = 0.0
        for f in fs:
            u = [l[uv].uv for l in f.loops]
            for i in range(1, len(u) - 1):
                a2 += abs((u[i] - u[0]).cross(u[i + 1] - u[0])) / 2
        stats.append((fs, a2 / max(a3, 1e-12)))
    med = float(np.median([r for _, r in stats]))
    for fs, r in stats:
        if r > limit * med:
            k = math.sqrt(med / r)
            loops = [l for f in fs for l in f.loops]
            c = sum((l[uv].uv for l in loops), Vector((0, 0))) / len(loops)
            for l in loops:
                l[uv].uv = c + (l[uv].uv - c) * k


def uv_layout(ob, name, size=2048):
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    path = os.path.join(ROOT, "renders", name + ".png")
    bpy.ops.uv.export_layout(filepath=path, size=(size, size), opacity=0.25, export_all=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return path


def _bake_setup(ob, image_name, size, emit_builder=None):
    img = bpy.data.images.get(image_name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(image_name, size, size, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    m = bpy.data.materials.get("_WLF_Bake") or bpy.data.materials.new("_WLF_Bake")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if emit_builder is not None:
        em = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(emit_builder(nt), em.inputs['Color'])
        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    else:
        bs = nt.nodes.new('ShaderNodeBsdfDiffuse')
        nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return img


def _read(img):
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def _box(a, r):
    c = np.cumsum(np.cumsum(np.pad(a, ((r + 1, r), (r + 1, r))), 0), 1)
    return c[2 * r + 1:, 2 * r + 1:] - c[:-2 * r - 1, 2 * r + 1:] - c[2 * r + 1:, :-2 * r - 1] + c[:-2 * r - 1, :-2 * r - 1]


def _despeckle(ao, valid, r=5):
    """Folded faces at the tuft roots bake as small near-black specks: lift texels far darker than their island
    neighbourhood toward the neighbourhood's mean."""
    m = valid.astype(float)
    mean = _box(ao * m, r) / np.maximum(_box(m, r), 1)
    return np.where(valid, np.maximum(ao, mean * 0.85), ao)


def bake_data(ob, size=1024, ao_samples=96, ao_dist=0.25):
    """Rest position, normal, info (part, on-jaw) and AO per texel."""
    scn = bpy.context.scene
    prev_engine = scn.render.engine
    scn.render.engine = 'CYCLES'
    try:
        scn.cycles.device = 'GPU'
    except Exception:
        pass
    arm = [m for m in ob.modifiers if m.type == 'ARMATURE']
    for m in arm:
        m.show_render = m.show_viewport = False
    hidden = {o.name: o.hide_render for o in scn.objects}
    for o in scn.objects:
        o.hide_render = o is not ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    old = list(ob.data.materials)
    out = {}

    def geo(nt, socket, add=None, mul=None):
        g = nt.nodes.new('ShaderNodeNewGeometry')
        v = g.outputs[socket]
        if mul is not None:
            n = nt.nodes.new('ShaderNodeVectorMath')
            n.operation = 'MULTIPLY'
            n.inputs[1].default_value = mul
            nt.links.new(v, n.inputs[0])
            v = n.outputs[0]
        if add is not None:
            n = nt.nodes.new('ShaderNodeVectorMath')
            n.operation = 'ADD'
            n.inputs[1].default_value = add
            nt.links.new(v, n.inputs[0])
            v = n.outputs[0]
        return v

    def attr(nt):
        a = nt.nodes.new('ShaderNodeAttribute')
        a.attribute_name = "info"
        return a.outputs['Color']

    scn.cycles.samples = 1
    for key, builder in (("pos", lambda nt: geo(nt, 'Position', add=(2, 2, 2))),
                         ("nrm", lambda nt: geo(nt, 'Normal', mul=(0.5, 0.5, 0.5), add=(0.5, 0.5, 0.5))),
                         ("info", attr)):
        img = _bake_setup(ob, "_WLF_" + key, size, builder)
        bpy.ops.object.bake(type='EMIT', margin=6, use_clear=True)
        out[key] = _read(img)
    w = scn.world
    w.light_settings.distance = ao_dist
    scn.cycles.samples = ao_samples
    img = _bake_setup(ob, "_WLF_ao", size, None)
    bpy.ops.object.bake(type='AO', margin=6, use_clear=True)
    out["ao"] = _read(img)[..., 0]
    ob.data.materials.clear()
    for m in old:
        ob.data.materials.append(m)
    for m in arm:
        m.show_render = m.show_viewport = True
    for o in scn.objects:
        o.hide_render = hidden.get(o.name, o.hide_render)
    scn.render.engine = prev_engine
    P = out["pos"][..., :3] - 2.0
    valid = out["pos"][..., :3].sum(-1) > 0.5
    out["ao"] = _despeckle(out["ao"], valid)
    N = out["nrm"][..., :3] * 2 - 1
    N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-6)
    eyes = {k: np.array(ob[k]) for k in ob.keys() if k.startswith("eye")}
    return dict(P=P, N=N, part=np.rint(out["info"][..., 0] * 255).astype(int), on_jaw=out["info"][..., 1] > 0.5,
                ao=out["ao"], valid=valid, eyes=eyes)


def _c(h):
    return hexc(h)


def _mix(a, b, t):
    t = np.clip(np.asarray(t, float), 0, 1)[..., None]
    return a * (1 - t) + np.asarray(b) * t


def _streaks(P, F, seed, across=0.010, length=0.035, steps=7):
    """Fur strokes: 3D noise averaged along the fur flow, so each streak runs along the hair and across UV seams."""
    acc = 0.0
    for k in range(steps):
        t = (k / (steps - 1) - 0.5) * length
        acc = acc + vnoise((P + F * t) / across, seed=seed)
    return acc / steps


def write_texture(D, col, smooth, image_name, ob=None, material_name=None):
    os.makedirs(TEX_DIR, exist_ok=True)
    H, Wd = D['part'].shape
    img = bpy.data.images.get(image_name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(image_name, Wd, H, alpha=True)
    img.colorspace_settings.name = 'sRGB'
    img.alpha_mode = 'CHANNEL_PACKED'
    rgba = np.concatenate([col, smooth[..., None]], -1).astype(np.float32)   # byte image: stored (sRGB) values
    img.pixels.foreach_set(rgba.ravel())
    fill_gutters(img, D['valid'])
    path = os.path.join(TEX_DIR, image_name + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    if ob is not None:
        game_material(ob, img, material_name or "M_" + image_name[2:])
    return path


def game_material(ob, img, name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], inv.inputs[1])
    nt.links.new(inv.outputs[0], bsdf.inputs['Roughness'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m
