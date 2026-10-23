"""Build the zombie wolf (2026-10-23): body -> rig -> weights -> UVs -> painted coats -> clips, review renders,
export. Its own file, blender/zombie_wolf.blend (scene ZombieWolf, cameras ZWF_CAM_*), built in a headless Blender:

    blender.exe -b --factory-startup --python tools/zwolf_run.py -- build review clips lowest export
    blender.exe -b --factory-startup blender/zombie_wolf.blend --python tools/zwolf_run.py -- paint review closeups

The rig is the wolf's skeleton and is named WolfRig (zwolf_anim): the wolf's clips and these share their curve paths.
"""
import bpy, importlib, math, os
import numpy as np
from mathutils import Vector
from beast_common import ROOT
import beast_scene, beast_rig

NAME = "ZombieWolf"
RIG = "WolfRig"
BODY = "ZombieWolfBody"
P = "ZWF_"
VIEWS = ("Front", "Side", "SideR", "Top", "34", "34R", "Face", "FaceR", "HeadSide", "HeadSideR", "HeadFront",
         "Rear", "Wound", "Above", "Colony")
GAME = dict(dist=22.0, pitch=50.0, fov=30.0, res=620)     # the game camera: the whole wolf ~80-100 px


def blend_path():
    return os.path.join(ROOT, "blender", "zombie_wolf.blend")


def reload_all():
    import beast_common, beast_body, beast_paint, beast_anim, beast_export, wolf_body, wolf_rig, wolf_paint, wolf_anim
    mods = [beast_common, beast_scene, beast_rig, beast_body, beast_paint, beast_anim, beast_export, wolf_body,
            wolf_rig, wolf_paint, wolf_anim]
    for name in ("zwolf_body", "zwolf_rig", "zwolf_paint", "zwolf_anim"):
        mods.append(importlib.import_module(name))
    for m in mods:
        importlib.reload(m)


def _eevee(scn):
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scn.render.engine = eng
            return
        except TypeError:
            pass


def _game_cam(scn, name, az, target=(0, -0.15, 0.40)):
    """The game's camera: GAME['dist'] away at GAME['pitch'], vertical fov GAME['fov'], from azimuth az (deg; 0 = in
    front of the wolf, 90 = its left side)."""
    a, p = math.radians(az), math.radians(GAME['pitch'])
    d = GAME['dist']
    t = Vector(target)
    loc = t + Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * d
    cam = beast_scene._cam(scn, name, tuple(loc), tuple(t))
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.lens = cam.data.sensor_height / 2 / math.tan(math.radians(GAME['fov']) / 2)
    return cam


def setup_scene():
    """The file's one scene renamed ZombieWolf: the shared lights and ground, the wolf-sized cameras (ZWF_CAM_*), plus
    right-side views (the torn flank and ear are on the right), a wound close-up and the game camera."""
    scn = bpy.context.scene
    scn.name = NAME
    for n in ("Cube", "Light", "Camera"):                       # the factory startup's objects
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
    beast_scene.setup_scene(NAME, prefix=P)
    _eevee(scn)
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, P + n, loc, tgt, **kw)
    c("CAM_SideR", (-8, -0.2, 0.55), (0, -0.2, 0.55), ortho=2.0)
    c("CAM_34R", (-1.75, -2.45, 1.25), (0, -0.22, 0.5), lens=50)
    c("CAM_FaceR", (-0.55, -1.75, 0.98), (0, -0.82, 0.84), lens=70)
    c("CAM_HeadSideR", (-3, -0.80, 0.84), (0, -0.80, 0.84), ortho=0.42)
    c("CAM_Wound", (-0.95, -0.62, 0.86), (-0.08, -0.12, 0.57), lens=60)
    c("CAM_Above", (1.45, -2.05, 2.75), (0, -0.20, 0.42), lens=50)
    c("CAM_ClipSide", (-12, -0.1, 0.5), (0, -0.1, 0.5), ortho=2.4)
    c("CAM_Clip34R", (-2.3, -3.0, 1.9), (0, -0.1, 0.42), lens=45)
    c("CAM_ClipWound", (-1.25, -0.85, 1.25), (-0.05, -0.12, 0.50), lens=50)
    for i, az in enumerate((90, -90, 30, 210)):
        _game_cam(scn, f"{P}CAM_Game{i}", az)
    scn.camera = bpy.data.objects[P + "CAM_34"]
    return scn


def work_layer(on):
    lc = bpy.context.view_layer.layer_collection.children.get(P + "Work")
    if lc is not None:
        lc.exclude = not on


