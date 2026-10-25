"""The dragon (2026-10-17, Daniel's "big test"): a six-limbed fire dragon after his two references (one perched on a
rock, one in flight). About 12 m nose to tail, 2.8 m at the shoulder, 16 m across the wings.

Stage 1 is a blockout: the skeleton plus rough volumes skinned to it, so the proportions and the wing fold can be
judged in poses (dragon_pose) before any detail goes on. The neck, trunk and tail are one loft with smooth chain
weights; legs, wing arms and fingers are rigid segments per bone (they fold too far for blended weights). The wing
membranes are Coons patches between the arm, the fingers and the flank, with their weights blended the same way, so
closing the fingers folds them like a fan.

Coordinates: metres, Z up, the dragon faces -Y, its left side is +X (beast_common). Joints are written for the left
side; the right side is mirrored.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from beast_common import loft, cone, spline, mesh_obj, get_coll, remove_obj, smoothstep, srgb_to_lin

RIG = "DragonRig"
COLL = "DRG_Blockout"
SIDES = ((1, "L"), (-1, "R"))
UP, FWD = (0, 0, 1), (0, -1, 0)
LEG_UP = (0, -0.5, 0.85)          # loft `up` for legs: forward on the vertical parts, up on the paws

# ----------------------------------------------------------------------------------------- proportions
NECK_N, TAIL_N = 7, 14
SPINE = dict(pelvis=(0, 1.25, 2.27), hips_end=(0, 1.75, 2.20), spine2=(0, 0.35, 2.43), chest=(0, -0.55, 2.49),
             neck_base=(0, -1.55, 2.53))
NECK_CTRL = ((0, -1.55, 2.53), (0, -2.15, 2.90), (0, -2.55, 3.50), (0, -2.80, 4.10), (0, -3.10, 4.50),
             (0, -3.50, 4.70))
TAIL_CTRL = ((0, 1.75, 2.20), (0, 2.80, 1.85), (0, 3.90, 1.30), (0, 5.00, 0.80), (0, 6.10, 0.50), (0, 7.25, 0.40))
TAIL_RATIO = 0.93                 # each tail bone this much shorter than the one before
HEAD = ((0, -3.50, 4.70), (0, -4.70, 4.50))      # head base -> snout tip
JAW = ((0, -3.55, 4.48), (0, -4.55, 4.26))       # hinge -> chin
FRONT = dict(scap=(0.55, -0.95, 2.35), sho=(0.80, -1.40, 1.65), elb=(0.80, -1.00, 0.95), wri=(0.76, -1.25, 0.28),
             paw=(0.76, -1.55, 0.12), toe=(0.76, -1.95, 0.03))
HIND = dict(hip=(0.75, 1.20, 1.90), knee=(0.88, 0.55, 1.20), hock=(0.82, 1.30, 0.62), paw=(0.80, 1.12, 0.12),
            toe=(0.80, 0.74, 0.03))
# the wing (bind pose = spread): elbow behind the shoulder-wrist line, four fingers from the knuckle; `att` is where
# the trailing edge meets the flank, in front of the hip. The wing root sits on top of the shoulders, right above the
# front legs' shoulder blades (Daniel, 2026-10-17: "a tad up, to the shoulders"; it was 0.3 m further back and
# 0.2 m lower).
WING = dict(root=(0.18, -0.90, 2.82), sho=(0.55, -1.15, 2.95), elb=(1.88, -0.75, 3.25), wri=(3.58, -1.35, 3.45),
            knu=(3.85, -1.30, 3.45), thumb=(3.73, -1.80, 3.52), att=(0.80, 1.30, 2.30),
            tips=((7.93, -0.20, 3.15), (7.13, 1.40, 3.05), (5.53, 2.45, 2.95), (3.88, 2.75, 2.85)))
FINGER_SEGS = (3, 3, 2, 2)
FINGER_BOW = 0.05                 # fingers bow toward the leading edge (fraction of their length)


class WingSpec:
    """A membrane wing for the wing code below (2026-10-23: parametrised so the giant bat reuses it; the dragon's is
    DRAGON_WING, every default being the dragon's own constant, so the dragon builds exactly as before).

    wing: joints of the left wing in the bind pose (root, sho, elb, wri, knu, thumb, att, tips: one per finger);
    segs: bones per finger; bow: fingers bow toward the leading edge; nu, nv, mem_i, mem_j: the arm panel's grid and
    its helper bones' nodes; trunk: the bones the flank edge leans on; sag / finger_sag: the trailing edge's scallops;
    lead: how far the leading edge's membrane stands in front of the shoulder-wrist line; flank(B, s_, sfx, nv):
    optional left edge (P, W) of the arm panel from the shoulder to `att` (the dragon's is a straight line on the
    trunk); att_w(B, s_, sfx): optional weights at `att`; rest_bones: the creature's bone table (for membrane_pose)."""

    def __init__(self, wing=None, segs=None, bow=None, nu=15, nv=10, mem_i=(3, 6, 9, 12), mem_j=(3, 6, 9),
                 trunk=("Chest", "Spine2", "Spine1", "Hips"), sag=0.12, finger_sag=0.18, lead=(0, -0.12, 0.02),
                 flank=None, att_w=None, rest_bones=None, name="dragon"):
        self.wing = wing if wing is not None else WING
        self.segs = segs if segs is not None else FINGER_SEGS
        self.bow = bow if bow is not None else FINGER_BOW
        self.nu, self.nv, self.mem_i, self.mem_j = nu, nv, mem_i, mem_j
        self.trunk, self.sag, self.finger_sag, self.lead = trunk, sag, finger_sag, lead
        self.flank, self.att_w, self.rest_bones, self.name = flank, att_w, rest_bones, name
        self.panel = {}

    def bones(self):
        if self.rest_bones is None:
            return rest_bones_cached()
        if "B" not in self.panel:
            self.panel["B"] = self.rest_bones()
        return self.panel["B"]

# neck -> trunk -> tail loft: x, y, z, a (half width), b (dorsal), c (ventral). The spine runs near the top of the
# back, so the trunk hangs below it (c >> b); the throat swells into the chest.
BODY_ROWS = (
    (0, -3.50, 4.70, 0.30, 0.30, 0.34),
    (0, -3.10, 4.50, 0.36, 0.32, 0.42),
    (0, -2.80, 4.10, 0.40, 0.34, 0.48),
    (0, -2.55, 3.50, 0.46, 0.37, 0.58),
    (0, -2.15, 2.90, 0.60, 0.40, 0.80),
    (0, -1.55, 2.53, 0.86, 0.42, 1.18),
    (0, -0.95, 2.51, 0.98, 0.42, 1.45),
    (0, -0.20, 2.47, 1.00, 0.42, 1.36),
    (0, 0.60, 2.40, 0.92, 0.40, 1.12),
    (0, 1.25, 2.28, 0.84, 0.42, 0.92),
    (0, 1.75, 2.20, 0.64, 0.38, 0.64),
    (0, 2.80, 1.85, 0.46, 0.33, 0.42),
    (0, 3.90, 1.30, 0.32, 0.26, 0.29),
    (0, 5.00, 0.80, 0.20, 0.18, 0.19),
    (0, 6.10, 0.50, 0.11, 0.10, 0.10),
    (0, 7.25, 0.40, 0.025, 0.025, 0.025),
)
HEAD_K = 1.3                      # the head parts are written at natural size and enlarged about the head base
SKULL_ROWS = (
    (0, -3.25, 4.76, 0.26, 0.26, 0.30),
    (0, -3.55, 4.74, 0.34, 0.30, 0.30),
    (0, -3.85, 4.68, 0.29, 0.24, 0.20),
    (0, -4.15, 4.60, 0.22, 0.17, 0.13),
    (0, -4.45, 4.53, 0.18, 0.14, 0.11),
    (0, -4.66, 4.49, 0.15, 0.10, 0.09),
)
BROW = ((0.17, -3.66, 4.90), (0.21, -3.98, 4.83), 0.065)     # ridge over each eye
JAW_ROWS = (
    (0, -3.45, 4.46, 0.24, 0.10, 0.16),
    (0, -3.80, 4.42, 0.24, 0.10, 0.15),
    (0, -4.15, 4.36, 0.19, 0.08, 0.11),
    (0, -4.45, 4.30, 0.16, 0.07, 0.08),
    (0, -4.62, 4.27, 0.12, 0.06, 0.06),
)
EYE = ((0.255, -3.82, 4.74), 0.065)
HORN = ((0.17, -3.55, 4.92, 0.10), (0.26, -3.30, 5.14, 0.085), (0.33, -2.98, 5.28, 0.065), (0.38, -2.66, 5.33, 0.045),
        (0.41, -2.38, 5.42, 0.02))
CROWN = (((0.24, -3.42, 4.84), (0.44, -3.02, 5.02), 0.055), ((0.29, -3.35, 4.70), (0.55, -3.00, 4.76), 0.05),
         ((0.28, -3.30, 4.56), (0.50, -3.00, 4.48), 0.045))
JAW_SPIKES = (((0.22, -3.65, 4.35), (0.36, -3.55, 4.20), 0.04), ((0.20, -3.85, 4.32), (0.33, -3.80, 4.15), 0.035),
              ((0.17, -4.05, 4.28), (0.28, -4.02, 4.12), 0.03))
FANGS = (((0.12, -4.40, 4.45), (0.12, -4.42, 4.30), 0.028), ((0.15, -4.20, 4.50), (0.15, -4.21, 4.38), 0.022))
FRILL = ((0.27, -3.45, 4.55), ((0.62, -3.15, 4.95), (0.74, -3.00, 4.62), (0.62, -3.05, 4.28)))   # base, spine tips

# colours (sRGB): Daniel's first dragon, "classic fire dragon: rusty red back, paler belly, dark horns and spikes,
# amber eyes". Blockout only; the real paint will be masks + colour presets (dragons come in many colours).
COL = dict(back="8c2e14", belly="d9a04c", horn="2a211c", membrane="7a2a14", eye="ffa21a", claw="1c1714")


def _rgb(h):
    from beast_common import hexc
    return tuple(float(x) for x in srgb_to_lin(hexc(h)))


# ----------------------------------------------------------------------------------------- chains
def _curve(ctrl, n, ratio=1.0, dense=24):
    """n+1 points along a Catmull-Rom curve through ctrl; the steps shrink by `ratio` each."""
    P = spline(ctrl, dense)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    steps = ratio ** np.arange(n)
    at = np.concatenate([[0], np.cumsum(steps)]) / steps.sum() * s[-1]
    return np.array([np.interp(at, s, P[:, k]) for k in range(3)]).T


def neck_pts():
    return _curve(NECK_CTRL, NECK_N)


def tail_pts():
    return _curve(TAIL_CTRL, TAIL_N, TAIL_RATIO)


def finger_pts(i, ws=None):
    """Joints of finger i (0 = the leading one, to the wing tip), left wing, knuckle first."""
    ws = ws or DRAGON_WING
    k, t = np.array(ws.wing["knu"], float), np.array(ws.wing["tips"][i], float)
    d = t - k
    L = np.linalg.norm(d)
    lead = -np.cross((0, 0, 1), d / L)
    lead /= np.linalg.norm(lead)
    return np.array([k + d * x + lead * ws.bow * L * 4 * x * (1 - x) for x in np.linspace(0, 1, ws.segs[i] + 1)])


def _m(p, s):
    return (s * p[0], p[1], p[2])


def hk(p):
    """Head parts and bones: enlarged by HEAD_K about the head base (the neck's end stays put)."""
    h0 = np.array(HEAD[0], float)
    return tuple(h0 + (np.asarray(p[:3], float) - h0) * HEAD_K)


def hk_rows(rows):
    return [(*hk(r), *(np.asarray(r[3:], float) * HEAD_K)) for r in rows]


# ----------------------------------------------------------------------------------------- skeleton
def _frame(ydir, zhint):
    y = Vector(ydir).normalized()
    z = Vector(zhint)
    z = (z - y * z.dot(y)).normalized()
    return Matrix((y.cross(z), y, z)).transposed()


def _bone(B, name, head, tail, zhint, parent, deform=True):
    head, tail = Vector(head), Vector(tail)
    B[name] = (head, _frame(tail - head, zhint), (tail - head).length, parent, deform)


def wing_chain(sfx, ws=None):
    """The wing bones below WingScap, parents first."""
    ws = ws or DRAGON_WING
    names = [f"WingArm{sfx}", f"WingForearm{sfx}", f"WingHand{sfx}", f"WingThumb{sfx}"]
    for i in range(len(ws.segs)):
        names += [f"WingF{i + 1}_{k + 1}{sfx}" for k in range(ws.segs[i])]
    return names


def wing_bones(B, s, sfx, ws=None, parent="Chest", zhint=UP):
    """The wing's bones (WingScap .. the fingers) and the arm panel's helpers into the bone table B."""
    ws = ws or DRAGON_WING
    m = lambda p: _m(p, s)
    W = ws.wing
    _bone(B, f"WingScap{sfx}", m(W["root"]), m(W["sho"]), zhint, parent)
    _bone(B, f"WingArm{sfx}", m(W["sho"]), m(W["elb"]), zhint, f"WingScap{sfx}")
    _bone(B, f"WingForearm{sfx}", m(W["elb"]), m(W["wri"]), zhint, f"WingArm{sfx}")
    _bone(B, f"WingHand{sfx}", m(W["wri"]), m(W["knu"]), zhint, f"WingForearm{sfx}")
    _bone(B, f"WingThumb{sfx}", m(W["wri"]), m(W["thumb"]), zhint, f"WingHand{sfx}")
    for i in range(len(ws.segs)):
        P, par = finger_pts(i, ws), f"WingHand{sfx}"
        for k in range(len(P) - 1):
            name = f"WingF{i + 1}_{k + 1}{sfx}"
            _bone(B, name, m(P[k]), m(P[k + 1]), zhint, par)
            par = name
    P, _ = coons(*arm_panel(B, s, sfx, ws))                 # the arm panel's helper bones (membrane_pose)
    for n, (h, fr) in _mem_frames(P, sfx, ws).items():
        B[n] = (Vector(h), fr, 0.25, f"WingScap{sfx}", True)


def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform), the beasts' conventions (beast_rig.build_armature):
    Root and Motion point up with +Z toward the front, Motion carries the root motion; spine, neck, tail and legs bend
    about their local X (+ raises / swings forward). Wing bones keep +Z on the membrane's upper side, so turning about
    local Z sweeps a bone within the wing plane and about local X flaps it."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.8, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.6, None, True)
    S = SPINE
    _bone(B, "Hips", S["pelvis"], S["hips_end"], UP, "Root")
    _bone(B, "Spine1", S["pelvis"], S["spine2"], UP, "Hips")
    _bone(B, "Spine2", S["spine2"], S["chest"], UP, "Spine1")
    _bone(B, "Chest", S["chest"], S["neck_base"], UP, "Spine2")
    neck, par = neck_pts(), "Chest"
    for i in range(NECK_N):
        _bone(B, f"Neck{i + 1}", neck[i], neck[i + 1], UP, par)
        par = f"Neck{i + 1}"
    _bone(B, "Head", HEAD[0], hk(HEAD[1]), UP, par)
    import dragon_head as DH
    _bone(B, "Jaw", DH.to_body(DH.HINGE), DH.to_body(DH.CHIN_TIP), UP, "Head")
    tail, par = tail_pts(), "Hips"
    for i in range(TAIL_N):
        _bone(B, f"Tail{i + 1}", tail[i], tail[i + 1], UP, par)
        par = f"Tail{i + 1}"
    for s, sfx in SIDES:
        m = lambda p: _m(p, s)
        F, H, W = FRONT, HIND, WING
        _bone(B, f"Scapula{sfx}", m(F["scap"]), m(F["sho"]), FWD, "Chest")
        _bone(B, f"UpperArm{sfx}", m(F["sho"]), m(F["elb"]), FWD, f"Scapula{sfx}")
        _bone(B, f"Forearm{sfx}", m(F["elb"]), m(F["wri"]), FWD, f"UpperArm{sfx}")
        _bone(B, f"FrontPaw{sfx}", m(F["wri"]), m(F["paw"]), FWD, f"Forearm{sfx}")
        _bone(B, f"FrontToes{sfx}", m(F["paw"]), m(F["toe"]), UP, f"FrontPaw{sfx}")
        _bone(B, f"Thigh{sfx}", m(H["hip"]), m(H["knee"]), FWD, "Hips")
        _bone(B, f"Shin{sfx}", m(H["knee"]), m(H["hock"]), FWD, f"Thigh{sfx}")
        _bone(B, f"HindFoot{sfx}", m(H["hock"]), m(H["paw"]), FWD, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(H["paw"]), m(H["toe"]), UP, f"HindFoot{sfx}")
        wing_bones(B, s, sfx)
    mouth = Vector(DH.to_body(DH.MOUTH))                     # sockets: head = attach point, +Y up, +Z forward
    _bone(B, "Socket_Mouth", mouth, mouth + Vector((0, 0, 0.2)), FWD, "Head")
    return B


