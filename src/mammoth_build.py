"""Rebuild the woolly mammoth from scratch: body -> rig -> weights -> UVs -> painted coat -> clips. Run inside Blender
with the Mammoth scene on screen (mammoth_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, beast_coat, mammoth_body

RIG = "MammothRig"


def reload_all():
    import beast_paint, beast_anim, beast_export
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_coat, beast_paint, beast_anim, beast_export,
            mammoth_body]
    for name in ("mammoth_rig", "mammoth_paint", "mammoth_anim"):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        importlib.reload(m)


def setup_scene():
    """The Mammoth scene: shared lights and ground, cameras framed for the mammoth (MAM_CAM_*), and a wolf beside it
    for scale (an instance of the Wolf scene's body, not exported)."""
    scn = beast_scene.setup_scene("Mammoth", prefix="MAM_")
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "MAM_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -20, 1.60), (0, 0, 1.60), ortho=4.2)
    c("CAM_Side", (20, -0.80, 1.60), (0, -0.80, 1.60), ortho=6.4)
    c("CAM_Top", (0, -0.8, 20), (0, -0.7999, 0), ortho=6.4)
    c("CAM_34", (6.4, -8.6, 4.2), (0, -0.90, 1.50), lens=50)
    c("CAM_Face", (2.2, -6.0, 2.6), (0, -2.40, 1.90), lens=60)
    c("CAM_HeadSide", (10, -2.40, 1.80), (0, -2.40, 1.80), ortho=3.0)
    c("CAM_HeadFront", (0, -12, 1.90), (0, 0, 1.90), ortho=3.0)
    c("CAM_Rear", (-5.0, 7.0, 4.2), (0, 0.4, 1.4), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, -0.6, 1.4), lens=300)
    scn.camera = bpy.data.objects["MAM_CAM_34"]
    wolf = bpy.data.collections.get("WLF_Body")
    inst = bpy.data.objects.get("MAM_ScaleWolf")
    if wolf is not None and inst is None:
        inst = bpy.data.objects.new("MAM_ScaleWolf", None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = wolf
        inst.location = (2.6, -1.6, 0)
        inst.hide_select = True
    if inst is not None and inst.name not in scn.collection.objects:
        scn.collection.objects.link(inst)
    return scn


def show():
    scn = bpy.data.scenes.get("Mammoth") or setup_scene()
    beast_scene.show_scene(scn)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("MAM_Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024, body_tris=2600, paint=True, rig=True):
    """Body -> rig -> weights -> UVs -> painted coat. -> (body, rig, report)"""
    assert bpy.context.scene.name == "Mammoth", "put the Mammoth scene on screen first: mammoth_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = mammoth_body.build_body(target_tris=body_tris)
    report = {"tris": mammoth_body.tri_report(body)}
    arm = None
    if rig:
        import mammoth_rig
        arm = beast_rig.build_armature(mammoth_body.rest_bones(), name=RIG, coll_name="MAM_Rig")
        report["weights"] = mammoth_rig.skin(body, arm)
    if paint:
        import mammoth_paint
        mammoth_paint.unwrap(body)
        report["uv_layout"] = mammoth_paint.uv_layout(body)
        report["textures"], report["coverage"] = mammoth_paint.build_texture(body, size=tex)
    work_layer(False)
    if arm is not None:
        arm.hide_render = True
    return body, arm, report


def build_all(tex=1024, body_tris=2600, paint=True, clips=True):
    body, rig, report = build_model(tex, body_tris, paint)
    if clips:
        import mammoth_anim
        report["clips"] = {n: int(a["frames"]) for n, a in mammoth_anim.build_clips().items()}
        mammoth_anim.clear()
    return report


def export():
    import beast_export, mammoth_anim
    return (beast_export.export_model(RIG, ("MammothBody",), "Mammoth", "T_Mammoth") +
            beast_export.export_clips(mammoth_anim, RIG, "Mammoth"))
