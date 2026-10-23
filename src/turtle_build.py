"""Build the giant turtle (2026-10-23): body -> rig -> weights -> UVs -> painted hide and shell -> clips, review
renders, checks, export. Its own file, blender/turtle.blend (scene Turtle, cameras TRT_CAM_*), built headless:

    blender.exe -b --factory-startup --python tools/creature_run.py -- turtle build review game clips lowest trace sheets closeups hero export
    blender.exe -b --factory-startup blender/turtle.blend --python tools/creature_run.py -- turtle paint review
"""
import bpy, os
import numpy as np
from beast_common import ROOT
import beast_rig, beast_review as RV
import turtle_body as TB

NAME, RIG, BODY = TB.NAME, TB.RIG, TB.BODY
P = "TRT_"
VIEWS = ("Front", "Side", "Top", "Below", "34", "34R", "Rear", "Face", "FaceR", "HeadSide", "HeadFront")


def blend_path():
    return os.path.join(ROOT, "blender", "turtle.blend")


def setup_scene():
    scn = RV.new_scene(NAME, P)
    c = lambda n, loc, tgt, **kw: RV.cam(scn, P + n, loc, tgt, **kw)
    c("CAM_Front", (0, -12, 0.85), (0, 0, 0.85), ortho=2.8)
    c("CAM_Side", (12, 0.0, 0.85), (0, 0.0, 0.85), ortho=4.0)
    c("CAM_Top", (0, 0.0, 12), (0, 0.0001, 0.8), ortho=4.0)
    c("CAM_Below", (0, 0.0, -12), (0, 0.0001, 0.8), ortho=4.0)
    c("CAM_34", (4.2, -5.6, 3.4), (0, -0.15, 0.75), lens=40)
    c("CAM_34R", (-4.2, -5.6, 3.4), (0, -0.15, 0.75), lens=40)
    c("CAM_Rear", (-3.6, 5.4, 3.2), (0, 0.1, 0.75), lens=40)
    c("CAM_Face", (1.15, -3.25, 1.45), (0, -1.72, 0.86), lens=60)
    c("CAM_FaceR", (-1.15, -3.25, 1.45), (0, -1.72, 0.86), lens=60)
    c("CAM_HeadSide", (6, -1.72, 0.86), (0, -1.72, 0.86), ortho=0.85)
    c("CAM_HeadFront", (0, -6, 0.86), (0, 0, 0.86), ortho=0.85)
    c("CAM_ClipSide", (14, -0.2, 0.9), (0, -0.2, 0.9), ortho=4.4)
    c("CAM_Clip34", (4.6, -6.0, 3.6), (0, -0.3, 0.6), lens=36)
    c("CAM_ClipFace", (1.7, -4.1, 1.5), (0, -1.6, 0.65), lens=45)
    RV.game_cams(scn, P, (0, 0, 0.7))
    for i, az in enumerate((90, -90, 30, 210)):
        RV.game_cam(scn, f"{P}CAM_GameW{i}", az, (1.3, 0.0, 0.6))
    c("CAM_Scale", (5.6, -6.6, 3.4), (1.3, -0.2, 0.6), lens=40)
    scn.camera = bpy.data.objects[P + "CAM_34"]
    return scn


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get("TRT_Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024):
    import turtle_paint
    setup_scene()
    work_layer(True)
    ob = bpy.data.objects.get(BODY)
    if ob is not None:
        bpy.data.objects.remove(ob, do_unlink=True)
    body, acc, hi = TB.build_body()
    report = {"tris": TB.tri_report(body)}
    import zwolf_body
    report["tidy"] = dict(zwolf_body.TIDY)
    rig = beast_rig.build_armature(TB.rest_bones(), name=RIG, coll_name=P + "Rig")
    report["bones"] = len(rig.data.bones)
    report["weights"] = TB.skin(body, rig, acc)
    turtle_paint.unwrap(body)
    report["textures"], report["coverage"] = turtle_paint.build_texture(body, size=tex)
    report["uv_layout"] = RV.uv_png(body, "uv_layout_turtle", tex=report["textures"][0])
    report["uv_overlap"] = RV.uv_overlap([body])
    work_layer(False)
    rig.hide_render = True
    return body, rig, report


def build():
    body, rig, rep = build_model()
    return rep


def paint():
    import turtle_paint
    body = bpy.data.objects[BODY]
    work_layer(True)
    paths, cov = turtle_paint.build_texture(body)
    work_layer(False)
    RV.uv_png(body, "uv_layout_turtle", tex=paths[0])
    return paths


def review(views=VIEWS, res=900):
    setup_scene()
    RV.show_wolf(False)
    out = []
    ground = bpy.data.objects.get("Ground")
    for v in views:
        if ground is not None:
            ground.hide_render = v == "Below"
        out.append(RV.shot(P + "CAM_" + v, f"turtle_{v.lower()}", res=res))
    if ground is not None:
        ground.hide_render = False
    return out


def game():
    setup_scene()
    RV.add_wolf(P, at=(2.6, -0.2, 0.0))
    RV.show_wolf(False)
    out = [RV.game_sheet([f"{P}CAM_Game{i}" for i in range(4)], "turtle_game_sheet")]
    RV.show_wolf(True)
    out.append(RV.game_sheet([f"{P}CAM_GameW{i}" for i in range(4)], "turtle_vs_wolf_game", crop=240))
    out.append(RV.shot(P + "CAM_Scale", "turtle_vs_wolf_34", res=1000))
    RV.show_wolf(False)
    return out


def anim():
    import turtle_anim
    return turtle_anim


def clips():
    A = anim()
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def lowest():
    return RV.lowest(anim(), (BODY,))


def trace():
    A = anim()
    return {c: RV.motion_trace(A, RIG, c, bones=("Head", "FrontToesL", "Socket_Back")) for c in sorted(A.MOVING)}


def sheets(res=380):
    setup_scene()
    A = anim()
    return [RV.frames_sheet(A, RIG, n, A.SHEET_FRAMES[n], (P + "CAM_Clip34", P + "CAM_ClipSide"), f"turtle_clip_{n}",
                            res=res) for n in A.CLIPS]


def closeups():
    setup_scene()
    A = anim()
    face = P + "CAM_ClipFace"
    return [RV.frames_sheet(A, RIG, "Bite", (0, 11, 16, 22), (face,), "turtle_frames_Bite"),
            RV.frames_sheet(A, RIG, "Withdraw", (0, 12, 24, 36), (face, P + "CAM_34R"), "turtle_frames_Withdraw"),
            RV.frames_sheet(A, RIG, "Death", (20, 40, 75), (face, P + "CAM_Rear"), "turtle_frames_Death"),
            RV.frames_sheet(A, RIG, "Walk", (0, 12, 24, 36), (P + "CAM_34",), "turtle_frames_Walk"),
            RV.frames_sheet(A, RIG, "Idle", (0, 84), (face,), "turtle_frames_Idle")]


def hero(res=1000):
    setup_scene()
    A = anim()
    RV.cam(bpy.context.scene, P + "CAM_Hero", (3.3, -4.6, 2.1), (0.0, -0.45, 0.75), lens=40)
    A.use("Idle")
    bpy.context.scene.frame_set(84)
    out = [RV.shot(P + "CAM_Hero", "turtle_hero", res=res)]
    A.use("Withdraw")
    bpy.context.scene.frame_set(36)
    out.append(RV.shot(P + "CAM_Hero", "turtle_hero_withdrawn", res=res))
    A.clear()
    return out


def export():
    import beast_export
    A = anim()
    A.build_clips()
    A.clear()
    return (beast_export.export_model(RIG, (BODY,), NAME, "T_Turtle") +
            beast_export.export_clips(A, RIG, NAME))
