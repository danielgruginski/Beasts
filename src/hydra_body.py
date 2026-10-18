"""The hydra (2026-10-17). Daniel: "how about an hydra monster? Like the dragon, but more aquatic like, no spikes, no
wings, two or three heads". A low, long-bodied water beast -- a giant newt more than a dragon -- on four short,
sprawled legs with webbed feet, a flat paddle tail with a smooth fin, and two or three eel-like heads on long
necks branching from the chest. About 11 m from the middle snout to the tail tip, 1.8 m at the shoulder.

Stage 1 is a blockout, as the dragon's was: the skeleton plus rough volumes skinned to it, to judge proportions
(and two heads against three) before the melted body and heads go on. Trunk and tail are one loft with chain
weights; each neck is its own loft weighted along its own chain; legs are rigid segments per bone.

Coordinates: metres, Z up, the hydra faces -Y, its left side is +X (beast_common). Left side written, right
mirrored. Bones: the quadrupeds' names (Hips, Spine1, Spine2, Chest, Tail1.., Scapula/UpperArm/Forearm/FrontPaw/
FrontToes, Thigh/Shin/HindFoot/HindToes, Root, Motion); the middle neck is Neck1..7 + Head + Jaw (beast_anim's
chain), the side necks Neck1L..7L + HeadL + JawL and the R mirror.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from beast_common import loft, cone, spline, get_coll, srgb_to_lin, hexc
import dragon_body as DB
from dragon_body import Acc, chain_weights, _bones_of, _bone, _seg, _claw, _curve

RIG = "HydraRig"
COLL = "HYD_Blockout"
SIDES = DB.SIDES
UP, FWD = (0, 0, 1), (0, -1, 0)
HEADS = 3                         # 3 or 2 (Daniel: "two or three heads"; both rendered for him to choose)

# ----------------------------------------------------------------------------------------- proportions
NECK_N, TAIL_N = 7, 12
SPINE = dict(pelvis=(0, 1.10, 1.55), hips_end=(0, 1.50, 1.50), spine2=(0, 0.15, 1.64), chest=(0, -0.75, 1.68),
             neck_base=(0, -1.45, 1.74))
TAIL_CTRL = ((0, 1.50, 1.50), (0, 2.40, 1.30), (0, 3.40, 1.05), (0, 4.40, 0.80), (0, 5.40, 0.58), (0, 6.30, 0.42),
             (0, 7.00, 0.35))
TAIL_RATIO = 0.94
# necks (left / middle): base inside the chest's front, rising in a soft S; the side necks splay out
NECKS3 = {"": ((0, -1.40, 1.85), (0, -1.95, 2.40), (0, -2.35, 3.00), (0, -2.65, 3.50), (0, -2.98, 3.82)),
          "L": ((0.42, -1.35, 1.80), (0.66, -1.85, 2.28), (0.96, -2.22, 2.80), (1.24, -2.50, 3.20),
                (1.42, -2.78, 3.42))}
NECKS2 = {"L": ((0.30, -1.38, 1.82), (0.48, -1.90, 2.36), (0.70, -2.30, 2.92), (0.90, -2.60, 3.38),
                (1.02, -2.92, 3.66))}
HEAD_FWD = {3: {"": (0, -1.0, -0.12), "L": (0.30, -1.0, -0.16)},    # where each head points (left; R mirrored)
            2: {"L": (0.18, -1.0, -0.14)}}
NECK_R = (0.44, 0.24)             # neck radius at the base and at the head

# head, local frame: origin at the back of the skull, -Y forward, +Z up; placed at its neck's end (head_matrix)
SKULL = ((0, 0.10, 0.02, 0.21, 0.20, 0.22), (0, -0.15, 0.04, 0.26, 0.22, 0.19), (0, -0.40, 0.02, 0.22, 0.17, 0.13),
         (0, -0.65, 0.00, 0.17, 0.12, 0.10), (0, -0.88, -0.02, 0.13, 0.09, 0.08), (0, -1.05, -0.03, 0.10, 0.06, 0.06))
JAWR = ((0, 0.00, -0.15, 0.20, 0.07, 0.10), (0, -0.35, -0.17, 0.19, 0.07, 0.09), (0, -0.70, -0.16, 0.14, 0.06, 0.07),
        (0, -0.98, -0.14, 0.10, 0.05, 0.05))
HEAD_TIP = (0, -1.05, -0.03)
HINGE, CHIN = (0, -0.05, -0.11), (0, -0.98, -0.15)
EYE = ((0.20, -0.22, 0.11), 0.055)
NOSTRIL = ((0.07, -0.95, 0.04), 0.022)
GILL = ((0.17, 0.02, -0.06), ((0.36, 0.20, 0.14), (0.44, 0.27, -0.04), (0.36, 0.20, -0.22)))  # base, rounded lobe

FRONT = dict(scap=(0.50, -0.80, 1.65), sho=(0.82, -1.05, 1.20), elb=(1.10, -0.80, 0.72), wri=(1.12, -1.02, 0.24),
             paw=(1.12, -1.18, 0.10), toe=(1.16, -1.55, 0.03))
HIND = dict(hip=(0.68, 1.05, 1.40), knee=(1.08, 0.62, 0.90), hock=(1.10, 1.18, 0.40), paw=(1.10, 1.05, 0.10),
            toe=(1.15, 0.68, 0.03))

# trunk -> tail loft: x, y, z, a (half width), b (dorsal), c (ventral). A broad, flat-bellied trunk; the tail
# flattens side to side into a paddle.
BODY_ROWS = (
    (0, -1.80, 1.74, 0.50, 0.38, 0.50),
    (0, -1.30, 1.72, 0.84, 0.38, 0.84),
    (0, -0.60, 1.68, 0.95, 0.36, 0.95),
    (0, 0.20, 1.64, 0.98, 0.35, 0.92),
    (0, 0.90, 1.58, 0.90, 0.35, 0.82),
    (0, 1.50, 1.50, 0.70, 0.34, 0.66),
    (0, 2.40, 1.30, 0.45, 0.32, 0.48),
    (0, 3.40, 1.05, 0.28, 0.30, 0.36),
    (0, 4.40, 0.80, 0.17, 0.28, 0.28),
    (0, 5.40, 0.58, 0.10, 0.24, 0.22),
    (0, 6.30, 0.42, 0.06, 0.18, 0.15),
    (0, 7.00, 0.35, 0.02, 0.06, 0.05),
)
TAIL_FIN = ((2.3, 0.03), (3.2, 0.14), (4.4, 0.27), (5.6, 0.30), (6.5, 0.22), (7.05, 0.07))   # (y, height) dorsal
TAIL_KEEL = ((3.4, 0.02), (4.6, 0.12), (5.8, 0.17), (6.6, 0.12), (7.05, 0.04))               # ventral

# colours (sRGB), blockout only: deep sea green back, pale belly, darker fins, yellow eyes
COL = dict(back="1f4a44", belly="c9c08a", fin="2f6e66", eye="e8d040", claw="20201c", gill="a8584e")


def _rgb(h):
    return tuple(float(x) for x in srgb_to_lin(hexc(h)))


# ----------------------------------------------------------------------------------------- chains
def neck_ids(heads=None):
    """'' (middle), 'L', 'R' with three heads; 'L', 'R' with two."""
    return ("", "L", "R") if (heads or HEADS) == 3 else ("L", "R")


def _neck_ctrl(nid, heads=None):
    ctrl = NECKS3["" if nid == "" else "L"] if (heads or HEADS) == 3 else NECKS2["L"]
    s = -1 if nid == "R" else 1
    return [DB._m(p, s) for p in ctrl]


def neck_pts(nid, heads=None):
    return _curve(_neck_ctrl(nid, heads), NECK_N)


def tail_pts():
    return _curve(TAIL_CTRL, TAIL_N, TAIL_RATIO)


def head_matrix(nid, heads=None):
    """Local head space -> world: at its neck's end, -Y along HEAD_FWD."""
    P = neck_pts(nid, heads)
    f = np.array(HEAD_FWD[heads or HEADS]["" if nid == "" else "L"], float)
    if nid == "R":
        f[0] = -f[0]
    f /= np.linalg.norm(f)
    ly = -f
    lz = np.array(UP, float) - ly * np.dot(UP, ly)
    lz /= np.linalg.norm(lz)
    lx = np.cross(ly, lz)
    M = Matrix((lx, ly, lz)).transposed().to_4x4()
    M.translation = Vector(P[-1])
    return M


