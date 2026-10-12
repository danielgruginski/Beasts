"""Skinning the red deer stag (beast_rig.skin, as the wolf's), plus its separate shells (2026-10-11):

- the legs' stumps (fused: upper arm to mid forearm, stifle to mid gaskin) have heat weights like the rest, so the
  elbow and stifle bend in one skin;
- the lower legs (clean tubes) blend down the leg by height: the forearm / gaskin, the cannon and the pastern,
  crossing over at the knee / hock and the fetlock; at and above their seam on the stump they ride exactly like the
  stump's skin there, blending to the leg below it;
- the heat weights round the shoulders and haunches smoothed more (a lifted leg pinched a fold);
- the hooves' claws and the dewclaws rigid on the toes;
- ears on EarL / EarR, the antlers and eyes rigid on Head, the lower jaw on Jaw; the bottoms of the jowls follow
  the jaw part way.
"""
import numpy as np
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report, set_rigid
from beast_common import smoothstep
import deer_body as D

# down each lower leg: its bones, and the joints between them (height, half the blend's width)
LEG_CHAIN = {'F': (("UpperArm", "Forearm", "FrontPaw", "FrontToes"), ((0.690, 0.050), (0.380, 0.030), (0.130, 0.025))),
             'H': (("Thigh", "Shin", "HindFoot", "HindToes"), ((0.730, 0.050), (0.455, 0.030), (0.130, 0.025)))}


def _jaw_weight(cu):
    """The bottoms of the jowls behind the mouth's corner follow the jaw part way."""
    H = D.hx_inv(cu)
    z = H[:, 2]
    return (0.5 * smoothstep(-0.115, -0.140, z) * smoothstep(-0.20, -0.16, z) * smoothstep(-0.06, -0.12, H[:, 1]) *
            smoothstep(-0.34, -0.26, H[:, 1]) * smoothstep(0.075, 0.05, np.abs(H[:, 0])))


def skin(body, rig):
    beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=None, jaw_weight=_jaw_weight)
    n = body["n_fur"]
    part, _ = read_info(body)
    _smooth_joins(body, n)
    clean_weights(body)
    ear = np.nonzero(part == PART['ear'])[0]
    x = np.array([body.data.vertices[int(i)].co.x for i in ear])
    set_rigid(body, ear[x > 0], "EarL")
    set_rigid(body, ear[x <= 0], "EarR")
    _skin_legs(body, np.array(list(body["leg_verts"]), int))
    claw = np.nonzero(part == PART['claw'])[0]
    co = np.array([body.data.vertices[int(i)].co[:] for i in claw])
    for front in (True, False):
        for s, sfx in ((1, "L"), (-1, "R")):
            sel = claw[((co[:, 1] < 0) == front) & ((co[:, 0] > 0) == (s > 0))]
            set_rigid(body, sel, ("FrontToes" if front else "HindToes") + sfx)
    clean_weights(body)
    return weight_report(body)


JOINS = (((0.150, -0.46, 0.78), 0.24), ((0.140, 0.40, 0.78), 0.26))    # shoulder / haunch round the legs' tops
JOIN_BAND = 0.07                        # below its seam on the stump, a tube blends from the skin to its leg


def _smooth_joins(body, n):
    """Extra smoothing of the heat weights round the shoulders and haunches, where a lifted leg pinched a fold."""
    co = np.array([body.data.vertices[i].co[:] for i in range(n)])
    near = np.zeros(n, bool)
    for c, r in JOINS:
        near |= np.linalg.norm((np.stack([np.abs(co[:, 0]), co[:, 1], co[:, 2]], -1) - c), axis=1) < r
    beast_rig.smooth_weights(body, np.nonzero(near)[0], iterations=6, factor=0.5)


def _skin_legs(body, idx):
    """Each lower-leg vertex blends between the bones above and below the joint it is nearest (by height). At its
    top, where it is stitched onto the stump (deer_body.SEAM), it moves like the stump's skin there (the weights of
    the nearest stump vertex), blending to its leg's bones over JOIN_BAND below."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    if not len(idx):
        return
    n = body["n_fur"]
    me = body.data
    names = {g.index: g.name for g in body.vertex_groups}
    skin_v = sorted(set(range(n)) - set(int(i) for i in idx))     # the fused skin (the legs are part of the fur)
    kd = KDTree(len(skin_v))
    for j in skin_v:
        kd.insert(me.vertices[j].co, j)
    kd.balance()
    co = np.array([me.vertices[int(i)].co[:] for i in idx])
    for g in body.vertex_groups:
        g.remove([int(i) for i in idx])
    for i, p in zip(idx, co):
        kind = 'F' if p[1] < 0 else 'H'
        bones, joints = LEG_CHAIN[kind]
        sfx = "L" if p[0] > 0 else "R"
        u = [float(smoothstep(zj + w, zj - w, p[2])) for zj, w in joints]     # how far past each joint (0 above)
        w = {b + sfx: wt for b, wt in zip(bones, (1 - u[0], u[0] * (1 - u[1]), u[1] * (1 - u[2]), u[2]))}
        k = float(smoothstep(D.SEAM[kind] - JOIN_BAND, D.SEAM[kind] - 0.002, p[2]))
        if k > 0:
            skin = {names[g.group]: g.weight for g in me.vertices[kd.find(Vector(p))[1]].groups}
            w = {b: (1 - k) * w.get(b, 0.0) + k * skin.get(b, 0.0) for b in set(w) | set(skin)}
        for b, wt in w.items():
            if wt > 1e-4:
                body.vertex_groups[b].add([int(i)], wt, 'REPLACE')


TEST_POSE = {
    # bone: (axis in the bone's local frame, degrees)
    "Neck1": ('X', 10), "Neck2": ('X', 8), "Neck3": ('X', 6), "Head": ('Z', 20), "Jaw": ('X', -25),
    "EarL": ('X', -30), "EarR": ('X', 25), "Tail1": ('X', 30),
    "UpperArmL": ('X', 25), "ForearmL": ('X', 30), "FrontPawL": ('X', -95), "FrontToesL": ('X', -30),   # foreleg
                                                                                        # lifted, the knee folded
    "UpperArmR": ('X', -20), "ForearmR": ('X', 10),
    "ThighL": ('X', -30), "ShinL": ('X', 45), "HindFootL": ('X', -40),
    "ThighR": ('X', 25), "ShinR": ('X', -10),
    "Spine2": ('Z', 8), "Chest": ('Z', 8),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