def wing_collections(rig):
    """build_armature files the wing bones under Body; give them their own bone collection."""
    ad = rig.data
    col = ad.collections.get("Wings") or ad.collections.new("Wings")
    body = ad.collections.get("Body")
    for b in ad.bones:
        if b.name.startswith("Wing"):
            if body is not None:
                body.unassign(b)
            col.assign(b)
            b.color.palette = 'THEME03' if b.name.endswith("L") else 'THEME04'


# ----------------------------------------------------------------------------------------- weights
def _norm(w, keep=4):
    w = {k: v for k, v in w.items() if v > 1e-4}
    top = sorted(w.items(), key=lambda kv: -kv[1])[:keep]
    t = sum(v for _, v in top)
    return {k: v / t for k, v in top}


def chain_weights(P, bones, falloff=0.25):
    """Each point leans on the chain bones nearest to it, blended over `falloff` metres of extra distance.
    bones: [(name, head, tail)]."""
    D = []
    for _, h, t in bones:
        h, t = np.asarray(h, float), np.asarray(t, float)
        d = t - h
        u = np.clip(((P - h) @ d) / (d @ d), 0, 1)
        D.append(np.linalg.norm(P - (h + u[:, None] * d), axis=1))
    D = np.array(D).T
    W = np.clip(1 - (D - D.min(axis=1, keepdims=True)) / falloff, 0, None) ** 2
    names = [b[0] for b in bones]
    return [_norm({names[j]: W[i, j] for j in np.nonzero(W[i])[0]}) for i in range(len(P))]


