"""Golden eagle (2026-10-24, Daniel: "You know, one of the models we need is an eagle or a falcon, can you model us
one of those? Dont use the chicken as base, that model is bad"): body, feather cards, skeleton and skinning. Facing
-Y, left side +X, metres, Z up (beast_common). Its own body: nothing comes from the hen (chicken_*); the dragon's
mesh accumulator (dragon_body.Acc: per-vertex weights), lofts and bone frames, the beasts' fuse/heat/skin pipeline.

My calls (Daniel gave no more detail): a golden eagle (Aquila chrysaetos) at natural size: 0.85 m beak to tail tip,
2.1 m across the wings, about 0.6 m tall perched; a big hooked beak (dark tip, pale-grey base, yellow cere), a heavy
brow over amber eyes, a broad flat head with golden nape hackles, a deep chest, feathered "trousers" and a feathered
tarsus, bare yellow toes (three forward, one back) with big curved black talons; a long broad wing whose outer six
primaries end in slotted fingers; a fan tail of twelve feathers.

Bind pose: the flight posture standing on its feet -- the body level, the wings spread with the fingers open, the tail
closed. The feathers are laid out where their outline matters (the open wing from above), nothing overlaps in the
bind (clean UVs, bakes and AO), and the feet are modelled open; perched (wings folded) and spread (flying) are poses
(eagle_pose), as the bat's and the dragon's wings are.

What is a mesh and what is a card:
- one fused body (beast_body.fuse_body): trunk (a boxy section), neck, head with the brow shelf, forehead, nape,
  shoulders, scapulars and flanks (the folded wing lies against them), the trousers;
- separate pieces (dragon_body.Acc, each vertex with its own weights): the hooked upper beak with its cere (Head), the
  lower mandible (Jaw), the eyes (Head), the feathered tarsus and the toes (chain weights), the talons, the wing's
  flesh as two airfoil slabs (rigid on WingArm -- it carries the patagium's fill -- and WingForearm; the coverts are
  painted on them). No hand slab: folded, the primaries run along the hand and went through it;
- feather cards (open strips of three vertices across: leading edge, shaft, trailing edge; a slight V section and a
  slight ventral curve): 10 primaries (the outer six emarginated into fingers), 12 secondaries, 4 tertials, 12 greater
  coverts and 9 primary coverts per wing, 2 alula feathers, 4 scapulars a side, 12 tail feathers. Each card is rigid
  on its own bone (primaries, primary coverts, alula, scapulars, tail) or rides two bones with a weight fixed per card
  (secondaries and greater
  coverts on WingSecA/B, children of the forearm; the tertials on WingTertA/B, children of the humerus, turned
  alike, since 2026-10-24): two bones turned the same way
  about their own heads move every card between them rigidly about its own root (linear blend skinning of two equal
  rotations is a rotation), which is what a folding forearm does to its feathers.

Layers: in the open wing the proximal feather lies over the distal one (S12 over S1 over P1 over P10), the coverts on
top; folded, that order becomes inside -> outside. Each row steps up DL per feather; the rows sit at fixed heights over
the bones (see feathers()). The right side is the left mirrored.

Revision 2026-10-24 (Daniel: "Yes, fix them" -- the review list -- and "the head looks like a vulture structure, needs
a pass too"):
- the head: short, broad and flat-topped (HEAD, a boxy loft), a brow shelf over each eye (outer edge and front end
  down, the front turned in: the frown), an eyeball in a sculpted socket under it looking forward-out, a short thick
  neck with a hackle ruff at the nape; the beak built from its side profile (BEAK_UP, BEAK_LOW: the culmen in one
  arc from the cere to the hook, 2.9 cm deep at the cere, the cutting edge back to below the eye's front), its own
  (h, t) coordinates in 'root' for the painter;
- the spread wing: the primaries' tips on a broad, near-rectangular outline, six short fingers 5-7 deg apart; the
  secondaries 0.33-0.40 m (a ~0.44 m chord), fanned 72-97 deg so the trailing edge runs on into the hand's;
- the cards' tips blunt and rounded (CHEV, the rows' last width), not blunt chevrons; 12 narrower greater coverts
  with a third row;
- the scapulars: four cards a side on a Scap bone (rolled out over the folded wing's top edge);
- the legs: a 9.2 cm tarsus with a feathered sock over a slimmer lower half, fuller trousers past the ankle;
- the feather sculpt mirrored (_fur), so both sides clear the cards alike.

Hinged cards (2026-10-24, Daniel: "The feathers are all quads, what if each individual feather could be folded in 2
places, so we make things fit. Yes, much more polygons, we would go over budget, but that is how real feathers work"):
the folded wing creases along two lines across it (eagle_drape.CREASES) and every card that crosses a crease gets a
hinge row where its shaft crosses it (HINGE_T, filled by the build from the folded pose); folded, the wing beyond each
crease turns in toward the body as one piece (eagle_drape: the shape keys FoldL / FoldR, driven by the unweighted gauge
bones WingFoldL / WingFoldR that slide with the wing's lay).
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, smoothstep
import beast_body, beast_rig
from beast_body import PART, ellipsoid, _write_info
import dragon_body as DB

NAME, PREFIX = "Eagle", "EGL"
RIG = "EagleRig"
BODY = "EagleBody"
VOXEL, BODY_TRIS = 0.0035, 2000
UP, FWD = (0, 0, 1), (0, -1, 0)
SIDES = ((1, "L"), (-1, "R"))


def _n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _mv(v, s):
    return np.array((s * v[0], v[1], v[2]), float)


# ----------------------------------------------------------------------------------------- landmarks (left side)
# 2026-10-24 revision (Daniel: "the head looks like a vulture structure, needs a pass too"): a short, broad head on a
# short, thick neck (poll -> beak tip 12.5 cm, was 14.2), the jaw hinged at the gape's corner; a 9.2 cm tarsus (was
# 10.4) under a longer shin, so the leg's reach and the perched height stay
J = dict(PELVIS=(0, 0.050, 0.345), RUMP=(0, 0.120, 0.348), CHEST=(0, -0.070, 0.352), NECK=(0, -0.200, 0.364),
         N1=(0, -0.222, 0.374), N2=(0, -0.243, 0.384), POLL=(0, -0.262, 0.394), BEAK=(0, -0.386, 0.378),
         HINGE=(0, -0.314, 0.383), CHIN=(0, -0.373, 0.380), TAIL0=(0, 0.118, 0.350), TAIL1=(0, 0.165, 0.351),
         HIP=(0.045, 0.040, 0.318), KNEE=(0.072, -0.040, 0.258), ANKLE=(0.080, 0.028, 0.110),
         BALL=(0.073, -0.016, 0.030))
TOES = {  # base (inside the foot), joint, tip; 1 the hallux (back), 2 inner, 3 middle, 4 outer
    1: ((0.072, -0.004, 0.024), (0.070, 0.016, 0.0135), (0.068, 0.038, 0.0105)),
    2: ((0.066, -0.024, 0.024), (0.057, -0.048, 0.0135), (0.047, -0.073, 0.0105)),
    3: ((0.074, -0.028, 0.024), (0.076, -0.056, 0.0135), (0.078, -0.088, 0.0105)),
    4: ((0.081, -0.022, 0.024), (0.095, -0.042, 0.0135), (0.108, -0.063, 0.0105)),
}
TALON = {1: 0.044, 2: 0.038, 3: 0.032, 4: 0.027}
TARSUS_SOCK = 0.44                 # the feathered sock's end down the tarsus (ankle 0 .. ball 1)
TOE_R = (0.0098, 0.0090, 0.0076)

# the wing in the bind pose (spread): shoulder, elbow, wrist, the hand's end (knuckle); a 6 deg dihedral
DIHEDRAL = 6.0
WING = dict(S=(0.062, -0.150, 0.385), E=(0.228, -0.100, 0.400), W=(0.448, -0.182, 0.420), K=(0.598, -0.160, 0.432))
WN = _n((-math.sin(math.radians(DIHEDRAL)), 0.0, math.cos(math.radians(DIHEDRAL))))      # the wing's dorsal normal
WX = _n((math.cos(math.radians(DIHEDRAL)), 0.0, math.sin(math.radians(DIHEDRAL))))       # outward in its plane
WY = np.array((0.0, 1.0, 0.0))                                                           # backward in its plane
DL = 0.0011                         # one feather layer

# feather tables (left wing): angle in the wing plane from outward (+X) toward the back (+Y), length, full width,
# the leading (outer) vane's share of the width
# 2026-10-24 (the spread wing read as a hand or a comb from above): a broad, near-rectangular wing. The primaries'
# tips are laid on the outline -- the trailing edge running on from the secondaries' to the fingers, the tip blunt --
# and the six fingers (P5-P10) step 6-8 deg apart, separated only over their outer third or so
P_ANG = (62.0, 54.7, 47.5, 39.9, 32.4, 25.9, 19.8, 14.1, 9.0, 4.3)   # P1 (at the wrist) .. P10 (the leading edge)
P_LEN = (0.400, 0.402, 0.408, 0.418, 0.432, 0.444, 0.455, 0.457, 0.442, 0.402)
P_WID = (0.090, 0.090, 0.090, 0.088, 0.086, 0.082, 0.077, 0.071, 0.064, 0.054)
P_EMARG = {5: (0.66, 0.50), 6: (0.64, 0.48), 7: (0.62, 0.48), 8: (0.61, 0.48), 9: (0.60, 0.50), 10: (0.58, 0.56)}
S_N = 12
S_ANG = tuple(np.linspace(72, 97, S_N))       # S1 (at the wrist, angled out to meet P1) .. S12 (at the elbow)
S_LEN = (0.390, 0.392, 0.394, 0.396, 0.397, 0.397, 0.395, 0.390, 0.380, 0.367, 0.350, 0.330)   # chord ~0.44 m
# The tertials (2026-10-24, Daniel: the arm, "the thing after the shoulders", was a bare rod; "The feathers that should
# be there already exists, but they are 'glued' in a fan position from the feathers of the 'forearm'"): they were rooted
# by the elbow, fanned on from the secondaries and carried by the forearm. Now six, spread along the humerus from the
# elbow toward the shoulder and pointing back, on a two-bone row riding the humerus (WingTertA at T3: T1-T3 rigid on
# it; WingTertB at T6, its child, turned alike: in flight the six are one rigid piece): a bending elbow leaves them on
# the arm; folded, eagle_pose.FOLD_CARRY lays them in the stack where the forearm carried them, and FOLD_SLIDE slides
# the row's T6 end down and back in the cards' plane, so T4-T6 shingle back along the stack (spread up as they are
# along the arm, they stood up out of the folded wing as a fin over the scapulars, Daniel's "boxy", 2026-10-24). The
# row's A end at T3 as the single bone before it (at T1, the stoop swung T6 in over the back). TERT_GAP over S12, which
# the forearm carries and a flex moves under them; toward the shoulder the inner vanes narrow (T_LEAD: the outer vane's
# share) and the cards turn less, so they stay outboard of the shoulder's pivot (inboard of it, a rising wing lowers a
# card onto the back).
T_ANG = (98, 100, 102, 102, 100, 98)
T_LEN = (0.265, 0.245, 0.220, 0.190, 0.160, 0.130)
T_AT = (0.04, 0.18, 0.32, 0.46, 0.60, 0.74)
T_WID = (0.082, 0.082, 0.080, 0.078, 0.075, 0.072)
T_LEAD = (0.45, 0.45, 0.50, 0.55, 0.62, 0.70)
TERT_GAP = 0.003
PC_LEN = (0.130, 0.130, 0.125, 0.120, 0.115, 0.110, 0.100, 0.090, 0.080)
TAIL_X = (0.006, 0.017, 0.028, 0.038, 0.047, 0.055)                   # roots across the tail base, centre -> out
TAIL_LEN = (0.315, 0.313, 0.310, 0.306, 0.300, 0.292)
TAIL_Y, TAIL_Z = 0.142, 0.343

KIND = dict(primary=1, secondary=2, tertial=3, gcovert=4, pcovert=5, alula=6, tail=7, scapular=8)

# the wing's flesh (build_pieces' slabs): rows (t along, lead, trail, top, bottom), shoulder -> elbow and elbow -> wrist
ARM_SLAB = ((0.0, 0.040, 0.022, 0.016, 0.016), (0.55, 0.046, 0.022, 0.014, 0.013), (1.0, 0.048, 0.020, 0.012, 0.010))
FORE_SLAB = ((0.0, 0.040, 0.024, 0.012, 0.007), (0.5, 0.032, 0.020, 0.008, 0.005), (1.0, 0.020, 0.014, 0.005, 0.003))
# 2026-10-24 (Daniel: "the feathers are there, but they don't connect to the arm bone"): the feathers' layers float
# 1-3 cm over the wing's line and the flesh's top is 0.5-1.6 cm, so in flight a strip of light showed between the arm
# and its feathers. The slabs' rear half rises (rows (t, the lift)) so its top takes the feathers' roots, just behind
# the line, 2 mm in (the quills in the flesh, as ROOT_T has them): from below and behind the skin runs up into the
# feathers, and the inner wing is a thick wedge by the body. The tertials over the humerus (2.6-3.2 cm; S12 at the
# elbow passes under T1 into it), the secondaries over the forearm (1.0-2.2); the rear top's own height is ~0.85 of
# the slab's top. (Stopping a few mm under the cards left a slit of light under the roots; lifting only the trailing
# edge left the roots, 8 mm behind the line, over a gap; sinking the cards' roots into the flesh crossed 440 face pairs
# folded: each root dove through the cards under it.) Only in flight: the fold's shape keys take the lift back off
# (eagle_drape; lifted, the flesh stood out of the folded wing's top corners, Daniel's "boxy", 2026-10-24).
ARM_RISE = ((0.0, 0.012), (0.26, 0.0209), (0.54, 0.0196), (0.82, 0.0183), (1.0, 0.0178))
FORE_RISE = ((0.0, 0.0139), (0.5, 0.0112), (1.0, 0.0077))
RISE_FRONT, RISE_BACK = 0.25, 0.35   # the lift grows from this share of the lead in front of the line to this share of
#                                      the trail behind it (all of it behind)

# the hinges (2026-10-24): card name -> the t of its hinge rows, where its shaft crosses the folded wing's creases
# (eagle_drape.crease_hinges; the build fills it before the body is made); an existing row within HINGE_NEAR serves
# instead. Cards that cross no crease stay flat.
HINGE_T = {}
HINGE_NEAR = 0.004
FOLD_GAUGE = 0.1                    # the gauge bone's slide (m) at a full lay; the shape key = slide / FOLD_GAUGE


def with_hinges(rows, hinges):
    """-> (rows with a row at each hinge, the widths interpolated; the hinges' shaft t). A hinge is t, or (t, t_lead,
    t_trail): a row slanted across the card, each edge at its own t (where it crosses a crease); such a row is
    (t, k, (t_lead, k_lead), (t_trail, k_trail)). An existing row within HINGE_NEAR gives way to it (the tip stays)."""
    ts, ks = [r[0] for r in rows], [r[1] for r in rows]
    k_at = lambda t: float(np.interp(t, ts, ks))
    out, used = list(rows), []
    for h in hinges:
        t, tl, tt = (h, h, h) if np.isscalar(h) else h
        row = (t, k_at(t)) if tl == t == tt else (t, k_at(t), (tl, k_at(tl)), (tt, k_at(tt)))
        near = [i for i in range(1, len(out)) if abs(out[i][0] - t) < HINGE_NEAR]
        if near and near[0] == len(out) - 1:
            used.append(out[-1][0])
            continue
        if near:
            out[near[0]] = row
        else:
            i = next(i for i in range(len(out) - 1) if out[i][0] < t < out[i + 1][0])
            out.insert(i + 1, row)
        if len(row) > 2:                               # a plain row the slanted one runs through gives way
            lo, hi = min(t, tl, tt) - HINGE_NEAR, max(t, tl, tt) + HINGE_NEAR
            out = [r for j, r in enumerate(out) if r is row or j in (0, len(out) - 1) or len(r) > 2
                   or not lo <= r[0] <= hi]
        used.append(t)
    edge = lambda r, e: r[e][0] if len(r) > 2 else r[0]
    for i in range(1, len(out) - 1):                   # a slanted row's edges stay between their neighbours'
        r = out[i]
        if len(r) > 2:
            lo = [edge(out[i - 1], e) + 0.003 for e in (2, 3)]
            hi = [edge(out[i + 1], e) - (0.003 if i + 1 < len(out) - 1 else 0.03) for e in (2, 3)]
            tl, tt = (min(max(r[e][0], lo[j]), hi[j]) for j, e in enumerate((2, 3)))
            out[i] = (r[0], r[1], (tl, k_at(tl)), (tt, k_at(tt)))
    return tuple(out), tuple(used)

# the scapulars (2026-10-24: the folded wing stood off the back): mantle feathers rooted along each side of the back,
# lying back over the wing's root. One bone per side (Scap) holds them: in the rest (spread) they lie on the back under
# the tertials; folded (eagle_pose.FOLD_SCAP) it rolls them out and down over the folded wing's top edge
SCAP_ROOT = ((0.040, -0.130, 0.396), (0.046, -0.020, 0.389))   # the root line (left), front -> back
SCAP_ANG = (80.0, 82.5, 85.0, 87.5)                             # from outward toward the back, in their plane
SCAP_LEN = (0.155, 0.165, 0.162, 0.148)
SCAP_W, SCAP_LEAD, SCAP_TILT, SCAP_SLOPE = 0.090, 0.62, 10.0, 3.0  # width, outer vane's share, outward / back slope


def scap_plane():
    """(outward, back, normal) of the scapulars' plane (left): sloping down outward SCAP_TILT and back SCAP_SLOPE."""
    a, b = math.radians(SCAP_TILT), math.radians(SCAP_SLOPE)
    ex = np.array((math.cos(a), 0.0, -math.sin(a)))
    ey = np.array((0.0, math.cos(b), -math.sin(b)))
    ey = _n(ey - (ey @ ex) * ex)
    return ex, ey, _n(np.cross(ex, ey))


