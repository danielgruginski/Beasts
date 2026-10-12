"""Rig and skin weights for the dungeon ooze (Unity Generic, the beasts' conventions: Root and Motion point up with
+Z toward the front, Motion carries the root motion, sockets are unweighted deform bones with +Y up, +Z forward).

Bones (41):
  Root, Motion
  Body                 the mass, on the floor at the centre; never scaled non-uniformly (it has children)
    Dome               the upper mass: squash, stretch and lean (a leaf, so Unity never sees a sheared child)
    Tail               the uroid at the rear
    <Pod>1..3          each pseudopod's chain, along its POD control points (Reach, Lead, Side, Back, Bud, Probe)
    Gut                the contents' carrier
      Nucleus, Skull, Femur, Shin, Helm, Sword, Coins, Vac1..7     one per floating piece (rigid)
      Socket_Gut       where a swallowed victim is held
    Socket_Mouth       in front, where a grabbed victim is held (Engulf moves it into the body)
  Probe3 > Socket_Spit the acid glob leaves here

Shell weights: each vertex belongs to the mass or a pod by a soft minimum over ooze_body.parts(); along a pod it
blends linearly between the bones' middles (hat weights on the chain parameter), so moving a child bone stretches
the whole segment rather than a crease; in the mass it is Dome by height (DOME_Z), Tail near the uroid, else Body.
Smoothed over the mesh, 4 influences.
"""
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix

import beast_rig
from beast_common import smoothstep, get_coll
import ooze_body as OB

RIG = "OozeRig"
UP, FWD = Vector((0, 0, 1)), Vector((0, -1, 0))
PODS = list(OB.POD)
DOME_HEAD = Vector((0, 0.05, 0.0))
DOME_Z = (0.12, 0.50)                 # the mass is Body below, Dome above (smoothstep)
SIGMA = 0.06                          # soft minimum between pieces (m)
PIECE_BONE = (("nucleus", "Nucleus"), ("skull", "Skull"), ("femur", "Femur"), ("shin", "Shin"), ("helm", "Helm"),
              ("sword", "Sword"), ("coin", "Coins"), ("vac", "Vac"))
POD_X = {"Probe": Vector((1, 0, 0))}  # bend axis given directly (it rises and curls forward); the rest: up hint


def _frame(ydir, zhint=None, xaxis=None):
    y = Vector(ydir).normalized()
    if xaxis is not None:
        x = Vector(xaxis)
        x = (x - y * x.dot(y)).normalized()
        z = x.cross(y)
    else:
        z = Vector(zhint)
        z = (z - y * z.dot(y)).normalized()
        x = y.cross(z)
    return Matrix((x, y, z)).transposed()


def _bone(B, name, head, tail, parent, zhint=FWD, xaxis=None, deform=True):
    head, tail = Vector(head), Vector(tail)
    B[name] = (head, _frame(tail - head, zhint, xaxis), (tail - head).length, parent, deform)


def piece_centres(cont):
    """Centroid of each content piece (from the `piece` face attribute and ob["pieces"])."""
    me = cont.data
    names = list(cont["pieces"])
    piece = np.empty(len(me.polygons), np.int32)
    me.attributes["piece"].data.foreach_get("value", piece)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    out = {}
    for k, nm in enumerate(names):
        vs = sorted({v for p in np.where(piece == k)[0] for v in me.polygons[p].vertices})
        out[nm] = co[vs].mean(0)
    return out


def piece_bone(name):
    """Content piece name (skull, coin3, vac5, sword2...) -> its bone."""
    for key, bone in PIECE_BONE:
        if name.startswith(key):
            return bone + str(int(name[len(key):]) + 1) if key == "vac" else bone
    raise KeyError(name)


def rest_bones(cont):
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.4, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.3, None, True)
    _bone(B, "Body", (0, 0.05, 0.0), (0, 0.05, 0.45), "Root")
    _bone(B, "Dome", DOME_HEAD, DOME_HEAD + Vector((0, 0, 1.0)), "Body")
    _bone(B, "Tail", (0, 0.78, 0.13), (0, 1.10, 0.06), "Body", zhint=UP)
    for name, pod in OB.POD.items():
        pts = [Vector(p[:3]) for p in pod["pts"]]
        par = "Body"
        for i in range(3):
            n = f"{name}{i + 1}"
            _bone(B, n, pts[i], pts[i + 1], par, zhint=UP, xaxis=POD_X.get(name))
            par = n
    _bone(B, "Gut", (0, 0.1, 0.30), (0, 0.1, 0.60), "Body")
    centres = piece_centres(cont)
    groups = {}
    for nm, c in centres.items():
        groups.setdefault(piece_bone(nm), []).append(c)
    for bone, cs in groups.items():
        h = Vector(np.mean(cs, 0))
        _bone(B, bone, h, h + Vector((0, 0, 0.12)), "Gut")
    g = Vector((0.0, 0.05, 0.45))
    _bone(B, "Socket_Gut", g, g + Vector((0, 0, 0.1)), "Gut")
    m = Vector((0.0, -1.10, 0.40))
    _bone(B, "Socket_Mouth", m, m + Vector((0, 0, 0.1)), "Body")
    p = OB.POD["Probe"]["pts"]
    tip = Vector(p[3][:3]) + (Vector(p[3][:3]) - Vector(p[2][:3])).normalized() * p[3][3]
    _bone(B, "Socket_Spit", tip, tip + Vector((0, 0, 0.1)), "Probe3")
    return B


