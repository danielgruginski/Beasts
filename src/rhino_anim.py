"""Woolly rhino clips, keyed straight onto the rig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py.

The boss's two attacks are the Charge (a head-down gallop with the front horn levelled ahead like a lance) and the
Gore (the head drops, then tosses up and hooks to its right; event 'Bite' at the top of the toss). The rest follow the
woods boss design: sleep in the wallow, wake, the pawing tell before a charge, dazed after hitting an obstacle, the
stamp, the roar.

Clips (30 fps, the rhino faces -Y; Unity +Z):
  Sleep      3.0 s loop   lying on its belly, legs folded, slow breathing, an ear twitch
  Wake       1.5 s        heaves up, front end first, shakes its head, ends in the Idle stance
  Idle       2.5 s loop   breathing, head bob, a snort, ear flicks, tail swish
  Walk       1.0 s loop   lateral-sequence walk, root motion 1.3 m/s
  Run        0.53 s loop  trot, root motion 3.75 m/s
  Charge     0.33 s loop  head-down rotary gallop, the horn levelled, root motion 9 m/s (the legs are short: speed it
                          up in game rather than lengthen the stride)
  Gore       1.0 s        head drops, then tosses up and hooks right (event 'Bite' at 0.45 s)
  Paw        1.2 s loop   head low, tail up, the right forefoot scrapes back twice (the charge's tell)
  Daze       2.0 s loop   staggering, legs splayed, head wobbling
  Stamp      1.3 s        rears its front end up and slams down (event 'Bite' at 1.0 s)
  Roar       1.5 s        head up, a long bellow (event 'Roar' at 0.3 s)
  Hit        0.4 s        a flinch
  Death      2.0 s        sags, collapses onto its right side (the spear stays up), a hind-leg kick (event 'Dead'
                          at 1.6 s); holds the end
"""
import math
from mathutils import Vector, Matrix
import rhino_body as RB
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, TROT, GALLOP

FPS = 30
SPEC = BA.Species(RB.rest_bones, (0.0, -0.05, 1.15), "Rhino", "RhinoRig", neck_n=2, tail_n=len(RB.TAIL) - 1,
                  tongue=False)
LEGS = BA.LEGS
EVENTS = {"Gore": [("Bite", 0.45)], "Stamp": [("Bite", 1.0)], "Roar": [("Roar", 0.3)], "Death": [("Dead", 1.6)]}
MOVING = {"Walk", "Run", "Charge"}
HIP_PIVOT = Vector((0.0, 0.78, 1.10))       # rearing turns the trunk about the hips


def RhinoPose():
    return BA.Pose(SPEC)


def neutral(key):
    return BA.neutral(SPEC, key)


def action_name(clip):
    return SPEC.action_name(clip)


def gait(p, f, N, stride, duty, lift, phases, **kw):
    return BA.gait(SPEC, p, f, N, stride, duty, lift, phases, **kw)


def pivot(p, pitch, pv=HIP_PIVOT):
    """Pitch the trunk about pv instead of its centre (sets p.pitch and adds the matching offset to p.body)."""
    C = SPEC.body_c
    R = Matrix.Rotation(math.radians(-pitch), 3, 'X')
    p.pitch = pitch
    p.body = p.body + (pv - C) - R @ (pv - C)


def _tail(p, lift, swing, phase=0.0):
    for i in range(SPEC.tail_n):
        p.tail[i] = [lift if i == 0 else lift * 0.3, swing * math.sin(phase - 0.8 * i), 0.0]


def _ears(p, fwd, splay=0.0, flickL=0.0, flickR=0.0):
    p.ears = {1: [fwd + flickL, splay], -1: [fwd + flickR, splay]}


def _flick(f, c, width=4.0, amp=-30.0):
    return amp * max(0.0, 1 - abs(f - c) / width)


# ----------------------------------------------------------------------------------------- lying down
LIE_DROP = 0.38                             # how far the trunk sinks: the skirt spreads on the ground


