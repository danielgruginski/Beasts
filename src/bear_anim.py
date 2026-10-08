"""Cave bear clips, keyed straight onto the rig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py.

A close-quarters brute: it swipes, bites, rears up to its full height, crashes down on both forepaws, and bear-hugs.
Rearing turns the whole trunk about the hip joints (`pivot`); the forelegs then ride with the chest (wb = 1) and the
neck and head pitch back down so the face looks ahead. The feet are plantigrade: the heels lift at the end of a step
(negative hind flex), the soles stay flat when it stands up.

Clips (30 fps, the bear faces -Y; Unity +Z):
  Sleep      3.0 s loop   lying on its belly, head resting on its forepaws, slow breathing, an ear twitch
  Wake       1.5 s        heaves up, front end first, shakes its head, ends in the Idle stance
  Idle       3.0 s loop   breathing, a look round, a forepaw shifted, a sniff of the air, ear flicks
  Walk       1.07 s loop  heavy lateral-sequence walk, shoulders rolling, head low and swinging, 1.03 m/s
  Run        0.43 s loop  bounding lope (rotary gallop), root motion 5.3 m/s
  Swipe      1.0 s        a right-paw haymaker from the side across the front (event 'Bite' at 0.42 s)
  Bite       1.0 s        coils, lunges with a forepaw stepping in, bites and shakes (event 'Bite' at 0.4 s)
  Slam       1.4 s        rears and crashes down on both forepaws (event 'Bite' at 0.77 s)
  Hug        2.0 s        rears, opens its forelegs wide and crushes them shut (event 'Bite' at 0.73 s)
  Rear       2.7 s        stands up to its full 2.7 m and roars (event 'Roar' at 0.9 s)
  Roar       2.0 s        swats the ground, roars with the head thrust out and swinging (event 'Roar' at 0.3 s)
  Hit        0.47 s       knocked back and to its left, forelegs buckling, a small rebound
  Death      2.0 s        sags, rolls onto its side, a last paw twitch (event 'Dead' at 1.6 s); holds the end
"""
import math
from mathutils import Vector, Matrix
import bear_body as BB
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, GALLOP

FPS = 30
SPEC = BA.Species(BB.rest_bones, (0.0, -0.05, 1.0), "Bear", "BearRig", neck_n=2, tail_n=len(BB.TAIL) - 1,
                  tongue=False)
LEGS = BA.LEGS
EVENTS = {"Swipe": [("Bite", 0.42)], "Bite": [("Bite", 0.4)], "Slam": [("Bite", 0.77)], "Hug": [("Bite", 0.73)],
          "Rear": [("Roar", 0.9)], "Roar": [("Roar", 0.3)], "Death": [("Dead", 1.6)]}
MOVING = {"Walk", "Run"}
HIP_PIVOT = Vector((0.0, 0.58, 0.98))       # rearing turns the trunk about the hip joints


def BearPose():
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


def _ears(p, fwd, splay=0.0, flickL=0.0, flickR=0.0):
    p.ears = {1: [fwd + flickL, splay], -1: [fwd + flickR, splay]}


def _flick(f, c, width=4.0, amp=-30.0):
    return amp * max(0.0, 1 - abs(f - c) / width)


def _tail(p, lift, swing=0.0, phase=0.0):
    for i in range(SPEC.tail_n):
        p.tail[i] = [lift, swing * math.sin(phase - 0.8 * i), 0.0]


def _stand(p, up, arms=(0.0, 0.55, 0.40), spread=0.0, head=1.0):
    """Rear up by `up` (0..1 of 75 degrees) about the hips: the forelegs ride with the chest, the neck and head pitch
    back down so the face looks ahead, the heels stay down. `arms` = the forepaws' offset in the trunk's own (standing)
    frame; reared, its +y points down and its +z back toward the chest, and with no offset the forelegs reach
    straight out in front. (0, 0.55, 0.40) lets them hang before the belly; 'spread' moves them out sideways."""
    pivot(p, 75.0 * up)
    p.hips = [-12 * up, 0, 0]
    p.spine[0][0] += 4 * up
    p.neck[0][0] += -26 * up * head
    p.neck[1][0] += -22 * up * head
    p.head[0] += -27 * up * head
    air = min(1.0, up * 3.0)
    for s in (1, -1):
        lp = LegPose(target=neutral(('F', s)), wb=air)
        lp.boff = Vector((s * spread, arms[1], arms[2])) * air + Vector((0, 0, 0))
        lp.flex = -40 * air
        lp.toe = -25 * air
        lp.scap = 10 * air
        p.legs[('F', s)] = lp
        p.legs[('H', s)] = LegPose(target=neutral(('H', s)), flex=-6 * up)