def build_model(tex=1024, body_tris=3900, paint=True, rig=True):
    """Body -> rig -> weights -> UVs -> painted coats. -> (body, rig, report)"""
    import zwolf_body as Z
    setup_scene()
    work_layer(True)
    body, hi = Z.build_body(target_tris=body_tris)
    report = {"tris": Z.tri_report(body), "tidy": dict(Z.TIDY)}
    arm = None
    if rig:
        import zwolf_rig
        arm = beast_rig.build_armature(Z.rest_bones(), name=RIG, coll_name=P + "Rig")
        report["weights"] = zwolf_rig.skin(body, arm)
    if paint:
        import zwolf_paint, farm_paint
        zwolf_paint.unwrap(body)
        report["textures"], report["coverage"] = zwolf_paint.build_texture(body, size=tex)
        report["uv_layout"] = farm_paint.uv_png(body, os.path.join(ROOT, "renders", "uv_layout_zwolf.png"),
                                                tex=report["textures"][0])
        report["uv_plain"] = farm_paint.uv_png(body, os.path.join(ROOT, "renders", "uv_layout_zwolf_plain.png"))
    work_layer(False)
    if arm is not None:
        arm.hide_render = True
    return body, arm, report


def repaint(tex=1024):
    """The coats painted again on the built model (same UVs): for paint-only changes."""
    import zwolf_paint, farm_paint
    body = bpy.data.objects[BODY]
    work_layer(True)
    paths, cov = zwolf_paint.build_texture(body, size=tex)
    work_layer(False)
    farm_paint.uv_png(body, os.path.join(ROOT, "renders", "uv_layout_zwolf.png"), tex=paths[0])
    return paths


def review(prefix="zwolf", views=VIEWS, res=900):
    """EEVEE renders of the bind pose into renders/ (zwolf_34.png ...)."""
    setup_scene()
    eng = bpy.context.scene.render.engine
    return [beast_scene.shot(P + "CAM_" + v, f"{prefix}_{v.lower()}", engine=eng, res=res) for v in views]


def review_test_pose(res=900):
    import zwolf_rig
    rig = bpy.data.objects[RIG]
    zwolf_rig.test_pose(rig)
    eng = bpy.context.scene.render.engine
    paths = [beast_scene.shot(P + "CAM_34", "zwolf_testpose_34", engine=eng, res=res),
             beast_scene.shot(P + "CAM_34R", "zwolf_testpose_34r", engine=eng, res=res),
             beast_scene.shot(P + "CAM_FaceR", "zwolf_testpose_face", engine=eng, res=res)]
    zwolf_rig.reset_pose(rig)
    return paths


