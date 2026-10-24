"""Golden eagle clips (2026-10-24, Daniel: "Lets accept the issue and animate it": the folded wing stays as the model
has it). Keyed straight onto EagleRig with beast_rig.apply_pose, the bat's way (bat_anim): a Pose per frame -> armature
matrices -> keys. The skeleton plays in place; Motion carries the travel (Unity root motion, horizontal only).

The pose system is eagle_pose's (the model's perched and spread poses and its folded wing; perched() and the spread
pose come out of it to 1e-7) with what the clips need on top:
- wing strokes (the bat's and the dragon's): the spread wing turned about the shoulder -- 'Y' + down / - up, 'Z' + sweeps
  it back, 'X' + pitches the leading edge down -- then folded by `fold` or flexed by `flex`, the primaries fanned wider
  by `finger`. The fold is split so no two cards cross on the way (_place_wing): a rigid lay of the wing's plane onto
  the fold plane, and an in-plane twist per bone (the cards keep their layer heights) plus the small swing left over;
  `flex` is the in-plane part alone (the wrist drawn in on an upstroke, the wings tucked in a stoop);
- legs: the thigh does not follow the leg (_leg): the back's and flanks' skin under the scapulars and the folded
  primaries carries up to 0.67 of the thigh's heat weight, so the thigh turns with the trunk at its perched frame or its
  tucked one (`thigh` 0..1) and the knee and ankle do the work (IK knee -> ankle -> ball). Feet on the ground keep the
  toes' rest orientation and their bases on their rest spots (none sinks); tucked feet aim the ankle at a target;
- a floor for the wings: a stroke that would put a wing joint or a feather's tip under it is lifted (its 'Y' turn
  bisected, the bat's way).

Height: the eagle perches on the ground and flies 1.5 m up (FLY_H, the body over its perched place). The skeleton
carries the height, so the GameObject stays on the ground as the bat's does; TakeOff rises 1.5 m in the skeleton, Land
comes down, Dive stoops to the ground and climbs back.

Clips (30 fps, facing -Y; Unity +Z). Ground: Idle, Walk, Screech, Hit, Death; flight: TakeOff, Fly, Glide, Dive, Land.
  Idle     6.0 s loop   perched: breathing, quick head turns and tilts, one feather rouse (a body shake, the wings
                        and the tail shaken loose, the scapulars lifted)
  Walk     1.33 s loop  a slow strut on the ground: the body rolling over the planted foot, a head bob; 0.195 m/s
  TakeOff  2.0 s        from perched: crouch, spring, the wings unfold over the back, three hard downstrokes, rising
                        1.5 m and accelerating to Fly's speed (5.0 m of travel); ends in Fly's first frame
  Fly      0.8 s loop   one wingbeat, the hand flexed on the upstroke; 6 m/s
  Glide    3.0 s loop   soaring: wings fixed, banking left and right, the tail twisting, the head looking round; 9 m/s
  Dive     2.6 s        from Fly: a beat up (2.0 m), the wings tucked, the stoop, the talons thrown forward and struck
                        onto a spot on the ground (event 'Strike' at 1.27 s), heavy beats back up; ends in Fly's first
                        frame (16.3 m of travel)
  Land     2.2 s        from Fly: a descending glide, braking flaps with the body upright, the legs swung forward,
                        touchdown at 1.47 s, the wings folded; 4.6 m of travel; ends perched (Idle's first frame)
  Screech  2.0 s        perched: the body leans in, the neck stretches the head out and up, the beak wide (event
                        'Screech' at 0.53 s)
  Hit      0.6 s        perched: a flinch back, the wings jerk open, recovers
  Death    2.5 s        perched: the wings jerk, the legs give and fold back, it pitches forward onto its breast, the
                        wings drooping open on the ground, the head turned on its side (event 'Dead' at 1.0 s); holds
"""
import bpy, math
from mathutils import Vector, Matrix, Quaternion
import beast_rig
import beast_anim as BA
from beast_anim import K, ease
import eagle_body as EB
import eagle_pose as EP

FPS = 30
RIG = EB.RIG
SIDES = EB.SIDES
C = EP.C
FLY_H = 1.5                     # the body's height in flight over its perched place (m)
# the folded wing's creases (eagle_drape) per clip: the gauge slides this much of the lay (1 = the creases' full turns).
# Fitted by eagle_build.fold_fit (2026-10-24): where the legs swing under the folded wing (Walk) or the wingtips come to
# the ground (the crouch, the touchdown, the fall) the curled feathers relax, as pressed feathers flex
# (Idle 0.94, Walk 0.22, TakeOff 0.75, Death 0.53; Screech, Hit and Land were clean at 1 and take Idle's share, so the
# clips that hand over through the perched pose match)
GAUGE = dict(Idle=0.94, Screech=0.94, Hit=0.94, Land=0.94, Walk=0.22, TakeOff=0.75, Death=0.53)
_gauge = [1.0]                  # the clip being keyed's
EVENTS = {}
MOVING = {"Walk", "TakeOff", "Fly", "Glide", "Dive", "Land"}


def rad(d):
    return math.radians(d)


_rot = EP._rot


def wing(Y=0.0, Z=0.0, X=0.0, fold=0.0, flex=0.0, finger=0.0):
    """A wing stroke: the spread wing turned about the shoulder (Y + down, Z + back, X + leading edge down), folded
    `fold` (0..1: the in-plane fold and the lay onto the flank together, toward the model's folded wing) and flexed
    `flex` (the in-plane fold alone: the wrist drawn in, the hand and the primaries swept back in the wing's own
    plane -- an upstroke, a stoop), the primaries fanned `finger` deg wider."""
    return dict(turns=[('Y', Y), ('Z', Z), ('X', X)], fold=fold, flex=flex, finger=finger)


def mix_wing(a, b, t):
    m = lambda k: a[k] * (1 - t) + b[k] * t
    return dict(turns=[(ax, x * (1 - t) + y * t) for (ax, x), (_, y) in zip(a["turns"], b["turns"])],
                fold=m("fold"), flex=m("flex"), finger=m("finger"))


def turn_of(w, ax):
    return dict(w["turns"])[ax]


def with_turn(w, ax, v):
    w = dict(w)
    w["turns"] = [(a, v if a == ax else x) for a, x in w["turns"]]
    return w


