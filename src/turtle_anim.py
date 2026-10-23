"""Giant turtle clips (2026-10-23), keyed straight onto TurtleRig; the machinery (poses, leg IK, gaits, keying) is
beast_anim.py, with one addition: `p.retract` (m) slides the neck, head and jaw back into the shell along the
trunk (negative stretches the neck out: the snap), done in the Species' extra hook. The spine never bends (the
shell rides on Spine1).

Clips (30 fps, the turtle faces -Y; Unity +Z):
  Idle      4.0 s loop   slow breathing, the head turns this way and that, the mouth gapes open for a while (the
                         snapper's lure) and shuts
  Walk      1.6 s loop   a slow lateral walk, the shell rocking; root motion 0.34 m/s
  Bite      1.1 s        draws the head back, jaw wide, then the neck shoots 0.35 m out and the beak snaps shut
                         (event 'Bite' at 0.53 s)
  Withdraw  1.2 s        the head and neck slide into the shell, the forelegs fold up in front of it, the hind feet
                         tuck under the rim, the shell drops onto its plastron; holds (the defensive pose)
  Emerge    1.4 s        out again, a look round
  Hit       0.5 s        a jolt, the head half pulled in
  Death     2.5 s        the legs give way, the shell drops and tips a little, the head slides out and down onto the
                         ground, the jaw slack (event 'Dead' at 2.0 s); holds
"""
import math
from mathutils import Vector, Matrix
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK
import turtle_body as TB

FPS = 30
NECK_CHAIN = ("Neck1", "Neck2", "Neck3", "Head", "Jaw")


