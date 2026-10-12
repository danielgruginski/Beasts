"""Rebuild the red deer stag from scratch: body -> rig -> weights -> UVs -> painted coat -> clips (2026-10-11).
Run inside Blender with the Deer scene on screen (deer_build.show() puts it there)."""
import bpy, importlib
import beast_common, beast_scene, beast_rig, beast_body, beast_coat, deer_body

RIG = "DeerRig"
VIEWS = ("Front", "Side", "Top", "34", "Face", "HeadSide", "Rear", "Colony", "Legs", "Antlers")


def reload_all():
    import beast_paint, beast_anim, beast_export
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_coat, beast_paint, beast_anim, beast_export,
            deer_body]
    for name in ("deer_rig", "deer_paint", "deer_anim"):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        importlib.reload(m)


def setup_scene():
    """The Deer scene: shared lights and ground, cameras framed for the stag (DER_CAM_*), and a wolf beside it for
    scale (an instance of the Wolf scene's body, not exported)."""
    scn = beast_scene.setup_scene("Deer", prefix="DER_")
    if scn.render.engine == 'BLENDER_WORKBENCH':           # a new scene came up in Workbench: no material preview
        for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scn.render.engine = eng
                break
            except TypeError:
                pass
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "DER_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -14, 1.18), (0, 0, 1.18), ortho=3.0)
    c("CAM_Side", (14, 0.45, 1.30), (0, 0.45, 1.30), ortho=4.2)
    c("CAM_Top", (0, 0.45, 14), (0, 0.4501, 0), ortho=4.2)
    c("CAM_34", (2.9, -4.0, 2.4), (0, -0.30, 1.05), lens=50)
    c("CAM_Face", (0.95, -2.55, 1.85), (0, -1.12, 1.48), lens=70)
    c("CAM_HeadSide", (6, -1.05, 1.62), (0, -1.05, 1.62), ortho=1.45)
    c("CAM_HeadFront", (0, -6, 1.62), (0, 0, 1.62), ortho=1.45)
    c("CAM_Rear", (-2.3, 3.4, 2.2), (0, 0.3, 0.95), lens=50)
    c("CAM_Colony", (0, -26, 31), (0, -0.3, 0.9), lens=300)
    c("CAM_Legs", (0.75, -1.25, 0.42), (0.14, -0.45, 0.30), lens=50)
    c("CAM_Antlers", (0.9, -2.0, 2.1), (0.15, -0.95, 1.85), lens=50)
    scn.camera = bpy.data.objects["DER_CAM_34"]
    wolf = bpy.data.collections.get("WLF_Body")
    inst = bpy.data.objects.get("DER_ScaleWolf")
    if wolf is not None and inst is None:
        inst = bpy.data.objects.new("DER_ScaleWolf", None)
        inst.instance_type = 'COLLECTION'
        inst.instance_collection = wolf
        inst.hide_select = True
    if inst is not None:
        inst.location = (1.15, 1.85, 0)              # beside and behind: clear of the stag in every view
        if inst.name not in scn.collection.objects:
            scn.collection.objects.link(inst)
    return scn


