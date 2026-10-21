"""Chicken clips (2026-10-20), keyed straight onto the bird rig (chicken_body.rest_bones) with beast_rig.apply_pose.

The quadrupeds' clip machinery (beast_anim) assumes four legs, so the hen has her own small pose system in the same
style: a Pose per frame (root travel on Motion, the trunk's offset / pitch / roll / yaw about its centre, per-bone
bends of neck, head, jaw, tail, the wings' flap and fold, per leg a foot target), turned into armature-space matrices
(pose_matrices) and keyed. Legs: the foot is placed (planted on the ground, or carried by the trunk), the shank
(HindFoot) is given a tilt, and the thigh and drumstick reach the ankle by two-bone IK with the knee kept forward.
The skeleton plays in place; Motion travels (Unity root motion), as for the beasts.

Clips (30 fps, the hen faces -Y; Unity +Z):
  Idle     3.0 s loop   breathing, jerky looks round, a tail flick, a weight shift
  Peck     2.4 s loop   bent to the ground, three quick pecks, a look between
  Scratch  2.0 s loop   a foot rakes back twice each side, head down watching
  Alert    1.2 s        stands tall, neck up, head cocked; holds the end
  Call     1.2 s        a cluck: head jerks, the beak opens twice
  Walk     0.6 s loop   the head holds still and thrusts forward each step (root motion ~0.3 m/s)
  Run      0.33 s loop  long strides, wings half out (root motion ~1.6 m/s)
  Flap     1.0 s        wings beat, a hop up and down
  Hit      0.5 s        a flinch, wings jerk
  Death    1.5 s        falls onto her left side, the legs stiff; holds (event 'Dead' at 1.2 s)
  Sleep    3.0 s loop   sitting, legs folded under, head tucked back
  Wake     1.2 s        head up, stands, a ruffle
"""
import bpy, math
from mathutils import Vector, Matrix
import beast_rig
import beast_anim as BA
from beast_anim import K, ease, two_bone
import chicken_body as CB

FPS = 30
FWD = Vector((0, -1, 0))
C = Vector((0, 0.02, 0.21))                       # the trunk's pivot
RIG = CB.NAME + "Rig"
EVENTS = {"Death": [("Dead", 1.2)]}
MOVING = {"Walk", "Run"}
SIDES = (1, -1)


def rad(d):
    return math.radians(d)


def _rot(p=0.0, y=0.0, r=0.0):
    return Matrix.Rotation(rad(p), 4, 'X') @ Matrix.Rotation(rad(y), 4, 'Z') @ Matrix.Rotation(rad(r), 4, 'Y')


class Leg:
    def __init__(self, target=None, tilt=0.0, toe=0.0, carried=0.0, off=None):
        self.target = target            # foot (shank's end) position, world; None = rest
        self.tilt = tilt                # shank tilt, deg: + leans the ankle back (folding), - forward
        self.toe = toe                  # toes, deg: - curls down
        self.carried = carried          # 0 = target on the ground, 1 = carried by the trunk (rest foot + off)
        self.off = off if off is not None else Vector()


class Pose:
    def __init__(self):
        self.root = Vector()
        self.body = Vector()
        self.pitch = self.roll = self.yaw = 0.0
        self.chest = [0.0, 0.0, 0.0]
        self.neck = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self.head = [0.0, 0.0, 0.0]
        self.bob = Vector()              # world offset of the neck's base (the walk's head hold)
        self.jaw = 0.0
        self.tail = [0.0, 0.0, 0.0]
        self.wings = {1: [0.0, 0.0], -1: [0.0, 0.0]}   # (flap: + up and out, fold: + tip out)
        self.legs = {1: Leg(), -1: Leg()}


_REST = {}


def rest():
    if not _REST:
        B = CB.rest_bones()
        _REST['B'] = B
        _REST['R'] = {n: beast_rig.frame_matrix(h, fr) for n, (h, fr, L, par, d) in B.items()}
    return _REST


def foot0(s):
    R = rest()['R']
    sfx = "L" if s > 0 else "R"
    return R[f"HindToes{sfx}"].translation.copy()