def _lie(p, front, hind):
    """Fold the legs under and sink the trunk; front / hind = 0 (standing) .. 1 (lying). The front end rising first
    tilts the trunk nose-up."""
    p.body = p.body + Vector((0, 0, -LIE_DROP * (0.5 * front + 0.5 * hind)))
    p.pitch += 9.0 * (hind - front)
    for s in (1, -1):
        F0, H0 = neutral(('F', s)), neutral(('H', s))
        fl = LegPose(target=F0 + Vector((s * 0.03, 0.30, 0.05)) * front)
        fl.flex = -90 * front
        fl.toe = -25 * front
        fl.scap = -8 * front
        hl = LegPose(target=H0 + Vector((s * 0.06, -0.42, 0.05)) * hind)
        hl.flex = 55 * hind
        hl.toe = -20 * hind
        p.legs[('F', s)] = fl
        p.legs[('H', s)] = hl
    p.neck[0][0] += 4 * front
    p.head[0] += -6 * front


def _clip_sleep():
    N = 90

    def fn(f):
        p = RhinoPose()
        a = 2 * math.pi * f / N
        _lie(p, 1.0, 1.0)
        p.body += Vector((0, 0, 0.010 * math.sin(a)))                     # slow breathing
        p.spine[2][0] = 1.0 * math.sin(a)
        p.neck[0][1] = 6
        p.head[1] = 4
        p.head[2] = 6
        _ears(p, -10, 10, flickR=_flick(f, 58, 3, -35))
        _tail(p, -10, 0)
        return p
    return N, fn, True


def _clip_wake():
    N = 45

    def fn(f):
        p = RhinoPose()
        t = f / N
        front = 1 - ease(t / 0.55)
        hind = 1 - ease((t - 0.30) / 0.55)
        _lie(p, front, hind)
        p.body += Vector((0, K([(0, 0), (8, 0.06), (24, -0.03), (45, 0)], f), 0))
        shake = K([(0, 0), (30, 0), (33, 1), (36, -1), (39, 0.7), (42, -0.3), (45, 0)], f)
        p.head[2] += 18 * shake
        p.head[1] += 8 * shake
        p.neck[0][0] += K([(0, 0), (6, -6), (20, 6), (32, 0), (45, 0)], f)
        _ears(p, -10 * front, 10 * front + 12 * abs(shake))
        _tail(p, K([(0, -10), (20, 5), (45, 0)], f), 8 * shake)
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- idle and locomotion
def _clip_idle():
    N = 75

    def fn(f):
        p = RhinoPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 25                                         # three breaths a loop
        p.body = Vector((0.010 * math.sin(a), 0, 0.006 * math.sin(b)))
        p.roll = 0.8 * math.sin(a)
        p.spine[2][0] = 0.8 * math.sin(b)
        snort = K([(0, 0), (40, 0), (42, 1), (46, -0.4), (52, 0), (75, 0)], f)
        p.neck[0] = [-2 + 2 * math.sin(a), 6 * math.sin(a + 0.6), 0]
        p.head = [2 * math.sin(b + 1.0) + 6 * snort, 5 * math.sin(a + 0.9), 3 * snort]
        p.jaw = 3 * snort
        _ears(p, 4, 4, flickL=_flick(f, 18), flickR=_flick(f, 60) + _flick(f, 65))
        _tail(p, 0, 14, a * 2)
        return p
    return N, fn, True


def _clip_walk():
    N = 30

    def fn(f):
        p = RhinoPose()
        gait(p, f, N, 1.30, 0.66, 0.12, WALK, front_fold=75, hind_flex=32, scap=12)
        a = 2 * math.pi * f / N
        p.body = Vector((0.012 * math.sin(a), 0, -0.015 - 0.012 * math.cos(2 * a)))
        p.roll = 2.0 * math.sin(a)
        p.yaw = 1.5 * math.sin(a + 0.8)
        p.pitch = 0.8 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -1.2 * math.sin(a + 0.8)
        p.neck[0][0] = -2 + 2.5 * math.sin(2 * a + 1.0)
        p.head = [1 - 2.5 * math.sin(2 * a + 1.0), -3 * math.sin(a), 0]
        _ears(p, 4, 2)
        _tail(p, 0, 10, a)
        return p
    return N, fn, True


