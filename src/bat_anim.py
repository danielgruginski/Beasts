"""Giant bat clips (2026-10-23), keyed straight onto BatRig with beast_rig.apply_pose.

The quadrupeds' clip machinery (beast_anim) wants four legs, so the bat has a small pose system of its own in the
hen's style (chicken_anim), with the dragon's wings (dragon_anim._wings): a Pose per frame (root travel on Motion; the
trunk's offset / pitch / roll / yaw about its centre; spine, neck, head, jaw and ear bends; per wing a stroke
dict(turns, fold, curl, thumb): the spread wing turned about the shoulder, blended bone by bone toward the folded wing
by `fold` (shortest rotation), the fingers curled; per hind leg FK bends) -> armature-space matrices
(pose_matrices), with the arm panels' helper bones placed by dragon_body.membrane_pose. The skeleton plays in place;
Motion travels (Unity root motion), as for the beasts.

The bind pose is the flying pose at hover height (bat_body.H); every clip but Death stays up there. Clips (30 fps,
facing -Y; Unity +Z):
  Idle     1.6 s loop   a lazy hover: two slow beats, the body raised, legs hanging, head looking round, ear flicks
  Hover    1.07 s loop  the tense hover facing a target: two quicker beats, body upright, jaw ajar, ears forward
  Fly      0.67 s loop  one wingbeat: down fast and forward, up with the hand drawn in; root motion 4.5 m/s
  Dive     1.5 s        the attack: rears up, half folds and swoops 1 m forward and 0.8 m down to bite (event 'Bite'
                        at 0.73 s), the hind claws reaching, then beats back up to the hover spot (in place)
  Screech  1.8 s        rears with the wings spread wide, head thrust out, jaw wide, ears back (event 'Screech' 0.5 s)
  Hit      0.5 s        knocked back and up, the wings flinch, recovers to the hover
  Death    2.0 s        the wings jerk and fold, it drops tumbling to the ground and lies on its belly, the wings
                        spread flat, the head turned on the ground (event 'Dead' at 1.3 s); holds
"""
import bpy, math
from mathutils import Vector, Matrix
import beast_rig
import beast_anim as BA
from beast_anim import K, ease
import dragon_body as DB
import bat_body as BB

FPS = 30
RIG = BB.RIG
H = BB.H
C = Vector(BB.h(0, 0.02, 0.0))                   # the trunk's pivot
SIDES = BB.SIDES
EVENTS = {"Dive": [("Bite", 0.73)], "Screech": [("Screech", 0.5)], "Death": [("Dead", 1.3)]}
MOVING = {"Fly"}


def rad(d):
    return math.radians(d)


def _rot(p=0.0, y=0.0, r=0.0):
    return Matrix.Rotation(rad(p), 4, 'X') @ Matrix.Rotation(rad(y), 4, 'Z') @ Matrix.Rotation(rad(r), 4, 'Y')


def wing(Y=0.0, Z=0.0, X=0.0, fold=0.0, curl=0.0, thumb=0.0):
    """A wing stroke: the spread wing turned about the shoulder -- 'Y' + down / - up, 'Z' + sweeps it back, 'X' +
    pitches the leading edge down -- drawn `fold` (0..1) toward the folded wing, each finger joint curled `curl` deg
    down (a cupped stroke)."""
    return dict(turns=[('Y', Y), ('Z', Z), ('X', X)], fold=fold, curl=curl, thumb=thumb)


def mix_wing(a, b, t):
    return dict(turns=[(ax, x * (1 - t) + y * t) for (ax, x), (_, y) in zip(a["turns"], b["turns"])],
                fold=a["fold"] * (1 - t) + b["fold"] * t, curl=a["curl"] * (1 - t) + b["curl"] * t,
                thumb=a.get("thumb", 0) * (1 - t) + b.get("thumb", 0) * t)