def hx(M, p):
    return tuple(M @ Vector(p[:3]))


# ----------------------------------------------------------------------------------------- skeleton
def rest_bones(heads=None):
    """name -> (head, Matrix3 frame, length, parent, deform), as dragon_body.rest_bones (beast_rig conventions)."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.8, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.6, None, True)
    S = SPINE
    _bone(B, "Hips", S["pelvis"], S["hips_end"], UP, "Root")
    _bone(B, "Spine1", S["pelvis"], S["spine2"], UP, "Hips")
    _bone(B, "Spine2", S["spine2"], S["chest"], UP, "Spine1")
    _bone(B, "Chest", S["chest"], S["neck_base"], UP, "Spine2")
    for nid in neck_ids(heads):
        P, par = neck_pts(nid, heads), "Chest"
        for i in range(NECK_N):
            _bone(B, f"Neck{i + 1}{nid}", P[i], P[i + 1], UP, par)
            par = f"Neck{i + 1}{nid}"
        M = head_matrix(nid, heads)
        zup = tuple(M.to_3x3() @ Vector(UP))
        _bone(B, f"Head{nid}", hx(M, (0, 0, 0)), hx(M, HEAD_TIP), zup, par)
        _bone(B, f"Jaw{nid}", hx(M, HINGE), hx(M, CHIN), zup, f"Head{nid}")
    P, par = tail_pts(), "Hips"
    for i in range(TAIL_N):
        _bone(B, f"Tail{i + 1}", P[i], P[i + 1], UP, par)
        par = f"Tail{i + 1}"
    for s, sfx in SIDES:
        m = lambda p: DB._m(p, s)
        F, H = FRONT, HIND
        _bone(B, f"Scapula{sfx}", m(F["scap"]), m(F["sho"]), FWD, "Chest")
        _bone(B, f"UpperArm{sfx}", m(F["sho"]), m(F["elb"]), FWD, f"Scapula{sfx}")
        _bone(B, f"Forearm{sfx}", m(F["elb"]), m(F["wri"]), FWD, f"UpperArm{sfx}")
        _bone(B, f"FrontPaw{sfx}", m(F["wri"]), m(F["paw"]), FWD, f"Forearm{sfx}")
        _bone(B, f"FrontToes{sfx}", m(F["paw"]), m(F["toe"]), UP, f"FrontPaw{sfx}")
        _bone(B, f"Thigh{sfx}", m(H["hip"]), m(H["knee"]), FWD, "Hips")
        _bone(B, f"Shin{sfx}", m(H["knee"]), m(H["hock"]), FWD, f"Thigh{sfx}")
        _bone(B, f"HindFoot{sfx}", m(H["hock"]), m(H["paw"]), FWD, f"Shin{sfx}")
        _bone(B, f"HindToes{sfx}", m(H["paw"]), m(H["toe"]), UP, f"HindFoot{sfx}")
    return B


# ----------------------------------------------------------------------------------------- blockout
def _belly(P):
    """Back colour on top, belly colour underneath (by height under the trunk loft's axis)."""
    back, belly = np.array(_rgb(COL["back"])), np.array(_rgb(COL["belly"]))
    R = spline(BODY_ROWS, 8)
    i = np.argmin(np.abs(R[:, 1][None, :] - P[:, 1][:, None]), axis=1)
    k = np.clip((R[i, 2] - P[:, 2]) / np.maximum(R[i, 5], 1e-3), 0, 1)
    k = k * k * (3 - 2 * k)
    return [tuple(back * (1 - x) + belly * x) for x in k]


def _neck_col(nid, heads):
    """Back above, belly below the neck's axis."""
    P0 = spline([(*p, 0, 0, 0) for p in neck_pts(nid, heads)], 8)[:, :3]
    back, belly = np.array(_rgb(COL["back"])), np.array(_rgb(COL["belly"]))

    def col(P):
        i = np.argmin(((P[:, None, :] - P0[None]) ** 2).sum(-1), axis=1)
        k = np.clip((P0[i, 2] - P[:, 2]) / 0.3, 0, 1)
        k = k * k * (3 - 2 * k)
        return [tuple(back * (1 - x) + belly * x) for x in k]
    return col


def _neck_rows(nid, heads):
    P = neck_pts(nid, heads)
    r = np.linspace(NECK_R[0], NECK_R[1], len(P))
    return [(*p, ri, ri * 0.95, ri * 1.05) for p, ri in zip(P, r)]


def _fin(bm, base, top):
    """A smooth two-sided strip between two curves (base along the body, top its rounded edge)."""
    vb = [bm.verts.new(Vector(p)) for p in base]
    vt = [bm.verts.new(Vector(p)) for p in top]
    for i in range(len(vb) - 1):
        bm.faces.new((vb[i], vb[i + 1], vt[i + 1], vt[i]))


def _tail_fins(sign, table):
    """Points along the tail's top (sign +1) or bottom (-1) and the fin's edge above / below them."""
    R = spline(BODY_ROWS, 12)
    ys = np.linspace(table[0][0], table[-1][0], 28)
    h = np.interp(ys, [t[0] for t in table], [t[1] for t in table])
    base, top = [], []
    for y, hh in zip(ys, h):
        i = int(np.argmin(np.abs(R[:, 1] - y)))
        z0 = R[i, 2] + (R[i, 4] * 0.9 if sign > 0 else -R[i, 5] * 0.9)
        base.append((0.0, y, z0))
        top.append((0.0, y + 0.10 * hh, z0 + sign * hh))
    return np.array(base), np.array(top)


def _head(acc, fins, nid, heads, B):
    """One head: skull and jaw lofts, eyes, nostrils, the rounded gill fins behind the jaw."""
    M = head_matrix(nid, heads)
    back, belly, eye = _rgb(COL["back"]), _rgb(COL["belly"]), _rgb(COL["eye"])
    acc.add(lambda bm: loft(bm, SKULL, seg=20, per_seg=4, cap0=0.8, cap1=0.6, xform=M), f"Head{nid}", back)
    acc.add(lambda bm: loft(bm, JAWR, seg=16, per_seg=4, cap0=0.8, cap1=0.6, xform=M), f"Jaw{nid}", belly)
    for s in (1, -1):
        c, r = EYE
        acc.add(lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r,
                                                     matrix=Matrix.Translation(hx(M, DB._m(c, s)))) and None,
                f"Head{nid}", eye)
        c, r = NOSTRIL
        acc.add(lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=r,
                                                     matrix=Matrix.Translation(hx(M, DB._m(c, s)))) and None,
                f"Head{nid}", _rgb("0e1a18"))
        gb, lobe = GILL

        def gill(bm, s=s):
            ctrl = np.array([DB._m(p, s) for p in lobe])
            arc = spline([(*p, 0, 0, 0) for p in ctrl], 6)[:, :3]           # a rounded edge, no points
            vb = bm.verts.new(Vector(hx(M, DB._m(gb, s))))
            va = [bm.verts.new(Vector(hx(M, p))) for p in arc]
            for a, b in zip(va[:-1], va[1:]):
                bm.faces.new((vb, a, b))
        fins.add(gill, f"Head{nid}", _rgb(COL["gill"]))


