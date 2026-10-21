"""Build the hen (2026-10-20): body -> rig -> weights -> UVs -> plumage -> clips, renders, export. The same step
functions as farm_build (tools/farm_run.py picks this module for 'chicken'); blender/farm_chicken.blend.
"""
import bpy, os
import numpy as np
from beast_common import ROOT
import beast_scene, beast_rig
import chicken_body as CB

VIEWS = ("Front", "Side", "34", "Face", "Rear", "Colony", "Legs")
COATS = ("brown", "white", "black")


class _Sp:
    NAME, PREFIX = CB.NAME, CB.PREFIX
    COATS = {c: None for c in COATS}


def species(name):
    return _Sp()


def blend_path(name):
    return os.path.join(ROOT, "blender", "farm_chicken.blend")


def rig_name(sp=None):
    return CB.NAME + "Rig"


def setup_scene(sp=None):
    scn = bpy.context.scene
    scn.name = CB.NAME
    for n in ("Cube", "Light", "Camera"):
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
    beast_scene.setup_scene(CB.NAME, prefix=CB.PREFIX + "_")
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scn.render.engine = eng
            break
        except TypeError:
            pass
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, CB.PREFIX + "_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -6, 0.22), (0, 0, 0.22), ortho=0.6)
    c("CAM_Side", (6, 0.02, 0.22), (0, 0.02, 0.22), ortho=0.6)
    c("CAM_34", (0.55, -0.75, 0.55), (0, 0.0, 0.2), lens=50)
    c("CAM_Face", (0.22, -0.45, 0.45), (0, -0.12, 0.36), lens=70)
    c("CAM_Rear", (-0.45, 0.65, 0.5), (0, 0.05, 0.2), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, 0, 0.2), lens=300)
    c("CAM_Legs", (0.25, -0.30, 0.12), (0.04, 0.01, 0.07), lens=50)
    scn.camera = bpy.data.objects[CB.PREFIX + "_CAM_34"]
    return scn


def build_model(sp=None, tex=512):
    import chicken_paint, farm_paint
    setup_scene()
    lc = bpy.context.view_layer.layer_collection.children.get(CB.PREFIX + "_Work")
    if lc is not None:
        lc.exclude = False
    body, hi = CB.build_body()
    report = {"tris": CB.tri_report(body)}
    arm = beast_rig.build_armature(CB.rest_bones(), name=rig_name(), coll_name=CB.PREFIX + "_Rig")
    report["weights"] = CB.skin(body, arm)
    chicken_paint.unwrap(body)
    report["textures"], report["coverage"] = chicken_paint.build_texture(body, size=tex)
    report["uv_layout"] = farm_paint.uv_png(body, os.path.join(ROOT, "renders", "uv_layout_chicken.png"),
                                            size=512, tex=report["textures"][0])
    lc = bpy.context.view_layer.layer_collection.children.get(CB.PREFIX + "_Work")
    if lc is not None:
        lc.exclude = True
    arm.hide_render = True
    return body, arm, report


def review(sp=None, views=VIEWS, res=800):
    setup_scene()
    eng = bpy.context.scene.render.engine
    return [beast_scene.shot(f"{CB.PREFIX}_CAM_{v}", f"chicken_{v.lower()}", engine=eng, res=res) for v in views]


def review_test_pose(sp=None, res=800):
    return []


def coat_shots(sp=None, cam="34", res=600):
    setup_scene()
    m = bpy.data.materials["M_Chicken"]
    tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
    first = tex.image
    eng = bpy.context.scene.render.engine
    paths = []
    for i, c in enumerate(COATS):
        name = "T_Chicken" if i == 0 else "T_Chicken_" + c.title()
        tex.image = bpy.data.images.load(os.path.join(ROOT, "textures", name + ".png"), check_existing=True)
        paths.append(beast_scene.shot(f"{CB.PREFIX}_CAM_{cam}", f"chicken_coat_{c}", engine=eng, res=res))
    tex.image = first
    return paths


def anim(sp=None):
    import chicken_anim
    return chicken_anim


def build_clips(sp=None):
    A = anim()
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def clip_sheets(sp=None, names=None, res=300):
    A = anim()
    scn = bpy.context.scene
    beast_scene._cam(scn, CB.PREFIX + "_CAM_ClipSide", (6, 0.0, 0.2), (0, 0.0, 0.2), ortho=0.7)
    beast_scene._cam(scn, CB.PREFIX + "_CAM_Clip34", (0.6, -0.85, 0.55), (0, 0, 0.17), lens=45)
    paths = []
    for n in (names or A.CLIPS):
        A.use(n)
        paths.append(beast_scene.render_sheet(n, A.SHEET_FRAMES[n], cams=(CB.PREFIX + "_CAM_ClipSide",
                                                                        CB.PREFIX + "_CAM_Clip34"),
                                              rig_name=rig_name(), res=res, out=f"chicken_clip_{n}"))
    A.clear()
    return paths


def lowest(sp=None, names=None, step=2):
    A = anim()
    body = bpy.data.objects[CB.NAME + "Body"]
    scn = bpy.context.scene
    out = {}
    for n in (names or A.CLIPS):
        A.use(n)
        act = bpy.data.actions[A.action_name(n)]
        lo = 9.0
        for f in range(0, int(act["frames"]) + 1, step):
            scn.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            me = body.evaluated_get(dg).to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            lo = min(lo, float(co.reshape(-1, 3)[:, 2].min()))
            body.evaluated_get(dg).to_mesh_clear()
        out[n] = round(lo, 3)
    A.clear()
    return out


def export(sp=None):
    import beast_export
    A = anim()
    return (beast_export.export_model(rig_name(), (CB.NAME + "Body",), CB.NAME, "T_" + CB.NAME) +
            beast_export.export_clips(A, rig_name(), CB.NAME))
