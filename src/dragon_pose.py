"""Test poses for the dragon blockout: the wing fold is the make-or-break, so the proportions are judged in the
poses that stress it before any detail goes on (standing with the wings folded, wings spread, the flight downstroke,
head low breathing fire).

A pose is turns in each bone's own frame (`rot`: bone -> [(axis, deg), ...]) plus, for the wings, aimed bones
(`aim`: bone -> (direction, membrane normal), written as if the chest were at rest; they ride on the chest's turn).
Left side written, the right mirrored.
"""
import bpy, math
from mathutils import Vector, Matrix
import beast_rig
import dragon_body as D


def _mirror_rot(sfx, ax, deg):
    """A turn about a bone's local axis, mirrored for the right side: the wing and leg frames mirror so that X turns
    keep their sign and Y / Z turns flip."""
    return (ax, deg if (sfx == "L" or ax == 'X') else -deg)


def solve(rig, rot=None, aim=None, lift=0.0, key_frame=None):
    """Pose the rig (matrix_basis on every bone). -> armature-space matrices."""
    rot, aim = rot or {}, aim or {}
    R = beast_rig.rest(rig)
    world, basis = {}, {}
    turn = None
    for b in sorted(rig.data.bones, key=lambda b: len(b.parent_recursive)):
        n = b.name
        here = R[n].copy() if b.parent is None else world[b.parent.name] @ (R[b.parent.name].inverted() @ R[n])
        if n == "Root" and lift:
            m = Matrix.Translation((0, 0, lift)) @ here
        elif n in aim:
            if turn is None:
                turn = world["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
            d, z = aim[n]
            m = Matrix.Translation(here.translation) @ D._frame(turn @ Vector(d), turn @ Vector(z)).to_4x4()
        else:
            q = Matrix.Identity(3)
            for ax, deg in rot.get(n, ()):
                q = q @ Matrix.Rotation(math.radians(deg), 3, ax)
            m = here @ q.to_4x4()
        world[n] = m
        basis[n] = here.inverted() @ m
    for n, m in basis.items():
        pb = rig.pose.bones[n]
        pb.matrix_basis = m
        if key_frame is not None:
            pb.keyframe_insert("location", frame=key_frame, group=n)
            pb.keyframe_insert("rotation_quaternion", frame=key_frame, group=n)
    bpy.context.view_layer.update()
    return world


# ----------------------------------------------------------------------------------------- wing states
# folded (left wing, armature space with the chest at rest): the humerus back along the flank, the forearm folded
# forward so the wrist (thumb claw) sits above and in front of the shoulder, the fingers swept back along the body
# in a narrow fan; the membrane's upper side faces out.
FOLD = {
    "WingArm": ((0.30, 0.90, -0.30), (0.95, 0.0, 0.30)),
    "WingForearm": ((0.02, -0.90, 0.44), (0.99, 0.0, 0.10)),
    "WingHand": ((0.02, -0.25, 0.97), (1.0, 0.0, 0.0)),
    "WingThumb": ((0.15, -0.75, 0.64), (1.0, 0.0, 0.0)),
    "F1": ((-0.02, 0.99, -0.08), (0.99, 0.0, 0.12)),
    "F2": ((-0.03, 0.96, -0.25), (0.99, 0.0, 0.12)),
    "F3": ((-0.04, 0.91, -0.40), (0.99, 0.0, 0.12)),
    "F4": ((-0.05, 0.84, -0.53), (0.99, 0.0, 0.12)),
}


def _mx(v, s):
    return (v[0] * s, v[1], v[2])


def wing_fold(fold=FOLD):
    aim = {}
    for s, sfx in D.SIDES:
        for key, (d, z) in fold.items():
            if key.startswith("F"):
                i = int(key[1]) - 1
                for k in range(D.FINGER_SEGS[i]):
                    aim[f"WingF{i + 1}_{k + 1}{sfx}"] = (_mx(d, s), _mx(z, s))
            else:
                aim[key + sfx] = (_mx(d, s), _mx(z, s))
    return aim


def wing_turned(rig, turns, curl=0.0):
    """The spread (rest) wing turned rigidly about the shoulder: turns = [(world axis, deg), ...] for the left wing
    (+Y turns it down, -Y up, +Z sweeps it back), mirrored for the right. curl (deg): each finger joint bends the
    finger down by this much (a cupped downstroke)."""
    R = beast_rig.rest(rig)
    aim = {}
    for s, sfx in D.SIDES:
        M = Matrix.Identity(3)
        for ax, deg in turns:
            M = Matrix.Rotation(math.radians(deg if (s > 0 or ax == 'X') else -deg), 3, ax) @ M
        for n in D.wing_chain(sfx):
            d, z = M @ R[n].col[1].xyz, M @ R[n].col[2].xyz
            if curl and n.startswith("WingF") and n[5].isdigit():
                k = int(n.split("_")[1][0])
                c = Matrix.Rotation(math.radians(-curl * k), 3, d.cross(z).normalized())
                d, z = c @ d, c @ z
            aim[n] = (tuple(d), tuple(z))
    return aim


# ----------------------------------------------------------------------------------------- poses
def _sym(rot):
    """{'UpperArm': [...]} -> both sides (mirrored turns); names with no side pass through."""
    out = {}
    for n, turns in rot.items():
        if n in ("UpperArm", "Forearm", "FrontPaw", "FrontToes", "Thigh", "Shin", "HindFoot", "HindToes", "Scapula",
                 "WingScap"):
            for _, sfx in D.SIDES:
                out[n + sfx] = [_mirror_rot(sfx, ax, deg) for ax, deg in turns]
        else:
            out[n] = turns
    return out


NECK_FIRE = [-20, -16, -10, -2, 8, 14, 18]
NECK_FLY = [-8, -14, -16, -12, -6, 2, 8]


def pose(rig, name):
    if name == "spread":                                   # the bind pose
        return solve(rig)
    if name == "folded":
        return solve(rig, aim=wing_fold())
    if name == "downstroke":
        rot = {f"Neck{i + 1}": [('X', a)] for i, a in enumerate(NECK_FLY)}
        rot.update({"Head": [('X', 12)], "Tail1": [('X', 14)], "Tail2": [('X', 6)], "Tail3": [('X', 2)]})
        rot.update(_sym({"UpperArm": [('X', -40)], "Forearm": [('X', 70)], "FrontPaw": [('X', 50)],
                         "Thigh": [('X', -55)], "Shin": [('X', -35)], "HindFoot": [('X', -35)]}))
        return solve(rig, rot=rot, aim=wing_turned(rig, [('Y', 34)], curl=6), lift=3.5)
    if name == "fire":
        rot = {f"Neck{i + 1}": [('X', a)] for i, a in enumerate(NECK_FIRE)}
        rot.update({"Head": [("X", 30)], "Jaw": [("X", -34)], "Chest": [("X", -6)]})
        return solve(rig, rot=rot, aim=wing_turned(rig, [('Y', -42), ('Z', 18)]))
    raise KeyError(name)


POSES = ("folded", "spread", "downstroke", "fire")
