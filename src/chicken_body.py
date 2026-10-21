"""Chicken (farm animal, 2026-10-20): a village hen, procedural body and bird skeleton, facing -Y, left side +X.

No approved creature is a bird, so the hen is new, built with the beasts' tools (beast_body.fuse_body for the
feathered body, clean lofted shells for the rest, heat weights) and the beasts' conventions (Root and Motion, sockets,
the leg bones named Thigh / Shin / HindFoot / HindToes so beast_paint's regions and the Unity setup work as for the
quadrupeds).

A hen of the time, small and upright: 0.40 m to the top of the comb, a round feathered body held level, the breast
full, a short neck with hackles, a small head with a single serrated comb, wattles and a short curved beak, folded
wings along the sides, a narrow upright tail, feathered drumsticks and bare yellow shanks with three toes forward and
one back. About 1.3k triangles: at the colony camera she is a few pixels tall.

build_body() -> ChickenBody (fused body joined with the shells: beak (upper 'horn', lower 'jaw'), eyes, comb and
wattles ('whisker'), wings ('hair'), tail ('tail'), shanks and toes ('claw')). rest_bones() is the skeleton.
"""
import bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome
import beast_body
from beast_body import PART, ellipsoid, _write_info, _mx
from farm_body import _frame

NAME, PREFIX = "Chicken", "CHK"
VOXEL, BODY_TRIS = 0.0025, 760

# joints (left side): hip, knee (inside the drumstick), ankle (the hock, where the feathers end), foot, toe tip
J = dict(HIP=(0.040, 0.035, 0.195), KNEE=(0.046, -0.010, 0.150), ANKLE=(0.042, 0.032, 0.088),
         FOOT=(0.040, 0.002, 0.012), TOE=(0.040, -0.055, 0.004))
BLOBS = [((0, 0.015, 0.215), (0.088, 0.135, 0.092), False),     # the body
         ((0, -0.065, 0.205), (0.072, 0.070, 0.085), False),    # the breast
         ((0, 0.110, 0.240), (0.064, 0.065, 0.065), False),     # the rump, under the tail
         ((0, 0.040, 0.168), (0.070, 0.090, 0.058), False),     # the belly's fluff
         ((0.045, 0.020, 0.150), (0.032, 0.040, 0.052), True),  # the drumstick
         ((0, -0.117, 0.368), (0.028, 0.040, 0.032), False),    # the head
         ((0.016, -0.128, 0.356), (0.014, 0.020, 0.014), True)] # the cheek (ear lobe)
NECK = [(0, -0.058, 0.252, 0.052, 0.052, 0.058), (0, -0.084, 0.300, 0.041, 0.041, 0.043),
        (0, -0.100, 0.335, 0.032, 0.032, 0.032), (0, -0.108, 0.360, 0.026, 0.028, 0.026)]
BEAK_UP = [(0, -0.138, 0.365, 0.011, 0.010, 0.006), (0, -0.157, 0.362, 0.009, 0.007, 0.005),
           (0, -0.176, 0.352, 0.002, 0.002, 0.002)]
BEAK_LOW = [(0, -0.138, 0.353, 0.009, 0.003, 0.005), (0, -0.158, 0.351, 0.007, 0.003, 0.004),
            (0, -0.170, 0.348, 0.002, 0.002, 0.002)]
COMB = [(0, -0.142, 0.388, 0.004, 0.008, 0.012), (0, -0.124, 0.400, 0.005, 0.014, 0.014),
        (0, -0.104, 0.398, 0.005, 0.013, 0.014), (0, -0.086, 0.388, 0.004, 0.007, 0.010)]
COMB_POINTS = [(-0.132, 0.405, 0.010), (-0.118, 0.412, 0.013), (-0.104, 0.410, 0.012), (-0.092, 0.401, 0.008)]
WATTLE = [(0.008, -0.146, 0.346, 0.004, 0.008, 0.008), (0.008, -0.145, 0.333, 0.005, 0.010, 0.010),
          (0.008, -0.143, 0.322, 0.002, 0.004, 0.004)]
EYE_C, EYE_N, EYE_R = (0.026, -0.124, 0.374), (0.85, -0.35, 0.25), 0.0085
WING = [(0.085, -0.055, 0.255, 0.007, 0.022, 0.026), (0.093, -0.005, 0.250, 0.010, 0.030, 0.040),
        (0.092, 0.055, 0.238, 0.008, 0.026, 0.034), (0.084, 0.105, 0.222, 0.005, 0.016, 0.020),
        (0.070, 0.140, 0.205, 0.002, 0.005, 0.005)]                # folded: tapering back to the primaries