def _bones_of(B, names):
    return [(n, B[n][0], B[n][0] + B[n][1].col[1] * B[n][2]) for n in names]


def polyline(points, bones, n, start=None, end=None, blend=0.2):
    """n points evenly along a polyline, each riding on the bone of its segment, blended across the joints over
    `blend` metres. start / end: a bone the first / last `blend` metres blend in from (shared corners).
    A joint's blend reaches at most a quarter of the segments on either side: the bat's finger bones are 0.22 m, and a
    0.2 m blend bent its membrane's edge across the whole bone while the finger itself bent at the joint, 3 cm off it.
    -> (P (n, 3), [weights])"""
    pts = np.asarray(points, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s0 = np.concatenate([[0], np.cumsum(seg)])
    P, W = [], []
    for s in np.linspace(0, s0[-1], n):
        i = min(np.searchsorted(s0, s, side='right') - 1, len(seg) - 1)
        f = (s - s0[i]) / seg[i]
        P.append(pts[i] + (pts[i + 1] - pts[i]) * f)
        w = {bones[i]: 1.0}
        d0, d1 = s - s0[i], s0[i + 1] - s
        prev = bones[i - 1] if i > 0 else start
        nxt = bones[i + 1] if i + 1 < len(bones) else end
        b0 = min(blend, 0.25 * seg[i], 0.25 * seg[i - 1] if i > 0 else blend)
        b1 = min(blend, 0.25 * seg[i], 0.25 * seg[i + 1] if i + 1 < len(seg) else blend)
        if prev is not None and d0 < b0:
            k = 0.5 + 0.5 * d0 / b0
            w = {bones[i]: k}
            w[prev] = w.get(prev, 0) + 1 - k
        elif nxt is not None and d1 < b1:
            k = 0.5 + 0.5 * d1 / b1
            w = {bones[i]: k}
            w[nxt] = w.get(nxt, 0) + 1 - k
        W.append(w)
    return np.array(P), W


def _wmix(terms):
    out = {}
    for f, w in terms:
        for k, v in w.items():
            out[k] = out.get(k, 0.0) + f * v
    return _norm({k: max(v, 0.0) for k, v in out.items()})


def coons(bottom, top, left, right):
    """Coons patch: bottom/top = (P (nu, 3), W) along u, left/right = (P (nv, 3), W) along v; the corners must meet
    (bottom[0] = left[0], bottom[-1] = right[0], top[0] = left[-1], top[-1] = right[-1]). Positions are exact Coons;
    weights blend the same way with the corners taken from bottom/top. -> P (nu, nv, 3), W [nu][nv]
    The left / right edges' corner weights are replaced by bottom's / top's: where they differed (a finger edge
    starting half on the hand, the side edge all on the hand), the difference leaked along the whole bottom / top edge,
    so a finger's membrane edge carried hand weight to its tip and left the finger when it spread (Daniel 2026-10-24:
    "a hole in the middle of the dragon wing ... as if the membrane were not attached to the finger"). A corner is
    on a joint, where either weighting puts it in the same place."""
    (Pb, Wb), (Pt, Wt), (Pl, Wl), (Pr, Wr) = bottom, top, left, right
    Wl, Wr = list(Wl), list(Wr)
    Wl[0], Wl[-1], Wr[0], Wr[-1] = Wb[0], Wt[0], Wb[-1], Wt[-1]
    nu, nv = len(Pb), len(Pl)
    P = np.zeros((nu, nv, 3))
    W = [[None] * nv for _ in range(nu)]
    for i in range(nu):
        u = i / (nu - 1)
        for j in range(nv):
            v = j / (nv - 1)
            P[i, j] = ((1 - v) * Pb[i] + v * Pt[i] + (1 - u) * Pl[j] + u * Pr[j]
                       - ((1 - u) * (1 - v) * Pb[0] + u * (1 - v) * Pb[-1] + (1 - u) * v * Pt[0] + u * v * Pt[-1]))
            W[i][j] = _wmix([(1 - v, Wb[i]), (v, Wt[i]), (1 - u, Wl[j]), (u, Wr[j]),
                             (-(1 - u) * (1 - v), Wb[0]), (-u * (1 - v), Wb[-1]), (-(1 - u) * v, Wt[0]),
                             (-u * v, Wt[-1])])
    return P, W


def _sag(a, b, toward, n, depth=0.15):
    """n points from a to b, sagging toward `toward` by depth x |b - a| in the middle (a scalloped trailing edge)."""
    a, b, toward = (np.asarray(x, float) for x in (a, b, toward))
    mid = (a + b) / 2
    d = toward - mid
    d /= np.linalg.norm(d)
    L = np.linalg.norm(b - a)
    t = np.linspace(0, 1, n)
    return a + (b - a) * t[:, None] + d * (depth * L * 4 * t * (1 - t))[:, None]


# ----------------------------------------------------------------------------------------- the mesh accumulator
class Acc:
    """One bmesh plus, per vertex, its weights and its colour (None = back/belly by the normal).

    Each piece is built in a bmesh of its own and appended: an op that deletes vertices (create_uvsphere) leaves
    free slots that later vertices fill, and then the iteration order no longer matches the order the per-vertex
    lists were written in (the horn bases came out in the eye's colour)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.W, self.C = [], []

    def add(self, build, weights=None, color=None):
        tmp = bmesh.new()
        out = build(tmp)
        tmp.verts.index_update()
        P = np.array([v.co[:] for v in tmp.verts]).reshape(-1, 3)
        if weights is None:
            W = out
        elif isinstance(weights, str):
            W = [{weights: 1.0}] * len(P)
        else:
            W = weights(P)
        assert len(W) == len(P), (len(W), len(P))
        vmap = [self.bm.verts.new(v.co) for v in tmp.verts]
        for f in tmp.faces:
            self.bm.faces.new([vmap[v.index] for v in f.verts])
        for e in tmp.edges:
            if e.seam:
                ne = self.bm.edges.get((vmap[e.verts[0].index], vmap[e.verts[1].index]))
                if ne is not None:
                    ne.seam = True
        tmp.free()
        self.W += W
        if callable(color):
            color = color(P)
        elif not isinstance(color, list):
            color = [color] * len(P)
        assert len(color) == len(P), (len(color), len(P))
        self.C += color

    def finish(self, name, coll, mat):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.normal_update()
        back, belly = np.array(_rgb(COL["back"])), np.array(_rgb(COL["belly"]))
        rgba = []
        for v, c in zip(bm.verts, self.C):
            if c is None:
                k = float(smoothstep(0.15, -0.55, v.normal.z))
                c = back * (1 - k) + belly * k
            rgba += [c[0], c[1], c[2], 1.0]
        ob = mesh_obj(name, bm, coll)
        me = ob.data
        for a in list(me.color_attributes):
            me.color_attributes.remove(a)
        att = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
        att.data.foreach_set('color', rgba)
        me.materials.clear()
        me.materials.append(mat)
        me.shade_smooth()
        ob.vertex_groups.clear()
        groups = {}
        for i, w in enumerate(self.W):
            for bone, x in w.items():
                g = groups.get(bone) or ob.vertex_groups.new(name=bone)
                groups[bone] = g
                g.add([i], x, 'REPLACE')
        return ob


def blockout_material():
    m = bpy.data.materials.get("M_DRG_Blockout") or bpy.data.materials.new("M_DRG_Blockout")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    att = next((n for n in nt.nodes if n.type == 'ATTRIBUTE'), None) or nt.nodes.new('ShaderNodeAttribute')
    att.attribute_name = "Col"
    att.location = (bsdf.location.x - 260, bsdf.location.y)
    nt.links.new(att.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
    m.use_backface_culling = False
    m.diffuse_color = (*_rgb(COL["back"]), 1)
    return m


# ----------------------------------------------------------------------------------------- pieces
def _seg(bm, a, b, ra, rb, rmid=None, up=LEG_UP, cap=0.8):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rmid = rmid if rmid is not None else (ra + rb) / 2
    rows = [(*a, ra, ra, ra), (*((a + b) / 2), rmid, rmid, rmid), (*b, rb, rb, rb)]
    return loft(bm, rows, up=up, seg=12, per_seg=3, cap0=cap, cap1=cap)


def _tube(bm, rows, up=UP, seg=10, cap0=0.0, cap1=0.5):
    rows = [(x, y, z, r, r, r) for x, y, z, r in rows]
    return loft(bm, rows, up=up, seg=seg, per_seg=3, cap0=cap0, cap1=cap1)


def _claw(bm, base, d, L, r):
    base, d = np.asarray(base, float), np.asarray(d, float)
    d /= np.linalg.norm(d)
    return cone(bm, base, base + d * L, r, seg=6, bend=tuple(np.array((0, 0, -1.0)) * L * 0.35))


def build_blockout(rig, old_head=False, frill_fused=None):
    """The blockout meshes, skinned and bound to the rig: DragonBlockout (body, head, legs, wing bones) and
    DragonMembrane. The face is dragon_head's (old_head=True brings back the first blockout's lofted head; the horns
    and the crown spikes are kept either way). -> (objects, report)"""
    B = rest_bones()
    coll = get_coll(COLL)
    mat = blockout_material()
    body, mem = Acc(), Acc()
    horn, claw, eye = _rgb(COL["horn"]), _rgb(COL["claw"]), _rgb(COL["eye"])

    # neck, trunk and tail: one loft, chain weights
    chain = [f"Neck{i + 1}" for i in range(NECK_N)] + ["Head", "Chest", "Spine2", "Spine1", "Hips"] + \
            [f"Tail{i + 1}" for i in range(TAIL_N)]
    chain_b = _bones_of(B, chain)
    body.add(lambda bm: loft(bm, BODY_ROWS, seg=24, per_seg=6, cap0=0.6, cap1=0.8),
             lambda P: chain_weights(P, chain_b), _belly)

    # dorsal spikes, head to tail tip; each rides with the chain at its base
    R = spline(BODY_ROWS, 16)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(R[:, :3], axis=0), axis=1))])
    for at in np.arange(0.45, s[-1] - 0.3, 0.34):
        i = int(np.searchsorted(s, at))
        p, row = R[i, :3], R[i]
        T = R[min(i + 1, len(R) - 1), :3] - R[max(i - 1, 0), :3]
        T /= np.linalg.norm(T)
        N = np.array(UP) - np.dot(UP, T) * T
        N /= np.linalg.norm(N)
        f = at / s[-1]
        h = float(np.interp(f, (0.0, 0.18, 0.27, 0.42, 0.55, 1.0), (0.16, 0.26, 0.40, 0.30, 0.28, 0.07)))
        base = p + N * row[4] * 0.85
        tip = base + (N * 0.85 + T * 0.55) / np.linalg.norm(N * 0.85 + T * 0.55) * h
        w = chain_weights(base[None], chain_b)[0]
        body.add(lambda bm, b=base, t=tip, h=h: cone(bm, b, t, h * 0.32, seg=4), lambda P, w=w: [w] * len(P), horn)

    # head
    back = _rgb(COL["back"])
    rep_head = {}
    if old_head:
        body.add(lambda bm: loft(bm, hk_rows(SKULL_ROWS), seg=20, per_seg=4, cap0=0.8, cap1=0.5), "Head", back)
        body.add(lambda bm: loft(bm, hk_rows(JAW_ROWS), seg=16, per_seg=4, cap0=0.8, cap1=0.5), "Jaw", _belly_jaw)
    else:
        import dragon_head
        rep_head = dragon_head.build(body, _rgb, frill_fused=frill_fused)
    for s_, sfx in SIDES:
        m = lambda p: _m(p, s_)
        K = HEAD_K
        body.add(lambda bm: _tube(bm, [(*m(hk(p)), p[3] * K) for p in HORN], seg=10), "Head", horn)
        if old_head:                                     # (the new head melts the crown spikes in)
            for a, b, r0 in CROWN:
                body.add(lambda bm: cone(bm, m(hk(a)), m(hk(b)), r0 * K, seg=6), "Head", horn)
            c, r = EYE
            body.add(lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r * K,
                                                          matrix=Matrix.Translation(m(hk(c)))) and None, "Head", eye)
            a, b, r = BROW
            body.add(lambda bm: _seg(bm, m(hk(a)), m(hk(b)), r * K, r * K * 0.7, up=UP, cap=0.8), "Head", back)
            for a, b, r0 in JAW_SPIKES:
                body.add(lambda bm: cone(bm, m(hk(a)), m(hk(b)), r0 * K, seg=5), "Jaw", horn)
            for a, b, r0 in FANGS:
                body.add(lambda bm: cone(bm, m(hk(a)), m(hk(b)), r0 * K, seg=5), "Head", _rgb("e8dcc0"))
            fb, tips = hk(FRILL[0]), [hk(t) for t in FRILL[1]]
            for t in tips:
                body.add(lambda bm: cone(bm, m(fb), m(t), 0.035 * K, seg=5), "Head", horn)

            def frill(bm):
                vb = bm.verts.new(m(fb))
                vt = [bm.verts.new(m(t)) for t in tips]
                for a, b in zip(vt[:-1], vt[1:]):
                    bm.faces.new((vb, a, b))
            mem.add(frill, "Head", _rgb(COL["membrane"]))

        # legs: rigid segments per bone, toes with claws
        F, H = FRONT, HIND
        segs = ((f"Scapula{sfx}", (0.62, -1.10, 2.15), F["sho"], 0.36, 0.42, 0.42),
                (f"UpperArm{sfx}", F["sho"], F["elb"], 0.42, 0.26, 0.38),
                (f"Forearm{sfx}", F["elb"], F["wri"], 0.26, 0.18, 0.23),
                (f"FrontPaw{sfx}", F["wri"], F["paw"], 0.18, 0.19, 0.19),
                (f"Thigh{sfx}", (0.70, 1.30, 2.20), H["hip"], 0.48, 0.56, 0.55),
                (f"Thigh{sfx}", H["hip"], H["knee"], 0.56, 0.30, 0.50),
                (f"Shin{sfx}", H["knee"], H["hock"], 0.30, 0.17, 0.25),
                (f"HindFoot{sfx}", H["hock"], H["paw"], 0.17, 0.18, 0.16))
        for bone, a, b, ra, rb, rm in segs:
            body.add(lambda bm: _seg(bm, m(a), m(b), ra, rb, rm), bone, back)
        for toes, paw, spread, L, r in ((f"FrontToes{sfx}", F["paw"], (-26, -9, 9, 26), 0.42, 0.075),
                                        (f"HindToes{sfx}", H["paw"], (-24, -8, 8, 24), 0.46, 0.08)):
            for k, ang in enumerate(spread):
                a = math.radians(ang)
                d = np.array((math.sin(a) * s_, -math.cos(a), -0.12))
                base = np.array(m(paw)) + np.array((s_ * 0.05 * (k - 1.5), -0.04, -0.02))
                tip = base + d * L
                tip[2] = max(tip[2], r)
                body.add(lambda bm: _seg(bm, base, tip, r * 1.1, r * 0.8, up=UP, cap=0.6), toes, back)
                body.add(lambda bm: _claw(bm, tip, d, 0.20, r * 0.6), toes, claw)

        # wing arm, thumb and fingers: rigid segments
        W = WING
        for bone, a, b, ra, rb in ((f"WingScap{sfx}", W["root"], W["sho"], 0.22, 0.22),
                                   (f"WingArm{sfx}", W["sho"], W["elb"], 0.22, 0.15),
                                   (f"WingForearm{sfx}", W["elb"], W["wri"], 0.15, 0.12),
                                   (f"WingHand{sfx}", W["wri"], W["knu"], 0.12, 0.10),
                                   (f"WingThumb{sfx}", W["wri"], W["thumb"], 0.08, 0.05)):
            body.add(lambda bm: _seg(bm, m(a), m(b), ra, rb, up=UP), bone, back)
        th = np.array(W["thumb"]) - np.array(W["wri"])
        body.add(lambda bm: _claw(bm, m(W["thumb"]), _m(th, s_), 0.22, 0.05), f"WingThumb{sfx}", claw)
        for i in range(4):
            P = finger_pts(i)
            r = np.linspace(0.07, 0.025, len(P))
            for k in range(len(P) - 1):
                body.add(lambda bm: _seg(bm, m(P[k]), m(P[k + 1]), r[k], r[k + 1], up=UP, cap=0.5),
                         f"WingF{i + 1}_{k + 1}{sfx}", back)

        build_membranes(mem, B, s_, sfx)

    ob_body = body.finish("DragonBlockout", coll, mat)
    mem.C = [c if c is not None else _rgb(COL["membrane"]) for c in mem.C]
    ob_mem = mem.finish("DragonMembrane", coll, mat)
    import beast_rig
    rep = {o.name: beast_rig.bind(o, rig) for o in (ob_body, ob_mem)}
    rep["tris"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (ob_body, ob_mem)}
    rep["head"] = rep_head
    return (ob_body, ob_mem), rep


# The arm + flank membrane (arm, flank, the last finger and the trailing edge between them) is not skinned to those
# bones directly: in the fold the arm turns ~150 degrees from the flank, and blending the two swung the middle of the
# panel out from the side like a saddlebag (Daniel: "Something is wrong with the folded wing, it has a bad
# geometry"). Instead a grid of helper bones (WingMem<i><j>) sits on the Coons surface spanned by the panel's edges
# as they are posed (membrane_pose, every frame of every clip), and the panel's inside is weighted to them.
NU_ARM, NV_ARM = 15, 10
MEM_I = (3, 6, 9, 12)            # helper bones at these grid columns (along the arm) ...
MEM_J = (3, 6, 9)                # ... and rows (arm -> trailing edge; 9 = on the trailing edge itself)
_PANEL = {}


def arm_panel(B, s_, sfx, ws=None):
    """The arm + flank membrane's edges (rest): bottom = shoulder, elbow, wrist, knuckle; top = the trailing edge
    from the flank to the last finger's tip; left = the flank; right = the last finger. Each (P, weights)."""
    ws = ws or DRAGON_WING
    m = lambda p: _m(p, s_)
    W = ws.wing
    sh, el, wr, kn, att = (np.array(m(W[k])) for k in ("sho", "elb", "wri", "knu", "att"))
    last = len(ws.segs) - 1
    f4 = np.array([m(p) for p in finger_pts(last, ws)])
    fb4 = [f"WingF{last + 1}_{k + 1}{sfx}" for k in range(ws.segs[last])]
    trunk = _bones_of(B, list(ws.trunk))
    nu, nv = ws.nu, ws.nv
    bottom = polyline([sh, el, wr, kn], [f"WingArm{sfx}", f"WingForearm{sfx}", f"WingHand{sfx}"], nu,
                      start=f"WingScap{sfx}")
    topP = _sag(att, f4[-1], el, nu, ws.sag)
    leftP = np.linspace(sh, att, nv)
    skin = body_skin_weights(leftP) if ws.flank is None else None
    if ws.att_w is not None:
        att_w = ws.att_w(B, s_, sfx)
    elif skin is not None:
        att_w = skin[-1]
    else:
        att_w = chain_weights(att[None], trunk)[0]
    top = (topP, [_wmix([(1 - u, att_w), (u, {fb4[-1]: 1.0})]) for u in np.linspace(0, 1, nu)])
    if ws.flank is not None:
        left = ws.flank(B, s_, sfx, nv)
    elif skin is not None:
        left = (leftP, skin)
    else:
        lw = chain_weights(leftP, trunk)
        left = (leftP, [_wmix([(1 - smoothstep(0, 0.35, v), {f"WingScap{sfx}": 1.0}), (smoothstep(0, 0.35, v), w)])
                        for v, w in zip(np.linspace(0, 1, nv), lw)])
    right = polyline(f4, fb4, nv, start=f"WingHand{sfx}")
    return bottom, top, left, right