class Pose:
    def __init__(self):
        self.root = Vector()                              # Motion's travel (horizontal)
        self.body = Vector()                              # the trunk's offset
        self.pitch = self.roll = self.yaw = 0.0           # deg, + pitch = nose up, about C
        self.spine = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self.neck = [[0.0, 0.0, 0.0] for _ in range(3)]   # + pitch raises, + yaw turns left
        self.head = [0.0, 0.0, 0.0]
        self.jaw = 0.0                                    # deg, + opens
        self.tail = [0.0, 0.0, 0.0]                       # Tail1 (pitch + up, yaw, roll)
        self.tail_fan = 0.0
        self.wing = {1: wing(), -1: wing()}
        self.legs = {1: None, -1: None}                   # None = planted at the bind ankle (root space), or
        #                       (space, ankle, ball[, w]) with space 'body', 'root' or 'world'; w 0 = the foot on the
        #                       ball (the ankle bent toward its target), 1 = the ankle on its target (default: 'body' 1)
        self.toes = {1: 0.0, -1: 0.0}                     # curl, deg (+ grips)
        self.thigh = {1: 0.0, -1: 0.0}                    # the thigh's frame: 0 perched .. 1 tucked (flying)
        self.flat = {1: False, -1: False}                 # the toes keep their rest orientation (on the ground)
        self.scap = 0.0                                   # the scapulars rolled further out (a rouse), deg
        self.stance = {1: True, -1: True}                 # Walk: the foot is planted (for the drift check)
        self.floor = None                                # no wing joint or feather tip under this (world z)


# ----------------------------------------------------------------------------------------- the classic poses
def perched():
    """eagle_pose.perched() as a clip Pose."""
    q = EP.perched()
    p = Pose()
    p.pitch, p.body = q.pitch, q.body.copy()
    p.neck = [list(n) for n in q.neck]
    p.head = list(q.head)
    p.tail = list(q.tail)
    p.wing = {s: wing(fold=1.0) for s in (1, -1)}
    p.toes = {1: 3.0, -1: 3.0}
    p.flat = {1: True, -1: True}
    return p


TUCK = lambda s: (('body', (0.055 * s, 0.085, 0.262), (0.040 * s, 0.180, 0.262)))   # eagle_pose.spread()'s feet


def flying():
    """The flying pose at FLY_H: eagle_pose.spread() with the wings at the top of a beat taken out (the Fly loop's
    first frame sets them)."""
    p = Pose()
    p.body = Vector((0, 0.0, FLY_H))
    p.pitch = 4.0
    p.neck = [[3.0, 0, 0], [2.0, 0, 0], [0.0, 0, 0]]
    p.head = [-8.0, 0, 0]
    p.tail = [2.0, 0, 0]
    p.tail_fan = 18.0
    p.legs = {1: TUCK(1), -1: TUCK(-1)}
    p.toes = {1: 70.0, -1: 70.0}
    p.thigh = {1: 1.0, -1: 1.0}
    return p


# ----------------------------------------------------------------------------------------- pose -> matrices
def _turn_matrix(w, s):
    M = Matrix.Identity(3)
    for ax, deg in w["turns"]:
        M = Matrix.Rotation(rad(deg if (s > 0 or ax == 'X') else -deg), 3, ax) @ M
    return M


def _fold_nrm(s):
    n = EP._fold_basis()[0]
    return n if s > 0 else Vector((-n.x, n.y, n.z))


def _mx(v, s):
    v = Vector(v)
    return v if s > 0 else Vector((-v.x, v.y, v.z))


def _plane_turn(M, s):
    """The rigid turn that lays the (stroke-turned) spread wing's plane onto the fold plane: its axes (out, back,
    dorsal) = (M WX, M WY, M WN) onto (back x outward normal, back, outward normal) of eagle_pose's fold."""
    n, a, u = EP._fold_basis()
    F = Matrix((_mx(a.cross(n), s), _mx(a, s), _mx(n, s))).transposed()      # the left's axes, mirrored
    S = Matrix((M @ _mx(EB.WX, s), M @ _mx(EB.WY, s), M @ _mx(EB.WN, s))).transposed()
    return F @ S.transposed()


def _q(m):
    q = m.to_quaternion()
    return -q if q.w < 0 else q


def _swing_twist(q, axis):
    """q = swing @ twist, the twist about `axis` (unit)."""
    p = axis * Vector((q.x, q.y, q.z)).dot(axis)
    t = Quaternion((q.w, p.x, p.y, p.z))
    if t.magnitude < 1e-9:
        return q.copy(), Quaternion()
    t.normalize()
    return q @ t.inverted(), t


def ramp(a, b, x):
    return min(max((x - a) / (b - a), 0.0), 1.0)


ALULA_LIFT = 0.5      # the alula's lift off the coverts (eagle_pose.FOLD_LIFT) is done by this much of the lay


def _place_wing(p, W, rel, s, sfx, w, turn):
    """One wing's bones into W for the stroke w -> the lowest z of its joints and feather-bone tips (world).

    The fold (2026-10-24): eagle_pose's per-bone slerp from the spread aim to the folded one crossed 500-1,500 card
    pairs on the way (the cards of a fan twisting against each other at 1.1-1.4 mm layer steps). Here each bone's
    turn from its spread frame S_b to its folded frame F_b is split: F_b = G R_b S_b, where G lays the spread wing's
    plane onto the fold plane rigidly (one turn for every bone of the wing) and R_b = G^-1 F_b S_b^-1 is the bone's
    own turn, which is nearly about the wing's normal; R_b is split again into its twist about the normal (the
    in-plane fold, in which every card keeps its layer's height over the plane) and the small swing left over. A
    fold t runs all three by t; `flex` runs the twist and the swing alone (the wing drawn in in its own plane, no lay).
    Both ends are eagle_pose's."""
    D = EP.rest()
    R, B = D['R'], D['B']
    lay = min(max(w["fold"], 0.0), 1.0)
    inp = min(lay + min(max(w["flex"], 0.0), 1.0) * (1 - lay), 1.0)
    M = _turn_matrix(w, s)
    G = _plane_turn(M, s)
    qg = Quaternion().slerp(_q(G), lay)
    axis = (M @ _mx(EB.WN, s)).normalized()
    lo = 9.0
    for n in EP.WING_BONES:
        bn = n + sfx
        par = B[bn][3]
        here = W[par] @ rel(bn, par)
        if n in EP.FOLD_CARRY and lay > 0:            # folded, carried as the tertials are (eagle_pose.FOLD_CARRY)
            c = EP.FOLD_CARRY[n] + sfx
            here = Matrix.Translation(here.translation.lerp((W[c] @ rel(bn, c)).translation, lay))
        q0 = R[bn].to_3x3()
        if n.startswith("WingP") and w["finger"]:
            k = int(n[5:])
            ax = R[f"WingHand{sfx}"].col[2].xyz
            q0 = Matrix.Rotation(rad(-s * w["finger"] * (k - 5.5) / 4.5), 3, ax) @ q0
        Sb = M @ q0
        k = inp
        if k > 0:
            Rb = G.inverted() @ EP.fold_frame(n, s) @ Sb.transposed()
            swing, twist = _swing_twist(_q(Rb), axis)
            if twist.w < 0:
                twist = -twist
            if swing.w < 0:
                swing = -swing
            q = qg @ Quaternion().slerp(swing, k) @ Quaternion().slerp(twist, k) @ _q(Sb)
        else:
            q = _q(Sb)
        W[bn] = Matrix.Translation(here.translation) @ (turn @ q.to_matrix()).to_4x4()
        if n in EP.FOLD_LIFT and lay > 0:
            W[bn] = Matrix.Translation(turn @ _fold_nrm(s) * EP.FOLD_LIFT[n] * ramp(0, ALULA_LIFT, lay)) @ W[bn]
        tip = W[bn].translation + W[bn].col[1].xyz * B[bn][2]
        lo = min(lo, W[bn].translation.z, tip.z)
    return lo


