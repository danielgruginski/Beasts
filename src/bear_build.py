"""Rebuild the cave bear from scratch: body -> rig -> weights -> UVs -> painted coat -> clips. Run inside Blender
with the Bear scene on screen (bear_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, beast_coat, bear_body

RIG = "BearRig"


def reload_all():
    import beast_paint, beast_anim, beast_export
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_coat, beast_paint, beast_anim, beast_export,
            bear_body]
    for name in ("bear_rig", "bear_paint", "bear_anim"):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        importlib.reload(m)


def setup_scene():
    """The Bear scene: shared lights and ground, cameras framed for the bear (BER_CAM_*), and a wolf beside it for
    scale (an instance of the Wolf scene's body, not exported)."""
    scn = beast_scene.setup_scene("Bear", prefix="BER_")
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "BER_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -14, 0.80), (0, 0, 0.80), ortho=2.2)
    c("CAM_Side", (14, -0.25, 0.80), (0, -0.25, 0.80), ortho=3.6)
    c("CAM_Top", (0, -0.25, 14), (0, -0.2499, 0), ortho=3.6)
    c("CAM_34", (3.1, -4.1, 2.3), (0, -0.35, 0.70), lens=50)
    c("CAM_Face", (1.05, -2.85, 1.30), (0, -1.30, 0.95), lens=70)
    c("CAM_HeadSide", (6, -1.30, 1.0), (0, -1.30, 1.0), ortho=1.1)
    c("CAM_HeadFront", (0, -6, 1.0), (0, 0, 1.0), ortho=1.1)
    c("CAM_Rear", (-2.6, 3.8, 2.4), (0, 0.3, 0.7), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, -0.2, 0.7), lens=300)
    scn.camera = bpy.data.objects["BER_CAM_34"]
    wolf = bpy.data.collections.get("WLF_Body")
    inst = bpy.data.objects.get("BER_ScaleWolf")
    if wolf is not None and inst is None:
        inst = bpy.data.objects.new("BER_ScaleWolf", None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = wolf
        inst.location = (1.9, 0.9, 0)
        inst.hide_select = True
    if inst is not None and inst.name not in scn.collection.objects:
        scn.collection.objects.link(inst)
    return scn


def show():
    scn = bpy.data.scenes.get("Bear") or setup_scene()
    beast_scene.show_scene(scn)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("BER_Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024, body_tris=2300, paint=True):
    """Body -> rig -> weights -> UVs -> painted coat. -> (body, rig, report)"""
    import bear_rig, bear_paint
    assert bpy.context.scene.name == "Bear", "put the Bear scene on screen first: bear_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = bear_body.build_body(target_tris=body_tris)
    rig = beast_rig.build_armature(bear_body.rest_bones(), name=RIG, coll_name="BER_Rig")
    report = {"weights": bear_rig.skin(body, rig), "tris": bear_body.tri_report(body)}
    if paint:
        bear_paint.unwrap(body)
        report["uv_layout"] = bear_paint.uv_layout(body)
        report["textures"], report["coverage"] = bear_paint.build_texture(body, size=tex)
    work_layer(False)
    rig.hide_render = True
    return body, rig, report


def build_all(tex=1024, body_tris=2300, paint=True, clips=True):
    body, rig, report = build_model(tex, body_tris, paint)
    if clips:
        import bear_anim
        report["clips"] = {n: int(a["frames"]) for n, a in bear_anim.build_clips().items()}
        bear_anim.clear()
    return report


def export():
    import beast_export, bear_anim
    return (beast_export.export_model(RIG, ("BearBody",), "Bear", "T_Bear") +
            beast_export.export_clips(bear_anim, RIG, "Bear"))