# ----------------------------------------------------------------------------------------- lying down
LIE_DROP = 0.50


def _lie(p, front, hind):
    """Lie on the belly, the forelegs stretched out in front, the hind legs folded under; 0 standing .. 1 lying."""
    p.body = p.body + Vector((0, 0, -LIE_DROP * (0.5 * front + 0.5 * hind)))
    p.pitch += 6.0 * (hind - front)
    for s in (1, -1):
        F0, H0 = neutral(('F', s)), neutral(('H', s))
        fl = LegPose(target=F0 + Vector((s * 0.02, -0.22, 0.02)) * front)
        fl.flex = 35 * front
        fl.toe = -10 * front
        fl.scap = 14 * front
        hl = LegPose(target=H0 + Vector((s * 0.08, -0.32, 0.04)) * hind)
        hl.flex = -20 * hind
        hl.toe = -15 * hind
        p.legs[('F', s)] = fl
        p.legs[('H', s)] = hl
    p.neck[0][0] += -6 * front
    p.head[0] += -10 * front


def _clip_sleep():
    N = 90

    def fn(f):
        p = BearPose()
        a = 2 * math.pi * f / N
        _lie(p, 1.0, 1.0)
        p.body += Vector((0, 0, 0.010 * math.sin(a)))
        p.spine[2][0] = 1.2 * math.sin(a)
        p.neck[0][1] = 5
        p.head[1] = 6
        p.head[2] = 8
        _ears(p, -12, 8, flickL=_flick(f, 61, 3, -35))
        return p
    return N, fn, True


def _clip_wake():
    N = 45

    def fn(f):
        p = BearPose()
        t = f / N
        front = 1 - ease(t / 0.55)
        hind = 1 - ease((t - 0.30) / 0.55)
        _lie(p, front, hind)
        p.body += Vector((0, K([(0, 0), (8, 0.05), (24, -0.03), (45, 0)], f), 0))
        shake = K([(0, 0), (30, 0), (33, 1), (36, -1), (39, 0.7), (42, -0.3), (45, 0)], f)
        p.head[2] += 20 * shake
        p.head[1] += 10 * shake
        p.neck[0][0] += K([(0, 0), (6, -4), (20, 8), (32, 0), (45, 0)], f)
        _ears(p, -12 * front, 8 * front + 12 * abs(shake))
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- idle and locomotion
def _clip_idle():
    N = 90

    def fn(f):
        p = BearPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 30                                         # three breaths a loop
        shift = K([(0, 0), (28, 0), (34, 1), (46, 1), (52, 0), (90, 0)], f)   # weight onto the right, the left forepaw
        p.body = Vector((0.015 * math.sin(a) - 0.035 * shift, 0, 0.007 * math.sin(b)))   # lifts and settles again
        p.roll = 1.5 * math.sin(a) - 2.5 * shift
        p.spine[2][0] = 1.0 * math.sin(b)
        sniff = K([(0, 0), (56, 0), (62, 1), (72, 1), (78, 0), (90, 0)], f)
        twitch = math.sin(2 * math.pi * f / 5) * sniff
        look = K([(0, 0), (10, 0), (18, 1), (26, 1), (34, 0), (90, 0)], f)  # a look round to its right
        p.neck[0] = [-3 + 6 * sniff + 2 * math.sin(a), 8 * math.sin(a + 0.6) - 14 * look, 0]
        p.head = [4 * sniff + 2 * twitch + 2 * math.sin(b + 1.0), 6 * math.sin(a + 0.9) - 12 * look, 3 * math.sin(a) - 4 * look]
        _ears(p, 4 + 10 * sniff, 4, flickL=_flick(f, 22), flickR=_flick(f, 84) + 18 * look)
        _tail(p, 0, 6, a)
        F0 = neutral(('F', 1))
        lift = K([(0, 0), (34, 0), (37, 1), (41, 0.6), (44, 0), (90, 0)], f)
        lp = LegPose(target=F0 + Vector((0.01, -0.03, 0.07)) * lift)
        lp.flex = -35 * lift
        lp.toe = 10 * lift
        p.legs[('F', 1)] = lp
        return p
    return N, fn, True


