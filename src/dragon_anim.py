"""Dragon clips, keyed straight onto DragonRig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py.

Daniel 2026-10-17: animations next, "in small parts, so ground set first" (flight later: it waits on the membrane
fit and the shoulder tenting). The dragon is a quadruped to beast_anim -- Hips, Spine1, Spine2, Chest, Neck1-7,
Head, Jaw, Tail1-14, Scapula/UpperArm/Forearm/FrontPaw/FrontToes, Thigh/Shin/HindFoot/HindToes, Motion -- with no
ears and no tongue. The wings are its own (`_wings`, beast_anim's `extra` hook): they ride folded on the chest
(dragon_pose.FOLD) and can open toward another wing pose (`p.wing_open` toward `p.wing_to`, the raised threat
display by default) or lift a little with the breath (`p.wing_lift`, deg).

Big and heavy: 12 m, 2.8 m at the shoulder. Everything is slower than the beasts' clips; the neck (seven bones)
and the tail (fourteen) move in waves, each bone a little after the one before.

Clips (30 fps, the dragon faces -Y; Unity +Z):
  Idle       4.0 s loop   two slow breaths (chest and folded wings rise), the neck swaying, a look to its left,
                          a snort, the tail tip curling
  Walk       1.6 s loop   heavy lateral-sequence walk, shoulders rolling, the spine and tail swinging in an S,
                          head steady; root motion 1.25 m/s
  Run        0.8 s loop   heavy rotary gallop, back gathering and stretching, tail streaming; root motion 5.5 m/s
"""
import math
from mathutils import Vector, Matrix
import bpy
import beast_anim as BA
import dragon_body as DB
import dragon_pose as DP
from beast_anim import LegPose, K, ease, WALK, GALLOP

FPS = 30
RIG = "DragonRig"
_AIMS = {}


def _aims(key):
    """Wing aims (bone -> (direction, membrane normal), chest at rest) for 'fold' or a dragon_pose wing turn."""
    if key not in _AIMS:
        if key == "fold":
            _AIMS[key] = DP.wing_fold()
        elif key == "raised":                                   # up and back: the threat display (the fire pose's)
            _AIMS[key] = DP.wing_turned(bpy.data.objects[RIG], [('Y', -42), ('Z', 18)])
        else:
            raise KeyError(key)
    return _AIMS[key]


