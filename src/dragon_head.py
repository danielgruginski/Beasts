"""The dragon's head (2026-10-17). Daniel on the blockout: "I actually love the horns, but the face will need a lot of
work. Since the dragon is large, the face will actually be visible on the game."

After his perched reference: a deep wedge of a head, not a tube. A heavy brow over a narrow slanted eye framed by
lids, wide jowls, a snout with a dip at the brow, paired ridges down to the nostrils and a swell over the fangs, a
lip line that curls up toward the corner, the front fangs hanging over a deep lower jaw whose line drops to a jaw
angle and rises to a chin, hooks under the jaw, a row of spikes back from each cheek, and the big ribbed frill behind
the jaw. No nose horn (Daniel: "I know the references had a nose horn, but I prefer without one"). The horns stay the
blockout's (dragon_body.HORN; he loves them).

Second pass, after his notes on the first ("an organic pass ... that takes primitives and smoothes them out, creating
a single piece"; "the jaw is a straight line, it should have a proper jaw line"; "the snout is also flat, it should
have some curves"): the whole head is ONE distance field, every primitive melted into the next with a fillet (what a
voxel remesh or metaballs do): skull, jaw, brow, lids, jowls and nostrils. The snout and the jaw are profiles along
their length (half width, top and bottom keyed by y, smoothed), not tapered boxes. The mouth is a slit cut into the
field, open at the front and closed at the corners, so the head is a single skin: weights split along the slit and
blend behind its corners, which stretch when the jaw opens, as lips do.

The spikes were melted in too, and Daniel: "the spikes fused with the skull made things look weird". They are crisp
cones again, each seated where it leaves the skin (seat_spike). The frill's ribs went the same way (he picked the
separate version; FRILL_FUSED). Separate shells: spikes, teeth, eyeballs, tongue, frill ribs and membranes, horns.

Head space: metres at final size, the poll (where the neck's last bone ends) at the origin, horizontal, the snout
toward -Y, left +X. FRAME hangs it on the neck, pitched down like the Head bone.
"""
import math
import numpy as np
import bmesh
from mathutils import Vector

from beast_body import HeadFrame
from beast_common import cone, loft, smoothstep
from ooze_body import smin, smax, sd_capsule, sd_ellipsoid, sdf_mesh

POLL = (0.0, -3.50, 4.70)           # dragon_body.HEAD[0], the neck's end
PITCH = 9.5                         # the snout points this much below level (as the Head bone)
FRAME = HeadFrame(POLL, PITCH)
VOXEL = 0.010
TARGET_TRIS = 12000                 # the melted head; the face is seen in game (Daniel: more for the jaw is fine)

# ----------------------------------------------------------------------------------------- the upper head
CRANIUM = ((0.0, -0.02, 0.12), (0.34, 0.40, 0.32))
# the snout's profile: y, half width, top, lip (its underside = the mouth line). The top dips at the brow ("stop"),
# runs down the bridge and swells over the nostrils; the sides pinch to a waist and flare round the fangs; the lip
# line drops over the fangs and curls up toward the corner of the mouth.
MUZZLE_KEYS = (
    (-0.30, 0.290, 0.300, -0.120),
    (-0.45, 0.280, 0.270, -0.130),
    (-0.60, 0.250, 0.215, -0.145),
    (-0.78, 0.222, 0.200, -0.155),
    (-0.95, 0.205, 0.185, -0.160),
    (-1.10, 0.215, 0.168, -0.172),
    (-1.20, 0.215, 0.172, -0.182),
    (-1.29, 0.200, 0.160, -0.178),
    (-1.35, 0.175, 0.140, -0.165),
    (-1.39, 0.130, 0.110, -0.140),
    (-1.42, 0.050, 0.060, -0.110),       # a blunt, square front (not a beak)
)
MUZZLE_ROUND = (0.80, 0.045)        # top corners: fraction of the section (round); the lip edge: metres (crisp)
NOSE_RIDGES = ((0.115, -1.24, 0.135), (0.19, -0.42, 0.26), 0.040, 0.050)      # paired, nostril -> into the brow
FANG_SWELL = ((0.165, -1.17, -0.06), (0.070, 0.125, 0.075))        # the upper lip bulges over the fang roots (above the slit)
JOWL = ((0.24, -0.20, -0.08), (0.17, 0.30, 0.20))                   # wide cheeks behind the mouth corner
BROW = ((0.19, -0.26, 0.27), (0.26, -0.62, 0.18), 0.080, 0.040)     # the ridge over each eye (capsule a -> b)
CHEEK_RIDGE = ((0.27, -0.36, 0.00), (0.25, -0.78, -0.03), 0.045)    # under the eye, down the side of the snout
NOSTRIL = ((0.120, -1.29, 0.075), (0.068, 0.072, 0.052))            # the raised rim ...
NOSTRIL_HOLE = ((0.150, -1.325, 0.085), (0.030, 0.048, 0.024))     # ... and the hole in it, opening out and forward
STUB = ((0.0, 0.0, 0.02), (0.0, 0.25, -0.08), 0.28)                 # into the neck (hidden by the neck's end)
# the eye: centre (on the skin), long axis (the back end raised: a glare), outward normal; the lids are a ring round
# the almond (A, B: its half axes), the socket is carved inside it and the eyeball sits in the socket
EYE = dict(c=(0.262, -0.50, 0.105), axis=(0.10, 1.0, 0.28), n=(0.86, -0.42, 0.22), A=0.132, B=0.058,
           lid=(0.032, 0.024), socket=(0.122, 0.050, 0.080), ball=(0.122, 0.050, 0.050), ball_out=0.026)