def _clip_walk():
    """A heavy, rolling walk: the head carried low and swinging opposite the shoulders."""
    N = 32

    def fn(f):
        p = BearPose()
        gait(p, f, N, 1.10, 0.68, 0.13, WALK, front_fold=70, hind_flex=-30, scap=12)
        a = 2 * math.pi * f / N
        p.body = Vector((0.022 * math.sin(a), 0, -0.016 - 0.016 * math.cos(2 * a)))
        p.roll = 4.0 * math.sin(a)                                       # the shoulders roll
        p.yaw = 2.0 * math.sin(a + 0.8)
        p.pitch = 1.0 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -2.2 * math.sin(a + 0.8)
        p.neck[0] = [-9 + 3 * math.sin(2 * a + 1.0), -4 * math.sin(a + 0.4), 0]
        p.neck[1][1] = -3 * math.sin(a + 0.6)
        p.head = [4 - 3 * math.sin(2 * a + 1.0), -6 * math.sin(a + 0.8), -3 * math.sin(a)]
        _ears(p, 3, 2)
        _tail(p, 0, 5, a)
        return p
    return N, fn, True


def _clip_run():
    N = 13

    def fn(f):
        p = BearPose()
        gait(p, f, N, 2.30, 0.30, 0.20, GALLOP, front_fold=85, hind_flex=-40, scap=20)
        a = 2 * math.pi * f / N
        gather = math.cos(a - 0.5)
        p.body = Vector((0, 0, -0.03 + 0.05 * math.sin(a - 1.2)))
        p.pitch = -2 + 3 * math.sin(a - 0.3)
        p.spine[0][0] = 8 * gather
        p.spine[2][0] = -7 * gather
        p.hips = [-10 * gather, 0, 0]
        p.neck[0][0] = -8 - 3 * math.sin(a - 0.3)
        p.head = [2 + 3 * math.sin(a - 0.3), 0, 0]
        _ears(p, -25, 0)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- attacks
def _clip_swipe():
    """A right-paw haymaker: weight onto the left side, the right forepaw drawn up and out, then raked across the
    front at chest height (event 'Bite' at 0.42 s) and down; the trunk and head turn into the blow."""
    N = 30

    def fn(f):
        p = BearPose()
        p.roll = K([(0, 0), (8, -6), (13, 3), (18, 4), (30, 0)], f)
        p.yaw = K([(0, 0), (8, -10), (13, 8), (17, 12), (30, 0)], f)
        pivot(p, K([(0, 0), (8, 12), (13, 9), (18, 4), (30, 0)], f))       # the shoulders lift into the blow
        p.body += Vector((K([(0, 0), (8, 0.07), (13, 0.02), (18, -0.03), (30, 0)], f),
                          K([(0, 0), (8, 0.05), (13, -0.10), (18, -0.08), (30, 0)], f), 0))
        turn = K([(0, 0), (8, -14), (13, 12), (17, 16), (30, 0)], f)
        p.neck[0] = [K([(0, 0), (8, 4), (13, -6), (30, 0)], f), turn * 0.5, 0]
        p.head = [K([(0, 0), (10, 6), (14, -4), (30, 0)], f), turn * 0.5, K([(0, 0), (12, -10), (18, -6), (30, 0)], f)]
        p.jaw = K([(0, 0), (6, 14), (12, 22), (18, 10), (30, 0)], f)
        _ears(p, K([(0, 0), (5, -35), (24, -35), (30, 0)], f), -4)
        F0 = neutral(('F', -1))
        path = [(0, F0), (4, F0 + Vector((-0.08, 0.04, 0.30))), (8, Vector((-0.66, -0.50, 1.02))),
                (11, Vector((-0.42, -1.00, 0.98))), (13, Vector((-0.04, -1.14, 0.88))), (16, Vector((0.26, -0.96, 0.58))),
                (21, Vector((0.08, -0.82, 0.18))), (26, F0 + Vector((0.02, -0.04, 0.02))), (30, F0)]
        tgt = Vector(K([(k, tuple(v)) for k, v in path], f))
        lp = LegPose(target=tgt)
        lp.flex = K([(0, 0), (6, -40), (11, -10), (14, 10), (20, -10), (26, -5), (30, 0)], f)
        lp.toe = K([(0, 0), (8, -10), (12, 25), (18, 10), (30, 0)], f)            # claws spread for the rake
        lp.scap = K([(0, 0), (8, -14), (13, 18), (18, 10), (30, 0)], f)
        p.legs[('F', -1)] = lp
        p.legs[('F', 1)].scap = K([(0, 0), (8, 6), (14, -4), (30, 0)], f)
        return p
    return N, fn, False


