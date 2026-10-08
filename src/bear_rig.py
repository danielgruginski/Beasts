"""Skinning the cave bear (beast_rig.skin, as the wolf's), plus its separate shells:

- the coat above the belly fringe's hem rides on the spine, not the legs (they swing inside it); the hind legs keep
  theirs up the backs of the thighs;
- hair (fringes, clumps): the weights of the skin at its root (beast_rig.skin_hair_from_roots);
- ears on EarL / EarR, claws on the toes, the tongue and lower teeth with the lower jaw on Jaw; the bottoms of the
  jowls follow the jaw part way.
"""
import numpy as np
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report
from beast_common import smoothstep
import bear_body as B

TRUNK = (("Chest", -0.44), ("Spine2", -0.02), ("Spine1", 0.38), ("Hips", 0.72))     # bone, where along y it leads


def _jaw_weight(cu):
    """The bottoms of the jowls follow the jaw part way, so the corners of the mouth stretch."""
    H = B.hx_inv(cu)
    z = H[:, 2]
    return (0.6 * smoothstep(-0.21, -0.27, z) * smoothstep(-0.38, -0.31, z) * smoothstep(-0.05, -0.12, H[:, 1]) *
            smoothstep(-0.32, -0.24, H[:, 1]) * smoothstep(0.22, 0.17, np.abs(H[:, 0])))


def _leg_share(co):
    """How much of its leg weight a skin vertex keeps: below the belly fringe's hem the legs are bare and keep theirs,
    the thighs keep theirs behind the skirt; elsewhere the coat rides on the spine."""
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    ax = np.abs(x)
    dF = np.hypot(ax - 0.310, y + 0.470)
    dH = np.hypot(ax - 0.310, y - 0.580)
    near = smoothstep(0.26, 0.17, np.minimum(dF, dH))
    low = np.maximum(smoothstep(0.66, 0.52, z) * near, smoothstep(0.40, 0.30, z))   # the feet: always the legs'
    behind = smoothstep(0.88, 0.64, z) * smoothstep(0.50, 0.70, y)
    return np.maximum(low, behind)


def skin(body, rig):
    rep = beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=None, jaw_weight=_jaw_weight)
    n = body["n_fur"]
    part, _ = read_info(body)
    co = np.array([body.data.vertices[i].co[:] for i in range(n)])
    beast_rig.coat_on_trunk(body, n, _leg_share(co), TRUNK)
    clean_weights(body)
    beast_rig.skin_hair_from_roots(body, n, np.nonzero(part == PART['hair'])[0])
    beast_rig.set_rigid(body, np.nonzero(part == PART['tongue'])[0], "Jaw")
    ear = np.nonzero(part == PART['ear'])[0]
    x = np.array([body.data.vertices[int(i)].co.x for i in ear])
    beast_rig.set_rigid(body, ear[x > 0], "EarL")
    beast_rig.set_rigid(body, ear[x <= 0], "EarR")
    claw = np.nonzero(part == PART['claw'])[0]
    co = np.array([body.data.vertices[int(i)].co[:] for i in claw])
    for front in (True, False):
        for s, sfx in ((1, "L"), (-1, "R")):
            sel = claw[((co[:, 1] < 0) == front) & ((co[:, 0] > 0) == (s > 0))]
            beast_rig.set_rigid(body, sel, ("FrontToes" if front else "HindToes") + sfx)
    clean_weights(body)
    return weight_report(body)


TEST_POSE = {
    # bone: (axis in the bone's local frame, degrees)
    "Neck1": ('X', 12), "Head": ('X', 15), "Jaw": ('X', -30), "EarL": ('X', -30), "EarR": ('X', 20),
    "UpperArmL": ('X', 35), "ForearmL": ('X', -55), "FrontPawL": ('X', 40),
    "UpperArmR": ('X', -20), "ForearmR": ('X', 10),
    "ThighL": ('X', -25), "ShinL": ('X', 35), "HindFootL": ('X', -20),
    "ThighR": ('X', 25), "ShinR": ('X', -10),
    "Spine2": ('Z', 8), "Chest": ('Z', 8),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