# ----------------------------------------------------------------------------------------- the lower jaw
# y, half width, top (just over the lip line: the two halves touch there before the slit is cut), bottom. The jaw line
# drops to a deep angle under the jowl, rises along the jaw and swells into a chin.
JAW_KEYS = (
    (-0.02, 0.250, -0.090, -0.500),
    (-0.20, 0.250, -0.090, -0.530),
    (-0.40, 0.235, -0.125, -0.500),
    (-0.65, 0.210, -0.146, -0.430),
    (-0.90, 0.185, -0.158, -0.385),
    (-1.08, 0.165, -0.169, -0.400),
    (-1.20, 0.160, -0.179, -0.420),
    (-1.29, 0.150, -0.175, -0.395),
    (-1.35, 0.135, -0.162, -0.350),      # a wide, flat front, not a knob
    (-1.39, 0.105, -0.137, -0.290),
    (-1.41, 0.050, -0.115, -0.220),
    (0.08, 0.200, -0.100, -0.420),       # behind the hinge it closes in under the neck
    (0.14, 0.100, -0.140, -0.320),
)
JAW_ROUND = (0.040, 0.55)           # the lower lip edge: metres (crisp); the underside: fraction (round)
JAWLINE = ((0.200, -0.25, -0.40), (0.150, -1.05, -0.34), 0.050)     # the mandible's edge along each side
CHIN = ((0.0, -1.22, -0.38), (0.15, 0.13, 0.09))
Y_CORNER = -0.36                    # the corner of the mouth: the slit ends here
GAP = (0.020, 0.006)                # the slit's height at the front and at the corner
# the upper lip hangs this far below the mouth line outside the (narrower) lower jaw, clear of it by LIP_CLEAR, so
# from the side the slit is covered: the inner teeth no longer show through it as a dashed line. The jaw swings down
# inside the lip when it opens.
LIP_HANG = 0.032
LIP_CLEAR = 0.016
HINGE = (0.0, -0.08, -0.16)         # the Jaw bone: hinge -> chin
CHIN_TIP = (0.0, -1.30, -0.28)
MOUTH = (0.0, -1.30, -0.17)         # Socket_Mouth: between the front teeth (fire)

# ----------------------------------------------------------------------------------------- spikes (melted in)
BROW_SPIKES = (((0.22, -0.40, 0.31), (0.30, -0.20, 0.44), 0.040), ((0.25, -0.56, 0.27), (0.33, -0.40, 0.38), 0.032))
CHEEK_SPIKES = (((0.37, -0.12, -0.02), (0.62, 0.16, -0.04), 0.050), ((0.38, -0.02, -0.12), (0.61, 0.24, -0.20), 0.046),
                ((0.35, 0.07, -0.21), (0.54, 0.31, -0.32), 0.042))
JAW_HOOKS = (((0.17, -0.78, -0.36), (0.19, -0.66, -0.52), 0.035), ((0.20, -0.46, -0.46), (0.22, -0.32, -0.63), 0.040),
             ((0.21, -0.18, -0.50), (0.23, -0.04, -0.68), 0.042))
