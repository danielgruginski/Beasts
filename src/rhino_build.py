"""Rebuild the woolly rhino (the woods' boss) from scratch: body -> rig -> weights -> UVs -> painted coat -> the spear
split off -> clips. Run inside Blender with the Rhino scene on screen (rhino_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, rhino_body

RIG = "RhinoRig"


def reload_all():
    import beast_paint, beast_anim, beast_export
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_paint, beast_anim, beast_export, rhino_body]
    for name in ("rhino_rig", "rhino_paint", "rhino_anim"):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        importlib.reload(m)


def setup_scene():
    """The Rhino scene: shared lights and ground, cameras framed for the rhino (RHN_CAM_*), and a wolf beside it
    for scale (an instance of the Wolf scene's body, not exported)."""
    scn = beast_scene.setup_scene("Rhino", prefix="RHN_")
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "RHN_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -14, 0.95), (0, 0, 0.95), ortho=2.6)
    c("CAM_Side", (14, -0.25, 0.95), (0, -0.25, 0.95), ortho=4.4)
    c("CAM_Top", (0, -0.25, 14), (0, -0.2499, 0), ortho=4.4)
    c("CAM_34", (3.7, -4.9, 2.7), (0, -0.35, 0.85), lens=50)
    c("CAM_Face", (1.35, -3.6, 1.65), (0, -1.55, 1.05), lens=70)
    c("CAM_HeadSide", (6, -1.55, 1.15), (0, -1.55, 1.15), ortho=1.4)
    c("CAM_HeadFront", (0, -6, 1.1), (0, 0, 1.1), ortho=1.4)
    c("CAM_Rear", (-3.0, 4.4, 2.9), (0, 0.3, 0.8), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, -0.2, 0.8), lens=300)
    scn.camera = bpy.data.objects["RHN_CAM_34"]
    wolf = bpy.data.collections.get("WLF_Body")
    inst = bpy.data.objects.get("RHN_ScaleWolf")
    if wolf is not None and inst is None:
        inst = bpy.data.objects.new("RHN_ScaleWolf", None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = wolf
        inst.location = (2.2, 0.9, 0)
        inst.hide_select = True
    if inst is not None and inst.name not in scn.collection.objects:
        scn.collection.objects.link(inst)
    return scn


def show():
    scn = bpy.data.scenes.get("Rhino") or setup_scene()
    beast_scene.show_scene(scn)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("RHN_Work")
    if lc is not None:
        lc.exclude = not on


def build_body(body_tris=2000):
    assert bpy.context.scene.name == "Rhino", "put the Rhino scene on screen first: rhino_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = rhino_body.build_body(target_tris=body_tris)
    work_layer(False)
    return body, {"tris": rhino_body.tri_report(body)}


def build_model(tex=1024, body_tris=2000, paint=True):
    """Body -> rig -> weights -> UVs -> painted coat (the spear still part of RhinoBody). -> (body, rig, report)"""
    import rhino_rig, rhino_paint
    assert bpy.context.scene.name == "Rhino", "put the Rhino scene on screen first: rhino_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = rhino_body.build_body(target_tris=body_tris)
    rig = beast_rig.build_armature(rhino_body.rest_bones(), name=RIG, coll_name="RHN_Rig")
    report = {"weights": rhino_rig.skin(body, rig), "tris": rhino_body.tri_report(body)}
    if paint:
        rhino_paint.unwrap(body)
        report["uv_layout"] = rhino_paint.uv_layout(body)
        report["textures"], report["coverage"] = rhino_paint.build_texture(body, size=tex)
    work_layer(False)
    rig.hide_render = True
    return body, rig, report


def build_all(tex=1024, body_tris=2000, paint=True, clips=True):
    import rhino_rig
    body, rig, report = build_model(tex, body_tris, paint)
    report["spear"] = rhino_rig.split_spear(body, rig)
    if clips:
        import rhino_anim
        report["clips"] = {n: int(a["frames"]) for n, a in rhino_anim.build_clips().items()}
        rhino_anim.clear()
    return report


def export():
    import beast_export, rhino_anim
    return (beast_export.export_model(RIG, ("RhinoBody", "Spear"), "Rhino", "T_Rhino") +
            beast_export.export_clips(rhino_anim, RIG, "Rhino"))