def _clip_run():
    N = 16

    def fn(f):
        p = RhinoPose()
        gait(p, f, N, 2.00, 0.42, 0.17, TROT, front_fold=95, hind_flex=42, scap=16)
        a = 2 * math.pi * f / N
        p.body = Vector((0, 0, -0.03 - 0.025 * math.cos(2 * a)))
        p.roll = 1.5 * math.sin(a)
        p.pitch = -1 + 1.2 * math.sin(2 * a)
        p.neck[0][0] = -6 + 3 * math.sin(2 * a + 1.2)
        p.head = [-2 - 3 * math.sin(2 * a + 1.2), 0, 0]
        _ears(p, -12, 0)
        _tail(p, 15, 6, a)
        return p
    return N, fn, True


def _clip_charge():
    """The charge: a head-down rotary gallop; neck and head lowered so the front horn points straight ahead at
    chest height, like a levelled lance. The head rides steady while the body heaves."""
    N = 10

    def fn(f):
        p = RhinoPose()
        gait(p, f, N, 3.00, 0.22, 0.25, GALLOP, front_fold=65, hind_flex=45, scap=22)
        a = 2 * math.pi * f / N
        gather = math.cos(a - 0.5)                    # + gathered (back rounded), - stretched
        p.body = Vector((0, 0, -0.03 + 0.05 * math.sin(a - 1.2)))
        bob = 2.5 * math.sin(a - 0.3)
        p.pitch = -2 + bob
        p.spine[0][0] = 4 * gather
        p.spine[2][0] = -4 * gather
        p.hips = [-6 * gather, 0, 0]
        p.neck[0][0] = -12 - bob * 0.6                # the neck takes up the heave: the horn stays level
        p.neck[1][0] = -6 - bob * 0.4
        p.head = [-12, 0, 0]
        _ears(p, -40, -4)
        _tail(p, 35, 4, a)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- attacks and tells
def _clip_gore():
    """The horn attack: weight back and head down (the horn levelled low at the foe), a step in with the right
    forefoot, then a toss up and to its right through the target (event 'Bite' at 0.45 s), and back."""
    N = 30

    def fn(f):
        p = RhinoPose()
        p.body = Vector((K([(0, 0), (9, 0), (13, -0.04), (18, -0.03), (30, 0)], f),
                         K([(0, 0), (9, 0.10), (12, -0.12), (15, -0.22), (22, -0.08), (30, 0)], f),
                         K([(0, 0), (9, -0.06), (13, 0.03), (17, 0.01), (30, 0)], f)))
        p.pitch = K([(0, 0), (9, -4), (13, 6), (17, 4), (30, 0)], f)
        p.roll = K([(0, 0), (9, 0), (14, -4), (20, -2), (30, 0)], f)
        n = K([(0, 0), (9, -14), (12, 4), (14, 12), (18, 6), (30, 0)], f)
        p.neck[0][0], p.neck[1][0] = n, 0.6 * n
        hook = K([(0, 0), (9, 6), (12, -8), (14, -24), (18, -20), (30, 0)], f)     # - = toward its right
        p.neck[0][1] = 0.4 * hook
        p.head = [K([(0, 0), (9, -24), (11.5, 0), (13.5, 30), (17, 22), (30, 0)], f), 0.6 * hook,
                  K([(0, 0), (9, 0), (14, -18), (20, -8), (30, 0)], f)]
        p.jaw = K([(0, 0), (13, 2), (15, 8), (22, 4), (30, 0)], f)
        e = K([(0, 0), (6, -35), (24, -35), (30, 0)], f)
        _ears(p, e, -4)
        _tail(p, K([(0, 0), (8, 25), (24, 25), (30, 0)], f), 0)
        step = K([(0, 0), (9, 0), (12.5, 1), (22, 1), (27, 0), (30, 0)], f)       # the right forefoot steps in
        up = K([(0, 0), (9, 0), (11, 1), (12.5, 0), (22, 0), (24.5, 1), (27, 0), (30, 0)], f)
        F0 = neutral(('F', -1))
        lp = LegPose(target=F0 + Vector((0, -0.26 * step, 0.16 * up)))
        lp.flex = -60 * up
        lp.scap = 10 * step
        p.legs[('F', -1)] = lp
        p.legs[('F', 1)].scap = K([(0, 0), (9, -6), (14, 8), (30, 0)], f)
        return p
    return N, fn, False


