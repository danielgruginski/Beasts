"""Woolly mammoth clips, keyed straight onto the rig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py.

A huge, slow beast: a lateral-sequence walk with the trunk swinging like a pendulum, an elephant's fast amble for the
run (no suspension: elephants never gallop), and a head-down charge with the trunk tucked under the chin. The trunk
is a six-bone chain (Pose.trunk): + pitch curls it toward its front (raised up for the trumpet), - curls it back
under the chin (the charge, bringing grass to the mouth).

Clips (30 fps, the mammoth faces -Y; Unity +Z):
  Sleep      4.0 s loop   lying on its belly, legs folded, the trunk curled on the ground, slow breathing
  Wake       2.0 s        heaves up front end first, shakes its head, ends in the Idle stance
  Idle       3.0 s loop   breathing, the trunk swaying and sniffing, ear flaps, tail swish, weight shifting
  Walk       1.6 s loop   lateral-sequence walk, root motion 1.4 m/s
  Run        0.8 s loop   amble, root motion 4.5 m/s
  Charge     0.67 s loop  head down, tusks levelled, trunk tucked, root motion 6.3 m/s
  Trumpet    2.0 s        stamps, rears its head with the trunk raised high and trumpets (event 'Roar' at 0.6 s)
  TuskSwipe  1.2 s        winds up to its left and sweeps its tusks through to the right, hooking up (event 'Bite'
                          at 0.5 s)
  Stomp      1.6 s        rears its front end up and slams both forefeet down (event 'Bite' at 1.03 s)
  Graze      4.0 s loop   the trunk reaches to the ground, grips, curls the grass up to its mouth, it chews
  Hit        0.5 s        a flinch
  Death      2.5 s        staggers, the forelegs buckle, sinks onto its belly and slumps to its right, the trunk
                          lying on the ground (event 'Dead' at 2.2 s); holds the end
"""
import math
from mathutils import Vector, Matrix
import mammoth_body as MB
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK

FPS = 30
SPEC = BA.Species(MB.rest_bones, (0.0, -0.20, 2.00), "Mammoth", "MammothRig", neck_n=2, tail_n=len(MB.TAIL) - 1,
                  tongue=False, trunk_n=len(MB.TRUNK_ROWS) - 1)
LEGS = BA.LEGS
EVENTS = {"Trumpet": [("Roar", 0.6)], "TuskSwipe": [("Bite", 0.5)], "Stomp": [("Bite", 1.03)],
          "Death": [("Dead", 2.2)]}
MOVING = {"Walk", "Run", "Charge"}
HIP_PIVOT = Vector((0.0, 0.85, 2.00))       # rearing turns the trunk about the hips
TN = SPEC.trunk_n


def MammothPose():
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
        p.tail[i] = [lift if i == 0 else lift * 0.4, swing * math.sin(phase - 0.8 * i), 0.0]


def _ears(p, fwd, splay=0.0, flapL=0.0, flapR=0.0):
    """fwd: + forward / - pinned back; splay: + out from the head (a flap adds to it)."""
    p.ears = {1: [fwd, splay + flapL], -1: [fwd, splay + flapR]}


def _bump(f, c, width):
    return max(0.0, 1 - abs(f - c) / width)


# the trunk's shapes, per bone (pitch; + curls toward its front)
HANG = [0, 0, 2, 4, 6, 8]                       # hanging, the tip turned out a little
RAISED = [36, 36, 32, 26, 18, 10]               # up in front of the face (trumpeting)
TUCKED = [-6, -18, -28, -34, -30, -20]          # curled back under the chin (charging)
TO_MOUTH = [-4, -24, -58, -64, -52, -40]        # curled back and up to the lips (eating)
REACH = [10, 8, 4, -2, -12, -22]                # swung forward, the tip down on the ground ahead
ON_GROUND = [12, 32, 36, 16, 2, -6]             # lying: forward along the ground


