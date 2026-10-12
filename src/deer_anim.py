"""Red deer stag clips, keyed straight onto the rig; the machinery (poses, leg IK, gaits, keying) is beast_anim.py
(2026-10-11).

Skittish prey: it grazes, looks up when it hears something and bolts; cornered or hit, a stag may lash out once with
its antlers. The long neck has three bones (Pose.neck): grazing takes the head down to the grass, the alert snaps it
up high. The legs are long and thin, unguligrade: the "paw" bones are the cannons (FrontPaw / HindFoot), the "toes"
the pasterns and hooves.

Clips (30 fps, the stag faces -Y; Unity +Z):
  Idle    4.0 s loop    breathing, a weight shift, ear flicks, a tail flick, a slow look round
  Graze   5.0 s loop    head down at the grass, chewing, ears turning, a slow step forward (root motion 0.16 m a loop)
  Alert   1.5 s         head snaps up high, ears forward and stiff, tail up, a forefoot stamp; holds the end
  Walk    1.2 s loop    four-beat lateral walk, the head nodding, root motion 1.1 m/s
  Trot    0.67 s loop   two-beat diagonal trot, root motion 2.9 m/s
  Run     0.47 s loop   the flight gallop: long bounding strides, tail up showing the rump patch, head forward,
                        root motion 8.1 m/s
  Attack  1.2 s         head down, a lunge forward and up with a twist of the antlers (event 'Bite' at 0.5 s)
  Hit     0.5 s         a flinch sideways
  Death   2.2 s         the legs fold, it falls onto its left side, the head last (event 'Dead' at 1.9 s); holds
  Sleep   4.0 s loop    lying on its belly, legs folded under, the head low, slow breathing
  Wake    2.0 s         rises hind end first, as deer do, ends in the Idle stance
"""
import math
from mathutils import Vector
import deer_body as DB
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, TROT, GALLOP

FPS = 30
SPEC = BA.Species(DB.rest_bones, (0.0, -0.05, 0.95), "Deer", "DeerRig", neck_n=3, tail_n=len(DB.TAIL) - 1,
                  tongue=False)
LEGS = BA.LEGS
EVENTS = {"Attack": [("Bite", 0.5)], "Death": [("Dead", 1.9)]}
MOVING = {"Graze", "Walk", "Trot", "Run"}
FWD = Vector((0, -1, 0))


def DeerPose():
    return BA.Pose(SPEC)


def neutral(key):
    return BA.neutral(SPEC, key)


def action_name(clip):
    return SPEC.action_name(clip)


def gait(p, f, N, stride, duty, lift, phases, **kw):
    return BA.gait(SPEC, p, f, N, stride, duty, lift, phases, **kw)


def _bump(f, c, width):
    return max(0.0, 1 - abs(f - c) / width)


def _ears(p, fwd, splay=0.0, flickL=0.0, flickR=0.0, turnL=0.0, turnR=0.0):
    """fwd: + forward / - back; splay: + out from the head; a flick adds a quick turn back."""
    p.ears = {1: [fwd + flickL + turnL, splay], -1: [fwd + flickR + turnR, splay]}


def _flick(f, c, w=3.0, amp=-35.0):
    return amp * _bump(f, c, w)


def _tail(p, lift, swing=0.0, phase=0.0):
    """+ lift raises it (flagged up, the rump patch shows), swing sways it."""
    for i in range(SPEC.tail_n):
        p.tail[i] = [lift if i == 0 else lift * 0.5, swing * math.sin(phase - 0.8 * i), 0.0]


def _neck(p, pitches, yaws=(0, 0, 0)):
    for i in range(3):
        p.neck[i] = [pitches[i], yaws[i], 0.0]


# the neck's shapes: per-bone pitches (Neck1..3) and the head's, + raises
UP_HIGH = ((18, 4, -2), -3)                      # the alert: neck upright, head high, face toward the sound
GRAZE_DOWN = ((-44, -40, -30), 76)               # neck down to the grass, the face nearly vertical


