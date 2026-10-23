"""Leech clips (2026-10-23), keyed straight onto LeechRig with beast_rig.apply_pose (the swell bones' scale too).

A pose is a curve: the body's centre line from the rear sucker to the front one, in world space, built from flat
stretches lying on the ground and cubic Beziers fitted to a length (bezier_fit: the handles grow until the curve is
as long as the body there). The bones sit along it at their rest arc positions, scaled to the curve's length (a leech
stretches and shrinks), framed by parallel transport from the rear (so loops and coils don't flip), with an optional
roll. Swell<k> scales a segment (pulses). The skeleton plays in place; Motion travels (root motion), and the world
curve is turned into the skeleton's frame once (the centipede's lesson: no root on top of a world-space chain).

Clips (30 fps, facing -Y; Unity +Z):
  Idle   3.0 s loop  lying stretched out, the front end raised and searching from side to side, two pulses
                     running down the body
  Crawl  2.0 s loop  looping like an inchworm: the rear sucker lets go and is drawn up behind the front one (the body
                     arches 0.4 m high), then the front lets go and reaches forward; root motion 0.33 m/s
  Lunge  2.2 s       rears its front up and back, strikes 0.3 m past its head and latches on 0.4 m up (event 'Bite'
                     at 0.6 s), drinks (three swellings running back, events 'Drain' 1.1 s, 'Drain2' 1.5 s), lets go
  Hit    0.5 s       a writhe, the front recoiling
  Death  2.0 s       writhes, curls into a C on its side and shrinks (event 'Dead' at 1.6 s); holds
"""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import beast_rig
import beast_anim as BA
from beast_anim import K, ease
import leech_body as LB

FPS = 30
RIG = LB.RIG
EVENTS = {"Lunge": [("Bite", 0.6), ("Drain", 1.1), ("Drain2", 1.5)], "Death": [("Dead", 1.6)]}
MOVING = {"Crawl"}
FWD, UPV = np.array((0.0, -1.0, 0.0)), np.array((0.0, 0.0, 1.0))
A0 = LB.centre(0.0)                    # the rear end lying flat
F0 = LB.centre(LB.L0)                  # the front end
SWELLS = [f"Swell{k + 1}" for k in range(LB.N_BODY)]


# ----------------------------------------------------------------------------------------- curves
def _unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-9)


def arc(P):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def line(p, d, length, n=8):
    p, d = np.asarray(p, float), _unit(d)
    return p + np.outer(np.linspace(0, length, n), d)


def bezier(P0, P1, P2, P3, n=60):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * P3)


def bezier_fit(P0, d0, P3, d3, length, n=60):
    """A cubic from P0 leaving along d0 to P3 arriving along d3 whose length is `length` (the handles, equal, grow
    until it is; if even the shortest is too long, the shortest)."""
    P0, P3 = np.asarray(P0, float), np.asarray(P3, float)
    d0, d3 = _unit(d0), _unit(d3)
    chord = np.linalg.norm(P3 - P0)
    lo, hi = 0.02 * max(chord, 0.05), 3.0 * max(length, chord)
    best = None
    for _ in range(40):
        h = 0.5 * (lo + hi)
        B = bezier(P0, P0 + d0 * h, P3 - d3 * h, P3, n)
        L = arc(B)[-1]
        best = B
        if L > length:
            hi = h
        else:
            lo = h
    return best


def arch_fit(p0, p3, length, n=60):
    """A bell-shaped arch from p0 to p3 (it leaves and lands flat), as high as it must be to be `length` long."""
    p0, p3 = np.asarray(p0, float), np.asarray(p3, float)
    s = np.linspace(0, 1, n)[:, None]
    base = p0 + (p3 - p0) * s
    bell = np.sin(np.pi * s) ** 1.4                  # a rounder top than sin^2, still leaving the ground flat
    lo, hi = 0.0, length
    B = base
    for _ in range(40):
        h = 0.5 * (lo + hi)
        B = base + UPV * h * bell
        if arc(B)[-1] > length:
            hi = h
        else:
            lo = h
    return B


def join(*parts):
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[1:] if np.linalg.norm(p[0] - out[-1][-1]) < 1e-6 else p)
    return np.vstack(out)