def pose_matrices(p):
    D = rest()
    B, R = D['B'], D['R']
    rel = lambda c, par: R[par].inverted() @ R[c]
    M = Matrix.Translation(p.root)
    BT = (Matrix.Translation(C + p.body) @ Matrix.Rotation(rad(p.yaw), 4, 'Z') @
          Matrix.Rotation(rad(-p.pitch), 4, 'X') @ Matrix.Rotation(rad(p.roll), 4, 'Y') @ Matrix.Translation(-C))
    MB = M @ BT
    W = {"Root": M @ R["Root"]}
    W["Hips"] = MB @ R["Hips"]
    W["Chest"] = W["Hips"] @ rel("Chest", "Hips") @ _rot(*p.chest)
    W["Neck1"] = Matrix.Translation(p.bob) @ W["Chest"] @ rel("Neck1", "Chest") @ _rot(*p.neck[0])
    W["Neck2"] = W["Neck1"] @ rel("Neck2", "Neck1") @ _rot(*p.neck[1])
    W["Head"] = W["Neck2"] @ rel("Head", "Neck2") @ _rot(*p.head)
    W["Jaw"] = W["Head"] @ rel("Jaw", "Head") @ _rot(-p.jaw)
    W["Tail1"] = W["Hips"] @ rel("Tail1", "Hips") @ _rot(*p.tail)
    for s in SIDES:
        sfx = "L" if s > 0 else "R"
        flap, fold = p.wings[s]
        W[f"Wing{sfx}"] = W["Chest"] @ rel(f"Wing{sfx}", "Chest") @ _rot(0, -s * fold * 0.4, -s * flap)
        W[f"WingTip{sfx}"] = W[f"Wing{sfx}"] @ rel(f"WingTip{sfx}", f"Wing{sfx}") @ _rot(0, -s * fold, -s * flap * 0.5)
        _leg(p, s, sfx, W, MB, R, B)
    W["Socket_Head"] = W["Head"] @ rel("Socket_Head", "Head")
    W["Socket_Mouth"] = W["Jaw"] @ rel("Socket_Mouth", "Jaw")
    Minv = M.inverted()
    out = {k: Minv @ v for k, v in W.items()}
    out["Motion"] = M @ R["Motion"]
    return out


def _leg(p, s, sfx, W, MB, R, B):
    lp = p.legs[s]
    th, sh, ft, to = (f"{n}{sfx}" for n in ("Thigh", "Shin", "HindFoot", "HindToes"))
    F0 = foot0(s)
    ground = (p.root + F0) if lp.target is None else lp.target.copy()
    carried = MB @ (F0 + lp.off)
    F = ground.lerp(carried, lp.carried)
    if lp.carried < 0.5:
        F.z = max(F.z, 0.006)
    Mr = MB.to_3x3()
    rest_up = (R[ft].translation - F0).normalized()                 # foot -> ankle at rest
    tilt = Matrix.Rotation(rad(-lp.tilt), 3, 'X')                   # + tips the ankle back (+y)
    A = F + (Mr @ (tilt @ rest_up)) * B[ft][2]
    H = (MB @ R[th]).translation
    pole = Mr @ Vector((0, -1, 0.3))                                # the knee stays forward
    Kn, A2 = two_bone(H, A, B[th][2], B[sh][2], pole)
    xh = Mr @ R[th].col[0].xyz
    W[th] = BA._frame(H, Kn - H, xh)
    W[sh] = BA._frame(Kn, A2 - Kn, xh)
    W[ft] = BA._frame(A2, F - A2, xh)
    toe_dir = Mr @ (R[to].col[1].xyz)
    toe_dir.z = 0
    toe_dir = toe_dir.normalized() if toe_dir.length > 1e-6 else Vector((0, -1, 0))
    toe_dir = Matrix.Rotation(rad(-lp.toe), 3, Mr @ Vector((1, 0, 0))) @ toe_dir       # - curls them down
    W[to] = BA._frame(W[ft].translation + W[ft].col[1].xyz * B[ft][2], toe_dir, xh)


# ----------------------------------------------------------------------------------------- helpers
def _look(f, keys, N=None):
    """Chickens move the head in snaps: a held key track with quick changes."""
    return K(keys, f, N)


def _breath(p, f, period=30, amp=0.002):
    p.body.z += amp * math.sin(2 * math.pi * f / period)


