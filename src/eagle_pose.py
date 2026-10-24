"""Golden eagle poses (2026-10-24): pose functions, not clips (the model is judged first; clips come after Daniel's
look). A Pose -> armature-space matrices for every bone (pose_matrices) -> beast_rig.apply_pose (no keys).

- PERCHED (perched()): standing on the ground with the body raised 50 degrees, the head held level, the wings folded
  along the body (humerus back, forearm forward along the flank, hand back under it; the remiges lie back in one
  stack leaning in over the flank, the secondaries hanging down-back with their fan closed, the primaries running
  back to the tail's middle beside it; the scapulars rolled out over the wing's top edge), the tail closed and lifted
  a little, the toes gripping a little.
- SPREAD (spread()): flying, 0.9 m up: the wings fully out (the bind pose's open wing, the fingers a little wider),
  the tail fanned, the feet tucked back under the tail with the toes closed.

The wings ride on the chest. Each wing bone -- the arm chain, the alula, the primaries, the secondaries' and the
tertials' two bones -- turns from its spread (rest) aim toward its folded aim (fold_frames) along the shortest rotation
(slerp, the dragon's and the bat's way), its head carried by its parent. The folded aims are written in a "horizontal
fold" frame (the wing closed in its own plane: X out, Y back, Z dorsal; phi = the angle from out toward back, beta =
toward the dorsal side) and laid against the flank by FOLD (lay: the dorsal side turned outward about the body's
axis; tilt: the long axis down; yaw: the tips in). Legs: planted feet by two-bone IK (hip -> knee -> the bind pose's
ankle, the tarsus and toes kept as bound), or tucked to body-space targets the same way.
"""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import beast_rig
import dragon_body as DB
import eagle_body as EB

RIG = EB.RIG
SIDES = EB.SIDES
C = Vector((0, 0.040, 0.318))           # the trunk's pivot, between the hip joints


def rad(d):
    return math.radians(d)


def _rot(p=0.0, y=0.0, r=0.0):
    return Matrix.Rotation(rad(p), 4, 'X') @ Matrix.Rotation(rad(y), 4, 'Z') @ Matrix.Rotation(rad(r), 4, 'Y')


class Pose:
    def __init__(self):
        self.root = Vector()
        self.body = Vector()                          # the trunk's offset
        self.pitch = self.roll = self.yaw = 0.0       # deg, + pitch = nose up (about C)
        self.spine = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self.neck = [[0.0, 0.0, 0.0] for _ in range(3)]     # + pitch raises, + yaw turns left
        self.head = [0.0, 0.0, 0.0]
        self.jaw = 0.0                                # deg, + opens
        self.tail = [0.0, 0.0, 0.0]                   # Tail1
        self.tail_fan = 0.0                           # deg the outermost feathers turn out from the closed tail
        self.fold = {1: 0.0, -1: 0.0}                 # 0 = spread (bind) .. 1 = folded
        self.finger = {1: 0.0, -1: 0.0}               # extra spread between neighbouring primaries (deg)
        self.legs = {1: None, -1: None}               # None = planted; or (ankle, ball) in body space (tucked)
        self.toes = {1: 0.0, -1: 0.0}                 # curl, deg (+ grips)


# ----------------------------------------------------------------------------------------- rest data
_REST = {}


def rest():
    if not _REST:
        B = EB.rest_bones()
        _REST['B'] = B
        _REST['R'] = {n: beast_rig.frame_matrix(h, fr) for n, (h, fr, L, par, d) in B.items()}
    return _REST


WING_BONES = (["WingArm", "WingForearm", "WingHand", "WingAlula"] + [f"WingP{k}" for k in range(1, 11)] +
              ["WingSecA", "WingSecB", "WingTertA", "WingTertB"])