# ----------------------------------------------------------------------------------------- idle and grazing
def _clip_idle():
    N = 120

    def fn(f):
        p = DeerPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 40                                          # three breaths a loop
        shift = K([(0, 0), (34, 0), (44, 1), (70, 1), (80, 0), (120, 0)], f, N)   # weight onto the left, a hind
        p.body = Vector((0.010 * math.sin(a) + 0.018 * shift, 0, 0.004 * math.sin(b)))   # foot rests
        p.roll = 0.8 * math.sin(a) + 1.5 * shift
        p.spine[2][0] = 0.6 * math.sin(b)
        look = K([(0, 0), (16, 0), (34, 26), (58, 26), (76, -10), (100, -10), (112, 0), (120, 0)], f, N)
        nod = K([(0, 0), (34, -3), (58, -3), (76, 2), (112, 0), (120, 0)], f, N)
        _neck(p, (1.5 * math.sin(a) + nod, 0.8 * math.sin(a + 0.5), 0), (look * 0.25, look * 0.25, look * 0.2))
        p.head = [1.5 * math.sin(b + 1.0) - nod, look * 0.3, 0]
        _ears(p, 6, 0, flickL=_flick(f, 22), flickR=_flick(f, 88) + _flick(f, 95),
              turnL=-14 * K([(0, 0), (60, 0), (66, 1), (80, 1), (86, 0), (120, 0)], f, N))
        flick = math.sin(2 * math.pi * f / 5) * K([(0, 0), (96, 0), (100, 1), (108, 1), (112, 0), (120, 0)], f, N)
        _tail(p, 4 + 8 * abs(flick), 20 * flick)
        rest = K([(0, 0), (40, 0), (46, 1), (70, 1), (76, 0), (120, 0)], f, N)       # the right hind foot cocked
        H0 = neutral(('H', -1))
        lp = LegPose(target=H0 + Vector((0, -0.04 * rest, 0.03 * rest)))
        lp.flex = 14 * rest
        lp.toe = 20 * rest
        p.legs[('H', -1)] = lp
        return p
    return N, fn, True


GRAZE_STEP = 0.16                               # a slow step forward a loop (root motion)


def _clip_graze():
    N = 150

    def fn(f):
        p = DeerPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 50
        p.root = FWD * (GRAZE_STEP * ease((f - 70) / 44))
        p.body = Vector((0.006 * math.sin(a), 0.03, -0.10 + 0.003 * math.sin(b)))   # the chest lowered: the muzzle
        p.pitch = -13                                                     # reaches the grass ahead of the forefeet
        pitches, head = GRAZE_DOWN
        sweep = 6 * math.sin(a) + 3 * math.sin(2 * a + 1)                # the muzzle moves over the grass
        bite = K([(0, 0), (20, 0), (24, 1), (30, 0), (90, 0), (94, 1), (100, 0), (150, 0)], f, N)
        _neck(p, (pitches[0] + 1.5 * math.sin(b) - 2 * bite, pitches[1] - 2 * bite, pitches[2]),
              (sweep * 0.3, sweep * 0.3, sweep * 0.2))
        p.head = [head + 2 * math.sin(b + 1) + 3 * bite, sweep * 0.3, 14 + 3 * math.sin(a)]   # tilted: antlers clear
        chew = 1 - bite
        p.jaw = 3 + 4 * chew * (0.5 + 0.5 * math.sin(2 * math.pi * f / 9)) + 6 * bite
        _ears(p, 2, 6, flickL=_flick(f, 48), flickR=_flick(f, 128),
              turnL=-20 * K([(0, 0), (56, 0), (62, 1), (84, 1), (90, 0), (150, 0)], f, N),
              turnR=18 * K([(0, 0), (104, 0), (110, 1), (124, 1), (130, 0), (150, 0)], f, N))
        _tail(p, 2, 6, 2 * a)
        steps = {('H', 1): 68, ('F', 1): 78, ('H', -1): 92, ('F', -1): 102}        # a slow walk's footfalls
        for key, c in steps.items():
            q = min(max((f - c) / 14, 0.0), 1.0)
            F0 = neutral(key)
            tgt = F0 + FWD * (GRAZE_STEP * ease(q))
            tgt.z += 0.07 * math.sin(math.pi * q)
            lp = LegPose(target=tgt)
            sw = math.sin(math.pi * q)
            lp.flex = (-60 if key[0] == 'F' else 30) * sw
            lp.toe = -12 * sw
            if key[0] == 'F':
                lp.scap = 6 * (ease(q) - 0.5) * (0 < q < 1)
            p.legs[key] = lp
        return p
    return N, fn, True