def _step_targets(p, f, N, stride, duty, lift, phases):
    """Feet for a cyclic biped gait (beast_anim.gait's way): planted while in stance, swung forward in the air.
    -> the swing amount per side."""
    p.root = FWD * (stride * f / N)
    exc = stride * duty
    sw = {}
    for s in SIDES:
        ph = (f / N + phases[s]) % 1.0
        F0 = foot0(s)
        if ph < duty:
            u, z, q = 0.5 - ph / duty, 0.0, 0.0
        else:
            q = (ph - duty) / (1 - duty)
            u = -0.5 + ease(q)
            z = lift * math.sin(math.pi * q) ** 0.8
        t = p.root + F0 + FWD * exc * u
        t.z = F0.z + z
        a = math.sin(math.pi * q) if ph >= duty else 0.0
        p.legs[s] = Leg(target=t, tilt=35 * a, toe=-45 * a)
        sw[s] = a
    return sw


def _head_hold(p, f, N, stride, k=0.5):
    """The head holds still in the world for most of each step, then thrusts forward: the neck's base is offset
    against the root's travel (k of it, or the neck stretches too far)."""
    q = (2 * f / N) % 1.0
    s = 0.0 if q < 0.65 else ease((q - 0.65) / 0.35)
    p.bob = Vector((0, -(stride / 2) * (s - q) * k, 0))


# ----------------------------------------------------------------------------------------- clips
def _clip_idle():
    N = 90

    def fn(f):
        p = Pose()
        a = 2 * math.pi * f / N
        _breath(p, f)
        shift = K([(0, 0), (30, 0), (36, 1), (60, 1), (66, 0), (90, 0)], f, N)
        p.body.x = 0.006 * shift
        p.roll = 3 * shift
        look = _look(f, [(0, 0), (12, 0), (14, 30), (34, 30), (36, -20), (58, -20), (60, 10), (76, 10), (78, 0), (90, 0)], N)
        cock = _look(f, [(0, 0), (40, 0), (42, 20), (54, 20), (56, 0), (90, 0)], N)
        p.neck = [[2 * math.sin(a), look * 0.3, 0], [0, look * 0.3, 0]]
        p.head = [0, look * 0.4, cock]
        flick = K([(0, 0), (70, 0), (72, 1), (74, -0.5), (76, 0.3), (78, 0), (90, 0)], f, N)
        p.tail = [4 * math.sin(a), 18 * flick, 0]
        p.wings = {1: [0, 0], -1: [0, 0]}
        return p
    return N, fn, True


def _clip_peck():
    N = 72

    def fn(f):
        p = Pose()
        a = 2 * math.pi * f / N
        _breath(p, f)
        down = K([(0, 0.4), (8, 0.4), (11, 1), (14, 0.45), (20, 0.45), (23, 1), (26, 0.45), (32, 0.45), (35, 1),
                  (38, 0.4), (54, 0.2), (66, 0.4), (72, 0.4)], f, N)
        p.pitch = -34 - 6 * down
        p.body.z += -0.030 - 0.015 * down                                 # the legs bend: she leans into it
        p.body.y += 0.01
        look = _look(f, [(0, 0), (40, 0), (42, 25), (52, 25), (54, -15), (62, -15), (64, 0), (72, 0)], N)
        p.neck = [[-50 * down - 10, look * 0.3, 0], [-45 * down, look * 0.3, 0]]
        p.head = [-30 * down, look * 0.4, 0]
        p.jaw = 10 * K([(0, 0), (9, 0), (10, 1), (12, 0), (21, 0), (22, 1), (24, 0), (33, 0), (34, 1), (36, 0), (72, 0)], f, N)
        p.tail = [10, 6 * math.sin(a), 0]
        return p
    return N, fn, True


def _clip_scratch():
    N = 60

    def fn(f):
        p = Pose()
        _breath(p, f)
        p.pitch = -10
        p.neck = [[-14, 0, 0], [-16, 0, 0]]
        p.head = [-10, 0, 8 * math.sin(2 * math.pi * f / N)]
        p.tail = [8, 0, 0]
        for s, c0 in ((1, 0), (-1, 30)):
            u = (f - c0) % N                                   # this foot's own time: two rakes, then rest
            r1 = K([(0, 0), (4, 1), (9, 0), (13, 1), (18, 0), (60, 0)], u)
            F0 = foot0(s)
            t = F0 + Vector((0, -0.025 + 0.07 * r1, 0.02 * math.sin(math.pi * r1)))
            p.legs[s] = Leg(target=t, tilt=25 * r1, toe=-30 * r1)
            p.roll += -4 * s * r1
            p.body.x += 0.008 * s * r1
        return p
    return N, fn, True