def _wings(p, W, rel):
    D = EP.rest()
    R = D['R']
    turn = W["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    for s, sfx in SIDES:
        w = p.wing[s]
        lo = _place_wing(p, W, rel, s, sfx, w, turn)
        if p.floor is not None and lo < p.floor + 0.02:
            a, b = -85.0, turn_of(w, 'Y')               # a: high enough (assumed clear), b: too low
            for _ in range(14):
                mid = 0.5 * (a + b)
                if _place_wing(p, W, rel, s, sfx, with_turn(w, 'Y', mid), turn) < p.floor + 0.02:
                    b = mid
                else:
                    a = mid
            w = with_turn(w, 'Y', a)
            _place_wing(p, W, rel, s, sfx, w, turn)
        t = min(max(w["fold"], 0.0), 1.0)              # the scapulars roll out over the wing as it lays
        sc = "Scap" + sfx
        W[sc] = (W["Chest"] @ rel(sc, "Chest") @ Matrix.Rotation(rad(-s * EP.FOLD_SCAP[1] * t), 4, 'Z') @
                 Matrix.Rotation(rad(s * (EP.FOLD_SCAP[0] * t + p.scap)), 4, 'Y'))
        EP.gauge(W, rel, sfx, t * _gauge[0])          # the creases follow the wing's lay (not a flex)


_THIGH = {}


def thigh_refs():
    """Each thigh's frame relative to the trunk in eagle_pose's perched and spread poses (the two the model was
    checked in): side -> (perched, tucked) quaternions."""
    if not _THIGH:
        mp, ms = EP.pose_matrices(EP.perched()), EP.pose_matrices(EP.spread())
        q = Pose()
        q.body, q.pitch = Vector((0, 0, EP.LIFT)), 3.0
        Bp, Bs = body_matrix(perched()).inverted(), body_matrix(q).inverted()
        for s, sfx in SIDES:
            th = "Thigh" + sfx
            _THIGH[s] = ((Bp @ mp[th]).to_quaternion(), (Bs @ ms[th]).to_quaternion())
    return _THIGH


def _leg(p, W, M, MB, rel, s, sfx):
    """The thigh is not posed by the leg's IK (2026-10-24): the skin of the back and the flanks under the scapulars
    and the folded primaries carries up to 0.67 of the thigh's heat weight, so a thigh swinging with the leg pushed
    the skin through the cards. It turns with the trunk, at its perched frame (thigh 0) or its tucked one (1) or
    between; the knee, the ankle and the foot do the work: a two-bone IK knee -> ankle -> ball, the ankle bent
    toward the target's ankle (the hint), as a bird walks on its knee and ankle with the femur held still."""
    D = EP.rest()
    R, B = D['R'], D['B']
    th, sh, ta = f"Thigh{sfx}", f"Shin{sfx}", f"Tarsus{sfx}"
    qa, qb = thigh_refs()[s]
    k = min(max(p.thigh[s], 0.0), 1.0)
    W[th] = MB @ Matrix.Translation(R[th].translation) @ qa.slerp(qb, k).to_matrix().to_4x4()
    knee = W[th].translation + W[th].col[1].xyz * B[th][2]
    leg = p.legs[s]
    if leg is None:
        ankle_t, ball_t = _rest_leg(s)
        ankle_t, ball_t, w = M @ ankle_t, M @ ball_t, 0.0
    else:
        space, ankle_b, ball_b = leg[:3]
        X = MB if space == 'body' else (M if space == 'root' else Matrix.Identity(4))
        ankle_t, ball_t = X @ Vector(ankle_b), X @ Vector(ball_b)
        w = leg[3] if len(leg) > 3 else (1.0 if space == 'body' else 0.0)
    # w 0: the foot on its ball target (the ankle bent toward its target); w 1: the ankle toward its target, the
    # tarsus aimed at the ball (eagle_pose's tucked feet)
    ls = B[sh][2]
    # flat feet on their ball target: the toes' bases keep their rest place on the ground however the tarsus
    # turns over them -- their middle stays put, none goes below its rest height (the tarsus' turn moves the bases
    # about the ball: three passes)
    goal = ball_t.copy()
    toes = [f"Toe{i}_1{sfx}" for i in EB.TOES]
    rest_ball = _rest_leg(s)[1]
    base_t = [ball_t + (R[t].translation - rest_ball) for t in toes]
    for it in range(3 if (p.flat[s] and w < 1) else 1):
        ankle, ball = EP._ik(knee, goal, ls, B[ta][2], ankle_t - knee)
        if w > 0:
            a2 = knee + (ankle_t - knee).normalized() * ls
            ankle = knee + (ankle.lerp(a2, w) - knee).normalized() * ls
        tars = EP._aim(R[ta].to_3x3(), R[ta].col[1].xyz, goal - ankle)
        if p.flat[s] and w < 1:
            Wt = Matrix.Translation(ankle) @ tars.to_4x4()
            d = [(Wt @ rel(t, ta)).translation - bt for t, bt in zip(toes, base_t)]
            err = sum(d, Vector()) / len(d)
            err.z = min(v.z for v in d)
            goal = goal - err * (1 - w)
    W[sh] = Matrix.Translation(knee) @ EP._aim(R[sh].to_3x3(), R[sh].col[1].xyz, ankle - knee).to_4x4()
    W[ta] = Matrix.Translation(ankle) @ tars.to_4x4()
    for i in EB.TOES:
        a, b = f"Toe{i}_1{sfx}", f"Toe{i}_2{sfx}"
        if p.flat[s]:                               # on the ground: the toes keep their rest orientation
            W[a] = Matrix.Translation((W[ta] @ rel(a, ta)).translation) @ R[a].to_3x3().to_4x4() @ \
                _rot(-0.4 * p.toes[s])
        else:
            W[a] = W[ta] @ rel(a, ta) @ _rot(-0.4 * p.toes[s])
        W[b] = W[a] @ rel(b, a) @ _rot(-0.6 * p.toes[s])


def body_matrix(p):
    """World matrix of the trunk's transform (MB in pose_matrices)."""
    M = Matrix.Translation(p.root)
    return M @ (Matrix.Translation(C + p.body) @ Matrix.Rotation(rad(p.yaw), 4, 'Z') @
                Matrix.Rotation(rad(-p.pitch), 4, 'X') @ Matrix.Rotation(rad(p.roll), 4, 'Y') @ Matrix.Translation(-C))


def pose_matrices(p):
    D = EP.rest()
    R = D['R']
    rel = lambda c, par: R[par].inverted() @ R[c]
    M = Matrix.Translation(p.root)
    MB = body_matrix(p)
    W = {"Root": M @ R["Root"]}
    W["Hips"] = MB @ R["Hips"]
    W["Spine1"] = MB @ R["Spine1"] @ _rot(*p.spine[0])
    W["Chest"] = W["Spine1"] @ rel("Chest", "Spine1") @ _rot(*p.spine[1])
    par = "Chest"
    for i in range(3):
        n = f"Neck{i + 1}"
        W[n] = W[par] @ rel(n, par) @ _rot(*p.neck[i])
        par = n
    W["Head"] = W[par] @ rel("Head", par) @ _rot(*p.head)
    W["Jaw"] = W["Head"] @ rel("Jaw", "Head") @ _rot(-p.jaw)
    W["Tail1"] = W["Hips"] @ rel("Tail1", "Hips") @ _rot(*p.tail)
    for s, sfx in SIDES:
        _leg(p, W, M, MB, rel, s, sfx)
        EP._tail(p, W, rel, s, sfx)
    _wings(p, W, rel)
    W["Socket_Head"] = W["Head"] @ rel("Socket_Head", "Head")
    W["Socket_Mouth"] = W["Jaw"] @ rel("Socket_Mouth", "Jaw")
    W["Socket_Grip"] = W["TarsusR"] @ rel("Socket_Grip", "TarsusR")
    Minv = M.inverted()
    out = {k: Minv @ v for k, v in W.items()}
    out["Motion"] = M @ R["Motion"]
    return out


# ----------------------------------------------------------------------------------------- clip helpers
def lerp(a, b, t):
    return a * (1 - t) + b * t


def E(keys, f):
    """Keys joined by eased segments (no overshoot, a hold at every key): for envelopes. K (Catmull-Rom) overshoots
    next to a plateau: the Dive's leg throw went negative and pulled the feet up onto the back."""
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys[:-1], keys[1:]):
        if f <= f1:
            return v0 + (v1 - v0) * ease((f - f0) / (f1 - f0))
    return keys[-1][1]