# ----------------------------------------------------------------------------------------- sheets of renders
def _load(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a


def _save(a, name):
    h, w = a.shape[:2]
    img = bpy.data.images.new("_zw_sheet", w, h, alpha=True)
    img.pixels.foreach_set(a.ravel())
    path = os.path.join(ROOT, "renders", name + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def game_shots(prefix="zwolf"):
    """The game camera from four sides (renders/<prefix>_game<i>.png, at the game's pixel size) and one sheet of their
    middles blown up x3 (nearest), so the pixels the player gets can be judged: renders/<prefix>_game_sheet.png."""
    scn = bpy.context.scene
    eng = scn.render.engine
    res, crop, k = GAME['res'], 200, 3
    tiles = []
    for i in range(4):
        p = beast_scene.shot(f"{P}CAM_Game{i}", f"{prefix}_game{i}", engine=eng, res=res)
        a = _load(p)
        c0 = (res - crop) // 2
        a = a[c0:c0 + crop, c0:c0 + crop]
        tiles.append(np.repeat(np.repeat(a, k, 0), k, 1))
    sheet = np.concatenate([np.concatenate(tiles[2:], 1), np.concatenate(tiles[:2], 1)], 0)
    return _save(sheet, f"{prefix}_game_sheet")


def frames_sheet(clip, frames, cams, out, res=420, engine=None, follow=True):
    """Clip frames rendered from each camera (rows = cameras, columns = frames; EEVEE by default), the cameras moving
    with the Root bone. -> renders/<out>.png"""
    import zwolf_anim as A
    scn = bpy.context.scene
    eng = engine or scn.render.engine
    rig = bpy.data.objects[RIG]
    A.use(clip)
    rows = []
    for cam_name in cams:
        cam = bpy.data.objects[cam_name]
        home = cam.location.copy()
        row = []
        for f in frames:
            scn.frame_set(f)
            if follow:
                off = rig.matrix_world @ rig.pose.bones["Root"].head
                cam.location = home + Vector((off.x, off.y, 0))
            row.append(_load(beast_scene.shot(cam_name, "_zw_tile", engine=eng, res=res)))
        cam.location = home
        rows.append(np.concatenate(row, axis=1))
    A.clear()
    return _save(np.concatenate(rows[::-1], axis=0), out)


def clip_sheets(names=None, res=360):
    """Workbench contact sheets of every clip's key frames from the right side and 3/4: renders/zwolf_clip_<Clip>.png."""
    import zwolf_anim as A
    paths = []
    for n in (names or A.CLIPS):
        A.use(n)
        paths.append(beast_scene.render_sheet(n, A.SHEET_FRAMES[n], cams=(P + "CAM_ClipSide", P + "CAM_Clip34R"),
                                              rig_name=RIG, res=res, out=f"zwolf_clip_{n}"))
    A.clear()
    return paths


def closeups():
    """EEVEE frames of the clips that move the wound, ear and face most, for tearing: walk, run, bite, lunge, death."""
    cams = (P + "CAM_ClipWound", P + "CAM_FaceR")
    return [frames_sheet("Walk", (0, 6, 12, 18), cams, "zwolf_frames_Walk"),
            frames_sheet("Run", (0, 3, 6, 9), cams, "zwolf_frames_Run"),
            frames_sheet("Bite", (9, 12, 16, 22), cams, "zwolf_frames_Bite"),
            frames_sheet("Lunge", (10, 19, 24, 30), cams, "zwolf_frames_Lunge"),
            frames_sheet("Death", (20, 30, 44, 66), (P + "CAM_Above", P + "CAM_34R"), "zwolf_frames_Death")]


def coat_shots(cams=("34", "34R"), res=600):
    """The bind pose once per coat (the material's image swapped): renders/zwolf_coats.png (rows = coats)."""
    m = bpy.data.materials["M_ZombieWolf"]
    tex = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None)
    first = tex.image
    eng = bpy.context.scene.render.engine
    rows = []
    for name in ("T_ZombieWolf", "T_ZombieWolf_Dark", "T_ZombieWolf_Pale"):
        tex.image = bpy.data.images.load(os.path.join(ROOT, "textures", name + ".png"), check_existing=True)
        tex.image.reload()
        rows.append(np.concatenate([_load(beast_scene.shot(P + "CAM_" + c, "_zw_tile", engine=eng, res=res))
                                    for c in cams], 1))
    tex.image = first
    return _save(np.concatenate(rows[::-1], 0), "zwolf_coats")


# ----------------------------------------------------------------------------------------- clips and export
def build_clips():
    import zwolf_anim as A
    out = {n: int(a["frames"]) for n, a in A.build_clips().items()}
    A.clear()
    return out


def lowest(names=None, step=2):
    """The lowest vertex per clip (evaluated mesh, world z): nothing should go under -0.03. Also the lowest point of
    the trunk alone (y between the legs) at the clip's last frame, to see whether a dead, thinner trunk floats."""
    import zwolf_anim as A
    body = bpy.data.objects[BODY]
    scn = bpy.context.scene
    out = {}
    for n in (names or A.CLIPS):
        A.use(n)
        act = bpy.data.actions[A.action_name(n)]
        N = int(act["frames"])
        lo = 9.0
        for f in list(range(0, N + 1, step)) + [N]:
            scn.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            me = body.evaluated_get(dg).to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            lo = min(lo, float(co[:, 2].min()))
            if f == N:
                rest = np.array([v.co[:] for v in body.data.vertices])
                trunk = (rest[:, 2] > 0.45) & (rest[:, 1] > -0.30) & (rest[:, 1] < 0.30)
                trunk_lo = float(co[trunk, 2].min())
            body.evaluated_get(dg).to_mesh_clear()
        out[n] = (round(lo, 3), round(trunk_lo, 3))
    A.clear()
    return out


def export():
    """export/ZombieWolf.fbx (WolfRig + ZombieWolfBody), Textures/T_ZombieWolf*.png, Anims/ZombieWolf@<clip>.fbx +
    zombiewolf_clips.json."""
    import beast_export, zwolf_anim
    zwolf_anim.build_clips()
    zwolf_anim.clear()
    return (beast_export.export_model(RIG, (BODY,), NAME, "T_ZombieWolf") +
            beast_export.export_clips(zwolf_anim, RIG, NAME))