def body_skin_weights(P, ob_name="DragonBody", limit=4):
    """The body skin's own weights at the surface points nearest P (rest, object space: its polygon's vertex weights
    blended by poly_3d_calc, the strongest `limit` kept), so the membrane's flank edge moves with the flank instead of
    its own trunk chain (Daniel 2026-10-24: "where the membrane touches the dragon body, there is a gap": up to 14 cm in
    Fly / Glide / Takeoff). None while the body has no weights yet (the first build; membrane_helpers re-weights)."""
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc
    ob = bpy.data.objects.get(ob_name)
    if ob is None or not ob.vertex_groups:
        return None
    me = ob.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    names = {g.index: g.name for g in ob.vertex_groups}
    out = []
    for p in P:
        loc, _, fi, _ = bvh.find_nearest(Vector(p))
        if fi is None:
            return None
        vs = list(me.polygons[fi].vertices)
        bary = poly_3d_calc([me.vertices[i].co for i in vs], loc)
        w = {}
        for i, b in zip(vs, bary):
            for g in me.vertices[i].groups:
                w[names[g.group]] = w.get(names[g.group], 0.0) + b * g.weight
        top = sorted(w.items(), key=lambda kv: -kv[1])[:limit]
        s = sum(x for _, x in top) or 1.0
        out.append({n: x / s for n, x in top if x > 1e-4})
    return out


