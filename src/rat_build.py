"""Rebuild the giant rat from scratch: body -> rig -> weights -> UVs -> painted coats -> clips. Run inside Blender with
the Rat scene on screen (rat_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, rat_body

RIG = "RatRig"


def reload_all():
    import beast_paint, beast_anim, beast_export, rat_rig, rat_paint, rat_anim
    for m in (beast_common, beast_scene, beast_rig, beast_body, beast_paint, beast_anim, beast_export, rat_body,
              rat_rig, rat_paint, rat_anim):
        importlib.reload(m)


def setup_scene():
    """The Rat scene: shared lights and ground, cameras framed for the rat (RAT_CAM_*)."""
    scn = beast_scene.setup_scene("Rat", prefix="RAT_")
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "RAT_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -6, 0.25), (0, 0, 0.25), ortho=0.9)
    c("CAM_Side", (6, 0.05, 0.28), (0, 0.05, 0.28), ortho=1.6)
    c("CAM_Top", (0, 0.1, 6), (0, 0.1001, 0), ortho=1.7)
    c("CAM_34", (1.25, -1.55, 0.95), (0, -0.05, 0.2), lens=50)
    c("CAM_Face", (0.42, -1.2, 0.48), (0, -0.46, 0.29), lens=70)
    c("CAM_HeadSide", (3, -0.47, 0.30), (0, -0.47, 0.30), ortho=0.32)
    c("CAM_Rear", (-1.0, 1.9, 0.9), (0, 0.2, 0.2), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, 0, 0.2), lens=300)
    scn.camera = bpy.data.objects["RAT_CAM_34"]
    return scn


def show():
    scn = bpy.data.scenes.get("Rat") or setup_scene()
    beast_scene.show_scene(scn)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("RAT_Work")
    if lc is not None:
        lc.exclude = not on


def build_all(tex=1024, body_tris=2100, paint=True, clips=True):
    import rat_rig, rat_paint
    assert bpy.context.scene.name == "Rat", "put the Rat scene on screen first: rat_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = rat_body.build_body(target_tris=body_tris)
    rig = beast_rig.build_armature(rat_body.rest_bones(), name=RIG, coll_name="RAT_Rig")
    report = {"weights": rat_rig.skin(body, rig), "tris": rat_body.tri_report(body)}
    if paint:
        rat_paint.unwrap(body)
        report["uv_layout"] = rat_paint.uv_layout(body)
        report["textures"], report["coverage"] = rat_paint.build_texture(body, size=tex)
    if clips:
        import rat_anim
        report["clips"] = {n: int(a["frames"]) for n, a in rat_anim.build_clips().items()}
        rat_anim.clear()
    work_layer(False)
    rig.hide_render = True
    return report


def export():
    import beast_export, rat_anim
    return (beast_export.export_model(RIG, ("RatBody",), "Rat", "T_Rat") +
            beast_export.export_clips(rat_anim, RIG, "Rat"))
