"""Skinning the woolly rhino (beast_rig.skin, as the wolf's), plus its separate shells:

- the coat's clumps and fringes: every vertex takes the weights of the skin at its root (the 'root' attribute), so a
  clump rides on the skin it grows from without stretching;
- the coat above the skirt's hem rides on the spine, not the legs (they swing inside the skirt);
- the spear: 100% on Chest, then split into its own object "Spear" after painting, so the game can hide it;
- the ears (separate funnels) ride on EarL / EarR;
- the chin and lower lip ride on Jaw; the lower cheeks behind the mouth corner follow it part way.
"""
import numpy as np
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report, _set_group
from beast_common import smoothstep

SPEAR_BONE = "Chest"


def _jaw_weight(cu):
    """The lower cheek just behind the mouth corner follows the jaw part way, so the corner stretches."""
    import rhino_body
    H = rhino_body.hx_inv(cu)                                              # head space
    z = H[:, 2]
    return (0.7 * smoothstep(-0.28, -0.36, z) * smoothstep(-0.52, -0.44, z) * smoothstep(-0.42, -0.50, H[:, 1]) *
            smoothstep(-0.66, -0.58, H[:, 1]) * smoothstep(0.24, 0.18, np.abs(H[:, 0])))    # the cheek only


TRUNK = (("Chest", -0.45), ("Spine2", 0.08), ("Spine1", 0.52), ("Hips", 0.90))   # bone, where along y it leads


def _leg_share(co):
    """How much of its leg weight a skin vertex keeps: the skirt hides the upper legs, so above its hem the coat
    rides on the spine (the legs swing inside it); the hind legs keep theirs up to the stifle behind the skirt."""
    import rhino_body as RB
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    ax = np.abs(x)
    dF = np.hypot(ax - RB.J['FPAW'][0], y - RB.J['FPAW'][1])          # off the leg columns
    dH = np.hypot(ax - RB.J['HPAW'][0], y - RB.J['HPAW'][1])
    near = smoothstep(0.26, 0.17, np.minimum(dF, dH))
    low = smoothstep(0.54, 0.38, z) * near                            # the leg below the skirt
    behind = smoothstep(0.84, 0.62, z) * smoothstep(0.62, 0.80, y)      # the thighs behind the skirt's back edge
    return np.maximum(low, behind)


def skin(body, rig):
    rep = beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=None, jaw_weight=_jaw_weight)
    n = body["n_fur"]
    part, _ = read_info(body)
    co = np.array([body.data.vertices[i].co[:] for i in range(n)])
    beast_rig.coat_on_trunk(body, n, _leg_share(co), TRUNK)
    clean_weights(body)
    beast_rig.skin_hair_from_roots(body, n, np.nonzero(part == PART['hair'])[0])
    ear = np.nonzero(part == PART['ear'])[0]
    if len(ear):
        x = np.array([body.data.vertices[int(i)].co.x for i in ear])
        beast_rig.set_rigid(body, ear[x > 0], "EarL")
        beast_rig.set_rigid(body, ear[x <= 0], "EarR")
    beast_rig.set_rigid(body, np.nonzero(part == PART['spear'])[0], SPEAR_BONE)
    clean_weights(body)
    return weight_report(body)


def split_spear(body, rig, name="Spear"):
    """Separate the spear's faces into their own object (same rig, material and UVs), named Spear."""
    part, _ = read_info(body)
    return beast_rig.split_part(body, part == PART['spear'], name, (SPEAR_BONE,))


TEST_POSE = {
    # bone: (axis in the bone's local frame, degrees)
    "Neck1": ('X', 10), "Head": ('X', 18), "Jaw": ('X', -18), "EarL": ('X', -30), "EarR": ('X', 20),
    "Tail1": ('X', -20), "Tail2": ('Z', 25),
    "UpperArmL": ('X', 30), "ForearmL": ('X', -50), "FrontPawL": ('X', 45),
    "UpperArmR": ('X', -20), "ForearmR": ('X', 10),
    "ThighL": ('X', -25), "ShinL": ('X', 35), "HindFootL": ('X', -30),
    "ThighR": ('X', 25), "ShinR": ('X', -10),
    "Spine2": ('Z', 8), "Chest": ('Z', 8),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
