"""Wolf clips, keyed straight onto the rig (no constraints to bake), the way the insectoids' are.
The machinery (poses, leg IK, gaits, keying) is in beast_anim.py.

Every frame is a WolfPose: where the root is (it travels on the Motion bone; the skeleton plays in place), how the trunk
sits (offset, pitch, roll, yaw about BODY_C), per-bone bends of spine, neck, head, tail and ears, the jaw and tongue,
and per leg a paw target for the leg IK plus the pastern/hock flex, toe curl and (front) shoulder-blade swing.
`pose_matrices` turns that into armature-space bone matrices; beast_rig.apply_pose keys them.

Legs: the distal segment (front pastern / hind metatarsus) keeps its rest angle turned by `flex`; the two segments
above it are a 2-bone IK (elbow bends back, stifle forward) in the leg's hinge plane. Paw targets are on the ground
(absolute) or, with weight `wb`, carried by the trunk (in the air, lying dead).

Clips (30 fps, the wolf faces -Y; Unity +Z):
  Idle       4.0 s loop   breathing, looks around, ear flicks, tail sway
  IdlePant   3.0 s loop   panting, tongue out
  Walk       0.8 s loop   lateral-sequence walk, root motion 1.0 m/s
  Trot       0.53 s loop  diagonal trot, root motion 2.1 m/s
  Run        0.4 s loop   rotary gallop, spine flexing, root motion 5.5 m/s
  Bite       1.1 s        wind-up, snap (event 'Bite' at 0.47 s), head shake
  Lunge      1.5 s        crouch, leap 1.6 m, bite on landing (event 'Bite' at 0.87 s), root motion
  Threat     2.4 s        head low, ears pinned, jaw chattering, tail stiff
  Howl       3.5 s        nose to the sky (event 'Howl' at 0.8 s)
  Hit        0.5 s
  Death      2.2 s        staggers, collapses onto its side (event 'Dead' at 1.9 s)
  GetUp      1.5 s        from the Death end pose back to standing
"""
import math
from mathutils import Vector
import wolf_body as W
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, TROT, GALLOP

FPS = 30
SPEC = BA.Species(W.rest_bones, (0.0, 0.0, 0.66), "Wolf", "WolfRig", neck_n=2, tail_n=5, tongue=True)
LEGS = BA.LEGS
EVENTS = {"Bite": [("Bite", 0.47)], "Lunge": [("Bite", 0.87)], "Howl": [("Howl", 0.8)], "Death": [("Dead", 1.9)]}
MOVING = {"Walk", "Trot", "Run", "Lunge"}


def WolfPose():
    return BA.Pose(SPEC)


def neutral(key):
    return BA.neutral(SPEC, key)


def pose_matrices(p):
    return BA.pose_matrices(SPEC, p)


def gait(p, f, N, stride, duty, lift, phases, **kw):
    return BA.gait(SPEC, p, f, N, stride, duty, lift, phases, **kw)


def action_name(clip):
    return SPEC.action_name(clip)


# ----------------------------------------------------------------------------------------- clips
def _clip_walk():
    N = 24

    def fn(f):
        p = WolfPose()
        gait(p, f, N, 0.80, 0.62, 0.075, WALK)
        a = 2 * math.pi * f / N
        p.body = Vector((0.006 * math.sin(a), 0, -0.02 - 0.008 * math.cos(2 * a)))
        p.roll = 1.8 * math.sin(a)
        p.yaw = 2.0 * math.sin(a + 0.8)
        p.pitch = 0.8 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -1.5 * math.sin(a + 0.8)
        p.neck[0][0] = -4 + 2.0 * math.sin(2 * a + 1.0)
        p.head = [2 - 2.0 * math.sin(2 * a + 1.0), -2 * math.sin(a), 0]
        for i in range(5):
            p.tail[i] = [2 if i == 0 else 0, 6 * math.sin(a - 0.6 * i), 0]
        p.ears = {1: [3, 0], -1: [3, 0]}
        return p
    return N, fn, True


