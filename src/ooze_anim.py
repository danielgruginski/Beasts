"""Clips for the dungeon ooze (30 fps). Each frame is an OozePose; `pose_world` turns it into armature-space bone
matrices (parents first, every child carried by its parent's motion) and `build_clip` keys location, rotation and
scale per bone. The skeleton plays in place; Motion carries the travel (Crawl).

A pose holds:
  dome        the Dome's squash/stretch (scale along world X, Y, Z about its head on the floor) and lean (deg, +
              forward, + to its left). Whatever sits in the domed part of the mass (pod bases, contents) follows it
              by the same height weight the skin uses (ooze_rig.DOME_Z).
  loc / rot   world-space offsets and rotations (about the bone's head) per bone
  bend / ext  local pitch / yaw (deg; pods: + pitch lifts, the Probe: + curls forward) and stretch along the bone (m)
  scl         local scale (leaf bones only: Dome, the pod tips (uniform), Nucleus, Vac*)
  curve       pod -> (control point, tip, weight): the pod's chain laid along a quadratic curve from its base,
              blended with the bent chain by the weight (reach for a point, wrap round a victim, flop down dead)

Clips: Idle, Crawl (root motion), Lash (the Probe slams down in front), Grab (Reach shoots out and pulls back),
Engulf (Reach and Lead close round a victim, the dome rolls over it: Socket_Mouth carries it in to Socket_Gut), Spit
(the Probe aims, the dome pumps: a glob from Socket_Spit), Hit, Death (collapses to a puddle, vacuoles pop, the
remains sink), Puddle (lying flat, alive: an ambush), Rise (from the puddle).
"""
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion

from beast_anim import track as K, _fcurves
from beast_common import smoothstep
import ooze_body as OB
import ooze_rig as OR

RIG = OR.RIG
FPS = 30
PODS = OR.PODS
FLOOR_PODS = ("Lead", "Back", "Bud")
RAISED = ("Reach", "Side", "Probe")
PIECES = ("Nucleus", "Skull", "Femur", "Shin", "Helm", "Sword", "Coins")
VACS = tuple(f"Vac{i + 1}" for i in range(7))
MOVING = {"Crawl"}
CRAWL_LOOP = 1.2                      # m per Crawl loop (2 s): 0.6 m/s
EVENTS = {"Lash": [("Hit", 20 / FPS)], "Grab": [("Hit", 18 / FPS)],
          "Engulf": [("Grab", 22 / FPS), ("Engulf", 46 / FPS)], "Spit": [("Spit", 21 / FPS)],
          "Death": [("Dead", 56 / FPS)], "Rise": [("Risen", 30 / FPS)]}
SHEET_FRAMES = {"Idle": (0, 22, 45, 67), "Crawl": (0, 15, 30, 45), "Lash": (0, 13, 20, 26, 40),
                "Grab": (0, 10, 18, 28, 44), "Engulf": (0, 14, 22, 34, 46, 62, 80), "Spit": (0, 14, 21, 30, 44),
                "Hit": (0, 3, 7, 12, 24), "Death": (0, 12, 24, 36, 56, 70), "Puddle": (0, 45),
                "Rise": (0, 10, 20, 30, 40, 50)}


def rad(d):
    return math.radians(d)


def action_name(clip):
    return "Ooze_" + clip


def dome_w(z):
    return float(smoothstep(OR.DOME_Z[0], OR.DOME_Z[1], z))


