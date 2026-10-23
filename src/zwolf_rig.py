"""Skinning the zombie wolf to its armature (beast_rig.build_armature(wolf_body.rest_bones()): the wolf's skeleton).

- Fur body: the wolf's (wolf_rig): heat-map weights from the body bones, smoothed, 4 influences; the jaw, tongue and
  lower teeth rigid on Jaw / Tongue1-2, the eyes, nose and upper teeth on Head, the jowls' bottom following the jaw.
- Rib bars (PART['bone']): the weights of the nearest skin vertex (the cavity they lie in), so they ride with it.
"""
import numpy as np
from mathutils.kdtree import KDTree
import beast_rig
from beast_rig import clean_weights, weight_report
from beast_body import read_info, PART
from beast_common import smoothstep
import wolf_rig
import zwolf_body as Z

NO_HEAT = wolf_rig.NO_HEAT
test_pose = wolf_rig.test_pose
reset_pose = wolf_rig.reset_pose


def skin(body, rig):
    beast_rig.skin(body, rig, NO_HEAT, Z.hw_inv, tongue_t=lambda cu: smoothstep(-0.81, -0.87, cu[:, 1]),
                   jaw_weight=wolf_rig._jaw_weight)
    part, _ = read_info(body)
    copy_nearest_skin(body, np.nonzero(part == PART['bone'])[0])
    clean_weights(body)
    return weight_report(body)


def copy_nearest_skin(body, idx):
    """Shells lying in or on the skin take the weights of the nearest fur vertex."""
    if not len(idx):
        return
    n = body["n_fur"]
    me = body.data
    kd = KDTree(n)
    for j in range(n):
        kd.insert(me.vertices[j].co, j)
    kd.balance()
    names = {g.index: g.name for g in body.vertex_groups}
    src = {int(i): [(names[g.group], g.weight) for g in me.vertices[kd.find(me.vertices[int(i)].co)[1]].groups]
           for i in idx}
    for g in body.vertex_groups:
        g.remove([int(i) for i in idx])
    for i, ws in src.items():
        for b, w in ws:
            body.vertex_groups[b].add([i], w, 'REPLACE')