def _clip_alert():
    """The head snaps up high, ears forward and stiff, the body tenses, the tail goes up; a forefoot stamp; held."""
    N = 45

    def fn(f):
        p = DeerPose()
        up = K([(0, 0), (5, 1.05), (9, 1.0), (45, 1.0)], f)
        tense = K([(0, 0), (6, 1), (45, 1)], f)
        p.body = Vector((0, 0.025 * tense, -0.015 * tense))
        p.pitch = 2 * tense
        pitches, head = UP_HIGH
        look = K([(0, 0), (8, 0), (14, 8), (45, 8)], f)                 # toward the sound, a little to its left
        _neck(p, [x * up for x in pitches], (look * 0.3, look * 0.3, look * 0.2))
        p.head = [head * up, look * 0.3, 0]
        _ears(p, 26 * up, -6 * up)
        _tail(p, 30 * tense)
        stamp = [(0, 0), (14, 0), (19, 1), (22, 1), (24.5, 0), (45, 0)]
        F0 = neutral(('F', 1))
        lift = K(stamp, f)
        lp = LegPose(target=F0 + Vector((0, -0.02 * lift, 0.13 * lift)))
        lp.flex = -55 * lift
        lp.toe = -15 * lift
        p.legs[('F', 1)] = lp
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- locomotion
def _clip_walk():
    N = 36

    def fn(f):
        p = DeerPose()
        gait(p, f, N, 1.30, 0.62, 0.10, WALK, front_fold=80, hind_flex=40, scap=14)
        a = 2 * math.pi * f / N
        p.body = Vector((0.010 * math.sin(a), 0, -0.012 - 0.010 * math.cos(2 * a)))
        p.roll = 1.5 * math.sin(a)
        p.yaw = 1.5 * math.sin(a + 0.8)
        p.pitch = 0.6 * math.sin(2 * a)
        for i in range(3):
            p.spine[i][1] = -1.2 * math.sin(a + 0.8)
        nod = 3.0 * math.sin(2 * a + 1.0)                                  # the head nods with each forefoot
        _neck(p, (-2 + nod, -1 + 0.5 * nod, 0), (-1.5 * math.sin(a), 0, 0))
        p.head = [1 - 1.2 * nod, -1.5 * math.sin(a), 0]
        _ears(p, 4, 2 + 3 * math.sin(2 * a))
        _tail(p, 2, 5, a)
        return p
    return N, fn, True


def _clip_trot():
    N = 20

    def fn(f):
        p = DeerPose()
        gait(p, f, N, 1.95, 0.40, 0.16, TROT, front_fold=105, hind_flex=50, scap=20)
        a = 2 * math.pi * f / N
        p.body = Vector((0, 0, -0.018 - 0.016 * math.cos(2 * a)))
        p.roll = 1.0 * math.sin(a)
        p.pitch = -1 + 0.8 * math.sin(2 * a)
        bob = 1.6 * math.sin(2 * a + 1.2)
        _neck(p, (2 + bob, 1, 0))
        p.head = [-1 - bob, 0, 0]
        _ears(p, -4, 0)
        _tail(p, 12, 4, a)
        return p
    return N, fn, True


def _clip_run():
    """The flight gallop: long bounding strides with the back gathering and stretching, the hind feet landing ahead
    of where the forefeet left, tail up flashing the rump patch, head and neck reaching forward, ears back."""
    N = 14

    def fn(f):
        p = DeerPose()
        gait(p, f, N, 3.80, 0.28, 0.24, GALLOP, front_fold=120, hind_flex=62, scap=32)
        a = 2 * math.pi * f / N
        flexb = math.cos(a - 0.5)                      # + gathered (back arched), - stretched
        p.body = Vector((0, 0, -0.02 + 0.06 * math.sin(a - 1.2)))
        p.pitch = -1 + 4 * math.sin(a - 0.3)
        p.spine[0][0] = 8 * flexb
        p.spine[2][0] = -7 * flexb
        p.hips = [-10 * flexb, 0, 0]
        reach = 3 * math.sin(a - 0.3)
        _neck(p, (-26 - reach, -14, -4))               # the neck reaches forward, lower than at rest
        p.head = [50 + reach, 0, 0]                    # the face kept forward, the antlers laid back
        p.jaw = 4
        _ears(p, -28, -4)
        _tail(p, 55, 4, a)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- the attack and hits