def _rest_leg(s):
    """The bind pose's ankle and ball (root space)."""
    R, B = EP.rest()['R'], EP.rest()['B']
    ta = "Tarsus" + ("L" if s > 0 else "R")
    return R[ta].translation.copy(), (R[ta] @ Vector((0, B[ta][2], 0)))


def leg_mode(p, s):
    leg = p.legs[s]
    if leg is None:
        return 0.0
    return leg[3] if len(leg) > 3 else (1.0 if leg[0] == 'body' else 0.0)


def leg_world(p, s):
    """A pose's leg targets in world space: (ankle, ball)."""
    leg = p.legs[s]
    M = Matrix.Translation(p.root)
    if leg is None:
        a, b = _rest_leg(s)
        return M @ a, M @ b
    space, a, b = leg[:3]
    X = body_matrix(p) if space == 'body' else (M if space == 'root' else Matrix.Identity(4))
    return X @ Vector(a), X @ Vector(b)



def mix_pose(a, b, t, root=None):
    """a blended toward b by t (every field; the legs through world-space targets; the root a's, or `root`)."""
    p = Pose()
    L = lambda x, y: x * (1 - t) + y * t
    p.root = (a.root if root is None else root).copy()
    p.body = a.body.lerp(b.body, t)
    p.pitch, p.roll, p.yaw = L(a.pitch, b.pitch), L(a.roll, b.roll), L(a.yaw, b.yaw)
    p.spine = [[L(x, y) for x, y in zip(u, v)] for u, v in zip(a.spine, b.spine)]
    p.neck = [[L(x, y) for x, y in zip(u, v)] for u, v in zip(a.neck, b.neck)]
    p.head = [L(x, y) for x, y in zip(a.head, b.head)]
    p.jaw, p.tail_fan, p.scap = L(a.jaw, b.jaw), L(a.tail_fan, b.tail_fan), L(a.scap, b.scap)
    p.tail = [L(x, y) for x, y in zip(a.tail, b.tail)]
    p.wing = {s: mix_wing(a.wing[s], b.wing[s], t) for s in (1, -1)}
    p.toes = {s: L(a.toes[s], b.toes[s]) for s in (1, -1)}
    p.thigh = {s: L(a.thigh[s], b.thigh[s]) for s in (1, -1)}
    p.flat = {s: a.flat[s] if t < 0.5 else b.flat[s] for s in (1, -1)}
    p.floor = a.floor if a.floor is not None else b.floor
    for s in (1, -1):
        la, lb = a.legs[s], b.legs[s]
        if la is None and lb is None and a.root == b.root:
            continue
        if la is not None and lb is not None and la[0] == lb[0] == 'body' and len(la) == len(lb) == 3:
            p.legs[s] = ('body', Vector(la[1]).lerp(Vector(lb[1]), t), Vector(la[2]).lerp(Vector(lb[2]), t))
            continue
        a0, a1 = leg_world(a, s)
        b0, b1 = leg_world(b, s)
        p.legs[s] = ('world', a0.lerp(b0, t), a1.lerp(b1, t), L(leg_mode(a, s), leg_mode(b, s)))
    return p


def toward(p, q, t):
    """p blended toward q by t, keeping p's root (q's legs are taken at p's root)."""
    if t <= 0:
        return p
    q.root = p.root.copy()
    return mix_pose(p, q, t)


def travel(speeds, N):
    """Root y per frame (forward = -Y) from a speed per frame (m/s), trapezoid-integrated."""
    y = [0.0]
    for f in range(1, N + 1):
        y.append(y[-1] - 0.5 * (speeds(f - 1) + speeds(f)) / FPS)
    return y


# ----------------------------------------------------------------------------------------- Fly and Glide
FLY_N, FLY_SPEED = 24, 6.0
GLIDE_N, GLIDE_SPEED = 90, 9.0
TOP = dict(Y=-30.0, Z=3.0, X=0.0, flex=0.2)              # the top of a beat (Fly's first frame)


def fly_beat(q, Y=(-30.0, 36.0), Z=(3.0, -10.0), X=7.0, flex=0.2, up_flex=0.42, down=0.45, finger=2.0):
    """One wingbeat at phase q (0 = the top): the downstroke takes `down` of it, the wing fully out (the top's
    flex gone in its first third), sweeping forward and pitched down mid-stroke; the upstroke draws the wing in
    (up_flex at its middle, the top's flex at its end) and sweeps it back."""
    q = q % 1.0
    if q < down:
        u = ease(q / down)
        x = X * math.sin(math.pi * q / down) ** 2
        fl = flex * (1 - ease(q / (down * 0.35)))
    else:
        v = (q - down) / (1 - down)
        u = 1 - ease(v)
        x = 0.0
        fl = flex * ease(v) + up_flex * math.sin(math.pi * v) ** 2
    return wing(lerp(Y[0], Y[1], u), lerp(Z[0], Z[1], u), x, 0.0, fl, finger)


