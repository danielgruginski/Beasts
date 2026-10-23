"""Build the giant bat (2026-10-23): body -> rig -> weights -> UVs -> painted hide -> the wings split off -> clips,
review renders, checks, export. Its own file, blender/bat.blend (scene Bat, cameras BAT_CAM_*), built headless:

    blender.exe -b --factory-startup --python tools/creature_run.py -- bat build review game clips lowest trace sheets closeups export
    blender.exe -b --factory-startup blender/bat.blend --python tools/creature_run.py -- bat paint review

Steps (tools/creature_run.py calls them by name): build, paint, review, game, clips, lowest, trace, sheets, closeups,
export.
"""
import bpy, math, os
import numpy as np
from mathutils import Vector
from beast_common import ROOT
import beast_scene, beast_rig, beast_review as RV
import bat_body as BB

NAME, RIG, BODY, WING_OB = BB.NAME, BB.RIG, BB.BODY, BB.WING_OB
P = "BAT_"
H = BB.H
VIEWS = ("Front", "Side", "Top", "Below", "34", "34R", "Rear", "Face", "FaceR", "HeadSide", "HeadFront", "Wing")


def blend_path():
    return os.path.join(ROOT, "blender", "bat.blend")


def setup_scene():
    scn = RV.new_scene(NAME, P, lift=H)
    c = lambda n, loc, tgt, **kw: RV.cam(scn, P + n, loc, tgt, **kw)
    c("CAM_Front", (0, -9, H + 0.05), (0, 0, H + 0.05), ortho=3.4)
    c("CAM_Side", (9, 0.05, H), (0, 0.05, H), ortho=1.9)
    c("CAM_Top", (0, 0.05, H + 9), (0, 0.0501, H), ortho=3.4)
    c("CAM_Below", (0, 0.05, H - 9), (0, 0.0501, H), ortho=3.4)
    c("CAM_34", (2.1, -2.8, H + 1.45), (0, 0.04, H), lens=38)
    c("CAM_34R", (-2.1, -2.8, H + 1.45), (0, 0.04, H), lens=38)
    c("CAM_Rear", (-2.2, 3.8, H + 1.5), (0, 0.05, H), lens=40)
    c("CAM_Face", (0.62, -1.30, H + 0.32), (0, -0.33, H + 0.07), lens=70)
    c("CAM_FaceR", (-0.62, -1.30, H + 0.32), (0, -0.33, H + 0.07), lens=70)
    c("CAM_HeadSide", (4, -0.30, H + 0.12), (0, -0.30, H + 0.12), ortho=0.62)
    c("CAM_HeadFront", (0, -4, H + 0.12), (0, 0, H + 0.12), ortho=0.62)
    c("CAM_Wing", (1.45, -1.30, H + 1.75), (0.75, 0.10, H), lens=45)
    c("CAM_ClipSide", (12, -0.3, 1.05), (0, -0.3, 1.05), ortho=3.6)
    c("CAM_Clip34", (2.4, -3.2, H + 1.25), (0, -0.05, H - 0.10), lens=34)
    c("CAM_ClipFront", (0, -9, H + 0.4), (0, 0, H - 0.05), ortho=3.6)
    c("CAM_ClipLow", (1.9, -2.9, 1.9), (0, -0.45, 0.85), lens=30)
    RV.game_cams(scn, P, (0, -0.1, 0.9))
    for i, az in enumerate((90, -90, 30, 210)):            # the bat beside the wolf (at +2 m x)
        RV.game_cam(scn, f"{P}CAM_GameW{i}", az, (1.0, 0.0, 0.7))
    c("CAM_Scale", (4.6, -5.4, 2.9), (1.1, 0.0, 0.9), lens=40)
    scn.camera = bpy.data.objects[P + "CAM_34"]
    return scn


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get(P.rstrip("_") + "_Work")
    if lc is not None:
        lc.exclude = not on


def _wing_material(wing):
    """M_BatWing: M_Bat's texture, back faces culled: the membrane has an underside of its own (_two_layers), so each
    side shows its own faces and normals (the Unity setup culls them too)."""
    src = bpy.data.materials["M_Bat"]
    m = bpy.data.materials.get("M_BatWing")
    if m is not None:
        bpy.data.materials.remove(m)
    m = src.copy()
    m.name = "M_BatWing"
    m.use_backface_culling = True
    wing.data.materials.clear()
    wing.data.materials.append(m)
    return m