def body_curve(A, a_dir, e0, F, f_dir, e1, length, alpha=None):
    """Rear flat stretch (e0 from A along a_dir), a fitted middle, front flat stretch (e1 ending at F along f_dir).
    alpha (not None): the middle is a bell-shaped arch (the crawl's loop); None: a Bezier along the directions."""
    A, F = np.asarray(A, float), np.asarray(F, float)
    p0 = A + _unit(a_dir) * e0
    p3 = F - _unit(f_dir) * e1
    d0, d3 = _unit(a_dir), _unit(f_dir)
    if alpha is not None:
        mid = arch_fit(p0, p3, max(length - e0 - e1, 0.05))
    else:
        mid = bezier_fit(p0, d0, p3, d3, max(length - e0 - e1, 0.05))
    return join(line(A, a_dir, e0), mid, line(p3, f_dir, e1))


def rest_curve():
    return line(A0, FWD, LB.L0, 40)


# ----------------------------------------------------------------------------------------- pose
class Pose:
    def __init__(self):
        self.root = Vector()
        self.curve = rest_curve()
        self.roll = 0.0                    # deg about the centre line (+ tips the back toward +x)
        self.swell = [1.0] * LB.N_BODY


_REST = {}


def rest():
    if not _REST:
        B = LB.rest_bones()
        _REST['B'] = B
        _REST['R'] = {n: beast_rig.frame_matrix(h, fr) for n, (h, fr, L, par, d) in B.items()}
    return _REST


def _frames(P):
    """Parallel-transported up vectors along the polyline (from world up at the rear end)."""
    T = np.gradient(P, axis=0)
    T = T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    N = np.zeros_like(P)
    n = UPV - T[0] * (UPV @ T[0])
    N[0] = _unit(n if np.linalg.norm(n) > 1e-6 else np.array((1.0, 0, 0)))
    for i in range(1, len(P)):
        q = Vector(T[i - 1]).rotation_difference(Vector(T[i]))
        v = np.array(q @ Vector(N[i - 1]))
        v = v - T[i] * (v @ T[i])
        N[i] = _unit(v)
    return T, N


def _at(P, S, N, s):
    i = int(np.clip(np.searchsorted(S, s) - 1, 0, len(S) - 2))
    t = (s - S[i]) / max(S[i + 1] - S[i], 1e-9)
    return P[i] * (1 - t) + P[i + 1] * t, _unit(N[i] * (1 - t) + N[i + 1] * t)


def pose_matrices(p):
    D = rest()
    R, B = D['R'], D['B']
    rel = lambda c, par: R[par].inverted() @ R[c]
    M = Matrix.Translation(p.root)
    P = np.asarray(p.curve, float)
    S = arc(P)
    k = S[-1] / LB.L0
    T, N = _frames(P)
    W = {"Root": M @ R["Root"]}
    for name, u0, u1 in LB.bone_spans():
        a, up = _at(P, S, N, u0 * k)
        b, _ = _at(P, S, N, u1 * k)
        Y = _unit(b - a)
        Z = up - Y * (up @ Y)
        Z = _unit(Z)
        if p.roll:
            q = Quaternion(Vector(Y), math.radians(p.roll))
            Z = np.array(q @ Vector(Z))
        X = np.cross(Y, Z)
        m = Matrix((X, Y, Z)).transposed().to_4x4()
        m.translation = Vector(a)
        W[name] = m
    for i, sb in enumerate(SWELLS):
        W[sb] = W[f"Body{i + 1}"] @ rel(sb, f"Body{i + 1}") @ Matrix.Scale(p.swell[i], 4)
    Minv = M.inverted()
    out = {kk: Minv @ v for kk, v in W.items()}
    out["Motion"] = M @ R["Motion"]
    return out


def pulse(p, phase, amp=0.10, width=0.14, rear_to=True):
    """A swelling running along the body: phase 0..1 travels front to rear (rear_to) or rear to front."""
    for i in range(LB.N_BODY):
        x = (LB.N_BODY - 1 - i) / (LB.N_BODY - 1) if rear_to else i / (LB.N_BODY - 1)
        d = (x - phase) / width
        p.swell[i] *= 1.0 + amp * math.exp(-d * d)