def _wings(sp, p, Wm, rel):
    """The wing bones, riding on the chest: folded, opened toward p.wing_to by p.wing_open, lifted by p.wing_lift."""
    R = BA.rest_data(sp)['R']
    B = BA.rest_data(sp)['B']
    turn = Wm["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    fold = _aims("fold")
    t = getattr(p, "wing_open", 0.0)
    alt = _aims(getattr(p, "wing_to", "raised")) if t else fold
    lift = Matrix.Rotation(math.radians(getattr(p, "wing_lift", 0.0)), 3, 'X')
    for s, sfx in DB.SIDES:
        n = f"WingScap{sfx}"
        Wm[n] = Wm["Chest"] @ rel(n, "Chest")
        for n in DB.wing_chain(sfx):
            par = B[n][3]
            here = Wm[par] @ rel(n, par)
            d = Vector(fold[n][0]).lerp(Vector(alt[n][0]), t)
            z = Vector(fold[n][1]).lerp(Vector(alt[n][1]), t)
            Wm[n] = Matrix.Translation(here.translation) @ DB._frame(turn @ (lift @ d), turn @ (lift @ z)).to_4x4()


SPEC = BA.Species(DB.rest_bones, (0.0, 0.35, 2.3), "Dragon", RIG, neck_n=DB.NECK_N, tail_n=DB.TAIL_N, tongue=False,
                  ears=False, tail_floor=[0.10] * DB.TAIL_N, extra=_wings)
LEGS = BA.LEGS
EVENTS = {}
MOVING = {"Walk", "Run"}


def DragonPose():
    return BA.Pose(SPEC)


def neutral(key):
    return BA.neutral(SPEC, key)


def gait(p, f, N, stride, duty, lift, phases, **kw):
    return BA.gait(SPEC, p, f, N, stride, duty, lift, phases, **kw)


def _neck_wave(p, pitch, yaw, phase=0.0, lag=0.35, spread=None):
    """Spread a neck turn over the seven bones (more at the base, `spread` weights), each a little behind the one
    before (`lag` radians): pitch / yaw are callables of the phase, or numbers."""
    w = spread or (1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7)
    tot = sum(w)
    for i in range(SPEC.neck_n):
        ph = phase - lag * i
        pv = pitch(ph) if callable(pitch) else pitch
        yv = yaw(ph) if callable(yaw) else yaw
        p.neck[i][0] += pv * w[i] / tot
        p.neck[i][1] += yv * w[i] / tot


def _tail_wave(p, amp, phase, lag=0.45, grow=0.12, lift=0.0, curl=0.0):
    """A wave running down the tail: each bone swings `amp` deg (growing toward the tip) a little after the one
    before; `lift` raises the whole tail (spread over the first bones), `curl` turns the last bones sideways."""
    n = SPEC.tail_n
    for i in range(n):
        p.tail[i][1] += amp * (1 + grow * i) * math.sin(phase - lag * i)
        p.tail[i][0] += lift * max(0.0, 1 - i / 5.0) / 3.0
        p.tail[i][1] += curl * max(0.0, (i - (n - 5)) / 5.0)


# ----------------------------------------------------------------------------------------- idle and locomotion
def _clip_idle():
    N = 120

    def fn(f):
        p = DragonPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 60                                          # two slow breaths a loop
        breath = math.sin(b)
        p.body = Vector((0.025 * math.sin(a), 0, 0.012 * breath))
        p.roll = 1.0 * math.sin(a)
        p.spine[2][0] = 1.2 * breath                                      # the chest swells
        p.wing_lift = 2.0 * math.sin(b - 0.4)                              # and the folded wings ride up on it
        look = K([(0, 0), (24, 0), (36, 1), (54, 1), (66, 0), (120, 0)], f)          # a look to its left
        snort = K([(0, 0), (86, 0), (89, 1), (93, 0.2), (98, 0), (120, 0)], f)        # a snort
        _neck_wave(p, lambda ph: 2.0 * math.sin(ph), lambda ph: 4.0 * math.sin(ph + 0.6), phase=a)
        _neck_wave(p, -6 * snort, 18 * look)
        p.head = [3 * math.sin(a + 1.2) + 8 * snort, 10 * look + 2 * math.sin(a + 1.6), 4 * look]
        p.jaw = 8 * snort
        _tail_wave(p, 1.1, a, curl=10 * math.sin(a - 1.0))
        return p
    return N, fn, True


def _clip_walk():
    """A heavy, deliberate walk: lateral sequence, the shoulders rolling, the spine and tail swinging in an S
    (reptile-like), the neck counter-swinging so the head stays on line."""
    N = 48

    def fn(f):
        p = DragonPose()
        gait(p, f, N, 2.0, 0.68, 0.24, WALK, front_fold=60, hind_flex=32, scap=14)
        a = 2 * math.pi * f / N
        p.body = Vector((0.04 * math.sin(a), 0, -0.03 - 0.025 * math.cos(2 * a)))
        p.roll = 2.5 * math.sin(a)
        p.yaw = 2.0 * math.sin(a + 0.8)
        p.pitch = 0.8 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -2.5 * math.sin(a + 0.8)
        _neck_wave(p, lambda ph: 1.5 * math.sin(2 * ph + 1.0), lambda ph: 6.0 * math.sin(ph + 2.4), phase=a,
                   lag=0.25)
        p.head = [-1.5 * math.sin(2 * a + 1.0), -2.0 * math.sin(a + 2.0), -2.0 * math.sin(a)]
        p.wing_lift = 1.2 * math.sin(2 * a - 1.2)
        _tail_wave(p, 1.6, a + 0.6)
        return p
    return N, fn, True


def _clip_run():
    """A heavy rotary gallop: the back gathers and stretches, the neck reaches forward and low with the head held
    level, the tail streams out and lifts against the bounds, the folded wings bounce."""
    N = 24

    def fn(f):
        p = DragonPose()
        gait(p, f, N, 4.4, 0.36, 0.42, GALLOP, front_fold=80, hind_flex=40, scap=22)
        a = 2 * math.pi * f / N
        gather = math.cos(a - 0.5)
        p.body = Vector((0, 0, -0.06 + 0.10 * math.sin(a - 1.2)))
        p.pitch = -2 + 4 * math.sin(a - 0.3)
        p.spine[0][0] = 7 * gather
        p.spine[1][0] = 3 * gather
        p.spine[2][0] = -6 * gather
        p.hips = [-8 * gather, 0, 0]
        _neck_wave(p, lambda ph: -16 - 5 * math.sin(ph - 0.3), 0.0, phase=a, lag=0.3)
        p.head = [12 + 5 * math.sin(a - 0.9), 0, 0]
        p.jaw = 6 + 4 * math.sin(a - 1.5)                                  # panting
        p.wing_lift = 4.0 * math.sin(a - 1.8)
        for i in range(SPEC.tail_n):
            p.tail[i][0] += 1.0 + 0.6 * math.sin(a - 1.0 - 0.35 * i)       # streams out, lifting against the bounds
        _tail_wave(p, 0.8, a, lag=0.5)
        return p
    return N, fn, True


CLIPS = {"Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run}


# ----------------------------------------------------------------------------------------- build
def pose_matrices(p):
    return BA.pose_matrices(SPEC, p)


def build_clip(name, rig_ob=None):
    return BA.build_clip(SPEC, CLIPS, EVENTS, name, rig_ob)


def build_clips(names=None):
    SPEC.rest.clear()
    _AIMS.clear()
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig_ob=None):
    BA.use(SPEC, name, rig_ob)


def clear(rig_ob=None):
    BA.clear(SPEC, rig_ob)


def still(p, rig_ob=None):
    BA.still(SPEC, p, rig_ob)


def report(names=None):
    """Lowest vertex per clip (sampled): nothing should go much under the ground."""
    return BA.ground_report(SPEC, names or CLIPS, "DragonBody")