BACK = "back"          # int face attribute: 1 on the membrane's underside (the copied, flipped faces)


def _one_layer(wing):
    """Drop the underside layer (faces with BACK = 1 and their vertices), back to the painted single sheet."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(wing.data)
    lay = bm.faces.layers.int.get(BACK)
    if lay is not None:
        back = [f for f in bm.faces if f[lay]]
        verts = {v for f in back for v in f.verts}
        bmesh.ops.delete(bm, geom=back, context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[v for v in verts if not v.link_faces], context='VERTS')
        bm.faces.layers.int.remove(lay)
    bm.to_mesh(wing.data)
    bm.free()
    wing.data.update()


def _two_layers(wing):
    """The membrane's underside as faces of its own (2026-10-23, Daniel: "Do these tasks you mentioned"): every face
    copied onto new vertices (same UVs, weights and info) and flipped, tagged BACK. Unity's URP Lit drawn from both
    sides (_Cull 0) lit the underside with the upper side's normals, so from below it read as bright as the top; with
    two layers and back faces culled each side is lit with its own normal, in any shader and render path. +960 tris."""
    import bmesh
    _one_layer(wing)
    bm = bmesh.new()
    bm.from_mesh(wing.data)
    lay = bm.faces.layers.int.new(BACK)
    ret = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))
    new = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.reverse_faces(bm, faces=new)
    for f in new:
        f[lay] = 1
    bm.to_mesh(wing.data)
    bm.free()
    wing.data.update()
    return {"faces": len(wing.data.polygons), "back": len(new)}


def build_model(tex=1024):
    """Body -> rig -> weights -> UVs -> paint -> the wings split off. -> (body, wing, rig, report)"""
    import bat_paint, dragon_body
    setup_scene()
    work_layer(True)
    for n in (BODY, WING_OB):
        beast_scene_obj = bpy.data.objects.get(n)
        if beast_scene_obj is not None:
            bpy.data.objects.remove(beast_scene_obj, do_unlink=True)
    body, acc, hi = BB.build_body()
    report = {"tris": BB.tri_report(body)}
    import zwolf_body
    report["tidy"] = dict(zwolf_body.TIDY)
    rig = beast_rig.build_armature(BB.rest_bones(), name=RIG, coll_name=P + "Rig")
    dragon_body.wing_collections(rig)
    report["bones"] = len(rig.data.bones)
    report["weights"] = BB.skin(body, rig, acc)
    bat_paint.unwrap(body)
    report["textures"], report["coverage"] = bat_paint.build_texture(body, size=tex)
    report["uv_layout"] = RV.uv_png(body, "uv_layout_bat", tex=report["textures"][0])
    report["uv_plain"] = RV.uv_png(body, "uv_layout_bat_plain")
    wing = _split_wing(body)
    report["split"] = {o.name: RV.tris(o) for o in (body, wing)}
    work_layer(False)
    rig.hide_render = True
    return body, wing, rig, report


def _split_wing(body):
    from beast_body import read_info, PART
    part, _ = read_info(body)
    sel = part == PART['membrane']
    beast_rig.split_part(body, sel, WING_OB, [g.name for g in body.vertex_groups])
    wing = bpy.data.objects[WING_OB]
    _two_layers(wing)
    _wing_material(wing)
    return wing


def build():
    body, wing, rig, rep = build_model()
    return rep


def paint():
    """The hide painted again on the built model (same UVs): both objects baked, their texels merged."""
    import bat_paint
    from beast_paint import bake_data, write_texture
    body, wing = bpy.data.objects[BODY], bpy.data.objects[WING_OB]
    work_layer(True)
    D = bake_data(body, size=1024, ao_dist=0.12)
    _one_layer(wing)                                            # the bake sees one sheet (the layers share UVs)
    D2 = bake_data(wing, size=1024, ao_dist=0.12)
    _two_layers(wing)
    for k in ("P", "N", "part", "on_jaw", "aux", "ao", "info"):
        D[k] = np.where(D2['valid'][(...,) + (None,) * (D[k].ndim - 2)], D2[k], D[k])
    D['valid'] = D['valid'] | D2['valid']
    col, smooth = bat_paint.paint(D)
    path = write_texture(D, col, smooth, "T_Bat", body, "M_Bat")
    import deer_paint
    deer_paint.matte(bpy.data.materials["M_Bat"])
    _wing_material(wing)
    work_layer(False)
    RV.uv_png(body, "uv_layout_bat", tex=path)
    return path


def review(views=VIEWS, res=900):
    setup_scene()
    RV.show_wolf(False)
    out = []
    ground = bpy.data.objects.get("Ground")
    for v in views:
        if ground is not None:
            ground.hide_render = v == "Below"                  # the ground disc hides the underside
        out.append(RV.shot(P + "CAM_" + v, f"bat_{v.lower()}", res=res))
    if ground is not None:
        ground.hide_render = False
    return out


def game():
    """The game camera (22 m, 50 deg, fov 30) from four sides, the bat alone and beside the wolf; a 3/4 scale shot."""
    setup_scene()
    RV.add_wolf(P, at=(2.0, 0.0, 0.0))
    RV.show_wolf(False)
    out = [RV.game_sheet([f"{P}CAM_Game{i}" for i in range(4)], "bat_game_sheet")]
    RV.show_wolf(True)
    out.append(RV.game_sheet([f"{P}CAM_GameW{i}" for i in range(4)], "bat_vs_wolf_game", crop=240))
    out.append(RV.shot(P + "CAM_Scale", "bat_vs_wolf_34", res=1000))
    RV.show_wolf(False)
    return out


def hero(res=1000):
    """Two posed shots for the docs: Hover (frame 4) from the front at 3/4, and the Dive's bite from the side."""
    setup_scene()
    A = anim()
    RV.cam(bpy.context.scene, P + "CAM_Hero", (1.55, -2.75, H + 0.75), (0.0, 0.0, H + 0.15), lens=40)
    A.use("Hover")
    bpy.context.scene.frame_set(4)
    out = [RV.shot(P + "CAM_Hero", "bat_hero", res=res)]
    A.use("Dive")
    bpy.context.scene.frame_set(22)
    RV.cam(bpy.context.scene, P + "CAM_HeroDive", (2.6, -2.6, 1.55), (0.0, -0.75, 0.95), lens=40)
    out.append(RV.shot(P + "CAM_HeroDive", "bat_hero_dive", res=res))
    A.clear()
    return out


