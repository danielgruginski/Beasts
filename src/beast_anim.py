"""Clip machinery shared by the quadrupeds (moved out of wolf_anim.py): poses, leg IK, gaits, key tracks, keying.

A creature module describes itself with a Species (its bone table, trunk pivot, action prefix, how many neck and
tail bones, whether it has a tongue). Every frame is a Pose: where the root is (it travels on the Motion bone; the
skeleton plays in place), how the trunk sits (offset, pitch, roll, yaw about the pivot), per-bone bends of spine,
neck, head, tail and ears, the jaw (and tongue), and per leg a paw target for the leg IK plus the distal-segment flex,
toe curl and (front) shoulder-blade swing. `pose_matrices` turns that into armature-space bone matrices;
beast_rig.apply_pose keys them.

Bone names are shared by all quadrupeds: Hips, Spine1, Spine2, Chest, Neck1.., Head, Jaw, (Tongue1, Tongue2),
EarL/R, Tail1.., ScapulaL/R, UpperArm, Forearm, FrontPaw, FrontToes, Thigh, Shin, HindFoot, HindToes; the mammoth
adds Trunk1.. hanging from Head (Species.trunk_n, Pose.trunk: + pitch curls it toward its front).

Legs: the distal segment (front paw / hind foot) keeps its rest angle turned by `flex`; the two segments above it
are a 2-bone IK on the bind pose's own knee side. Paw targets are on the ground (absolute) or, with weight `wb`,
carried by the trunk (in the air, lying dead). Paws and toes never go below the ground.
"""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix
import beast_rig

LEGS = [('F', 1), ('F', -1), ('H', 1), ('H', -1)]

# footfall phases (fraction of the cycle) per leg
WALK = {('H', 1): 0.0, ('F', 1): 0.25, ('H', -1): 0.5, ('F', -1): 0.75}          # lateral sequence
TROT = {('H', 1): 0.0, ('F', -1): 0.02, ('H', -1): 0.5, ('F', 1): 0.52}          # diagonal pairs
GALLOP = {('H', 1): 0.0, ('H', -1): 0.10, ('F', -1): 0.44, ('F', 1): 0.54}       # rotary gallop
BOUND = {('H', 1): 0.0, ('H', -1): 0.04, ('F', 1): 0.46, ('F', -1): 0.54}        # half-bound (rodents)


def rad(d):
    return math.radians(d)


class Species:
    def __init__(self, rest_bones, body_c, prefix, rig, neck_n=2, tail_n=5, tongue=True, tail_floor=None, trunk_n=0):
        self.rest_bones = rest_bones
        self.body_c = Vector(body_c)
        self.prefix = prefix
        self.rig = rig
        self.neck_n = neck_n
        self.tail_n = tail_n
        self.tongue = tongue
        self.tail_floor = tail_floor      # per tail bone: lowest z of its end (a tail lying on the ground drags)
        self.trunk_n = trunk_n            # the mammoth's trunk: Trunk1.. from Head
        self.rest = {}

    def action_name(self, clip):
        return f"{self.prefix}_{clip}"


class LegPose:
    def __init__(self, target=None, flex=0.0, toe=0.0, scap=0.0, wb=0.0, boff=None):
        self.target = target        # absolute paw target (None = the rest paw point, planted)
        self.flex = flex            # distal segment turn, deg (front: - folds the paw back; hind: + flexes the hock)
        self.toe = toe              # toes, deg (- curls down)
        self.scap = scap            # front: shoulder blade swing, deg (+ forward)
        self.wb = wb                # 0 = target on the ground, 1 = carried by the trunk (rest paw point + boff)
        self.boff = boff if boff is not None else Vector()


