"""Giant rat clips, keyed straight onto the rig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py.

Clips (30 fps, the rat faces -Y; Unity +Z):
  Idle       3.0 s loop   sniffing in bursts, looks around, ear flicks, tail swish
  Rear       2.8 s        rears up on its hind legs, hands to the chest, sniffs the air
  Walk       0.53 s loop  scurry (lateral sequence), root motion 0.87 m/s
  Run        0.33 s loop  half-bound, spine flexing, root motion 2.7 m/s
  Bite       0.8 s        snap (event 'Bite' at 0.4 s)
  Lunge      1.2 s        crouch, leap 0.8 m, bite on landing (event 'Bite' at 0.73 s), root motion
  Threat     2.0 s        back arched, teeth bared, tail lashing, a front-foot stamp
  Hit        0.4 s
  Death      1.8 s        flips onto its back, legs curled up (event 'Dead' at 1.6 s)
  GetUp      1.1 s        rolls back over from the Death end pose
"""
import math
from mathutils import Vector, Matrix
import rat_body as RB
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, BOUND

FPS = 30
SPEC = BA.Species(RB.rest_bones, (0.0, 0.02, 0.30), "Rat", "RatRig", neck_n=2, tail_n=len(RB.TAIL) - 1, tongue=False,
                  tail_floor=[r + 0.002 for r in RB.TAIL_R[1:]])
LEGS = BA.LEGS
EVENTS = {"Bite": [("Bite", 0.4)], "Lunge": [("Bite", 0.73)], "Death": [("Dead", 1.6)]}
MOVING = {"Walk", "Run", "Lunge"}
HIP_PIVOT = Vector((0.0, 0.17, 0.20))      # rearing turns the trunk about the haunches


def RatPose():
    return BA.Pose(SPEC)


def neutral(key):
    return BA.neutral(SPEC, key)


def action_name(clip):
    return SPEC.action_name(clip)


def pivot(p, pitch, pv=HIP_PIVOT):
    """Pitch the trunk about pv instead of its centre (sets p.pitch and adds the matching offset to p.body)."""
    C = SPEC.body_c
    R = Matrix.Rotation(math.radians(-pitch), 3, 'X')
    p.pitch = pitch
    p.body = p.body + (pv - C) - R @ (pv - C)


def _tail_wave(p, amp, phase, lift=0.0, speed=1.0):
    for i in range(SPEC.tail_n):
        p.tail[i] = [lift if i == 0 else 0.0, amp * math.sin(phase - 0.7 * i * speed), 0.0]


# ----------------------------------------------------------------------------------------- locomotion
def _clip_walk():
    N = 16

    def fn(f):
        p = RatPose()
        BA.gait(SPEC, p, f, N, 0.46, 0.60, 0.035, WALK, front_fold=75, hind_flex=-28, scap=18)
        a = 2 * math.pi * f / N
        p.body = p.body + Vector((0.004 * math.sin(a), 0, -0.006 - 0.004 * math.cos(2 * a)))
        p.roll = 2.0 * math.sin(a)
        p.yaw = 3.0 * math.sin(a + 0.8)
        for i in range(3):
            p.spine[i][1] = -2.5 * math.sin(a + 0.8)
        p.neck[0][0] = -2 + 1.5 * math.sin(2 * a + 1.0)
        p.head = [1.5 * math.sin(4 * a), -4 * math.sin(a), 0]           # nose bobs while it scurries
        _tail_wave(p, 7, a, lift=4)
        return p
    return N, fn, True


def _clip_run():
    N = 10

    def fn(f):
        p = RatPose()
        BA.gait(SPEC, p, f, N, 0.90, 0.35, 0.07, BOUND, front_fold=95, hind_flex=-45, scap=26)
        a = 2 * math.pi * f / N
        flexb = math.cos(a - 0.4)                      # + gathered (back humped), - stretched
        p.body = p.body + Vector((0, 0, -0.01 + 0.02 * math.sin(a - 1.0)))
        p.pitch = 4 * math.sin(a - 0.2)
        p.spine[0][0] = 10 * flexb
        p.spine[2][0] = -10 * flexb
        p.hips = [-12 * flexb, 0, 0]
        p.neck[0][0] = -6 - 3 * math.sin(a - 0.2)
        p.head = [4 + 3 * math.sin(a - 0.2), 0, 0]
        p.ears = {1: [-25, 0], -1: [-25, 0]}
        _tail_wave(p, 4, a, lift=10)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- idles
def _clip_idle():
    N = 90

    def fn(f):
        p = RatPose()
        a = 2 * math.pi * f / N
        p.body = Vector((0.006 * math.sin(a), 0, 0.002 * math.sin(2 * math.pi * f / 15)))
        burst = K([(0, 1), (28, 1), (36, 0), (58, 0), (64, 1), (84, 1), (90, 1)], f, N)
        sniff = burst * math.sin(2 * math.pi * f / 5)
        look = K([(0, 0), (20, 0), (32, 25), (56, 25), (66, -15), (84, -15), (90, 0)], f, N)
        p.neck[0] = [2 + 1.2 * sniff, look * 0.3, 0]
        p.neck[1] = [0, look * 0.3, 0]
        p.head = [2.5 * sniff + K([(0, 4), (32, -2), (66, 6), (90, 4)], f, N), look * 0.4, 0]
        flick = lambda c: -28 * max(0.0, 1 - abs(f - c) / 3.0)
        p.ears = {1: [4 + flick(40), 0], -1: [4 + flick(74), 0]}
        _tail_wave(p, 5, a, lift=0)
        return p
    return N, fn, True


