"""Skinning the wolf to its armature (beast_rig.build_armature(wolf_body.rest_bones())).

- Fur body: heat-map weights from the body bones (not Root/Motion, sockets, jaw or tongue), smoothed, 4 influences.
- Jaw, tongue and lower teeth ride rigidly on Jaw / Tongue1-2; eyes, nose, upper teeth on Head.
- The bottom of the jowls follows the jaw part way, so the corners of the mouth stretch when it opens.
"""
import bpy, math
import numpy as np
from mathutils import Matrix, Vector, Quaternion
import wolf_body as W
import beast_rig
from beast_rig import smooth_weights, clean_weights, weight_report
from beast_common import smoothstep

NO_HEAT = ("Root", "Motion", "Jaw", "Tongue1", "Tongue2")


def skin(body, rig):
    return beast_rig.skin(body, rig, NO_HEAT, W.hw_inv, tongue_t=lambda cu: smoothstep(-0.81, -0.87, cu[:, 1]),
                          jaw_weight=_jaw_weight)


def _jaw_weight(cu):
    """The bottom of the jowls follows the jaw part way, so the corners of the mouth stretch."""
    x, y, z = cu[:, 0], cu[:, 1], cu[:, 2]
    return smoothstep(0.776, 0.752, z) * smoothstep(-0.69, -0.725, y) * smoothstep(-0.815, -0.79, y)


# ----------------------------------------------------------------------------------------- test pose
TEST_POSE = {
    # bone: (axis in the bone's local frame, degrees)
    "Neck1": ('X', 12), "Neck2": ('X', 10), "Head": ('Z', 25), "Jaw": ('X', -32),
    "EarL": ('X', -35), "EarR": ('X', -35),
    "Tail1": ('X', -25), "Tail2": ('Z', 25), "Tail3": ('Z', 25), "Tail4": ('Z', 20),
    "UpperArmL": ('X', 35), "ForearmL": ('X', -60), "FrontPawL": ('X', 70),
    "UpperArmR": ('X', -25), "ForearmR": ('X', 10),
    "ThighL": ('X', -30), "ShinL": ('X', 45), "HindFootL": ('X', -40),
    "ThighR": ('X', 30), "ShinR": ('X', -10),
    "Spine2": ('Z', 10), "Chest": ('Z', 10),
}


def test_pose(rig, pose=TEST_POSE):
    for name, (ax, deg) in pose.items():
        pb = rig.pose.bones.get(name)
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        axis = Vector((1, 0, 0)) if ax == 'X' else Vector((0, 1, 0)) if ax == 'Y' else Vector((0, 0, 1))
        pb.rotation_quaternion = Quaternion(axis, math.radians(deg))
    bpy.context.view_layer.update()


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
