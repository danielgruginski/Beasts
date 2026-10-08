"""Skinning the woolly rhino (beast_rig.skin, as the wolf's), plus its separate shells:

- the coat's clumps and fringes: every vertex takes the weights of the skin at its root (the 'root' attribute), so a
  clump rides on the skin it grows from without stretching;
- the coat above the skirt's hem rides on the spine, not the legs (they swing inside the skirt);
- the spear: 100% on Chest, then split into its own object "Spear" after painting, so the game can hide it;
- the ears (separate funnels) ride on EarL / EarR;
- the chin and lower lip ride on Jaw; the lower cheeks behind the mouth corner follow it part way.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
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


def _read_root(body):
    att = body.data.attributes.get("root")
    buf = np.zeros(len(body.data.vertices) * 3, np.float32)
    if att is not None:
        att.data.foreach_get('vector', buf)
    return buf.reshape(-1, 3)


LEG_BONES = ("UpperArm", "Forearm", "FrontPaw", "FrontToes", "Thigh", "Shin", "HindFoot", "HindToes")
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


def _coat_on_trunk(body, n):
    """Move the leg weights of skin vertices above the skirt's hem onto the trunk bones (split along y)."""
    names = {g.index: g.name for g in body.vertex_groups}
    co = np.array([body.data.vertices[i].co[:] for i in range(n)])
    keep = _leg_share(co)
    ys = np.array([t[1] for t in TRUNK])
    moved = 0
    for i in range(n):
        k = keep[i]
        if k > 0.999:
            continue
        v = body.data.vertices[i]
        leg = [(names[g.group], g.weight) for g in v.groups if names[g.group].startswith(LEG_BONES)]
        if not leg:
            continue
        free = sum(w for _, w in leg) * (1 - k)
        for nm, w in leg:
            body.vertex_groups[nm].add([i], w * k, 'REPLACE')
        y = co[i, 1]
        j = int(np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2))
        t = float(np.clip((y - ys[j]) / (ys[j + 1] - ys[j]), 0, 1))
        for nm, w in ((TRUNK[j][0], free * (1 - t)), (TRUNK[j + 1][0], free * t)):
            if w > 1e-4:
                g = body.vertex_groups[nm]
                try:
                    w0 = g.weight(i)
                except RuntimeError:
                    w0 = 0.0
                g.add([i], w0 + w, 'REPLACE')
        moved += 1
    return moved


def skin(body, rig):
    rep = beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=None, jaw_weight=_jaw_weight)
    n = body["n_fur"]
    part, _ = read_info(body)
    _coat_on_trunk(body, n)
    clean_weights(body)
    names = {g.index: g.name for g in body.vertex_groups}
    # clumps and fringes: the weights of the nearest skin vertex to their root
    hair = np.nonzero(part == PART['hair'])[0]
    if len(hair):
        kd = KDTree(n)
        for i in range(n):
            kd.insert(body.data.vertices[i].co, i)
        kd.balance()
        roots = _read_root(body)
        src = {}
        for i in hair:
            _, j, _ = kd.find(Vector(roots[i]))
            src[int(i)] = j
        weights = {j: [(names[g.group], g.weight) for g in body.data.vertices[j].groups] for j in set(src.values())}
        for g in body.vertex_groups:
            g.remove([int(i) for i in hair])
        for i, j in src.items():
            for nm, w in weights[j]:
                body.vertex_groups[nm].add([i], w, 'REPLACE')
    ear = np.nonzero(part == PART['ear'])[0]
    if len(ear):
        co = np.array([body.data.vertices[int(i)].co[:] for i in ear])
        for g in body.vertex_groups:
            g.remove([int(i) for i in ear])
        _set_group(body, "EarL", ear[co[:, 0] > 0], np.ones(int((co[:, 0] > 0).sum())))
        _set_group(body, "EarR", ear[co[:, 0] <= 0], np.ones(int((co[:, 0] <= 0).sum())))
    spear = np.nonzero(part == PART['spear'])[0]
    if len(spear):
        for g in body.vertex_groups:
            g.remove([int(i) for i in spear])
        _set_group(body, SPEAR_BONE, spear, np.ones(len(spear)))
    clean_weights(body)
    return weight_report(body)


def split_spear(body, rig, name="Spear"):
    """Separate the spear's faces into their own object (same rig, material and UVs), named Spear."""
    from beast_common import remove_obj
    remove_obj(name)
    part, _ = read_info(body)
    sel = part == PART['spear']
    if not sel.any():
        return None
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    body.hide_set(False)
    vl.objects.active = body
    body.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')              # the unwrap left everything selected
    bm = bmesh.from_edit_mesh(body.data)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.select = bool(sel[v.index])
    bm.select_flush(True)
    bmesh.update_edit_mesh(body.data)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    sp = next(o for o in bpy.context.selected_objects if o is not body)
    sp.name = name
    sp.data.name = name
    for g in list(sp.vertex_groups):                 # only the spear bone is used
        if g.name != SPEAR_BONE:
            sp.vertex_groups.remove(g)
    for k in [k for k in sp.keys()]:
        del sp[k]
    return {"verts": len(sp.data.vertices), "tris": sum(len(p.vertices) - 2 for p in sp.data.polygons)}


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
