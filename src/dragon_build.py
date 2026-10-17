"""Rebuild the dragon (2026-10-17). Stage 1, the blockout: skeleton + rough volumes + wing membranes, posed in the
test poses (dragon_pose). Stage 2, the face (dragon_head). Stage 3, the real body (dragon_skin): build_body().
Its own file, blender/dragon.blend (scene Dragon); run with that scene on screen (dragon_build.show() puts it
there)."""
import bpy, importlib, os
import numpy as np
import beast_common, beast_scene, beast_rig, dragon_body, dragon_pose, dragon_head, dragon_skin, dragon_paint

RIG = dragon_body.RIG
BLEND = os.path.join(beast_common.ROOT, "blender", "dragon.blend")


def reload_all():
    import beast_paint
    for m in (beast_common, beast_scene, beast_rig, beast_paint, dragon_head, dragon_body, dragon_pose, dragon_skin,
              dragon_paint):
        importlib.reload(m)


def setup_scene():
    """The Dragon scene: shared lights, a 36 m ground (the beasts' default disc is 12 m), cameras framed for a
    12 m dragon with a 16 m wingspan (DRG_CAM_*), and a 1.8 m figure in front of the snout for scale."""
    scn = bpy.data.scenes.get("Dragon") or bpy.data.scenes.new("Dragon")
    beast_scene.add_ground(scn, size=36.0)
    scn = beast_scene.setup_scene("Dragon", prefix="DRG_")
    if scn.render.engine == 'BLENDER_WORKBENCH':
        for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scn.render.engine = eng
                break
            except TypeError:
                pass
    c = lambda n, loc, tgt, **kw: beast_scene._cam(scn, "DRG_" + n, loc, tgt, **kw)
    c("CAM_Front", (0, -60, 2.8), (0, 0, 2.8), ortho=17.5)
    c("CAM_Side", (60, 0.5, 3.1), (0, 0.5, 3.1), ortho=15.5)
    c("CAM_Top", (0, 1.1, 60), (0, 1.1001, 0), ortho=17.5)
    c("CAM_34", (13.5, -15.5, 9.5), (0, 0.6, 2.4), lens=40)
    c("CAM_Rear", (-11, 15, 9), (0, 0.6, 2.4), lens=40)
    c("CAM_Face", (3.0, -8.6, 5.7), (0, -4.1, 4.8), lens=50)
    c("CAM_HeadSide", (30, -4.0, 4.9), (0, -4.0, 4.9), ortho=3.4)
    c("CAM_HeadFront", (0, -30, 4.75), (0, 0, 4.75), ortho=2.6)
    c("CAM_Fly", (13.5, -15.5, 13.0), (0, 0.6, 5.9), lens=40)
    c("CAM_Colony", (0, -26, 31), (0, 0.6, 2.0), lens=50)
    scn.camera = bpy.data.objects["DRG_CAM_34"]
    for o in ("KEY", "FILL"):
        ob = bpy.data.objects.get(o)
        if ob is not None and ob.name not in scn.collection.objects:
            scn.collection.objects.link(ob)
    dragon_body.scale_man(beast_common.get_coll("DRG_Scale", scene=scn))
    return scn


def show():
    """Put the Dragon scene on screen (created if missing), viewports in material preview from the 3/4 view."""
    scn = bpy.data.scenes.get("Dragon") or setup_scene()
    beast_scene.show_scene(scn)
    beast_scene.frame_viewports(shading='MATERIAL', lift=2.2, distance=24.0)


def build_blockout(frill_fused=None):
    """Skeleton -> blockout meshes, skinned and bound. -> (rig, objects, report)"""
    assert bpy.context.scene.name == "Dragon", "put the Dragon scene on screen first: dragon_build.show()"
    reload_all()
    setup_scene()
    rig = beast_rig.build_armature(dragon_body.rest_bones(), name=RIG, coll_name="DRG_Rig")
    dragon_body.wing_collections(rig)
    objs, rep = dragon_body.build_blockout(rig, frill_fused=frill_fused)
    rep["bones"] = len(rig.data.bones)
    rig.hide_render = True
    return rig, objs, rep