class Fe:
    """One feather card (left side): root, direction d and dorsal normal n (after its layer offset and drop),
    length, half widths of the leading / trailing vane, rows ((t, width fraction), ...), curve (ventral drop at the
    tip, fraction of the length), camber (edges below the shaft, fraction of the half width), its bones' weights
    (names without the side suffix)."""

    def __init__(self, name, kind, idx, root, ang, L, width, lead, rows, bones, plane=None, off=0.0, drop=1.0,
                 curve=0.035, camber=0.015, chev=0.45):
        ex, ey, n = plane if plane is not None else (WX, WY, WN)
        a = math.radians(ang)
        d = math.cos(a) * ex + math.sin(a) * ey
        dr = math.radians(drop)                        # the tip drops toward the ventral side
        d2 = d * math.cos(dr) - n * math.sin(dr)
        n2 = n * math.cos(dr) + d * math.sin(dr)
        self.name, self.kind, self.idx = name, kind, idx
        self.root = np.asarray(root, float) + n * off
        self.d, self.n = _n(d2), _n(n2)
        self.L, self.wl, self.wt = L, width * lead, width * (1 - lead)
        rows, self.hinges = with_hinges(rows, HINGE_T.get(name, ()))
        self.rows, self.bones, self.curve, self.camber = rows, bones, curve, camber
        self.off = off
        self.chev = chev                                # how far the tip's edges sit behind the shaft (x half width)

    def geometry(self, s=1):
        """-> (V (n, 3), faces, fc (n, 3): u across (-1 lead edge .. +1 trail edge), v along, id) for side s."""
        d, n = self.d, self.n
        lat = np.cross(d, n)                            # the leading side (left wing)
        V, fc = [], []
        last = len(self.rows) - 1
        for i, row in enumerate(self.rows):
            for u in (-1.0, 0.0, 1.0):
                t, k = row[:2]
                if u != 0.0 and len(row) > 2:           # a crease row: each edge where it crosses the crease
                    t, k = row[2] if u < 0 else row[3]
                w = (self.wl if u < 0 else self.wt) * k * abs(u)
                tt = t
                if i == last and u != 0.0:              # a blunt chevron tip: the edges a little behind the shaft
                    tt = t - self.chev * w / self.L
                c = self.root + d * self.L * tt - n * self.curve * self.L * tt * tt
                p = c - lat * (w if u > 0 else -w) - n * self.camber * w
                V.append(p)
                fc.append((u, tt, KIND[self.kind] + self.idx / 100.0))
        F = []
        for i in range(last):
            a = 3 * i
            F.append((a, a + 3, a + 4, a + 1))
            F.append((a + 1, a + 4, a + 5, a + 2))
        V = np.array(V)
        if s < 0:
            V[:, 0] *= -1
            F = [tuple(reversed(f)) for f in F]
        return V, F, np.array(fc)

    def line(self, t, u):
        """Points (len(t), 3) along the shaft (u 0) or an edge (u -1 lead, +1 trail) at t (no tip chevron)."""
        t = np.asarray(t, float)
        k = np.interp(t, [r[0] for r in self.rows], [r[1] for r in self.rows])
        lat = np.cross(self.d, self.n)
        w = ((self.wl if u < 0 else self.wt) * k * abs(u))[:, None]
        c = self.root + self.d * self.L * t[:, None] - self.n * self.curve * self.L * (t * t)[:, None]
        return c - lat * (w if u > 0 else -w) - self.n * self.camber * w

    def frame(self, s=1):
        """The bone frame of the card (head, tail, z hint) for side s."""
        h = _mv(self.root, s)
        return h, h + _mv(self.d, s) * self.L, _mv(self.n, s)


