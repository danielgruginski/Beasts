"""Build the farm animals (2026-10-20): body -> rig -> weights -> UVs -> painted coats -> clips, review renders,
export. One .blend per animal (blender/farm_<name>.blend, its scene named after it), because the builds run in a
headless Blender (`tools/farm_run.py`) while the live one is busy with other work: a background Blender has no
window, so it can't switch scenes.

    blender.exe -b --factory-startup --python tools/farm_run.py -- goat build review export
(or, with farm_<name>.blend already there, -b blender/farm_goat.blend ...). Species modules: farm_goat, farm_sheep,
farm_cow, farm_horse, farm_pig (farm_body.Hoofed subclasses, module attribute SP) and farm_chicken.
"""
import bpy, importlib, os
import numpy as np
from beast_common import ROOT
import beast_scene, beast_rig

SPECIES = ("goat", "sheep", "cow", "horse", "pig")
VIEWS = ("Front", "Side", "34", "Face", "HeadSide", "Rear", "Colony", "Legs")


def species(name):
    return importlib.import_module("farm_" + name).SP


def blend_path(name):
    return os.path.join(ROOT, "blender", f"farm_{name}.blend")


def dims(sp):
    """(withers height, nose-to-rump length, the body's centre y) in R."""
    w = sp.W(np.array([(0, -0.40, 1.15), (0, sp.hx((0, -sp.HEAD_LEN, 0))[1], 1.0), (0, sp.TAIL[0][1], 1.0)]))
    return float(w[0, 2]), float(w[2, 1] - w[1, 1]), float(0.5 * (w[2, 1] + w[1, 1]))


def setup_scene(sp):
    """The animal's scene (the file's one scene, renamed), cameras framed for its size (<PREFIX>_CAM_*), the shared
    lights and ground, EEVEE."""
    scn = bpy.context.scene
    scn.name = sp.NAME
    for n in ("Cube", "Light", "Camera"):                 # the factory startup's objects
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
    beast_scene.setup_scene(sp.NAME, prefix=sp.PREFIX + "_")
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scn.render.engine = eng
            break
        except TypeError:
            pass
    h, L, yc = dims(sp)
    k = max(h, 0.55 * L)
    head = sp.W(sp.hx((0, -0.20, 0.0)))
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, sp.PREFIX + "_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -14, 0.62 * h + 0.15 * k), (0, 0, 0.62 * h + 0.15 * k), ortho=1.6 * k)
    c("CAM_Side", (14, yc, 0.55 * h + 0.2 * k), (0, yc, 0.55 * h + 0.2 * k), ortho=1.25 * L + 0.4 * k)
    c("CAM_Top", (0, yc, 14), (0, yc + 0.0001, 0), ortho=1.25 * L + 0.4 * k)
    c("CAM_34", (2.4 * k, yc - 3.3 * k, 2.0 * k), (0, yc - 0.15 * L, 0.55 * h), lens=50)
    c("CAM_Face", tuple(head + np.array((0.8, -2.1, 0.35)) * k), tuple(head), lens=70)
    c("CAM_HeadSide", (6, head[1], head[2]), tuple(head), ortho=1.2 * k)
    c("CAM_HeadFront", (0, -6, head[2]), (0, 0, head[2]), ortho=1.2 * k)
    c("CAM_Rear", (-1.9 * k, yc + 2.8 * k, 1.8 * k), (0, yc + 0.2 * L, 0.5 * h), lens=50)
    c("CAM_Colony", (0, yc - 26, 31), (0, yc, 0.5 * h), lens=300)
    legs = sp.W(np.array((sp.J['WRI'][0], sp.J['WRI'][1], 0.30)))
    c("CAM_Legs", tuple(legs + np.array((0.6, -0.8, 0.10)) * k), tuple(legs), lens=50)
    scn.camera = bpy.data.objects[sp.PREFIX + "_CAM_34"]
    return scn


def work_layer(sp, on):
    lc = bpy.context.view_layer.layer_collection.children.get(sp.PREFIX + "_Work")
    if lc is not None:
        lc.exclude = not on


def rig_name(sp):
    return sp.NAME + "Rig"


def build_model(sp, tex=1024, paint=True, rig=True):
    """Body -> rig -> weights -> UVs -> painted coats. -> (body, rig, report)"""
    import farm_rig, farm_paint
    setup_scene(sp)
    work_layer(sp, True)
    body, hi = sp.build_body()
    report = {"tris": sp.tri_report(body)}
    arm = None
    if rig:
        arm = beast_rig.build_armature(sp.rest_bones(), name=rig_name(sp), coll_name=sp.PREFIX + "_Rig")
        report["weights"] = farm_rig.skin(sp, body, arm)
    if paint:
        farm_paint.unwrap(sp, body)
        report["textures"], report["coverage"] = farm_paint.build_texture(sp, body, size=tex)
        report["uv_layout"] = farm_paint.uv_png(body, os.path.join(ROOT, "renders", f"uv_layout_{sp.NAME.lower()}.png"),
                                                tex=report["textures"][0])
    work_layer(sp, False)
    if arm is not None:
        arm.hide_render = True
    return body, arm, report


