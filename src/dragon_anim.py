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
  Bite       1.4 s        neck drawn back, strikes down to a man's height ~2 m ahead, snaps (event 'Bite' at 0.63 s),
                          worries its catch
  Claw       1.2 s        rises on its haunches, rakes the right foreleg down across the front (event 'Bite' 0.53 s)
  TailSweep  1.8 s        winds the tail out left, whips it round to the right (event 'Bite' at 0.8 s), head
                          watching it go
  Fire       2.5 s        a deep breath, then fire from Socket_Mouth, the head sweeping side to side (events 'Fire'
                          at 0.9 s, 'FireEnd' at 2.0 s)
  Roar       2.2 s        rears onto its haunches, wings thrown up, roars (event 'Roar' at 0.6 s), comes down
  Hit        0.6 s        head snapped away, body rocked back, wings twitching open, a small rebound
  Death      3.0 s        a last cry, forelegs then hind legs buckle onto its belly, the neck falls and the head
                          hits the ground (event 'Dead' at 2.0 s), a last breath and tail twitch; holds the end
  Takeoff    2.2 s        crouch, wings swept up, leap (event 'TakeOff' at 0.63 s), three climbing beats; root
                          motion 10 m forward, 7 m up
  Fly        1.2 s loop   one slow, deep wingbeat, legs tucked, neck stretched, head level; 10 m/s
  Glide      2.0 s loop   wings out with a slight dihedral, a slow bank; 14 m/s
  Land       2.4 s        glide in, flare and brake, hind feet first (event 'Land' at 1.4 s), wings folding;
                          root motion 15.6 m forward, 7 m down
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


def _turned(turns, curl=0.0):
    """Aims for the spread wing turned rigidly about the shoulder (dragon_pose.wing_turned, from the rest data):
    turns = [(axis, deg)] for the left wing -- 'Y' + turns it down / - up, 'Z' + sweeps it back, 'X' + pitches the
    leading edge down -- mirrored for the right; curl bends each finger joint down (a cupped stroke)."""
    R = BA.rest_data(SPEC)['R']
    aim = {}
    for s, sfx in DB.SIDES:
        M = Matrix.Identity(3)
        for ax, deg in turns:
            M = Matrix.Rotation(math.radians(deg if (s > 0 or ax == 'X') else -deg), 3, ax) @ M
        for n in DB.wing_chain(sfx):
            d, z = M @ R[n].col[1].xyz, M @ R[n].col[2].xyz
            if curl and n.startswith("WingF") and n[5].isdigit():
                k = int(n.split("_")[1][0])
                c = Matrix.Rotation(math.radians(-curl * k), 3, d.cross(z).normalized())
                d, z = c @ d, c @ z
            aim[n] = (d, z)
    return aim