def coons_P(Pb, Pt, Pl, Pr):
    """Coons surface positions only (see coons). -> (nu, nv, 3)"""
    nu, nv = len(Pb), len(Pl)
    u = np.linspace(0, 1, nu)[:, None, None]
    v = np.linspace(0, 1, nv)[None, :, None]
    return ((1 - v) * Pb[:, None] + v * Pt[:, None] + (1 - u) * Pl[None] + u * Pr[None]
            - ((1 - u) * (1 - v) * Pb[0] + u * (1 - v) * Pb[-1] + (1 - u) * v * Pt[0] + u * v * Pt[-1]))


def _mem_frames(P, sfx, ws=None):
    """Helper bone frames on a Coons grid P: at each (MEM_I, MEM_J) node, +Y along the arm, +Z the surface normal."""
    ws = ws or DRAGON_WING
    out = {}
    for a, i in enumerate(ws.mem_i):
        for b, j in enumerate(ws.mem_j):
            du = P[i + 1, j] - P[i - 1, j]
            dv = P[i, min(j + 1, len(P[0]) - 1)] - P[i, j - 1]
            out[f"WingMem{a + 1}{b + 1}{sfx}"] = (P[i, j], _frame(du, np.cross(du, dv)))
    return out


def _mem_weights(W, sfx, ws=None):
    """The arm panel's weights: its edges keep their own; inside, bilinear over a lattice of nodes, the edge nodes
    carrying the edge weights there and the inner ones a helper bone each."""
    ws = ws or DRAGON_WING
    nu, nv = len(W), len(W[0])
    I = [0, *ws.mem_i, nu - 1]
    J = [0, *ws.mem_j] + ([nv - 1] if ws.mem_j[-1] != nv - 1 else [])
    top_helpers = ws.mem_j[-1] == nv - 1              # the trailing edge rides on helpers too

    def node(a, b):
        i, j = I[a], J[b]
        if a in (0, len(I) - 1) or b == 0 or (b == len(J) - 1 and not top_helpers):
            return W[i][j]
        return {f"WingMem{a}{b}{sfx}": 1.0}
    out = [[None] * nv for _ in range(nu)]
    for i in range(nu):
        for j in range(nv):
            if i in (0, nu - 1) or j == 0 or (j == nv - 1 and not top_helpers):
                out[i][j] = W[i][j]
                continue
            if j == nv - 1:                         # on the trailing edge: along it, between its helpers
                a = max(k for k in range(len(I) - 1) if I[k] <= i)
                s = (i - I[a]) / (I[a + 1] - I[a])
                out[i][j] = _wmix([(1 - s, node(a, len(J) - 1)), (s, node(a + 1, len(J) - 1))])
                continue
            a = max(k for k in range(len(I) - 1) if I[k] <= i)
            b = max(k for k in range(len(J) - 1) if J[k] <= j)
            s = (i - I[a]) / (I[a + 1] - I[a])
            t = (j - J[b]) / (J[b + 1] - J[b])
            out[i][j] = _wmix([((1 - s) * (1 - t), node(a, b)), (s * (1 - t), node(a + 1, b)),
                               ((1 - s) * t, node(a, b + 1)), (s * t, node(a + 1, b + 1))])
    return out


