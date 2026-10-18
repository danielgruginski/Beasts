"""Hydra clips, keyed straight onto HydraRig; the machinery is beast_anim.py, the patterns dragon_anim's (Daniel:
a creature like an approved one starts from its finished parts).

The middle neck is beast_anim's own chain (Neck1..7, Head, Jaw). The side necks (Neck1L..7L, HeadL, JawL and the R
mirror) are posed by `_side_necks` through beast_anim's `extra` hook, from `p.side[nid]` = dict(neck=[[pitch, yaw,
roll] x 7], head=[...], jaw=deg): turns in each bone's own frame, + pitch raises, + yaw turns outward (the right
chain mirrors itself: the same numbers on both sides move them as mirror images). Every head keeps its own rhythm
-- three heads in step look like one animal with a stutter.

Clips (30 fps, the hydra faces -Y; Unity +Z):
  Idle       4.0 s loop   breathing, each neck weaving to its own beat, the left head yawning, heads looking about
  Walk       1.33 s loop  a sprawling lizard's walk: the spine and tail swing in an S, the necks bob and counter-
                          sway so the heads stay on line; root motion 1.0 m/s
  Run        0.67 s loop  a lizard's trot, thrashing side to side, necks stretched forward; root motion 3.9 m/s
  Bite       1.4 s        the middle head strikes low ahead (event 'Bite' at 0.6 s), the side heads hiss aside
  TripleBite 2.4 s        left, middle, right strike in turn (events 'Bite' 0.6 s, 'Bite2' 1.2 s, 'Bite3' 1.8 s)
  TailSweep  1.8 s        the dragon's tail whip (event 'Bite' at 0.8 s), the heads watching it go
"""
import math
from mathutils import Vector, Matrix
import bpy
import beast_anim as BA
import hydra_body as HB
from beast_anim import LegPose, K, ease, WALK, TROT, GALLOP

FPS = 30
RIG = HB.RIG
SIDE = ("L", "R")


def _side_necks(sp, p, Wm, rel):
    """The side necks, heads and jaws, chained from the chest like the middle one."""
    for nid in SIDE:
        d = p.side[nid]
        par = "Chest"
        for i in range(HB.NECK_N):
            n = f"Neck{i + 1}{nid}"
            Wm[n] = Wm[par] @ rel(n, par) @ BA._rot(*d["neck"][i])
            par = n
        Wm[f"Head{nid}"] = Wm[par] @ rel(f"Head{nid}", par) @ BA._rot(*d["head"])
        Wm[f"Jaw{nid}"] = Wm[f"Head{nid}"] @ rel(f"Jaw{nid}", f"Head{nid}") @ BA._rot(-d["jaw"])


SPEC = BA.Species(HB.rest_bones, (0.0, 0.2, 1.5), "Hydra", RIG, neck_n=HB.NECK_N, tail_n=HB.TAIL_N, tongue=False,
                  ears=False, tail_floor=[0.10] * HB.TAIL_N, extra=_side_necks)
LEGS = BA.LEGS
EVENTS = {"Bite": [("Bite", 0.60)], "TripleBite": [("Bite", 0.60), ("Bite2", 1.20), ("Bite3", 1.80)],
          "TailSweep": [("Bite", 0.80)]}
MOVING = {"Walk", "Run"}


def HydraPose():
    p = BA.Pose(SPEC)
    p.side = {nid: dict(neck=[[0.0, 0.0, 0.0] for _ in range(HB.NECK_N)], head=[0.0, 0.0, 0.0], jaw=0.0)
              for nid in SIDE}
    return p


def neutral(key):
    return BA.neutral(SPEC, key)


def gait(p, f, N, stride, duty, lift, phases, **kw):
    return BA.gait(SPEC, p, f, N, stride, duty, lift, phases, **kw)


def chain(p, nid):
    """The [pitch, yaw, roll] list of a neck: '' the middle one, 'L' / 'R' the sides."""
    return p.neck if nid == "" else p.side[nid]["neck"]