def _wings(sp, p, Wm, rel):
    """The wing bones, riding on the chest. Standing: folded, opened toward p.wing_to by p.wing_open, lifted by
    p.wing_lift. Flying: p.wing = dict(turns=[(axis, deg)], curl=deg, fold=0..1), the spread wing turned about the
    shoulder (_turned) and drawn part way back toward the fold. Each bone turns from one pose to the other along
    the shortest rotation (a straight blend of the directions folded the forearm through itself)."""
    R = BA.rest_data(sp)['R']
    B = BA.rest_data(sp)['B']
    turn = Wm["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    fold = _aims("fold")
    w = getattr(p, "wing", None)
    if w is not None:
        alt, t = _turned(w.get("turns", ()), w.get("curl", 0.0)), 1.0 - w.get("fold", 0.0)
    else:
        t = getattr(p, "wing_open", 0.0)
        alt = _aims(getattr(p, "wing_to", "raised")) if t else fold
    lift = Matrix.Rotation(math.radians(getattr(p, "wing_lift", 0.0)), 3, 'X')
    for s, sfx in DB.SIDES:
        n = f"WingScap{sfx}"
        Wm[n] = Wm["Chest"] @ rel(n, "Chest")
        for n in DB.wing_chain(sfx):
            par = B[n][3]
            here = Wm[par] @ rel(n, par)
            q = DB._frame(*fold[n]).to_quaternion()
            if t:
                q = q.slerp(DB._frame(*alt[n]).to_quaternion(), min(max(t, 0.0), 1.0))
            Wm[n] = Matrix.Translation(here.translation) @ (turn @ lift @ q.to_matrix()).to_4x4()
    if "WingMem11L" in R:
        DB.membrane_pose(Wm, R)                                  # the arm panels' helper bones


SPEC = BA.Species(DB.rest_bones, (0.0, 0.35, 2.3), "Dragon", RIG, neck_n=DB.NECK_N, tail_n=DB.TAIL_N, tongue=False,
                  ears=False, tail_floor=[0.10] * DB.TAIL_N, extra=_wings)
LEGS = BA.LEGS
EVENTS = {"Bite": [("Bite", 0.63)], "Claw": [("Bite", 0.53)], "TailSweep": [("Bite", 0.80)],
          "Fire": [("Fire", 0.90), ("FireEnd", 2.00)], "Roar": [("Roar", 0.60)], "Death": [("Dead", 2.0)],
          "Takeoff": [("TakeOff", 0.63)], "Land": [("Land", 1.40)]}
MOVING = {"Walk", "Run", "Fly", "Glide", "Takeoff", "Land"}


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


# ----------------------------------------------------------------------------------------- attacks
BASE = (1.7, 1.5, 1.2, 1.0, 0.8, 0.5, 0.3)                 # neck turns mostly at the base (a strike from the chest)
HIP_PIVOT = Vector((0.0, 1.20, 1.90))                       # rearing turns the trunk about the hip joints


def pivot(p, pitch, pv=HIP_PIVOT):
    """Pitch the trunk about pv instead of its centre (sets p.pitch and adds the matching offset to p.body)."""
    C = SPEC.body_c
    R = Matrix.Rotation(math.radians(-pitch), 3, 'X')
    p.pitch = pitch
    p.body = p.body + (pv - C) - R @ (pv - C)


def _path(keys, f):
    return Vector(K([(k, tuple(v)) for k, v in keys], f))


def _clip_bite():
    """Draws the neck back and up, then strikes forward and down to a man's height ~2 m ahead of the snout, jaws
    wide, snaps shut (event 'Bite' at 0.63 s), worries its catch and draws back; the right forepaw steps in."""
    N = 42

    def fn(f):
        p = DragonPose()
        p.body = Vector((0, K([(0, 0), (11, 0.18), (17, -0.38), (28, -0.30), (42, 0)], f),
                         K([(0, 0), (11, 0.02), (17, -0.14), (28, -0.10), (42, 0)], f)))
        p.pitch = K([(0, 0), (11, 3), (17, -6), (28, -4), (42, 0)], f)
        p.spine[2][0] = K([(0, 0), (11, 4), (17, -6), (28, -4), (42, 0)], f)
        strike = K([(0, 0), (11, 14), (15, -38), (18, -52), (28, -48), (36, -12), (42, 0)], f)
        _neck_wave(p, strike, 0.0, spread=BASE)
        shake = K([(0, 0), (20, 0), (22, 10), (24, -9), (26, 6), (28, 0), (42, 0)], f)
        p.head = [K([(0, 0), (11, -10), (15, 34), (18, 62), (28, 58), (36, 16), (42, 0)], f), 0.5 * shake, shake]
        p.jaw = K([(0, 0), (6, 10), (12, 22), (17, 42), (18.5, 44), (19.5, 4), (28, 6), (34, 12), (42, 0)], f)
        p.wing_lift = K([(0, 0), (11, -4), (17, 6), (28, 4), (42, 0)], f)
        _tail_wave(p, 1.0, 2 * math.pi * f / N, lift=K([(0, 0), (11, -3), (17, 6), (42, 0)], f))
        F0 = neutral(('F', -1))
        step = F0 + Vector((0, -0.45, 0))
        lp = LegPose(target=_path([(0, F0), (11, F0), (16, F0 + Vector((0, -0.25, 0.30))), (19, step), (30, step),
                                   (35, F0 + Vector((0, -0.2, 0.22))), (40, F0), (42, F0)], f))
        lp.flex = K([(0, 0), (12, 0), (15, -50), (19, 0), (30, 0), (34, -40), (40, 0), (42, 0)], f)
        lp.scap = K([(0, 0), (11, -4), (19, 14), (30, 12), (42, 0)], f)
        p.legs[('F', -1)] = lp
        return p
    return N, fn, False


def _clip_claw():
    """Rises a little onto its hind legs, weight onto the left, the right foreleg drawn up and out, then raked down
    and across the front (event 'Bite' at 0.53 s), the head turning into the blow."""
    N = 36

    def fn(f):
        p = DragonPose()
        rise = K([(0, 0), (10, 1), (16, 0.7), (22, 0.2), (36, 0)], f)
        pivot(p, 15 * rise)
        p.roll = K([(0, 0), (10, -5), (16, 3), (22, 3), (36, 0)], f)
        p.yaw = K([(0, 0), (10, -8), (16, 10), (21, 12), (36, 0)], f)
        p.body += Vector((K([(0, 0), (10, 0.10), (16, 0.0), (36, 0)], f),
                          K([(0, 0), (10, 0.10), (16, -0.25), (22, -0.2), (36, 0)], f), 0))
        turn = K([(0, 0), (10, -16), (16, 14), (21, 18), (36, 0)], f)
        _neck_wave(p, K([(0, 0), (10, 6), (16, -12), (24, -6), (36, 0)], f), turn)
        p.head = [K([(0, 0), (10, -4), (16, 10), (36, 0)], f), 0.4 * turn, K([(0, 0), (14, -8), (20, -6), (36, 0)], f)]
        p.jaw = K([(0, 0), (8, 14), (16, 30), (22, 12), (36, 0)], f)
        p.wing_lift = K([(0, 0), (10, 6), (16, -2), (36, 0)], f)
        _tail_wave(p, 1.0, 2 * math.pi * f / N)
        for i in range(SPEC.tail_n):                                # the tail swings against the blow
            p.tail[i][1] += K([(0, 0), (10, 1.5), (17, -2.0), (36, 0)], f - 0.6 * i)
        F0 = neutral(('F', -1))
        path = [(0, F0), (5, F0 + Vector((-0.10, 0.05, 0.40))), (10, Vector((-1.30, -2.00, 2.40))),
                (14, Vector((-0.85, -2.85, 1.85))), (16, Vector((-0.10, -3.10, 1.20))), (19, Vector((0.25, -2.65, 0.50))),
                (24, F0 + Vector((0.05, -0.30, 0.10))), (30, F0 + Vector((0, -0.05, 0.02))), (36, F0)]
        lp = LegPose(target=_path(path, f))
        lp.flex = K([(0, 0), (6, -50), (11, -20), (15, 10), (19, -10), (26, -5), (36, 0)], f)
        lp.toe = K([(0, 0), (8, -10), (13, 30), (19, 10), (36, 0)], f)
        lp.scap = K([(0, 0), (10, -16), (16, 20), (21, 10), (36, 0)], f)
        p.legs[('F', -1)] = lp
        p.legs[('F', 1)].scap = K([(0, 0), (10, 6), (16, -4), (36, 0)], f)
        return p
    return N, fn, False


def _clip_tail():
    """Tail sweep: winds the tail out to its left, then whips it round hard to the right in a wide, low arc (event
    'Bite' at 0.8 s as it passes its flank), the trunk and neck turning against it, the head watching it go."""
    N = 54

    def fn(f):
        p = DragonPose()
        sweep = lambda t: K([(0, 0), (12, 1.0), (18, 0.8), (26, -2.0), (34, -1.6), (46, -0.2), (54, 0)], t)
        for i in range(SPEC.tail_n):
            lag = 0.55 * i                                          # each bone after the one before: a whip
            p.tail[i][1] += 4.0 * sweep(f - lag)
            p.tail[i][0] += K([(0, 0), (12, 1.0), (24, -0.6), (40, -0.4), (54, 0)], f - lag) * (1 if i < 6 else 0.3)
        body = K([(0, 0), (12, -1.0), (22, 0.8), (30, 1.0), (44, 0.2), (54, 0)], f)   # the trunk turns against it
        p.yaw = 10 * body
        p.hips = [0, -8 * body, 0]
        for i in range(3):
            p.spine[i][1] = -3 * body
        p.roll = 4 * body
        p.body = Vector((0.15 * body, 0, -0.05 * abs(body)))
        _neck_wave(p, -6 * abs(body), 36 * body)                    # looking back at the tail
        p.head = [4 * abs(body), 14 * body, 8 * body]
        p.jaw = K([(0, 0), (12, 6), (24, 24), (34, 14), (54, 0)], f)
        p.wing_lift = 4 * abs(body)
        for s in (1, -1):                                           # the hind feet shuffle to keep their footing
            H0 = neutral(('H', s))
            if s > 0:
                hop = K([(0, 0), (16, 0), (20, 1), (24, 0), (54, 0)], f)
            else:
                hop = K([(0, 0), (34, 0), (38, 1), (42, 0), (54, 0)], f)
            lp = LegPose(target=H0 + Vector((0.12 * body, 0, 0.18 * hop)))
            lp.flex = 20 * hop
            p.legs[('H', s)] = lp
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- fire and roar
def _clip_fire():
    """Fire breath: draws a deep breath (neck back, chest swelling, wings half raised), lunges into it -- the neck
    low and the head level, dragon_pose's fire pose -- and breathes fire from Socket_Mouth, sweeping its head from
    side to side (events 'Fire' at 0.9 s and 'FireEnd' at 2.0 s), then closes its jaws and settles."""
    N = 75

    def fn(f):
        p = DragonPose()
        inhale = K([(0, 0), (22, 1), (27, 0.2), (30, 0), (75, 0)], f)
        breathe = K([(0, 0), (22, 0), (28, 1), (60, 1), (70, 0), (75, 0)], f)
        sweep = math.sin(2 * math.pi * (f - 28) / 32) * breathe
        p.body = Vector((0, 0.20 * inhale - 0.25 * breathe, 0.02 * inhale - 0.06 * breathe))
        p.pitch = 3 * inhale - 4 * breathe
        p.spine[2][0] = 4 * inhale - 6 * breathe                        # the chest swells, then drives the breath
        for i, a in enumerate(DP.NECK_FIRE):
            p.neck[i][0] += a * breathe
        _neck_wave(p, 16 * inhale, 10 * sweep)
        p.head = [30 * breathe - 14 * inhale, 6 * sweep, 3 * sweep]
        p.jaw = 8 * inhale + 40 * breathe + 1.5 * math.sin(2 * math.pi * f / 4) * breathe
        p.wing_open = 0.45 * max(inhale, breathe)
        p.wing_lift = 3 * inhale
        _tail_wave(p, 1.0, 2 * math.pi * f / 37, lift=6 * inhale - 3 * breathe)
        for s_ in (1, -1):                                              # braced: the forepaws spread a little
            F0 = neutral(('F', s_))
            lp = LegPose(target=F0 + Vector((0.10 * s_ * breathe, -0.10 * breathe, 0)))
            lp.scap = -6 * breathe
            p.legs[('F', s_)] = lp
        return p
    return N, fn, False


def _clip_roar():
    """Rears up onto its haunches, throws its wings up and out, and roars at the sky then down at you (event
    'Roar' at 0.6 s); comes back down onto its forefeet with a thud."""
    N = 66

    def fn(f):
        p = DragonPose()
        up = K([(0, 0), (16, 1), (46, 1), (56, -0.08), (60, 0), (66, 0)], f)
        u = max(up, 0.0)
        pivot(p, 18 * u)
        p.body += Vector((0, 0.10 * u, 0.8 * min(up, 0.0)))                # (the landing thud)
        p.hips = [-6 * u, 0, 0]
        roar = K([(0, 0), (16, 0), (19, 1), (44, 1), (50, 0), (66, 0)], f)
        look = K([(0, 0), (19, 1), (30, 1), (40, 0), (66, 0)], f)          # at the sky first, then down at you
        _neck_wave(p, -14 * u + 14 * roar * look - 6 * roar * (1 - look), 4 * math.sin(2 * math.pi * f / 22) * roar)
        p.head = [-12 * u + 22 * roar - 10 * look * roar, 0, 4 * math.sin(2 * math.pi * f / 22) * roar]
        p.jaw = 46 * roar + 2.5 * math.sin(2 * math.pi * f / 5) * roar + 8 * K([(0, 0), (8, 1), (16, 0)], f)
        p.wing_open = 0.9 * K([(0, 0), (8, 0.2), (18, 1), (44, 1), (56, 0), (66, 0)], f)
        p.wing_lift = 4 * roar * math.sin(2 * math.pi * f / 11)
        _tail_wave(p, 1.4, 2 * math.pi * f / 33, lift=-4 * u)            # the tail braces on the ground
        air = min(1.0, u * 2.0)
        for s_ in (1, -1):
            lp = LegPose(target=neutral(('F', s_)), wb=air)
            lp.boff = Vector((0.15 * s_, -0.25, 0.25)) * air             # forefeet drawn up before the chest
            lp.flex = -35 * air
            lp.toe = 15 * air
            lp.scap = 12 * air
            p.legs[('F', s_)] = lp
            p.legs[('H', s_)] = LegPose(target=neutral(('H', s_)), flex=-8 * u)
        return p
    return N, fn, False


# ----------------------------------------------------------------------------------------- hit and death
def _clip_hit():
    """Struck from the front-right: the head snaps away up and to its left, the body rocks back, the wings twitch
    open, a pained snarl; a small rebound."""
    N = 18

    def fn(f):
        p = DragonPose()
        k = K([(0, 0), (2, 1), (6, 0.8), (11, -0.2), (18, 0)], f)
        kp = max(k, 0.0)
        p.body = Vector((0.08 * k, 0.12 * k, -0.04 * kp))
        p.roll, p.yaw, p.pitch = 4 * k, 6 * k, 3 * k
        p.spine[2] = [-3 * k, 4 * k, 0]
        _neck_wave(p, 10 * k, 18 * k, phase=0.0)
        p.head = [12 * k, 16 * k, 12 * k]
        p.jaw = K([(0, 0), (2, 30), (7, 14), (12, 4), (18, 0)], f)
        p.wing_open = 0.25 * kp
        p.wing_to = "raised"
        for i in range(SPEC.tail_n):
            p.tail[i][1] += K([(0, 0), (3, -1.5), (9, 1.0), (18, 0)], f - 0.5 * i)
        for s_ in (1, -1):
            p.legs[('F', s_)].scap = -8 * k
            p.legs[('F', s_)].flex = 10 * kp
        return p
    return N, fn, False


DEATH_DROP = 0.88                  # the belly on the ground
DEATH_FORE = (0.15, -0.20, -30.0)  # forefeet: out, forward (m), paw flex (deg); further forward sank the elbows


def _death_pose(f):
    p = DragonPose()
    cry = K([(0, 0), (4, 1), (14, 1), (22, 0), (90, 0)], f)               # a last cry, head thrown up
    front = K([(0, 0), (16, 0), (30, 1), (90, 1)], f)                     # the forelegs buckle ...
    hind = K([(0, 0), (30, 0), (46, 1), (90, 1)], f)                      # ... then the hind legs
    neck = K([(0, 0), (40, 0), (58, 1), (62, 0.96), (90, 1)], f)          # the neck falls, the head hits the ground
    sway = math.sin(2 * math.pi * f / 26) * K([(0, 0), (8, 1), (40, 1), (50, 0), (90, 0)], f)
    p.body = Vector((0.10 * sway, 0.15 * cry,
                     -DEATH_DROP * (0.55 * front + 0.45 * hind) + 0.06 * cry))
    p.pitch = 6 * cry - 9 * front + 9 * hind                               # nose-down as the front drops first
    p.roll = 3 * sway
    p.spine[2][0] = -4 * neck
    _neck_wave(p, 18 * cry - 58 * neck, 12 * neck + 6 * sway, spread=BASE)
    p.head = [-16 * cry + 30 * neck, 10 * neck, 14 * neck]
    breath = K([(0, 0), (70, 0), (76, 1), (84, 0), (90, 0)], f)           # a last breath out
    p.jaw = 40 * cry + K([(0, 0), (22, 8), (58, 14), (64, 6), (90, 6)], f) + 6 * breath
    p.spine[1][0] = 2 * breath
    p.wing_open = 0.3 * cry
    p.wing_lift = -6 * K([(0, 0), (40, 0), (60, 1), (90, 1)], f)          # the wings sag
    twitch = K([(0, 0), (78, 0), (81, 1), (85, 0), (90, 0)], f)
    for i in range(SPEC.tail_n):
        p.tail[i][1] += 1.2 * sway + 3.0 * twitch * (i > 9)
        p.tail[i][0] += -2.0 * hind * (i < 4)
    for kind, s_ in LEGS:
        k_ = front if kind == 'F' else hind
        base = neutral((kind, s_))
        if kind == 'F':                                                    # forefeet slide forward and out
            lp = LegPose(target=base + Vector((DEATH_FORE[0] * s_, DEATH_FORE[1], 0)) * k_)
            lp.flex = DEATH_FORE[2] * k_
            lp.toe = 20 * k_
            lp.scap = 10 * k_
        else:                                                              # hind feet splay, hocks flat
            lp = LegPose(target=base + Vector((0.25 * s_, -0.10, 0)) * k_)
            lp.flex = -25 * k_
            lp.toe = 10 * k_
        p.legs[(kind, s_)] = lp
    return p


def _clip_death():
    return 90, _death_pose, False


# ----------------------------------------------------------------------------------------- flight
# Flight clips play at the Root's height like the rest (the skeleton stays where it stands); the Motion bone carries
# the travel, forward and -- in Takeoff and Land -- up and down, so the game must let root motion move it vertically.
FLY_N = 36                         # one wingbeat: 1.2 s (a 16 m span beats slowly)
FLY_SPEED = 10.0                   # m/s
GLIDE_SPEED = 14.0
STROKE = [(0, -55.0), (15, 38.0), (36, -55.0)]          # 'Y': up at the top of the beat, down at the bottom
SWEEP = [(0, 10.0), (15, -12.0), (36, 10.0)]            # 'Z': back at the top, forward through the downstroke
PITCH = [(0, -6.0), (8, 8.0), (15, 6.0), (36, -6.0)]    # 'X': leading edge down while it pushes
FOLD_UP = [(0, 0.10), (15, 0.0), (26, 0.40), (36, 0.10)]  # the hand drawn in on the way up
CURL = [(0, 2.0), (8, 9.0), (15, 6.0), (36, 2.0)]


def _beat(f, loop=FLY_N):
    """The wing's stroke at frame f of a beat (looped). -> p.wing dict"""
    return dict(turns=[('Y', K(STROKE, f, loop)), ('Z', K(SWEEP, f, loop)), ('X', K(PITCH, f, loop))],
                fold=K(FOLD_UP, f, loop), curl=K(CURL, f, loop))


def _mix_wing(a, b, t):
    """Blend two wing dicts (turn by turn, same axes in the same order)."""
    return dict(turns=[(ax, x * (1 - t) + y * t) for (ax, x), (_, y) in zip(a["turns"], b["turns"])],
                fold=a["fold"] * (1 - t) + b["fold"] * t, curl=a["curl"] * (1 - t) + b["curl"] * t)


GLIDE_WING = dict(turns=[('Y', -7.0), ('Z', 2.0), ('X', 3.0)], fold=0.0, curl=2.0)
WING_REACH = 7.5                   # shoulder to wingtip, m
SHOULDER_Z = 2.95                  # the wing's shoulder over the ground, standing


def _depth_cap(w, height, margin=0.4):
    """Near the ground the downstroke may only go as deep as the wingtips can without touching it: caps the 'Y'
    turn by the shoulder's height over the ground (m)."""
    cap = math.degrees(math.asin(max(-1.0, min(1.0, (height - margin) / WING_REACH))))
    w = dict(w)
    w["turns"] = [(ax, min(v, cap) if ax == 'Y' else v) for ax, v in w["turns"]]
    return w
FOLDED = dict(turns=[('Y', -7.0), ('Z', 2.0), ('X', 3.0)], fold=1.0, curl=0.0)


def _airborne(p, k=1.0, phase=0.0):
    """Flying posture by k (0 standing .. 1 flying): neck stretched forward and low, head level, legs tucked -- the
    forelegs folded up under the chest, the hind legs trailing -- tail streaming with a slow wave."""
    for i, a in enumerate(DP.NECK_FLY):
        p.neck[i][0] += a * k
    p.head[0] += 12 * k
    for i, a in enumerate((14, 6, 2)):
        p.tail[i][0] += a * k
    for i in range(SPEC.tail_n):
        p.tail[i][0] += 0.8 * k * math.sin(phase - 0.5 * i)
        p.tail[i][1] += 0.5 * k * math.sin(0.5 * phase - 0.4 * i)
    for kind, s_ in LEGS:
        lp = LegPose(target=p.root + neutral((kind, s_)), wb=k)
        if kind == 'F':
            lp.boff = Vector((0.0, 0.35, 0.70))
            lp.flex, lp.toe, lp.scap = -70 * k, -30 * k, -10 * k
        else:
            lp.boff = Vector((-0.10 * s_, 0.95, 0.75))
            lp.flex, lp.toe = 30 * k, -25 * k
        p.legs[(kind, s_)] = lp


def _clip_fly():
    """The flap loop: a slow, deep wingbeat (down fast, up slower with the hand drawn in), the body rising on each
    downstroke, the neck soaking it up so the head stays level; root motion 10 m/s."""
    N = FLY_N

    def fn(f):
        p = DragonPose()
        p.root = Vector((0, -FLY_SPEED * f / FPS, 0))
        a = 2 * math.pi * f / N
        _airborne(p, 1.0, a)
        bob = K([(0, -0.22), (17, 0.22), (36, -0.22)], f, N)
        p.body = Vector((0, 0, bob))
        p.pitch = K([(0, 1.5), (12, -2.0), (36, 1.5)], f, N)
        _neck_wave(p, -10 * bob, 0.0)
        p.head[0] += -8 * bob
        p.wing = _beat(f)
        return p
    return N, fn, True


def _clip_glide():
    """Gliding: wings held out with a slight dihedral, small corrections, a slow bank from side to side; root
    motion 14 m/s."""
    N = 60

    def fn(f):
        p = DragonPose()
        p.root = Vector((0, -GLIDE_SPEED * f / FPS, 0))
        a = 2 * math.pi * f / N
        _airborne(p, 1.0, a)
        p.roll = 3 * math.sin(a)
        p.body = Vector((0, 0, 0.05 * math.sin(2 * a)))
        _neck_wave(p, 0.0, -3 * math.sin(a))
        p.head[2] += -2 * math.sin(a)
        w = dict(GLIDE_WING)
        w["turns"] = [('Y', -7 + 2.5 * math.sin(2 * a + 0.5)), ('Z', 2 + 1.5 * math.sin(a)), ('X', 3 + math.sin(2 * a))]
        p.wing = w
        for i in range(SPEC.tail_n):
            p.tail[i][1] += 1.0 * math.sin(a - 0.3 * i)                 # the tail steers the bank
        return p
    return N, fn, True


def _clip_takeoff():
    """Crouches with the wings swept up, leaps (event 'TakeOff' at 0.63 s, the feet leave the ground), and climbs
    on three deep beats, the legs tucking up; ends at the top of a beat, as Fly starts. Root motion: 10 m forward,
    7 m up."""
    N = 66

    def fn(f):
        p = DragonPose()
        p.root = Vector((0, K([(0, 0), (16, 0), (22, -0.8), (34, -3.0), (48, -6.2), (66, -10.0)], f),
                         K([(0, 0), (16, 0), (22, 0.8), (34, 2.4), (48, 4.4), (66, 7.0)], f)))
        air = K([(0, 0), (17, 0), (30, 1), (66, 1)], f)
        crouch = K([(0, 0), (12, 1), (16, 1), (20, -0.3), (26, 0), (66, 0)], f)
        p.body = Vector((0, 0.10 * crouch, -0.35 * crouch))
        p.pitch = -4 * max(crouch, 0) + K([(0, 0), (16, 0), (20, 12), (36, 3), (66, 0)], f)
        _airborne(p, air, 2 * math.pi * f / FLY_N)
        for kind, s_ in LEGS:                                       # before the leap: feet planted, then pushing off
            if air < 1e-3:
                lp = LegPose(target=neutral((kind, s_)))
                lp.flex = (-20 if kind == 'H' else 10) * max(crouch, 0)
                p.legs[(kind, s_)] = lp
        p.neck[0][0] += 8 * max(crouch, 0)
        p.head[0] += -10 * max(crouch, 0)
        p.jaw = 10 * K([(0, 0), (16, 0), (20, 1), (30, 0), (66, 0)], f)
        up = dict(turns=[('Y', -55.0), ('Z', 10.0), ('X', -6.0)], fold=0.1, curl=2.0)
        if f <= 14:                                                  # opening and sweeping up out of the fold
            k = ease(f / 14)
            p.wing = dict(turns=up["turns"], fold=1 - 0.9 * k, curl=2.0)
        else:                                                        # three beats, the first the deepest
            beat = K([(14, 0), (24, 15), (40, 36), (50, 51), (66, 72)], f)
            p.wing = _depth_cap(_beat(beat), SHOULDER_Z + p.root.z + p.body.z)
        return p
    return N, fn, False


def _clip_land():
    """Glides in, flares -- nose up, wings swept forward and back-beating to brake -- reaches down with the hind
    feet (event 'Land' at 1.4 s), then the forefeet, sinks into the landing and folds its wings. Root motion: 15.6 m
    forward, 7 m down."""
    N = 72
    anchor = Vector((0, -15.6, 0))

    def fn(f):
        p = DragonPose()
        p.root = Vector((0, K([(0, 0), (20, -9.0), (36, -14.0), (44, -15.4), (48, -15.6), (72, -15.6)], f),
                         K([(0, 7.0), (20, 4.2), (32, 1.6), (42, 0.0), (72, 0.0)], f)))
        air = K([(0, 1), (30, 1), (46, 0), (72, 0)], f)
        a = 2 * math.pi * f / FLY_N
        _airborne(p, air, a)
        flare = K([(0, 0), (18, 0), (30, 1), (42, 0.6), (50, 0), (72, 0)], f)
        sink = K([(0, 0), (42, 0), (48, 1), (58, 0.3), (72, 0)], f)
        p.pitch = 22 * flare - 4 * sink
        p.body = Vector((0, 0, -0.35 * sink))
        _neck_wave(p, -10 * flare, 0.0)
        p.head[0] += -14 * flare
        hind = K([(0, 1), (32, 1), (42, 0), (72, 0)], f)
        front = K([(0, 1), (38, 1), (47, 0), (72, 0)], f)
        for kind, s_ in LEGS:                                        # legs reach down for the ground
            k = hind if kind == 'H' else front
            lp = p.legs[(kind, s_)]
            lp.target = anchor + neutral((kind, s_))
            lp.wb = k
            if kind == 'H':
                lp.flex = 30 * k - 15 * sink
            else:
                lp.flex = -70 * k + 12 * sink
            lp.toe = -25 * k
            lp.scap = -10 * k
        brake = dict(turns=[('Y', 30.0), ('Z', -28.0), ('X', -14.0)], fold=0.0, curl=10.0)
        top = dict(turns=[('Y', -40.0), ('Z', -20.0), ('X', -10.0)], fold=0.2, curl=4.0)
        settle = dict(turns=[('Y', -35.0), ('Z', 4.0), ('X', 0.0)], fold=0.25, curl=2.0)
        if f < 20:
            w = dict(GLIDE_WING)
        elif f < 44:                                                  # two braking beats
            ph = K([(20, 0), (30, 1), (36, 0), (44, 1)], f)
            w = _mix_wing(_mix_wing(GLIDE_WING, top, min(1.0, (f - 20) / 6)), brake, ph)
        elif f < 52:                                                  # down: the wings lift clear of the ground ...
            w = _mix_wing(brake, settle, ease((f - 44) / 8))
        else:                                                         # ... and fold away
            k = ease((f - 52) / 16)
            w = _mix_wing(settle, FOLDED, k)
            w["fold"] = settle["fold"] * (1 - k) + k
        p.wing = _depth_cap(w, SHOULDER_Z + p.root.z + p.body.z)
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run, "Bite": _clip_bite, "Claw": _clip_claw,
         "TailSweep": _clip_tail, "Fire": _clip_fire, "Roar": _clip_roar, "Hit": _clip_hit, "Death": _clip_death,
         "Takeoff": _clip_takeoff, "Fly": _clip_fly, "Glide": _clip_glide, "Land": _clip_land}