def membrane_pose(Wm, R, ws=None):
    """Add the arm panels' helper bones to a pose. Wm: armature-space matrices of (at least) the trunk, wing and
    finger bones; R: rest matrices. The panel's edges ride on their bones -- except the trailing edge, which spans
    its posed ends with its rest sag (blending trunk and finger there swung it out too) -- and the helpers sit on the
    Coons surface between them."""
    ws = ws or DRAGON_WING
    cache = _PANEL if ws is DRAGON_WING else ws.panel
    for s_, sfx in SIDES:
        if sfx not in cache:
            cache[sfx] = arm_panel(ws.bones(), s_, sfx, ws)
        bottom, top, left, right = cache[sfx]

        def lbs(P, Ws):
            out = np.zeros((len(P), 3))
            for k, (p, w) in enumerate(zip(P, Ws)):
                v = Vector(p)
                acc = Vector()
                for n, wt in w.items():
                    acc += float(wt) * ((Wm[n] @ R[n].inverted()) @ v)
                out[k] = acc
            return out
        Pb, Pl, Pr = lbs(*bottom), lbs(*left), lbs(*right)
        el = np.array(Wm[f"WingForearm{sfx}"].translation)
        Pt = _sag(Pl[-1], Pr[-1], el, len(Pb), ws.sag)
        P = coons_P(Pb, Pt, Pl, Pr)
        for n, (h, fr) in _mem_frames(P, sfx, ws).items():
            Wm[n] = Matrix.Translation(Vector(h)) @ fr.to_4x4()
    return Wm