def fly_pose(f):
    q = (f % FLY_N) / FLY_N
    p = flying()
    p.root = Vector((0, -FLY_SPEED * f / FPS, 0))
    w = fly_beat(q)
    p.wing = {1: w, -1: w}
    bob = 0.03 * math.sin(2 * math.pi * (q - 0.2))
    p.body = Vector((0, 0, FLY_H + bob))
    p.pitch = 4.0 + 1.5 * math.sin(2 * math.pi * (q + 0.1))
    p.neck = [[3.0 - 10 * bob, 0, 0], [2.0, 0, 0], [0.0, 0, 0]]
    p.head = [-8.0 - 1.5 * math.sin(2 * math.pi * (q + 0.1)), 0, 0]
    p.tail = [2.0 + 2 * math.sin(2 * math.pi * (q - 0.1)), 0, 0]
    p.tail_fan = 18.0 + 4 * math.sin(2 * math.pi * q)
    return p


def _clip_fly():
    return FLY_N, fly_pose, True


def glide_pose(f):
    N = GLIDE_N
    a = 2 * math.pi * f / N
    p = flying()
    p.root = Vector((0, -GLIDE_SPEED * f / FPS, 0))
    roll = 11 * math.sin(a)
    p.roll = roll
    p.yaw = 3 * math.sin(a - 0.5)
    p.pitch = 2.0 + 1.0 * math.sin(2 * a)
    p.body = Vector((0, 0, FLY_H + 0.05 * math.sin(a + 1.0)))
    for s in (1, -1):
        low = max(0.0, s * math.sin(a))                  # this wing is the lower one in the bank
        p.wing[s] = wing(Y=-6 + 3 * low, Z=2 + 2 * low, X=1.0, flex=0.04 + 0.10 * low,
                         finger=4 + 1.5 * math.sin(3 * a + s))
    p.tail_fan = 20 + 6 * math.sin(2 * a + 0.5)
    p.tail = [1.0 + 2 * math.sin(2 * a), 0.12 * roll, -0.3 * roll]
    look = 16 * math.sin(2 * a + 0.8)
    p.neck = [[-2.0, 0.2 * look - 0.3 * roll, 0], [-3.0, 0.3 * look, 0], [-2.0, 0.2 * look, 0]]
    p.head = [-10.0, 0.3 * look, 0.5 * roll]
    return p


def _clip_glide():
    return GLIDE_N, glide_pose, True


# ----------------------------------------------------------------------------------------- ground clips
def _breath(p, f, period=45, k=1.0):
    b = math.sin(2 * math.pi * f / period)
    p.body = p.body + Vector((0, 0, 0.003 * b * k))
    p.pitch += 0.6 * b * k
    p.spine[1][0] += 0.5 * b * k


def _look(p, yaw, tilt, pitch):
    """A head turn spread over the neck and the head (deg)."""
    for i, k in enumerate((0.15, 0.25, 0.25)):
        p.neck[i][1] += yaw * k
    p.head[1] += yaw * 0.35
    p.head[2] += tilt
    p.head[0] += pitch


IDLE_N = 180
ROUSE = 138                                    # the rouse's start


def idle_pose(f):
    N = IDLE_N
    p = perched()
    _breath(p, f)
    keys = [(0, (0, 0, 0)), (22, (0, 0, 0)), (26, (38, 0, -3)), (58, (38, 9, -3)), (63, (-8, 0, 2)),
            (90, (-8, 0, 2)), (94, (-44, -7, 0)), (118, (-44, -7, 0)), (123, (0, 0, 0)), (180, (0, 0, 0))]
    yaw, tilt, pitch = K(keys, f)
    _look(p, yaw, tilt, pitch)
    env = E([(0, 0), (ROUSE, 0), (ROUSE + 5, 1), (ROUSE + 17, 1), (ROUSE + 24, 0), (N, 0)], f)
    if env > 0:
        sh = math.sin(2 * math.pi * (f - ROUSE) / 4.5) * env
        p.roll += 6 * sh
        p.body = p.body + Vector((0, 0, 0.006 * env))
        p.head[1] += 10 * sh
        p.head[2] += 6 * sh
        p.tail[1] += 4 * sh
        p.tail_fan += 8 * env
        p.scap += -4 * env
        for s in (1, -1):
            p.wing[s] = wing(fold=1.0 - 0.10 * env + 0.03 * sh * s)
    return p


def _clip_idle():
    return IDLE_N, idle_pose, True


WALK_N, WALK_STRIDE, WALK_DUTY = 40, 0.26, 0.62


def walk_pose(f):
    N = WALK_N
    p = perched()
    p.root = Vector((0, -WALK_STRIDE * f / N, 0))
    a = 2 * math.pi * f / N
    p.pitch = 42 + 1.5 * math.cos(2 * a)
    p.roll = -5 * math.sin(a)
    p.yaw = 4 * math.sin(a - 0.4)
    p.body = Vector((-0.010 * math.sin(a), 0.0, -0.022 + 0.008 * math.cos(2 * a)))
    bob = math.sin(2 * a - 0.8)
    p.neck = [[-12.0 + 3 * bob, 0, 0], [-14.0 + 2 * bob, 0, 0], [-10.0, 0, 0]]
    p.head = [-4.0 - 4 * bob, 2 * math.sin(a), 3 * math.sin(a)]
    p.tail = [6.0, -4 * math.sin(a), 0]
    fwd = Vector((0, -1, 0))
    for s, off in ((1, 0.0), (-1, 0.5)):
        ankle, ball = _rest_leg(s)
        ph = (f / N + off) % 1.0
        p.stance[s] = ph < WALK_DUTY
        if ph < WALK_DUTY:
            u = 0.5 - ph / WALK_DUTY
            z = 0.0
            th = lerp(-8.0, 26.0, ph / WALK_DUTY)
            curl = 3.0
        else:
            q = (ph - WALK_DUTY) / (1 - WALK_DUTY)
            u = -0.5 + ease(q)
            z = 0.045 * math.sin(math.pi * q) ** 0.8
            th = lerp(26.0, -8.0, ease(q))
            curl = 3.0 + 30 * math.sin(math.pi * q)
        p.flat[s] = True
        d = Matrix.Rotation(rad(th), 3, 'X') @ (ankle - ball)
        c = ball + fwd * (WALK_STRIDE * WALK_DUTY * u) + Vector((0, 0, z))
        p.legs[s] = ('root', c + d, c)
        p.toes[s] = curl
    return p


def _clip_walk():
    return WALK_N, walk_pose, True


SCREECH_N, SCREECH_AT = 60, 16