CHIN_HOOK = ((0.0, -1.21, -0.43), (0.0, -1.11, -0.60), 0.045)
SPIKE_TIP = 0.006
# Daniel on the melted spikes: "the spikes fused with the skull made things look weird" -> the spikes are separate,
# crisp shells again, each seated where it leaves the skin (seat_spike). The frill's ribs can go either way ("I'm
# undecided if the ear flaps should be metaballs or not"): FRILL_FUSED melts them into the head.
FRILL_FUSED = False
# the frill: ribs fanning up and back from behind the cheek (melted in); a membrane between them (a shell), cupped
# outward and scalloped toward the base
FRILL_BASE = (0.33, 0.06, -0.02)
FRILL_TIPS = ((0.46, 0.38, 0.66), (0.64, 0.58, 0.34), (0.68, 0.62, 0.02), (0.56, 0.52, -0.30))
FRILL_RIB = (0.030, 0.008)

# ----------------------------------------------------------------------------------------- shells
# teeth: (y, length, radius, shows) along the lip lines. The front upper ones hang from the overhanging lip outside
# the narrower lower jaw, so they show with the mouth shut (the fang and two behind it, as in the reference); the
# rest stand over the jaw and bite into it, seen only when the mouth opens.
UPPER_TEETH = [(-1.31, 0.07, 0.022, True), (-1.22, 0.18, 0.036, True), (-1.10, 0.10, 0.026, True),
               (-0.99, 0.075, 0.023, True)] + [(-0.90 + 0.085 * k, 0.07 - 0.004 * k, 0.021, False) for k in range(6)]
LOWER_TEETH = [(-1.25, 0.06, 0.020), (-1.14, 0.13, 0.030)] + [(-1.02 + 0.09 * k, 0.065 - 0.003 * k, 0.020)
                                                             for k in range(7)]

COL = dict(back="8c2e14", belly="d9a04c", horn="2a211c", membrane="7a2a14", eye="ffa21a", mouth="5e1c1a",
           tooth="e8dcc0", pupil="120c08", tongue="8a3a36")


# ----------------------------------------------------------------------------------------- profiles
def _profile(keys, n=600, sigma=0.018):
    """Dense, smoothed profile (columns: y ascending, then the keyed values) from sparse keys: linear between keys,
    then a Gaussian blur along y, so the curves have no kinks at the keys."""
    K = np.array(sorted(keys, key=lambda k: k[0]), float)
    ys = np.linspace(K[0, 0], K[-1, 0], n)
    cols = [np.interp(ys, K[:, 0], K[:, j]) for j in range(1, K.shape[1])]
    dy = ys[1] - ys[0]
    w = max(1, int(3 * sigma / dy))
    k = np.exp(-0.5 * (np.arange(-w, w + 1) * dy / sigma) ** 2)
    k /= k.sum()
    out = [ys]
    for c in cols:
        pad = np.concatenate([np.full(w, c[0]), c, np.full(w, c[-1])])
        out.append(np.convolve(pad, k, mode='valid'))
    return np.stack(out, 1)


MUZZLE = _profile(MUZZLE_KEYS)
LIP = MUZZLE.copy()
LIP[:, 3] -= LIP_HANG
JAW = _profile(JAW_KEYS)
# in front of the corner the jaw's top follows the lip line exactly (the halves touch there; the slit parts them)
JAW[:, 2] = np.where(JAW[:, 0] <= Y_CORNER, np.interp(JAW[:, 0], MUZZLE[:, 0], MUZZLE[:, 3]) + 0.003, JAW[:, 2])


def at(prof, y, col):
    """A profile column at y (clamped to its ends)."""
    return np.interp(y, prof[:, 0], prof[:, col])


def lip(y):
    return at(MUZZLE, y, 3)


def gap(y):
    return GAP[1] + (GAP[0] - GAP[1]) * smoothstep(Y_CORNER, Y_CORNER - 0.12, y)


def sd_profile(P, prof, r_top, r_bot):
    """A rounded box swept along y whose half width, top and bottom follow the profile. The top and bottom corners
    round separately: a radius above 0.2 is a fraction of the section (round), below it metres (a crisp edge). The
    ends are capped flat, so a profile closes in on itself where it ends in the open."""
    y = P[..., 1]
    ys = prof[:, 0]
    yc = np.clip(y, ys[0], ys[-1])
    hw = np.interp(yc, ys, prof[:, 1])
    top = np.interp(yc, ys, prof[:, 2])
    bot = np.interp(yc, ys, prof[:, 3])
    zc, hz = (top + bot) / 2, (top - bot) / 2
    m = np.minimum(hw, hz)
    rt = r_top * m if r_top > 0.2 else np.minimum(r_top, 0.95 * m)
    rb = r_bot * m if r_bot > 0.2 else np.minimum(r_bot, 0.95 * m)
    r = np.where(P[..., 2] > zc, rt, rb)
    qx = np.abs(P[..., 0]) - (hw - r)
    qz = np.abs(P[..., 2] - zc) - (hz - r)
    d2 = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - r
    dy = np.maximum(ys[0] - y, y - ys[-1])
    return np.minimum(np.maximum(d2, dy), 0) + np.sqrt(np.maximum(d2, 0) ** 2 + np.maximum(dy, 0) ** 2)