def head(p, nid):
    return p.head if nid == "" else p.side[nid]["head"]


def set_jaw(p, nid, deg):
    if nid == "":
        p.jaw = deg
    else:
        p.side[nid]["jaw"] = deg


def wave(p, nid, pitch, yaw, phase=0.0, lag=0.35, spread=(1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7)):
    """Spread a neck turn over its seven bones (more at the base), each a little behind the one before (`lag`
    radians); pitch / yaw are callables of the phase, or numbers (dragon_anim._neck_wave)."""
    c = chain(p, nid)
    tot = sum(spread)
    for i in range(HB.NECK_N):
        ph = phase - lag * i
        c[i][0] += (pitch(ph) if callable(pitch) else pitch) * spread[i] / tot
        c[i][1] += (yaw(ph) if callable(yaw) else yaw) * spread[i] / tot


def tail_wave(p, amp, phase, lag=0.45, grow=0.12, lift=0.0, curl=0.0):
    n = SPEC.tail_n
    for i in range(n):
        p.tail[i][1] += amp * (1 + grow * i) * math.sin(phase - lag * i)
        p.tail[i][0] += lift * max(0.0, 1 - i / 5.0) / 3.0
        p.tail[i][1] += curl * max(0.0, (i - (n - 5)) / 5.0)


# ----------------------------------------------------------------------------------------- idle and locomotion
def _clip_idle():
    N = 120

    def fn(f):
        p = HydraPose()
        a = 2 * math.pi * f / N
        b = 2 * math.pi * f / 60
        p.body = Vector((0.02 * math.sin(a), 0, 0.010 * math.sin(b)))
        p.roll = 0.8 * math.sin(a)
        p.spine[2][0] = 1.0 * math.sin(b)
        # the middle head: slow sway, a look to the right and back
        look = K([(0, 0), (40, 0), (52, 1), (74, 1), (86, 0), (120, 0)], f)
        wave(p, "", lambda ph: 2.5 * math.sin(ph + 0.3), lambda ph: 5.0 * math.sin(ph + 1.0) - 14 * look, phase=a)
        p.head = [2 * math.sin(a + 1.4), -8 * look + 2 * math.sin(a + 1.6), -4 * look]
        # the left head: twice as fast, restless; a yawn
        yawn = K([(0, 0), (66, 0), (76, 1), (88, 1), (98, 0), (120, 0)], f)
        wave(p, "L", lambda ph: 3.0 * math.sin(ph + 2.0) + 8 * yawn, lambda ph: 7.0 * math.sin(ph + 0.8),
             phase=2 * a)
        p.side["L"]["head"] = [3 * math.sin(2 * a + 1.2) + 14 * yawn, 5 * math.sin(2 * a), 6 * yawn]
        p.side["L"]["jaw"] = 34 * yawn
        # the right head: low and watchful, a slow sweep, a snap at nothing
        snap = K([(0, 0), (20, 0), (24, 1), (27, 0.1), (30, 0), (120, 0)], f)
        wave(p, "R", lambda ph: -6.0 + 3.0 * math.sin(ph + 1.4), lambda ph: 9.0 * math.sin(ph + 2.6), phase=a)
        p.side["R"]["head"] = [6 + 2 * math.sin(a + 0.5) - 6 * snap, -6 * math.sin(a + 2.9), 0]
        p.side["R"]["jaw"] = 22 * snap
        tail_wave(p, 1.0, a, curl=8 * math.sin(a - 1.0))
        return p
    return N, fn, True