def _clip_rear():
    N = 84

    def fn(f):
        p = RatPose()
        up = K([(0, 0), (18, 1), (66, 1), (84, 0)], f)
        pivot(p, 52 * up)
        sniff = up * math.sin(2 * math.pi * f / 5) * K([(0, 0), (20, 0), (24, 1), (60, 1), (64, 0), (84, 0)], f)
        look = K([(0, 0), (24, 0), (36, 20), (50, -20), (62, 0), (84, 0)], f)
        p.neck[0] = [-16 * up + 1.5 * sniff, look * 0.4, 0]
        p.neck[1] = [-10 * up, look * 0.3, 0]
        p.head = [-8 * up + 2.5 * sniff, look * 0.4, 0]
        p.spine[0][0] = 6 * up
        p.ears = {1: [8 * up, 4 * up], -1: [8 * up, 4 * up]}
        p.tail[0] = [45 * up, 0, 0]                                       # the tail stays on the ground
        p.tail[1] = [8 * up, 0, 0]
        for s in (1, -1):
            lp = LegPose(wb=K([(0, 0), (8, 0), (16, 1), (68, 1), (78, 0), (84, 0)], f))
            lp.boff = Vector((-0.02 * s, -0.06, 0.07))                      # hands held up before the chest
            lp.flex = -55 * up
            lp.toe = -30 * up
            lp.scap = 10 * up
            p.legs[('F', s)] = lp
            p.legs[('H', s)] = LegPose(flex=-22 * up)                    # heels lift a little
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- actions
def _clip_bite():
    N = 24

    def fn(f):
        p = RatPose()
        p.body = Vector((0, K([(0, 0), (6, 0.03), (11, -0.09), (14, -0.10), (20, -0.02), (24, 0)], f),
                         K([(0, 0), (6, -0.02), (12, 0.0), (24, 0)], f)))
        p.pitch = K([(0, 0), (6, 3), (11, -4), (24, 0)], f)
        n = K([(0, 0), (6, 8), (10, -10), (14, -12), (20, -3), (24, 0)], f)
        p.neck[0][0] = p.neck[1][0] = n
        shake = K([(0, 0), (13, 0), (15, 12), (17, -10), (19, 6), (21, 0), (24, 0)], f)
        p.head = [K([(0, 0), (6, 6), (10, -6), (14, -8), (24, 0)], f), shake * 0.5, shake]
        p.jaw = K([(0, 0), (6, 4), (9, 34), (11, 36), (12, 2), (13, 3), (24, 0)], f)
        e = K([(0, 0), (5, -35), (20, -35), (24, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        sc = K([(0, 0), (6, -6), (11, 14), (18, 8), (24, 0)], f)
        for s in (1, -1):
            p.legs[('F', s)].scap = sc
        _tail_wave(p, 10, f * 0.5)
        return p
    return N, fn, False


def _clip_lunge():
    N = 36
    TRAVEL = 0.8

    def fn(f):
        p = RatPose()
        p.root = Vector((0, K([(0, 0), (8, 0), (11, -0.15), (20, -0.68), (24, -TRAVEL), (36, -TRAVEL)], f), 0))
        p.body = Vector((0, K([(0, 0), (8, 0.04), (11, 0), (36, 0)], f),
                         K([(0, 0), (8, -0.07), (11, -0.01), (15, 0.14), (20, 0.01), (23, -0.04), (32, 0), (36, 0)], f)))
        p.pitch = K([(0, 0), (8, -3), (11, 8), (15, 0), (19, -9), (23, -3), (36, 0)], f)
        for i in range(3):
            p.spine[i][0] = K([(0, 0), (8, 5), (12, -5), (18, -3), (21, 4), (36, 0)], f)
        n = K([(0, 0), (8, -5), (15, 4), (19, -6), (36, 0)], f)
        p.neck[0][0] = p.neck[1][0] = n
        p.jaw = K([(0, 0), (10, 8), (15, 38), (20, 40), (22, 2), (25, 4), (36, 0)], f)
        e = K([(0, 0), (6, -40), (28, -40), (36, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        _tail_wave(p, 6, f * 0.4, lift=K([(0, 0), (11, 20), (22, 20), (36, 0)], f))
        landed = f >= 16
        for s in (1, -1):
            front = LegPose(target=neutral(('F', s)) + Vector((0, -TRAVEL if landed else 0, 0)))
            front.wb = K([(0, 0), (7, 0), (10, 1), (19, 1), (21, 0), (36, 0)], f)
            front.boff = Vector((0, -0.12, 0.07))
            front.flex = K([(0, 0), (8, 0), (11, -50), (18, -15), (21, 0), (36, 0)], f)
            front.scap = K([(0, 0), (8, -6), (13, 22), (19, 15), (23, 0), (36, 0)], f)
            hind = LegPose(target=neutral(('H', s)) + Vector((0, -TRAVEL if landed else 0, 0)))
            hind.wb = K([(0, 0), (9, 0), (11, 1), (21, 1), (24, 0), (36, 0)], f)
            hind.boff = Vector((0, 0.10, 0.04))
            hind.flex = K([(0, 0), (9, -30), (14, -10), (21, 0), (36, 0)], f)
            p.legs[('F', s)] = front
            p.legs[('H', s)] = hind
        return p
    return N, fn, False


def _clip_threat():
    N = 60

    def fn(f):
        p = RatPose()
        h = K([(0, 0), (10, 1), (50, 1), (60, 0)], f)
        p.body = Vector((0, 0.03 * h, 0.035 * h))
        p.spine[0][0] = 14 * h                                            # the back humps up
        p.spine[2][0] = -12 * h
        p.hips[0] = -10 * h
        p.neck[0][0] = -10 * h
        p.neck[1][0] = -6 * h
        p.head = [4 * h, 6 * math.sin(2 * math.pi * f / 30) * h, 0]
        p.jaw = (28 + 4 * math.sin(2 * math.pi * f / 6)) * h                # hissing, incisors bared
        p.ears = {1: [-45 * h, -6 * h], -1: [-45 * h, -6 * h]}
        _tail_wave(p, 22 * h, 2 * math.pi * f / 12, lift=12 * h)          # tail lashing
        stamp = K([(0, 0), (26, 0), (30, 1), (33, 0), (60, 0)], f)
        p.legs[('F', 1)] = LegPose(target=neutral(('F', 1)) + Vector((0, -0.02, 0.06 * stamp)), flex=-30 * stamp)
        return p
    return N, fn, False


def _clip_hit():
    N = 12

    def fn(f):
        p = RatPose()
        k = K([(0, 0), (3, 1), (12, 0)], f)
        p.body = Vector((0.03 * k, 0.03 * k, -0.01 * k))
        p.roll, p.yaw = 9 * k, -10 * k
        p.neck[0] = [-6 * k, -12 * k, 0]
        p.head = [0, -16 * k, 0]
        p.jaw = K([(0, 0), (3, 22), (7, 5), (12, 0)], f)
        e = K([(0, 0), (2, -40), (10, -20), (12, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        _tail_wave(p, 18 * k, f * 0.9)
        return p
    return N, fn, False


def _death_pose(f):
    p = RatPose()
    # flips onto its back (it rests on its back at a centre height of ~0.15 m; on its side also ~0.15)
    p.roll = K([(0, 0), (8, -12), (22, 90), (34, 176), (40, 168), (54, 172)], f)
    p.body = Vector((K([(0, 0), (22, 0.10), (34, 0.06), (54, 0.06)], f), 0,
                     K([(0, 0), (8, 0.01), (22, -0.145), (34, -0.110), (40, -0.105), (54, -0.110)], f)))
    d = K([(0, 0), (22, 0), (38, 1), (54, 1)], f)
    p.neck[0] = [-4 * d, 10 * d + K([(0, 0), (4, -10), (12, 0)], f), 0]
    p.neck[1] = [-4 * d, 8 * d, 0]
    p.head = [-8 * d, 6 * d, 12 * d]
    p.jaw = K([(0, 0), (4, 24), (18, 14), (40, 12), (54, 10)], f)
    e = K([(0, 0), (4, -40), (54, -20)], f)
    p.ears = {1: [e, 0], -1: [e, 0]}
    for i in range(SPEC.tail_n):     # upside down, + pitch bends the tail toward the ground (it drags on it)
        p.tail[i] = [(24 if i == 0 else 14) * d, 8 * d * (1 if i % 2 else -0.5), 0]
    wb = K([(0, 0), (10, 0), (24, 1), (54, 1)], f)
    kick = K([(0, 0), (40, 0), (44, 1), (48, 0), (54, 0)], f)
    for kind, s in LEGS:
        lp = LegPose(wb=wb)
        lp.boff = Vector((0, -0.03 if kind == 'F' else 0.03, 0.07 * wb + 0.03 * kick * (kind == 'H')))   # curled up
        lp.flex = (-60 if kind == 'F' else -40) * wb
        lp.toe = -35 * wb
        p.legs[(kind, s)] = lp
    return p


def _clip_death():
    return 54, _death_pose, False


def _clip_getup():
    N = 33
    return N, (lambda f: _death_pose(34.0 * (1 - ease(f / N)))), False      # the flip (Death 0-34) in reverse


CLIPS = {"Idle": _clip_idle, "Rear": _clip_rear, "Walk": _clip_walk, "Run": _clip_run, "Bite": _clip_bite,
         "Lunge": _clip_lunge, "Threat": _clip_threat, "Hit": _clip_hit, "Death": _clip_death, "GetUp": _clip_getup}


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
