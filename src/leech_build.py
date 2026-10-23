"""Build the leech (2026-10-23): body -> rig -> weights -> UVs -> painted skin -> clips, review renders, checks,
export. Its own file, blender/leech.blend (scene Leech, cameras LCH_CAM_*), built headless:

    blender.exe -b --factory-startup --python tools/creature_run.py -- leech build review game clips lowest trace sheets closeups hero export
    blender.exe -b --factory-startup blender/leech.blend --python tools/creature_run.py -- leech paint review
"""
import bpy, os
import numpy as np
from beast_common import ROOT
import beast_rig, beast_review as RV
import leech_body as LB

NAME, RIG, BODY = LB.NAME, LB.RIG, LB.BODY
P = "LCH_"
VIEWS = ("Front", "Side", "Top", "Below", "34", "34R", "Rear", "Face", "HeadSide", "Mouth")


def blend_path():
    return os.path.join(ROOT, "blender", "leech.blend")


def setup_scene():
    scn = RV.new_scene(NAME, P)
    c = lambda n, loc, tgt, **kw: RV.cam(scn, P + n, loc, tgt, **kw)
    c("CAM_Front", (0, -8, 0.15), (0, 0, 0.15), ortho=0.8)
    c("CAM_Side", (8, 0.0, 0.2), (0, 0.0, 0.2), ortho=2.1)
    c("CAM_Top", (0, 0.0, 8), (0, 0.0001, 0.05), ortho=2.1)
    c("CAM_Below", (0, 0.0, -8), (0, 0.0001, 0.05), ortho=2.1)
    c("CAM_34", (1.6, -2.2, 1.3), (0, -0.05, 0.08), lens=40)
    c("CAM_34R", (-1.6, -2.2, 1.3), (0, -0.05, 0.08), lens=40)
    c("CAM_Rear", (-1.2, 2.4, 1.2), (0, 0.1, 0.08), lens=40)
    c("CAM_Face", (0.45, -1.45, 0.38), (0, -0.82, 0.07), lens=60)
    c("CAM_HeadSide", (4, -0.72, 0.08), (0, -0.72, 0.08), ortho=0.5)
    c("CAM_Mouth", (0.12, -1.55, 0.16), (0, -0.90, 0.07), lens=70)
    c("CAM_ClipSide", (10, -0.3, 0.45), (0, -0.3, 0.45), ortho=2.8)
    c("CAM_Clip34", (2.1, -2.8, 1.7), (0, -0.35, 0.18), lens=36)
    RV.game_cams(scn, P, (0, 0, 0.1))
    for i, az in enumerate((90, -90, 30, 210)):
        RV.game_cam(scn, f"{P}CAM_GameW{i}", az, (0.8, 0.0, 0.25))
    c("CAM_Scale", (3.2, -3.6, 2.0), (0.7, -0.1, 0.25), lens=40)
    scn.camera = bpy.data.objects[P + "CAM_34"]
    return scn


def build_model(tex=1024):
    import leech_paint
    setup_scene()
    ob = bpy.data.objects.get(BODY)
    if ob is not None:
        bpy.data.objects.remove(ob, do_unlink=True)
    body, W = LB.build_body()
    report = {"tris": LB.tri_report(body)}
    rig = beast_rig.build_armature(LB.rest_bones(), name=RIG, coll_name=P + "Rig")
    report["bones"] = len(rig.data.bones)
    report["weights"] = LB.skin(body, rig, W)
    leech_paint.unwrap(body)
    report["textures"], report["coverage"] = leech_paint.build_texture(body, size=tex)
    report["uv_layout"] = RV.uv_png(body, "uv_layout_leech", tex=report["textures"][0])
    report["uv_overlap"] = RV.uv_overlap([body])
    nm = sum(1 for e in body.data.edges if len([p for p in body.data.polygons if e.key in p.edge_keys]) != 2) \
        if len(body.data.edges) < 20000 else -1
    report["nonmanifold"] = nm
    rig.hide_render = True
    return body, rig, report


def build():
    body, rig, rep = build_model()
    return rep


def paint():
    import leech_paint
    body = bpy.data.objects[BODY]
    paths, cov = leech_paint.build_texture(body)
    RV.uv_png(body, "uv_layout_leech", tex=paths[0])
    return paths


def review(views=VIEWS, res=900):
    setup_scene()
    RV.show_wolf(False)
    out = []
    ground = bpy.data.objects.get("Ground")
    for v in views:
        if ground is not None:
            ground.hide_render = v == "Below"
        out.append(RV.shot(P + "CAM_" + v, f"leech_{v.lower()}", res=res))
    if ground is not None:
        ground.hide_render = False
    return out


def game():
    setup_scene()
    RV.add_wolf(P, at=(1.6, 0.0, 0.0))
    RV.show_wolf(False)
    out = [RV.game_sheet([f"{P}CAM_Game{i}" for i in range(4)], "leech_game_sheet")]
    RV.show_wolf(True)
    out.append(RV.game_sheet([f"{P}CAM_GameW{i}" for i in range(4)], "leech_vs_wolf_game", crop=220))
    out.append(RV.shot(P + "CAM_Scale", "leech_vs_wolf_34", res=1000))
    RV.show_wolf(False)
    return out


def anim():
    import leech_anim
    return leech_anim


def clips():
    A = anim()
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def lowest():
    return RV.lowest(anim(), (BODY,))


def trace():
    A = anim()
    return {c: RV.motion_trace(A, RIG, c, bones=("Head", "Sucker", "Body5")) for c in sorted(A.MOVING)}


def sheets(res=380):
    setup_scene()
    A = anim()
    return [RV.frames_sheet(A, RIG, n, A.SHEET_FRAMES[n], (P + "CAM_Clip34", P + "CAM_ClipSide"), f"leech_clip_{n}",
                            res=res) for n in A.CLIPS]


def closeups():
    setup_scene()
    A = anim()
    return [RV.frames_sheet(A, RIG, "Lunge", (12, 18, 30, 40), (P + "CAM_Clip34",), "leech_frames_Lunge"),
            RV.frames_sheet(A, RIG, "Crawl", (0, 12, 24, 42), (P + "CAM_34",), "leech_frames_Crawl"),
            RV.frames_sheet(A, RIG, "Death", (20, 36, 60), (P + "CAM_34", P + "CAM_Top"), "leech_frames_Death"),
            RV.frames_sheet(A, RIG, "Idle", (0, 22, 45), (P + "CAM_Face",), "leech_frames_Idle")]


def hero(res=1000):
    setup_scene()
    A = anim()
    RV.cam(bpy.context.scene, P + "CAM_Hero", (1.5, -2.0, 0.95), (0.0, -0.35, 0.18), lens=40)
    A.use("Crawl")
    bpy.context.scene.frame_set(24)
    out = [RV.shot(P + "CAM_Hero", "leech_hero", res=res)]
    A.use("Lunge")
    bpy.context.scene.frame_set(12)
    out.append(RV.shot(P + "CAM_Hero", "leech_hero_rear", res=res))
    A.clear()
    return out


def export():
    import beast_export
    A = anim()
    A.build_clips()
    A.clear()
    return (beast_export.export_model(RIG, (BODY,), NAME, "T_Leech") +
            beast_export.export_clips(A, RIG, NAME))
