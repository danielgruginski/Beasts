"""Skinning the hoofed farm animals: deer_rig's recipe for a farm_body.Hoofed species (2026-10-20).

Heat weights on the fused body; the grafted lower legs blend down the leg by height (D units, through W_inv) and
ride like the stump's skin at their seam; extra smoothing round the shoulders and haunches; hooves rigid on the toes,
ears on EarL / EarR, the other shells rigid on Head (or what the species says), the jaw on Jaw with the jowls'
bottoms following it part way.
"""
import numpy as np
import beast_rig
from beast_body import PART, read_info
from beast_rig import clean_weights, weight_report, set_rigid
from beast_common import smoothstep

JOIN_BAND = 0.07


def leg_chain(sp):
    J = sp.J
    return {'F': (("UpperArm", "Forearm", "FrontPaw", "FrontToes"),
                  ((J['ELB'][2], 0.050), (J['WRI'][2], 0.030), (J['FPAW'][2], 0.025))),
            'H': (("Thigh", "Shin", "HindFoot", "HindToes"),
                  ((J['KNEE'][2], 0.050), (J['HOCK'][2], 0.030), (J['HPAW'][2], 0.025)))}


def _jaw_weight(sp):
    jz = sp.JAW_H[0][2]                        # the jaw's top line (head space)
    hz = sp.HINGE_H[2]

    def fn(cu):
        H = sp.hx_inv(cu)
        z = H[:, 2]
        L = sp.HEAD_LEN
        return (0.5 * smoothstep(hz, jz + 0.01, z) * smoothstep(jz - 0.05, jz - 0.01, z) *
                smoothstep(-0.06, -0.12, H[:, 1]) * smoothstep(-0.80 * L, -0.60 * L, H[:, 1]) *
                smoothstep(0.075, 0.05, np.abs(H[:, 0])))
    return fn


def skin(sp, body, rig):
    beast_rig.skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=sp.W_inv, jaw_weight=sp.jaw_weight() or _jaw_weight(sp))
    n = body["n_fur"]
    part, _ = read_info(body)
    _smooth_joins(sp, body, n)
    clean_weights(body)
    ear = np.nonzero(part == PART['ear'])[0]
    x = np.array([body.data.vertices[int(i)].co.x for i in ear])
    set_rigid(body, ear[x > 0], "EarL")
    set_rigid(body, ear[x <= 0], "EarR")
    _skin_legs(sp, body, np.array(list(body["leg_verts"]), int))
    claw = np.nonzero(part == PART['claw'])[0]
    co = np.array([body.data.vertices[int(i)].co[:] for i in claw])
    for front in (True, False):
        for s, sfx in ((1, "L"), (-1, "R")):
            sel = claw[((co[:, 1] < 0) == front) & ((co[:, 0] > 0) == (s > 0))]
            set_rigid(body, sel, ("FrontToes" if front else "HindToes") + sfx)
    _skin_tail(sp, body, part)
    if sp.COAT_ON_TRUNK:
        _coat_on_trunk(sp, body, n)
    sp.skin_extra(body, rig, part)
    clean_weights(body)
    return weight_report(body)


