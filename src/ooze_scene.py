"""The Ooze scene's cameras, floor and review renders (the lights and the world are the shared ones, beast_scene).

The ooze is see-through, so its review renders and clip sheets use EEVEE (beast_scene.shot is Workbench, which
can't show the shell's alpha). Everything the ooze adds to the file is prefixed OOZ_: the shared Ground, KEY and
FILL and the other creatures' CAM_* objects stay untouched.
"""
import bpy, math, os
from mathutils import Vector
import numpy as np
import beast_scene
from beast_common import ROOT

RENDERS = os.path.join(ROOT, "renders")
P = "OOZ_"


def setup_scene(name="Ooze"):
    scn = bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
    scn.unit_settings.system = 'METRIC'
    scn.view_settings.view_transform = 'Standard'
    scn.render.resolution_x = scn.render.resolution_y = 1000
    scn.render.fps = 30
    _eevee(scn)
    beast_scene.add_lights(scn)                       # shared KEY, FILL and world
    rim = bpy.data.objects.get(P + "RIM")
    if rim is None:
        rim = bpy.data.objects.new(P + "RIM", bpy.data.lights.new(P + "RIM", 'SUN'))
    if rim.name not in scn.collection.objects:
        scn.collection.objects.link(rim)
    rim.data.energy = 2.0
    rim.rotation_euler = tuple(math.radians(a) for a in (70, 0, 170))
    add_cameras(scn)
    add_floor(scn)
    return scn


def _cam(scn, name, loc, target, ortho=None, lens=85):
    return beast_scene._cam(scn, P + name, loc, target, ortho=ortho, lens=lens)


def add_cameras(scn):
    """Framed for a creature ~3.2 m across (pseudopods out) and 1.5 m tall."""
    _cam(scn, "CAM_Front", (0, -10, 0.7), (0, 0, 0.7), ortho=3.6)
    _cam(scn, "CAM_Side", (10, -0.3, 0.7), (0, -0.3, 0.7), ortho=3.6)
    _cam(scn, "CAM_Top", (0, -0.3, 10), (0, -0.2999, 0), ortho=3.6)
    _cam(scn, "CAM_34", (3.3, -4.7, 2.7), (0, -0.25, 0.45), lens=50)
    _cam(scn, "CAM_Rear", (-3.1, 4.3, 2.7), (0, 0.0, 0.45), lens=50)
    _cam(scn, "CAM_Low", (1.3, -4.3, 1.15), (0, -0.4, 0.6), lens=35)        # an adventurer's eye
    _cam(scn, "CAM_Close", (1.1, -2.6, 1.5), (0.2, -0.6, 0.55), lens=50)
    _cam(scn, "CAM_Scale", (0.9, -6.6, 2.0), (0.55, -0.6, 0.65), lens=40)
    _cam(scn, "CAM_Colony", (0, -26, 31), (0, 0, 0.4), lens=300)             # ~40 m at 50 deg pitch
    _cam(scn, "CAM_ClipSide", (12, -0.6, 0.75), (0, -0.6, 0.75), ortho=4.4)
    _cam(scn, "CAM_Clip34", (3.6, -5.4, 3.0), (0, -0.5, 0.45), lens=45)
    scn.camera = bpy.data.objects[P + "CAM_34"]
    vl = scn.view_layers[0]
    for o in scn.collection.objects:                  # out of the way in this scene's viewport (renders still see them)
        if o.type in ('CAMERA', 'LIGHT'):
            o.hide_set(True, view_layer=vl)


def add_floor(scn, size=14.0):
    """A flagstone-grey floor disc (a dungeon), so floor contact and the see-through shell read (not exported)."""
    import bmesh
    name = P + "Floor"
    ob = bpy.data.objects.get(name)
    if ob is None:
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=size / 2)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        m = bpy.data.materials.get("M_DungeonFloor") or bpy.data.materials.new("M_DungeonFloor")
        m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = (0.16, 0.155, 0.15, 1)
        bsdf.inputs['Roughness'].default_value = 0.9
        m.diffuse_color = (0.16, 0.155, 0.15, 1)
        me.materials.append(m)
        ob.hide_select = True
    if ob.name not in scn.collection.objects:
        scn.collection.objects.link(ob)
    return ob