def _clip_bite():
    """Coils, lunges with the right forepaw stepping in, the head thrust out level with the jaws wide, snaps shut
    (event 'Bite' at 0.4 s), shakes its head, lets go and steps back."""
    N = 30

    def fn(f):
        p = BearPose()
        p.body = Vector((K([(0, 0), (7, 0.02), (12, -0.02), (22, -0.01), (30, 0)], f),
                         K([(0, 0), (7, 0.08), (11, -0.20), (14, -0.23), (21, -0.12), (30, 0)], f),
                         K([(0, 0), (7, -0.05), (11, 0.01), (14, -0.01), (22, -0.02), (30, 0)], f)))
        p.pitch = K([(0, 0), (7, -3), (11, 4), (14, 2), (22, 0), (30, 0)], f)
        n = K([(0, 0), (7, -8), (10, 10), (12, 6), (15, 2), (22, 0), (30, 0)], f)
        p.neck[0][0], p.neck[1][0] = n, 0.6 * n
        shake = K([(0, 0), (13, 0), (16, 14), (19, -12), (22, 8), (25, 0), (30, 0)], f)
        p.head = [K([(0, 0), (7, -6), (10, 20), (12, 10), (15, 4), (22, 0), (30, 0)], f), shake * 0.5, shake]
        p.jaw = K([(0, 0), (5, 6), (9, 34), (11, 36), (12.5, 3), (15, 4), (22, 2), (30, 0)], f)
        _ears(p, K([(0, 0), (6, -40), (24, -40), (30, 0)], f), 0)
        F0 = neutral(('F', -1))
        reach = Vector((0.0, -0.20, 0.0))
        path = [(0, F0), (6, F0 + Vector((0, -0.05, 0.10))), (11, F0 + reach), (21, F0 + reach),
                (25, F0 + Vector((0, -0.09, 0.08))), (30, F0)]
        lp = LegPose(target=Vector(K([(k, tuple(v)) for k, v in path], f)))
        lp.flex = K([(0, 0), (4, -35), (9, -10), (11, 0), (21, 0), (23, -30), (28, -8), (30, 0)], f)
        lp.scap = K([(0, 0), (7, -4), (11, 12), (21, 10), (30, 0)], f)
        p.legs[('F', -1)] = lp
        p.legs[('F', 1)].scap = K([(0, 0), (8, -6), (13, 8), (20, 4), (30, 0)], f)
        return p
    return N, fn, False


def _clip_slam():
    """Rears half way and crashes down on both forepaws (event 'Bite' at 0.77 s): the ground-pound."""
    N = 42

    def fn(f):
        p = BearPose()
        up = K([(0, 0), (6, 0.12), (14, 0.72), (19, 0.78), (22.5, 0.20), (23.5, -0.04), (27, -0.06), (42, 0)], f)
        _stand(p, max(up, 0.0), arms=(0, -0.20, 0.38), spread=0.10 * max(up, 0.0), head=0.6)
        if up < 0:                                                         # the crash: trunk and head driven down
            p.body += Vector((0, 0, 0.9 * up))
            p.pitch += 40 * up
        p.neck[0][0] += K([(0, 0), (16, 10), (23, -16), (30, -6), (42, 0)], f)
        p.head[0] += K([(0, 0), (16, 8), (23, -10), (42, 0)], f)
        p.jaw = 26 * K([(0, 0), (8, 0), (14, 1), (23, 1), (28, 0.3), (42, 0)], f)
        _ears(p, K([(0, 0), (8, -35), (36, -35), (42, 0)], f), 0)
        land = K([(0, 0), (21, 0), (23.5, 1), (42, 1)], f)
        if land > 0:                                                       # forepaws come down a little forward
            for s in (1, -1):
                lp = p.legs[('F', s)]
                lp.wb = lp.wb * (1 - land)
                lp.target = neutral(('F', s)) + Vector((s * 0.04, -0.14, 0)) * K([(0, 0), (23.5, 1), (34, 1), (42, 0)], f)
                lp.flex = lp.flex * (1 - land) + 15 * land * K([(0, 0), (24, 1), (34, 0), (42, 0)], f)
        return p
    return N, fn, False