# ----------------------------------------------------------------------------------------- build
def pose_matrices(p):
    return BA.pose_matrices(SPEC, p)


def build_clip(name, rig_ob=None):
    return BA.build_clip(SPEC, CLIPS, EVENTS, name, rig_ob)


def tail_floor(mesh="DragonBody", margin=0.03):
    """Per tail bone: how high its end must stay so the tail's underside stays on the ground -- the skin's depth
    below the bone's end (rest), plus a margin. (A flat 10 cm let the 30 cm thick tail root sink into the ground
    when it reared.)"""
    import numpy as np
    B = BA.rest_data(SPEC)['B']
    co = np.array([v.co[:] for v in bpy.data.objects[mesh].data.vertices])
    out = []
    for i in range(SPEC.tail_n):
        h, fr, L, par, d = B[f"Tail{i + 1}"]
        end = np.array(h + fr.col[1] * L)
        near = (np.abs(co[:, 1] - end[1]) < 0.15) & (np.abs(co[:, 0]) < 1.0)
        depth = end[2] - co[near, 2].min() if near.any() else 0.1
        out.append(float(depth + margin))
    return out


def build_clips(names=None):
    SPEC.rest.clear()
    _AIMS.clear()
    SPEC.tail_floor = tail_floor()
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig_ob=None):
    BA.use(SPEC, name, rig_ob)