# ----------------------------------------------------------------------------------------- clips
def _clip_idle():
    N = 90

    def fn(f):
        p = Pose()
        a = 2 * math.pi * f / N
        lf = 0.62                                                   # the raised front
        yaw = math.radians(24 * math.sin(a))
        lift = 0.15 + 0.06 * math.sin(2 * a + 0.6)
        base = F0 - FWD * lf
        tip_dir = _unit(np.array((-math.sin(yaw), -math.cos(yaw), -0.35)))
        tip = base + np.array((-math.sin(yaw) * lf * 0.85, -math.cos(yaw) * lf * 0.85, lift))
        length = LB.L0 * (1.0 + 0.015 * math.sin(2 * a))
        p.curve = body_curve(A0, FWD, length - lf, tip, tip_dir, 0.05, length)
        for ph0 in (0.0, 0.5):
            pulse(p, ((f / N) * 2 + ph0) % 1.0 * 1.3 - 0.15, amp=0.09)
        return p
    return N, fn, True


CRAWL_N, CRAWL_D = 60, 0.65


def _crawl_pose(f):
    N, D = CRAWL_N, CRAWL_D
    p = Pose()
    p.root = Vector((0.0, -D * f / N, 0.0))
    if f <= 24:                                         # the rear is drawn up behind the front
        t = ease(f / 24)
        A = A0 + FWD * D * t + UPV * 0.05 * math.sin(math.pi * f / 24)
        F = F0.copy()
        sig = 1.0 - 0.08 * math.sin(math.pi * t)
        sw = 1.0 + 0.07 * math.sin(math.pi * t)
    elif f <= 30:
        A, F, sig, sw = A0 + FWD * D, F0.copy(), 1.0, 1.0
    elif f <= 54:                                       # the front lets go and reaches forward
        t = ease((f - 30) / 24)
        A = A0 + FWD * D
        F = F0 + FWD * D * t + UPV * 0.10 * math.sin(math.pi * (f - 30) / 24)
        sig = 1.0 + 0.03 * math.sin(math.pi * t)
        sw = 1.0 - 0.04 * math.sin(math.pi * t)
    else:
        A, F, sig, sw = A0 + FWD * D, F0 + FWD * D, 1.0, 1.0
    length = LB.L0 * sig
    e0, e1 = 0.14, 0.12
    p.curve = body_curve(A, FWD, e0, F, FWD, e1, length, alpha=1.0)
    p.swell = [sw] * LB.N_BODY
    return p


def _clip_crawl():
    return CRAWL_N, _crawl_pose, True


LUNGE_HIT = 18


def _clip_lunge():
    N = 66
    tip_keys = [(0, F0), (12, np.array((0.0, -0.58, 0.50))), (LUNGE_HIT, np.array((0.0, -1.18, 0.42))),
                (48, np.array((0.0, -1.18, 0.42))), (57, np.array((0.0, -1.02, 0.22))), (66, F0)]
    dir_keys = [(0, FWD), (12, np.array((0.0, -0.55, -0.85))), (LUNGE_HIT, np.array((0.0, -1.0, -0.08))),
                (48, np.array((0.0, -1.0, -0.08))), (57, np.array((0.0, -0.8, -0.5))), (66, FWD)]
    sig_keys = [(0, 1.0), (12, 0.95), (LUNGE_HIT, 1.22), (48, 1.24), (57, 1.08), (66, 1.0)]

    def fn(f):
        p = Pose()
        tip = np.array(K(tip_keys, f))
        d = _unit(np.array(K(dir_keys, f)))
        length = LB.L0 * K(sig_keys, f)
        if LUNGE_HIT < f < 50:                              # the body pumps while it drinks
            length *= 1.0 + 0.035 * math.sin(2 * math.pi * (f - LUNGE_HIT) / (32 / 3))
        e0 = 0.35
        p.curve = body_curve(A0, FWD, e0, tip, d, 0.06, length)
        if LUNGE_HIT < f < 50:                              # three swellings run back from the mouth: it drinks
            ph = (f - LUNGE_HIT) / 32 * 3
            pulse(p, (ph % 1.0) * 1.2 - 0.1, amp=0.14, width=0.12)
        if f < 14:
            p.swell = [s * (1 - 0.05 * math.sin(math.pi * f / 14)) for s in p.swell]
        return p
    return N, fn, False