def build_blockout(rig, heads=None):
    """The blockout meshes, skinned and bound to the rig: HydraBlockout (trunk, tail, necks, heads, legs) and
    HydraFins (the tail fins and gill fins, two-sided sheets). -> (objects, report)"""
    heads = heads or HEADS
    B = rest_bones(heads)
    coll = get_coll(COLL)
    mat = DB.blockout_material()
    body, fins = Acc(), Acc()
    back, claw, fin = _rgb(COL["back"]), _rgb(COL["claw"]), _rgb(COL["fin"])

    # trunk and tail: one loft, chain weights
    trunk = ["Chest", "Spine2", "Spine1", "Hips"] + [f"Tail{i + 1}" for i in range(TAIL_N)]
    tb = _bones_of(B, trunk)
    body.add(lambda bm: loft(bm, BODY_ROWS, seg=24, per_seg=6, cap0=0.9, cap1=0.8),
             lambda P: chain_weights(P, tb), _belly)
    for sign, table in ((1, TAIL_FIN), (-1, TAIL_KEEL)):
        base, top = _tail_fins(sign, table)
        fins.add(lambda bm, b=base, t=top: _fin(bm, b, t), lambda P: chain_weights(P, tb), fin)

    # necks and heads
    for nid in neck_ids(heads):
        chain = _bones_of(B, ["Chest"] + [f"Neck{i + 1}{nid}" for i in range(NECK_N)] + [f"Head{nid}"])
        body.add(lambda bm, n=nid: loft(bm, _neck_rows(n, heads), seg=18, per_seg=4, cap0=0.6, cap1=0.6),
                 lambda P, c=chain: chain_weights(P, c), _neck_col(nid, heads))
        _head(body, fins, nid, heads, B)

    # legs: rigid segments per bone, webbed feet
    for s_, sfx in SIDES:
        m = lambda p: DB._m(p, s_)
        F, H = FRONT, HIND
        segs = ((f"Scapula{sfx}", (0.55, -0.85, 1.55), F["sho"], 0.30, 0.34, 0.34),
                (f"UpperArm{sfx}", F["sho"], F["elb"], 0.34, 0.22, 0.30),
                (f"Forearm{sfx}", F["elb"], F["wri"], 0.22, 0.15, 0.19),
                (f"FrontPaw{sfx}", F["wri"], F["paw"], 0.15, 0.15, 0.15),
                (f"Thigh{sfx}", (0.62, 1.10, 1.55), H["hip"], 0.40, 0.44, 0.44),
                (f"Thigh{sfx}", H["hip"], H["knee"], 0.44, 0.26, 0.38),
                (f"Shin{sfx}", H["knee"], H["hock"], 0.26, 0.16, 0.22),
                (f"HindFoot{sfx}", H["hock"], H["paw"], 0.16, 0.15, 0.15))
        for bone, a, b, ra, rb, rm in segs:
            body.add(lambda bm, a=a, b=b, ra=ra, rb=rb, rm=rm: _seg(bm, m(a), m(b), ra, rb, rm), bone, back)
        for toes, paw, spread, L, r in ((f"FrontToes{sfx}", F["paw"], (-34, -12, 10, 32), 0.38, 0.06),
                                        (f"HindToes{sfx}", H["paw"], (-32, -11, 10, 31), 0.42, 0.065)):
            tips = []
            for k, ang in enumerate(spread):
                a = math.radians(ang)
                d = np.array((math.sin(a) * s_, -math.cos(a), -0.10))
                base = np.array(m(paw)) + np.array((s_ * 0.05 * (k - 1.5), -0.04, -0.02))
                tip = base + d * L
                tip[2] = max(tip[2], r)
                tips.append(tip)
                body.add(lambda bm, b=base, t=tip: _seg(bm, b, t, r * 1.1, r * 0.75, up=UP, cap=0.6), toes, back)
                body.add(lambda bm, t=tip, d=d: _claw(bm, t, d, 0.10, r * 0.5), toes, claw)
            # the web between the toes: a fan from the paw, its edge sagging between the tips
            p0 = np.array(m(paw)) + np.array((0, -0.06, 0.0))
            edge = []
            for a, b in zip(tips[:-1], tips[1:]):
                edge += [a * 0.92 + p0 * 0.08, (a + b) / 2 * 0.70 + p0 * 0.30]
            edge.append(tips[-1] * 0.92 + p0 * 0.08)

            def web(bm, p0=p0, edge=edge):
                v0 = bm.verts.new(Vector(p0))
                ve = [bm.verts.new(Vector(e)) for e in edge]
                for a, b in zip(ve[:-1], ve[1:]):
                    bm.faces.new((v0, a, b))
            fins.add(web, toes, fin)

    ob_body = body.finish("HydraBlockout", coll, mat)
    ob_fins = fins.finish("HydraFins", coll, mat)
    import beast_rig
    rep = {o.name: beast_rig.bind(o, rig) for o in (ob_body, ob_fins)}
    rep["tris"] = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (ob_body, ob_fins)}
    rep["heads"] = heads
    return (ob_body, ob_fins), rep


def scale_man(coll):
    """The dragon's 1.8 m capsule, for scale (not exported)."""
    from beast_common import remove_obj
    remove_obj("HYD_ScaleMan")
    ob = DB.scale_man(coll)
    ob.name = "HYD_ScaleMan"
    ob.location = (1.6, -5.2, 0)
    return ob