def screech_pose(f):
    p = perched()
    _breath(p, f, k=0.5)
    up = K([(0, 0), (8, -0.25), (15, 1), (38, 1), (48, 0.1), (60, 0)], f)
    p.pitch += -12 * max(up, 0)                   # the body leans in, the neck stretches the head out and up
    p.body = p.body + Vector((0, -0.03 * up, 0.0))
    p.neck[0][0] += 6 * up
    p.neck[1][0] += 10 * up
    p.neck[2][0] += 8 * up
    p.head[0] += 8 * up
    trem = math.sin(2 * math.pi * f / 3.0) * E([(0, 0), (17, 0), (19, 1), (36, 1), (40, 0), (60, 0)], f)
    p.jaw = K([(0, 0), (10, 0), (SCREECH_AT, 30), (36, 32), (44, 3), (50, 0), (60, 0)], f) + 2.0 * trem
    p.head[0] += 1.5 * trem
    m = E([(0, 0), (10, 0), (16, 1), (40, 1), (52, 0), (60, 0)], f)
    p.wing = {s: wing(fold=1.0 - 0.09 * m) for s in (1, -1)}
    p.tail_fan = 14 * m
    p.tail[0] += 4 * m
    return p


def _clip_screech():
    return SCREECH_N, screech_pose, False


HIT_N = 18


def hit_pose(f):
    p = perched()
    k = K([(0, 0), (3, 1), (7, 0.55), (11, -0.15), (18, 0)], f)
    kp = max(k, 0.0)
    p.pitch += 6 * k
    p.roll += -2.5 * k
    p.yaw += 6 * k
    p.body = p.body + Vector((0.01 * k, 0.025 * k, 0.035 * kp))
    p.neck[0][0] += 8 * k
    p.neck[1][0] += 4 * k
    p.head = [p.head[0] + 10 * k, p.head[1] - 10 * k, p.head[2] + 12 * k]
    p.jaw = 16 * K([(0, 0), (3, 1), (8, 0.3), (18, 0)], f)
    p.wing = {s: wing(fold=1.0 - 0.16 * kp) for s in (1, -1)}
    p.tail_fan = 16 * kp
    p.tail[0] += 16 * kp
    p.toes = {s: 3.0 for s in (1, -1)}
    return p


def _clip_hit():
    return HIT_N, hit_pose, False


DEATH_N, DEATH_HIT = 75, 30


def death_pose(f):
    N = DEATH_N
    p = perched()
    p.floor = 0.0
    jerk = K([(0, 0), (3, 1), (7, 0.5), (12, 0.2)], f)
    fall = ease(ramp(6, DEATH_HIT, f) ** 1.6)
    bounce = 0.02 * K([(DEATH_HIT, 0), (DEATH_HIT + 3, 1), (DEATH_HIT + 7, 0), (N, 0)], f)
    p.pitch = lerp(50 + 4 * jerk, -6.0, fall)
    p.roll = lerp(-4 * jerk, 14.0, fall)
    p.yaw = lerp(0.0, 8.0, fall)
    p.body = Vector((0, lerp(0.0, -0.05, fall), lerp(-0.01, DEATH_Z, fall) + bounce))
    dn = E([(0, 0), (DEATH_HIT - 4, 0), (DEATH_HIT + 8, 1), (N, 1)], f)
    p.neck = [[lerp(-16 + 8 * jerk, -6, fall) - 6 * dn, 4 * dn, 0], [lerp(-18, -4, fall) - 6 * dn, 16 * dn, 0],
              [lerp(-14, -2, fall) - 6 * dn, 18 * dn, 0]]
    p.head = [lerp(-4 + 10 * jerk, 0, fall) - 6 * dn, 14 * dn, 34 * dn]
    p.jaw = K([(0, 0), (3, 18), (14, 10), (DEATH_HIT + 4, 6), (N, 5)], f)
    open_ = E([(0, 0), (4, 0.3), (14, 0.45), (DEATH_HIT, 0.6), (N, 0.62)], f)
    for s in (1, -1):
        down = E([(0, 0), (12, 0), (DEATH_HIT, 1), (N, 1)], f)
        p.wing[s] = wing(Y=22 * down, Z=-4 * down, fold=1.0 - open_ * (1.0 if s > 0 else 0.8), finger=2 * down)
    p.tail_fan = K([(0, 0), (6, 14), (DEATH_HIT, 22), (N, 22)], f)
    p.tail[0] = lerp(6.0 + 12 * jerk, 4.0, fall)
    # the legs give: the feet leave the ground as it falls and fold back under the tail (the tuck), the toes curl
    for s in (1, -1):
        a, b = _rest_leg(s)
        q = Pose()
        q.root, q.body, q.pitch, q.roll, q.yaw = p.root, p.body, p.pitch, p.roll, p.yaw
        ta, tb = leg_world(dict_legs(q, s, TUCK(s)), s)
        k = ease(ramp(4, DEATH_HIT - 4, f))
        up = Vector((0, 0, 0.05 * math.sin(math.pi * k)))
        p.legs[s] = ('world', a.lerp(ta, k) + up, b.lerp(tb, k) + up, k)
        p.thigh[s] = k * DEATH_THIGH
        p.flat[s] = k < 0.3
        p.toes[s] = lerp(3.0, 30.0, ramp(6, DEATH_HIT + 10, f))
    # the scapulars unroll as the legs fold (the back's skin rides the thighs)
    p.scap = (-EP.FOLD_SCAP[0] * p.wing[1]["fold"] + DEATH_SCAP) * ease(ramp(4, DEATH_HIT - 4, f))
    return p


DEATH_THIGH, DEATH_SCAP = 1.0, -3.0            # the thigh folds all the way back; the scapulars lift 3 deg off the back


DEATH_Z = -0.215                                 # the body's offset lying on its breast


def _clip_death():
    return DEATH_N, death_pose, False


# ----------------------------------------------------------------------------------------- TakeOff, Land, Dive
TAKEOFF_N = 60
_TO_SPEED = lambda f: FLY_SPEED * ease(ramp(10, TAKEOFF_N, f))


def beats(f, tops, params):
    """Wingbeats between the frames `tops` (each from a top to the next top), beat i shaped by params[i]
    (fly_beat's keywords); before the first top: None."""
    for i in range(len(tops) - 1):
        if tops[i] <= f <= tops[i + 1]:
            return fly_beat((f - tops[i]) / (tops[i + 1] - tops[i]) if f < tops[i + 1] else 0.0, **params[i])
    return None