def copy_nearest_skin(body, idx):
    """Shells lying on the skin (the horse's mane and forelock) take the weights of the nearest skin vertex."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    n = body["n_fur"]
    me = body.data
    legs = set(int(i) for i in body.get("leg_verts", []))
    skin_v = [j for j in range(n) if j not in legs]
    kd = KDTree(len(skin_v))
    for j in skin_v:
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


def _skin_tail(sp, body, part):
    """The separate tail tube (sp.TAIL_TUBE) blends along the tail bones by where it lies on the tail's line: Hips
    at the root, Tail1 .. TailN down it."""
    idx = np.nonzero(part == PART['tail'])[0]
    if not len(idx):
        return
    from beast_paint import polyline_t
    co = sp.W_inv(np.array([body.data.vertices[int(i)].co[:] for i in idx]))
    t, _ = polyline_t(co, sp.TAIL)
    nb = len(sp.TAIL) - 1
    for g in body.vertex_groups:
        g.remove([int(i) for i in idx])
    for i, ti in zip(idx, t):
        u = ti * nb                                       # 0 .. nb along the bones
        w = {}
        if u < 0.15:                                      # the root, in the rump
            k = float(smoothstep(-0.05, 0.15, u))
            w = {"Hips": 1 - k, "Tail1": k}
        else:
            j = min(int(u - 0.15 + 0.5), nb - 1)          # blend across each joint
            f = u - j
            if j > 0 and f < 0.5:
                k = float(smoothstep(-0.25, 0.25, f))
                w = {f"Tail{j}": 1 - k, f"Tail{j + 1}": k}
            elif j < nb - 1 and f > 0.5:
                k = float(smoothstep(0.75, 1.25, f))
                w = {f"Tail{j + 1}": 1 - k, f"Tail{j + 2}": k}
            else:
                w = {f"Tail{j + 1}": 1.0}
        for b, wt in w.items():
            if wt > 1e-4:
                body.vertex_groups[b].add([int(i)], wt, 'REPLACE')


def _coat_on_trunk(sp, body, n):
    """A coat over the tops of the legs (the sheep's fleece) rides on the spine, not the legs: skin near a leg's axis
    and below z0 (D) keeps its leg weights; higher up (to z1) or away from the legs (the belly between them) it keeps
    only `least` of them (beast_rig.coat_on_trunk)."""
    z0, z1, least = sp.COAT_ON_TRUNK
    co = sp.W_inv(np.array([body.data.vertices[i].co[:] for i in range(n)]))
    ax, z = np.abs(co[:, 0]), co[:, 2]
    d = np.full(n, 9.0)
    for rows in (sp.FRONT_STUMP_T + sp.FRONT_LEG_T, sp.HIND_STUMP_T + sp.HIND_LEG_T):
        rows = sorted(rows, key=lambda r: -r[2])
        cx, cy = sp.leg_centre(rows, z)                   # the leg's axis at each vertex's height
        d = np.minimum(d, np.hypot(ax - cx, co[:, 1] - cy))
    keep = least + (1 - least) * smoothstep(z1, z0, z) * smoothstep(0.13, 0.07, d)
    keep[np.array(list(body["leg_verts"]), int)] = 1.0
    keep[z < min(sp.SEAM.values()) + 0.02] = 1.0
    trunk = tuple((b, y * sp.KY) for b, y in (("Chest", -0.45), ("Spine2", -0.05), ("Spine1", 0.25), ("Hips", 0.55)))
    beast_rig.coat_on_trunk(body, n, keep, trunk)


def _smooth_joins(sp, body, n):
    J = sp.J
    joins = (((J['SHO'][0], (J['SHO'][1] + J['ELB'][1]) / 2, J['ELB'][2] + 0.10), 0.24 * sp.LEG_T),
             ((J['KNEE'][0], (J['HIP'][1] + J['KNEE'][1]) / 2, J['KNEE'][2] + 0.05), 0.26 * sp.LEG_T))
    co = sp.W_inv(np.array([body.data.vertices[i].co[:] for i in range(n)]))
    near = np.zeros(n, bool)
    for c, r in joins:
        near |= np.linalg.norm((np.stack([np.abs(co[:, 0]), co[:, 1], co[:, 2]], -1) - c), axis=1) < r
    beast_rig.smooth_weights(body, np.nonzero(near)[0], iterations=6, factor=0.5)


def _skin_legs(sp, body, idx):
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    if not len(idx):
        return
    chain = leg_chain(sp)
    n = body["n_fur"]
    me = body.data
    names = {g.index: g.name for g in body.vertex_groups}
    skin_v = sorted(set(range(n)) - set(int(i) for i in idx))
    kd = KDTree(len(skin_v))
    for j in skin_v:
        kd.insert(me.vertices[j].co, j)
    kd.balance()
    co = np.array([me.vertices[int(i)].co[:] for i in idx])
    cd = sp.W_inv(co)
    for g in body.vertex_groups:
        g.remove([int(i) for i in idx])
    for i, p, q in zip(idx, co, cd):
        kind = 'F' if q[1] < 0 else 'H'
        bones, joints = chain[kind]
        sfx = "L" if q[0] > 0 else "R"
        u = [float(smoothstep(zj + w, zj - w, q[2])) for zj, w in joints]
        w = {b + sfx: wt for b, wt in zip(bones, (1 - u[0], u[0] * (1 - u[1]), u[1] * (1 - u[2]), u[2]))}
        k = float(smoothstep(sp.SEAM[kind] - JOIN_BAND, sp.SEAM[kind] - 0.002, q[2]))
        if k > 0:
            skin = {names[g.group]: g.weight for g in me.vertices[kd.find(Vector(p))[1]].groups}
            w = {b: (1 - k) * w.get(b, 0.0) + k * skin.get(b, 0.0) for b in set(w) | set(skin)}
        for b, wt in w.items():
            if wt > 1e-4:
                body.vertex_groups[b].add([int(i)], wt, 'REPLACE')


TEST_POSE = {
    "Neck1": ('X', 10), "Neck2": ('X', 8), "Neck3": ('X', 6), "Head": ('Z', 20), "Jaw": ('X', -25),
    "EarL": ('X', -30), "EarR": ('X', 25), "Tail1": ('X', 30),
    "UpperArmL": ('X', 25), "ForearmL": ('X', 30), "FrontPawL": ('X', -95), "FrontToesL": ('X', -30),
    "UpperArmR": ('X', -20), "ForearmR": ('X', 10),
    "ThighL": ('X', -30), "ShinL": ('X', 45), "HindFootL": ('X', -40),
    "ThighR": ('X', 25), "ShinR": ('X', -10),
    "Spine2": ('Z', 8), "Chest": ('Z', 8),
}


def test_pose(rig):
    import wolf_rig
    wolf_rig.test_pose(rig, TEST_POSE)