def _clip_paw():
    """The tell before a charge: head low with the horn levelled, tail up, the right forefoot scraping the ground
    back twice (two 0.6 s cycles)."""
    N = 36

    def fn(f):
        p = RhinoPose()
        a = 2 * math.pi * f / N
        p.body = Vector((0, 0.06, -0.05))
        p.pitch = -4
        snort = K([(0, 0), (8, 0), (10, 1), (14, 0), (26, 0), (28, 1), (32, 0), (36, 0)], f, N)
        p.neck[0][0] = -12 + 3 * snort
        p.neck[1][0] = -5
        p.head = [-14 + 4 * snort, 2 * math.sin(a), 0]
        p.jaw = 4 * snort
        _ears(p, -30, -4)
        _tail(p, 30, 10, 2 * a)
        q = (f % 18) / 18.0
        F0 = neutral(('F', -1))
        y = K([(0, 0.16), (4.5, -0.16), (7, -0.18), (15.5, 0.16), (18, 0.16)], q * 18)
        z = K([(0, 0.0), (1.5, 0.09), (4.5, 0.13), (7, 0.0), (18, 0.0)], q * 18)
        lp = LegPose(target=F0 + Vector((0, y, z)))
        lp.flex = -70 * (z / 0.13)
        lp.toe = 15 * (0.0 if z > 0.01 else 1.0)
        lp.scap = -12 * (y / 0.16)
        p.legs[('F', -1)] = lp
        return p
    return N, fn, True


def _clip_daze():
    N = 60

    def fn(f):
        p = RhinoPose()
        a = 2 * math.pi * f / N
        p.body = Vector((0.05 * math.sin(a), 0.04, -0.07 + 0.012 * math.sin(2 * a)))
        p.roll = 4 * math.sin(a)
        p.yaw = 3 * math.sin(a + 1.0)
        p.neck[0] = [-16 + 3 * math.sin(2 * a), 8 * math.sin(a + 0.5), 0]
        p.neck[1] = [-6, 4 * math.sin(a + 0.8), 0]
        p.head = [-8 + 4 * math.sin(2 * a + 0.4), 10 * math.sin(a + 1.0), 10 * math.sin(a + 0.3)]
        p.jaw = 6 + 3 * math.sin(2 * a)
        _ears(p, -20, 18 + 6 * math.sin(a))
        _tail(p, -6, 4, a)
        for kind, s in LEGS:                                              # legs splayed to keep it up
            p.legs[(kind, s)] = LegPose(target=neutral((kind, s)) + Vector((s * 0.08, 0.04 if kind == 'F' else -0.03, 0)))
        return p
    return N, fn, True


def _clip_stamp():
    """Rears its front end up off the ground and slams both forefeet down (event 'Bite' at 1.0 s)."""
    N = 39

    def fn(f):
        p = RhinoPose()
        up = K([(0, 0), (6, 0.12), (16, 0.85), (26, 1.0), (28.5, 0.55), (30, -0.08), (32, -0.10), (39, 0)], f)
        p.body = Vector((0, 0.08 * max(up, 0), 0.10 * min(up, 0)))
        pivot(p, 21 * max(up, 0) + 8 * min(up, 0))
        p.hips = [-6 * max(up, 0), 0, 0]
        p.neck[0][0] = 10 * max(up, 0) - 22 * K([(0, 0), (28, 0), (30, 1), (34, 0.6), (39, 0)], f)
        p.head = [12 * max(up, 0), 0, 0]
        p.jaw = 16 * K([(0, 0), (10, 0), (16, 1), (26, 1), (29, 0), (39, 0)], f)
        e = K([(0, 0), (8, -30), (34, -30), (39, 0)], f)
        _ears(p, e, 0)
        _tail(p, 20 * max(up, 0), 0)
        air = K([(0, 0), (6, 0), (10, 1), (27, 1), (29.5, 0), (39, 0)], f)
        for s in (1, -1):
            lp = LegPose(target=neutral(('F', s)), wb=air)
            lp.boff = Vector((0, -0.06, 0.10))
            lp.flex = -75 * air
            lp.toe = -20 * air
            lp.scap = 14 * air
            p.legs[('F', s)] = lp
            hl = LegPose(target=neutral(('H', s)))
            hl.flex = 12 * max(up, 0)
            p.legs[('H', s)] = hl
        return p
    return N, fn, False


