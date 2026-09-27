"""Rebuild the wolf from scratch: body -> rig -> weights -> UVs -> painted textures. Run inside Blender with the Wolf
scene on screen."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, wolf_body


def reload_all():
    import beast_body, beast_paint, beast_anim, wolf_rig, wolf_paint, beast_export, wolf_anim
    for m in (beast_common, beast_scene, beast_rig, beast_body, beast_paint, beast_anim, wolf_body, wolf_rig, wolf_paint,
              beast_export, wolf_anim):
        importlib.reload(m)


def work_layer(on):
    """WLF_Work (dense bake source, fused parts) must be in the view layer while building."""
    lc = bpy.context.view_layer.layer_collection.children.get("WLF_Work")
    if lc is not None:
        lc.exclude = not on


def build_all(tex=1024, body_tris=4000, paint=True, clips=True):
    import wolf_rig, wolf_paint
    assert bpy.context.scene.name == "Wolf", "put the Wolf scene on screen first: wolf_build.show()"
    beast_scene.setup_scene("Wolf")
    work_layer(True)
    body, hi = wolf_body.build_body(target_tris=body_tris)
    rig = beast_rig.build_armature(wolf_body.rest_bones())
    report = {"weights": wolf_rig.skin(body, rig), "tris": wolf_body.tri_report(body)}
    if paint:
        wolf_paint.unwrap(body)
        report["uv_layout"] = wolf_paint.uv_layout(body)
        report["textures"], report["coverage"] = wolf_paint.build_texture(body, hi, size=tex)
    if clips:
        import wolf_anim
        report["clips"] = {n: int(a["frames"]) for n, a in wolf_anim.build_clips().items()}
        wolf_anim.clear()
    work_layer(False)
    return report


def export():
    import beast_export, wolf_anim
    return beast_export.export_model() + beast_export.export_clips(wolf_anim)


def show():
    """Put the Wolf scene on screen (created if missing), viewports in material preview from the 3/4 view."""
    scn = bpy.data.scenes.get("Wolf") or beast_scene.setup_scene("Wolf")
    beast_scene.show_scene(scn)
    beast_scene.frame_viewports(shading='MATERIAL')