def _clip_hug():
    """Rears up, throws its forelegs wide, crushes them shut round whatever is in front (event 'Bite' at 0.73 s),
    squeezes with a bite to the head, and drops back down."""
    N = 60

    def fn(f):
        p = BearPose()
        up = K([(0, 0), (12, 0.66), (40, 0.70), (52, 0.10), (60, 0)], f)
        spread = K([(0, 0), (10, 0.20), (17, 0.42), (22, 0.04), (40, 0.02), (50, 0.06), (60, 0)], f)
        ay = K([(0, 0.55), (12, 0.00), (17, -0.10), (22, 0.14), (40, 0.16), (52, 0.45), (60, 0.55)], f)
        az = K([(0, 0.40), (12, 0.30), (17, 0.30), (22, 0.22), (40, 0.22), (52, 0.38), (60, 0.40)], f)
        _stand(p, up, arms=(0, ay, az), spread=spread)
        squeeze = K([(0, 0), (21, 0), (23, 1), (40, 1), (44, 0), (60, 0)], f)
        p.spine[2][0] += -6 * squeeze
        p.neck[0][0] += 10 * squeeze
        p.head[0] += K([(0, 0), (20, 8), (26, -14), (34, -10), (40, 0), (60, 0)], f)
        p.jaw = K([(0, 0), (10, 10), (20, 34), (26, 6), (30, 30), (34, 4), (44, 6), (60, 0)], f)
        _ears(p, K([(0, 0), (8, -40), (48, -40), (60, 0)], f), 0)
        for s in (1, -1):
            lp = p.legs[('F', s)]
            lp.flex = -40 * lp.wb - 30 * squeeze
            lp.toe = -25 * lp.wb + 20 * squeeze
        return p
    return N, fn, False


def _clip_rear():
    """Stands up to its full height, forelegs raised, and roars down at you (event 'Roar' at 0.9 s)."""
    N = 81

    def fn(f):
        p = BearPose()
        up = K([(0, 0), (22, 1.0), (60, 1.0), (78, 0), (81, 0)], f)
        ay = K([(0, 0.55), (14, 0.30), (24, 0.20), (58, 0.20), (70, 0.38), (81, 0.55)], f)   # paws out at chest
        az = K([(0, 0.40), (24, 0.36), (58, 0.36), (81, 0.40)], f)                          # height, clear of
        spread = K([(0, 0), (24, 0.26), (58, 0.26), (70, 0.06), (81, 0)], f)                # the roaring face
        _stand(p, up, arms=(0, ay, az), spread=spread)
        for s in (1, -1):                                                  # paws up, claws spread
            p.legs[('F', s)].flex = -20 * up
            p.legs[('F', s)].toe = 15 * up
        sway = math.sin(2 * math.pi * f / 40) * up
        p.roll += 3 * sway
        roar = K([(0, 0), (24, 0), (27, 1), (52, 1), (57, 0), (81, 0)], f)
        p.neck[0][0] += 16 * roar                                          # roars upward, the jaw clear of the chest
        p.head[0] += 14 * roar
        p.head[2] += 4 * sway
        p.jaw = 38 * roar + 2 * math.sin(2 * math.pi * f / 6) * roar
        _ears(p, -30 * roar, 4)
        return p
    return N, fn, False


def _clip_roar():
    """Swats the ground with its right forepaw, thrusts its head out low and level and roars (event 'Roar' at 0.3 s),
    swinging its head from side to side."""
    N = 60

    def fn(f):
        p = BearPose()
        roar = K([(0, 0), (6, 0), (9, 1), (46, 1), (54, 0), (60, 0)], f)
        bob = K([(0, 0), (4, 0.03), (7, -0.04), (11, 0), (60, 0)], f)       # the swat
        p.body = Vector((0, -0.10 * roar, -0.04 * roar + bob))
        p.pitch = K([(0, 0), (4, 4), (7, -3), (11, 0), (60, 0)], f) - 2 * roar
        swing = math.sin(2 * math.pi * (f - 9) / 30) * roar
        p.neck[0] = [-14 * roar, 6 * swing, 0]
        p.neck[1] = [8 * roar, 4 * swing, 0]
        p.head = [30 * roar + K([(0, 0), (4, 6), (7, -6), (10, 0), (60, 0)], f), 8 * swing, 6 * swing]
        p.jaw = 31 * roar + 3 * math.sin(2 * math.pi * f / 5) * roar
        _ears(p, -40 * max(roar, K([(0, 0), (3, 1), (8, 1), (60, 0)], f)), 0)
        F0 = neutral(('F', -1))
        down = F0 + Vector((0, -0.06, 0))
        path = [(0, F0), (4, F0 + Vector((-0.02, -0.05, 0.18))), (7, down), (49, down),
                (53, F0 + Vector((0, -0.03, 0.06))), (57, F0), (60, F0)]
        lp = LegPose(target=Vector(K([(k, tuple(v)) for k, v in path], f)))
        lp.flex = K([(0, 0), (3, -45), (6, -5), (8, 3), (12, 0), (49, 0), (52, -25), (57, 0), (60, 0)], f)
        lp.toe = K([(0, 0), (4, 15), (7, 4), (12, 0), (60, 0)], f)
        lp.scap = K([(0, 0), (4, 10), (7, 4), (12, -6), (49, -6), (57, 0), (60, 0)], f)
        p.legs[('F', -1)] = lp
        p.legs[('F', 1)].scap = -6 * roar
        return p
    return N, fn, False


