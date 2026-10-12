"""Rebuild the warg (2026-10-12): body -> rig -> weights -> UVs -> painted coats (-> clips, once there are some).
Run inside Blender with the Warg scene on screen (warg_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, warg_body

RIG = "WargRig"
VIEWS = ("Front", "Side", "Top", "34", "Face", "HeadSide", "Rear", "Colony")


def reload_all():
    import beast_paint, beast_anim, beast_export
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_paint, beast_anim, beast_export, warg_body]
    for name in ("warg_rig", "warg_paint", "warg_anim", "warg_tack"):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        importlib.reload(m)


def setup_scene():
    """The Warg scene: shared lights and ground, cameras framed for the warg (WRG_CAM_*), and a wolf beside it for
    scale (an instance of the Wolf scene's body, not exported)."""
    scn = beast_scene.setup_scene("Warg", prefix="WRG_")
    if scn.render.engine == 'BLENDER_WORKBENCH':
        for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scn.render.engine = eng
                break
            except TypeError:
                pass
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "WRG_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -14, 0.80), (0, 0, 0.80), ortho=2.4)
    c("CAM_Side", (14, -0.25, 0.80), (0, -0.25, 0.80), ortho=3.0)
    c("CAM_Top", (0, -0.25, 14), (0, -0.2499, 0), ortho=3.0)
    c("CAM_34", (2.6, -3.6, 1.8), (0, -0.30, 0.70), lens=50)
    c("CAM_Face", (0.75, -2.45, 1.30), (0, -1.10, 1.12), lens=70)
    c("CAM_HeadSide", (6, -1.05, 1.15), (0, -1.05, 1.15), ortho=0.65)
    c("CAM_HeadFront", (0, -6, 1.15), (0, 0, 1.15), ortho=0.65)
    c("CAM_Rear", (-2.0, 2.9, 1.7), (0, 0.2, 0.65), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, -0.25, 0.6), lens=300)
    c("CAM_Scale", (3.6, -4.6, 1.9), (0.9, -0.2, 0.65), lens=45)
    scn.camera = bpy.data.objects["WRG_CAM_34"]
    wolf = bpy.data.collections.get("WLF_Body")
    inst = bpy.data.objects.get("WRG_ScaleWolf")
    if wolf is not None and inst is None:
        inst = bpy.data.objects.new("WRG_ScaleWolf", None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = wolf
        inst.hide_select = True
    if inst is not None:
        inst.location = (1.45, 0.9, 0)               # beside and behind: clear of the warg in the front views
        if inst.name not in scn.collection.objects:
            scn.collection.objects.link(inst)
    return scn


def show():
    """Put the Warg scene on screen (created if missing), viewports in material preview from the 3/4 view."""
    scn = bpy.data.scenes.get("Warg") or setup_scene()
    beast_scene.show_scene(scn)
    beast_scene.frame_viewports(shading='MATERIAL', lift=0.25, distance=5.4)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("WRG_Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024, body_tris=4300, paint=True, rig=True):
    """Body -> rig -> weights -> UVs -> painted coats. -> (body, rig, report)"""
    assert bpy.context.scene.name == "Warg", "put the Warg scene on screen first: warg_build.show()"
    reload_all()
    setup_scene()
    work_layer(True)
    body, hi = warg_body.build_body(target_tris=body_tris)
    report = {"tris": warg_body.tri_report(body)}
    arm = None
    if rig:
        import warg_rig
        arm = beast_rig.build_armature(warg_body.rest_bones(), name=RIG, coll_name="WRG_Rig")
        report["weights"] = warg_rig.skin(body, arm)
    if paint:
        import warg_paint
        warg_paint.unwrap(body)
        report["uv_layout"] = warg_paint.uv_layout(body)
        report["textures"], report["coverage"] = warg_paint.build_texture(body, hi, size=tex)
    work_layer(False)
    if arm is not None:
        arm.hide_render = True
    return body, arm, report


def review(prefix="warg", views=VIEWS, res=900, engine='BLENDER_EEVEE_NEXT'):
    """Renders of the bind pose into renders/ (warg_front.png ...). EEVEE by default: the material (normal map,
    smoothness) shows, which Workbench's textured studio light does not."""
    return [beast_scene.shot("WRG_CAM_" + v, f"{prefix}_{v.lower()}", engine=engine, res=res) for v in views]


def export():
    """Warg.fbx (WargBody, WargTack, WargMask on WargRig), the clips and the T_Warg* textures into export/."""
    import beast_export, warg_anim
    warg_anim.build_clips()
    return (beast_export.export_model("WargRig", ("WargBody", "WargTack", "WargMask"), "Warg", "T_Warg") +
            beast_export.export_clips(warg_anim, "WargRig", "Warg"))