def _clip_walk():
    """A sprawling lizard's walk: lateral sequence, the spine bending side to side with each step and the tail
    swinging after it; each neck bobs to its own phase and counter-sways so the heads stay on line."""
    N = 40

    def fn(f):
        p = HydraPose()
        gait(p, f, N, 1.3, 0.65, 0.16, WALK, front_fold=50, hind_flex=30, scap=10)
        a = 2 * math.pi * f / N
        p.body = Vector((0.05 * math.sin(a), 0, -0.02 - 0.02 * math.cos(2 * a)))
        p.roll = 3.0 * math.sin(a)
        p.yaw = 3.0 * math.sin(a + 0.8)
        p.hips = [0, 4.0 * math.sin(a + 0.2), 0]
        for i in range(3):
            p.spine[i][1] = -5.0 * math.sin(a + 0.8 + 0.4 * i)
        for nid, off in (("", 0.0), ("L", 2.1), ("R", 4.2)):
            wave(p, nid, lambda ph, o=off: 2.0 * math.sin(2 * ph + 1.0 + o),
                 lambda ph: 7.0 * math.sin(ph + 2.6), phase=a, lag=0.25)
            h = head(p, nid)
            h[0] += -2.0 * math.sin(2 * a + 1.0 + off)
            h[1] += -2.5 * math.sin(a + 2.0)
        tail_wave(p, 2.2, a + 1.4, lag=0.5)
        return p
    return N, fn, True


def _clip_run():
    """A lizard's run: a trot (diagonal pairs), the spine and tail thrashing side to side, the necks stretched
    forward and low with the heads level, each bobbing a little after the last; root motion ~3.9 m/s."""
    N = 20

    def fn(f):
        p = HydraPose()
        gait(p, f, N, 2.6, 0.45, 0.22, TROT, front_fold=60, hind_flex=34, scap=16)
        a = 2 * math.pi * f / N
        p.body = Vector((0.06 * math.sin(a), 0, -0.04 + 0.04 * math.sin(2 * a - 1.0)))
        p.roll = 4.0 * math.sin(a)
        p.yaw = 5.0 * math.sin(a + 0.6)
        p.hips = [0, 7.0 * math.sin(a + 0.2), 0]
        for i in range(3):
            p.spine[i][1] = -9.0 * math.sin(a + 0.7 + 0.45 * i)
        for nid, off in (("", 0.0), ("L", 0.8), ("R", 1.6)):
            wave(p, nid, lambda ph, o=off: -16.0 + 3.0 * math.sin(2 * ph + o), lambda ph: 9.0 * math.sin(ph + 2.4),
                 phase=a, lag=0.3)
            h = head(p, nid)
            h[0] += 14.0 - 3.0 * math.sin(2 * a + off)
            h[1] += -3.0 * math.sin(a + 2.0)
            set_jaw(p, nid, 6 + 4 * math.sin(2 * a + off))           # panting
        tail_wave(p, 3.4, a + 1.3, lag=0.55)
        return p
    return N, fn, True


# ----------------------------------------------------------------------------------------- attacks
BASE = (1.7, 1.5, 1.2, 1.0, 0.8, 0.5, 0.3)                 # a strike turns the neck mostly at its base


def strike(f, t0, t_hit, t_end, depth=-46.0, head_up=44.0, back=12.0):
    """A neck's strike as (neck pitch, head pitch, jaw): drawn back and up, then down and out with the jaws wide,
    snapping shut at t_hit, held a moment, drawn back."""
    pitch = K([(t0, 0), (t_hit - 7, back), (t_hit - 2, 0.75 * depth), (t_hit + 1, depth), (t_hit + 8, 0.9 * depth),
               (t_end, 0)], f)
    hp = K([(t0, 0), (t_hit - 7, -8), (t_hit - 2, 0.7 * head_up), (t_hit + 1, head_up), (t_hit + 8, 0.9 * head_up),
            (t_end, 0)], f)
    jaw = K([(t0, 0), (t_hit - 8, 12), (t_hit - 2, 40), (t_hit - 0.5, 42), (t_hit + 0.5, 4), (t_hit + 8, 6),
             (t_end, 0)], f)
    return pitch, hp, jaw


def _hiss(p, nid, k, f):
    """A side head drawn back and out, jaws open, while another strikes."""
    wave(p, nid, 10 * k, 12 * k)
    h = head(p, nid)
    h[0] += -6 * k
    set_jaw(p, nid, 26 * k + 3 * math.sin(2 * math.pi * f / 5) * k)