def takeoff_pose(f, Y=None):
    N = TAKEOFF_N
    Y = Y or travel(_TO_SPEED, N)
    p = perched()
    p.floor = 0.0
    p.root = Vector((0, Y[int(f)], 0))
    up = K([(0, -0.010), (10, -0.045), (14, 0.05), (18, 0.20), (26, 0.40), (34, 0.58), (41, 0.80), (47, 0.98),
            (54, 1.22), (60, FLY_H - 0.0285)], f)
    p.body = Vector((0, 0, up))
    p.pitch = K([(0, 50), (10, 36), (14, 44), (18, 40), (26, 28), (36, 18), (46, 10), (60, 5.4)], f)
    t_n = ease(ramp(8, 30, f))
    fl = flying()
    p.neck = [[lerp(a[0], b[0], t_n), 0, 0] for a, b in zip(p.neck, fl.neck)]
    p.neck[0][0] += -8 * K([(0, 0), (8, 1), (14, 0.5), (20, 0)], f)          # the head forward in the crouch
    p.head = [lerp(p.head[0], fl.head[0], t_n), 0, 0]
    p.tail = [K([(0, 6), (10, 8), (16, -8), (30, 0), (60, 4.0)], f), 0, 0]
    p.tail_fan = K([(0, 0), (10, 8), (18, 30), (40, 26), (60, 18.0)], f)
    # the wings: unfold over the back (8-18), then three hard beats; the last ends at Fly's top
    hard = dict(Y=(-30.0, 40.0), Z=(3.0, -12.0), X=8.0, flex=0.2, up_flex=0.45)
    w = beats(f, (18, 33, 47, N), (hard, hard, dict(hard, Y=(-30.0, 36.0), Z=(3.0, -10.0), X=7.0, up_flex=0.42)))
    if w is None:
        k = ease(ramp(8, 18, f))
        w = wing(Y=TOP['Y'] * k, Z=TOP['Z'] * k, X=0.0, fold=1.0 - k, flex=TOP['flex'] * k, finger=2.0 * k)
    p.wing = {1: w, -1: w}
    # the feet push off where they stood, then trail back and tuck under the tail
    lift = ease(ramp(13, 30, f))
    for s in (1, -1):
        a, b = _rest_leg(s)
        if lift <= 0:
            p.legs[s] = ('world', a, b)
            p.flat[s] = True
        else:
            q = Pose()
            q.root, q.body, q.pitch = p.root, p.body, p.pitch
            ta, tb = leg_world(dict_legs(q, s, TUCK(s)), s)
            p.legs[s] = ('world', a.lerp(ta, lift), b.lerp(tb, lift), lift)
        p.thigh[s] = lift
        p.toes[s] = K([(0, 3), (12, 0), (16, -15), (24, 30), (34, 70), (60, 70)], f)
    return toward(p, fly_pose(f - N), ease(ramp(N - 8, N, f)))


def dict_legs(p, s, leg):
    p.legs[s] = leg
    return p


def _clip_takeoff():
    Y = travel(_TO_SPEED, TAKEOFF_N)
    return TAKEOFF_N, (lambda f: takeoff_pose(f, Y)), False


LAND_N, LAND_TOUCH = 66, 44
_LAND_SPEED = lambda f: FLY_SPEED * (1 - ease(ramp(0, LAND_TOUCH + 2, f)))


def land_pose(f, Y=None):
    N = LAND_N
    Y = Y or travel(_LAND_SPEED, N)
    p = flying()
    p.floor = 0.0
    p.root = Vector((0, Y[int(f)], 0))
    end = Vector((0, Y[N], 0))
    z = K([(0, FLY_H - 0.0285), (8, 1.40), (16, 1.05), (26, 0.62), (36, 0.28), (LAND_TOUCH, -0.02),
           (LAND_TOUCH + 4, -0.05), (54, -0.02), (N, -0.010)], f)
    p.body = Vector((0, 0, z))
    p.pitch = K([(0, 5.4), (10, 10), (20, 28), (30, 48), (38, 58), (LAND_TOUCH, 54), (LAND_TOUCH + 4, 44),
                 (56, 51), (N, 50)], f)
    per = perched()
    t_n = ease(ramp(30, N, f))
    p.neck = [[lerp(a[0], b[0], t_n), 0, 0] for a, b in zip(flying().neck, per.neck)]
    p.head = [lerp(flying().head[0], per.head[0], t_n), 0, 0]
    p.neck[0][0] += 6 * K([(0, 0), (30, 0), (LAND_TOUCH, 1), (54, 0)], f)
    p.tail = [K([(0, 4.0), (14, -6), (28, -10), (38, 6), (LAND_TOUCH, 16), (50, 14), (58, 8), (N, 6)], f), 0, 0]
    p.tail_fan = K([(0, 18.0), (14, 32), (LAND_TOUCH, 38), (52, 8), (60, 0), (N, 0)], f)
    # wings: from the top of a beat into a braking glide, two braking flaps swept forward, held up at touchdown,
    # folded once standing
    brake = dict(Y=(-30.0, 26.0), Z=(-6.0, -16.0), X=4.0, flex=0.15, up_flex=0.35)
    if f <= 16:
        k = ease(f / 16)
        w = mix_wing(wing(**TOP, finger=2.0), wing(Y=-12, Z=-2, X=0, flex=0.06, finger=4), k)
    elif f <= 22:
        k = ease((f - 16) / 6)
        w = mix_wing(wing(Y=-12, Z=-2, X=0, flex=0.06, finger=4), wing(Y=-30, Z=-6, X=0, flex=0.15, finger=3), k)
    elif f <= 40:
        w = beats(f, (22, 31, 40), (brake, brake))
    else:
        k = ease(ramp(LAND_TOUCH, 62, f))
        w0 = wing(Y=-30, Z=-6, X=0, flex=0.15, finger=3)
        w = mix_wing(w0, wing(fold=1.0), k)
    p.wing = {1: w, -1: w}
    # legs: tucked, swung forward and down to the landing spots, planted from touchdown
    reach = ease(ramp(12, LAND_TOUCH, f))
    for s in (1, -1):
        a, b = _rest_leg(s)
        a, b = a + end, b + end
        tq = Pose()
        tq.root, tq.body, tq.pitch = p.root, p.body, p.pitch
        ta, tb = leg_world(dict_legs(tq, s, TUCK(s)), s)
        p.flat[s] = f >= LAND_TOUCH - 6
        if f >= LAND_TOUCH:
            p.legs[s] = ('world', a, b)
        else:
            hover = Vector((0, 0, 0.12 * math.sin(math.pi * reach)))
            p.legs[s] = ('world', ta.lerp(a, reach) + hover, tb.lerp(b, reach) + hover, 1.0 - reach)
        p.thigh[s] = 1.0 - reach
        p.toes[s] = K([(0, 70), (14, 40), (30, -18), (LAND_TOUCH - 2, -12), (LAND_TOUCH + 2, 3), (N, 3)], f)
    if f < 8:
        fp = fly_pose(f)
        fp.root = p.root.copy()
        p = mix_pose(fp, p, ease(f / 8))
    return toward(p, idle_pose(f - N), ease(ramp(N - 8, N, f)))


def _clip_land():
    Y = travel(_LAND_SPEED, LAND_N)
    return LAND_N, (lambda f: land_pose(f, Y)), False


DIVE_N, DIVE_STRIKE = 78, 38
_DIVE_SPEED = lambda f: K([(0, 6.0), (6, 6.0), (14, 6.6), (22, 9.0), (30, 11.0), (DIVE_STRIKE, 4.0), (48, 4.2),
                           (62, 5.4), (72, 6.0), (78, 6.0)], f)