def _clip_roar():
    N = 45

    def fn(f):
        p = RhinoPose()
        up = K([(0, 0), (10, 1), (36, 1), (45, 0)], f)
        p.body = Vector((0, 0.05 * up, 0.01 * up))
        p.pitch = 5 * up
        p.hips[0] = -3 * up
        p.neck[0][0] = 16 * up
        p.neck[1][0] = 14 * up
        p.head = [24 * up, 3 * math.sin(2 * math.pi * f / 15) * up, 0]
        p.jaw = K([(0, 0), (8, 4), (12, 20), (34, 22), (40, 3), (45, 0)], f) + 2 * math.sin(2 * math.pi * f / 6) * up
        _ears(p, -30 * up, 6 * up)
        _tail(p, 22 * up, 0)
        return p
    return N, fn, False


def _clip_hit():
    N = 12

    def fn(f):
        p = RhinoPose()
        k = K([(0, 0), (3, 1), (12, 0)], f)
        p.body = Vector((0.04 * k, 0.05 * k, -0.02 * k))
        p.roll, p.yaw = 5 * k, -5 * k
        p.neck[0] = [-6 * k, -8 * k, 0]
        p.head = [8 * k, -14 * k, 6 * k]
        p.jaw = K([(0, 0), (3, 12), (8, 3), (12, 0)], f)
        e = K([(0, 0), (2, -35), (9, -15), (12, 0)], f)
        _ears(p, e, 0)
        _tail(p, -10 * k, 0)
        return p
    return N, fn, False


def _death_pose(f):
    p = RhinoPose()
    # sags, the front buckles, rolls onto its right side (it rests on its flank, centre ~0.6 m up), so the spear in
    # its left shoulder stands up out of the corpse to be looted
    p.roll = -K([(0, 0), (10, -4), (24, 20), (34, 58), (42, 84), (48, 80), (60, 82)], f)
    p.body = Vector((-K([(0, 0), (10, -0.04), (34, 0.25), (42, 0.38), (60, 0.38)], f), K([(0, 0), (42, 0.06), (60, 0.06)], f),
                     K([(0, 0), (10, -0.06), (24, -0.15), (34, -0.26), (42, -0.41), (48, -0.40), (60, -0.42)], f)))
    p.pitch = K([(0, 0), (10, -6), (24, -8), (42, -2), (60, -2)], f)
    down = K([(0, 0), (30, 0), (46, 1), (60, 1)], f)
    p.neck[0] = [-6 * down + K([(0, 0), (6, 10), (16, -6), (30, 0)], f), -6 * down, 0]
    p.neck[1] = [-4 * down, -4 * down, 0]
    p.head = [-6 * down, -4 * down, -10 * down]
    p.jaw = K([(0, 0), (6, 18), (20, 10), (50, 8), (60, 7)], f)
    e = K([(0, 0), (4, -35), (60, -15)], f)
    _ears(p, e, 10 * down)
    _tail(p, -6 * down, 8 * down)
    wb = K([(0, 0), (16, 0), (34, 1), (60, 1)], f)
    kick = K([(0, 0), (46, 0), (50, 1), (54, 0), (60, 0)], f)
    for kind, s in LEGS:
        lp = LegPose(wb=wb)
        up_side = s > 0                                  # lying on its right side: the left legs are on top
        lp.boff = Vector((-(0.10 if up_side else 0.02), (0.05 if kind == 'H' else -0.05) - 0.12 * kick * (kind == 'H' and up_side),
                          0.03 if up_side else 0.12))      # the down-side feet ride a little higher as it rolls
        lp.flex = (-20 if kind == 'F' else 12) * wb + (25 * kick if kind == 'H' and up_side else 0)
        lp.toe = -25 * wb
        p.legs[(kind, s)] = lp
    return p


def _clip_death():
    return 60, _death_pose, False


CLIPS = {"Sleep": _clip_sleep, "Wake": _clip_wake, "Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run,
         "Charge": _clip_charge, "Gore": _clip_gore, "Paw": _clip_paw, "Daze": _clip_daze, "Stamp": _clip_stamp,
         "Roar": _clip_roar, "Hit": _clip_hit, "Death": _clip_death}


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