_REST = {}


def rest_bones_cached():
    if not _REST:
        _REST.update(rest_bones())
    return _REST


DRAGON_WING = WingSpec()


def build_membranes(mem, B, s_, sfx, ws=None, n_finger=12, n_tip=6, n_lead=10):
    """One wing's membranes into an Acc: Coons patches whose boundaries run along the bones' joints, so a patch edge
    rides on its bone; the arm panel's inside rides on its helper bones (arm_panel, membrane_pose). n_finger,
    n_tip, n_lead: the finger panels' rows along and across, the leading edge's rows (the dragon's 12, 6, 10)."""
    ws = ws or DRAGON_WING
    m = lambda p: _m(p, s_)
    W = ws.wing
    nf = len(ws.segs)
    sh, el, wr, kn = (np.array(m(W[k])) for k in ("sho", "elb", "wri", "knu"))
    fingers = [np.array([m(p) for p in finger_pts(i, ws)]) for i in range(nf)]
    fbones = [[f"WingF{i + 1}_{k + 1}{sfx}" for k in range(ws.segs[i])] for i in range(nf)]
    tips_ = [f[-1] for f in fingers]
    last = [fb_[-1] for fb_ in fbones]
    arm_bones = [f"WingArm{sfx}", f"WingForearm{sfx}", f"WingHand{sfx}"]

    # arm + flank membrane: arm (bottom), trailing edge flank -> F4 tip (top), flank (left), F4 (right)
    P, Wc = coons(*arm_panel(B, s_, sfx, ws))
    Wc = _mem_weights(Wc, sfx, ws)
    mem.add(lambda bm: _patch(bm, P, Wc))
    # between the fingers: finger i (bottom), finger i+1 (top), the knuckle (left), trailing edge (right)
    for i in range(nf - 1):
        fb0 = polyline(fingers[i], fbones[i], n_finger, start=f"WingHand{sfx}")
        fb1 = polyline(fingers[i + 1], fbones[i + 1], n_finger, start=f"WingHand{sfx}")
        leftK = (np.repeat(kn[None], n_tip, axis=0), [{f"WingHand{sfx}": 1.0}] * n_tip)
        te = _sag(tips_[i], tips_[i + 1], kn, n_tip, ws.finger_sag)
        rightT = (te, [{last[i]: 1 - v, last[i + 1]: v} for v in np.linspace(0, 1, n_tip)])
        mem.add(lambda bm: _patch(bm, *coons(fb0, fb1, leftK, rightT), weld_u0=True))
    # leading edge: shoulder -> elbow -> wrist (bottom), the straight shoulder -> wrist line pushed forward (top)
    armP = polyline([sh, el, wr], arm_bones[:2], n_lead, start=f"WingScap{sfx}", end=f"WingHand{sfx}")
    lead = (np.linspace(sh, wr, n_lead) + np.array(ws.lead) * np.array((s_, 1, 1)) *
            np.sin(np.linspace(0, math.pi, n_lead))[:, None])
    topL = (lead, armP[1])
    mem.add(lambda bm: _patch(bm, *coons(armP, topL, (np.array([sh, sh, sh]), [armP[1][0]] * 3),
                                         (np.array([wr, wr, wr]), [armP[1][-1]] * 3)), weld_u0=True, weld_u1=True))