def _clip_hit():
    """Knocked back and to its left: the head snaps away, the body sags and rocks back (a small rebound)."""
    N = 14

    def fn(f):
        p = BearPose()
        k = K([(0, 0), (2, 1), (5, 0.85), (9, -0.20), (14, 0)], f)
        p.body = Vector((0.07 * k, 0.09 * k, -0.05 * max(k, 0)))
        p.roll, p.yaw, p.pitch = 8 * k, -10 * k, 3 * k
        p.spine[2] = [-4 * k, -6 * k, 0]
        p.neck[0] = [-10 * k, -12 * k, 0]
        p.head = [14 * k, -18 * k, 14 * k]
        p.jaw = K([(0, 0), (2, 24), (6, 8), (10, 2), (14, 0)], f)
        _ears(p, K([(0, 0), (1, -45), (9, -20), (14, 0)], f), 0)
        for s in (1, -1):                                                   # the forelegs buckle under the blow
            p.legs[('F', s)].flex = 14 * max(k, 0)
            p.legs[('F', s)].scap = -8 * k
        return p
    return N, fn, False


def _death_pose(f):
    p = BearPose()
    # sags, the front buckles, rolls onto its left side (it rests on its flank, centre ~0.5 m up)
    p.roll = K([(0, 0), (10, -4), (24, 20), (34, 56), (42, 82), (48, 78), (60, 80)], f)
    p.body = Vector((K([(0, 0), (10, -0.03), (34, 0.20), (42, 0.32), (60, 0.32)], f), K([(0, 0), (42, 0.05), (60, 0.05)], f),
                     K([(0, 0), (10, -0.05), (24, -0.12), (34, -0.27), (42, -0.47), (48, -0.42), (60, -0.425)], f)))
    p.pitch = K([(0, 0), (10, -6), (24, -8), (42, -2), (60, -2)], f)
    down = K([(0, 0), (30, 0), (46, 1), (60, 1)], f)
    p.neck[0] = [-6 * down + K([(0, 0), (6, 10), (16, -6), (30, 0)], f), 8 * down, 0]
    p.neck[1] = [-4 * down, 5 * down, 0]
    p.head = [-8 * down, 4 * down, 12 * down]
    p.jaw = K([(0, 0), (6, 20), (20, 12), (50, 10), (60, 9)], f)
    _ears(p, K([(0, 0), (4, -35), (60, -15)], f), 10 * down)
    wb = K([(0, 0), (16, 0), (34, 1), (60, 1)], f)
    twitch = K([(0, 0), (46, 0), (50, 1), (54, 0), (60, 0)], f)
    tuck = K([(0, 0), (14, 0), (24, 1), (36, 1), (44, 0.3), (60, 0.3)], f)   # the down forepaw draws in as it rolls
    for kind, s in LEGS:
        lp = LegPose(wb=wb)
        up_side = s < 0                                  # lying on its left side: the right legs are on top
        lp.boff = Vector((0.10 if up_side else 0.02 - (0.20 if kind == 'F' else 0.08) * tuck, (0.05 if kind == 'H' else -0.08) - 0.10 * twitch * (kind == 'F' and up_side),
                          0.03 if up_side else 0.10))
        lp.flex = (-25 if kind == 'F' else -10) * wb + (20 * twitch if kind == 'F' and up_side else 0)
        lp.toe = -20 * wb + (0 if up_side else 30 * tuck)
        p.legs[(kind, s)] = lp
    return p


def _clip_death():
    return 60, _death_pose, False


CLIPS = {"Sleep": _clip_sleep, "Wake": _clip_wake, "Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run,
         "Swipe": _clip_swipe, "Bite": _clip_bite, "Slam": _clip_slam, "Hug": _clip_hug, "Rear": _clip_rear,
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