def _clip_bite():
    """The middle head draws back and strikes low ahead, jaws level and wide, snapping shut (event 'Bite' at
    0.6 s); the side heads pull aside and hiss; the body lunges with it."""
    N = 42

    def fn(f):
        p = HydraPose()
        lunge = K([(0, 0), (11, 0.15), (18, -0.40), (28, -0.30), (42, 0)], f)
        p.body = Vector((0, lunge, K([(0, 0), (11, 0.02), (18, -0.08), (42, 0)], f)))
        p.pitch = K([(0, 0), (11, 2), (18, -4), (42, 0)], f)
        pitch, hp, jaw = strike(f, 0, 18, 40)
        wave(p, "", pitch, 0.0, spread=BASE)
        p.head[0] += hp
        p.jaw = jaw
        side = K([(0, 0), (8, 1), (30, 1), (40, 0), (42, 0)], f)
        for nid in SIDE:
            _hiss(p, nid, side, f)
        tail_wave(p, 1.2, 2 * math.pi * f / N, lift=K([(0, 0), (11, -2), (18, 4), (42, 0)], f))
        F0 = neutral(('F', 1))
        lp = LegPose(target=Vector(K([(0, tuple(F0)), (12, tuple(F0)), (16, tuple(F0 + Vector((0, -0.2, 0.2)))),
                                      (19, tuple(F0 + Vector((0, -0.35, 0)))), (30, tuple(F0 + Vector((0, -0.35, 0)))),
                                      (36, tuple(F0 + Vector((0, -0.15, 0.15)))), (41, tuple(F0))], f)))
        lp.flex = K([(0, 0), (13, 0), (16, -40), (19, 0), (31, 0), (35, -30), (41, 0)], f)
        p.legs[('F', 1)] = lp
        return p
    return N, fn, False


def _clip_triple():
    """All three heads strike in turn -- left, middle, right -- each snapping shut (events 'Bite', 'Bite2',
    'Bite3' at 0.6, 1.2 and 1.8 s), the body swaying toward each strike, the others drawing back between."""
    N = 72

    def fn(f):
        p = HydraPose()
        order = (("L", 18), ("", 36), ("R", 54))
        for nid, t in order:
            pitch, hp, jaw = strike(f, t - 14, t, t + 16, depth=-40.0, head_up=38.0, back=10.0)
            wave(p, nid, pitch, 0.0, spread=BASE)
            head(p, nid)[0] += hp
            set_jaw(p, nid, jaw)
        p.yaw = K([(0, 0), (16, 6), (36, 0), (54, -6), (72, 0)], f)
        p.roll = K([(0, 0), (16, 2), (36, 0), (54, -2), (72, 0)], f)
        p.body = Vector((K([(0, 0), (18, 0.08), (36, 0), (54, -0.08), (72, 0)], f),
                         K([(0, 0), (18, -0.15), (36, -0.25), (54, -0.15), (72, 0)], f), 0))
        tail_wave(p, 1.4, 2 * math.pi * f / 36)
        return p
    return N, fn, False