class OozePose:
    def __init__(self):
        self.root = Vector()
        self.dome_s = Vector((1, 1, 1))        # world X, Y, Z
        self.dome_lean = [0.0, 0.0]            # deg: forward (about X), to its left (about -Y)
        self.loc, self.rot, self.bend_, self.ext_, self.scl, self.curve_ = {}, {}, {}, {}, {}, {}

    def dome(self, sz=1.0, sx=None, sy=None, lean=0.0, roll=0.0):
        """Compose onto the dome: sz height, sx, sy width and depth (default: volume kept, 1/sqrt(sz)); leans add."""
        k = 1 / math.sqrt(max(sz, 1e-3))
        s = Vector((sx if sx is not None else k, sy if sy is not None else k, sz))
        self.dome_s = Vector((self.dome_s.x * s.x, self.dome_s.y * s.y, self.dome_s.z * s.z))
        self.dome_lean = [self.dome_lean[0] + lean, self.dome_lean[1] + roll]

    def move(self, n, v):
        self.loc[n] = self.loc.get(n, Vector()) + Vector(v)

    def turn(self, n, axis, deg):
        self.rot[n] = Matrix.Rotation(rad(deg), 3, Vector(axis)) @ self.rot.get(n, Matrix.Identity(3))

    def turn_m(self, n, m3):
        self.rot[n] = m3 @ self.rot.get(n, Matrix.Identity(3))

    def bend(self, n, pitch=0.0, yaw=0.0):
        p, y = self.bend_.get(n, (0.0, 0.0))
        self.bend_[n] = (p + pitch, y + yaw)

    def ext(self, n, m):
        self.ext_[n] = self.ext_.get(n, 0.0) + m

    def scale(self, n, s):
        s = Vector(s) if hasattr(s, "__len__") else Vector((s, s, s))
        old = self.scl.get(n, Vector((1, 1, 1)))
        self.scl[n] = Vector((old.x * s.x, old.y * s.y, old.z * s.z))

    def curve(self, pod, ctrl, tip, w):
        if w > 1e-4:
            self.curve_[pod] = (Vector(ctrl), Vector(tip), min(w, 1.0))

    # -- the dome's transform (rest space) and what follows it
    def dome_matrix(self):
        h = OR.DOME_HEAD
        R = Matrix.Rotation(rad(self.dome_lean[0]), 4, 'X') @ Matrix.Rotation(rad(self.dome_lean[1]), 4, (0, -1, 0))
        S = Matrix.Diagonal((*self.dome_s, 1.0))
        return Matrix.Translation(h) @ R @ S @ Matrix.Translation(-h)

    def follow(self, q):
        q = Vector(q)
        return (self.dome_matrix() @ q - q) * dome_w(q.z)


# ----------------------------------------------------------------------------------------- pose -> matrices
_REST = {}


def rest(rig):
    key = rig.name
    if key not in _REST:
        _REST[key] = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    return _REST[key]


def _delta_matrix(p, n, Rn, follow=True):
    """Rest-space matrix of bone n with its own offsets (as if its parent were at rest)."""
    head = Rn.to_translation()
    off = p.loc.get(n, Vector()) + (p.follow(head) if follow else Vector())
    Rw = p.rot.get(n, Matrix.Identity(3)).to_4x4()
    pitch, yaw = p.bend_.get(n, (0.0, 0.0))
    Rl = Matrix.Rotation(rad(pitch), 4, 'X') @ Matrix.Rotation(rad(yaw), 4, 'Z')
    e = p.ext_.get(n, 0.0)
    s = p.scl.get(n, Vector((1, 1, 1)))
    return (Matrix.Translation(off) @ Matrix.Translation(head) @ Rw @ Matrix.Translation(-head) @ Rn @
            Matrix.Translation((0, e, 0)) @ Rl @ Matrix.Diagonal((*s, 1.0)))


def _blend(A, B, w):
    la, ra, sa = A.decompose()
    lb, rb, sb = B.decompose()
    w = min(max(w, 0.0), 1.0)
    return Matrix.LocRotScale(la.lerp(lb, w), ra.slerp(rb, w), sa.lerp(sb, w))


def _curve_chain(rig_R, pod, P0, C, T):
    """The pod's three bones laid along the quadratic curve P0 -> C -> T (T = the tip bone's tail); the first two
    stretch to fit, the tip keeps its length. Rest-space matrices."""
    names = [f"{pod}{i + 1}" for i in range(3)]
    L = [rig_R[n].to_translation() for n in names]
    pts = [Vector(q[:3]) for q in OB.POD[pod]["pts"]]
    lens = [(pts[i + 1] - pts[i]).length for i in range(3)]
    u = np.linspace(0, 1, 97)
    Bz = [(1 - t) ** 2 * P0 + 2 * t * (1 - t) * C + t * t * T for t in map(float, u)]
    s = np.concatenate([[0], np.cumsum([(Bz[i + 1] - Bz[i]).length for i in range(96)])])
    S = s[-1]

    def at(d):
        i = int(np.clip(np.searchsorted(s, d) - 1, 0, 95))
        f = (d - s[i]) / max(s[i + 1] - s[i], 1e-9)
        return Bz[i].lerp(Bz[i + 1], float(np.clip(f, 0, 1)))
    s2 = max(S - lens[2], 0.05)
    J = [P0, at(s2 * lens[0] / (lens[0] + lens[1])), at(s2), T]
    out = {}
    for i, n in enumerate(names):
        Rn = rig_R[n]
        y0 = Rn.to_3x3().col[1]
        y1 = (J[i + 1] - J[i]).normalized()
        q = y0.rotation_difference(y1)
        out[n] = Matrix.Translation(J[i]) @ q.to_matrix().to_4x4() @ Rn.to_3x3().to_4x4()
    return out