class Pose:
    def __init__(self, sp):
        self.root = Vector()
        self.root_yaw = 0.0
        self.body = Vector()
        self.pitch = self.roll = self.yaw = 0.0           # trunk, deg (pitch + = nose up)
        self.hips = [0.0, 0.0, 0.0]                       # (pitch, yaw, roll) in the bone's frame, deg
        self.spine = [[0.0, 0.0, 0.0] for _ in range(3)]  # Spine1, Spine2, Chest: + pitch arches the front up
        self.neck = [[0.0, 0.0, 0.0] for _ in range(sp.neck_n)]   # + pitch raises the head, + yaw turns it left
        self.head = [0.0, 0.0, 0.0]
        self.jaw = 0.0                                    # + opens
        self.tongue = [0.0, 0.0]                          # (slide out m, droop deg)
        self.ears = {1: [0.0, 0.0], -1: [0.0, 0.0]}      # (+ forward / - pinned back, + splay out)
        self.tail = [[0.0, 0.0, 0.0] for _ in range(sp.tail_n)]  # + pitch lifts, yaw swings
        self.trunk = [[0.0, 0.0, 0.0] for _ in range(sp.trunk_n)]  # + pitch curls it toward its front, yaw swings
        self.legs = {k: LegPose() for k in LEGS}


# ----------------------------------------------------------------------------------------- rest data
def rest_data(sp):
    if sp.rest:
        return sp.rest
    B = sp.rest_bones()
    R = {n: beast_rig.frame_matrix(h, fr) for n, (h, fr, L, par, d) in B.items()}
    sp.rest.update(B=B, R=R)
    for kind, s in LEGS:
        sfx = 'L' if s > 0 else 'R'
        toes = f"FrontToes{sfx}" if kind == 'F' else f"HindToes{sfx}"
        sp.rest[('paw', kind, s)] = R[toes].translation.copy()
        sp.rest[('toe_z', kind, s)] = (R[toes].translation + R[toes].col[1].xyz * B[toes][2]).z
        up, lo = (f"UpperArm{sfx}", f"Forearm{sfx}") if kind == 'F' else (f"Thigh{sfx}", f"Shin{sfx}")
        A, Kn, J2 = R[up].translation, R[lo].translation, R[lo].translation + R[lo].col[1].xyz * B[lo][2]
        u = (J2 - A).normalized()
        sp.rest[('pole', kind, s)] = ((Kn - A) - u * (Kn - A).dot(u)).normalized()    # the bind pose's knee side
    return sp.rest


def neutral(sp, key):
    return rest_data(sp)[('paw',) + key].copy()


def _rot(p=0.0, y=0.0, r=0.0):
    return (Matrix.Rotation(rad(p), 4, 'X') @ Matrix.Rotation(rad(y), 4, 'Z') @ Matrix.Rotation(rad(r), 4, 'Y'))


def _frame(head, ydir, xhint):
    Y = Vector(ydir).normalized()
    X = Vector(xhint)
    X = (X - Y * X.dot(Y)).normalized()
    Z = X.cross(Y)
    m = Matrix((X, Y, Z)).transposed().to_4x4()
    m.translation = head
    return m