def build(scn=None):
    cont = bpy.data.objects["OozeContents"]
    arm = beast_rig.build_armature(rest_bones(cont), name=RIG, coll_name="OOZ_Rig")
    arm.hide_render = True
    return arm


def _chain_t(P, pts):
    """Chain parameter 0..3 of points P along the control polyline pts (nearest segment)."""
    best = np.full(len(P), 1e9)
    t = np.zeros(len(P))
    for i in range(3):
        a, b = np.asarray(pts[i][:3]), np.asarray(pts[i + 1][:3])
        ab = b - a
        u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(P - (a + u[:, None] * ab), axis=1)
        m = d < best
        best[m] = d[m]
        t[m] = i + u[m]
    return t


def shell_weights(P):
    """bone -> weight array for shell vertices P (N, 3)."""
    D = OB.parts(P)
    names = ["mass"] + PODS
    Dm = np.stack([D[k] for k in names], 1)
    E = np.exp(-(Dm - Dm.min(1, keepdims=True)) / SIGMA)
    E /= E.sum(1, keepdims=True)
    W = {}
    add = lambda b, w: W.__setitem__(b, W.get(b, 0) + w)
    for k, name in enumerate(PODS):
        t = _chain_t(P, OB.POD[name]["pts"])
        hats = np.stack([np.clip(1 - np.abs(t - (j + 0.5)), 0, 1) for j in range(3)], 1)
        hats[t < 0.5, 0] = 1
        hats[t > 2.5, 2] = 1
        hats /= hats.sum(1, keepdims=True)
        for j in range(3):
            add(f"{name}{j + 1}", E[:, k + 1] * hats[:, j])
    du = np.min(np.stack([np.linalg.norm(P - np.asarray(c), axis=1) - r for c, r in OB.UROID], 1), 1)
    tail = 1 - smoothstep(0.02, 0.22, du)
    dome = smoothstep(DOME_Z[0], DOME_Z[1], P[:, 2])
    add("Tail", E[:, 0] * tail)
    add("Dome", E[:, 0] * (1 - tail) * dome)
    add("Body", E[:, 0] * (1 - tail) * (1 - dome))
    return W


FLOOR_BAND = (0.02, 0.16)             # below this the shell is Body's (and the floor pods'): the rim stays on the floor
LIFTERS = ("Dome", "Reach", "Side", "Probe")    # bones that move things up and down


def _pin_floor(body, co):
    """Hand the lifting bones' weights near the floor to Body (after smoothing, which spreads Dome and the raised
    pods down to the rim: it rose 15 cm off the floor in Crawl)."""
    keep = smoothstep(FLOOR_BAND[0], FLOOR_BAND[1], co[:, 2])
    groups = {g.index: g.name for g in body.vertex_groups}
    gb = body.vertex_groups.get("Body") or body.vertex_groups.new(name="Body")
    for v in body.data.vertices:
        k = float(keep[v.index])
        if k >= 1.0:
            continue
        moved = 0.0
        for g in v.groups:
            if groups[g.group].startswith(LIFTERS):
                moved += g.weight * (1 - k)
                g.weight *= k
        if moved > 0:
            old = next((g.weight for g in v.groups if g.group == gb.index), 0.0)
            gb.add([v.index], old + moved, 'REPLACE')


def skin(body, cont, rig):
    """Weights for the shell (soft pieces, smoothed) and the contents (rigid per piece); bind both."""
    for ob in (body, cont):
        ob.vertex_groups.clear()
    co = np.array([v.co[:] for v in body.data.vertices])
    for bone, w in shell_weights(co).items():
        idx = np.where(w > 1e-3)[0]
        beast_rig._set_group(body, bone, idx, w[idx])
    beast_rig.smooth_weights(body, list(range(len(co))), iterations=3, factor=0.5)
    _pin_floor(body, co)
    beast_rig.clean_weights(body)
    me = cont.data
    names = list(cont["pieces"])
    piece = np.empty(len(me.polygons), np.int32)
    me.attributes["piece"].data.foreach_get("value", piece)
    per_bone = {}
    for p in me.polygons:
        per_bone.setdefault(piece_bone(names[piece[p.index]]), set()).update(p.vertices)
    for bone, vs in per_bone.items():
        vs = sorted(vs)
        beast_rig._set_group(cont, bone, vs, [1.0] * len(vs))
    return {"shell": beast_rig.bind(body, rig), "contents": beast_rig.bind(cont, rig)}