# ----------------------------------------------------------------------------------------- the folded wing
# Written for the left wing in the body's rest axes. The folded wing is a stack in one plane against the flank: NRM is
# its outer side (out, leaning in at the top), BACK its long axis. The humerus aims at ELBOW (inside the plane's
# reach: back and down along the side), the forearm forward at WRIST (the bend of the wing, at the breast's side);
# every other wing bone lies in the plane at an angle from BACK toward its top (deg; + up), then turned in about the
# body's vertical (deg, with the hand: the primaries' plane stays the hand's).
# 2026-10-24 (the fold looked like planks standing off the body, saw-toothed): the plane leans in 32 deg (was 17.5),
# the forearm lies lower on the flank (its top edge, the remiges' inner vanes, under the scapulars), the secondaries
# hang 16 deg down-back (were 32: tall planks with a stepped lower edge), their fan closed (FOLD_CLOSE), the
# primaries 3 deg down (their wide inner vanes clear the shoulder), the tertials 4 deg down; the scapulars roll out
# over the wing's top edge (FOLD_SCAP).
FOLD = dict(nrm=(0.85, 0.0, 0.53), back=(0.0, 1.0, -0.06), elbow=(0.106, 0.030, 0.334), wrist=(0.118, -0.205, 0.322))
FOLD_ANG = {"WingHand": (-1.0, 2.0), "WingAlula": (-12.0, 0.0), "WingSecB": (-16.0, 0.0), "WingTertA": (-4.0, 0.0)}
for _k in range(1, 11):
    FOLD_ANG[f"WingP{_k}"] = (-3.0, 2.0)        # (angle up, then turned in about the body's vertical, with the hand)
CROSS = 0.0                          # the left primaries a little higher: they cross over the right ones
RIGID_PAIR = {"WingSecA": "WingSecB", "WingTertB": "WingTertA"}     # turned as their partner, then
# closed by FOLD_CLOSE (deg) toward it: the secondaries' 25 deg spread fan (S1 72 .. S12 97) closes folded
# (2026-10-24), so they lie parallel along the flank. The cards between the two bones blend two rotations about the
# fold's normal 25 deg apart: a rotation, scaled in the fold's plane by cos 12.5 deg (0.976) at most (S6, S7)
FOLD_CLOSE = {"WingSecA": 25.0}
FOLD_LIFT = {"WingAlula": 0.016}    # folded, the alula lies on the coverts: lifted this far (m) along the fold's normal
# folded, a bone's head is carried by this bone instead of its parent (blended by the lay): the tertials' row
# (WingTertA/B) rides the humerus in flight, so a bending elbow leaves them on the arm (it turns back with a flex as
# every wing bone does: rigid with the humerus, the stoop swung them in over the back onto the other side's); folded
# they lie in the stack where the forearm carried them (carried by the humerus they crossed S11/S12 or the coverts,
# 2026-10-24)
FOLD_CARRY = {"WingTertA": "WingForearm"}         # (WingTertB rides WingTertA)
# folded, a bone's head slides this far (m) in the fold's frame (back, up, out; the left side's), by the lay, in its
# parent's frame (so mid-fold the slide stays in the cards' plane): the tertials' row's T6 end goes down and back, so
# T4-T6 shingle back along the stack instead of standing up out of it in a fin (their roots are spread along the
# humerus, which folded lies across the stack: T6 11 cm above T1, 2026-10-24)
FOLD_SLIDE = {"WingTertB": (0.06, -0.08, 0.0)}


def slide_local(name, s):
    """FOLD_SLIDE[name] in its parent's own axes (its parent's folded frame: eagle_pose's and the clips' alike)."""
    n, a, u = _fold_basis()
    da, du, dn = FOLD_SLIDE[name]
    v = a * da + u * du + n * dn
    if s < 0:
        v = Vector((-v.x, v.y, v.z))
    par = rest()['B'][name + ("L" if s > 0 else "R")][3]
    return fold_frame(par[:-1], s).transposed() @ v
FOLD_SCAP = (20.5, 3.0)              # folded, the scapulars roll out and down about their bone, and turn out (deg)


def _fold_basis():
    n = Vector(FOLD['nrm']).normalized()
    a = Vector(FOLD['back'])
    a = (a - n * a.dot(n)).normalized()
    return n, a, n.cross(a)                            # outward, back, up (in the plane)


def fold_frame(name, s):
    """The folded frame (Matrix3, armature space with the chest at rest) of wing bone `name` (no side suffix)."""
    R = rest()['R']
    B = rest()['B']
    sfx = "L" if s > 0 else "R"
    if name in RIGID_PAIR:
        par = RIGID_PAIR[name]
        F = fold_frame(par, s) @ R[par + sfx].to_3x3().inverted() @ R[name + sfx].to_3x3()
        close = FOLD_CLOSE.get(name, 0.0)
        if close:                            # the fan partly closed: turned down in the fold plane
            n = _fold_basis()[0]
            if s < 0:
                n = Vector((-n.x, n.y, n.z))
            F = Matrix.Rotation(rad(-s * close), 3, n) @ F
        return F
    n, a, u = _fold_basis()
    S = R["WingArmL"].translation
    if name == "WingArm":
        d = Vector(FOLD['elbow']) - S
    elif name == "WingForearm":
        L = B["WingArmL"][2]
        elbow = S + (Vector(FOLD['elbow']) - S).normalized() * L
        d = Vector(FOLD['wrist']) - elbow
        d = d - n * d.dot(n)                 # in the plane: the secondaries' layers stay layers along it
    else:
        ang, yaw = FOLD_ANG[name]
        if name.startswith("WingP") and s > 0:
            ang += CROSS
        t = rad(ang)
        d = a * math.cos(t) + u * math.sin(t)
        if yaw:
            Z = Matrix.Rotation(rad(yaw), 3, 'Z')
            d, n = Z @ d, Z @ n
    if s < 0:
        d, n = Vector((-d.x, d.y, d.z)), Vector((-n.x, n.y, n.z))
    return DB._frame(d, n)