def anim():
    import bat_anim
    return bat_anim


def clips():
    A = anim()
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def lowest():
    return RV.lowest(anim(), (BODY, WING_OB))


def trace():
    A = anim()
    return {c: RV.motion_trace(A, RIG, c, bones=("Head", "WingF2_3L", "HindToesR")) for c in sorted(A.MOVING)}


def sheets(res=380):
    """EEVEE contact sheets per clip (rows: cameras, columns: SHEET_FRAMES): renders/bat_clip_<Clip>.png."""
    setup_scene()
    A = anim()
    paths = []
    for n in A.CLIPS:
        cams = (P + "CAM_ClipLow", P + "CAM_ClipSide") if n in ("Dive", "Death") else (P + "CAM_Clip34",
                                                                                     P + "CAM_ClipFront")
        paths.append(RV.frames_sheet(A, RIG, n, A.SHEET_FRAMES[n], cams, f"bat_clip_{n}", res=res))
    return paths


def closeups():
    setup_scene()
    A = anim()
    c34, face = P + "CAM_34", P + "CAM_Face"
    return [RV.frames_sheet(A, RIG, "Fly", (0, 4, 8, 12, 16), (c34, P + "CAM_Front"), "bat_frames_Fly"),
            RV.frames_sheet(A, RIG, "Hover", (0, 4, 8, 12), (c34, face), "bat_frames_Hover"),
            RV.frames_sheet(A, RIG, "Dive", (8, 16, 22, 30), (face,), "bat_frames_Dive_face", follow="Head"),
            RV.frames_sheet(A, RIG, "Dive", (8, 16, 22, 30), (P + "CAM_ClipLow",), "bat_frames_Dive"),
            RV.frames_sheet(A, RIG, "Screech", (0, 20, 40), (face, c34), "bat_frames_Screech"),
            RV.frames_sheet(A, RIG, "Death", (10, 21, 30, 59), (P + "CAM_Clip34", P + "CAM_ClipSide"),
                            "bat_frames_Death")]


def export():
    import beast_export
    A = anim()
    A.build_clips()
    A.clear()
    return (beast_export.export_model(RIG, (BODY, WING_OB), NAME, "T_Bat") +
            beast_export.export_clips(A, RIG, NAME))