# ----------------------------------------------------------------------------------------- the field
def _eye_axes(side=1):
    n = np.array(EYE["n"], float) * (side, 1, 1)
    n /= np.linalg.norm(n)
    a = np.array(EYE["axis"], float) * (side, 1, 1)
    a -= n * (a @ n)
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    return a, b, n


def _eye_local(P, side=1):
    a, b, n = _eye_axes(side)
    q = P - np.array(EYE["c"], float) * (side, 1, 1)
    return q @ a, q @ b, q @ n


def _sd_lids(Pm):
    """A ring round the almond (the lids), thicker above."""
    u, v, w = _eye_local(Pm)
    A, B = EYE["A"], EYE["B"]
    r = np.sqrt(u * u + v * v)
    e = np.sqrt((u / A) ** 2 + (v / B) ** 2)
    radial = r * (1 - 1 / np.maximum(e, 1e-6))
    t = np.where(v > 0, EYE["lid"][0], EYE["lid"][1])
    return np.sqrt(radial ** 2 + w ** 2) - t


def _crown():
    """The blockout's crown spikes (behind the horns) in head space."""
    import dragon_body
    out = []
    for a, b, r in dragon_body.CROWN:
        out.append((FRAME.hx_inv(np.array(dragon_body.hk(a))), FRAME.hx_inv(np.array(dragon_body.hk(b))),
                    r * dragon_body.HEAD_K))
    return out


def _spikes():
    """The spikes, (base, tip, base radius, curve: the tip's sideways offset per metre of length, or None): left side
    ones (mirrored), centre ones, and the frill ribs. Cheek spikes droop a little, the hooks curl back."""
    side = [(a, b, r, None) for a, b, r in BROW_SPIKES] + [(a, b, r, (0, 0, -0.10)) for a, b, r in CHEEK_SPIKES] + \
           [(a, b, r, (0, 0.17, 0)) for a, b, r in JAW_HOOKS] + [(a, b, r, None) for a, b, r in _crown()]
    centre = [(*CHIN_HOOK, (0, 0.20, 0))]
    base = np.array(FRILL_BASE)
    ribs = [(base, np.array(t) + (np.array(t) - base) * 0.04, FRILL_RIB[0], None) for t in FRILL_TIPS]
    return side, centre, ribs