def _retract(sp, p, Wm, rel):
    r = getattr(p, "retract", 0.0)
    if not r:
        return
    R = BA.rest_data(sp)['R']
    turn = Wm["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    T = Matrix.Translation(turn @ Vector((0.0, r, -0.10 * max(r, 0.0))))
    for n in NECK_CHAIN:
        Wm[n] = T @ Wm[n]


SPEC = BA.Species(TB.rest_bones, (0.0, 0.0, 0.95), "Turtle", TB.RIG, neck_n=3, tail_n=len(TB.TAIL) - 1,
                  tongue=False, ears=False, tail_floor=[0.16, 0.10, 0.05], extra=_retract)
LEGS = BA.LEGS
EVENTS = {"Bite": [("Bite", 0.53)], "Death": [("Dead", 2.0)]}
MOVING = {"Walk"}
DROP = 0.44                                   # the shell down onto its plastron


def TurtlePose():
    p = BA.Pose(SPEC)
    p.retract = 0.0
    return p


def neutral(key):
    return BA.neutral(SPEC, key)


def action_name(clip):
    return SPEC.action_name(clip)


def _tail(p, lift, swing, phase=0.0):
    for i in range(SPEC.tail_n):
        p.tail[i][0] += lift / SPEC.tail_n
        p.tail[i][1] += swing * math.sin(phase - 0.6 * i) * (0.6 + 0.3 * i)


def _tuck(p, k, head=True):
    """The defensive pose by k (0 out .. 1 in): the head slides in, the forelegs fold up in front of the opening,
    the hind feet tuck under the rim, the shell drops onto its plastron."""
    p.body = p.body + Vector((0, 0, -DROP * ease(k) ** 1.6))           # the legs fold first, the shell drops after
    if head:
        p.retract += 0.72 * k
        p.neck[0][0] += -10 * k
        p.neck[1][0] += 18 * k
        p.neck[2][0] += 8 * k
        p.head[0] += -6 * k
    for s in (1, -1):
        fl = LegPose(wb=k)
        fl.boff = Vector((-0.30 * s, -0.04, 0.47)) * k
        fl.flex = -5 * k
        fl.toe = -20 * k
        hl = LegPose(wb=k)
        hl.boff = Vector((-0.24 * s, -0.16, 0.46)) * k
        hl.flex = 18 * k
        hl.toe = 12 * k
        p.legs[('F', s)] = fl
        p.legs[('H', s)] = hl
    for i in range(SPEC.tail_n):
        p.tail[i][1] += 12 * k
        p.tail[i][0] += -4 * k


# ----------------------------------------------------------------------------------------- clips
def _clip_idle():
    N = 120

    def fn(f):
        p = TurtlePose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 40                                   # three slow breaths a loop
        p.body = Vector((0, 0, 0.008 * math.sin(b)))
        look = K([(0, 0), (20, 0), (34, 18), (56, 18), (70, -14), (92, -14), (106, 0), (120, 0)], f, N)
        p.neck[0] = [1.5 * math.sin(b), look * 0.4, 0]
        p.neck[1] = [0, look * 0.3, 0]
        p.head = [2 * math.sin(b + 0.7), look * 0.3, look * 0.08]
        gape = K([(0, 0), (60, 0), (72, 1), (96, 1), (104, 0), (120, 0)], f, N)
        p.jaw = 26 * gape + 1.5 * math.sin(b)
        p.head[0] += 6 * gape
        p.retract = 0.03 * math.sin(b)
        _tail(p, 0, 3, a)
        return p
    return N, fn, True


def _clip_walk():
    N = 48

    def fn(f):
        p = TurtlePose()
        BA.gait(SPEC, p, f, N, 0.55, 0.76, 0.10, WALK, front_fold=30, hind_flex=18, scap=6)
        a = 2 * math.pi * f / N
        p.body = Vector((0.015 * math.sin(a), 0, -0.010 + 0.010 * math.cos(2 * a)))
        p.roll = 2.2 * math.sin(a)
        p.yaw = 1.2 * math.sin(a + 0.8)
        p.pitch = 0.6 * math.sin(2 * a)
        p.neck[0] = [-1 + 1.5 * math.sin(2 * a + 1.0), -3 * math.sin(a), 0]
        p.head = [1.5 - 1.5 * math.sin(2 * a + 1.0), -2 * math.sin(a), 0]
        p.retract = -0.03 + 0.02 * math.sin(2 * a)
        _tail(p, 0, 5, a)
        return p
    return N, fn, True


BITE_AT = 16


def _clip_bite():
    N = 33

    def fn(f):
        p = TurtlePose()
        p.retract = K([(0, 0), (8, 0.14), (12, 0.12), (BITE_AT, -0.36), (20, -0.34), (27, -0.10), (33, 0)], f)
        p.jaw = K([(0, 0), (6, 8), (11, 36), (BITE_AT - 2, 36), (BITE_AT, 0), (33, 0)], f)
        p.neck[0] = [K([(0, 0), (8, 6), (BITE_AT, -6), (33, 0)], f), 0, 0]
        p.neck[2] = [K([(0, 0), (8, -6), (BITE_AT, 4), (33, 0)], f), 0, 0]
        p.head = [K([(0, 0), (8, 12), (12, 14), (BITE_AT, -4), (24, -2), (33, 0)], f), 0, 0]
        p.body = Vector((0, K([(0, 0), (8, 0.04), (BITE_AT, -0.08), (26, -0.04), (33, 0)], f),
                         K([(0, 0), (8, 0.02), (BITE_AT, -0.02), (33, 0)], f)))
        p.pitch = K([(0, 0), (8, 2), (BITE_AT, -2.5), (33, 0)], f)
        for s in (1, -1):                              # the forefeet brace
            lp = LegPose(target=neutral(('F', s)))
            lp.flex = K([(0, 0), (8, -6), (BITE_AT, 4), (33, 0)], f)
            p.legs[('F', s)] = lp
        _tail(p, 0, 4, f * 0.3)
        return p
    return N, fn, False


def _clip_withdraw():
    N = 36

    def fn(f):
        p = TurtlePose()
        _tuck(p, ease(f / 26))
        p.jaw = K([(0, 0), (4, 14), (12, 4), (20, 0)], f)          # a hiss on the way in
        return p
    return N, fn, False


def _clip_emerge():
    N = 42

    def fn(f):
        p = TurtlePose()
        _tuck(p, 1.0 - ease((f - 4) / 26))
        look = K([(0, 0), (24, 0), (30, 14), (36, -10), (42, 0)], f)
        p.neck[0][1] += look * 0.5
        p.head[1] += look * 0.4
        return p
    return N, fn, False


def _clip_hit():
    N = 15

    def fn(f):
        p = TurtlePose()
        k = K([(0, 0), (2, 1), (6, 0.6), (11, -0.1), (15, 0)], f)
        p.body = Vector((0.03 * k, 0.06 * k, 0.03 * k))
        p.roll, p.yaw, p.pitch = 4 * k, -3 * k, 3 * k
        p.retract = 0.22 * max(k, 0)
        p.neck[1][0] = 10 * k
        p.head = [-6 * k, -6 * k, 4 * k]
        p.jaw = K([(0, 0), (2, 22), (8, 5), (15, 0)], f)
        _tail(p, 0, 6 * k, f * 0.5)
        return p
    return N, fn, False


def _death_pose(f):
    p = TurtlePose()
    give = K([(0, 0), (10, 0.15), (24, 0.75), (34, 1.0), (40, 0.97), (75, 1.0)], f)
    p.body = Vector((0.04 * give, 0.03 * give, -(DROP - 0.045) * give + 0.012 * K([(0, 0), (34, 0), (37, 1), (42, 0)], f)))
    p.roll = 3.0 * give
    p.pitch = K([(0, 0), (20, -2), (34, -4), (75, -4)], f)
    out = K([(0, 0), (14, 0.05), (34, 0.25), (56, 0.30), (75, 0.30)], f)
    p.retract = -out
    down = K([(0, 0), (24, 0), (52, 1), (75, 1)], f)
    p.neck[0] = [K([(0, 0), (6, 8), (16, 0)], f) - 2 * down, 6 * down, 0]
    p.neck[1] = [-1 * down, 5 * down, 0]
    p.neck[2] = [0, 4 * down, 0]
    p.head = [4 * down, 6 * down, -8 * down]
    p.jaw = K([(0, 0), (6, 22), (20, 12), (60, 10), (75, 10)], f)
    for kind, s in LEGS:
        lp = LegPose(wb=give)
        lp.boff = Vector((0.12 * s, -0.06 if kind == 'F' else 0.08, 0.50 if kind == 'F' else 0.45)) * give
        lp.flex = (5 if kind == 'F' else 18) * give
        lp.toe = -20 * give
        p.legs[(kind, s)] = lp
    for i in range(SPEC.tail_n):
        p.tail[i][0] += -6 * down
        p.tail[i][1] += -8 * down
    return p


def _clip_death():
    return 75, _death_pose, False


CLIPS = {"Idle": _clip_idle, "Walk": _clip_walk, "Bite": _clip_bite, "Withdraw": _clip_withdraw,
         "Emerge": _clip_emerge, "Hit": _clip_hit, "Death": _clip_death}
SHEET_FRAMES = {"Idle": (0, 34, 72, 96), "Walk": (0, 12, 24, 36), "Bite": (0, 8, 12, 16, 22, 33),
                "Withdraw": (0, 8, 16, 26, 36), "Emerge": (0, 10, 20, 30, 42), "Hit": (0, 2, 6, 11),
                "Death": (0, 14, 24, 34, 52, 75)}


# ----------------------------------------------------------------------------------------- build / export
def pose_matrices(p):
    return BA.pose_matrices(SPEC, p)


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