def _clip_attack():
    """Lowers its head, antlers forward, weight back; lunges forward and up with a twist, the right forefoot stepping
    in (event 'Bite' at 0.5 s); then backs up into its stance."""
    N = 36

    def fn(f):
        p = DeerPose()
        lunge = K([(0, 0), (9, -0.08), (13, 0.22), (16, 0.26), (24, 0.12), (36, 0)], f)   # + forward
        p.body = Vector((0, -lunge, K([(0, 0), (9, -0.06), (13, -0.02), (16, 0.02), (36, 0)], f)))
        p.pitch = K([(0, 0), (9, -5), (13, 2), (16, 4), (24, 1), (36, 0)], f)
        p.hips = [K([(0, 0), (9, 4), (14, -6), (36, 0)], f), 0, 0]
        dip = K([(0, 0), (9, 1), (13, 0.55), (15, 0.15), (19, -0.15), (26, -0.05), (36, 0)], f)   # head down; at
        twist = K([(0, 0), (11, 0), (15, 1), (19, 0.7), (30, 0), (36, 0)], f)      # the hit the tines still point
        _neck(p, (-22 * dip, -20 * dip, -12 * dip), (0, 4 * twist, 6 * twist))     # ahead, then they hook up
        p.head = [-6 * dip + 6 * twist, 8 * twist, -22 * twist]
        _ears(p, K([(0, 0), (6, -30), (28, -30), (36, 0)], f), -8)
        _tail(p, K([(0, 0), (8, 20), (28, 20), (36, 0)], f))
        step = K([(0, 0), (9, 0), (14, 1), (24, 1), (32, 0), (36, 0)], f)
        lift = K([(0, 0), (9, 0), (11.5, 1), (14, 0), (24, 0), (28, 1), (32, 0), (36, 0)], f)
        F0 = neutral(('F', -1))
        lp = LegPose(target=F0 + Vector((0, -0.26 * step, 0.12 * lift)))
        lp.flex = -60 * lift
        lp.toe = -12 * lift
        lp.scap = 12 * step
        p.legs[('F', -1)] = lp
        for s in (1, -1):                                                   # the hind legs drive
            lp = LegPose(target=neutral(('H', s)))
            lp.flex = K([(0, 0), (9, 14), (14, -8), (36, 0)], f)
            p.legs[('H', s)] = lp
        return p
    return N, fn, False


def _clip_hit():
    N = 15

    def fn(f):
        p = DeerPose()
        k = K([(0, 0), (3, 1), (7, 0.6), (11, -0.15), (15, 0)], f)
        p.body = Vector((0.06 * k, 0.04 * k, -0.025 * max(k, 0)))
        p.roll, p.yaw = 7 * k, -6 * k
        _neck(p, (-6 * k, -4 * k, 0), (-8 * k, -6 * k, -4 * k))
        p.head = [6 * k, -10 * k, 10 * k]
        p.jaw = K([(0, 0), (3, 10), (8, 2), (15, 0)], f)
        _ears(p, K([(0, 0), (2, -40), (9, -15), (15, 0)], f), 10 * max(k, 0))
        _tail(p, K([(0, 0), (3, 25), (15, 0)], f))
        return p
    return N, fn, False


DOWN_Z = 0.69                                    # lying on its side, the trunk's centre drops this far


def _death_pose(f):
    """Staggers, the legs fold (the front first), it rolls onto its left side and the trunk comes to rest on its
    flank; the head comes down last, onto its left cheek with the antlers turned up off the ground."""
    p = DeerPose()
    p.roll = K([(0, 0), (8, -4), (18, 8), (28, 40), (36, 78), (42, 86), (48, 84), (66, 85)], f)
    p.body = Vector((K([(0, 0), (8, -0.03), (28, 0.10), (36, 0.20), (42, 0.24), (66, 0.24)], f),
                     K([(0, 0), (8, -0.02), (30, 0.04), (66, 0.04)], f),
                     K([(0, 0), (8, -0.02), (18, -0.16), (28, -0.40), (36, -0.62), (42, -DOWN_Z), (48, -DOWN_Z + 0.02),
                        (66, -DOWN_Z)], f)))
    p.pitch = K([(0, 0), (8, 3), (20, -7), (34, -2), (66, -2)], f)
    jerk = K([(0, 0), (4, 1), (12, 0)], f)
    down = K([(0, 0), (36, 0), (50, 1), (66, 1)], f)                     # the head last
    _neck(p, (8 * jerk + 6 * (1 - down) * K([(0, 0), (20, 1), (66, 1)], f) - 10 * down, -6 * down, -4 * down),
          (0, 6 * down, 4 * down))
    p.head = [-4 * jerk - 6 * down, 8 * down, 45 * down]                  # the antlers turned up off the ground
    p.jaw = K([(0, 0), (4, 14), (20, 8), (66, 6)], f)
    _ears(p, K([(0, 0), (4, -40), (66, -20)], f), 10 * down)
    _tail(p, K([(0, 0), (6, 20), (30, 0), (66, -6)], f))
    wb = K([(0, 0), (14, 0), (30, 1), (66, 1)], f)
    fold = K([(0, 0), (10, 0), (24, 1), (66, 0.7)], f)
    for kind, s in LEGS:
        lp = LegPose(wb=wb)
        up_side = s < 0                                  # lying on its left side: the right legs are on top
        lp.boff = Vector((0.10 if up_side else 0.02, (0.06 if kind == 'H' else -0.06), 0.04 if up_side else 0.10))
        lp.flex = (-70 if kind == 'F' else 40) * fold
        lp.toe = -25 * wb
        p.legs[(kind, s)] = lp
    return p


