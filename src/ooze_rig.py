"""Rig and skin weights for the dungeon ooze (Unity Generic, the beasts' conventions: Root and Motion point up with
+Z toward the front, Motion carries the root motion, sockets are unweighted deform bones with +Y up, +Z forward).

Bones (47):
  Root, Motion
  Body                 the mass, on the floor at the centre; never scaled non-uniformly (it has children)
    HalfL, HalfR       the mass's left (+X) and right halves: they part when it divides (Split); nothing else moves them
      DomeL, DomeR     each half's upper mass: squash, stretch and lean (leaves, so Unity never sees a sheared child;
                       both sit where one Dome bone did and take the same dome transform in every clip)
      <Pod>1..3        each pseudopod's chain on its side's half (Reach, Back, Bud left; Lead, Side, Probe right)
    WaistTop, WaistLow the middle band (upper with the dome, lower on the floor): pinched thin as the halves part
    Tail               the uroid at the rear
    Gut                the contents' carrier
      Nucleus, Nucleus2, Skull, Femur, Shin, Helm, Sword, Coins, Vac1..7     one per floating piece (rigid; Nucleus2,
                       the twin hidden inside the nucleus, follows it except when it divides)
      Socket_Gut       where a swallowed victim is held
    Socket_Mouth       in front, where a grabbed victim is held (Engulf moves it into the body)
  Probe3 > Socket_Spit the acid glob leaves here

Shell weights: each vertex belongs to the mass or a pod by a soft minimum over ooze_body.parts(); along a pod it
blends linearly between the bones' middles (hat weights on the chain parameter), so moving a child bone stretches
the whole segment rather than a crease. In the mass: Tail near the uroid; the rest is upper (Dome*) or lower (Half*)
by height (DOME_Z), split left/right across the middle (SIDE_W), with the middle band partly on the Waist bones
(WAIST). Smoothed over the mesh, 4 influences; near the floor nothing that lifts keeps a share (_pin_floor).
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
DOME_Z = (0.12, 0.50)                 # the mass is Half* below, Dome* above (smoothstep)
SIGMA = 0.06                          # soft minimum between pieces (m)
SIDE_W = 0.22                         # the left/right blend across x = 0 (+-, m)
WAIST = (1.0, 0.02, 0.32)            # the middle band's share on the Waist bones: peak, then fading out over |x|
                                      # (at 0.7 the middle kept 30% of its height in Split: a saddle, no strand)
HALF_X = 0.42                         # the halves' pivots (+-x)
SIDE = {"Reach": "L", "Back": "L", "Bud": "L", "Lead": "R", "Side": "R", "Probe": "R"}
DOMES = ("DomeL", "DomeR", "WaistTop")   # bones that take the dome transform
PIECE_BONE = (("nucleus2", "Nucleus2"), ("nucleus", "Nucleus"), ("skull", "Skull"), ("femur", "Femur"), ("shin", "Shin"), ("helm", "Helm"),
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
    for s, sx in (("L", 1), ("R", -1)):
        h = Vector((sx * HALF_X, 0.05, 0.0))
        _bone(B, "Half" + s, h, h + Vector((0, 0, 0.4)), "Body")
        _bone(B, "Dome" + s, DOME_HEAD, DOME_HEAD + Vector((0, 0, 1.0)), "Half" + s)
    _bone(B, "WaistTop", DOME_HEAD, DOME_HEAD + Vector((0, 0, 0.8)), "Body")
    _bone(B, "WaistLow", DOME_HEAD, DOME_HEAD + Vector((0, 0, 0.3)), "Body")
    _bone(B, "Tail", (0, 0.78, 0.13), (0, 1.10, 0.06), "Body", zhint=UP)
    for name, pod in OB.POD.items():
        pts = [Vector(p[:3]) for p in pod["pts"]]
        par = "Half" + SIDE[name]
        for i in range(3):
            n = f"{name}{i + 1}"
            _bone(B, n, pts[i], pts[i + 1], par, zhint=UP, xaxis=POD_X.get(name))
            par = n
    _bone(B, "Gut", (0, 0.1, 0.30), (0, 0.1, 0.60), "Body")
    centres = piece_centres(cont)
    groups = {}
    for nm, c in centres.items():
        groups.setdefault(piece_bone(nm), []).append(c)
    heads = {bone: Vector(np.mean(cs, 0)) for bone, cs in groups.items()}
    heads["Nucleus2"] = heads["Nucleus"]          # same pivot: it copies the nucleus's motion exactly
    for bone, h in heads.items():
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
    left, waist = _side_shares(P)
    up, low = E[:, 0] * (1 - tail) * dome, E[:, 0] * (1 - tail) * (1 - dome)
    add("Tail", E[:, 0] * tail)
    add("DomeL", up * (1 - waist) * left)
    add("DomeR", up * (1 - waist) * (1 - left))
    add("WaistTop", up * waist)
    add("HalfL", low * (1 - waist) * left)
    add("HalfR", low * (1 - waist) * (1 - left))
    add("WaistLow", low * waist)
    return W


def _side_shares(P):
    """-> (share of the left half, share of the middle band on the Waist bones) for points P."""
    left = smoothstep(-SIDE_W, SIDE_W, P[:, 0])
    waist = WAIST[0] * (1 - smoothstep(WAIST[1], WAIST[2], np.abs(P[:, 0])))
    return left, waist


WAIST_CORE = (0.06, 0.32)             # after smoothing: the middle band is all Waist inside 0.06, none past 0.32


def _waist_pass(body, co):
    """Re-split each vertex's mass weights after smoothing (which diluted the middle band, so Split left a saddle
    instead of a strand): the upper share over DomeL / DomeR / WaistTop, the lower over HalfL / HalfR / WaistLow, by
    WAIST_CORE and side. A vertex that is mostly pod takes its pod's side and no waist (else the Probe, a right pod
    whose base reaches x 0.22, and the left dome stretched a membrane across the gap). The dome bones move together
    and so do the lower ones in every clip but Split, so the other clips are unchanged."""
    groups = {g.index: g.name for g in body.vertex_groups}
    vg = {n: body.vertex_groups.get(n) or body.vertex_groups.new(name=n)
          for n in ("DomeL", "DomeR", "WaistTop", "HalfL", "HalfR", "WaistLow")}
    x = co[:, 0]
    core = 1 - smoothstep(WAIST_CORE[0], WAIST_CORE[1], np.abs(x))
    left_x = smoothstep(-SIDE_W, SIDE_W, x)
    for v in body.data.vertices:
        w = {groups[g.group]: g.weight for g in v.groups}
        up = w.get("DomeL", 0) + w.get("DomeR", 0) + w.get("WaistTop", 0)
        low = w.get("HalfL", 0) + w.get("HalfR", 0) + w.get("WaistLow", 0)
        if up + low < 1e-4:
            continue
        podL = sum(wt for n, wt in w.items() if n[:-1] in SIDE and SIDE[n[:-1]] == "L")
        podR = sum(wt for n, wt in w.items() if n[:-1] in SIDE and SIDE[n[:-1]] == "R")
        i = v.index
        if podL + podR > 0.4 and abs(podL - podR) > 0.15:
            wa, left = 0.0, 1.0 if podL > podR else 0.0
        else:
            wa, left = float(core[i]), float(left_x[i])
        for total, (a, b, c) in ((up, ("DomeL", "DomeR", "WaistTop")), (low, ("HalfL", "HalfR", "WaistLow"))):
            for n, s in ((a, (1 - wa) * left), (b, (1 - wa) * (1 - left)), (c, wa)):
                if total * s > 1e-4:
                    vg[n].add([i], total * s, 'REPLACE')
                elif n in w:
                    vg[n].remove([i])


FLOOR_BAND = (0.02, 0.16)            # below this the shell is on the lower mass (and the floor pods): the rim stays down
LIFTERS = ("Dome", "WaistTop", "Reach", "Side", "Probe")    # bones that move things up and down


def _pin_floor(body, co):
    """Hand the lifting bones' weights near the floor to the lower mass, by side (after smoothing, which spreads the
    domes and the raised pods down to the rim: it rose 15 cm off the floor in Crawl)."""
    keep = smoothstep(FLOOR_BAND[0], FLOOR_BAND[1], co[:, 2])
    left, waist = _side_shares(co)
    groups = {g.index: g.name for g in body.vertex_groups}
    low = {n: body.vertex_groups.get(n) or body.vertex_groups.new(name=n) for n in ("HalfL", "HalfR", "WaistLow")}
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
            i = v.index
            share = {"HalfL": (1 - waist[i]) * left[i], "HalfR": (1 - waist[i]) * (1 - left[i]), "WaistLow": waist[i]}
            for n, s in share.items():
                if s > 1e-4:
                    old = next((g.weight for g in v.groups if g.group == low[n].index), 0.0)
                    low[n].add([i], old + moved * float(s), 'REPLACE')


def skin(body, cont, rig):
    """Weights for the shell (soft pieces, smoothed) and the contents (rigid per piece); bind both."""
    for ob in (body, cont):
        ob.vertex_groups.clear()
    co = np.array([v.co[:] for v in body.data.vertices])
    for bone, w in shell_weights(co).items():
        idx = np.where(w > 1e-3)[0]
        beast_rig._set_group(body, bone, idx, w[idx])
    beast_rig.smooth_weights(body, list(range(len(co))), iterations=3, factor=0.5)
    _waist_pass(body, co)
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