def dive_pose(f, Y=None):
    N = DIVE_N
    Y = Y or travel(_DIVE_SPEED, N)
    p = flying()
    p.floor = 0.0
    p.root = Vector((0, Y[int(f)], 0))
    z = K([(0, FLY_H - 0.0285), (8, 1.80), (14, 1.98), (20, 1.92), (26, 1.40), (32, 0.72), (DIVE_STRIKE, 0.17),
           (43, 0.26), (52, 0.62), (64, 1.15), (N, FLY_H - 0.0285)], f)
    p.body = Vector((0, 0, z))
    p.pitch = K([(0, 5.4), (10, 10), (16, -20), (22, -42), (28, -30), (33, 0), (DIVE_STRIKE, 30), (44, 34),
                 (56, 18), (68, 8), (N, 5.4)], f)
    p.neck = [[K([(0, 3), (16, 4), (24, 5), (32, 3), (DIVE_STRIKE, -12), (48, -4), (N, 3.0)], f), 0, 0],
              [K([(0, 2), (24, 10), (DIVE_STRIKE, -14), (50, -2), (N, 2.0)], f), 0, 0],
              [K([(0, 0), (24, 8), (DIVE_STRIKE, -6), (50, 0), (N, 0.0)], f), 0, 0]]
    p.head = [K([(0, -8), (24, 14), (DIVE_STRIKE, -16), (52, -8), (N, -8.0)], f), 0, 0]
    p.tail = [K([(0, 4.0), (16, 6), (28, 4), (DIVE_STRIKE - 2, -14), (46, -6), (N, 4.0)], f), 0, 0]
    p.tail_fan = K([(0, 18.0), (12, 18), (20, 2), (30, 4), (DIVE_STRIKE - 2, 40), (46, 30), (N, 18.0)], f)
    # wings: a beat up, tucked for the stoop, opened and raised to brake at the strike, heavy beats back up
    stoop = wing(Y=-8, Z=2, X=0, flex=0.72, finger=0)
    brake = wing(Y=-30, Z=-4, X=0, flex=0.18, finger=4)
    heavy = dict(Y=(-30.0, 40.0), Z=(3.0, -12.0), X=8.0, flex=0.2, up_flex=0.45)
    if f <= 14:
        w = fly_beat(f / 14)
    elif f <= 22:
        w = mix_wing(fly_beat(0.0), stoop, ease((f - 14) / 8))
    elif f <= 30:
        w = stoop
    elif f <= 37:
        w = mix_wing(stoop, brake, ease((f - 30) / 7))
    elif f <= 41:
        w = brake
    else:
        w = beats(f, (41, 55, 67, N), (heavy, heavy, dict(heavy, Y=(-30.0, 36.0), Z=(3.0, -10.0), X=7.0,
                                                          up_flex=0.42)))
        if f < 45:
            w = mix_wing(brake, w, ease((f - 41) / 4))
    p.wing = {1: w, -1: w}
    # the talons: tucked, thrown forward under the chest, struck down onto a spot on the ground ahead and held
    # there a moment (clenched), then drawn back into the tuck
    thr = E([(0, 0), (26, 0), (34, 1), (44, 1), (58, 0), (N, 0)], f)
    hit = E([(0, 0), (33, 0), (DIVE_STRIKE - 1, 1), (DIVE_STRIKE + 3, 1), (DIVE_STRIKE + 8, 0), (N, 0)], f)
    spot = Vector((0, Y[DIVE_STRIKE] - 0.16, 0))
    for s in (1, -1):
        tk = TUCK(s)
        fwd_a, fwd_b = (0.060 * s, -0.110, 0.150), (0.058 * s, -0.200, 0.110)
        q = Pose()
        q.root, q.body, q.pitch = p.root, p.body, p.pitch
        q.legs[s] = ('body', Vector(tk[1]).lerp(Vector(fwd_a), thr), Vector(tk[2]).lerp(Vector(fwd_b), thr))
        a, b = leg_world(q, s)
        ra, rb = _rest_leg(s)
        ga, gb = spot + ra + Vector((0, 0.02, 0.02)), spot + rb + Vector((0, 0, 0.012))
        p.legs[s] = ('world', a.lerp(ga, hit), b.lerp(gb, hit), 1.0 - hit)
        p.thigh[s] = 1.0 - 0.8 * thr
        p.toes[s] = K([(0, 70), (24, 70), (33, -25), (DIVE_STRIKE - 1, -18), (DIVE_STRIKE + 2, 40), (60, 60),
                       (N, 70)], f)
    if f < 8:
        fp = fly_pose(f)
        fp.root = p.root.copy()
        p = mix_pose(fp, p, ease(f / 8))
    return toward(p, fly_pose(f - N), ease(ramp(N - 8, N, f)))


def _clip_dive():
    Y = travel(_DIVE_SPEED, DIVE_N)
    return DIVE_N, (lambda f: dive_pose(f, Y)), False


CLIPS = {"Idle": _clip_idle, "Walk": _clip_walk, "TakeOff": _clip_takeoff, "Fly": _clip_fly, "Glide": _clip_glide,
         "Dive": _clip_dive, "Land": _clip_land, "Screech": _clip_screech, "Hit": _clip_hit, "Death": _clip_death}
EVENTS = {"Dive": [("Strike", DIVE_STRIKE / FPS)], "Screech": [("Screech", SCREECH_AT / FPS)],
          "Death": [("Dead", DEATH_HIT / FPS)]}
SHEET_FRAMES = {"Idle": (0, 26, 60, 96, 140, 150), "Walk": (0, 8, 16, 24, 32), "TakeOff": (0, 10, 15, 20, 26, 34, 44, 60),
                "Fly": (0, 5, 10, 15, 20), "Glide": (0, 22, 45, 67), "Dive": (0, 14, 22, 30, 35, 38, 46, 60, 78),
                "Land": (0, 14, 24, 32, 40, 44, 52, 66), "Screech": (0, 10, 16, 30, 46), "Hit": (0, 3, 7, 11, 18),
                "Death": (0, 6, 14, 22, 30, 40, 74)}
# the clips that hand over to each other: (clip, its last frame) -> (next clip, its first frame)
CHAINS = (("TakeOff", "Fly"), ("Fly", "Glide"), ("Glide", "Fly"), ("Fly", "Dive"), ("Dive", "Fly"), ("Fly", "Land"),
          ("Land", "Idle"), ("Idle", "TakeOff"), ("Idle", "Walk"), ("Walk", "Idle"), ("Idle", "Screech"),
          ("Screech", "Idle"), ("Idle", "Hit"), ("Hit", "Idle"), ("Idle", "Death"))


# ----------------------------------------------------------------------------------------- build (the bat's way)


def action_name(clip):
    return f"{EB.NAME}_{clip}"


def build_clip(name, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    N, fn, loop = CLIPS[name]()
    _gauge[0] = GAUGE.get(name, 1.0)
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
    EP._REST.clear()
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