def _clip_tail():
    """Tail sweep (dragon_anim's): winds the tail out to its left, whips it round to the right in a wide, low arc
    (event 'Bite' at 0.8 s), the trunk turning against it, the heads watching it go."""
    N = 54

    def fn(f):
        p = HydraPose()
        sweep = lambda t: K([(0, 0), (12, 1.0), (18, 0.8), (26, -2.0), (34, -1.6), (46, -0.2), (54, 0)], t)
        for i in range(SPEC.tail_n):
            lag = 0.6 * i
            p.tail[i][1] += 4.6 * sweep(f - lag)
            p.tail[i][0] += K([(0, 0), (12, 1.0), (24, -0.6), (40, -0.4), (54, 0)], f - lag) * (1 if i < 5 else 0.3)
        body = K([(0, 0), (12, -1.0), (22, 0.8), (30, 1.0), (44, 0.2), (54, 0)], f)
        p.yaw = 10 * body
        p.hips = [0, -8 * body, 0]
        for i in range(3):
            p.spine[i][1] = -4 * body
        p.roll = 4 * body
        p.body = Vector((0.12 * body, 0, -0.04 * abs(body)))
        for nid, k in (("", 1.0), ("L", 1.2), ("R", 0.8)):
            wave(p, nid, -5 * abs(body), 30 * body * k * (1 if nid != "R" else -1))
            head(p, nid)[1] += 10 * body * (1 if nid != "R" else -1)
            set_jaw(p, nid, K([(0, 0), (12, 6), (24, 20), (34, 12), (54, 0)], f))
        for s_ in (1, -1):
            H0 = neutral(('H', s_))
            hop = K([(0, 0), (16, 0), (20, 1), (24, 0), (54, 0)], f) if s_ > 0 else \
                K([(0, 0), (34, 0), (38, 1), (42, 0), (54, 0)], f)
            lp = LegPose(target=H0 + Vector((0.10 * body, 0, 0.15 * hop)))
            lp.flex = 20 * hop
            p.legs[('H', s_)] = lp
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Walk": _clip_walk, "Run": _clip_run, "Bite": _clip_bite, "TripleBite": _clip_triple,
         "TailSweep": _clip_tail}


# ----------------------------------------------------------------------------------------- build
def pose_matrices(p):
    return BA.pose_matrices(SPEC, p)


def build_clip(name, rig_ob=None):
    return BA.build_clip(SPEC, CLIPS, EVENTS, name, rig_ob)


def tail_floor(meshes=("HydraBody", "HydraFins"), margin=0.03):
    """Per tail bone: how high its end must stay so the tail's underside -- the keel fin included (it dug 12 cm
    into the ground in Bite) -- stays on the ground (dragon_anim's)."""
    import numpy as np
    B = BA.rest_data(SPEC)['B']
    co = np.vstack([np.array([v.co[:] for v in bpy.data.objects[m].data.vertices]) for m in meshes])
    out = []
    for i in range(SPEC.tail_n):
        h, fr, L, par, d = B[f"Tail{i + 1}"]
        end = np.array(h + fr.col[1] * L)
        near = (np.abs(co[:, 1] - end[1]) < 0.15) & (np.abs(co[:, 0]) < 0.8)
        depth = end[2] - co[near, 2].min() if near.any() else 0.1
        out.append(float(depth + margin))
    return out


def build_clips(names=None):
    SPEC.rest.clear()
    SPEC.tail_floor = tail_floor()
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig_ob=None):
    BA.use(SPEC, name, rig_ob)


def clear(rig_ob=None):
    BA.clear(SPEC, rig_ob)


def still(p, rig_ob=None):
    BA.still(SPEC, p, rig_ob)


def report(names=None, step=16):
    """Lowest point per clip (sampled) over the ground, counting the root motion's height."""
    import numpy as np
    rig = bpy.data.objects[RIG]
    scn = bpy.context.scene
    res = {}
    for name in (names or CLIPS):
        use(name)
        N = int(bpy.data.actions[SPEC.action_name(name)]["frames"])
        lo = 1e9
        for f in range(0, N + 1, max(1, N // step)):
            scn.frame_set(f)
            up = rig.pose.bones["Motion"].head.z
            dg = bpy.context.evaluated_depsgraph_get()
            for mesh in ("HydraBody", "HydraFins"):
                ob = bpy.data.objects[mesh]
                me = ob.evaluated_get(dg).to_mesh()
                co = np.empty(len(me.vertices) * 3)
                me.vertices.foreach_get('co', co)
                lo = min(lo, float(co.reshape(-1, 3)[:, 2].min()) + up)
                ob.evaluated_get(dg).to_mesh_clear()
        res[name] = round(lo, 3)
    clear()
    return res