def _clip_death():
    return 66, _death_pose, False


# ----------------------------------------------------------------------------------------- lying down
LIE_DROP = 0.53                                  # lying on its belly: the trunk sinks this far


def _lie(p, front, hind):
    """Fold the legs under and sink the trunk; front / hind = 0 (standing) .. 1 (lying). The forelegs fold at the
    knees with the cannons under the chest, the hind legs fold with the cannons forward along the ground."""
    p.body = p.body + Vector((0, 0, -LIE_DROP * (0.45 * front + 0.55 * hind)))
    p.pitch += 6.0 * (hind - front)
    for s in (1, -1):
        F0, H0 = neutral(('F', s)), neutral(('H', s))
        fl = LegPose(target=F0 + Vector((0.0, 0.02, -0.01)) * front)     # the cannon back along the ground under
        fl.flex = -95 * front                                              # the chest, the knee ahead of it
        fl.toe = -15 * front
        fl.scap = -10 * front
        hl = LegPose(target=H0 + Vector((s * 0.10, -0.36, -0.01)) * hind)
        hl.flex = 95 * hind
        hl.toe = -10 * hind
        p.legs[('F', s)] = fl
        p.legs[('H', s)] = hl


def _clip_sleep():
    N = 120

    def fn(f):
        p = DeerPose()
        a = 2 * math.pi * f / N
        _lie(p, 1.0, 1.0)
        p.body += Vector((0, 0, 0.008 * math.sin(a)))                     # slow breathing
        p.spine[2][0] = 1.0 * math.sin(a)
        _neck(p, (-16, -14, -6), (4, 4, 3))                                # the head low, the chin near the ground
        p.head = [18 + 1.5 * math.sin(a), 4, 8]
        _ears(p, -10, 10, flickR=_flick(f, 70, 3, -30))
        _tail(p, -4)
        return p
    return N, fn, True


def _clip_wake():
    N = 60

    def fn(f):
        p = DeerPose()
        t = f / N
        hind = 1 - ease(t / 0.50)                                          # deer rise hind end first
        front = 1 - ease((t - 0.30) / 0.55)
        _lie(p, front, hind)
        p.body += Vector((0, K([(0, 0), (12, 0.06), (36, -0.03), (60, 0)], f), 0))
        sleepy = 1 - ease(t / 0.6)
        shake = K([(0, 0), (44, 0), (47, 1), (50, -1), (53, 0.6), (56, -0.2), (60, 0)], f)
        _neck(p, (-16 * sleepy, -14 * sleepy, -6 * sleepy), (4 * sleepy, 4 * sleepy, 3 * sleepy))
        p.head = [18 * sleepy, 4 * sleepy + 6 * shake, 8 * sleepy + 16 * shake]
        _ears(p, -10 * sleepy, 10 * sleepy + 10 * abs(shake))
        _tail(p, -4 * sleepy + 10 * abs(shake), 10 * shake)
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Graze": _clip_graze, "Alert": _clip_alert, "Walk": _clip_walk, "Trot": _clip_trot,
         "Run": _clip_run, "Attack": _clip_attack, "Hit": _clip_hit, "Death": _clip_death, "Sleep": _clip_sleep,
         "Wake": _clip_wake}


# ----------------------------------------------------------------------------------------- build / checks
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


def slide_report(names=("Walk", "Trot", "Run", "Graze"), z_contact=0.016):
    """How far each hoof drifts on the ground while it is planted (world xy, the root motion added): per clip the
    worst drift over any stance, metres."""
    out = {}
    for name in names:
        N, fn, loop = CLIPS[name]()
        worst = 0.0
        for kind, s in LEGS:
            toes = f"{'FrontToes' if kind == 'F' else 'HindToes'}{'L' if s > 0 else 'R'}"
            B = BA.rest_data(SPEC)['B']
            run = []
            for f in range(N + 1):
                p = fn(f)
                m = pose_matrices(p)
                tip = m[toes] @ Vector((0, B[toes][2], 0))
                w = p.root + tip                               # the skeleton plays in place: add the travel
                if w.z < z_contact:
                    run.append(w)
                elif run:
                    worst = max(worst, max((q - run[0]).xy.length for q in run))
                    run = []
            if run:
                worst = max(worst, max((q - run[0]).xy.length for q in run))
        out[name] = round(worst, 3)
    return out