def parts(P):
    """The field's pieces: skin (upper, lower, lids), spikes, and the carves (nostrils, sockets, the slit)."""
    Pm = P.copy()
    Pm[..., 0] = np.abs(Pm[..., 0])                    # mirrored: every side feature is written for the left
    up = sd_ellipsoid(P, *CRANIUM)
    up = smin(up, sd_profile(P, MUZZLE, *MUZZLE_ROUND), 0.12)
    a, b, ra, rb = NOSE_RIDGES
    up = smin(up, sd_capsule(Pm, np.array(a), np.array(b), ra, rb), 0.05)
    up = smin(up, sd_ellipsoid(Pm, *FANG_SWELL), 0.05)
    up = smin(up, sd_ellipsoid(Pm, *JOWL), 0.10)
    a, b, ra, rb = BROW
    up = smin(up, sd_capsule(Pm, np.array(a), np.array(b), ra, rb), 0.09)
    a, b, r = CHEEK_RIDGE
    up = smin(up, sd_capsule(Pm, np.array(a), np.array(b), r), 0.05)
    up = smin(up, sd_ellipsoid(Pm, *NOSTRIL), 0.04)
    up = smin(up, sd_capsule(P, np.array(STUB[0]), np.array(STUB[1]), STUB[2]), 0.12)
    y = P[..., 1]
    outside = at(JAW, y, 1) + LIP_CLEAR - np.abs(P[..., 0])            # < 0 outside the jaw's sides
    flap = smax(sd_profile(P, LIP, *MUZZLE_ROUND), outside, 0.006)
    flap = smax(flap, y - Y_CORNER, 0.03)
    up = smin(up, flap, 0.02)
    lo = sd_profile(P, JAW, *JAW_ROUND)
    a, b, r = JAWLINE
    lo = smin(lo, sd_capsule(Pm, np.array(a), np.array(b), r), 0.05)
    lo = smin(lo, sd_ellipsoid(P, *CHIN), 0.05)
    lids = _sd_lids(Pm)
    spk = np.full(P.shape[:-1], 1e3)
    if FRILL_FUSED:                                    # only the frill's ribs ever melt in
        for a, b, r, _ in _spikes()[2]:
            spk = np.minimum(spk, sd_capsule(Pm, np.asarray(a, float), np.asarray(b, float), r, FRILL_RIB[1]))
    y, z = P[..., 1], P[..., 2]
    slit = np.maximum(np.abs(z - lip(y)) - gap(y) / 2, y - Y_CORNER)
    slit = np.maximum(slit, np.abs(P[..., 0]) - (at(JAW, y, 1) + LIP_CLEAR - 0.004))   # not through the lip
    nostril = sd_ellipsoid(Pm, *NOSTRIL_HOLE)
    socket = sd_ellipsoid(np.stack(_eye_local(Pm), -1), (0, 0, 0), EYE["socket"])
    # upper and lower meet hard in front of the corner and blend behind it: a 3 cm blend there filled the 1.6 cm
    # channel between the hanging lip and the jaw's side with a web, which stretched into a curtain on opening
    k_ul = 0.004 + 0.026 * smoothstep(Y_CORNER - 0.06, Y_CORNER + 0.06, y)
    return dict(up=up, lo=lo, lids=lids, spk=spk, slit=slit, nostril=nostril, socket=socket, k_ul=k_ul)


def combine(p):
    skin = smin(p["up"], p["lo"], p["k_ul"])
    skin = smin(skin, p["lids"], 0.025)
    d = smin(skin, p["spk"], 0.035)
    d = smax(d, -p["nostril"], 0.02)
    d = smax(d, -p["socket"], 0.02)
    return smax(d, -p["slit"], 0.006)


def head_field(P):
    return combine(parts(P))


def _mesh_field(field, lo, hi, voxel=VOXEL, chunk=8):
    """Sample a field over a box symmetric in x (a few x slices at a time) and mesh it. -> (V, F) in head space."""
    n = int(math.ceil(hi[0] / voxel))
    i0 = np.array([-n, int(math.floor(lo[1] / voxel)), int(math.floor(lo[2] / voxel))])
    i1 = np.array([n, int(math.ceil(hi[1] / voxel)), int(math.ceil(hi[2] / voxel))])
    ny, nz = i1[1] - i0[1] + 1, i1[2] - i0[2] + 1
    D = np.empty((i1[0] - i0[0] + 1, ny, nz), np.float32)
    J, K = np.meshgrid(np.arange(i0[1], i1[1] + 1), np.arange(i0[2], i1[2] + 1), indexing="ij")
    for s in range(0, D.shape[0], chunk):
        xs = np.arange(i0[0] + s, min(i0[0] + s + chunk, i1[0] + 1))
        P = np.stack(np.broadcast_arrays(xs[:, None, None], J[None], K[None]), -1).astype(np.float64) * voxel
        D[s:s + len(xs)] = field(P)
    for ax in range(3):                                  # close the grid's own faces
        sl = [slice(None)] * 3
        for end in (0, -1):
            sl[ax] = end
            D[tuple(sl)] = np.maximum(D[tuple(sl)], voxel)
    return sdf_mesh(D, i0, voxel)