def _clip_alert():
    N = 36

    def fn(f):
        p = Pose()
        up = K([(0, 0), (5, 1.05), (9, 1), (36, 1)], f)
        p.pitch = 8 * up
        p.body.z = 0.015 * up
        p.neck = [[18 * up, 0, 0], [10 * up, 0, 0]]
        cock = _look(f, [(0, 0), (12, 0), (14, 25), (24, 25), (26, -15), (36, -15)])
        p.head = [-8 * up, cock * 0.5, cock]
        p.tail = [12 * up, 0, 0]
        p.wings = {1: [4 * up, 0], -1: [4 * up, 0]}
        return p
    return N, fn, False


def _clip_call():
    N = 36

    def fn(f):
        p = Pose()
        jerk = K([(0, 0), (6, 0), (8, 1), (12, 0.6), (16, 1), (22, 0.5), (30, 0), (36, 0)], f)
        p.neck = [[8 * jerk, 0, 0], [4 * jerk, 0, 0]]
        p.head = [12 * jerk, 0, 0]
        p.jaw = 28 * K([(0, 0), (7, 0), (9, 1), (12, 0), (15, 0), (17, 1), (21, 0), (36, 0)], f)
        p.pitch = 3 * jerk
        p.tail = [6 * jerk, 0, 0]
        return p
    return N, fn, False


WALK_STRIDE, RUN_STRIDE = 0.18, 0.55


def _clip_walk():
    N = 18

    def fn(f):
        p = Pose()
        sw = _step_targets(p, f, N, WALK_STRIDE, 0.62, 0.035, {1: 0.0, -1: 0.5})
        a = 2 * math.pi * f / N
        p.body = Vector((0.010 * math.sin(a), 0, 0.004 * math.cos(2 * a)))
        p.roll = 6 * math.sin(a)
        p.yaw = 3 * math.sin(a)
        _head_hold(p, f, N, WALK_STRIDE)
        p.neck = [[2, -3 * math.sin(a), 0], [0, 0, 0]]
        p.tail = [4, 6 * math.sin(a), 0]
        return p
    return N, fn, True


def _clip_run():
    N = 10

    def fn(f):
        p = Pose()
        _step_targets(p, f, N, RUN_STRIDE, 0.42, 0.06, {1: 0.0, -1: 0.5})
        a = 2 * math.pi * f / N
        p.pitch = -14
        p.body = Vector((0.008 * math.sin(a), 0, 0.010 + 0.012 * math.cos(2 * a)))
        p.roll = 5 * math.sin(a)
        p.neck = [[-10, 0, 0], [6, 0, 0]]
        p.head = [12, 0, 0]
        p.tail = [-6, 0, 0]
        beat = math.sin(2 * a)
        p.wings = {1: [30 + 18 * beat, 10], -1: [30 + 18 * beat, 10]}
        return p
    return N, fn, True


def _clip_flap():
    N = 30

    def fn(f):
        p = Pose()
        hop = K([(0, 0), (5, -0.4), (9, 1), (15, 1.1), (21, 0.6), (25, 0), (27, -0.3), (30, 0)], f)
        p.body.z = 0.09 * max(hop, 0) - 0.03 * max(-hop, 0)
        p.pitch = 10 * K([(0, 0), (8, 1), (22, 1), (30, 0)], f)
        beat = math.sin(2 * math.pi * f / 6)
        open_ = K([(0, 0), (4, 1), (24, 1), (30, 0)], f)
        p.wings = {s: [open_ * (55 + 35 * beat), open_ * 25] for s in SIDES}
        p.neck = [[10 * open_, 0, 0], [0, 0, 0]]
        p.tail = [20 * open_, 0, 0]
        for s in SIDES:
            p.legs[s] = Leg(carried=max(hop, 0), off=Vector((0, 0.01, 0.0)), tilt=20 * max(hop, 0))
        return p
    return N, fn, False