def pose_world(rig, p):
    """-> armature-space matrix per bone."""
    R = rest(rig)
    world, done = {}, set()
    bones = sorted(rig.data.bones, key=lambda b: len(b.parent_recursive))
    for b in bones:
        n = b.name
        if n in done:
            continue
        par = b.parent.name if b.parent else None
        Dp = world[par] @ R[par].inverted() if par else Matrix.Identity(4)
        if n == "Motion":
            world[n] = Matrix.Translation(p.root) @ R[n]
        elif n == "Dome":
            world[n] = Dp @ p.dome_matrix() @ _delta_matrix(p, n, R[n], follow=False)
        elif n.endswith("1") and n[:-1] in OB.POD:
            pod = n[:-1]
            names = [f"{pod}{i + 1}" for i in range(3)]
            chain, M = {}, Matrix.Identity(4)
            for i, m in enumerate(names):                    # the bent chain, in the body's rest space
                Dm = _delta_matrix(p, m, R[m], follow=(i == 0))
                M = Dm if i == 0 else M @ R[names[i - 1]].inverted() @ Dm
                chain[m] = M
            if pod in p.curve_:
                C, T, w = p.curve_[pod]
                P0 = chain[names[0]].to_translation()
                cc = _curve_chain(R, pod, P0, C, T)
                chain = {m: _blend(chain[m], cc[m], w) for m in names}
            for m in names:
                world[m] = Dp @ chain[m]
                done.add(m)
        else:
            world[n] = Dp @ _delta_matrix(p, n, R[n], follow=n in PIECES or n in VACS or n.startswith("Socket_Gut"))
    return world


def apply(rig, p, frame=None):
    R = rest(rig)
    world = pose_world(rig, p)
    for b in rig.data.bones:
        n = b.name
        par = b.parent.name if b.parent else None
        base = (world[par] @ R[par].inverted() @ R[n]) if par else R[n]
        basis = base.inverted() @ world[n]
        loc, q, s = basis.decompose()
        pb = rig.pose.bones[n]
        if frame is not None and pb.rotation_quaternion.dot(q) < 0:
            q = -q
        pb.location, pb.rotation_quaternion, pb.scale = loc, q, s
        if frame is not None:
            for path in ("location", "rotation_quaternion", "scale"):
                pb.keyframe_insert(path, frame=frame, group=n)