def _ventral(P, rows, per_seg=12):
    """How far each point sits on the underside of a loft through `rows` (1 = straight down its ventral axis -N)."""
    R = spline(rows, per_seg)
    C = R[:, :3]
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.array(UP) - (T @ np.array(UP))[:, None] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    i = np.argmin(((P[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
    d = P - C[i]
    d /= np.maximum(np.linalg.norm(d, axis=1), 1e-6)[:, None]
    return -(d * N[i]).sum(1)


def _mix_belly(k):
    back, belly = np.array(_rgb(COL["back"])), np.array(_rgb(COL["belly"]))
    return [tuple(back * (1 - x) + belly * x) for x in k]


def _belly(P):
    """The golden belly plates: throat, chest, belly and the underside of the tail."""
    return _mix_belly(smoothstep(0.35, 0.75, _ventral(P, BODY_ROWS)))


def _belly_jaw(P):
    return _mix_belly(smoothstep(0.2, 0.6, _ventral(P, hk_rows(JAW_ROWS), 4)))


def _patch(bm, P, W, weld_u0=False, weld_u1=False):
    """Grid faces over P (nu, nv, 3). weld_u0 / weld_u1: that end column is one point (the knuckle, the shoulder):
    one vertex, a fan of triangles. -> weights in vertex creation order."""
    nu, nv = P.shape[:2]
    V = [[None] * nv for _ in range(nu)]
    out = []
    for i in range(nu):
        for j in range(nv):
            if j > 0 and ((weld_u0 and i == 0) or (weld_u1 and i == nu - 1)):
                V[i][j] = V[i][0]
                continue
            V[i][j] = bm.verts.new(Vector(P[i, j]))
            out.append(W[i][j])
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            u = []
            for v in q:
                if v not in u:
                    u.append(v)
            if len(u) >= 3:
                bm.faces.new(u)
    return out


# ----------------------------------------------------------------------------------------- scale reference
def scale_man(coll):
    """A 1.8 m capsule in front of the snout, for scale (not exported)."""
    remove_obj("DRG_ScaleMan")
    bm = bmesh.new()
    loft(bm, [(0, 0, 0.25, 0.22, 0.22, 0.22), (0, 0, 0.9, 0.25, 0.25, 0.25), (0, 0, 1.55, 0.22, 0.22, 0.22)],
         up=(0, -1, 0), seg=12, per_seg=3, cap0=1.0, cap1=1.0)
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.13,
                              matrix=Matrix.Translation((0, 0, 1.67)))
    ob = mesh_obj("DRG_ScaleMan", bm, coll)
    ob.location = (1.2, -5.6, 0)
    m = bpy.data.materials.get("M_DRG_ScaleMan") or bpy.data.materials.new("M_DRG_ScaleMan")
    m.use_nodes = True
    next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value = (0.35, 0.40, 0.48, 1)
    m.diffuse_color = (0.35, 0.40, 0.48, 1)
    ob.data.materials.clear()
    ob.data.materials.append(m)
    ob.hide_select = True
    return ob
