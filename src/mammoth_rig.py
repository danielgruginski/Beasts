"""Skinning the woolly mammoth (beast_rig.skin, as the wolf's), plus its separate shells:

- the coat's skin above the skirt's hem rides on the spine, not the legs (they swing inside it); the legs keep theirs
  below it and the hind legs up the backs of the thighs;
- the trunk (a separate tube) blends along Trunk1-6 by how far down it each ring is, from Head at its root;
- hair (fringes, clumps): the weights of the skin at its root (beast_rig.skin_hair_from_roots);
- ears on EarL / EarR, the tusks and eyes rigid on Head, the lower lip on Jaw.
"""
import numpy as np
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report
from beast_common import smoothstep
import mammoth_body as B

TRUNK = (("Chest", -1.00), ("Spine2", -0.20), ("Spine1", 0.45), ("Hips", 0.90))     # bone, where along y it leads


def _leg_share(co):
    """How much of its leg weight a skin vertex keeps: below the skirt's hem the legs are bare of the coat and keep
    theirs, the thighs keep theirs behind; elsewhere the coat rides on the spine."""
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    ax = np.abs(x)
    dF = np.hypot(ax - 0.57, y + 1.12)
    dH = np.hypot(ax - 0.55, y - 0.75)
    near = smoothstep(0.50, 0.36, np.minimum(dF, dH))
    low = np.maximum(smoothstep(1.50, 1.25, z) * near, smoothstep(1.05, 0.85, z))
    behind = smoothstep(1.85, 1.45, z) * smoothstep(0.95, 1.15, y) * smoothstep(0.20, 0.35, ax)
    return np.maximum(low, behind)


def skin(body, rig):
    rep = beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"))
    n = body["n_fur"]
    part, _ = read_info(body)
    co = np.array([body.data.vertices[i].co[:] for i in range(n)])
    beast_rig.coat_on_trunk(body, n, _leg_share(co), TRUNK)
    clean_weights(body)
    beast_rig.skin_hair_from_roots(body, n, np.nonzero(part == PART['hair'])[0])
    ear = np.nonzero(part == PART['ear'])[0]
    x = np.array([body.data.vertices[int(i)].co.x for i in ear])
    beast_rig.set_rigid(body, ear[x > 0], "EarL")
    beast_rig.set_rigid(body, ear[x <= 0], "EarR")
    _skin_trunk(body, np.nonzero(part == PART['proboscis'])[0])
    clean_weights(body)
    return weight_report(body)


def _skin_trunk(body, idx):
    """The trunk tube: each vertex blends between the two bones whose middles it lies between (by arc length down
    the centre line); above the top row it fades into Head."""
    from beast_paint import polyline_t
    if not len(idx):
        return
    rows = B.TRUNK_ROWS
    C = np.array([r[:3] for r in rows])
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    co = np.array([body.data.vertices[int(i)].co[:] for i in idx])
    t, _ = polyline_t(co, rows)
    a = t * cum[-1] - np.maximum(0.0, co[:, 2] - rows[0][2]) * (t < 1e-6)
    bones = ["Head"] + [f"Trunk{k + 1}" for k in range(len(rows) - 1)]
    mids = np.concatenate([[-0.12], 0.5 * (cum[:-1] + cum[1:])])
    for g in body.vertex_groups:
        g.remove([int(i) for i in idx])
    for i, ai in zip(idx, a):
        if ai <= mids[0]:
            w = {bones[0]: 1.0}
        elif ai >= mids[-1]:
            w = {bones[-1]: 1.0}
        else:
            j = int(np.searchsorted(mids, ai) - 1)
            u = float((ai - mids[j]) / (mids[j + 1] - mids[j]))
            w = {bones[j]: 1 - u, bones[j + 1]: u}
        for nm, wt in w.items():
            if wt > 1e-4:
                body.vertex_groups[nm].add([int(i)], wt, 'REPLACE')


TEST_POSE = {
    # bone: (axis in the bone's local frame, degrees)
    "Neck1": ('X', 8), "Head": ('X', 12), "Jaw": ('X', -20), "EarL": ('X', -30), "EarR": ('X', 20),
    "Trunk1": ('X', 10), "Trunk2": ('X', 20), "Trunk3": ('X', 25), "Trunk4": ('X', 30), "Trunk5": ('X', 30),
    "UpperArmL": ('X', 30), "ForearmL": ('X', -50), "FrontPawL": ('X', 30),
    "UpperArmR": ('X', -15), "ForearmR": ('X', 8),
    "ThighL": ('X', -20), "ShinL": ('X', 30), "HindFootL": ('X', -15),
    "ThighR": ('X', 18), "ShinR": ('X', -8),
    "Spine2": ('Z', 5), "Chest": ('Z', 5),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