def _bm_from(V, F):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in V]
    for f in F:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def _decimate(bm, target, weight=None):
    """Collapse to `target` triangles, symmetric in x, then even out slivers (the beasts' fuse_body clean-up).
    weight(P) -> 0..1 per vertex: lower keeps more (the decimate modifier's vertex group)."""
    import bpy
    me = bpy.data.meshes.new("_drg_dec")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("_drg_dec", me)
    bpy.context.scene.collection.objects.link(ob)
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    mod = ob.modifiers.new("dec", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = min(1.0, target / max(n, 1))
    mod.use_symmetry = True
    mod.symmetry_axis = 'X'
    if weight is not None:
        P = np.array([v.co[:] for v in me.vertices])
        w = weight(P)
        g = ob.vertex_groups.new(name="_dec")
        for x in np.unique(np.round(w, 2)):
            g.add([int(i) for i in np.nonzero(np.round(w, 2) == x)[0]], float(x), 'REPLACE')
        mod.vertex_group = "_dec"
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    out = bmesh.new()
    out.from_mesh(ob.data)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bmesh.ops.triangulate(out, faces=out.faces[:])
    bmesh.ops.beautify_fill(out, faces=out.faces[:], edges=out.edges[:])
    bmesh.ops.recalc_face_normals(out, faces=out.faces[:])
    from beast_body import unfold
    unfold(out)                        # folds (one at the chin's centre line took the belly colour)
    return out, n


def build_head_mesh(target=TARGET_TRIS):
    """The melted head in head space: sampled, meshed, smoothed a little (voxel steps), decimated."""
    V, F = _mesh_field(head_field, (-0.75, -1.50, -0.74), (0.75, 0.72, 0.74))
    bm = _bm_from(V, F)
    for _ in range(2):
        bmesh.ops.smooth_laplacian_vert(bm, verts=bm.verts[:], lambda_factor=0.3, lambda_border=0.0,
                                        use_x=True, use_y=True, use_z=True, preserve_volume=True)
    return _decimate(bm, target, _dec_weight)


def _dec_weight(P):
    """Keep the lips' edges (the collapse otherwise bridges the slit with faces that stretch from the snout to the
    chin when the jaw opens), and a little more round the eyes and nostrils."""
    y, z = P[:, 1], P[:, 2]
    near_slit = (y < Y_CORNER + 0.04) & (np.abs(z - lip(y)) < gap(y) / 2 + LIP_HANG + 0.02)
    jaw = (z < lip(y)) & (y < 0.05)
    u, v, w = _eye_local(np.abs(P) * (1, 0, 0) + P * (0, 1, 1))
    near_eye = np.sqrt((u / (EYE["A"] * 1.6)) ** 2 + (v / (EYE["B"] * 2.2)) ** 2 + (w / 0.08) ** 2) < 1
    near_nose = np.linalg.norm((np.abs(P) * (1, 0, 0) + P * (0, 1, 1) - np.array(NOSTRIL[0])) / 0.12, axis=1) < 1
    # where the slit's end meets the channel inside the hanging lip, nothing collapses at all: one triangle there
    # joined the jaw's edge to the lip and stretched into a strand when the mouth opened
    hw = at(JAW, y, 1)
    slit_end = (y < Y_CORNER) & (np.abs(z - lip(y)) < gap(y) / 2 + 0.02) & \
        (np.abs(P[:, 0]) > hw - 0.025) & (np.abs(P[:, 0]) < hw + LIP_CLEAR + 0.012)
    return np.where(slit_end, 0.0, np.where(near_slit, 0.15, np.where(near_eye | near_nose | jaw, 0.4, 1.0)))


def bridges(bm):
    """Faces in front of the corner of the mouth with corners on both lips (should be none)."""
    out = 0
    for f in bm.faces:
        P = np.array([v.co[:] for v in f.verts])
        if (P[:, 1] < Y_CORNER - 0.08).all() and \
                np.abs(P[:, 0]).mean() < at(JAW, P[:, 1], 1).mean():   # (corners close; the lip hangs past the line)
            side = P[:, 2] - lip(P[:, 1])
            if side.max() > 0.25 * gap(P[:, 1]).min() and side.min() < -0.25 * gap(P[:, 1]).min():
                out += 1
    return out


# ----------------------------------------------------------------------------------------- weights and colours
def jaw_weight(P):
    """How much each head-space point follows the jaw: everything under the slit in front of the corner; behind
    it, the jaw's angle under the jowl, fading up into the cheek and back into the neck."""
    y, z = P[:, 1], P[:, 2]
    front = smoothstep(Y_CORNER + 0.10, Y_CORNER - 0.02, y)
    # the upper lip hanging outside the jaw stays on the Head: outside the jaw's sides AND within the lip's own height
    # (on |x| alone it also caught the jaw-line ridge further down, which then stretched into streaks on opening)
    lip_hang = smoothstep(at(JAW, y, 1) + 0.3 * LIP_CLEAR, at(JAW, y, 1) + 0.6 * LIP_CLEAR, np.abs(P[:, 0])) * \
        smoothstep(lip(y) - LIP_HANG - 0.025, lip(y) - LIP_HANG - 0.008, z)
    below = smoothstep(lip(y) + 0.012, lip(y) - 0.012, z) * (1 - lip_hang)
    back = smoothstep(-0.22, -0.40, z) * smoothstep(0.22, 0.02, y)
    return np.clip(front * below + (1 - front) * back, 0, 1)


def head_colors(P, N, rgb):
    p = parts(P)
    skin = smin(smin(p["up"], p["lo"], 0.03), p["lids"], 0.025)
    horn = p["spk"] < skin - 0.008
    y, z = P[:, 1], P[:, 2]
    mouth = (y < Y_CORNER + 0.02) & (y > -1.33) & (np.abs(np.abs(z - lip(y)) - gap(y) / 2) < 0.008) & \
            (np.abs(P[:, 0]) < at(JAW, y, 1) - 0.03)          # inside the lips only
    # the plates under the jaw: a band along the jaw's bottom contour. (Picked from the decimated normals it followed
    # the big triangles in a staircase: gold blotches up the jaw's side that looked like broken UVs.)
    k = smoothstep(at(JAW, y, 3) + 0.10, at(JAW, y, 3) + 0.03, z) * (z < lip(y) - 0.05)
    back, belly = np.array(rgb(COL["back"])), np.array(rgb(COL["belly"]))
    out = []
    for i in range(len(P)):
        if mouth[i]:
            out.append(rgb(COL["mouth"]))
        elif horn[i]:
            out.append(rgb(COL["horn"]))
        else:
            out.append(tuple(back * (1 - k[i]) + belly * k[i]))
    return out


# ----------------------------------------------------------------------------------------- shells (head space)
def build_teeth(bm, upper=True):
    teeth = UPPER_TEETH if upper else [(y, L, r, False) for y, L, r in LOWER_TEETH]
    for s in (1, -1):
        for y, L, r, shows in teeth:
            lz = float(lip(y))
            g = float(gap(y)) / 2
            if upper:
                x = s * ((float(at(MUZZLE, y, 1)) - 0.022) if shows else (float(at(JAW, y, 1)) - 0.09))
                base, tip = (x, y, lz + g + 0.03), (x * 1.01, y + 0.012, lz - L)
                bend = (0, 0.25 * L, 0)
            else:
                x = s * (float(at(JAW, y, 1)) - 0.07)
                base, tip = (x, y, lz - g - 0.03), (x, y - 0.010, lz + L)
                bend = (0, 0.20 * L, 0)
            cone(bm, base, tip, r, seg=6, bend=bend)


def build_tongue(bm):
    def z(y):
        return float(lip(y) - gap(y) / 2) - 0.02
    rows = [(0, -0.36, z(-0.36), 0.12, 0.03, 0.03), (0, -0.70, z(-0.70), 0.10, 0.03, 0.03),
            (0, -1.02, z(-1.02), 0.07, 0.025, 0.025)]
    loft(bm, rows, up=(0, 0, 1), seg=10, per_seg=3, cap0=0.4, cap1=0.9)


def build_frill(bm, s):
    """A fan of membrane between the ribs, each bay cupped a little and scalloped toward the base."""
    base = np.array(FRILL_BASE) * (s, 1, 1)
    tips = [np.array(t) * (s, 1, 1) for t in FRILL_TIPS]
    n_r, n_a = 6, 5
    for t0, t1 in zip(tips[:-1], tips[1:]):
        grid = []
        for i in range(n_r + 1):
            u = i / n_r
            row = []
            for j in range(n_a + 1):
                v = j / n_a
                edge = t0 + (t1 - t0) * v
                scallop = 0.30 * 4 * v * (1 - v) * u ** 3
                p = base + (edge - base) * (u * (1 - scallop))
                cup = 0.035 * 4 * v * (1 - v) * math.sin(math.pi * u)
                row.append(p + np.array((s * cup, 0.0, 0.0)))
            grid.append(row)
        V = [[bm.verts.new(Vector(p)) if i > 0 else None for p in row] for i, row in enumerate(grid)]
        vb = bm.verts.new(Vector(base))
        for j in range(n_a):
            bm.faces.new((vb, V[1][j], V[1][j + 1]))
        for i in range(1, n_r):
            for j in range(n_a):
                bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))


