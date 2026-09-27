"""Armature for the beasts (Unity Generic rig) and the pose math the clips are keyed with.

The bone table comes from the creature module (wolf_body.rest_bones()): name -> (head, frame, length, parent,
deform). Clips are not posed through constraints: each frame, the animation code computes where every bone should
be (armature space) and `apply_pose` converts that to matrix_basis and keys it. Nothing needs baking on export.
"""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from beast_common import get_coll, remove_obj

RIG = "WolfRig"


def build_armature(table, name=RIG, coll_name="WLF_Rig"):
    coll = get_coll(coll_name)
    remove_obj(name)
    ad = bpy.data.armatures.get(name)
    if ad is not None and ad.users == 0:
        bpy.data.armatures.remove(ad)
    ad = bpy.data.armatures.new(name)
    ad.display_type = 'OCTAHEDRAL'
    ob = bpy.data.objects.new(name, ad)
    coll.objects.link(ob)
    ob.show_in_front = True
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    vl.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    for n, (h, fr, L, par, deform) in table.items():
        b = eb.new(n)
        b.head = h
        b.tail = h + fr.col[1] * L
        b.align_roll(fr.col[2])
        b.use_deform = deform or n.startswith("Socket_")      # sockets export as (unweighted) deform bones
    for n, (h, fr, L, par, deform) in table.items():
        if par:
            eb[n].parent = eb[par]
            eb[n].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    legs = ("Scapula", "UpperArm", "Forearm", "FrontPaw", "FrontToes", "Thigh", "Shin", "HindFoot", "HindToes")
    cols = {c: ad.collections.new(c) for c in ("Body", "Legs", "Head", "Tail", "Sockets")}
    for b in ad.bones:
        n = b.name
        if n.startswith("Socket_"):
            cols["Sockets"].assign(b)
            b.color.palette = 'THEME09'
        elif n.startswith(legs):
            cols["Legs"].assign(b)
            b.color.palette = 'THEME03' if n.endswith("L") else 'THEME04'
        elif n.startswith(("Head", "Jaw", "Tongue", "Ear")):
            cols["Head"].assign(b)
            b.color.palette = 'THEME06'
        elif n.startswith("Tail"):
            cols["Tail"].assign(b)
            b.color.palette = 'THEME07'
        else:
            cols["Body"].assign(b)
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return ob


def bind(mesh, rig):
    """Parent with an Armature modifier; the vertex groups (named after bones) are already on the mesh."""
    for m in [m for m in mesh.modifiers if m.type == 'ARMATURE']:
        mesh.modifiers.remove(m)
    mesh.parent = rig
    mesh.matrix_parent_inverse = rig.matrix_world.inverted()
    mod = mesh.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    return weight_report(mesh)


# ----------------------------------------------------------------------------------------- skinning
def _set_group(ob, name, idx, w):
    g = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    for i, wi in zip(idx, w):
        g.add([int(i)], float(wi), 'REPLACE')


def smooth_weights(ob, verts, iterations=3, factor=0.5):
    """Laplacian smoothing of all vertex groups over the mesh edges, on the given vertices only."""
    me = ob.data
    V, G = len(me.vertices), len(ob.vertex_groups)
    Wt = np.zeros((V, G))
    for v in me.vertices:
        for g in v.groups:
            Wt[v.index, g.group] = g.weight
    e = np.array([ed.vertices[:] for ed in me.edges])
    keep = np.zeros(V, bool)
    keep[verts] = True
    e = e[keep[e[:, 0]] & keep[e[:, 1]]]
    deg = np.bincount(e.ravel(), minlength=V).astype(float)
    for _ in range(iterations):
        acc = np.zeros_like(Wt)
        np.add.at(acc, e[:, 0], Wt[e[:, 1]])
        np.add.at(acc, e[:, 1], Wt[e[:, 0]])
        Wn = np.where(deg[:, None] > 0, (1 - factor) * Wt + factor * acc / np.maximum(deg, 1)[:, None], Wt)
        Wt = np.where(keep[:, None], Wn, Wt)
    Wt /= np.maximum(Wt.sum(1), 1e-9)[:, None]
    for gi, g in enumerate(ob.vertex_groups):
        g.remove([int(i) for i in verts])
        nz = [int(i) for i in verts if Wt[i, gi] > 1e-4]
        for i in nz:
            g.add([i], float(Wt[i, gi]), 'REPLACE')


def clean_weights(ob, limit=4):
    """Unity skins with up to 4 influences: keep the strongest, drop dust, normalise."""
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        ws = sorted(((g.weight, g.group) for g in v.groups), reverse=True)
        for i, (w, gi) in enumerate(ws):
            if i >= limit or w < 0.01:
                ob.vertex_groups[names[gi]].remove([v.index])
        tot = sum(g.weight for g in v.groups)
        if tot > 0:
            for g in v.groups:
                g.weight /= tot


