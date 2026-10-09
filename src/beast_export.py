"""FBX export for Unity (settings as the goblins' and insectoids': -Z forward / Y up, FBX_SCALE_ALL, deform bones only).

export/Wolf.fbx          rig + WolfBody in the bind pose (Generic rig in Unity, faces +Z)
export/Textures/*.png    T_Wolf (grey), T_Wolf_Black, T_Wolf_White: RGB colour, A smoothness
export/Anims/Wolf@<Clip>.fbx    the skeleton with one baked take each
export/Anims/wolf_clips.json    {clips: [{name, frames, fps, loop, rootMotion, events: [{name, time}]}]} (read by the
                                Unity setup)
"""
import bpy, json, os, shutil
from mathutils import Matrix
from beast_common import ROOT

EXPORT = os.path.join(ROOT, "export")

FBX = dict(apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', use_armature_deform_only=True,
           add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL',
           bake_anim=False, mesh_smooth_type='FACE', use_mesh_modifiers=True, use_custom_props=False,
           path_mode='STRIP', embed_textures=False)


def _select(objs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def _reveal(objs):
    """Unhide the view-layer collections holding objs (a hidden one, e.g. the rig's eye toggled off in the
    outliner, makes its objects unselectable and the export silently skips them). -> the old states to restore."""
    names = {c.name for o in objs for c in o.users_collection}
    old = []

    def walk(lc):
        if lc.collection.name in names:
            old.append((lc, lc.exclude, lc.hide_viewport))
            lc.exclude = False
            lc.hide_viewport = False
        for c in lc.children:
            walk(c)
    walk(bpy.context.view_layer.layer_collection)
    return old


def _restore(old):
    for lc, ex, hv in old:
        lc.exclude, lc.hide_viewport = ex, hv


def export_model(rig_name="WolfRig", meshes=("WolfBody",), name="Wolf", tex_prefix="T_Wolf"):
    os.makedirs(os.path.join(EXPORT, "Textures"), exist_ok=True)
    rig = bpy.data.objects[rig_name]
    objs = [bpy.data.objects[m] for m in meshes]
    shown = _reveal([rig] + objs)
    hidden = rig.hide_get()
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    _select([rig] + objs)
    path = os.path.join(EXPORT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'}, **FBX)
    for o in [rig] + objs:
        o.select_set(False)
    rig.hide_set(hidden)
    _restore(shown)
    written = [path]
    for fn in os.listdir(os.path.join(ROOT, "textures")):
        if fn.startswith(tex_prefix) and fn.endswith(".png"):
            dst = os.path.join(EXPORT, "Textures", fn)
            shutil.copy2(os.path.join(ROOT, "textures", fn), dst)
            written.append(dst)
    return written


def export_clips(anim, rig_name="WolfRig", name="Wolf"):
    """anim: the clip module (wolf_anim): CLIPS, FPS, MOVING, action_name, use, clear."""
    os.makedirs(os.path.join(EXPORT, "Anims"), exist_ok=True)
    rig = bpy.data.objects[rig_name]
    shown = _reveal([rig])
    hidden = rig.hide_get()
    scn = bpy.context.scene
    keep = (scn.frame_start, scn.frame_end, scn.render.fps)
    meta, written = [], []
    try:
        for clip in anim.CLIPS:
            act = bpy.data.actions[anim.action_name(clip)]
            anim.use(clip, rig)
            scn.render.fps = anim.FPS
            _select([rig])
            path = os.path.join(EXPORT, "Anims", f"{name}@{clip}.fbx")
            opts = dict(FBX)
            opts.update(bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
                        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                        bake_anim_simplify_factor=0.0)
            bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE'}, **opts)
            written.append(path)
            meta.append({
                "name": clip, "frames": int(act["frames"]), "fps": anim.FPS, "loop": bool(act["loop"]),
                "rootMotion": clip in anim.MOVING,
                "events": [{"name": k[len("event_"):], "time": float(act[k])} for k in act.keys() if k.startswith("event_")],
            })
    finally:
        scn.frame_start, scn.frame_end, scn.render.fps = keep
        anim.clear(rig)
        rig.select_set(False)
        rig.hide_set(hidden)
        _restore(shown)
    with open(os.path.join(EXPORT, "Anims", f"{name.lower()}_clips.json"), "w", encoding="utf-8") as f:
        json.dump({"clips": meta}, f, indent=1)          # a list, so Unity's JsonUtility can read it
    return written