def _trunk(p, shape, sway=0.0, phase=0.0, lag=0.55, extra=None):
    """Set the trunk to a shape (per-bone pitches), plus a sideways sway travelling down it."""
    for i in range(TN):
        e = extra[i] if extra is not None else 0.0
        p.trunk[i] = [shape[i] + e, sway * math.sin(phase - lag * i) * (0.6 + 0.1 * i), 0.0]


def _mix(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


# ----------------------------------------------------------------------------------------- lying down
LIE_DROP = 0.95                             # how far the trunk sinks: belly near the ground, the coat spread


def _lie(p, front, hind):
    """Fold the legs under and sink the trunk; front / hind = 0 (standing) .. 1 (lying). The front end rising first
    tilts the trunk nose-up. The forelegs kneel on the wrists, the hind legs fold forward."""
    p.body = p.body + Vector((0, 0, -LIE_DROP * (0.5 * front + 0.5 * hind)))
    p.pitch += 8.0 * (hind - front)
    for s in (1, -1):
        F0, H0 = neutral(('F', s)), neutral(('H', s))
        fl = LegPose(target=F0 + Vector((s * 0.04, 0.40, 0.06)) * front)
        fl.flex = -95 * front
        fl.toe = -20 * front
        fl.scap = -8 * front
        hl = LegPose(target=H0 + Vector((s * 0.08, -0.55, 0.06)) * hind)
        hl.flex = 60 * hind
        hl.toe = -20 * hind
        p.legs[('F', s)] = fl
        p.legs[('H', s)] = hl


def _clip_sleep():
    N = 120

    def fn(f):
        p = MammothPose()
        a = 2 * math.pi * f / N
        _lie(p, 1.0, 1.0)
        p.body += Vector((0, 0, 0.014 * math.sin(a)))                     # slow breathing
        p.spine[2][0] = 1.0 * math.sin(a)
        p.neck[0] = [-4, 4, 0]
        p.head = [6, 4, 4]
        _trunk(p, ON_GROUND, 3, a)
        _ears(p, -6, -4, flapR=12 * _bump(f, 80, 5))
        _tail(p, -10, 3, a)
        return p
    return N, fn, True


def _clip_wake():
    N = 60

    def fn(f):
        p = MammothPose()
        t = f / N
        front = 1 - ease(t / 0.55)
        hind = 1 - ease((t - 0.30) / 0.55)
        _lie(p, front, hind)
        p.body += Vector((0, K([(0, 0), (10, 0.08), (32, -0.04), (60, 0)], f), 0))
        shake = K([(0, 0), (40, 0), (44, 1), (48, -1), (52, 0.7), (56, -0.3), (60, 0)], f)
        p.neck[0] = [K([(0, -4), (8, -8), (26, 6), (42, 0), (60, 0)], f), 4 * front, 0]
        p.head = [6 * front, 4 * front + 8 * shake, 4 * front + 12 * shake]
        _trunk(p, _mix(HANG, ON_GROUND, K([(0, 1), (18, 1), (42, 0), (60, 0)], f)), 14 * abs(shake) + 3, f * 0.6)
        _ears(p, -6 * front, -4 * front + 20 * abs(shake))
        _tail(p, K([(0, -10), (30, 6), (60, 0)], f), 8 * shake)
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- idle and locomotion
def _clip_idle():
    N = 90

    def fn(f):
        p = MammothPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 45                                         # two slow breaths a loop
        p.body = Vector((0.014 * math.sin(a), 0, 0.008 * math.sin(b)))
        p.roll = 1.0 * math.sin(a)
        p.spine[2][0] = 0.6 * math.sin(b)
        p.neck[0] = [1.5 * math.sin(a + 0.5), 3 * math.sin(a + 0.6), 0]
        sniff = K([(0, 0), (48, 0), (56, 1), (70, 1), (78, 0), (90, 0)], f)
        p.head = [1.5 * math.sin(b + 1.0) + 3 * sniff, 4 * math.sin(a + 0.9), 1.5 * math.sin(a)]
        twitch = math.sin(2 * math.pi * f / 7) * sniff
        curl = [4, 10, 16, 22, 26, 24]
        _trunk(p, HANG, 5, a, extra=[c * sniff + (3 * twitch if i > 3 else 0) for i, c in enumerate(curl)])
        _ears(p, 2, 4, flapL=26 * _bump(f, 22, 8), flapR=26 * _bump(f, 70, 8))
        _tail(p, 0, 12, 2 * a)
        return p
    return N, fn, True


def _clip_walk():
    N = 48

    def fn(f):
        p = MammothPose()
        gait(p, f, N, 2.20, 0.66, 0.20, WALK, front_fold=55, hind_flex=30, scap=10)
        a = 2 * math.pi * f / N
        p.body = Vector((0.030 * math.sin(a), 0, -0.020 - 0.020 * math.cos(2 * a)))
        p.roll = 2.0 * math.sin(a)
        p.yaw = 1.5 * math.sin(a + 0.8)
        p.pitch = 0.6 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -1.0 * math.sin(a + 0.8)
        p.neck[0] = [-1 + 2 * math.sin(2 * a + 1.0), -2 * math.sin(a + 0.4), 0]
        p.head = [1 - 2 * math.sin(2 * a + 1.0), -3 * math.sin(a), 0]
        swing = [3 * math.sin(2 * a - 0.5 - 0.4 * i) for i in range(TN)]       # forward and back with the steps
        _trunk(p, HANG, 7, a - 0.6, extra=swing)
        _ears(p, 2, 6 + 4 * math.sin(2 * a))
        _tail(p, 0, 10, a)
        return p
    return N, fn, True


def _clip_run():
    """An elephant's amble: the walk's footfalls, faster and with less ground contact, never all feet off."""
    N = 24

    def fn(f):
        p = MammothPose()
        gait(p, f, N, 3.60, 0.48, 0.28, WALK, front_fold=70, hind_flex=40, scap=16)
        a = 2 * math.pi * f / N
        p.body = Vector((0.025 * math.sin(a), 0, -0.04 - 0.035 * math.cos(2 * a)))
        p.roll = 2.5 * math.sin(a)
        p.pitch = -1 + 1.0 * math.sin(2 * a)
        p.neck[0] = [-2 + 2.5 * math.sin(2 * a + 1.2), -2 * math.sin(a), 0]
        p.head = [-2 - 2.5 * math.sin(2 * a + 1.2), -3 * math.sin(a), 0]
        swing = [4 + 5 * math.sin(2 * a - 0.8 - 0.4 * i) for i in range(TN)]
        _trunk(p, HANG, 10, a - 0.7, extra=swing)
        _ears(p, 6, 16 + 6 * math.sin(2 * a))
        _tail(p, 20, 8, a)
        return p
    return N, fn, True


def _clip_charge():
    """Head down with the tusks levelled ahead, the trunk curled under the chin out of harm's way, ears pinned."""
    N = 20

    def fn(f):
        p = MammothPose()
        gait(p, f, N, 4.20, 0.42, 0.30, WALK, front_fold=75, hind_flex=45, scap=18)
        a = 2 * math.pi * f / N
        bob = 1.5 * math.sin(2 * a - 0.3)
        p.body = Vector((0.02 * math.sin(a), 0, -0.06 - 0.04 * math.cos(2 * a)))
        p.roll = 2.0 * math.sin(a)
        p.pitch = -3 + bob
        p.neck[0] = [-8 - bob * 0.6, -1.5 * math.sin(a), 0]           # the neck takes up the heave
        p.neck[1] = [-4 - bob * 0.4, 0, 0]
        p.head = [-8, 0, 0]
        _trunk(p, TUCKED, 3, a, extra=[2 * math.sin(2 * a - 0.5 * i) for i in range(TN)])
        _ears(p, -30, -10)
        _tail(p, 35, 6, a)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- attacks and displays
def _clip_trumpet():
    """Stamps its right forefoot, raises its head and curls the trunk high, ears flared, and trumpets (event 'Roar'
    at 0.6 s)."""
    N = 60

    def fn(f):
        p = MammothPose()
        up = K([(0, 0), (14, 1), (46, 1), (60, 0)], f)
        lift = K([(0, 0), (18, 1), (44, 1), (58, 0)], f)                 # the trunk follows the head
        blast = K([(0, 0), (16, 0), (19, 1), (42, 1), (46, 0), (60, 0)], f)
        pivot(p, 6 * up)
        p.hips = [-3 * up, 0, 0]
        p.neck[0][0] = 10 * up
        p.neck[1][0] = 8 * up
        tremble = math.sin(2 * math.pi * f / 4) * blast
        p.head = [14 * up + 1.5 * tremble, 3 * math.sin(2 * math.pi * f / 30) * up, 0]
        p.jaw = 16 * blast
        _trunk(p, _mix(HANG, RAISED, lift), 0, 0, extra=[0, 0, 0, 2 * tremble, 4 * tremble, 6 * tremble])
        _ears(p, 18 * up, 36 * up)
        _tail(p, 25 * up, 0)
        F0 = neutral(('F', -1))                                           # the stamp
        path = [(0, F0), (5, F0 + Vector((0, -0.06, 0.32))), (9, F0 + Vector((0, -0.10, 0))), (60, F0 + Vector((0, -0.10, 0)))]
        lp = LegPose(target=Vector(K([(k, tuple(v)) for k, v in path], f)))
        lp.flex = K([(0, 0), (4, -50), (8, -5), (11, 0), (60, 0)], f)
        lp.scap = K([(0, 0), (5, 8), (9, 4), (60, 4)], f)
        p.legs[('F', -1)] = lp
        return p
    return N, fn, False


def _clip_tuskswipe():
    """Weight onto its right, the head wound up to its left; then the head sweeps hard across to the right with
    the right forefoot stepping in, the tusks hooking up through the target (event 'Bite' at 0.5 s), and back."""
    N = 36

    def fn(f):
        p = MammothPose()
        yaw = K([(0, 0), (10, 20), (13.5, 2), (16, -26), (20, -30), (27, -14), (36, 0)], f)   # + = to its left
        p.body = Vector((K([(0, 0), (10, -0.06), (15, 0.04), (22, 0.04), (36, 0)], f),
                         K([(0, 0), (10, 0.10), (15, -0.18), (22, -0.12), (36, 0)], f),
                         K([(0, 0), (10, -0.03), (15, 0.02), (36, 0)], f)))
        p.yaw = 0.25 * yaw
        p.roll = K([(0, 0), (10, -3), (15, 3), (22, 2), (36, 0)], f)
        p.neck[0] = [K([(0, 0), (10, 4), (14, -6), (17, 6), (36, 0)], f), 0.35 * yaw, 0]
        p.neck[1] = [0, 0.25 * yaw, 0]
        p.head = [K([(0, 0), (10, 8), (14, -10), (17, 14), (22, 10), (36, 0)], f), 0.4 * yaw,
                  K([(0, 0), (10, 6), (16, -12), (24, -6), (36, 0)], f)]
        lagy = K([(0, 0), (12, 14), (16, 8), (19, -16), (26, -10), (36, 0)], f)        # the trunk swings after it
        _trunk(p, _mix(HANG, TUCKED, K([(0, 0), (8, 0.6), (24, 0.6), (36, 0)], f)))
        for i in range(TN):
            p.trunk[i][1] = lagy * (0.4 + 0.15 * i)
        _ears(p, K([(0, 0), (6, -25), (28, -25), (36, 0)], f), -6)
        _tail(p, K([(0, 0), (8, 20), (28, 20), (36, 0)], f), 0)
        step = K([(0, 0), (10, 0), (14, 1), (26, 1), (32, 0), (36, 0)], f)
        upf = K([(0, 0), (10, 0), (12, 1), (14, 0), (26, 0), (29, 1), (32, 0), (36, 0)], f)
        F0 = neutral(('F', -1))
        lp = LegPose(target=F0 + Vector((-0.08 * step, -0.32 * step, 0.20 * upf)))
        lp.flex = -55 * upf
        lp.scap = 10 * step
        p.legs[('F', -1)] = lp
        return p
    return N, fn, False


def _clip_stomp():
    """Rears its front end high on the hind legs, trunk up, and slams both forefeet down (event 'Bite' at 1.03 s)."""
    N = 48

    def fn(f):
        p = MammothPose()
        up = K([(0, 0), (8, 0.12), (20, 0.90), (26, 1.0), (29.5, 0.45), (31, -0.07), (34, -0.09), (48, 0)], f)
        pivot(p, 20 * max(up, 0) + 6 * min(up, 0))
        p.body += Vector((0, 0.06 * max(up, 0), 0.10 * min(up, 0)))
        p.hips = [-5 * max(up, 0), 0, 0]
        crash = K([(0, 0), (29, 0), (31, 1), (36, 0.6), (48, 0)], f)
        p.neck[0][0] = 8 * max(up, 0) - 10 * crash
        p.head = [10 * max(up, 0) - 6 * crash, 0, 0]
        p.jaw = 12 * K([(0, 0), (12, 0), (20, 1), (27, 1), (30, 0), (48, 0)], f)
        _trunk(p, _mix(HANG, RAISED, 0.75 * K([(0, 0), (8, 0), (22, 1), (28, 1), (32, 0), (48, 0)], f)),
               0, 0, extra=[2 * crash, 10 * crash, 14 * crash, 14 * crash, 12 * crash, 8 * crash])
        _ears(p, K([(0, 0), (10, 15), (28, 15), (31, -20), (40, 0), (48, 0)], f),
              K([(0, 0), (10, 30), (28, 30), (34, 10), (48, 0)], f))
        _tail(p, 22 * max(up, 0), 0)
        air = K([(0, 0), (8, 0), (13, 1), (28, 1), (30.5, 0), (48, 0)], f)
        for s in (1, -1):
            lp = LegPose(target=neutral(('F', s)) + Vector((0, -0.10, 0)) * K([(0, 0), (30, 1), (40, 1), (48, 0)], f),
                         wb=air)
            lp.boff = Vector((s * 0.04, -0.15, 0.12))
            lp.flex = -60 * air
            lp.toe = -15 * air
            lp.scap = 14 * air
            p.legs[('F', s)] = lp
            hl = LegPose(target=neutral(('H', s)))
            hl.flex = 10 * max(up, 0)
            p.legs[('H', s)] = hl
        return p
    return N, fn, False


def _clip_graze():
    """The trunk swings forward with its tip on the ground, grips (curls), curls back up to the lips, the jaw
    works, and it hangs again."""
    N = 120

    def fn(f):
        p = MammothPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 40
        p.body = Vector((0.010 * math.sin(a), 0, 0.006 * math.sin(b)))
        dip = K([(0, 0), (12, 1), (40, 1), (60, 0.2), (100, 0.2), (120, 0)], f, N)
        p.neck[0] = [-4 * dip, 2 * math.sin(a), 0]
        p.head = [-4 * dip + 3 * K([(0, 0), (50, 0), (64, 1), (96, 1), (110, 0), (120, 0)], f, N), 2 * math.sin(a + 1), 0]
        reach = K([(0, 0), (14, 1), (34, 1), (44, 0.4), (54, 0), (120, 0)], f, N)
        mouth = K([(0, 0), (40, 0), (58, 1), (78, 1), (94, 0), (120, 0)], f, N)
        grip = K([(0, 0), (26, 0), (32, 1), (60, 1), (74, 0), (120, 0)], f, N)
        shape = _mix(_mix(HANG, REACH, reach), TO_MOUTH, mouth)
        sweep = 6 * math.sin(2 * math.pi * f / 12) * K([(0, 0), (16, 0), (20, 1), (28, 1), (32, 0), (120, 0)], f, N)
        _trunk(p, shape, 0, 0, extra=[0, 0, 0, 0, 14 * grip, 24 * grip])
        for i in range(TN):
            p.trunk[i][1] = sweep * (0.3 + 0.15 * i) + 2 * math.sin(a - 0.5 * i)
        chew = K([(0, 0), (62, 0), (68, 1), (104, 1), (110, 0), (120, 0)], f, N)
        p.jaw = 10 * K([(0, 0), (56, 0), (62, 1), (68, 0.2), (120, 0)], f, N) + 5 * chew * (0.5 + 0.5 * math.sin(2 * math.pi * f / 10))
        _ears(p, 2, 6, flapL=20 * _bump(f, 90, 7), flapR=20 * _bump(f, 94, 7))
        _tail(p, 0, 10, 2 * a)
        return p
    return N, fn, True


def _clip_hit():
    N = 15

    def fn(f):
        p = MammothPose()
        k = K([(0, 0), (3, 1), (7, 0.6), (11, -0.15), (15, 0)], f)
        p.body = Vector((0.05 * k, 0.07 * k, -0.03 * max(k, 0)))
        p.roll, p.yaw = 4 * k, -5 * k
        p.neck[0] = [-6 * k, -8 * k, 0]
        p.head = [8 * k, -12 * k, 8 * k]
        p.jaw = K([(0, 0), (3, 12), (8, 3), (15, 0)], f)
        _trunk(p, HANG, 0, 0, extra=[6 * k, 10 * k, 12 * k, 12 * k, 10 * k, 8 * k])
        for i in range(TN):
            p.trunk[i][1] = K([(0, 0), (3, 10), (7, -6), (11, 3), (15, 0)], f) * (0.4 + 0.15 * i)
        _ears(p, K([(0, 0), (2, -30), (9, -10), (15, 0)], f), K([(0, 0), (2, 25), (10, 5), (15, 0)], f))
        _tail(p, -10 * k, 0)
        return p
    return N, fn, False


def _death_pose(f):
    """Staggers, the forelegs buckle (it kneels), the hind end sinks, it slumps onto its belly and leans to its
    right, the head sagging until the tusks rest on the ground and the trunk lies out in front."""
    p = MammothPose()
    front = K([(0, 0), (14, 0), (34, 1), (75, 1)], f)
    hind = K([(0, 0), (30, 0), (52, 1), (75, 1)], f)
    _lie(p, front, hind)
    p.body += Vector((K([(0, 0), (8, 0.04), (16, -0.03), (40, 0), (56, -0.08), (75, -0.09)], f), 0,
                      K([(0, 0), (50, 0), (60, -0.04), (75, -0.04)], f)))
    p.roll = K([(0, 0), (8, 3), (16, -2), (44, 0), (60, -7), (75, -8)], f)
    p.yaw = K([(0, 0), (8, 2), (16, -2), (30, 0), (75, 0)], f)
    sag = K([(0, 0), (34, 0.3), (60, 1), (75, 1)], f)
    p.neck[0] = [K([(0, 0), (6, 8), (14, -4), (30, 0), (75, 0)], f) - 2 * sag, -4 * sag, 0]   # the tusks prop
    p.neck[1] = [-2 * sag, -3 * sag, 0]                                                          # the head up
    p.head = [3 * sag, -4 * sag, -6 * sag]
    p.jaw = K([(0, 0), (6, 14), (20, 8), (60, 6), (75, 5)], f)
    _trunk(p, _mix(HANG, ON_GROUND, min(1.0, 1.25 * front)), 6 * (1 - sag), f * 0.4)   # laid out as the front sinks
    _ears(p, K([(0, 0), (4, -20), (75, -6)], f), 12 * sag)
    _tail(p, -8 * sag, 6 * (1 - sag), f * 0.3)
    return p


def _clip_death():
    return 75, _death_pose, False


CLIPS = {"Sleep": _clip_sleep, "Wake": _clip_wake, "Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run,
         "Charge": _clip_charge, "Trumpet": _clip_trumpet, "TuskSwipe": _clip_tuskswipe, "Stomp": _clip_stomp,
         "Graze": _clip_graze, "Hit": _clip_hit, "Death": _clip_death}


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
