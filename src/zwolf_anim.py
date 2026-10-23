"""Zombie wolf clips: the wolf's twelve (wolf_anim.CLIPS, unchanged) keyed onto the zombie wolf's rig. It is the wolf's
skeleton (wolf_body.rest_bones), so the poses, the leg IK and the events are the wolf's to the vertex.

The rig is named WolfRig like the wolf's, so in Unity the clips' curve paths are the same: the wolf's own clips play on
the zombie wolf and these on the wolf. These are exported as ZombieWolf@<clip>.fbx all the same, so its setup is
self-contained (ZombieWolfSetup.cs).

Clips (30 fps): Idle, IdlePant, Walk (1.0 m/s), Trot (2.06 m/s), Run (5.5 m/s), Bite ('Bite' 0.47 s), Lunge (1.6 m,
'Bite' 0.87 s), Threat, Howl ('Howl' 0.8 s), Hit, Death ('Dead' 1.9 s, onto its left side: the torn right flank up),
GetUp. See wolf_anim.py.
"""
import beast_anim as BA
import wolf_body as W
import wolf_anim

FPS = wolf_anim.FPS
RIG = "WolfRig"
SPEC = BA.Species(W.rest_bones, (0.0, 0.0, 0.66), "ZombieWolf", RIG, neck_n=2, tail_n=5, tongue=True)
CLIPS = wolf_anim.CLIPS
EVENTS = wolf_anim.EVENTS
MOVING = wolf_anim.MOVING
# key frames for the contact sheets (renders/zwolf_clip_<Clip>.png)
SHEET_FRAMES = {"Idle": (0, 40, 80), "IdlePant": (0, 4), "Walk": (0, 6, 12, 18), "Trot": (0, 4, 8, 12),
                "Run": (0, 3, 6, 9), "Bite": (0, 9, 13, 20), "Lunge": (10, 16, 22, 30), "Threat": (0, 30),
                "Howl": (0, 50), "Hit": (0, 3), "Death": (0, 20, 38, 66), "GetUp": (0, 20, 45)}


def action_name(clip):
    return SPEC.action_name(clip)


def build_clip(name, rig_ob=None):
    return BA.build_clip(SPEC, CLIPS, EVENTS, name, rig_ob)


def build_clips(names=None):
    SPEC.rest.clear()
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig_ob=None):
    BA.use(SPEC, name, rig_ob)


def clear(rig_ob=None):
    BA.clear(SPEC, rig_ob)


def still(p, rig_ob=None):
    BA.still(SPEC, p, rig_ob)