TAIL = [(0, 0.095, 0.245, 0.012, 0.020, 0.020), (0, 0.135, 0.288, 0.010, 0.036, 0.034),
        (0, 0.160, 0.325, 0.007, 0.032, 0.030), (0, 0.168, 0.350, 0.002, 0.010, 0.010)]
SHANK = [(0.042, 0.030, 0.125, 0.008, 0.008, 0.008), (0.042, 0.032, 0.088, 0.0075, 0.0075, 0.0075),
         (0.041, 0.014, 0.040, 0.0065, 0.0065, 0.0065), (0.040, 0.003, 0.012, 0.007, 0.007, 0.007)]
TOES = [((0.040, 0.002, 0.008), (0.020, -0.052, 0.004)), ((0.040, 0.002, 0.008), (0.040, -0.058, 0.004)),
        ((0.040, 0.002, 0.008), (0.060, -0.050, 0.004)), ((0.040, 0.004, 0.010), (0.040, 0.026, 0.005))]
LM = {}


def _flow(P, N):
    """Feathers lie back along the body and down the neck."""
    F = np.tile(np.array((0.0, 1.0, -0.35)), (len(P), 1))
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def _amount(P, N):
    A = np.full(len(P), 0.0012)
    head = (P[:, 1] < -0.09) & (P[:, 2] > 0.33)
    return np.where(head, 0.0003, A)