def _clip_hit():
    N = 15

    def fn(f):
        p = Pose()
        k = K([(0, 0), (3, 1), (7, 0.5), (11, -0.15), (15, 0)], f)
        p.body = Vector((0.02 * k, 0.015 * k, -0.01 * max(k, 0)))
        p.roll, p.yaw = 10 * k, -8 * k
        p.neck = [[-8 * k, -10 * k, 0], [-6 * k, -8 * k, 0]]
        p.head = [10 * k, -10 * k, 12 * k]
        p.jaw = 20 * K([(0, 0), (3, 1), (8, 0.2), (15, 0)], f)
        p.wings = {s: [40 * max(k, 0), 15 * max(k, 0)] for s in SIDES}
        p.tail = [20 * k, 0, 0]
        return p
    return N, fn, False


SIT_DROP = 0.105


def _sit(p, k):
    """Sitting on the ground: the trunk sinks, the feet stay planted and the shanks fold back under her."""
    p.body.z -= SIT_DROP * k
    for s in SIDES:
        F0 = foot0(s)
        p.legs[s] = Leg(target=p.root + F0 + Vector((0, -0.02 * k, 0)), tilt=78 * k, toe=10 * k)


def _clip_death():
    N = 45

    def fn(f):
        p = Pose()
        fall = K([(0, 0), (6, 0.1), (16, 0.6), (22, 1), (26, 0.95), (45, 1)], f)
        p.roll = 88 * fall
        p.body = Vector((0.07 * fall, 0, -0.125 * fall))
        p.pitch = -6 * fall
        jerk = K([(0, 0), (3, 1), (10, 0)], f)
        dn = K([(0, 0), (18, 0), (30, 1), (45, 1)], f)
        p.neck = [[10 * jerk - 25 * dn, 0, 0], [-15 * dn, 0, 0]]
        p.head = [-10 * dn, 0, -20 * dn]
        p.jaw = 14 * K([(0, 0), (3, 1), (30, 0.5), (45, 0.5)], f)
        p.wings = {s: [K([(0, 0), (4, 50), (16, 20), (45, 12)], f), 10] for s in SIDES}
        p.tail = [-10 * dn, 0, 0]
        for s in SIDES:
            p.legs[s] = Leg(carried=fall, off=Vector((0, -0.01, 0.025)), tilt=-15 * fall, toe=-35 * fall)
        return p
    return N, fn, False


def _clip_sleep():
    N = 90

    def fn(f):
        p = Pose()
        a = 2 * math.pi * f / N
        _sit(p, 1.0)
        p.body.z += 0.003 * math.sin(a)
        p.neck = [[-20, 35, 0], [-25, 40, 0]]                         # head tucked back along the side
        p.head = [10 + 2 * math.sin(a), 70, 20]
        p.tail = [-4, 0, 0]
        p.wings = {s: [3, 0] for s in SIDES}
        return p
    return N, fn, True


def _clip_wake():
    N = 36

    def fn(f):
        p = Pose()
        t = f / N
        sit = 1 - ease((t - 0.30) / 0.45)
        _sit(p, sit)
        tuck = 1 - ease(t / 0.35)
        p.neck = [[-20 * tuck, 35 * tuck, 0], [-25 * tuck, 40 * tuck, 0]]
        shake = K([(0, 0), (26, 0), (28, 1), (30, -1), (32, 0.6), (34, -0.3), (36, 0)], f)
        p.head = [10 * tuck, 70 * tuck + 8 * shake, 20 * tuck + 25 * shake]
        p.wings = {s: [12 * abs(shake), 0] for s in SIDES}
        p.roll = 6 * shake
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Peck": _clip_peck, "Scratch": _clip_scratch, "Alert": _clip_alert, "Call": _clip_call,
         "Walk": _clip_walk, "Run": _clip_run, "Flap": _clip_flap, "Hit": _clip_hit, "Death": _clip_death,
         "Sleep": _clip_sleep, "Wake": _clip_wake}
SHEET_FRAMES = {"Idle": (0, 14, 36, 60, 72), "Peck": (0, 11, 23, 35, 54), "Scratch": (0, 4, 13, 34, 43),
                "Alert": (0, 5, 14, 30), "Call": (0, 9, 17, 30), "Walk": (0, 3, 6, 9, 12, 15),
                "Run": (0, 2, 4, 6, 8), "Flap": (0, 5, 9, 12, 15, 25), "Hit": (0, 3, 7, 11),
                "Death": (0, 10, 16, 22, 45), "Sleep": (0, 45), "Wake": (0, 10, 18, 26, 30, 36)}


# ----------------------------------------------------------------------------------------- build (beast_anim's way)
def action_name(clip):
    return f"{CB.NAME}_{clip}"


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