class Pose:
    def __init__(self):
        self.root = Vector()
        self.body = Vector()
        self.pitch = self.roll = self.yaw = 0.0           # trunk, deg (pitch + = nose up)
        self.hips = [0.0, 0.0, 0.0]
        self.spine = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]   # Spine1, Chest
        self.neck = [0.0, 0.0, 0.0]                       # + pitch raises the head, + yaw turns it left
        self.head = [0.0, 0.0, 0.0]
        self.jaw = 0.0
        self.ears = {1: [0.0, 0.0], -1: [0.0, 0.0]}      # (+ forward / - back, + splay out)
        self.wing = {1: wing(), -1: wing()}
        self.legs = {1: [[0.0, 0.0, 0.0], 0.0, 0.0, 0.0], -1: [[0.0, 0.0, 0.0], 0.0, 0.0, 0.0]}  # thigh, knee, foot, toes
        self.floor = 0.0                                  # no wing joint or finger tip under this (world z)


# ----------------------------------------------------------------------------------------- rest data and wing aims
_REST = {}


def rest():
    if not _REST:
        B = BB.rest_bones()
        _REST['B'] = B
        _REST['R'] = {n: beast_rig.frame_matrix(h, fr) for n, (h, fr, L, par, d) in B.items()}
    return _REST


# the folded wing (left, armature space with the chest at rest): the humerus out and back, the forearm forward along
# the flank, the hand and the fingers folded back along the forearm; the membrane's upper side faces out
FOLD = {
    "WingArm": ((0.45, 0.80, -0.40), (0.80, -0.20, 0.55)),
    "WingForearm": ((0.12, -0.95, -0.30), (0.97, 0.05, 0.25)),
    "WingHand": ((0.10, -0.98, -0.18), (0.99, 0.0, 0.12)),
    "WingThumb": ((0.20, -0.90, 0.38), (0.98, 0.0, 0.18)),
    "F1": ((0.04, 0.99, -0.10), (0.99, 0.0, 0.10)),
    "F2": ((0.06, 0.98, -0.18), (0.99, 0.0, 0.10)),
    "F3": ((0.08, 0.96, -0.27), (0.99, 0.0, 0.10)),
    "F4": ((0.10, 0.93, -0.35), (0.99, 0.0, 0.10)),
}


def _fold_aims():
    if 'fold' not in _REST:
        aim = {}
        for s, sfx in SIDES:
            mx = lambda v: (v[0] * s, v[1], v[2])
            for key, (d, z) in FOLD.items():
                if key.startswith("F"):
                    i = int(key[1]) - 1
                    for k in range(BB.SEGS[i]):
                        aim[f"WingF{i + 1}_{k + 1}{sfx}"] = (mx(d), mx(z))
                else:
                    aim[key + sfx] = (mx(d), mx(z))
        _REST['fold'] = aim
    return _REST['fold']


def _turned(s, sfx, w):
    """Aims of one wing: the spread (rest) wing turned rigidly about the shoulder by w['turns'] (mirrored for the
    right), the fingers curled."""
    R = rest()['R']
    M = Matrix.Identity(3)
    for ax, deg in w["turns"]:
        M = Matrix.Rotation(rad(deg if (s > 0 or ax == 'X') else -deg), 3, ax) @ M
    aim = {}
    for n in DB.wing_chain(sfx, BB.WS):
        d, z = M @ R[n].col[1].xyz, M @ R[n].col[2].xyz
        if n.startswith("WingF") and n[5].isdigit():
            k = int(n.split("_")[1][0])
            c = Matrix.Rotation(rad(-w["curl"] * k), 3, d.cross(z).normalized())
            d, z = c @ d, c @ z
        elif n.startswith("WingThumb") and w.get("thumb"):
            c = Matrix.Rotation(rad(w["thumb"]), 3, d.cross(z).normalized())
            d, z = c @ d, c @ z
        aim[n] = (d, z)
    return aim