def build_fur_body():
    bm = bmesh.new()
    for c, r, mirror in BLOBS:
        for s in ((1, -1) if mirror else (1,)):
            ellipsoid(bm, (s * c[0], c[1], c[2]), r)
    loft(bm, NECK, up=(0, 0, 1), seg=16, per_seg=3, cap0=0.5, cap1=0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    sculpt = lambda co, no: beast_body.sculpt_fur(co, no, _flow, _amount, seed=31, across=0.012, along_len=0.03)
    head = lambda co: 1.0 - 0.45 * float(co.y < -0.09 and co.z > 0.32) - 0.3 * float(co.z < 0.13)
    return beast_body.fuse_body(bm, PREFIX, VOXEL, BODY_TRIS, sculpts=(sculpt,), dec_weight=head, seam_x=0.006,
                                flat_z=-1.0, fillet_iters=40)


def _snap(bvh, p, n, reach=0.03):
    hit = bvh.ray_cast(Vector(p + n * reach), Vector(-n), reach * 2)[0]
    return np.array(hit) if hit is not None else np.array(p)


def build_pieces(low):
    bml = bmesh.new()
    bml.from_mesh(low.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    bm = bmesh.new()
    tags = {}
    tags['horn'] = loft(bm, BEAK_UP, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.0, cap1=0.5, capk=1, shape=0.85)
    tags['jaw'] = loft(bm, BEAK_LOW, up=(0, 0, 1), seg=6, per_seg=2, cap0=0.0, cap1=0.5, capk=1)
    red = loft(bm, COMB, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.5, cap1=0.5, capk=2)
    for y, z, h in COMB_POINTS:
        red += cone(bm, (0, y, z - 0.004), (0, y + 0.002, z + h * 0.6), 0.006, seg=4)
    for s in (1, -1):
        red += loft(bm, [(s * r[0],) + r[1:] for r in WATTLE], up=(0, -1, 0), seg=6, per_seg=2, cap0=0.5, cap1=0.5,
                    capk=1)
    tags['whisker'] = red
    eyes = []
    for s in (1, -1):
        n = np.array(EYE_N) / np.linalg.norm(EYE_N) * np.array((s, 1, 1))
        c = _snap(bvh, np.array(EYE_C) * np.array((s, 1, 1)), n) - n * 0.0015
        LM['eye_L' if s > 0 else 'eye_R'] = c
        LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
        eyes += dome(bm, c, n, EYE_R, 0.004, seg=10, rings=2)
    tags['eye'] = eyes
    wings = []
    for s in (1, -1):
        wings += loft(bm, [(s * r[0],) + r[1:] for r in WING], up=(0, 0, 1), seg=8, per_seg=3, cap0=0.5, cap1=0.4,
                      capk=2, seam=math.pi * (0.5 if s > 0 else -0.5))
    tags['hair'] = wings
    tags['tail'] = loft(bm, TAIL, up=(0, -1, 0), seg=8, per_seg=3, cap0=0.0, cap1=0.5, capk=2)
    claws = []
    for s in (1, -1):
        claws += loft(bm, [(s * r[0],) + r[1:] for r in SHANK], up=(0, -1, 0), seg=6, per_seg=2, cap0=0.0,
                      cap1=0.5, capk=1)
        for base, tip in TOES:
            claws += cone(bm, (s * base[0],) + base[1:], (s * tip[0],) + tip[1:], 0.0055, seg=4)
    tags['claw'] = claws
    return bm, tags


def build_body():
    """-> (ChickenBody, CHK_BodyHi)"""
    fur, hi = build_fur_body()
    nfur = len(fur.data.vertices)
    bm, tags = build_pieces(fur)
    body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, PREFIX, NAME + "Body")
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    for k, v in LM.items():
        body[k] = [float(c) for c in v]
    return body, hi


def tri_report(ob):
    return beast_body.tri_report(ob)


# ------------------------------------------------------------------------------------------ skeleton
def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform); Root and Motion as the beasts'."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.15, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.1, None, True)

    def bone(name, head, tail, zhint, parent):
        h, t = Vector(head), Vector(tail)
        hh, fr = _frame(h, t - h, zhint)
        B[name] = (hh, fr, (t - h).length, parent, True)
    UP, FWD = (0, 0, 1), (0, -1, 0)
    bone("Hips", (0, 0.050, 0.215), (0, 0.130, 0.235), UP, "Root")
    bone("Chest", (0, 0.050, 0.215), (0, -0.060, 0.235), UP, "Hips")
    bone("Neck1", (0, -0.060, 0.250), (0, -0.088, 0.305), UP, "Chest")
    bone("Neck2", (0, -0.088, 0.305), (0, -0.105, 0.345), UP, "Neck1")
    bone("Head", (0, -0.105, 0.345), (0, -0.160, 0.362), UP, "Neck2")
    bone("Jaw", (0, -0.138, 0.352), (0, -0.172, 0.346), UP, "Head")
    bone("Tail1", (0, 0.105, 0.250), (0, 0.165, 0.330), (0, 1, 0), "Hips")
    for s, sfx in ((1, "L"), (-1, "R")):
        m = (lambda p: p) if s > 0 else _mx
        bone(f"Wing{sfx}", m((0.092, -0.050, 0.252)), m((0.097, 0.045, 0.242)), UP, "Chest")
        bone(f"WingTip{sfx}", m((0.097, 0.045, 0.242)), m((0.082, 0.125, 0.216)), UP, f"Wing{sfx}")
        bone(f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
        bone(f"Shin{sfx}", m(J['KNEE']), m(J['ANKLE']), FWD, f"Thigh{sfx}")
        bone(f"HindFoot{sfx}", m(J['ANKLE']), m(J['FOOT']), FWD, f"Shin{sfx}")
        bone(f"HindToes{sfx}", m(J['FOOT']), m(J['TOE']), UP, f"HindFoot{sfx}")
    bone("Socket_Head", (0, -0.110, 0.400), (0, -0.110, 0.500), FWD, "Head")
    bone("Socket_Mouth", (0, -0.165, 0.350), (0, -0.165, 0.450), FWD, "Jaw")
    return B


NO_HEAT = ("Root", "Motion", "Jaw", "WingL", "WingR", "WingTipL", "WingTipR", "HindToesL", "HindToesR")


def skin(body, rig):
    """Heat weights on the fused body (not from the wings, toes or jaw); the shells rigid: the beak and comb on
    Head, the lower beak on Jaw, the wings along Wing -> WingTip, the tail on Tail1, the shanks on HindFoot and the
    toes on HindToes."""
    import beast_rig
    from beast_rig import set_rigid, clean_weights, weight_report
    from beast_body import read_info
    beast_rig.skin(body, rig, no_heat=NO_HEAT)
    part, _ = read_info(body)
    co = np.array([v.co[:] for v in body.data.vertices])
    for nm in NO_HEAT[2:]:                       # bones left out of the heat solve have no groups yet
        if nm not in body.vertex_groups:
            body.vertex_groups.new(name=nm)
    wing = np.nonzero(part == PART['hair'])[0]
    for i in wing:
        p = co[i]
        sfx = "L" if p[0] > 0 else "R"
        t = float(np.clip((p[1] - 0.02) / 0.06, 0, 1))
        for g in body.vertex_groups:
            g.remove([int(i)])
        if t < 1:
            body.vertex_groups[f"Wing{sfx}"].add([int(i)], 1 - t, 'REPLACE')
        if t > 0:
            body.vertex_groups[f"WingTip{sfx}"].add([int(i)], t, 'REPLACE')
    set_rigid(body, np.nonzero(part == PART['tail'])[0], "Tail1")
    claw = np.nonzero(part == PART['claw'])[0]
    for s, sfx in ((1, "L"), (-1, "R")):
        side = claw[(co[claw, 0] > 0) == (s > 0)]
        toes = side[co[side, 2] < 0.011]
        set_rigid(body, side[co[side, 2] >= 0.011], f"HindFoot{sfx}")
        set_rigid(body, toes, f"HindToes{sfx}")
    clean_weights(body)
    return weight_report(body)