# ----------------------------------------------------------------------------------------- legs
def _ik(hip, target, l1, l2, pole):
    d = target - hip
    dist = min(d.length, (l1 + l2) * 0.999)
    u = d.normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    pp = (pole - u * pole.dot(u)).normalized()
    return hip + u * a + pp * h, hip + u * dist


def _aim(R3, rest_dir, new_dir):
    q = Vector(rest_dir).normalized().rotation_difference(Vector(new_dir).normalized())
    return q.to_matrix() @ R3


def _leg(p, W, MB, rel, s, sfx):
    D = rest()
    R, B = D['R'], D['B']
    th, sh, ta = f"Thigh{sfx}", f"Shin{sfx}", f"Tarsus{sfx}"
    hip = (W["Hips"] @ rel(th, "Hips")).translation
    l1, l2 = B[th][2], B[sh][2]
    leg = p.legs[s]
    if leg is None:                                            # planted: the bound ankle, tarsus and toes
        ankle = R[ta].translation.copy()
        tars = R[ta].to_3x3()
        pole = Vector((0.25 * s, -1.0, 0.1))
    else:
        ankle_b, ball_b = leg
        ankle = MB @ Vector(ankle_b)
        ball = MB @ Vector(ball_b)
        tars = _aim(R[ta].to_3x3(), R[ta].col[1].xyz, ball - ankle)
        pole = MB.to_3x3() @ Vector((0.25 * s, -1.0, -0.4))
    knee, ankle = _ik(hip, ankle, l1, l2, pole)
    W[th] = Matrix.Translation(hip) @ _aim(R[th].to_3x3(), R[th].col[1].xyz, knee - hip).to_4x4()
    W[sh] = Matrix.Translation(knee) @ _aim(R[sh].to_3x3(), R[sh].col[1].xyz, ankle - knee).to_4x4()
    W[ta] = Matrix.Translation(ankle) @ tars.to_4x4()
    for i in EB.TOES:
        a, b = f"Toe{i}_1{sfx}", f"Toe{i}_2{sfx}"
        W[a] = W[ta] @ rel(a, ta) @ _rot(-0.4 * p.toes[s])
        W[b] = W[a] @ rel(b, a) @ _rot(-0.6 * p.toes[s])


# ----------------------------------------------------------------------------------------- wings and tail
def _wing(p, W, rel, s, sfx):
    D = rest()
    R, B = D['R'], D['B']
    turn = W["Chest"].to_3x3() @ R["Chest"].to_3x3().inverted()
    t = min(max(p.fold[s], 0.0), 1.0)
    for n in WING_BONES:
        bn = n + sfx
        par = B[bn][3]
        here = W[par] @ rel(bn, par)
        if n in FOLD_SLIDE and t > 0:
            here = W[par] @ Matrix.Translation(slide_local(n, s) * t) @ rel(bn, par)
        if n in FOLD_CARRY and t > 0:
            c = FOLD_CARRY[n] + sfx
            here = Matrix.Translation(here.translation.lerp((W[c] @ rel(bn, c)).translation, t))
        q0 = R[bn].to_3x3()
        if n.startswith("WingP") and p.finger[s]:
            k = int(n[5:])
            ax = R[f"WingHand{sfx}"].col[2].xyz
            q0 = Matrix.Rotation(rad(-s * p.finger[s] * (k - 5.5) / 4.5), 3, ax) @ q0
        q0 = (turn @ q0).to_quaternion()
        q1 = (turn @ fold_frame(n, s)).to_quaternion()
        q = q0.slerp(q1, t) if t > 0 else q0
        W[bn] = Matrix.Translation(here.translation) @ q.to_matrix().to_4x4()
        if n in FOLD_LIFT and t > 0:         # lifted off the stack along the fold's outward normal
            nrm = turn @ _fold_basis()[0]
            if s < 0:
                nrm = turn @ Vector((-_fold_basis()[0].x, _fold_basis()[0].y, _fold_basis()[0].z))
            W[bn] = Matrix.Translation(nrm * FOLD_LIFT[n] * t) @ W[bn]
    sc = "Scap" + sfx
    W[sc] = (W["Chest"] @ rel(sc, "Chest") @ Matrix.Rotation(rad(-s * FOLD_SCAP[1] * t), 4, 'Z') @
             Matrix.Rotation(rad(s * FOLD_SCAP[0] * t), 4, 'Y'))
    gauge(W, rel, sfx, t)


