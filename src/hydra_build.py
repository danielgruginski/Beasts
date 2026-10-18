"""Hydra build steps (run inside Blender, Beasts/src on sys.path). Own file: blender/hydra.blend, scene Hydra.

    import hydra_build as H
    H.new_file()                 # a fresh blend with the Hydra scene (save the open file first)
    H.build_blockout(heads=3)    # skeleton -> blockout meshes, skinned and bound
    H.heads_sheet()              # renders/hydra_heads.png: three heads (top row) against two
    H.save()
"""
import bpy, importlib, os
import numpy as np
import beast_common, beast_scene, beast_rig, dragon_body, dragon_head, dragon_skin, hydra_head, hydra_body, hydra_skin

BLEND = os.path.join(beast_common.ROOT, "blender", "hydra.blend")
RIG = hydra_body.RIG


def reload_all():
    for m in (beast_common, beast_scene, beast_rig, dragon_body, dragon_head, dragon_skin, hydra_head, hydra_body,
              hydra_skin):
        importlib.reload(m)


def new_file():
    """A fresh blend (empty) whose one scene becomes Hydra; the open file is not saved. (Removing the empty file's
    own scene instead crashed Blender 4.4: the window still referenced it.)"""
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.data.scenes[0].name = "Hydra"
    scn = setup_scene()
    beast_scene.show_scene(scn)
    return scn


def setup_scene():
    """The Hydra scene: shared lights, a 36 m ground, cameras framed for an 11 m hydra (HYD_CAM_*), a 1.8 m figure
    in front of the heads for scale."""
    scn = bpy.data.scenes.get("Hydra") or bpy.data.scenes.new("Hydra")
    beast_scene.add_ground(scn, size=36.0)
    scn = beast_scene.setup_scene("Hydra", prefix="HYD_")
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scn.render.engine = eng
            break
        except TypeError:
            pass
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "HYD_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -60, 2.2), (0, 0, 2.2), ortho=9.0)
    c("CAM_Side", (60, 1.2, 2.2), (0, 1.2, 2.2), ortho=13.0)
    c("CAM_Top", (0, 1.2, 60), (0, 1.2001, 0), ortho=13.0)
    c("CAM_34", (11.5, -12.5, 7.5), (0, 0.4, 1.6), lens=40)
    c("CAM_Rear", (-9, 13, 7.5), (0, 0.4, 1.6), lens=40)
    c("CAM_Face", (3.2, -8.2, 4.4), (0, -3.0, 3.3), lens=45)
    c("CAM_Colony", (0, -26, 31), (0, 0.6, 1.2), lens=50)
    scn.camera = bpy.data.objects["HYD_CAM_34"]
    hydra_body.scale_man(beast_common.get_coll("HYD_Scale", scene=scn))
    return scn


def show():
    scn = bpy.data.scenes.get("Hydra") or setup_scene()
    beast_scene.show_scene(scn)
    beast_scene.frame_viewports(shading='MATERIAL', lift=1.6, distance=20.0)


def build_blockout(heads=None, melted=True):
    """Skeleton -> blockout meshes (the melted heads unless melted=False), skinned and bound. -> (rig, objects,
    report)"""
    assert bpy.context.scene.name == "Hydra", "put the Hydra scene on screen first: hydra_build.show()"
    reload_all()
    setup_scene()
    heads = heads or hydra_body.HEADS
    rig = beast_rig.build_armature(hydra_body.rest_bones(heads), name=RIG, coll_name="HYD_Rig")
    objs, rep = hydra_body.build_blockout(rig, heads, melted)
    rep["bones"] = len(rig.data.bones)
    rig.hide_render = True
    return rig, objs, rep


def build_body():
    """Skeleton -> the real body (hydra_skin): one skin with the three heads, shells, fins, weighted and bound; the
    blockout's collection is excluded. -> (rig, objects, report)"""
    assert bpy.context.scene.name == "Hydra", "put the Hydra scene on screen first: hydra_build.show()"
    reload_all()
    setup_scene()
    rig = beast_rig.build_armature(hydra_body.rest_bones(3), name=RIG, coll_name="HYD_Rig")
    objs, rep = hydra_skin.build(rig)
    rep["bones"] = len(rig.data.bones)
    rig.hide_render = True
    return rig, objs, rep