def two_bone(A, T, L1, L2, pole):
    """Knee/elbow position and the reachable end point for a 2-bone chain from A toward T."""
    dv = T - A
    d = dv.length
    u = dv.normalized()
    dc = min(max(d, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.9995)
    v = pole - u * pole.dot(u)
    v.normalize()
    ca = (L1 * L1 + dc * dc - L2 * L2) / (2 * L1 * dc)
    sa = math.sqrt(max(0.0, 1 - ca * ca))
    K = A + u * (L1 * ca) + v * (L1 * sa)
    return K, A + u * dc


def pose_matrices(sp, p):
    D = rest_data(sp)
    B, R = D['B'], D['R']
    rel = lambda c, par: R[par].inverted() @ R[c]
    C = sp.body_c
    M = Matrix.Translation(p.root) @ Matrix.Rotation(rad(p.root_yaw), 4, 'Z')
    BT = (Matrix.Translation(C + p.body) @ Matrix.Rotation(rad(p.yaw), 4, 'Z') @
          Matrix.Rotation(rad(-p.pitch), 4, 'X') @ Matrix.Rotation(rad(p.roll), 4, 'Y') @ Matrix.Translation(-C))
    MB = M @ BT
    Wm = {"Root": M @ R["Root"]}
    Wm["Hips"] = MB @ R["Hips"] @ _rot(*p.hips)
    Wm["Spine1"] = MB @ R["Spine1"] @ _rot(*p.spine[0])
    Wm["Spine2"] = Wm["Spine1"] @ rel("Spine2", "Spine1") @ _rot(*p.spine[1])
    Wm["Chest"] = Wm["Spine2"] @ rel("Chest", "Spine2") @ _rot(*p.spine[2])
    par = "Chest"
    for i in range(sp.neck_n):
        n = f"Neck{i + 1}"
        Wm[n] = Wm[par] @ rel(n, par) @ _rot(*p.neck[i])
        par = n
    Wm["Head"] = Wm[par] @ rel("Head", par) @ _rot(*p.head)
    Wm["Jaw"] = Wm["Head"] @ rel("Jaw", "Head") @ _rot(-p.jaw)
    if sp.tongue:
        Wm["Tongue1"] = Wm["Jaw"] @ rel("Tongue1", "Jaw") @ Matrix.Translation((0, p.tongue[0], 0)) @ _rot(-p.tongue[1])
        Wm["Tongue2"] = Wm["Tongue1"] @ rel("Tongue2", "Tongue1") @ _rot(-p.tongue[1] * 1.3)
    par = "Head"
    for i in range(sp.trunk_n):
        n = f"Trunk{i + 1}"
        Wm[n] = Wm[par] @ rel(n, par) @ _rot(*p.trunk[i])
        par = n
    for s, sfx in ((1, "L"), (-1, "R")):
        e = p.ears[s]
        Wm[f"Ear{sfx}"] = Wm["Head"] @ rel(f"Ear{sfx}", "Head") @ _rot(e[0], -s * e[1])
    par = "Hips"
    for i in range(sp.tail_n):
        n = f"Tail{i + 1}"
        Wm[n] = Wm[par] @ rel(n, par) @ _rot(*p.tail[i])
        if sp.tail_floor is not None:
            Wm[n] = _tail_drag(Wm[n], B[n][2], sp.tail_floor[i])
        par = n
    Mr = M.to_3x3()
    for key in LEGS:
        _leg(sp, p, key, Wm, MB, Mr, R, B, rel)
    # the skeleton plays in place; only the Motion bone travels (Unity turns it into root motion)
    Minv = M.inverted()
    out = {k: Minv @ v for k, v in Wm.items()}
    out["Motion"] = M @ R["Motion"]
    return out


def _tail_drag(m, L, floor):
    """If this tail bone's end would go under `floor`, tilt it up about its head (keeping its heading) so the end
    rests on the floor: the tail drags along the ground instead of passing through it."""
    head = m.translation
    Y = m.col[1].xyz.normalized()
    if (head + Y * L).z >= floor:
        return m
    h = Vector((Y.x, Y.y, 0.0))
    if h.length < 1e-6:
        return m
    h.normalize()
    tz = max(-0.999, min(0.9, (floor - head.z) / L))
    newY = h * math.sqrt(1 - tz * tz) + Vector((0, 0, tz))
    q = Y.rotation_difference(newY)
    return Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ m


def _leg(sp, p, key, Wm, MB, Mr, R, B, rel):
    kind, s = key
    sfx = 'L' if s > 0 else 'R'
    lp = p.legs[key]
    if kind == 'H':
        names = [f"Thigh{sfx}", f"Shin{sfx}", f"HindFoot{sfx}", f"HindToes{sfx}"]
        att = Wm["Hips"] @ rel(names[0], "Hips")
    else:
        scap = f"Scapula{sfx}"
        Wm[scap] = Wm["Chest"] @ rel(scap, "Chest") @ _rot(lp.scap)
        names = [f"UpperArm{sfx}", f"Forearm{sfx}", f"FrontPaw{sfx}", f"FrontToes{sfx}"]
        att = Wm[scap] @ rel(names[0], scap)
    A = att.translation
    T3 = att.to_3x3() @ R[names[0]].to_3x3().inverted()   # how the leg's attachment has turned from the bind pose
    pole = T3 @ rest_data(sp)[('pole',) + key]            # the knee/elbow stays on its bind-pose side
    hinge = att.to_3x3().col[0].normalized()
    L = [B[n][2] for n in names[:3]]
    rest_paw = rest_data(sp)[('paw',) + key]
    ground = lp.target.copy() if lp.target is not None else rest_paw.copy()
    carried = MB @ (rest_paw + lp.boff)
    P = ground.lerp(carried, max(0.0, min(1.0, lp.wb)))
    P.z = max(P.z, rest_paw.z - 0.01)                    # a carried paw (rolling over, landing) never sinks in
    wb = max(0.0, min(1.0, lp.wb))
    orient = lambda v: ((Mr @ v).lerp(MB.to_3x3() @ v, wb)).normalized()     # ground frame -> trunk frame
    dist_rest = orient(R[names[2]].to_3x3().col[1])
    Rf = Matrix.Rotation(rad(lp.flex), 3, hinge)
    dist_dir = (Rf @ dist_rest).normalized()
    J2 = P - dist_dir * L[2]
    K, J2 = two_bone(A, J2, L[0], L[1], pole)
    P = J2 + dist_dir * L[2]
    Wm[names[0]] = _frame(A, K - A, T3 @ R[names[0]].col[0].xyz)
    Wm[names[1]] = _frame(K, J2 - K, T3 @ R[names[1]].col[0].xyz)
    Wm[names[2]] = _frame(J2, dist_dir, orient(R[names[2]].to_3x3().col[0]))
    toe_rest = orient(R[names[3]].to_3x3().col[1])
    toe_dir = Matrix.Rotation(rad(lp.toe), 3, hinge) @ toe_rest
    Lt = B[names[3]][2]
    tz_min = min(0.012, rest_data(sp)[('toe_z',) + key] - 0.003)
    if P.z + toe_dir.z * Lt < tz_min:                    # toes stay on top of the ground
        toe_dir.z = (tz_min - P.z) / Lt
        toe_dir.normalize()
    Wm[names[3]] = _frame(P, toe_dir, orient(R[names[3]].to_3x3().col[0]))


# ----------------------------------------------------------------------------------------- interpolation
def track(keys, f, loop=None):
    """Catmull-Rom through (frame, value) keys; values are floats or sequences. loop = period for cyclic tracks."""
    ks = sorted(keys, key=lambda k: k[0])
    fr = [k[0] for k in ks]
    vals = [np.atleast_1d(np.asarray(k[1], float)) for k in ks]
    one = len(vals[0]) == 1
    if loop:
        f = f % loop
        fr = [fr[-2] - loop] + fr + [fr[1] + loop]
        vals = [vals[-2]] + vals + [vals[1]]
    else:
        if f <= fr[0]:
            return float(vals[0][0]) if one else vals[0]
        if f >= fr[-1]:
            return float(vals[-1][0]) if one else vals[-1]
        fr = [fr[0] - 1] + fr + [fr[-1] + 1]
        vals = [vals[0]] + vals + [vals[-1]]
    for i in range(1, len(fr) - 2):
        if fr[i] <= f <= fr[i + 1]:
            t = (f - fr[i]) / (fr[i + 1] - fr[i])
            p0, p1, p2, p3 = vals[i - 1], vals[i], vals[i + 1], vals[i + 2]
            m1 = (p2 - p0) / (fr[i + 1] - fr[i - 1]) * (fr[i + 1] - fr[i])
            m2 = (p3 - p1) / (fr[i + 2] - fr[i]) * (fr[i + 1] - fr[i])
            t2, t3 = t * t, t * t * t
            v = (2 * t3 - 3 * t2 + 1) * p1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * p2 + (t3 - t2) * m2
            return float(v[0]) if one else v
    return float(vals[-1][0]) if one else vals[-1]


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def K(keys, f, loop=None):
    return track(keys, f, loop)


# ----------------------------------------------------------------------------------------- gaits
def gait(sp, p, f, N, stride, duty, lift, phases, front_fold=95.0, hind_flex=35.0, scap=22.0):
    """Paw targets for a cyclic gait; the root travels `stride` per cycle along -Y. Returns the swing amount per leg."""
    fwd = Vector((0, -1, 0))
    p.root = fwd * (stride * f / N)
    exc = stride * duty
    swing = {}
    for key in LEGS:
        ph = (f / N + phases[key]) % 1.0
        F0 = neutral(sp, key)
        if ph < duty:
            u, z, sw = 0.5 - ph / duty, 0.0, 0.0
            q = ph / duty
            push = max(0.0, (q - 0.7) / 0.3)             # heel/pastern lifts at the end of stance
        else:
            q = (ph - duty) / (1 - duty)
            u = -0.5 + ease(q)
            z = lift * math.sin(math.pi * q) ** 0.8
            sw = math.sin(math.pi * q)
            push = 0.0
        tgt = p.root + F0 + fwd * exc * u
        tgt.z = F0.z + z
        lp = LegPose(target=tgt)
        if key[0] == 'F':
            lp.flex = -front_fold * sw ** 1.2 - 12 * push
            lp.scap = scap * u
            lp.toe = -18 * sw + 20 * push
        else:
            lp.flex = hind_flex * sw - 8 * push
            lp.toe = -12 * sw + 18 * push
        p.legs[key] = lp
        swing[key] = sw
    return swing


# ----------------------------------------------------------------------------------------- build
def build_clip(sp, clips, events, name, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[sp.rig]
    N, fn, loop = clips[name]()
    an = sp.action_name(name)
    act = bpy.data.actions.get(an)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(an)
    act.use_fake_user = True
    act["loop"] = loop
    act["frames"] = N
    for ev, t in events.get(name, []):
        act["event_" + ev] = t
    rig_ob.animation_data_create()
    rig_ob.animation_data.action = act
    R = beast_rig.rest(rig_ob)
    for pb in rig_ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
    for f in range(N + 1):
        beast_rig.apply_pose(rig_ob, pose_matrices(sp, fn(f)), frame=f, R=R)
    for fc in _fcurves(act):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    act.frame_range = (0, N)
    return act


def _fcurves(act):
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])) > 0:
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def use(sp, name, rig_ob=None):
    """Show a clip on the rig and set the scene range to it."""
    rig_ob = rig_ob or bpy.data.objects[sp.rig]
    act = bpy.data.actions[sp.action_name(name)]
    rig_ob.animation_data_create()
    rig_ob.animation_data.action = act
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 0, int(act["frames"])
    scn.frame_set(0)


def clear(sp, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[sp.rig]
    if rig_ob.animation_data:
        rig_ob.animation_data.action = None
    beast_rig.reset_pose(rig_ob)


def still(sp, p, rig_ob=None):
    rig_ob = rig_ob or bpy.data.objects[sp.rig]
    if rig_ob.animation_data:
        rig_ob.animation_data.action = None
    beast_rig.apply_pose(rig_ob, pose_matrices(sp, p), keys=False)
    bpy.context.view_layer.update()


def ground_report(sp, clips, mesh_name, step=16):
    """Lowest vertex of the skinned mesh per clip (sampled): nothing should go much under the ground."""
    ob = bpy.data.objects[mesh_name]
    scn = bpy.context.scene
    res = {}
    for name in clips:
        use(sp, name)
        N = int(bpy.data.actions[sp.action_name(name)]["frames"])
        lo = 1e9
        for f in range(0, N + 1, max(1, N // step)):
            scn.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            me = ob.evaluated_get(dg).to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            lo = min(lo, float(co.reshape(-1, 3)[:, 2].min()))
            ob.evaluated_get(dg).to_mesh_clear()
        res[name] = round(lo, 3)
    clear(sp)
    return res