def show():
    """Put the Deer scene on screen (created if missing), viewports in material preview from the 3/4 view."""
    scn = bpy.data.scenes.get("Deer") or setup_scene()
    beast_scene.show_scene(scn)
    beast_scene.frame_viewports(shading='MATERIAL', lift=0.6, distance=6.0)


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("DER_Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024, body_tris=2600, paint=True, rig=True):
    """Body -> rig -> weights -> UVs -> painted coat. -> (body, rig, report)"""
    assert bpy.context.scene.name == "Deer", "put the Deer scene on screen first: deer_build.show()"
    setup_scene()
    work_layer(True)
    body, hi = deer_body.build_body(target_tris=body_tris)
    report = {"tris": deer_body.tri_report(body)}
    arm = None
    if rig:
        import deer_rig
        arm = beast_rig.build_armature(deer_body.rest_bones(), name=RIG, coll_name="DER_Rig")
        report["weights"] = deer_rig.skin(body, arm)
    if paint:
        import deer_paint
        deer_paint.unwrap(body)
        report["uv_layout"] = deer_paint.uv_layout(body)
        report["textures"], report["coverage"] = deer_paint.build_texture(body, size=tex)
    work_layer(False)
    if arm is not None:
        arm.hide_render = True
    return body, arm, report


def build_all(tex=1024, body_tris=2600, paint=True, clips=True):
    """Body, rig, weights, UVs, the painted coat, then the clips."""
    body, rig, report = build_model(tex, body_tris, paint)
    if clips:
        import deer_anim
        report["clips"] = {n: int(a["frames"]) for n, a in deer_anim.build_clips().items()}
        deer_anim.clear()
    return report


# clip sheets: rows = cameras, columns = frames (key poses)
SHEET_FRAMES = {"Idle": (0, 24, 44, 60, 84, 100), "Graze": (0, 30, 72, 84, 96, 108), "Alert": (0, 4, 10, 18, 22, 44),
                "Walk": (0, 6, 12, 18, 24, 30), "Trot": (0, 4, 8, 12, 16), "Run": (0, 2, 4, 7, 9, 11),
                "Attack": (0, 9, 13, 15, 20, 30), "Hit": (0, 3, 7, 11), "Death": (0, 14, 24, 32, 40, 52, 66),
                "Sleep": (0, 60), "Wake": (0, 14, 26, 38, 48, 60)}


def clip_cameras():
    scn = bpy.data.scenes["Deer"]
    beast_scene._cam(scn, "DER_CAM_ClipSide", (12, -0.30, 1.20), (0, -0.30, 1.20), ortho=3.2)
    beast_scene._cam(scn, "DER_CAM_Clip34", (3.0, -4.2, 2.3), (0, -0.25, 0.95), lens=45)
    beast_scene._cam(scn, "DER_CAM_ColonySide", (26, -0.3, 31), (0, -0.3, 0.9), lens=300)   # the colony camera,
                                                                                            # side-on


def clip_sheets(names=None, res=360):
    """Contact sheets of the clips' key frames from the side and 3/4: renders/deer_clip_<Name>.png."""
    import deer_anim
    clip_cameras()
    wolf = bpy.data.objects.get("DER_ScaleWolf")
    if wolf is not None:
        wolf.hide_render = True                    # the scale wolf stands in the side camera's frame
    paths = []
    for n in (names or deer_anim.CLIPS):
        deer_anim.use(n)
        paths.append(beast_scene.render_sheet(n, SHEET_FRAMES[n], cams=("DER_CAM_ClipSide", "DER_CAM_Clip34"),
                                              rig_name=RIG, res=res, out="deer_clip_" + n))
        if n == "Run":                                 # the clip it uses most, from the game's camera
            paths.append(beast_scene.render_sheet(n, (0, 4, 7, 11), cams=("DER_CAM_Colony", "DER_CAM_ColonySide"),
                                                  rig_name=RIG, res=res, out="deer_clip_Run_colony"))
    deer_anim.clear()
    if wolf is not None:
        wolf.hide_render = False
    return paths


def export():
    """export/Deer.fbx (DeerRig + DeerBody: the antlers are part of the one mesh), Textures/T_Deer.png,
    Anims/Deer@<clip>.fbx + deer_clips.json."""
    import beast_export, deer_anim
    return (beast_export.export_model(RIG, ("DeerBody",), "Deer", "T_Deer") +
            beast_export.export_clips(deer_anim, RIG, "Deer"))


def review(prefix="deer", views=VIEWS, res=1000):
    """Renders of the bind pose into renders/ (deer_front.png ...)."""
    return [beast_scene.shot("DER_CAM_" + v, f"{prefix}_{v.lower()}", res=res) for v in views]


def review_test_pose(res=1000):
    """The rig's stress test (jaw open, head turned, a stride, ears and tail), rendered, then back to the bind pose."""
    import deer_rig
    rig = bpy.data.objects[RIG]
    deer_rig.test_pose(rig)
    paths = [beast_scene.shot("DER_CAM_34", "deer_testpose_34", res=res),
             beast_scene.shot("DER_CAM_Side", "deer_testpose_side", res=res),
             beast_scene.shot("DER_CAM_HeadFront", "deer_testpose_head", res=res)]
    beast_rig.reset_pose(rig)
    return paths


JOIN_VIEWS = {  # close-ups of where the lower legs leave the body: (camera, target)
    "shoulderL": ((1.0, -0.55, 0.85), (0.14, -0.44, 0.66)), "shoulderR": ((-1.0, -0.55, 0.85), (-0.14, -0.44, 0.66)),
    "stifleL": ((1.0, 0.30, 0.80), (0.14, 0.42, 0.64)), "stifleR": ((-1.0, 0.30, 0.80), (-0.14, 0.42, 0.64)),
    "shoulderL34": ((0.8, -1.2, 0.95), (0.14, -0.44, 0.66)), "stifleL34": ((0.8, 1.2, 0.95), (0.14, 0.42, 0.64)),
}


def review_joins(views=JOIN_VIEWS, res=800):
    """The leg joins in the rig's stress test (a stride: the left foreleg lifted, the hind legs apart), close up from
    the side and 3/4; then back to the bind pose. renders/deer_join_<view>.png"""
    import deer_rig
    scn = bpy.context.scene
    rig = bpy.data.objects[RIG]
    deer_rig.test_pose(rig)
    paths = []
    for name, (loc, tgt) in views.items():
        beast_scene._cam(scn, "DER_CAM_Join", loc, tgt, lens=50)
        paths.append(beast_scene.shot("DER_CAM_Join", "deer_join_" + name, res=res))
    beast_rig.reset_pose(rig)
    return paths