def _trail(d, n):
    """The trailing side of a bone along d in the wing (left)."""
    return -np.cross(_n(d), n)


# rows (t along, width fraction). The last row is narrowed and its edges drawn back (chev) behind the shaft: a rounded
# tip of three edges, not a blunt chevron (2026-10-24: the stacked trailing edges read as saw teeth)
EMARG_ROWS = lambda te, f: ((0.0, 0.45), (0.16, 1.0), (te, 1.0), (te + 0.08, f), (1.0, f * 0.55))
PLAIN_P = ((0.0, 0.45), (0.16, 1.0), (0.90, 1.0), (1.0, 0.68))
SEC_ROWS = ((0.0, 0.62), (0.90, 1.0), (1.0, 0.70))
GCOV_ROWS = ((0.0, 0.80), (0.86, 1.0), (1.0, 0.70))           # the greater coverts and the scapulars
COV_ROWS = ((0.0, 0.80), (1.0, 0.85))                         # the primary coverts and the alula (mostly hidden)
TAIL_ROWS = ((0.0, 0.50), (0.18, 1.0), (0.92, 1.0), (1.0, 0.72))
CHEV = 0.45                         # broad feathers: a blunt, rounded tip (the fingers taper: 1.0)
G_N = 12
G_ANG = (74.0, 86.0)                # their angles, wrist -> elbow: a narrower fan than the secondaries' (72 -> 97)
# The greater coverts overlap the other way from the remiges (2026-10-24), the distal one over the proximal one, so
# folded each covert's tip shows below the one in front of it: a row of tips, not a stair. All lie over the
# secondaries and tertials (S12 0.022, T4 0.027): G9 at G_OFF, each one toward the wrist a layer higher.
G_OFF = 0.0285


