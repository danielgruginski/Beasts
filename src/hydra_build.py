"""Hydra build steps (run inside Blender, Beasts/src on sys.path). Own file: blender/hydra.blend, scene Hydra.

    import hydra_build as H
    H.new_file()                 # a fresh blend with the Hydra scene (save the open file first)
    H.build_blockout(heads=3)    # skeleton -> blockout meshes, skinned and bound
    H.heads_sheet()              # renders/hydra_heads.png: three heads (top row) against two
    H.save()
"""
import bpy, importlib, os
import numpy as np
import beast_common, beast_scene, beast_rig, dragon_body, hydra_body

BLEND = os.path.join(beast_common.ROOT, "blender", "hydra.blend")
RIG = hydra_body.RIG


def reload_all():
    for m in (beast_common, beast_scene, beast_rig, dragon_body, hydra_body):
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


def build_blockout(heads=None):
    """Skeleton -> blockout meshes, skinned and bound. -> (rig, objects, report)"""
    assert bpy.context.scene.name == "Hydra", "put the Hydra scene on screen first: hydra_build.show()"
    reload_all()
    setup_scene()
    heads = heads or hydra_body.HEADS
    rig = beast_rig.build_armature(hydra_body.rest_bones(heads), name=RIG, coll_name="HYD_Rig")
    objs, rep = hydra_body.build_blockout(rig, heads)
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
        build_blockout(heads)
        row = []
        for cam in cams:
            beast_scene.shot(cam, "_tile", engine=engine, res=res, scene=scn)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        rows.append(row)
    build_blockout(3)
    return _sheet(rows, out, res)


def save():
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    return BLEND