def build_eye(bm, s):
    """The eyeball: an ellipsoid along the almond's axes, its crown just under the lids. -> pupil flags"""
    a, b, n = _eye_axes(s)
    ra, rb, rn = EYE["ball"]
    centre = np.array(EYE["c"], float) * (s, 1, 1) + n * (EYE["ball_out"] - rn)
    tmp = bmesh.new()
    bmesh.ops.create_uvsphere(tmp, u_segments=24, v_segments=14, radius=1.0)
    M = np.stack([a * ra, b * rb, n * rn], 1)
    pupil, vmap = [], {}
    for v in tmp.verts:
        p = np.array(v.co[:])
        vmap[v] = bm.verts.new(Vector(centre + M @ p))
        pupil.append(abs(p[0]) < 0.16 and p[2] > 0.3)   # a slit across the long axis, on the front
    for f in tmp.faces:
        bm.faces.new([vmap[v] for v in f.verts])
    tmp.free()
    return pupil


# ----------------------------------------------------------------------------------------- assembly
def to_body(P):
    return FRAME.hx(P)


def seat_spike(bm, bvh, a, b, r, curve):
    """A spike as a crisp cone, seated where it leaves the skin: from the tip back along its axis to the first hit on
    the head, then sunk in by most of its radius, so it neither floats nor shows its base. -> the seat (head space)"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    hit = bvh.ray_cast(Vector(b), Vector(-u), float(np.linalg.norm(b - a)) * 1.6)[0]
    seat = np.array(hit) if hit is not None else a
    base = seat - u * r * 0.8
    L = float(np.linalg.norm(b - base))
    cone(bm, base, b, r, seg=8, bend=tuple(np.asarray(curve, float) * L) if curve is not None else None)
    return seat


def build(acc, rgb, frill_fused=None):
    """Add the head to a dragon_body.Acc, moved into body space: the melted head (weights blended between Head and
    Jaw), the spikes, teeth, tongue, eyes and frill membranes. rgb(hex) -> linear colour. -> report"""
    global FRILL_FUSED
    if frill_fused is not None:
        FRILL_FUSED = bool(frill_fused)
    rep = {"frill_fused": FRILL_FUSED}
    head, rep["dense_tris"] = build_head_mesh()
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromBMesh(head)
    rep["bridges"] = bridges(head)
    head.verts.ensure_lookup_table()
    head.normal_update()
    P = np.array([v.co[:] for v in head.verts])
    N = np.array([v.normal[:] for v in head.verts])
    wj = jaw_weight(P)
    rep["tris"] = len(head.faces)
    weights = [{"Jaw": float(w), "Head": 1.0 - float(w)} if 0.0 < w < 1.0 else {("Jaw" if w >= 1.0 else "Head"): 1.0}
               for w in wj]
    _add(acc, head, weights, head_colors(P, N, rgb))

    def shell(fn, bone, color):
        tmp = bmesh.new()
        out = fn(tmp)
        n = len(tmp.verts)
        cols = [rgb(COL["pupil"]) if p else rgb(COL["eye"]) for p in out] if color == "eye" else [rgb(color)] * n
        _add(acc, tmp, [{bone: 1.0}] * n, cols)

    side, centre, ribs = _spikes()
    todo = [(np.asarray(a, float) * (s, 1, 1), np.asarray(b, float) * (s, 1, 1), r, c)
            for s in (1, -1) for a, b, r, c in side + ([] if FRILL_FUSED else ribs)] + centre
    for a, b, r, c in todo:
        tmp = bmesh.new()
        seat = seat_spike(tmp, bvh, a, b, r, c)
        bone = "Jaw" if jaw_weight(seat[None])[0] > 0.5 else "Head"
        _add(acc, tmp, [{bone: 1.0}] * len(tmp.verts), [rgb(COL["horn"])] * len(tmp.verts))
    rep["spikes"] = len(todo)

    shell(lambda bm: build_teeth(bm, True), "Head", COL["tooth"])
    shell(lambda bm: build_teeth(bm, False), "Jaw", COL["tooth"])
    shell(build_tongue, "Jaw", COL["tongue"])
    for s in (1, -1):
        shell(lambda bm: build_frill(bm, s), "Head", COL["membrane"])
        shell(lambda bm: build_eye(bm, s), "Head", "eye")
    return rep


def _add(acc, bm, weights, cols):
    """Move a head-space bmesh into body space and append it to an Acc with per-vertex weights and colours."""
    bm.verts.ensure_lookup_table()
    Q = FRAME.hx(np.array([v.co[:] for v in bm.verts]).reshape(-1, 3))
    index = {v: i for i, v in enumerate(bm.verts)}

    def build(target):
        vmap = [target.verts.new(Vector(q)) for q in Q]
        for f in bm.faces:
            try:
                target.faces.new([vmap[index[v]] for v in f.verts])
            except ValueError:
                pass
        return weights
    acc.add(build, None, cols)
    bm.free()