def _place_wing(p, Wm, rel, s, sfx, w, turn):
    """One wing's bones into Wm for the stroke w. -> the lowest z of its joints and finger tips."""
    D = rest()
    B = D['B']
    fold = _fold_aims()
    alt = _turned(s, sfx, w)
    t = 1.0 - min(max(w["fold"], 0.0), 1.0)
    n = f"WingScap{sfx}"
    Wm[n] = Wm["Chest"] @ rel(n, "Chest")
    lo = 9.0
    for n in DB.wing_chain(sfx, BB.WS):
        par = B[n][3]
        here = Wm[par] @ rel(n, par)
        q = DB._frame(*fold[n]).to_quaternion().slerp(DB._frame(*alt[n]).to_quaternion(), t)
        Wm[n] = Matrix.Translation(here.translation) @ (turn @ q.to_matrix()).to_4x4()
        tip = Wm[n].translation + Wm[n].col[1].xyz * B[n][2]
        lo = min(lo, Wm[n].translation.z, tip.z)
    return lo + p.root.z


def _wings(p, Wm, rel):
    """The wings ride on the chest; each bone turns from the folded aim toward the turned spread wing along the
    shortest rotation (the dragon's way). A stroke that would put a joint or a finger tip under p.floor is lifted:
    its 'Y' turn (down) is bisected until the wing clears the floor by 2 cm (lying dead, diving low)."""
    D = rest()
    R = D['R']
    turn = Wm["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    for s, sfx in SIDES:
        w = p.wing[s]
        lo = _place_wing(p, Wm, rel, s, sfx, w, turn)
        if p.floor is not None and lo < p.floor + 0.02:
            y0 = dict(w["turns"])['Y']
            a, b = -80.0, y0                       # a: high enough (assumed clear), b: too low
            for _ in range(12):
                mid = 0.5 * (a + b)
                ww = dict(w)
                ww["turns"] = [(ax, mid if ax == 'Y' else v) for ax, v in w["turns"]]
                if _place_wing(p, Wm, rel, s, sfx, ww, turn) < p.floor + 0.02:
                    b = mid
                else:
                    a = mid
            ww = dict(w)
            ww["turns"] = [(ax, a if ax == 'Y' else v) for ax, v in w["turns"]]
            _place_wing(p, Wm, rel, s, sfx, ww, turn)
    DB.membrane_pose(Wm, R, BB.WS)


def pose_matrices(p):
    D = rest()
    R = D['R']
    rel = lambda c, par: R[par].inverted() @ R[c]
    M = Matrix.Translation(p.root)
    BT = (Matrix.Translation(C + p.body) @ Matrix.Rotation(rad(p.yaw), 4, 'Z') @
          Matrix.Rotation(rad(-p.pitch), 4, 'X') @ Matrix.Rotation(rad(p.roll), 4, 'Y') @ Matrix.Translation(-C))
    MB = M @ BT
    W = {"Root": M @ R["Root"]}
    W["Hips"] = MB @ R["Hips"] @ _rot(*p.hips)
    W["Spine1"] = MB @ R["Spine1"] @ _rot(*p.spine[0])
    W["Chest"] = W["Spine1"] @ rel("Chest", "Spine1") @ _rot(*p.spine[1])
    W["Neck1"] = W["Chest"] @ rel("Neck1", "Chest") @ _rot(*p.neck)
    W["Head"] = W["Neck1"] @ rel("Head", "Neck1") @ _rot(*p.head)
    W["Jaw"] = W["Head"] @ rel("Jaw", "Head") @ _rot(-p.jaw)
    for s, sfx in SIDES:
        e = p.ears[s]
        W[f"Ear{sfx}"] = W["Head"] @ rel(f"Ear{sfx}", "Head") @ _rot(e[0], -s * e[1])
        th, kn, ft, to = p.legs[s]
        mir = lambda a: _rot(a[0], s * a[1], s * a[2])
        W[f"Thigh{sfx}"] = W["Hips"] @ rel(f"Thigh{sfx}", "Hips") @ mir(th)
        W[f"Shin{sfx}"] = W[f"Thigh{sfx}"] @ rel(f"Shin{sfx}", f"Thigh{sfx}") @ _rot(kn)
        W[f"HindFoot{sfx}"] = W[f"Shin{sfx}"] @ rel(f"HindFoot{sfx}", f"Shin{sfx}") @ _rot(ft)
        W[f"HindToes{sfx}"] = W[f"HindFoot{sfx}"] @ rel(f"HindToes{sfx}", f"HindFoot{sfx}") @ _rot(to)
    _wings(p, W, rel)
    W["Socket_Head"] = W["Head"] @ rel("Socket_Head", "Head")
    W["Socket_Mouth"] = W["Jaw"] @ rel("Socket_Mouth", "Jaw")
    Minv = M.inverted()
    out = {k: Minv @ v for k, v in W.items()}
    out["Motion"] = M @ R["Motion"]
    return out


# ----------------------------------------------------------------------------------------- strokes
def beat(f, N, Y=(-58.0, 46.0), Z=(12.0, -14.0), X=(-4.0, 8.0), fold=0.38, curl=(2.0, 8.0), down=0.42):
    """One wingbeat over N frames at frame f (looped): from the top (frame 0) the downstroke takes `down` of the
    beat, the wing fully out and cupped, sweeping forward; the upstroke draws the hand in (`fold` at its middle) and
    sweeps back. Y, Z, X, curl: (top, bottom)."""
    q = (f % N) / N
    if q < down:
        u = ease(q / down)
        fo = 0.0
        xk = X[0] + (X[1] - X[0]) * math.sin(math.pi * q / down) ** 2
    else:
        v = (q - down) / (1 - down)
        u = 1 - ease(v)
        fo = fold * math.sin(math.pi * v) ** 2
        xk = X[0]
    lerp = lambda ab: ab[0] + (ab[1] - ab[0]) * u
    return wing(lerp(Y), lerp(Z), xk, fo, lerp(curl))


def depth_cap(w, shoulder_z, margin=0.06):
    """Near the ground the downstroke goes only as deep as the wingtip can without touching it."""
    cap = math.degrees(math.asin(max(-1.0, min(1.0, (shoulder_z - margin) / BB.REACH))))
    w = dict(w)
    w["turns"] = [(ax, min(v, cap) if ax == 'Y' else v) for ax, v in w["turns"]]
    return w


def _legs_flight(p, k=1.0, swing=0.0):
    """The hind legs trail, the feet curled; k 0..1 hangs them down (hovering), swing follows the beat."""
    for s in (1, -1):
        p.legs[s] = [[-55 * k + 6 * swing, 6 * k, 0.0], 40 * k + 4 * swing, -10 * k, -25 - 10 * k]


# ----------------------------------------------------------------------------------------- clips
FLY_N, FLY_SPEED = 20, 4.5


def _clip_fly():
    N = FLY_N

    def fn(f):
        p = Pose()
        p.root = Vector((0, -FLY_SPEED * f / FPS, 0))
        w = beat(f, N)
        p.wing = {1: w, -1: w}
        q = f / N
        bob = 0.035 * math.sin(2 * math.pi * (q - 0.15))
        p.body = Vector((0, 0, bob))
        p.pitch = 2.0 * math.sin(2 * math.pi * (q + 0.1))
        p.neck = [-6 - 8 * bob / 0.035 * 0.3, 0, 0]
        p.head = [6 - 3 * math.sin(2 * math.pi * q), 0, 0]
        _legs_flight(p, 0.0, math.sin(2 * math.pi * q))
        for s in (1, -1):
            p.ears[s] = [-18, -6]
        return p
    return N, fn, True


def _hover_wing(f, N, hard=1.0):
    """The hover's beat: the stroke plane tilted with the upright body, more sweep, the hand drawn in deeply on the
    way back (a bat's hover is a figure of eight)."""
    return beat(f, N, Y=(-50.0 * hard, 36.0 * hard), Z=(22.0, -24.0), X=(-10.0, 14.0), fold=0.48, curl=(2, 10),
                down=0.45)


def _clip_idle():
    N = 48                                  # two slow beats

    def fn(f):
        p = Pose()
        b = 24
        w = _hover_wing(f, b, 0.9)
        p.wing = {1: w, -1: w}
        q = (f % b) / b
        p.pitch = 30 + 3 * math.sin(2 * math.pi * q)
        p.body = Vector((0, 0.02, 0.05 * math.sin(2 * math.pi * (q - 0.2))))
        look = K([(0, 0), (8, 0), (14, 28), (26, 28), (32, -20), (40, -20), (46, 0), (48, 0)], f, N)
        p.neck = [-24, look * 0.4, 0]
        p.head = [-6, look * 0.6, look * 0.2]
        flick = K([(0, 0), (30, 0), (32, 1), (34, -0.4), (36, 0), (48, 0)], f, N)
        p.ears = {1: [-4 + 18 * flick, 4], -1: [-4, 4]}
        _legs_flight(p, 0.8, math.sin(2 * math.pi * q))
        return p
    return N, fn, True


def _clip_hover():
    N = 32                                  # two quick beats

    def fn(f):
        p = Pose()
        b = 16
        w = _hover_wing(f, b, 1.0)
        p.wing = {1: w, -1: w}
        q = (f % b) / b
        p.pitch = 42 + 3 * math.sin(2 * math.pi * q)
        p.body = Vector((0, 0.04, 0.06 * math.sin(2 * math.pi * (q - 0.2))))
        p.neck = [-36, 0, 0]
        p.head = [-8 + 3 * math.sin(2 * math.pi * f / N), 0, 0]
        p.jaw = 10 + 4 * math.sin(2 * math.pi * f / N)
        p.ears = {s: [14, 2] for s in (1, -1)}
        _legs_flight(p, 1.0, math.sin(2 * math.pi * q))
        for s in (1, -1):
            p.legs[s][0][0] += 12                     # the claws held forward
        return p
    return N, fn, True


DIVE_AT = 22                                # the bite


def _clip_dive():
    N = 45

    def fn(f):
        p = Pose()
        # the body's path: rear up and back (0-10), swoop forward and down (10-22), pull up and back (22-45)
        y = K([(0, 0.02), (8, 0.10), (14, -0.30), (DIVE_AT, -1.00), (28, -0.85), (36, -0.35), (45, 0.02)], f)
        z = K([(0, 0.0), (8, 0.25), (14, 0.05), (DIVE_AT, -0.80), (28, -0.62), (36, -0.20), (45, 0.0)], f)
        p.body = Vector((0, y, z))
        p.pitch = K([(0, 30), (8, 45), (14, -10), (20, -38), (DIVE_AT, -30), (26, 10), (32, 35), (45, 30)], f)
        p.neck = [K([(0, -24), (8, 10), (16, -10), (DIVE_AT, -2), (28, -20), (45, -24)], f), 0, 0]
        p.head = [K([(0, -6), (8, 6), (18, 18), (DIVE_AT, 10), (30, -6), (45, -6)], f), 0, 0]
        p.jaw = K([(0, 6), (12, 8), (18, 40), (DIVE_AT - 1, 42), (DIVE_AT + 1, 2), (26, 4), (45, 6)], f)
        p.ears = {s: [K([(0, -4), (12, -30), (DIVE_AT, -38), (30, -10), (45, -4)], f), 2] for s in (1, -1)}
        # wings: a big upstroke as it rears, half folded through the swoop, two hard beats back up
        if f < 10:
            w = mix_wing(_hover_wing(0, 24), wing(-62, 10, -6, 0.15, 2), ease(f / 8))
        elif f < 22:
            t = ease((f - 10) / 8)
            w = mix_wing(wing(-62, 10, -6, 0.15, 2), wing(-20, 18, 4, 0.55, 0), t)
        else:
            w = _hover_wing(f - 22, 12, 1.25)
            w = mix_wing(wing(-20, 18, 4, 0.55, 0), w, ease((f - 22) / 4))
            if f > 38:
                w = mix_wing(w, _hover_wing(0, 24, 0.9), ease((f - 38) / 7))
        sh = H + z + 0.05
        w = depth_cap(w, sh)
        p.wing = {1: w, -1: w}
        reach = K([(0, 0), (14, 0), (20, 1), (24, 1), (32, 0), (45, 0)], f)
        for s in (1, -1):
            p.legs[s] = [[-44 + 60 * reach, 8, 0.0], 36 - 20 * reach, -10, -30 + 35 * reach]
        return p
    return N, fn, False


def _clip_screech():
    N = 54

    def fn(f):
        p = Pose()
        up = K([(0, 0), (8, 1), (44, 1), (54, 0)], f)
        b = 18
        w = _hover_wing(f, b, 0.75)
        spread = wing(-38, 6, -4, 0.0, 0, thumb=-10)
        shake = math.sin(2 * math.pi * f / 5) * K([(0, 0), (12, 0), (16, 1), (40, 1), (46, 0), (54, 0)], f)
        w = mix_wing(w, spread, 0.65 * up)
        w["turns"][0] = ('Y', w["turns"][0][1] + 3 * shake)
        p.wing = {1: w, -1: w}
        q = (f % b) / b
        p.pitch = 30 + 18 * up
        p.body = Vector((0, 0.02 + 0.06 * up, 0.12 * up + 0.04 * math.sin(2 * math.pi * (q - 0.2))))
        p.neck = [-24 - 6 * up, 0, 0]
        p.head = [-6 - 4 * up + 2 * shake, 0, 0]
        p.jaw = K([(0, 6), (10, 8), (15, 44), (40, 46), (48, 8), (54, 6)], f) + 2 * shake
        p.ears = {s: [K([(0, -4), (12, -40), (42, -40), (54, -4)], f), 10 * up] for s in (1, -1)}
        _legs_flight(p, 0.8, 0)
        return p
    return N, fn, False


def _clip_hit():
    N = 15

    def fn(f):
        p = Pose()
        k = K([(0, 0), (3, 1), (7, 0.55), (11, -0.15), (15, 0)], f)
        b = 24
        base = _hover_wing(f, b, 0.9)
        flinch = wing(-45, -10, -8, 0.40, 0)
        w = mix_wing(base, flinch, max(k, 0) * 0.8)
        p.wing = {1: w, -1: depth_cap(mix_wing(w, wing(-20, 0, 0, 0.5, 0), 0.3 * max(k, 0)), H)}
        q = (f % b) / b
        p.pitch = 30 + 22 * k
        p.roll = -14 * k
        p.yaw = 8 * k
        p.body = Vector((0.03 * k, 0.02 + 0.18 * k, 0.06 * k + 0.05 * math.sin(2 * math.pi * (q - 0.2))))
        p.neck = [-24 + 18 * k, -8 * k, 0]
        p.head = [-6 + 14 * k, -10 * k, 8 * k]
        p.jaw = 6 + 26 * K([(0, 0), (3, 1), (8, 0.3), (15, 0)], f)
        p.ears = {s: [-4 - 30 * max(k, 0), 4] for s in (1, -1)}
        _legs_flight(p, 0.8, 0)
        for s in (1, -1):
            p.legs[s][1] += 30 * max(k, 0)
        return p
    return N, fn, False


DEATH_Z = 0.105                              # the body's centre, lying on its belly
LAND = 21


def _clip_death():
    N = 60

    def fn(f):
        p = Pose()
        if f <= 6:
            drop = 0.0
        elif f <= LAND:
            drop = ((f - 6) / (LAND - 6)) ** 2
        else:
            drop = 1.0
        bounce = 0.05 * K([(LAND, 0), (LAND + 3, 1), (LAND + 6, 0), (N, 0)], f) if f > LAND else 0.0
        zc = (H + 0.04 * K([(0, 0), (4, 1), (6, 0.8)], f)) * (1 - drop) + DEATH_Z * drop + bounce
        p.body = Vector((0, -0.25 * drop, zc - H))
        p.pitch = K([(0, 30), (5, 46), (12, -20), (LAND, -8), (LAND + 4, -4), (N, -2)], f)
        p.roll = K([(0, 0), (8, -14), (15, 28), (LAND, 10), (LAND + 5, 4), (N, 4)], f)
        p.yaw = K([(0, 0), (12, 10), (LAND, 16), (N, 16)], f)
        jerk = K([(0, 0), (3, 1), (8, 0.3)], f)
        dn = K([(0, 0), (LAND - 2, 0), (LAND + 6, 1), (N, 1)], f)
        p.neck = [-24 + 30 * jerk + 16 * dn, 32 * dn, 0]
        p.head = [-6 + 10 * jerk - 4 * dn, 18 * dn, 26 * dn]
        p.jaw = K([(0, 6), (3, 34), (14, 20), (LAND + 4, 10), (N, 8)], f)
        p.ears = {s: [K([(0, -4), (4, 10), (16, -30), (N, -38)], f), K([(0, 4), (LAND + 6, 16), (N, 18)], f)]
                  for s in (1, -1)}
        # wings: a jerk up, folding as it drops, flopping out flat on impact
        up = wing(-55, -8, -8, 0.10, 0)
        falling = wing(-35, 12, 2, 0.58, 4)
        flat = wing(1.0, 4, 0, 0.30, -6)
        if f < 6:
            w = mix_wing(_hover_wing(f, 24, 0.9), up, ease(f / 5))
        elif f < LAND:
            w = mix_wing(up, falling, ease((f - 6) / 9))
        else:
            w = mix_wing(falling, flat, ease((f - LAND) / 7))
        wl = depth_cap(w, zc + 0.05)
        wr = depth_cap(mix_wing(w, wing(w["turns"][0][1] - 4, 8, 2, min(1, w["fold"] + 0.12), 0), 0.5), zc + 0.05)
        p.wing = {1: wl, -1: wr}
        sprawl = K([(0, 0), (LAND - 4, 0.3), (LAND + 4, 1), (N, 1)], f)
        for s in (1, -1):                               # from hanging to trailing flat on the ground
            p.legs[s] = [[-44 + 50 * sprawl, 8 + 12 * sprawl, 0.0], 32 - 26 * sprawl, -10 + 6 * sprawl,
                         -30 + 22 * sprawl]
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Hover": _clip_hover, "Fly": _clip_fly, "Dive": _clip_dive, "Screech": _clip_screech,
         "Hit": _clip_hit, "Death": _clip_death}