def review(sp, prefix=None, views=VIEWS, res=900):
    """EEVEE renders of the bind pose into renders/ (goat_34.png ...)."""
    setup_scene(sp)
    prefix = prefix or sp.NAME.lower()
    eng = bpy.context.scene.render.engine
    return [beast_scene.shot(f"{sp.PREFIX}_CAM_{v}", f"{prefix}_{v.lower()}", engine=eng, res=res) for v in views]


def review_test_pose(sp, res=900):
    import farm_rig
    rig = bpy.data.objects[rig_name(sp)]
    farm_rig.test_pose(rig)
    eng = bpy.context.scene.render.engine
    p = sp.NAME.lower()
    paths = [beast_scene.shot(f"{sp.PREFIX}_CAM_34", f"{p}_testpose_34", engine=eng, res=res),
             beast_scene.shot(f"{sp.PREFIX}_CAM_Side", f"{p}_testpose_side", engine=eng, res=res)]
    beast_rig.reset_pose(rig)
    return paths


def lineup(names, out="farm_lineup", res=1400):
    """Not used headless (one animal per file)."""
    raise NotImplementedError


# ----------------------------------------------------------------------------------------- clips and export
def anim(sp):
    import farm_anim
    return farm_anim.for_species(sp)


def build_clips(sp):
    A = anim(sp)
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def clip_sheets(sp, names=None, res=360):
    """Contact sheets of the clips' key frames from the side and 3/4: renders/<name>_clip_<Clip>.png."""
    A = anim(sp)
    scn = bpy.context.scene
    h, L, yc = dims(sp)
    k = max(h, 0.55 * L)
    beast_scene._cam(scn, sp.PREFIX + "_CAM_ClipSide", (12, yc, 0.5 * h), (0, yc, 0.5 * h), ortho=1.4 * L + 0.3 * k)
    beast_scene._cam(scn, sp.PREFIX + "_CAM_Clip34", (2.5 * k, yc - 3.5 * k, 1.9 * k), (0, yc, 0.42 * h), lens=45)
    paths = []
    for n in (names or A.CLIPS):
        A.use(n)
        paths.append(beast_scene.render_sheet(n, A.SHEET_FRAMES[n], cams=(sp.PREFIX + "_CAM_ClipSide",
                                                                        sp.PREFIX + "_CAM_Clip34"),
                                              rig_name=rig_name(sp), res=res, out=f"{sp.NAME.lower()}_clip_{n}"))
    A.clear()
    return paths


def export(sp):
    """export/<Name>.fbx (rig + body), Textures/T_<Name>*.png, Anims/<Name>@<clip>.fbx + <name>_clips.json."""
    import beast_export
    A = anim(sp)
    return (beast_export.export_model(rig_name(sp), (sp.NAME + "Body",), sp.NAME, "T_" + sp.NAME) +
            beast_export.export_clips(A, rig_name(sp), sp.NAME))


def lowest(sp, names=None, step=2):
    """The lowest vertex per clip (evaluated mesh, world z): nothing should go under -0.03."""
    A = anim(sp)
    body = bpy.data.objects[sp.NAME + "Body"]
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
            lo = min(lo, float((co.reshape(-1, 3)[:, 2]).min()))
            body.evaluated_get(dg).to_mesh_clear()
        out[n] = round(lo, 3)
    A.clear()
    return out


def coat_shots(sp, cam="34", res=700):
    """The bind pose rendered once per coat (the material's image swapped): renders/<name>_coat_<coat>.png."""
    setup_scene(sp)
    m = bpy.data.materials[f"M_{sp.NAME}"]
    tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
    first = tex.image
    eng = bpy.context.scene.render.engine
    paths = []
    for i, c in enumerate(sp.COATS):
        name = f"T_{sp.NAME}" if i == 0 else f"T_{sp.NAME}_{c.title()}"
        tex.image = bpy.data.images.load(os.path.join(ROOT, "textures", name + ".png"), check_existing=True)
        paths.append(beast_scene.shot(f"{sp.PREFIX}_CAM_{cam}", f"{sp.NAME.lower()}_coat_{c}", engine=eng, res=res))
    tex.image = first
    return paths


def head_shots(sp, res=600):
    """The bare head (Workbench, one colour) from the side, the front and 3/4: renders/<name>_head_<view>.png. For
    iterating on a head's shape with build_model(sp, paint=False, rig=False)."""
    setup_scene(sp)
    scn = bpy.context.scene
    head = sp.W(sp.hx((0, -0.22, -0.04)))
    k = float(sp.W(np.array((0, 0, 1.15)))[2])
    beast_scene._cam(scn, sp.PREFIX + "_CAM_HD34", tuple(head + np.array((0.9, -1.1, 0.25)) * 1.0 * k), tuple(head),
                     lens=60)
    out = []
    for v in ("HeadSide", "HeadFront", "HD34"):
        out.append(beast_scene.shot(f"{sp.PREFIX}_CAM_{v}", f"{sp.NAME.lower()}_head_{v.lower()}", res=res,
                                    color='SINGLE'))
    return out
