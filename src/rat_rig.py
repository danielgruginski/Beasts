"""Skinning the rat (beast_rig.skin, as the wolf's), plus the tail: a separate shell weighted along its length to the
eight tail bones (two neighbours blended), so it bends smoothly."""
import bpy
import numpy as np
import rat_body as RB
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report, _set_group
from beast_common import smoothstep


def _jaw_weight(cu):
    """The bottom of the jowls follows the jaw part way."""
    x, y, z = cu[:, 0], cu[:, 1], cu[:, 2]
    return smoothstep(0.252, 0.232, z) * smoothstep(-0.405, -0.425, y) * smoothstep(-0.49, -0.47, y)


def _tail_param(cu):
    """Arc position along the tail polyline, in bone units: 0 = Tail1's head, i = Tail(i+1)'s head."""
    P = np.array(RB.TAIL, float)
    best = np.full(len(cu), 1e9)
    t = np.zeros(len(cu))
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        d = b - a
        u = np.clip(((cu - a) @ d) / (d @ d), 0, 1)
        dist = np.linalg.norm(cu - (a + u[:, None] * d), axis=1)
        m = dist < best
        best[m] = dist[m]
        t[m] = i + u[m]
    return t


def skin(body, rig):
    rep = beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=RB.hw_inv, jaw_weight=_jaw_weight)
    n = body["n_fur"]
    part, _ = read_info(body)
    tail = np.nonzero(part == PART['tail'])[0]
    if len(tail):
        co = np.array([body.data.vertices[int(i)].co[:] for i in tail])
        for g in list(body.vertex_groups):
            g.remove([int(i) for i in tail])
        t = _tail_param(co)
        nb = len(RB.TAIL) - 1
        # a vertex at arc position t belongs to bone floor(t); blend toward the next bone over each joint
        k = np.clip(np.floor(t - 0.5), -1, nb - 1).astype(int)
        f = np.clip(t - 0.5 - k, 0, 1)
        for b in range(nb):
            w = np.where(k == b, 1 - f, 0.0) + np.where(k + 1 == b, f, 0.0)
            w[(b == 0) & (k < 0)] = 1.0
            sel = w > 1e-3
            if sel.any():
                _set_group(body, f"Tail{b + 1}", tail[sel], w[sel])
    clean_weights(body)
    return weight_report(body)


TEST_POSE = {
    "Neck1": ('X', 10), "Head": ('Z', 25), "Jaw": ('X', -35), "EarL": ('X', -30), "EarR": ('X', -30),
    "Tail1": ('X', 20), "Tail2": ('Z', 25), "Tail3": ('Z', 25), "Tail4": ('Z', 25), "Tail5": ('Z', 20),
    "UpperArmL": ('X', 40), "ForearmL": ('X', -60), "ThighL": ('X', -30), "ShinL": ('X', 40),
    "Spine2": ('X', 10), "Chest": ('Z', 12),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