def add_scale_human(scn):
    """A Humans body beside the ooze for scale (Humans/export/Human_Body.fbx, LOD0), in OOZ_Ref; rendered only by
    the scale shot, never exported."""
    from beast_common import get_coll
    ref = get_coll(P + "Ref", scene=scn)
    if bpy.data.objects.get(P + "RefRig") is not None:
        return ref
    path = os.path.join(os.path.dirname(ROOT), "Humans", "export", "Human_Body.fbx")
    if not os.path.exists(path):
        return ref
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    for o in [o for o in bpy.data.objects if o not in before]:
        if o.type == 'MESH' and o.name.split(".")[0].endswith(("_L1", "_L2")):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        for c in list(o.users_collection):
            c.objects.unlink(o)
        ref.objects.link(o)
        o.name = P + "Ref" + ("Rig" if o.type == 'ARMATURE' else o.name.split(".")[0])
        o.hide_render = True
    rig = bpy.data.objects[P + "RefRig"]
    rig.location = (1.75, -1.55, 0)
    rig.rotation_euler = (0, 0, math.radians(49))       # facing the ooze
    rig.hide_set(True)
    return ref


def _eevee(scn, samples=48):
    try:
        scn.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scn.render.engine = 'BLENDER_EEVEE'
    ee = scn.eevee
    ee.taa_render_samples = samples
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("use_gtao", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)


def shot(cam="CAM_34", name=None, res=1000, scene=None, frame=None, samples=48):
    """EEVEE render through OOZ_<cam> into renders/<name>.png."""
    scn = scene or bpy.context.scene
    prev_cam = scn.camera
    scn.camera = bpy.data.objects[P + cam]
    if frame is not None:
        scn.frame_set(frame)
    _eevee(scn, samples)
    scn.render.resolution_x = scn.render.resolution_y = res
    scn.render.film_transparent = False
    os.makedirs(RENDERS, exist_ok=True)
    path = os.path.join(RENDERS, (name or "ooze_" + cam[4:].lower()) + ".png")
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scn.name)
    scn.camera = prev_cam
    return path


def render_sheet(name, frames, cams=("CAM_ClipSide", "CAM_Clip34"), rig_name="OozeRig", res=320, samples=16,
                 out=None):
    """Clip frames (rows = cameras, columns = frames) in one PNG in renders/. The skeleton plays in place (only
    Motion travels), so the cameras stay put."""
    scn = bpy.context.scene
    rig = bpy.data.objects[rig_name]
    tmp = os.path.join(RENDERS, "_tile.png")
    rows = []
    for cam_name in cams:
        cam = bpy.data.objects[P + cam_name]
        home = cam.location.copy()
        row = []
        for f in frames:
            scn.frame_set(f)
            shot(cam_name, "_tile", res=res, samples=samples)
            img = bpy.data.images.load(tmp, check_existing=False)
            row.append(np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4))
            bpy.data.images.remove(img)
        cam.location = home
        rows.append(np.concatenate(row, axis=1))
    sheet = np.concatenate(rows[::-1], axis=0)
    h, w = sheet.shape[:2]
    img = bpy.data.images.new("_sheet", w, h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    path = os.path.join(RENDERS, (out or ("ooze_clip_" + name)) + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def show_scene(scn):
    bpy.context.window_manager.windows[0].scene = scn


def frame_viewports(shading='MATERIAL', distance=5.5):
    """Every 3D viewport at the ooze from the 3/4 view, in material preview."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = shading
                    r3 = sp.region_3d
                    r3.view_location = Vector((0, -0.25, 0.5))
                    r3.view_distance = distance
                    r3.view_rotation = Vector((3.3, -4.7, 2.2)).normalized().to_track_quat('Z', 'Y')
                    r3.view_perspective = 'PERSP'
