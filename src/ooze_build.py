"""Rebuild the dungeon ooze in the Ooze scene of blender/beasts.blend (2026-10-12):

    import ooze_build
    ooze_build.show()          # the Ooze scene on screen (in its own call: the switch applies after it returns)
    ooze_build.build_all()     # shell -> contents -> rig + weights -> UVs -> 2 textures -> materials -> clips
    ooze_build.export()        # export/Ooze.fbx, Textures/T_Ooze*.png, Anims/Ooze@<clip>.fbx + ooze_clips.json

shell (ooze_body) -> contents (ooze_contents) -> rig (ooze_rig) -> UVs, textures, materials (ooze_paint) ->
clips (ooze_anim). Review renders (EEVEE) with review(), clip sheets with clip_sheets().
"""
import importlib, time
import bpy

import beast_common, ooze_scene, ooze_body, ooze_contents, ooze_paint

RIG = "OozeRig"
MESHES = ("OozeBody", "OozeContents")


def reload_all():
    mods = [beast_common, ooze_scene, ooze_body, ooze_contents, ooze_paint]
    for name in ("beast_rig", "beast_export", "ooze_rig", "ooze_anim"):
        mods.append(importlib.import_module(name))
    for m in mods:
        importlib.reload(m)


def show():
    """Create the Ooze scene if needed and put it on screen, material preview."""
    scn = ooze_scene.setup_scene("Ooze")
    ooze_scene.show_scene(scn)
    ooze_scene.frame_viewports(shading='MATERIAL', distance=5.5)
    return scn


def build_model(rig=True):
    """Shell, contents, rig and weights, UVs, textures, materials. -> report"""
    reload_all()
    import ooze_rig
    scn = bpy.data.scenes["Ooze"]
    assert bpy.context.window_manager.windows[0].scene == scn, "put the Ooze scene on screen first: ooze_build.show()"
    ooze_scene.setup_scene(scn.name)
    for n in MESHES:                     # start clean: an Armature modifier left on the shell would be applied with
        beast_common.remove_obj(n)       # the decimation (in whatever pose the rig holds)
    coll = beast_common.get_coll("OOZ_Body", scene=scn)
    rep = {}
    t = time.time()
    body, rep["shell"] = ooze_body.build_shell(coll)
    cont, rep["contents"] = ooze_contents.build_contents(coll)
    rep["contents"].pop("pieces", None)
    ooze_paint.unwrap_shell(body)
    ooze_paint.unwrap_contents(cont)
    img, rep["paint_shell"] = ooze_paint.paint_shell(body)
    ooze_paint.assign(body, ooze_paint.shell_material(img))
    img2, rep["paint_contents"] = ooze_paint.paint_contents(cont)
    ooze_paint.assign(cont, ooze_paint.contents_material(img2))
    ooze_paint.uv_layout(body, "ooze")
    ooze_paint.uv_layout(cont, "ooze_contents")
    ooze_paint.check_sheet("T_Ooze", "ooze", "check_tex_ooze")
    ooze_paint.check_sheet("T_OozeContents", "ooze_contents", "check_tex_contents")
    if rig:
        arm = ooze_rig.build(scn)
        rep["weights"] = ooze_rig.skin(body, cont, arm)
    ooze_scene.add_scale_human(scn)
    rep["tris_total"] = rep["shell"]["tris"] + rep["contents"]["tris"]
    rep["seconds"] = round(time.time() - t, 1)
    return rep


def build_all(clips=True):
    rep = build_model()
    if clips:
        import ooze_anim
        rep["clips"] = {n: int(a["frames"]) for n, a in ooze_anim.build_clips().items()}
        ooze_anim.clear()
    return rep


def review(res=900):
    """The review set in renders/: hero, 3/4, rear, close, front, side, top, colony camera, and the scale shot."""
    out = [ooze_scene.shot(c, res=res) for c in ("CAM_Low", "CAM_34", "CAM_Rear", "CAM_Close", "CAM_Front",
                                                 "CAM_Side", "CAM_Top")]
    out.append(ooze_scene.shot("CAM_Colony", res=500))
    ref = bpy.data.collections.get("OOZ_Ref")
    if ref is not None:
        for o in ref.objects:
            o.hide_render = o.type == 'ARMATURE'
        out.append(ooze_scene.shot("CAM_Scale", res=res))
        for o in ref.objects:
            o.hide_render = True
    return out


def clip_sheets(names=None, res=320):
    """Contact sheets of the clips' key frames from the side and 3/4: renders/ooze_clip_<Name>.png."""
    import ooze_anim
    paths = []
    for n in (names or ooze_anim.CLIPS):
        ooze_anim.use(n)
        paths.append(ooze_scene.render_sheet(n, ooze_anim.SHEET_FRAMES[n], rig_name=RIG, res=res))
    ooze_anim.clear()
    return paths


def export():
    """export/Ooze.fbx (OozeRig + OozeBody + OozeContents), Textures/T_Ooze.png + T_OozeContents.png,
    Anims/Ooze@<clip>.fbx + ooze_clips.json."""
    import beast_export, ooze_anim
    return (beast_export.export_model(RIG, MESHES, "Ooze", "T_Ooze") +
            beast_export.export_clips(ooze_anim, RIG, "Ooze"))