def feathers():
    """Every feather card of the left wing and the left half of the tail, in layer order of their rows."""
    S, E, W, K = (np.array(WING[k], float) for k in "SEWK")
    out = []
    hand, fore, arm = K - W, E - W, S - E
    th, tf, ta = _trail(hand, WN), _trail(-fore, WN), _trail(-arm, WN)
    # one order for both poses (bottom/inside -> top/outside): P10, P9, PC9, P8, PC8 .. P1, PC1, S1..S12, T1..T4,
    # G1..G12, A2, A1. Each primary covert lies half a step over its own primary and under the next one in: folded,
    # every primary rooted nearer the wrist runs back over it (with all the coverts above the primaries they crossed).
    p_off = [-0.008 + 0.0014 * (10 - k) for k in range(1, 11)]      # a wider step: each covert sits in between
    for k in range(1, 11):
        u = 0.03 + 0.94 * (k - 1) / 9
        root = W + hand * u + th * 0.006
        rows = EMARG_ROWS(*P_EMARG[k]) if k in P_EMARG else PLAIN_P
        out.append(Fe(f"P{k}", 'primary', k, root, P_ANG[k - 1], P_LEN[k - 1], P_WID[k - 1], 0.32, rows,
                      {f"WingP{k}": 1.0}, off=p_off[k - 1], drop=0.5, curve=0.008,
                      chev=1.0 if k in P_EMARG else 0.5))
    for k in range(1, 10):
        u = 0.03 + 0.94 * (k - 1) / 9
        root = W + hand * u + np.cross(_n(hand), WN) * 0.008
        out.append(Fe(f"PC{k}", 'pcovert', k, root, P_ANG[k - 1] - 3, PC_LEN[k - 1], 0.060, 0.36, COV_ROWS,
                      {f"WingP{k}": 1.0}, off=p_off[k - 1] + 0.0007, drop=0.5, curve=0.002, camber=0.006,
                      chev=CHEV))
    # secondaries on the forearm (S1 at the wrist, lowest), their greater coverts above them
    s_off = [0.0100 + DL * (i - 1) for i in range(1, S_N + 1)]
    for i in range(1, S_N + 1):
        v = 0.03 + 0.94 * (i - 1) / (S_N - 1)
        root = W + fore * v + tf * 0.008
        out.append(Fe(f"S{i}", 'secondary', i, root, S_ANG[i - 1], S_LEN[i - 1], 0.088, 0.42, SEC_ROWS, None,
                      off=s_off[i - 1], drop=0.7, curve=0.015, chev=CHEV))
    sv = [0.03 + 0.94 * (i - 1) / (S_N - 1) for i in range(1, S_N + 1)]
    for i in range(1, G_N + 1):
        v = 0.03 + 0.94 * (i - 1) / (G_N - 1)
        root = W + fore * v - tf * 0.010
        g_off = float(np.interp(v, sv, s_off)) + 0.0105
        out.append(Fe(f"G{i}", 'gcovert', i, root, float(np.interp(v, (0.0, 1.0), G_ANG)), 0.155, 0.075, 0.36,
                      GCOV_ROWS, None, off=g_off, drop=0.7, curve=0.005, chev=CHEV))
    # the tertials along the humerus, over S12 (TERT_GAP), on WingTertA/B
    for j in range(1, len(T_AT) + 1):
        root = E + arm * T_AT[j - 1] + ta * 0.010
        t_off = s_off[-1] + DL * j + TERT_GAP
        out.append(Fe(f"T{j}", 'tertial', j, root, T_ANG[j - 1], T_LEN[j - 1], T_WID[j - 1], T_LEAD[j - 1], SEC_ROWS,
                      None, off=t_off, drop=0.7, curve=0.015, chev=CHEV))
    # the alula on the wrist's leading edge, on top
    for j, (ang, L) in enumerate(((7, 0.095), (11, 0.075)), 1):     # (2026-10-24) along the hand's leading edge, flat
        root = W + _n(hand) * 0.008 + np.cross(_n(hand), WN) * 0.012
        out.append(Fe(f"A{j}", 'alula', j, root, ang, L, 0.026, 0.30, COV_ROWS, {"WingAlula": 1.0},
                      off=0.014 + DL * (3 - j), drop=1.0, curve=0.005, chev=CHEV))
    # the scapulars, the front one on top (shingled)
    R0, R1 = (np.array(p, float) for p in SCAP_ROOT)
    for j in range(1, len(SCAP_ANG) + 1):
        root = R0 + (R1 - R0) * (j - 1) / (len(SCAP_ANG) - 1)
        out.append(Fe(f"SC{j}", 'scapular', j, root, SCAP_ANG[j - 1], SCAP_LEN[j - 1], SCAP_W, SCAP_LEAD, GCOV_ROWS,
                      {"Scap": 1.0}, plane=scap_plane(), off=DL * (len(SCAP_ANG) - j), drop=0.0, curve=0.012,
                      camber=0.010, chev=CHEV))
    # the tail (closed: the outer feathers toe in under the inner ones), central pair on top
    tail_plane = (np.array((1.0, 0, 0)), np.array((0, 1.0, 0)), np.array((0, 0, 1.0)))
    for k in range(1, 7):
        x = TAIL_X[k - 1]
        L = TAIL_LEN[k - 1]
        ang = 90 + math.degrees(math.atan2(x * 0.65, L))
        lay = 12 - 2 * k                     # 1L 10, 2L 8, ... (the right side gets the odd layers below it)
        out.append(Fe(f"F{k}", 'tail', k, (x, TAIL_Y, TAIL_Z), ang, L, 0.074, 0.40, TAIL_ROWS, {f"TailF{k}": 1.0},
                      plane=tail_plane, off=DL * lay, drop=0.0, curve=0.02, chev=CHEV))
    # the two-bone riders: their weight from the root's place between the two bones' heads
    by = {f.name: f for f in out}
    A, B = by[f"S{S_N}"], by["S1"]
    for f in out:
        if f.kind in ('secondary', 'gcovert'):
            f.bones = _between(f.root, A.root, B.root, "WingSecA", "WingSecB")
        elif f.kind == 'tertial':
            f.bones = _between(f.root, by["T3"].root, by[f"T{len(T_AT)}"].root, "WingTertA", "WingTertB")
    return out