def build_body():
    """Skeleton -> the real body (dragon_skin): skin, shells, membranes, weighted and bound; the blockout's
    collection is excluded from the view layer. -> (rig, objects, report)"""
    assert bpy.context.scene.name == "Dragon", "put the Dragon scene on screen first: dragon_build.show()"
    reload_all()
    setup_scene()
    rig = beast_rig.build_armature(dragon_body.rest_bones(), name=RIG, coll_name="DRG_Rig")
    dragon_body.wing_collections(rig)
    objs, rep = dragon_skin.build(rig)
    rep["bones"] = len(rig.data.bones)
    rig.hide_render = True
    return rig, objs, rep


def paint(**kw):
    """UVs, bakes, the colour presets and normal maps (dragon_paint) on the built body. -> report"""
    reload_all()
    return dragon_paint.build(**kw)


def pose(name):
    return dragon_pose.pose(bpy.data.objects[RIG], name)


def pose_sheet(poses=dragon_pose.POSES, cams=("DRG_CAM_Side", "DRG_CAM_34", "DRG_CAM_Front"), res=520,
               out="dragon_blockout_poses", engine='BLENDER_EEVEE_NEXT'):
    """One PNG in renders/: a column per pose, a row per camera. Flying poses swap CAM_34 for CAM_Fly and aim the
    side and front cameras higher. Leaves the rig in the bind pose."""
    scn = bpy.context.scene
    tiles = []
    tmp = os.path.join(beast_scene.RENDERS, "_tile.png")
    lifted = {"downstroke": 3.5}
    for cam in cams:
        row = []
        for p in poses:
            pose(p)
            lift = lifted.get(p, 0.0)
            name = "DRG_CAM_Fly" if (cam == "DRG_CAM_34" and lift) else cam
            ob = bpy.data.objects[name]
            home = ob.location.copy()
            if name != "DRG_CAM_Fly" and cam != "DRG_CAM_34":
                ob.location.z += lift
            beast_scene.shot(name, "_tile", engine=engine, res=res, scene=scn)
            ob.location = home
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        tiles.append(np.concatenate(row, axis=1))
    pose("spread")
    sheet = np.concatenate(tiles[::-1], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new("_sheet", w, h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    path = os.path.join(beast_scene.RENDERS, out + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def face_sheet(res=640, out="dragon_face_sheet", engine='BLENDER_EEVEE_NEXT'):
    """The head close up, mouth shut (top row) and open (bottom row): side, 3/4 and front. Leaves the bind pose."""
    scn = bpy.context.scene
    beast_scene._cam(scn, "DRG_CAM_HeadFront", (0, -30, 4.75), (0, 0, 4.75), ortho=2.6)
    rig = bpy.data.objects[RIG]
    tiles = []
    tmp = os.path.join(beast_scene.RENDERS, "_tile.png")
    for jaw in (0, -34):
        dragon_pose.solve(rig, rot={"Jaw": [('X', jaw)]})
        row = []
        for cam in ("DRG_CAM_HeadSide", "DRG_CAM_Face", "DRG_CAM_HeadFront"):
            beast_scene.shot(cam, "_tile", engine=engine, res=res, scene=scn)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        tiles.append(np.concatenate(row, axis=1))
    dragon_pose.solve(rig)
    sheet = np.concatenate(tiles[::-1], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new("_sheet", w, h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    path = os.path.join(beast_scene.RENDERS, out + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def frill_compare(res=640, out="dragon_frill_compare", engine='BLENDER_EEVEE_NEXT'):
    """The head shut, side / 3/4 / front: the frill's ribs melted into the head (top row) or separate (bottom row).
    Leaves the separate version built."""
    scn = bpy.context.scene
    tiles = []
    tmp = os.path.join(beast_scene.RENDERS, "_tile.png")
    for fused in (True, False):
        build_blockout(frill_fused=fused)
        row = []
        for cam in ("DRG_CAM_HeadSide", "DRG_CAM_Face", "DRG_CAM_HeadFront"):
            beast_scene.shot(cam, "_tile", engine=engine, res=res, scene=scn)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        tiles.append(np.concatenate(row, axis=1))
    sheet = np.concatenate(tiles[::-1], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new("_sheet", w, h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    path = os.path.join(beast_scene.RENDERS, out + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def save():
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    return BLEND