def _wavy(amp, phase, lift=0.0, length=LB.L0, waves=1.3):
    """The rest line with a sideways wave (amp m) and the front lifted."""
    u = np.linspace(0, length, 60)
    x = amp * np.sin(2 * math.pi * waves * u / length + phase) * np.clip(u / 0.3, 0, 1)
    z = LB.Z0 + lift * np.clip((u - length * 0.65) / (length * 0.35), 0, 1) ** 2
    y = LB.y_of(0.0) - u
    P = np.stack([x, y, z], 1)
    # keep the true length (the wave adds arc): squeeze along y
    for _ in range(3):
        L = arc(P)[-1]
        P[:, 1] = LB.y_of(0.0) - u * (length / L)
    return P


def _clip_hit():
    N = 15

    def fn(f):
        p = Pose()
        k = K([(0, 0), (3, 1), (8, 0.4), (12, -0.15), (15, 0)], f)
        p.curve = _wavy(0.10 * k, math.pi * 0.3 + 0.8 * f / N, lift=0.18 * max(k, 0), length=LB.L0 * (1 - 0.06 * max(k, 0)))
        p.swell = [1.0 - 0.06 * max(k, 0)] * LB.N_BODY
        return p
    return N, fn, False


def _clip_death():
    N = 60

    def fn(f):
        p = Pose()
        writhe = K([(0, 0), (6, 1), (20, 1), (30, 0.2), (40, 0), (60, 0)], f)
        curl = ease((f - 18) / 22)
        shrink = K([(0, 1.0), (20, 1.0), (44, 0.88), (60, 0.88)], f)
        length = LB.L0 * K([(0, 1.0), (24, 0.97), (44, 0.90), (60, 0.90)], f)
        wav = _wavy(0.14 * writhe, 7.0 * f / N * math.pi, lift=0.10 * writhe, length=length)
        # the C: an arc of 250 degrees round a point beside the body's middle, lying on the ground
        ang = math.radians(250) * curl
        if curl > 1e-3:
            r = length / ang
            u = np.linspace(0, length, 60)
            th = u / r - ang / 2
            C = np.stack([r * (1 - np.cos(th)) - r * (1 - math.cos(ang / 2)), -r * np.sin(th),
                          np.full_like(u, 0.0)], 1)
            C[:, 1] -= C[:, 1].mean()
            s_r = math.sin(math.radians(78 * curl))         # on its side the centre line sits higher
            C[:, 2] = LB.Z0 * (1 - s_r) + 0.125 * s_r
            P = wav * (1 - curl) + C * curl
        else:
            P = wav
        r = math.radians(78 * curl)                     # rolled onto its side: lift the centre line clear
        hw = np.array([LB.half_width(v) for v in np.linspace(0, LB.L0, len(P))])
        need = LB.Z0 - LB.BOTTOM * hw + hw * math.sin(r) + LB.BOTTOM * hw * math.cos(r) + 0.004
        P = P.copy()
        P[:, 2] = np.maximum(P[:, 2], need * shrink + (1 - shrink) * 0.02)
        p.curve = P
        p.roll = 78 * curl
        p.swell = [shrink] * LB.N_BODY
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Crawl": _clip_crawl, "Lunge": _clip_lunge, "Hit": _clip_hit, "Death": _clip_death}
SHEET_FRAMES = {"Idle": (0, 22, 45, 68), "Crawl": (0, 12, 24, 36, 48), "Lunge": (0, 12, 18, 34, 57, 66),
                "Hit": (0, 3, 8, 12), "Death": (0, 10, 24, 36, 60)}


# ----------------------------------------------------------------------------------------- build
def action_name(clip):
    return f"{LB.NAME}_{clip}"


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
        pb.scale = (1, 1, 1)
    for f in range(N + 1):
        beast_rig.apply_pose(rig_ob, pose_matrices(fn(f)), frame=f, R=R, scale_bones=SWELLS)
    for fc in BA._fcurves(act):
        for kf in fc.keyframe_points:
            kf.interpolation = 'LINEAR'
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
    for pb in rig_ob.pose.bones:
        pb.scale = (1, 1, 1)