def clear(rig_ob=None):
    BA.clear(SPEC, rig_ob)


def still(p, rig_ob=None):
    BA.still(SPEC, p, rig_ob)


AIRBORNE = {"Fly", "Glide"}         # played with the Root up in the air: no ground to check


def report(names=None, step=16):
    """Lowest point per clip (sampled) over the ground, counting the root motion's height (Takeoff and Land climb
    and descend on the Motion bone): nothing should go much under the ground. The wing membrane counts too."""
    import numpy as np
    rig = bpy.data.objects[RIG]
    scn = bpy.context.scene
    res = {}
    for name in [n for n in (names or CLIPS) if n not in AIRBORNE]:
        use(name)
        N = int(bpy.data.actions[SPEC.action_name(name)]["frames"])
        lo = 1e9
        for f in range(0, N + 1, max(1, N // step)):
            scn.frame_set(f)
            up = rig.pose.bones["Motion"].head.z
            dg = bpy.context.evaluated_depsgraph_get()
            for mesh in ("DragonBody", "DragonWingMembrane"):
                ob = bpy.data.objects[mesh]
                me = ob.evaluated_get(dg).to_mesh()
                co = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get('co', co)
                lo = min(lo, float(co.reshape(-1, 3)[:, 2].min()) + up)
                ob.evaluated_get(dg).to_mesh_clear()
        res[name] = round(lo, 3)
    clear()
    return res