def weight_report(ob):
    zero = sum(1 for v in ob.data.vertices if sum(g.weight for g in v.groups) < 1e-4)
    over = sum(1 for v in ob.data.vertices if len(v.groups) > 4)
    dots = [g.name for g in ob.vertex_groups if "." in g.name]
    return {"verts": len(ob.data.vertices), "unweighted": zero, "over4": over, "groups": len(ob.vertex_groups),
            "bad_group_names": dots}


def skin(body, rig, no_heat=("Root", "Motion", "Jaw"), unwarp=None, tongue_t=None, jaw_weight=None):
    """Heat-map weights for the fur body from the body bones (not no_heat, not sockets), smoothed; the separate
    pieces rigid (info.g = on the jaw -> Jaw, the rest -> Head; tongue blended Tongue1 -> Tongue2 by tongue_t(cu));
    jaw_weight(cu_fur) -> how much each fur vertex follows the jaw (the jowls). 4 influences max."""
    from beast_body import read_info, PART
    from beast_common import smoothstep
    n = body["n_fur"]
    part, on_jaw = read_info(body)
    ad = rig.data
    keep = {b.name: b.use_deform for b in ad.bones}
    for b in ad.bones:
        b.use_deform = keep[b.name] and not (b.name in no_heat or b.name.startswith("Socket_"))
    body.vertex_groups.clear()
    for m in [m for m in body.modifiers if m.type == 'ARMATURE']:
        body.modifiers.remove(m)
    body.parent = None
    for o in bpy.context.selected_objects:
        o.select_set(False)
    body.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for nm, d in keep.items():
        ad.bones[nm].use_deform = d

    V = len(body.data.vertices)
    co = np.array([v.co[:] for v in body.data.vertices])
    cu = unwarp(co) if unwarp is not None else co
    idx_extra = np.arange(n, V)
    for g in list(body.vertex_groups):                 # the separate pieces: rigid
        g.remove([int(i) for i in idx_extra])
    pe = part[n:]
    jaw = idx_extra[on_jaw[n:] & (pe != PART['tongue'])]
    tongue = idx_extra[pe == PART['tongue']]
    head = idx_extra[~on_jaw[n:]]
    _set_group(body, "Jaw", jaw, np.ones(len(jaw)))
    _set_group(body, "Head", head, np.ones(len(head)))
    if len(tongue) and tongue_t is not None:           # tongue: blend Tongue1 -> Tongue2 along its length
        t = tongue_t(cu[tongue])
        _set_group(body, "Tongue1", tongue, 1 - t)
        _set_group(body, "Tongue2", tongue, t)

    fur = np.arange(n)
    smooth_weights(body, fur, iterations=3, factor=0.5)
    if jaw_weight is not None:
        wj = jaw_weight(cu[:n])
        sel = np.nonzero(wj > 0.01)[0]
        if len(sel):
            for g in body.vertex_groups:
                for i in sel:
                    try:
                        w0 = g.weight(int(i))
                    except RuntimeError:
                        continue
                    g.add([int(i)], w0 * (1 - wj[i]), 'REPLACE')
            _set_group(body, "Jaw", sel, wj[sel])
    clean_weights(body)
    return weight_report(body)


# ----------------------------------------------------------------------------------------- pose math
def rest(rig):
    return {b.name: b.matrix_local.copy() for b in rig.data.bones}


def to_basis(rig, desired, R=None):
    """Armature-space matrices for some bones -> matrix_basis for every bone. Bones not in `desired` keep their
    rest pose relative to their parent."""
    R = R or rest(rig)
    world = {}
    basis = {}
    for b in sorted(rig.data.bones, key=lambda b: len(b.parent_recursive)):     # parents before children
        n = b.name
        if b.parent is None:
            parent_now = Matrix.Identity(4)
            rel = R[n]
        else:
            p = b.parent.name
            parent_now = world[p]
            rel = R[p].inverted() @ R[n]
        if n in desired:
            world[n] = desired[n]
            basis[n] = (parent_now @ rel).inverted() @ desired[n]
        else:
            world[n] = parent_now @ rel
            basis[n] = Matrix.Identity(4)
    return basis, world


def apply_pose(rig, desired, frame=None, R=None, keys=True):
    basis, world = to_basis(rig, desired, R)
    for n, m in basis.items():
        pb = rig.pose.bones[n]
        loc, rot, _ = m.decompose()
        pb.location = loc
        q = rot
        if keys and frame is not None and pb.rotation_quaternion.dot(q) < 0:
            q = -q                      # keep quaternions on one hemisphere so the curves don't flip
        pb.rotation_quaternion = q
        pb.scale = (1, 1, 1)
        if keys and frame is not None:
            pb.keyframe_insert("location", frame=frame, group=n)
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=n)
    return world


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def frame_matrix(head, frame3):
    return Matrix.Translation(Vector(head)) @ frame3.to_4x4()