def _clip_trot():
    N = 16

    def fn(f):
        p = WolfPose()
        gait(p, f, N, 1.10, 0.42, 0.10, TROT, front_fold=105, hind_flex=45)
        a = 2 * math.pi * f / N
        p.body = Vector((0, 0, -0.03 - 0.014 * math.cos(2 * a)))
        p.roll = 1.2 * math.sin(a)
        p.pitch = -2 + 1.0 * math.sin(2 * a)
        p.neck[0][0] = -8 + 2.5 * math.sin(2 * a + 1.2)
        p.neck[1][0] = -4
        p.head = [4 - 2.5 * math.sin(2 * a + 1.2), 0, 0]
        for i in range(5):
            p.tail[i] = [8 if i == 0 else 2, 5 * math.sin(a - 0.7 * i), 0]
        p.ears = {1: [-6, 0], -1: [-6, 0]}
        return p
    return N, fn, True


def _clip_run():
    N = 12

    def fn(f):
        p = WolfPose()
        gait(p, f, N, 2.20, 0.30, 0.14, GALLOP, front_fold=110, hind_flex=55, scap=30)
        a = 2 * math.pi * f / N
        flexb = math.cos(a - 0.5)                      # + gathered (spine arched), - stretched
        p.body = Vector((0, 0, -0.04 + 0.035 * math.sin(a - 1.2)))
        p.pitch = -2 + 3 * math.sin(a - 0.3)
        p.spine[0][0] = 7 * flexb                      # the back arches (gathered) and flattens (stretched)
        p.spine[2][0] = -7 * flexb
        p.hips = [-9 * flexb, 0, 0]                    # pelvis tucks under when gathered
        p.neck[0][0] = -7 - 3 * math.sin(a - 0.3)
        p.neck[1][0] = -2
        p.head = [6 + 3 * math.sin(a - 0.3), 0, 0]
        p.jaw = 8
        p.tongue = [0.01, 10]
        for i in range(5):
            p.tail[i] = [22 if i == 0 else 3 - 2 * flexb, 3 * math.sin(a - 0.7 * i), 0]
        p.ears = {1: [-30, 0], -1: [-30, 0]}
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- idles
def _clip_idle():
    N = 120

    def fn(f):
        p = WolfPose()
        a = 2 * math.pi * f / N
        p.body = Vector((0.010 * math.sin(a), 0, 0.004 * math.sin(2 * a)))
        p.roll = 1.2 * math.sin(a)
        p.spine[2][0] = 0.8 * math.sin(2 * a)
        look = K([(0, 0), (22, 0), (36, 22), (58, 22), (72, -12), (98, -12), (112, 0), (120, 0)], f, N)
        p.neck[0] = [K([(0, 0), (36, 3), (72, -3), (112, 0), (120, 0)], f, N), look * 0.3, 0]
        p.neck[1] = [0, look * 0.3, 0]
        p.head = [K([(0, 0), (36, -4), (72, 4), (112, 0), (120, 0)], f, N), look * 0.4, 0]
        flick = lambda c: -30 * max(0.0, 1 - abs(f - c) / 4.0)
        p.ears = {1: [6 + flick(46), 0], -1: [6 + flick(94) + flick(100), 0]}
        for i in range(5):
            p.tail[i] = [0, 5 * math.sin(a - 0.5 * i), 0]
        return p
    return N, fn, True


