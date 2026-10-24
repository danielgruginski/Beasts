"""glTF export for Godot (2026-10-24: the creatures pack for Godot; the FBX path for Unity is beast_export):

export/godot/<Name>/<Name>.glb          the rig and its meshes in the bind pose, every clip an animation named after the
                                        clip (each clip's action on an NLA track of its own while exporting:
                                        export_animation_mode NLA_TRACKS, sampled every frame)
export/godot/<Name>/<name>_clips.json   per clip: frames, fps, loop, root motion, events (name, time in seconds), as the
                                        FBX path's
export/godot/<Name>/T_*.png             the creature's textures (RGB colour, A smoothness; normal maps as they are)

glTF is +Y up with the model's front +Z (Godot's model front), Blender's front -Y going there by itself; metres. The
rig's bones all go (Root and the Motion bone of the root motion included); shape keys go as blend shapes, positions
only (the eagle's folded wings: Unity's calculated normals blackened them); materials go by name only, the pack builds
its own. tools/install_to_godot.py copies export/godot into the pack's project.
"""
import bpy, json, os, shutil
from mathutils import Matrix
from beast_common import ROOT
from beast_export import _reveal, _restore, _select

GODOT = os.path.join(ROOT, "export", "godot")

GLTF = dict(export_format="GLB", use_selection=True, export_yup=True, export_apply=True, export_skins=True,
            export_def_bones=False, export_rest_position_armature=True, export_morph=True, export_morph_normal=False,
            export_morph_tangent=False,
            export_materials="EXPORT", export_image_format="NONE", export_extras=True, export_animations=True,
            export_animation_mode="NLA_TRACKS", export_force_sampling=True, export_frame_step=1,
            export_anim_slide_to_zero=True, export_optimize_animation_size=False, export_reset_pose_bones=True,
            export_anim_single_armature=True)


def export_glb(anim, rig_name="WolfRig", meshes=("WolfBody",), name="Wolf", tex_prefix="T_Wolf", moving=None, clips=None):
    """anim: the clip module (CLIPS, FPS, MOVING, action_name, clear) or anything with those; moving: the root-motion
    clips when the module has no MOVING (the insectoids pass theirs); clips: the clip names (default anim.CLIPS).
    Returns the files written."""
    out = os.path.join(GODOT, name)
    os.makedirs(out, exist_ok=True)
    rig = bpy.data.objects[rig_name]
    objs = [bpy.data.objects[m] for m in meshes]
    scn = rig.users_scene[0]
    win = bpy.context.window
    prev_scene = win.scene if win else None
    if win: win.scene = scn            # the exporter's active scene (the kit's gdx_export: it visits every scene else)
    shown = _reveal([rig] + objs)
    hidden = rig.hide_get()
    keep = (scn.frame_start, scn.frame_end, scn.render.fps, scn.frame_current)
    names = list(clips or anim.CLIPS)
    moving = set(moving if moving is not None else getattr(anim, "MOVING", ()))
    rig.animation_data_create()
    ad = rig.animation_data
    old_action = ad.action
    old_tracks = [(t, t.mute) for t in ad.nla_tracks]
    tracks, meta = [], []
    path = os.path.join(out, name + ".glb")
    try:
        ad.action = None
        for t, _ in old_tracks: t.mute = True
        for pb in rig.pose.bones: pb.matrix_basis = Matrix.Identity(4)
        scn.render.fps = anim.FPS
        for clip in names:
            act = bpy.data.actions[anim.action_name(clip)]
            tr = ad.nla_tracks.new()
            tr.name = clip
            st = tr.strips.new(clip, int(act.frame_range[0]), act)
            if hasattr(st, "action_slot") and len(getattr(act, "slots", [])) > 0:
                st.action_slot = act.slots[0]            # Blender 4.4: a strip plays nothing without its slot
            tracks.append(tr)
            meta.append({
                "name": clip, "frames": int(act["frames"]), "fps": anim.FPS, "loop": bool(act["loop"]),
                "rootMotion": clip in moving,
                "events": [{"name": k[len("event_"):], "time": float(act[k])} for k in act.keys() if k.startswith("event_")],
            })
        bpy.context.view_layer.update()
        _select([rig] + objs)
        bpy.ops.export_scene.gltf(filepath=path, use_active_scene=True, **GLTF)
    finally:
        for tr in tracks: ad.nla_tracks.remove(tr)
        for t, m in old_tracks: t.mute = m
        ad.action = old_action
        scn.frame_start, scn.frame_end, scn.render.fps = keep[:3]
        scn.frame_set(keep[3])
        for o in [rig] + objs: o.select_set(False)
        rig.hide_set(hidden)
        _restore(shown)
        if win and prev_scene is not None: win.scene = prev_scene
    written = [path]
    with open(os.path.join(out, f"{name.lower()}_clips.json"), "w", encoding="utf-8") as f:
        json.dump({"clips": meta}, f, indent=1)
    written.append(f.name)
    tex = os.path.join(ROOT, "textures")
    for fn in sorted(os.listdir(tex)):
        if fn.startswith(tex_prefix) and fn.endswith(".png"):
            shutil.copy2(os.path.join(tex, fn), os.path.join(out, fn))
            written.append(os.path.join(out, fn))
    return written