# ----------------------------------------------------------------------------------------- helpers
def W(f, N, cycles=1, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def _pod_dir(pod, i=1, horizontal=False):
    pts = OB.POD[pod]["pts"]
    d = Vector(pts[i + 1][:3]) - Vector(pts[i][:3])
    if horizontal:
        d.z = 0
    return d.normalized()


def stretch(p, pod, e, horizontal=None):
    """Lengthen a pod by about e (m), shared by its last two joints. Floor pods slide along the floor."""
    horizontal = pod in FLOOR_PODS if horizontal is None else horizontal
    for i in (2, 3):
        if horizontal:
            p.move(f"{pod}{i}", _pod_dir(pod, i - 1, True) * (e / 2))
        else:
            p.ext(f"{pod}{i}", e / 2)


def drift(p, f, N, amp=1.0):
    """The floating contents, slowly (integer cycles, so it loops)."""
    for k, n in enumerate(PIECES):
        if n == "Coins":
            continue
        a = amp * (0.6 if n in ("Sword", "Helm") else 1.0)
        p.move(n, (0.012 * a * W(f, N, 1, 0.13 * k), 0.012 * a * W(f, N, 1, 0.31 * k + 0.25),
                   0.008 * a * W(f, N, 2, 0.17 * k)))
        p.turn(n, Vector((math.sin(k), math.cos(k), 0.5)).normalized(), 4 * a * W(f, N, 1, 0.21 * k))
    for k, n in enumerate(VACS):
        p.move(n, (0.006 * amp * W(f, N, 1, 0.4 * k), 0, 0.02 * amp * W(f, N, 1, 0.37 * k)))
    p.move("Nucleus", (0, 0, 0.01 * amp * W(f, N, 2, 0.1)))
    p.scale("Nucleus", 1 + 0.045 * amp * W(f, N, 2, 0.3))


def breathe(p, f, N, amp=1.0):
    """Idle life: the dome breathes, the pods sway (a wave down each), the uroid wags."""
    p.dome(sz=1 + 0.03 * amp * W(f, N))
    p.move("Body", (0.012 * amp * W(f, N, 1, 0.2), 0.015 * amp * W(f, N), 0))
    for k, pod in enumerate(PODS):
        for j in range(1, 4):
            a = W(f, N, 1, 0.21 * k + 0.12 * j)
            if pod in FLOOR_PODS:
                p.bend(f"{pod}{j}", yaw=3.0 * amp * a)
            else:
                p.bend(f"{pod}{j}", pitch=4.0 * amp * a, yaw=3.0 * amp * W(f, N, 1, 0.17 * k + 0.1 * j + 0.3))
        p.scale(f"{pod}3", 1 + 0.04 * amp * W(f, N, 2, 0.19 * k))
    p.bend("Tail", yaw=5 * amp * W(f, N, 1, 0.5))


# the collapsed shape (Death, Puddle, Rise): where things lie
FLAT = {"Reach": ((0.55, -1.0, 0.36), (0.62, -1.40, 0.20)), "Side": ((-1.1, 0.0, 0.34), (-1.40, 0.14, 0.18)),
        "Probe": ((-0.18, -0.30, 0.42), (-0.28, -0.80, 0.22))}           # pod -> (control point, tip) lying down
LIE_TURN = {"Skull": ((0, 1, 0), 70), "Helm": ((1, 0, 0), -35)}     # how the remains come to rest (world, deg)
CLEAR = 0.012                                                       # lowest point of a sunk piece above the floor


def _lie(n, dead, c=1.0):
    """World rotation and local scale of a sunk piece, c of the way there."""
    cc = min(max(c, 0.0), 1.0)
    if n == "Sword":
        axis = _sword_axis()
        Rw = Quaternion().slerp(axis.rotation_difference(Vector((axis.x, axis.y, 0)).normalized()), cc).to_matrix()
    elif n in LIE_TURN:
        ax, deg = LIE_TURN[n]
        Rw = Matrix.Rotation(rad(deg * cc), 3, Vector(ax))
    else:
        Rw = Matrix.Identity(3)
    s = Vector((1, 1, 1))
    if n == "Nucleus":                                              # local y is up: it slumps flat
        s = Vector((1 + 0.25 * c, 1 - 0.55 * c, 1 + 0.25 * c)) if dead else Vector((1 + 0.15 * c, 1 - 0.40 * c, 1 + 0.15 * c))
    return Rw, s


_SINK = {}


def _sink_z(rig, n, dead):
    """Where the piece's bone head ends up so that its lowest point, lying (_lie), is CLEAR above the floor
    (from the contents mesh: a centroid target sank the rotated helm and skull through the floor)."""
    key = (n, dead)
    if key not in _SINK:
        cont = bpy.data.objects["OozeContents"]
        me = cont.data
        names = list(cont["pieces"])
        piece = np.empty(len(me.polygons), np.int32)
        me.attributes["piece"].data.foreach_get("value", piece)
        vs = {v for p in me.polygons if OR.piece_bone(names[piece[p.index]]) == n for v in p.vertices}
        R = rest(rig)[n]
        h, Rr = R.to_translation(), R.to_3x3()
        Rw, s = _lie(n, dead)
        M = Rw @ Rr @ Matrix.Diagonal(s) @ Rr.transposed()
        _SINK[key] = CLEAR - min((M @ (me.vertices[i].co - h)).z for i in vs)
    return _SINK[key]


def collapse(p, rig, c, dead=False, t=0.0):
    """Blend toward the puddle by c (0..1). dead: the vacuoles pop and the nucleus goes slack."""
    R = rest(rig)
    p.dome(sz=1 - 0.70 * c, sx=1 + 0.30 * c, sy=1 + 0.30 * c)
    for pod, (C, T) in FLAT.items():
        p.curve(pod, C, T, c)
    for pod in FLOOR_PODS:
        stretch(p, pod, 0.10 * c)
    for pod in ("Reach", "Side"):                                   # tips sag flat (leaves: no shear)
        p.scale(f"{pod}3", Vector((1 + 0.2 * c, 1.0, 1 - 0.3 * c)))
    for n in PIECES:                                                # the remains sink to the floor
        h = R[n].to_translation()
        p.move(n, Vector((0, 0, (_sink_z(rig, n, dead) - h.z) * c)) - p.follow(h) * c)   # (and cancel the dome's carry)
        Rw, s = _lie(n, dead, c)
        p.turn_m(n, Rw)
        p.scale(n, s)
    for k, n in enumerate(VACS):
        h = R[n].to_translation()
        if dead:                                                   # pop one after another
            pop = smoothstep(0.15 + 0.08 * k, 0.25 + 0.08 * k, t)
            p.scale(n, max(1 - pop, 0.01))                           # (riding down with the dome)
        else:                                                      # gather under the flattened top
            p.move(n, Vector((0, 0, (0.14 + 0.02 * (k % 3) - h.z) * c)) - p.follow(h) * c)


_SWORD = []


def _sword_axis():
    """The sword's blade direction (from its pose in ooze_contents)."""
    if not _SWORD:
        import ooze_contents as OC
        M = OC._sword_pose()
        _SWORD.append((M.to_3x3() @ Vector((0, 1, 0))).normalized())
    return _SWORD[0]


# ----------------------------------------------------------------------------------------- clips
def _clip_idle():
    N = 90

    def fn(f):
        p = OozePose()
        breathe(p, f, N)
        drift(p, f, N)
        return p
    return N, fn, True


def _clip_crawl():
    """Amoeboid flow: the leading pods reach out, the mass surges into them, the rear pods and the uroid trail."""
    N = 60

    def fn(f):
        p = OozePose()
        p.root = Vector((0, -CRAWL_LOOP * f / N, 0))
        s = W(f, N)                                   # +: surging forward
        lag = W(f, N, 1, -0.12)
        p.move("Body", (0.01 * W(f, N, 1, 0.25), -0.12 * s, 0))
        p.dome(sz=1 - 0.06 * lag, sy=1 + 0.07 * lag, sx=1.0, lean=8 * W(f, N, 1, 0.15))
        stretch(p, "Lead", 0.22 * (0.5 + 0.5 * W(f, N, 1, -0.1)))
        p.bend("Lead2", yaw=4 * s)
        stretch(p, "Reach", 0.16 * (0.5 + 0.5 * W(f, N, 1, 0.4)))
        for j in (1, 2, 3):
            p.bend(f"Reach{j}", pitch=-5 * (0.5 + 0.5 * W(f, N, 1, 0.4)) + 2 * j * W(f, N, 1, 0.1 * j))
        stretch(p, "Back", -0.12 * (0.5 + 0.5 * s))
        p.bend("Back1", yaw=6 * W(f, N, 1, 0.15))
        stretch(p, "Bud", 0.05 * W(f, N, 1, 0.3))
        for j in (1, 2, 3):
            p.bend(f"Side{j}", pitch=5 * W(f, N, 1, 0.1 * j + 0.2), yaw=4 * W(f, N, 1, 0.1 * j))
            p.bend(f"Probe{j}", pitch=7 * W(f, N, 1, -0.12 - 0.06 * j))
        p.move("Tail", (0.02 * W(f, N, 2), 0.09 * s, 0))
        p.bend("Tail", yaw=6 * W(f, N, 2, 0.1))
        p.move("Gut", (0, 0.035 * W(f, N, 1, -0.15), 0.01 * W(f, N, 2)))
        drift(p, f, N, 0.6)
        return p
    return N, fn, True


def _clip_lash():
    """The Probe rears back, then slams down in front (Hit at frame 20)."""
    N = 40

    def fn(f):
        p = OozePose()
        breathe(p, f, N, 0.3)
        drift(p, f, N, 0.5)
        back = K([(0, 0), (12, 1), (15, 1), (18, 0), (40, 0)], f)
        strike = K([(0, 0), (15, 0), (20, 1), (26, 0.9), (40, 0)], f)
        for j, (b, s) in enumerate(((-30, 20), (-22, 10), (-15, -10)), 1):
            p.bend(f"Probe{j}", pitch=b * back)
        p.curve("Probe", (-0.16, -0.55, 1.55), (-0.25, -1.45, 0.24), strike)
        p.dome(sz=1 + 0.08 * back - 0.08 * strike, lean=-8 * back + 12 * strike)
        p.move("Body", (0, 0.05 * back - 0.09 * strike, 0))
        stretch(p, "Lead", 0.06 * strike)
        stretch(p, "Back", -0.05 * strike)
        p.scale("Probe3", 1 + 0.2 * K([(0, 0), (19, 0), (21, 1), (28, 0), (40, 0)], f))
        return p
    return N, fn, False


def _clip_grab():
    """Reach shoots out, swells round what it catches (Hit at 18) and hauls it back."""
    N = 44

    def fn(f):
        p = OozePose()
        breathe(p, f, N, 0.3)
        drift(p, f, N, 0.5)
        out = K([(0, 0), (6, 0.1), (16, 1), (22, 0.95), (36, 0.1), (44, 0)], f)
        tip = Vector((0.30, -1.95, 0.30)).lerp(Vector((0.35, -1.55, 0.45)), K([(0, 0), (22, 0), (36, 1), (44, 1)], f))
        p.curve("Reach", (0.48, -1.05, 0.95), tip, out)
        p.scale("Reach3", 1 + 0.25 * K([(0, 0), (16, 0), (19, 1), (30, 0.6), (44, 0)], f))
        p.dome(sz=1 - 0.05 * out, lean=8 * out, roll=-4 * out)
        p.move("Body", (0.03 * out, -0.07 * out, 0))
        stretch(p, "Back", -0.05 * out)
        return p
    return N, fn, False


def _clip_engulf():
    """Reach and Lead close round a victim in front (Grab at 22: hold it on Socket_Mouth), pull it in while the dome
    rolls over it and the Probe comes down on top (Engulf at 46: Socket_Mouth has reached Socket_Gut), then settle."""
    N = 80

    def fn(f):
        p = OozePose()
        breathe(p, f, N, 0.25)
        drift(p, f, N, 0.6)
        wrap = K([(0, 0), (10, 0.6), (20, 1), (40, 1), (52, 0.3), (64, 0), (80, 0)], f)
        pull = K([(0, 0), (22, 0), (46, 1), (80, 1)], f)
        reach_tip = Vector((-0.05, -1.55, 0.45)).lerp(Vector((-0.05, -0.95, 0.45)), pull)
        lead_tip = Vector((0.10, -1.60, 0.10)).lerp(Vector((0.10, -1.0, 0.10)), pull)   # along the floor: lifted,
        # its open underside would show
        p.curve("Reach", (0.80, -1.30, 0.85), reach_tip, wrap)
        p.curve("Lead", (-0.85, -1.35, 0.12), lead_tip, wrap)
        over = K([(0, 0), (16, 0.2), (30, 1), (46, 1), (60, 0), (80, 0)], f)
        p.curve("Probe", (-0.10, -0.70, 1.55), (-0.05, -1.25, 0.70), over)
        surge = K([(0, 0), (20, 1), (40, 0.8), (60, 0), (80, 0)], f)
        p.move("Body", (0, -0.22 * surge, 0))
        settle = K([(0, 0), (46, 0), (52, 1), (58, -0.6), (64, 0.35), (70, -0.15), (80, 0)], f)
        p.dome(sz=1 + 0.10 * over - 0.10 * settle, sy=1 + 0.12 * surge, lean=14 * over)
        p.turn("Gut", (0, 0, 1), 25 * pull)
        g, m = Vector((0.0, 0.05, 0.45)), Vector((0.0, -1.10, 0.40))
        # held where it was caught while the body surges at it, then drawn in to the gut
        p.move("Socket_Mouth", (g - m) * pull + Vector((0, 0.22 * surge * (1 - pull), 0)))
        return p
    return N, fn, False


def _clip_spit():
    """The dome contracts, the Probe aims forward and up, the dome pumps: the glob leaves Socket_Spit at 21."""
    N = 44

    def fn(f):
        p = OozePose()
        breathe(p, f, N, 0.3)
        drift(p, f, N, 0.5)
        aim = K([(0, 0), (12, 1), (30, 1), (44, 0)], f)
        p.curve("Probe", (-0.15, -0.10, 1.45), (-0.22, -0.80, 1.50), aim)
        pump = K([(0, 0), (14, -1), (19, -1), (22, 1), (28, -0.3), (34, 0.1), (44, 0)], f)
        p.dome(sz=1 + 0.10 * pump, lean=-4 * aim)
        p.scale("Probe3", 1 + 0.25 * K([(0, 0), (17, 0.3), (20, 1), (24, -0.2), (30, 0), (44, 0)], f))
        p.move("Gut", (0, 0, -0.03 * pump))
        return p
    return N, fn, False


def _clip_hit():
    """A jolt from the front: the dome jiggles (a damped wobble), the pods flinch."""
    N = 24

    def fn(f):
        p = OozePose()
        breathe(p, f, N, 0.2)
        drift(p, f, N, 0.3)
        j = math.exp(-f / 6.0) * math.cos(f / 2.2) * (f > 0)
        kick = K([(0, 0), (3, 1), (10, 0.2), (24, 0)], f)
        p.dome(sz=1 - 0.12 * j, lean=-10 * j)
        p.move("Body", (0, 0.06 * kick, 0))
        for k, pod in enumerate(PODS):
            for i in (1, 2, 3):
                if pod in FLOOR_PODS:
                    p.bend(f"{pod}{i}", yaw=(5 if k % 2 else -5) * j)
                else:
                    p.bend(f"{pod}{i}", pitch=8 * j)
        p.move("Gut", (0, 0.04 * kick, 0.02 * j))
        return p
    return N, fn, False


def _clip_death():
    """Collapses into a puddle with a last shudder: raised pods flop, the remains sink, the vacuoles pop."""
    N = 70

    def fn(f):
        rig = bpy.data.objects[RIG]
        p = OozePose()
        c = K([(0, 0), (6, -0.05), (30, 0.85), (40, 1.03), (48, 0.97), (56, 1.0), (70, 1.0)], f)
        collapse(p, rig, c, dead=True, t=f / N)
        shudder = math.exp(-f / 10.0) * math.sin(f / 1.6) * 0.5
        p.move("Body", (0.02 * shudder, 0.03 * shudder, 0))
        return p
    return N, fn, False


def _clip_puddle():
    N = 90

    def fn(f):
        rig = bpy.data.objects[RIG]
        p = OozePose()
        collapse(p, rig, 1.0)
        p.dome(sz=1 + 0.05 * W(f, N), sx=1 + 0.008 * W(f, N, 1, 0.25), sy=1 + 0.008 * W(f, N, 1, 0.5))   # ripple
        for k, pod in enumerate(PODS):
            p.bend(f"{pod}2", yaw=2 * W(f, N, 1, 0.2 * k))
        drift(p, f, N, 0.3)
        return p
    return N, fn, True


def _clip_rise():
    """From the puddle back to its full shape, overshooting (Risen at 30)."""
    N = 50

    def fn(f):
        rig = bpy.data.objects[RIG]
        p = OozePose()
        c = K([(0, 1), (4, 1.02), (20, 0.25), (28, -0.10), (36, 0.04), (44, -0.01), (50, 0)], f)
        collapse(p, rig, max(c, 0.0))
        if c < 0:
            p.dome(sz=1 - 1.0 * c)                     # past full height: stretches tall
        b = f / N
        breathe(p, f, N, smoothstep(0.6, 1.0, b))
        return p
    return N, fn, False


CLIPS = {"Idle": _clip_idle, "Crawl": _clip_crawl, "Lash": _clip_lash, "Grab": _clip_grab, "Engulf": _clip_engulf,
         "Spit": _clip_spit, "Hit": _clip_hit, "Death": _clip_death, "Puddle": _clip_puddle, "Rise": _clip_rise}


# ----------------------------------------------------------------------------------------- build / use
def build_clip(name, rig=None):
    rig = rig or bpy.data.objects[RIG]
    _REST.pop(rig.name, None)
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
    rig.animation_data_create()
    rig.animation_data.action = act
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.matrix_basis = Matrix.Identity(4)
    for f in range(N + 1):
        apply(rig, fn(f), frame=f)
    for fc in _fcurves(act):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    act.frame_range = (0, N)
    return act


def build_clips(names=None):
    return {n: build_clip(n) for n in (names or CLIPS)}


def use(name, rig=None):
    rig = rig or bpy.data.objects[RIG]
    act = bpy.data.actions[action_name(name)]
    rig.animation_data_create()
    rig.animation_data.action = act
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 0, int(act["frames"])
    scn.frame_set(0)


def clear(rig=None):
    rig = rig or bpy.data.objects[RIG]
    if rig.animation_data:
        rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def still(p, rig=None):
    rig = rig or bpy.data.objects[RIG]
    if rig.animation_data:
        rig.animation_data.action = None
    apply(rig, p)
    bpy.context.view_layer.update()


# ----------------------------------------------------------------------------------------- checks
def _evaluated(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    tris = [tuple(t.vertices) for t in me.loop_triangles] if me.loop_triangles else None
    if tris is None:
        me.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in me.loop_triangles]
    ev.to_mesh_clear()
    return co.reshape(-1, 3), tris


RAYS = (Vector((0, 0, 1)), Vector((0.35, 0.2, 1)).normalized(), Vector((-0.3, 0.3, 1)).normalized())


def _inside(bvh, o, d):
    """Odd number of hits along d (the shell is open only at the floor, so every ray going up leaves it)."""
    hits = 0
    for _ in range(10):
        loc, nrm, idx, dist = bvh.ray_cast(o, d)
        if loc is None:
            break
        hits += 1
        o = loc + d * 1e-4
    return hits % 2 == 1


def report(names=None, step=6):
    """Per clip: the shell's lowest vertex, its highest rim vertex (the open bottom must stay on the floor), the
    contents' lowest vertex, and how many content vertices end up outside the shell (rays up: an odd number of hits = inside; the sword, which
    sticks out, is left out)."""
    from mathutils.bvhtree import BVHTree
    body, cont = bpy.data.objects["OozeBody"], bpy.data.objects["OozeContents"]
    me = cont.data
    names_p = list(cont["pieces"])
    piece = np.empty(len(me.polygons), np.int32)
    me.attributes["piece"].data.foreach_get("value", piece)
    sword = {v for p in me.polygons if names_p[piece[p.index]].startswith("sword") for v in p.vertices}
    keep = np.array([i not in sword for i in range(len(me.vertices))])
    rim = np.array([v.co.z < 1e-4 for v in body.data.vertices])
    scn = bpy.context.scene
    out = {}
    for name in (names or CLIPS):
        use(name)
        N = int(bpy.data.actions[action_name(name)]["frames"])
        lo, rim_hi, outside, c_lo = 1e9, -1e9, 0, 1e9
        for f in list(range(0, N + 1, step)) + [N]:
            scn.frame_set(f)
            S, T = _evaluated(body)
            Cc, _ = _evaluated(cont)
            lo = min(lo, float(S[:, 2].min()))
            c_lo = min(c_lo, float(Cc[:, 2].min()))
            rim_hi = max(rim_hi, float(S[rim, 2].max()))
            bvh = BVHTree.FromPolygons([Vector(v) for v in S], T)
            n_out = 0
            for v in Cc[keep][::3]:
                n_out += sum(_inside(bvh, Vector(v), d) for d in RAYS) < 2       # majority of 3 (a ray grazing
                # an edge counts wrong)
            outside = max(outside, n_out)
        out[name] = dict(lowest=round(lo, 3), rim_high=round(rim_hi, 3), contents_out=outside,
                         contents_low=round(c_lo, 3))
    clear()
    return out