def gauge(W, rel, sfx, lay):
    """The fold's gauge bone (2026-10-24): slid EB.FOLD_GAUGE * lay along its own Y; the hinged cards' shape key
    Fold<side> follows it (eagle_drape)."""
    g = "WingFold" + sfx
    W[g] = W["Chest"] @ rel(g, "Chest") @ Matrix.Translation((0.0, EB.FOLD_GAUGE * lay, 0.0))


def _tail(p, W, rel, s, sfx):
    for k in range(1, 7):
        n = f"TailF{k}{sfx}"
        W[n] = W["Tail1"] @ rel(n, "Tail1") @ _rot(0, -s * p.tail_fan * (k - 0.5) / 5.5)


def pose_matrices(p):
    D = rest()
    R = D['R']
    rel = lambda c, par: R[par].inverted() @ R[c]
    M = Matrix.Translation(p.root)
    BT = (Matrix.Translation(C + p.body) @ Matrix.Rotation(rad(p.yaw), 4, 'Z') @
          Matrix.Rotation(rad(-p.pitch), 4, 'X') @ Matrix.Rotation(rad(p.roll), 4, 'Y') @ Matrix.Translation(-C))
    MB = M @ BT
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
        _leg(p, W, MB, rel, s, sfx)
        _wing(p, W, rel, s, sfx)
        _tail(p, W, rel, s, sfx)
    W["Socket_Head"] = W["Head"] @ rel("Socket_Head", "Head")
    W["Socket_Mouth"] = W["Jaw"] @ rel("Socket_Mouth", "Jaw")
    W["Socket_Grip"] = W["TarsusR"] @ rel("Socket_Grip", "TarsusR")
    Minv = M.inverted()
    out = {k: Minv @ v for k, v in W.items()}
    out["Motion"] = M @ R["Motion"]
    return out


# ----------------------------------------------------------------------------------------- the two poses
LIFT = 0.9                                         # the spread pose's height over the ground (m)


def perched():
    p = Pose()
    p.pitch = 50.0
    p.body = Vector((0, 0.0, -0.010))
    p.neck = [[-16.0, 0, 0], [-18.0, 0, 0], [-14.0, 0, 0]]
    p.head = [-4.0, 0, 0]
    p.tail = [6.0, 0, 0]
    p.fold = {1: 1.0, -1: 1.0}
    p.toes = {1: 4.0, -1: 4.0}
    return p


def spread():
    p = Pose()
    p.body = Vector((0, 0.0, LIFT))
    p.pitch = 3.0
    p.neck = [[3.0, 0, 0], [2.0, 0, 0], [0.0, 0, 0]]
    p.head = [-8.0, 0, 0]
    p.tail = [2.0, 0, 0]
    p.tail_fan = 34.0
    p.finger = {1: 3.0, -1: 3.0}
    tuck = lambda s: ((0.055 * s, 0.085, 0.262), (0.040 * s, 0.180, 0.262))
    p.legs = {1: tuck(1), -1: tuck(-1)}
    p.toes = {1: 70.0, -1: 70.0}
    return p


def bind():
    return Pose()


def folded():
    """The bind pose with the wings folded (body level): for tuning the fold in the body's own axes."""
    p = Pose()
    p.fold = {1: 1.0, -1: 1.0}
    return p


POSES = dict(perched=perched, spread=spread, bind=bind, folded=folded)


def still(p, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    if rig_ob.animation_data:
        rig_ob.animation_data.action = None
    beast_rig.apply_pose(rig_ob, pose_matrices(p), keys=False)
    bpy.context.view_layer.update()


def clear(rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[RIG]
    beast_rig.reset_pose(rig_ob)


def use(name, rig_ob=None):
    _REST.clear()
    still(POSES[name](), rig_ob)