SHEET_FRAMES = {"Idle": (0, 6, 12, 18, 30, 40), "Hover": (0, 4, 8, 12, 20), "Fly": (0, 4, 8, 12, 16),
                "Dive": (0, 8, 14, 18, 22, 28, 36, 44), "Screech": (0, 8, 16, 30, 46), "Hit": (0, 3, 7, 11, 15),
                "Death": (0, 4, 10, 16, 21, 26, 34, 59)}


# ----------------------------------------------------------------------------------------- build (beast_anim's way)
def action_name(clip):
    return f"{BB.NAME}_{clip}"


def build_clip(name, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    N, fn, loop = CLIPS[name]()
    an = action_name(name)
    act = bpy.data.actions.get(an)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(an)
    act.use_fake_user = True
    act["loop"] = loop
    act["frames"] = N
    for ev, t in EVENTS.get(name, []):
        act["event_" + ev] = t
    rig_ob.animation_data_create()
    rig_ob.animation_data.action = act
    R = beast_rig.rest(rig_ob)
    for pb in rig_ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
    for f in range(N + 1):
        beast_rig.apply_pose(rig_ob, pose_matrices(fn(f)), frame=f, R=R)
    for fc in BA._fcurves(act):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    act.frame_range = (0, N)
    return act


def build_clips(names=None):
    _REST.clear()
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    act = bpy.data.actions[action_name(name)]
    rig_ob.animation_data_create()
    rig_ob.animation_data.action = act
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 0, int(act["frames"])
    scn.frame_set(0)


def clear(rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    if rig_ob.animation_data:
        rig_ob.animation_data.action = None
    beast_rig.reset_pose(rig_ob)


def still(p, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    if rig_ob.animation_data:
        rig_ob.animation_data.action = None
    beast_rig.apply_pose(rig_ob, pose_matrices(p), keys=False)
    bpy.context.view_layer.update()