def _sheet(rows, out, res):
    sheet = np.concatenate([np.concatenate(r, axis=1) for r in rows][::-1], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new("_sheet", w, h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    path = os.path.join(beast_scene.RENDERS, out + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def heads_sheet(cams=("HYD_CAM_34", "HYD_CAM_Side", "HYD_CAM_Front", "HYD_CAM_Face"), res=480, out="hydra_heads",
                engine='BLENDER_EEVEE_NEXT'):
    """One PNG: a row per head count (three on top, then two), a column per camera. Leaves the three-headed
    blockout built."""
    scn = bpy.context.scene
    tmp = os.path.join(beast_scene.RENDERS, "_tile.png")
    rows = []
    for heads in (3, 2):
        build_blockout(heads, melted=False)
        row = []
        for cam in cams:
            beast_scene.shot(cam, "_tile", engine=engine, res=res, scene=scn)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        rows.append(row)
    build_blockout(3, melted=False)
    return _sheet(rows, out, res)


def head_sheet(res=560, out="hydra_head_sheet", engine='BLENDER_EEVEE_NEXT'):
    """The left head close (the middle one is hidden from the side by its neighbours): side (from outside), front,
    3/4 and from below, mouth shut (top row) and open (bottom row)."""
    import hydra_body as HB
    from mathutils import Vector
    scn = bpy.context.scene
    rig = bpy.data.objects[RIG]
    M = HB.head_matrix("L")
    c = Vector(HB.hx(M, (0, -0.50, 0.0)))
    fwd = (M.to_3x3() @ Vector((0, -1, 0))).normalized()
    side = (M.to_3x3() @ Vector((1, 0, 0))).normalized()
    views = {"side": c + side * 3.2, "front": c + fwd * 3.2 + Vector((0, 0, 0.3)),
             "34": c + (fwd + side * 0.9).normalized() * 3.0 + Vector((0, 0, 0.6)),
             "below": c + (fwd * 0.6 + side * 0.5).normalized() * 2.6 + Vector((0, 0, -1.2))}
    tmp = os.path.join(beast_scene.RENDERS, "_tile.png")
    rows = []
    for jaw in (0.0, 30.0):
        pb = rig.pose.bones["JawL"]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (-jaw * 3.14159 / 180, 0, 0)
        bpy.context.view_layer.update()
        row = []
        for name, loc in views.items():
            cam = beast_scene._cam(scn, "HYD_CAM_HeadTmp", tuple(loc), tuple(c), lens=50)
            beast_scene.shot("HYD_CAM_HeadTmp", "_tile", engine=engine, res=res, scene=scn)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        rows.append(row)
    pb.rotation_euler = (0, 0, 0)
    return _sheet(rows, out, res)


def save():
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    return BLEND


def export():
    """Hydra.fbx (HydraBody + HydraFins on HydraRig), the clips and the T_Hydra* textures into export/."""
    import beast_export, hydra_anim
    build_clips()
    return (beast_export.export_model(RIG, ("HydraBody", "HydraFins"), "Hydra", "T_Hydra") +
            beast_export.export_clips(hydra_anim, RIG, "Hydra"))


# ----------------------------------------------------------------------------------------- clips
CLIP_CAMS = {"side": ("HYD_CAM_ClipSide", (19, 1.0, 3.4), (0, 1.0, 1.7), dict(lens=46)),
             "34": ("HYD_CAM_Clip34", (10.5, -9.0, 4.8), (0, 0.6, 1.5), dict(lens=36)),
             "front": ("HYD_CAM_ClipFront", (2.5, -15, 2.8), (0, -1.0, 1.8), dict(lens=40))}


def clip_cameras():
    scn = bpy.data.scenes["Hydra"]
    for name, loc, tgt, kw in CLIP_CAMS.values():
        beast_scene._cam(scn, name, loc, tgt, **kw)


def build_clips(names=None):
    """hydra_anim's clips onto HydraRig. -> {clip: frames}"""
    import beast_anim, hydra_anim
    importlib.reload(beast_anim)
    importlib.reload(hydra_anim)
    out = {n: int(a["frames"]) for n, a in hydra_anim.build_clips(names).items()}
    hydra_anim.clear()
    return out


def clip_frames(name, cam="34", res=540, step=2, travel=False, follow_z=0.6, lift=0.0, end_home=False):
    """Render a clip's frames into renders/clip_<Hydra name>_<cam>/ (dragon_build.clip_frames); `py
    tools/frames_to_gif.py` turns them into a GIF. -> folder"""
    from mathutils import Vector
    import hydra_anim
    clip_cameras()
    scn = bpy.data.scenes["Hydra"]
    hydra_anim.use(name)
    act = bpy.data.actions[hydra_anim.SPEC.action_name(name)]
    N = int(act["frames"])
    folder = os.path.join(beast_scene.RENDERS, f"clip_hydra_{name}_{cam}")
    os.makedirs(folder, exist_ok=True)
    for fn in os.listdir(folder):
        os.remove(os.path.join(folder, fn))
    old = scn.camera, scn.render.resolution_x, scn.render.resolution_y, scn.render.filepath
    scn.camera = bpy.data.objects[CLIP_CAMS[cam][0]]
    scn.render.resolution_x = scn.render.resolution_y = res
    rig = bpy.data.objects[RIG]
    rig_home, cam_home = rig.location.copy(), scn.camera.location.copy()
    end = Vector()
    if end_home:
        scn.frame_set(N)
        end = rig.pose.bones["Motion"].head.copy()
    for f in range(0, N + (0 if act["loop"] else 1), step):
        scn.frame_set(f)
        if travel or lift:
            mo = rig.pose.bones["Motion"].head.copy() - end if travel else Vector()
            mo.z += lift
            rig.location = rig_home + mo
            scn.camera.location = cam_home + Vector((0, mo.y, follow_z * mo.z))
            bpy.context.view_layer.update()
        scn.render.filepath = os.path.join(folder, f"{f:04d}.png")
        bpy.ops.render.render(write_still=True, scene=scn.name)
    rig.location, scn.camera.location = rig_home, cam_home
    scn.camera, scn.render.resolution_x, scn.render.resolution_y, scn.render.filepath = old
    hydra_anim.clear()
    return folder