def _between(r, a, b, na, nb):
    ab = b - a
    t = float(np.clip(((r - a) @ ab) / (ab @ ab), 0.0, 1.0))
    return {na: 1.0 - t, nb: t} if 0.0 < t < 1.0 else ({na: 1.0} if t <= 0.0 else {nb: 1.0})


_FE = {}


def fe_table():
    if not _FE:
        _FE.update({f.name: f for f in feathers()})
    return _FE


def side_of(f, s):
    """Tail feathers: the right side's layer is one below the left's mirror (1L 10, 1R 9, 2L 8 ...)."""
    if f.kind == 'tail' and s < 0:
        g = Fe.__new__(Fe)
        g.__dict__.update(f.__dict__)
        g.root = f.root - np.array((0, 0, DL))
        return g
    return f


# ----------------------------------------------------------------------------------------- skeleton
def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform), the beasts' conventions (beast_rig.build_armature)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.20, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.12, None, True)
    b = lambda n, a, t, z, par: DB._bone(B, n, tuple(a), tuple(t), tuple(z), par)
    b("Hips", J['PELVIS'], J['RUMP'], UP, "Root")
    b("Spine1", J['PELVIS'], J['CHEST'], UP, "Hips")
    b("Chest", J['CHEST'], J['NECK'], UP, "Spine1")
    b("Neck1", J['NECK'], J['N1'], UP, "Chest")
    b("Neck2", J['N1'], J['N2'], UP, "Neck1")
    b("Neck3", J['N2'], J['POLL'], UP, "Neck2")
    b("Head", J['POLL'], J['BEAK'], UP, "Neck3")
    b("Jaw", J['HINGE'], J['CHIN'], UP, "Head")
    b("Tail1", J['TAIL0'], J['TAIL1'], UP, "Hips")
    FE = fe_table()
    for s, sfx in SIDES:
        m = lambda p: _mv(p, s)
        b(f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
        b(f"Shin{sfx}", m(J['KNEE']), m(J['ANKLE']), FWD, f"Thigh{sfx}")
        b(f"Tarsus{sfx}", m(J['ANKLE']), m(J['BALL']), FWD, f"Shin{sfx}")
        for i, (base, joint, tip) in TOES.items():
            b(f"Toe{i}_1{sfx}", m(base), m(joint), UP, f"Tarsus{sfx}")
            b(f"Toe{i}_2{sfx}", m(joint), m(tip), UP, f"Toe{i}_1{sfx}")
        Wd = {k: np.array(v, float) for k, v in WING.items()}
        nz = m(WN)
        b(f"WingArm{sfx}", m(Wd['S']), m(Wd['E']), nz, "Chest")
        b(f"WingForearm{sfx}", m(Wd['E']), m(Wd['W']), nz, f"WingArm{sfx}")
        b(f"WingHand{sfx}", m(Wd['W']), m(Wd['K']), nz, f"WingForearm{sfx}")
        h, t, z = FE["A1"].frame(s)
        b(f"WingAlula{sfx}", h, t, z, f"WingHand{sfx}")
        for k in range(1, 11):
            h, t, z = FE[f"P{k}"].frame(s)
            b(f"WingP{k}{sfx}", h, t, z, f"WingHand{sfx}")
        for nm, fe in (("WingSecA", f"S{S_N}"), ("WingSecB", "S1")):
            h, t, z = FE[fe].frame(s)
            b(nm + sfx, h, t, z, f"WingForearm{sfx}")
        h3, t3, z3 = FE["T3"].frame(s)                # the row's two bones turned alike (T3's frame); B rides A, so
        for nm, fe, par in (("WingTertA", "T3", f"WingArm{sfx}"),             # in flight the row is one rigid piece
                            ("WingTertB", f"T{len(T_AT)}", f"WingTertA{sfx}")):
            h = FE[fe].frame(s)[0]
            b(nm + sfx, h, h + (t3 - h3), z3, par)
        for k in range(1, 7):
            h, t, z = side_of(FE[f"F{k}"], s).frame(s)
            b(f"TailF{k}{sfx}", h, t, z, "Tail1")
        ex, ey, nz = scap_plane()
        r0 = np.array(SCAP_ROOT[0], float)
        b(f"Scap{sfx}", m(r0), m(r0 + ey * 0.15), m(nz), "Chest")
        # the fold's gauge (2026-10-24): unweighted, it slides FOLD_GAUGE along its own Y as the wing lays on the
        # flank; the shape key Fold<side> (the hinged cards bent) follows it
        g = m(Wd['S'])
        b(f"WingFold{sfx}", g, g + np.array((0.0, 0.0, 0.04)), FWD, "Chest")
    top = (0, -0.298, 0.430)
    b("Socket_Head", top, (top[0], top[1], top[2] + 0.08), FWD, "Head")
    mouth = (0, -0.372, 0.381)
    b("Socket_Mouth", mouth, (mouth[0], mouth[1], mouth[2] + 0.08), FWD, "Jaw")
    grip = (-0.075, -0.040, 0.012)
    b("Socket_Grip", grip, (grip[0], grip[1], grip[2] + 0.08), FWD, "TarsusR")
    return B


# ----------------------------------------------------------------------------------------- the fused body
TRUNK = [(0, -0.236, 0.370, 0.034, 0.030, 0.034), (0, -0.205, 0.360, 0.058, 0.044, 0.070),
         (0, -0.160, 0.348, 0.080, 0.052, 0.096), (0, -0.095, 0.340, 0.090, 0.054, 0.102),
         (0, -0.025, 0.337, 0.086, 0.050, 0.092), (0, 0.045, 0.340, 0.068, 0.043, 0.072),
         (0, 0.105, 0.345, 0.046, 0.031, 0.046), (0, 0.160, 0.348, 0.030, 0.013, 0.024),
         (0, 0.198, 0.350, 0.017, 0.007, 0.011)]
# the neck: short and thick, fully feathered (2026-10-24; it was a thin 8 cm tube)
NECK = [(0, -0.180, 0.362, 0.056, 0.052, 0.060), (0, -0.214, 0.375, 0.050, 0.047, 0.052),
        (0, -0.244, 0.389, 0.042, 0.040, 0.042)]
# the head (2026-10-24): broad, flat-topped and short, a boxy section (6.8 cm across at the eyes, 13 cm from the
# nape to the beak's tip); the lores taper into the cere
HEAD = [(0, -0.236, 0.392, 0.037, 0.032, 0.034), (0, -0.262, 0.400, 0.037, 0.024, 0.030),
        (0, -0.285, 0.402, 0.036, 0.022, 0.026), (0, -0.306, 0.403, 0.033, 0.020, 0.024),
        (0, -0.322, 0.401, 0.024, 0.015, 0.020), (0, -0.333, 0.398, 0.014, 0.010, 0.013)]
# the trousers (2026-10-24): fuller, down the shin past the ankle, the hem flaring over the tarsus' top
TROUSER = [(0.034, 0.030, 0.322, 0.044, 0.044, 0.044), (0.060, -0.008, 0.268, 0.052, 0.050, 0.050),
           (0.072, 0.010, 0.205, 0.049, 0.047, 0.047), (0.078, 0.021, 0.160, 0.043, 0.041, 0.041),
           (0.081, 0.026, 0.124, 0.038, 0.037, 0.037), (0.082, 0.028, 0.098, 0.037, 0.035, 0.035)]
BLOBS = [  # centre, radii, mirrored, Euler degrees (x, y, z; mirrored with the side)
    ((0, -0.246, 0.398), (0.042, 0.026, 0.026), False, None),        # the nape's hackles, a ruff behind the crown
    ((0.025, -0.316, 0.4165), (0.0155, 0.021, 0.0055), True, (10, 12, -16)),  # the brow shelf over the eye: its
    #                                    outer edge and its front end down, the front end turned in (the frown)
    ((0.020, -0.298, 0.390), (0.014, 0.024, 0.012), True, None),     # the cheeks, down to the gape
    ((0, -0.300, 0.380), (0.021, 0.028, 0.014), False, None),        # throat and chin
    ((0.052, -0.165, 0.380), (0.034, 0.048, 0.030), True, None),     # the shoulders, where the wings come out
    ((0.060, -0.080, 0.364), (0.026, 0.100, 0.018), True, None),     # the back's sides under the scapulars
    ((0.060, -0.060, 0.300), (0.034, 0.110, 0.045), True, None),     # the flanks under the folded wing
    ((0, -0.200, 0.318), (0.050, 0.045, 0.045), False, None),        # the crop / upper breast
    ((0, 0.150, 0.326), (0.030, 0.045, 0.022), False, None),         # undertail coverts
]
# the eye (2026-10-24): an eyeball bulging from a socket under the brow, looking forward-out (binocular)
EYE_C, EYE_N, EYE_R = (0.0285, -0.312, 0.4075), _n((0.70, -0.70, 0.06)), 0.0094
EYE_H, EYE_SINK = 0.0050, 0.0012           # the cap's height; its base below the socket's floor
SOCKET_R, SOCKET_D = 0.0105, 0.0022        # the socket sculpted into the head round the eye


def flow(P, N):
    """Feathers lie back along the body (back from the face), and down the legs."""
    F = np.tile(np.array((0.0, 1.0, -0.10)), (len(P), 1))
    legs = smoothstep(0.30, 0.24, P[:, 2]) * smoothstep(0.02, 0.04, np.abs(P[:, 0]))
    F = F * (1 - legs[:, None]) + np.array((0.0, 0.25, -1.0)) * legs[:, None]
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def _face(P):
    """1 on the face in front of and round the eyes (the lores, the cere's surround, the sockets), 0 elsewhere."""
    lores = smoothstep(-0.326, -0.336, P[:, 1]) * smoothstep(0.376, 0.386, P[:, 2])
    eyes = np.zeros(len(P))
    for s in (1, -1):
        d = np.linalg.norm(P - np.array(EYE_C) * np.array((s, 1, 1)), axis=1)
        eyes = np.maximum(eyes, smoothstep(0.018, 0.011, d))
    return np.maximum(lores, eyes)


def _nape(P):
    """The hackles: the hind crown, the nape and the back of the neck."""
    return (smoothstep(-0.200, -0.230, P[:, 1]) * smoothstep(-0.300, -0.272, P[:, 1]) *
            smoothstep(0.384, 0.404, P[:, 2]))


def _feather_amount(P, N):
    legs = smoothstep(0.26, 0.20, P[:, 2]) * smoothstep(0.03, 0.05, np.abs(P[:, 0]))
    return (0.0012 + 0.0030 * _nape(P) + 0.0024 * legs) * (1 - _face(P))


def _socket(co, no):
    """The eye sockets: a shallow dish round each eye's axis, so the eyeball sits in the head under the brow."""
    out = co.copy()
    for s in (1, -1):
        c = np.array(EYE_C) * np.array((s, 1, 1))
        n = _mv(EYE_N, s)
        d = co - c
        along = d @ n
        r = np.linalg.norm(d - along[:, None] * n, axis=1)
        k = np.clip(1 - (r / SOCKET_R) ** 2, 0, 1) ** 2 * smoothstep(-0.012, -0.004, along)
        out -= n * (SOCKET_D * k)[:, None]
    return out


def _fur(co, no):
    """The feather clumps (beast_body.sculpt_fur), mirrored (2026-10-24): the same on both sides, so the folded wing
    and the scapulars clear the body alike on the left and the right."""
    sg = np.where(co[:, 0] < 0, -1.0, 1.0)
    ca, na = co.copy(), no.copy()
    ca[:, 0] *= sg
    na[:, 0] *= sg
    d = beast_body.sculpt_fur(ca, na, flow, _feather_amount, seed=61, across=0.012, along_len=0.035) - ca
    d[:, 0] *= sg
    return co + d


def _dec_weight(co):
    y, z = co.y, co.z
    head = 1.0 if y < -0.240 else 0.0
    face = 1.0 if (y < -0.288 and z > 0.392) else 0.0
    legs = 1.0 if z < 0.21 else 0.0
    return 1.0 - 0.50 * head - 0.25 * face - 0.30 * legs


def build_fused():
    bm = bmesh.new()
    loft(bm, TRUNK, up=UP, seg=18, per_seg=3, cap0=0.8, cap1=0.6, shape=0.82)
    loft(bm, NECK, up=UP, seg=16, per_seg=3, cap0=0.5, cap1=0.5)
    loft(bm, HEAD, up=UP, seg=16, per_seg=3, cap0=0.4, cap1=0.5, shape=0.80)
    for s in (1, -1):
        loft(bm, [(s * r[0],) + r[1:] for r in TROUSER], up=(0, -1, 0.3), seg=12, per_seg=2, cap0=0.6, cap1=0.3)
    for c, r, mirror, eul in BLOBS:
        for s in ((1, -1) if mirror else (1,)):
            rot = Euler([math.radians(a) * k for a, k in zip(eul, (1, s, s))]).to_matrix() if eul else None
            ellipsoid(bm, (s * c[0], c[1], c[2]), r, rot=rot)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    body, hi = beast_body.fuse_body(bm, PREFIX, VOXEL, BODY_TRIS, sculpts=(_socket, _fur), dec_weight=_dec_weight,
                                    seam_x=0.005, flat_z=-1.0, fillet_iters=50)
    import zwolf_body
    zwolf_body.tidy(body)
    return body, hi


# ----------------------------------------------------------------------------------------- pieces
class FAcc(DB.Acc):
    """dragon_body.Acc plus per vertex the feather coordinates (u, v, id) and the card's normal (zeros off cards)."""

    def __init__(self):
        super().__init__()
        self.F, self.N = [], []

    def add(self, build, weights=None, color=None, fc=None, nrm=None):
        n0 = len(self.W)
        super().add(build, weights, color)
        n = len(self.W) - n0
        self.F += list(fc) if fc is not None else [(0.0, 0.0, 0.0)] * n
        self.N += [tuple(nrm)] * n if nrm is not None else [(0.0, 0.0, 0.0)] * n


def _mk(V, F):
    def build(bm):
        vs = [bm.verts.new(Vector(p)) for p in V]
        for f in F:
            bm.faces.new([vs[i] for i in f])
        return vs
    return build


def _chain(P, names, B, falloff=0.02):
    return DB.chain_weights(np.asarray(P), DB._bones_of(B, names), falloff)


def _slab(bm, a, b, rows, n, seg=5, rise=None):
    """An airfoil slab along a -> b (left wing): rows (t, lead, trail, top, bottom) -> loft with the centre pushed to
    the leading side by (lead - trail) / 2. rise: rows (t, lift): the rear lifted along n, nothing at RISE_FRONT of
    the lead in front of the line, all of it from RISE_BACK of the trail behind it (smoothly between)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = _n(b - a)
    lat = np.cross(d, n)
    R = []
    for t, le, tr, top, bot in rows:
        c = a + (b - a) * t + lat * (le - tr) / 2
        R.append(tuple(c) + ((le + tr) / 2, top, bot))
    vs = loft(bm, R, up=tuple(n), seg=seg, per_seg=1, cap0=0.7, cap1=0.7, shape=0.8)
    if rise:
        for v in vs:
            v.co = Vector(np.array(v.co) + slab_lift(np.array(v.co), a, b, rows, rise, n))
    return vs


def slab_lift(p, a, b, rows, rise, n=WN):
    """The lift _slab gives a point p of the slab along a -> b (left wing): along n, by rise at its place along the
    slab, nothing at RISE_FRONT of the lead in front of the line, all of it from RISE_BACK of the trail behind it.
    The lift is along n, so the lifted point gives the same answer (eagle_drape takes it back off when folded)."""
    a, b, n = np.asarray(a, float), np.asarray(b, float), np.asarray(n, float)
    d = _n(b - a)
    lat = np.cross(d, n)
    q = np.asarray(p, float) - a
    t = float(np.clip((q @ d) / np.linalg.norm(b - a), 0.0, 1.0))
    s = q @ lat                                         # + the leading side
    tt, tl, tw = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
    s0, s1 = RISE_FRONT * float(np.interp(t, tt, tl)), -RISE_BACK * float(np.interp(t, tt, tw))
    return n * float(np.interp(t, [r[0] for r in rise], [r[1] for r in rise])) * float(smoothstep(s0, s1, s))


def wing_slabs():
    """The wing's flesh slabs (left): (a, b, bone without its side, rows, rise)."""
    S_, E_, W_ = (np.array(WING[k], float) for k in "SEW")
    # the humerus carries the patagium's fill in front of the elbow (folded, its leading side faces down, under the
    # feathers); the forearm's leading side faces up when folded, so it stays narrow
    return [(S_ - _n(E_ - S_) * 0.030, E_ + _n(E_ - S_) * 0.015, "WingArm", ARM_SLAB, ARM_RISE),
            (E_ - _n(W_ - E_) * 0.012, W_ + _n(W_ - E_) * 0.004, "WingForearm", FORE_SLAB, FORE_RISE)]


def _mirror_build(build, s):
    """A piece built on the left, mirrored for the right (faces reversed)."""
    if s > 0:
        return build

    def bm_build(bm):
        tmp = bmesh.new()
        build(tmp)
        for v in tmp.verts:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(tmp, faces=tmp.faces[:])
        tmp.verts.index_update()
        vs = [bm.verts.new(v.co) for v in tmp.verts]
        for f in tmp.faces:
            bm.faces.new([vs[v.index] for v in f.verts])
        for e in tmp.edges:
            if e.seam:
                ne = bm.edges.get((vs[e.verts[0].index], vs[e.verts[1].index]))
                if ne is not None:
                    ne.seam = True
        tmp.free()
        return vs
    return bm_build


# The beak (2026-10-24): short and deep. Each mandible is built from its side profile: two curves (y, z) and a half
# width per row, from the base (inside the face) to the tip. The upper: the culmen arcs down from the cere in one
# curve to the hook; its cutting edge (tomium) runs from the gape's corner below the front of the eye to the hook's
# point. 4.7 cm from the cere to the tip, 2.9 cm deep at the cere's front (the lower mandible included).
# Rows: (culmen y, z, tomium y, z, half width); the last row is the tip.
BEAK_UP = [(-0.324, 0.4040, -0.318, 0.3870, 0.0118), (-0.344, 0.4085, -0.338, 0.3855, 0.0108),
           (-0.358, 0.4070, -0.352, 0.3840, 0.0094), (-0.368, 0.4025, -0.363, 0.3820, 0.0080),
           (-0.3765, 0.3950, -0.3700, 0.3790, 0.0065), (-0.3815, 0.3860, -0.3745, 0.3755, 0.0050),
           (-0.3830, 0.3775, -0.3775, 0.3725, 0.0034), (-0.3795, 0.3705, -0.3795, 0.3705, 0.0)]
# the ring across the upper mandible, (across, up) as fractions of the half width and of tomium -> culmen: the ridge,
# the left side down to the cutting edge, the palate (hidden), the right side back up
UP_RING = ((0.0, 1.0), (0.52, 0.90), (0.88, 0.60), (1.0, 0.24), (0.93, 0.0), (0.0, 0.10),
           (-0.93, 0.0), (-1.0, 0.24), (-0.88, 0.60), (-0.52, 0.90))
# the lower mandible: (top edge y, z, bottom (gonys) y, z, half width); its top edge sits inside the upper's cutting
# edge and its tip inside the hook, so the two read as one beak
BEAK_LOW = [(-0.314, 0.3885, -0.314, 0.3755, 0.0106), (-0.334, 0.3875, -0.334, 0.3765, 0.0099),
            (-0.350, 0.3855, -0.350, 0.3775, 0.0086), (-0.362, 0.3835, -0.362, 0.3785, 0.0067),
            (-0.3705, 0.3815, -0.3700, 0.3795, 0.0044), (-0.3745, 0.3808, -0.3745, 0.3808, 0.0)]
LOW_RING = ((0.0, 0.80), (0.86, 1.0), (1.0, 0.58), (0.84, 0.16), (0.42, 0.0), (0.0, -0.04),
            (-0.42, 0.0), (-0.84, 0.16), (-1.0, 0.58), (-0.86, 1.0))


def _mandible(ctrl, ring, per_seg=2):
    """A mandible from its profile rows (see BEAK_UP): rings across the rows (a Catmull-Rom through the rows but the
    tip), closed at the base by a fan (inside the face) and at the tip by a pole. -> build(bm) for an Acc, and the
    feather-coordinate function (h: 0 cutting edge .. 1 ridge; t: 0 base .. 1 tip) for its vertices."""
    from beast_common import spline
    rows = spline(np.array(ctrl[:-1], float), per_seg)
    tip = np.array(ctrl[-1], float)
    n = len(rows)
    V, H = [], []
    for i, (cy, cz, ty, tz, w) in enumerate(rows):
        C, T = np.array((cy, cz)), np.array((ty, tz))
        for a, h in ring:
            p = T + (C - T) * h
            V.append((a * w, p[0], p[1]))
            H.append((h, i / n, 0.0))
    V.append((0.0, tip[0], tip[1]))
    H.append((0.5, 1.0, 0.0))
    V.append((0.0, rows[0][0] + 0.004, 0.5 * (rows[0][1] + rows[0][3])))        # the base's centre, inside the face
    H.append((0.5, 0.0, 0.0))
    k = len(ring)

    def build(bm):
        vs = [bm.verts.new(Vector(p)) for p in V]
        for i in range(n - 1):
            for j in range(k):
                j1 = (j + 1) % k
                bm.faces.new((vs[i * k + j], vs[i * k + j1], vs[(i + 1) * k + j1], vs[(i + 1) * k + j]))
        t, b = vs[-2], vs[-1]
        for j in range(k):
            j1 = (j + 1) % k
            bm.faces.new((vs[(n - 1) * k + j], vs[(n - 1) * k + j1], t))
            bm.faces.new((vs[j1], vs[j], b))
        # the UV cut: along the palate's middle (hidden) from the base to the tip, and round the base
        c = k // 2
        line = [b] + [vs[i * k + c] for i in range(n)] + [t]
        for p, q in zip(line[:-1], line[1:]):
            e = bm.edges.get((p, q))
            if e is not None:
                e.seam = True
        for j in range(k):
            e = bm.edges.get((vs[j], vs[(j + 1) % k]))
            if e is not None:
                e.seam = True
        return vs
    return build, np.array(H)


def build_pieces(fur, B):
    """-> FAcc (every piece with per-vertex weights; C = part names), landmarks."""
    bml = bmesh.new()
    bml.from_mesh(fur.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    acc = FAcc()
    LM = {}
    # the beak (Head) and the lower mandible (Jaw); their (h, t) go into 'root' for the painter
    build, H = _mandible(BEAK_UP, UP_RING)
    acc.add(build, "Head", 'beak', fc=H)
    build, H = _mandible(BEAK_LOW, LOW_RING)
    acc.add(build, "Jaw", 'jaw', fc=H)
    FE = fe_table()
    for s, sfx in SIDES:
        m = lambda p: _mv(p, s)
        # the eyeball, in its socket on the decimated head: a cap standing EYE_H - EYE_SINK out of the socket's floor
        n = _mv(EYE_N, s)
        e = m(EYE_C)
        hit = bvh.ray_cast(Vector(e + n * 0.04), Vector(-n), 0.08)[0]
        c = (np.array(hit) if hit is not None else e) - n * EYE_SINK
        LM['eye_' + sfx] = c
        acc.add(lambda bm: dome(bm, c, n, EYE_R, EYE_H, seg=10, rings=3), "Head", 'eye')
        # the feathered tarsus and the toes (chain weights), the talons rigid on the last toe bone
        # (2026-10-24) a feathered sock round its top half (under the trousers' hem), the lower half slimmer: bare
        # and yellow in the bald preset, feathered to the toes in the golden one
        A, Bl = np.array(J['ANKLE']), np.array(J['BALL'])
        at = lambda f, r: tuple(m(A + (Bl - A) * f)) + (r,) * 3
        rows = [tuple(m(A + (0, 0, 0.018))) + (0.0190,) * 3, at(0.0, 0.0195), at(TARSUS_SOCK - 0.08, 0.0190),
                at(TARSUS_SOCK, 0.0145), at(TARSUS_SOCK + 0.12, 0.0114), tuple(m(Bl + (0, 0, 0.004))) + (0.0108,) * 3]
        acc.add(lambda bm: loft(bm, rows, up=(0, -1, 0), seg=7, per_seg=1, cap0=0.5, cap1=0.6, capk=2),
                lambda P: _chain(P, [f"Tarsus{sfx}"], B), 'foot')
        for i, (base, joint, tip) in TOES.items():
            pts = [m(base), m(joint), m(tip)]
            names = [f"Toe{i}_1{sfx}", f"Toe{i}_2{sfx}"]
            trows = [tuple(p) + (r, r, r * 0.95) for p, r in zip(pts, TOE_R)]
            acc.add(lambda bm: loft(bm, trows, up=UP, seg=5, per_seg=1, cap0=0.6, cap1=0.8, capk=2),
                    lambda P: _chain(P, names, B, 0.012), 'foot')
            dt = _n(np.array(tip) - np.array(joint))
            dt = _n((dt[0], dt[1], 0.0))
            L = TALON[i]
            tb = m(np.array(tip) + dt * 0.003 + np.array((0, 0, 0.0015)))
            tt = m(np.array(tip) + dt * (0.003 + L * 0.72) + np.array((0, 0, -0.0008)))
            bend = (0.0, 0.0, -0.0060 - 0.08 * L)
            acc.add(lambda bm: cone(bm, tb, tt, 0.0060 if i != 1 else 0.0068, seg=4, bend=bend),
                    f"Toe{i}_2{sfx}", 'claw')
        # the wing's flesh: humerus, forearm (with the patagium in front) -- airfoil slabs, rigid per bone
        nz = WN
        for a, b, bone, srows, rise in wing_slabs():
            acc.add(_mirror_build(lambda bm, a=a, b=b, srows=srows, rise=rise: _slab(bm, a, b, srows, nz, rise=rise), s),
                    bone + sfx, 'wing')
        # the feather cards
        for f in FE.values():
            g = side_of(f, s)
            V, F, fc = g.geometry(s)
            w = {k + sfx: v for k, v in g.bones.items()}
            acc.add(_mk(V, F), lambda P, w=w: [dict(w)] * len(P), 'feather', fc=fc, nrm=_mv(g.n, s))
    return acc, LM


def build_body():
    """-> (EagleBody: the fused body first, then the pieces), the FAcc, EGL_BodyHi."""
    fur, hi = build_fused()
    B = rest_bones()
    acc, LM = build_pieces(fur, B)
    acc.bm.verts.index_update()
    tags = {}
    for v, part in zip(list(acc.bm.verts), acc.C):
        tags.setdefault(part, []).append(v)
    body, nfur, part_extra = beast_body.join_pieces(fur, acc.bm, tags, PREFIX, BODY)
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    V = len(body.data.vertices)
    fcv = np.zeros((V, 3), np.float32)
    fcv[nfur:] = np.array(acc.F, np.float32)
    att = body.data.attributes.new("root", 'FLOAT_VECTOR', 'POINT')      # baked as D['root'] (beast_paint.bake_data)
    att.data.foreach_set('vector', fcv.ravel())
    nrm = np.zeros((V, 3))
    nrm[nfur:] = np.array(acc.N)
    _orient_cards(body, nrm)
    for k, v in LM.items():
        body[k] = [float(c) for c in v]
    return body, acc, hi


def _orient_cards(body, nrm):
    """join_pieces recalculates the pieces' normals, which picks either side of an open card: turn every card face
    to its card's dorsal normal."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.normal_update()
    flip = []
    for f in bm.faces:
        cn = nrm[f.verts[0].index]
        if cn @ cn > 0.5 and f.normal.dot(Vector(cn)) < 0:
            flip.append(f)
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(body.data)
    bm.free()
    return len(flip)


def tri_report(ob):
    """Triangles by part, and the cards by kind."""
    out = beast_body.tri_report(ob)
    att = ob.data.attributes.get("root")
    if att is not None:
        buf = np.zeros(len(ob.data.vertices) * 3, np.float32)
        att.data.foreach_get('vector', buf)
        kid = np.floor(buf.reshape(-1, 3)[:, 2] + 1e-3).astype(int)
        names = {v: k for k, v in KIND.items()}
        part, _ = beast_body.read_info(ob)
        cards = {}
        for p in ob.data.polygons:
            if part[p.vertices[0]] == PART['feather']:
                k = names.get(int(kid[p.vertices[0]]), '?')
                cards[k] = cards.get(k, 0) + len(p.vertices) - 2
        out['cards'] = cards
    return out


# ----------------------------------------------------------------------------------------- skinning
HEAT = ("Hips", "Spine1", "Chest", "Neck1", "Neck2", "Neck3", "Head", "Tail1", "ThighL", "ThighR", "ShinL", "ShinR")


def skin(body, rig, acc):
    """Heat on the fused body (smoothed), the pieces' and cards' own weights from the FAcc, 4 influences."""
    return beast_rig.skin_with_pieces(body, rig, acc.W, HEAT)