def _clip_idle_pant():
    N = 90

    def fn(f):
        p = WolfPose()
        a = 2 * math.pi * f / N
        pa = 2 * math.pi * f / 9                         # 0.3 s pants
        p.body = Vector((0.006 * math.sin(a), 0, 0.003 * math.sin(pa)))
        p.spine[2][0] = 1.2 * math.sin(pa)
        p.neck[0] = [-3, 4 * math.sin(a), 0]
        p.head = [-4 + 1.5 * math.sin(pa + 0.8), 3 * math.sin(a), 0]
        p.jaw = 15 + 5 * math.sin(pa)
        p.tongue = [0.030 + 0.004 * math.sin(pa), 22]
        p.ears = {1: [-8, 6], -1: [-8, 6]}
        for i in range(5):
            p.tail[i] = [0, 4 * math.sin(a - 0.5 * i), 0]
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- actions
def _clip_bite():
    N = 33

    def fn(f):
        p = WolfPose()
        p.body = Vector((0, K([(0, 0), (9, 0.05), (13, -0.15), (16, -0.17), (24, -0.05), (33, 0)], f),
                         K([(0, 0), (9, -0.035), (14, -0.03), (24, -0.01), (33, 0)], f)))
        p.pitch = K([(0, 0), (9, 4), (14, -6), (24, -2), (33, 0)], f)
        n = K([(0, 0), (9, 10), (13, -12), (16, -14), (24, -4), (33, 0)], f)
        p.neck[0][0] = p.neck[1][0] = n
        shake = K([(0, 0), (16, 0), (19, 14), (22, -12), (25, 8), (28, 0), (33, 0)], f)
        p.head = [K([(0, 0), (9, 8), (13, -8), (16, -10), (33, 0)], f), shake * 0.6, shake]
        p.jaw = K([(0, 0), (8, 5), (11, 38), (13, 40), (14.5, 2), (16, 3), (33, 0)], f)
        e = K([(0, 0), (8, -35), (24, -35), (33, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        p.tail[0][0] = K([(0, 0), (9, 15), (24, 15), (33, 0)], f)
        sc = K([(0, 0), (9, -6), (14, 12), (22, 8), (33, 0)], f)
        for s in (1, -1):
            p.legs[('F', s)].scap = sc
        return p
    return N, fn, False


def _clip_lunge():
    N = 45
    TRAVEL = 1.6

    def fn(f):
        p = WolfPose()
        p.root = Vector((0, K([(0, 0), (10, 0), (14, -0.30), (25, -1.35), (30, -TRAVEL), (45, -TRAVEL)], f), 0))
        p.body = Vector((0, K([(0, 0), (10, 0.06), (14, 0), (45, 0)], f),
                         K([(0, 0), (10, -0.13), (13, -0.02), (19, 0.26), (25, 0.02), (28, -0.08), (40, 0), (45, 0)], f)))
        p.pitch = K([(0, 0), (10, -4), (13, 9), (19, 0), (24, -10), (28, -4), (45, 0)], f)
        for i in range(3):
            p.spine[i][0] = K([(0, 0), (10, 4), (15, -5), (22, -3), (26, 3), (45, 0)], f)
        n = K([(0, 0), (10, -6), (19, 4), (24, -6), (45, 0)], f)
        p.neck[0][0] = p.neck[1][0] = n
        p.head[0] = K([(0, 0), (10, 4), (19, -6), (24, -10), (32, 0), (45, 0)], f)
        p.jaw = K([(0, 0), (12, 10), (18, 40), (24, 42), (26, 3), (30, 5), (45, 0)], f)
        e = K([(0, 0), (8, -40), (34, -40), (45, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        p.tail[0][0] = K([(0, 0), (13, 22), (27, 22), (45, 0)], f)
        landed = f >= 20
        for s in (1, -1):
            front = LegPose(target=neutral(('F', s)) + Vector((0, -TRAVEL if landed else 0, 0)))
            front.wb = K([(0, 0), (9, 0), (12, 1), (23, 1), (25.5, 0), (45, 0)], f)
            front.boff = Vector((0, -0.22, 0.14))
            front.flex = K([(0, 0), (10, 0), (14, -60), (22, -20), (25, 0), (45, 0)], f)
            front.scap = K([(0, 0), (10, -8), (16, 26), (24, 18), (28, 0), (45, 0)], f)
            hind = LegPose(target=neutral(('H', s)) + Vector((0, -TRAVEL if landed else 0, 0)))
            hind.wb = K([(0, 0), (11, 0), (14, 1), (26, 1), (29, 0), (45, 0)], f)
            hind.boff = Vector((0, 0.20, 0.10))
            hind.flex = K([(0, 0), (12, -10), (18, 25), (26, 10), (29, 0), (45, 0)], f)
            p.legs[('F', s)] = front
            p.legs[('H', s)] = hind
        return p
    return N, fn, False


def _clip_threat():
    N = 72

    def fn(f):
        p = WolfPose()
        hold = K([(0, 0), (12, 1), (60, 1), (72, 0)], f)
        p.body = Vector((0, 0.05 * hold, -0.06 * hold))
        p.pitch = -6 * hold
        p.neck[0][0] = -16 * hold
        p.neck[1][0] = -8 * hold
        p.head = [-4 * hold, 4 * math.sin(2 * math.pi * f / 36) * hold, 0]
        p.jaw = (12 + 3 * math.sin(2 * math.pi * f / 6)) * hold
        p.ears = {1: [-48 * hold, -8 * hold], -1: [-48 * hold, -8 * hold]}
        p.tail[0][0] = 26 * hold
        for i in range(1, 5):
            p.tail[i][0] = -4 * hold
        p.hips[0] = -3 * hold
        return p
    return N, fn, False


def _clip_howl():
    N = 105

    def fn(f):
        p = WolfPose()
        up = K([(0, 0), (18, 1), (88, 1), (105, 0)], f)
        p.body = Vector((0, 0.03 * up, -0.05 * up))
        p.pitch = 7 * up
        p.hips[0] = -6 * up
        p.neck[0][0] = 28 * up
        p.neck[1][0] = 26 * up
        p.head[0] = 20 * up
        p.jaw = K([(0, 0), (18, 4), (24, 22), (80, 24), (88, 3), (105, 0)], f) + 2 * math.sin(2 * math.pi * f / 7) * up
        p.ears = {1: [-22 * up, 4 * up], -1: [-22 * up, 4 * up]}
        for i in range(5):
            p.tail[i][0] = -6 * up
        return p
    return N, fn, False


def _clip_hit():
    N = 15

    def fn(f):
        p = WolfPose()
        k = K([(0, 0), (3, 1), (15, 0)], f)
        p.body = Vector((0.05 * k, 0.03 * k, -0.02 * k))
        p.roll, p.yaw = 8 * k, -8 * k
        p.neck[0] = [-8 * k, -10 * k, 0]
        p.head = [0, -18 * k, 0]
        p.jaw = K([(0, 0), (3, 20), (8, 5), (15, 0)], f)
        e = K([(0, 0), (2, -40), (12, -20), (15, 0)], f)
        p.ears = {1: [e, 0], -1: [e, 0]}
        p.tail[0][0] = -15 * k
        return p
    return N, fn, False


def _death_pose(f):
    p = WolfPose()
    p.roll = K([(0, 0), (8, -5), (20, 18), (30, 55), (38, 88), (44, 85), (66, 88)], f)
    # the trunk comes down only as fast as it rolls onto its side (it rests on its flank at z ~0.16)
    p.body = Vector((K([(0, 0), (8, -0.03), (30, 0.14), (38, 0.20), (66, 0.20)], f), K([(0, 0), (38, 0.05), (66, 0.05)], f),
                     K([(0, 0), (8, -0.02), (20, -0.12), (30, -0.30), (38, -0.46), (44, -0.45), (66, -0.46)], f)))
    p.pitch = K([(0, 0), (8, 3), (24, -8), (40, -2), (66, -2)], f)
    down = K([(0, 0), (30, 0), (46, 1), (66, 1)], f)
    for i in range(2):
        p.neck[i] = [-4 * down, 4 * down + K([(0, 0), (4, -10), (14, 0)], f), 0]
    p.head = [-8 * down, 3 * down, 0]
    p.jaw = K([(0, 0), (4, 22), (20, 14), (50, 10), (66, 9)], f)
    p.tongue = [0.025 * down, 25 * down]
    e = K([(0, 0), (4, -40), (66, -25)], f)
    p.ears = {1: [e, 0], -1: [e, 0]}
    for i in range(5):
        p.tail[i] = [-4 * down, 12 * down, 0]
    wb = K([(0, 0), (16, 0), (32, 1), (66, 1)], f)
    for kind, s in LEGS:
        lp = LegPose(wb=wb)
        up_side = s < 0                                  # lying on its left side: the right legs are on top
        lp.boff = Vector((0.10 if up_side else 0.02, 0.04 if kind == 'H' else -0.03, 0.03))
        lp.flex = (-25 if kind == 'F' else 15) * wb
        lp.toe = -30 * wb
        p.legs[(kind, s)] = lp
    return p


def _clip_death():
    return 66, _death_pose, False


def _clip_getup():
    N = 45
    return N, (lambda f: _death_pose(42.0 * (1 - ease(f / N)))), False      # the collapse (Death 0-42) in reverse


CLIPS = {"Idle": _clip_idle, "IdlePant": _clip_idle_pant, "Walk": _clip_walk, "Trot": _clip_trot, "Run": _clip_run,
         "Bite": _clip_bite, "Lunge": _clip_lunge, "Threat": _clip_threat, "Howl": _clip_howl, "Hit": _clip_hit,
         "Death": _clip_death, "GetUp": _clip_getup}


# ----------------------------------------------------------------------------------------- build / export
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
