"""Giant bat (2026-10-23, a unit from Daniel's card game): body, skeleton and skinning. Facing -Y, left side +X.

My calls (Daniel gave no details): a wolf-sized body (0.80 m nose to rump), a 2.9 m wingspan, the leathery wings of
the dragon (dragon_body's membrane code with a bat WingSpec: four long fingers, the thumb with its claw, the arm
panel running down the flank to the ankle), big upright ears, a short pug snout with an upturned nose pad and a
small nose leaf, two long upper fangs outside the lower jaw, a rusty mantle over dark fur. No tail and no tail
membrane (a fruit bat's build). The bind pose is the flying pose at hover height `H` (the body's centre 1.6 m over the
Root): the bat is always in the air, so the game moves it on the ground like the other beasts and every clip but
Death keeps it up there.

Pieces: one fused fur body (beast_body.fuse_body: trunk, neck ruff, shoulders, pectorals, thigh stumps, head,
muzzle, nose pad and leaf, cheeks, brows); clean lofts for the arms, fingers, thumbs and hind legs (thin tubes don't
survive the voxel fuse and decimation: the mammoth's lesson); cup ears; eye domes; the lower jaw; fangs; claws; the
membranes (Coons patches, dragon_body.build_membranes). The pieces are gathered in a dragon_body.Acc so each vertex
carries its own weights (chain weights along the arm and finger bones, the membranes' Coons weights and their
helper bones), and the fur body gets heat weights on its own (the membrane sheets stay out of the heat solve).

build_body() -> BatBody (all of it; the membranes split off into BatWing after painting, bat_build).
rest_bones() is the skeleton (beast_rig.build_armature): the beasts' Root / Motion / sockets, Hips, Spine1, Chest,
Neck1, Head, Jaw, EarL/R, Thigh / Shin / HindFoot / HindToes, and the dragon's wing chain WingScap, WingArm,
WingForearm, WingHand, WingThumb, WingF<i>_<k> plus the arm panel's helper bones WingMem<i><j>.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, smoothstep
import beast_body, beast_rig
from beast_body import PART, ellipsoid, _write_info, cup_ear
import dragon_body as DB

NAME, PREFIX = "Bat", "BAT"
RIG = "BatRig"
BODY = "BatBody"
WING_OB = "BatWing"
H = 1.60                            # the body's centre over the Root in the bind pose (flying)
VOXEL, BODY_TRIS = 0.004, 1900
UP, FWD = (0, 0, 1), (0, -1, 0)
SIDES = ((1, "L"), (-1, "R"))


def h(x, y, z):
    return (x, y, z + H)


# ----------------------------------------------------------------------------------------- landmarks (left side)
J = dict(HIPS=h(0, 0.20, -0.020), RUMP=h(0, 0.36, -0.020), CHEST=h(0, 0.00, 0.008), NECK=h(0, -0.18, 0.030),
         POLL=h(0, -0.25, 0.055), SNOUT=h(0, -0.44, 0.030), HINGE=h(0, -0.305, 0.004), CHIN=h(0, -0.418, -0.006),
         HIP=h(0.070, 0.245, -0.030), KNEE=h(0.165, 0.375, -0.050), ANKLE=h(0.215, 0.515, -0.068),
         BALL=h(0.220, 0.565, -0.078), TOE=h(0.212, 0.615, -0.098))
WING = dict(root=h(0.040, -0.120, 0.040), sho=h(0.110, -0.140, 0.050), elb=h(0.380, -0.020, 0.060),
            wri=h(0.820, -0.180, 0.070), knu=h(0.845, -0.180, 0.070), thumb=h(0.880, -0.268, 0.080),
            att=J['ANKLE'],
            tips=(h(1.120, -0.210, 0.060), h(1.460, 0.040, 0.030), h(1.120, 0.400, 0.030), h(0.800, 0.480, 0.020)))
SEGS = (2, 3, 3, 2)                 # digit 2 (along the leading edge), 3 (to the wingtip), 4, 5
# the arm panel's edge along the body: shoulder, the chest's side, the hip's side, the knee, the ankle
FLANK = (WING['sho'], h(0.118, -0.050, 0.020), h(0.098, 0.170, -0.012), h(0.168, 0.372, -0.044), J['ANKLE'])
FLANK_BONES = ("Chest", "Spine1", "Thigh", "Shin")


def _flank(B, s_, sfx, nv):
    pts = [DB._m(p, s_) for p in FLANK]
    bones = [b if b in ("Chest", "Spine1") else b + sfx for b in FLANK_BONES]
    return DB.polyline(pts, bones, nv, start=f"WingScap{sfx}", blend=0.05)


def _att_w(B, s_, sfx):
    return {f"Shin{sfx}": 1.0}


WS = DB.WingSpec(wing=WING, segs=SEGS, bow=0.035, trunk=("Chest", "Spine1", "Hips"), sag=0.10, finger_sag=0.20,
                 lead=(0.0, -0.075, 0.010), flank=_flank, att_w=_att_w, name="bat")
REACH = float(np.linalg.norm(np.array(WING['tips'][1]) - np.array(WING['sho'])))   # shoulder to wingtip


# ----------------------------------------------------------------------------------------- skeleton
def rest_bones():
    """name -> (head, Matrix3 frame, length, parent, deform), the beasts' conventions."""
    B = {}
    up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
    B["Root"] = (Vector((0, 0, 0)), up_fwd, 0.25, None, False)
    B["Motion"] = (Vector((0, 0, 0)), up_fwd.copy(), 0.15, None, True)
    b = lambda n, a, t, z, par: DB._bone(B, n, a, t, z, par)
    b("Hips", J['HIPS'], J['RUMP'], UP, "Root")
    b("Spine1", J['HIPS'], J['CHEST'], UP, "Hips")
    b("Chest", J['CHEST'], J['NECK'], UP, "Spine1")
    b("Neck1", J['NECK'], J['POLL'], UP, "Chest")
    b("Head", J['POLL'], J['SNOUT'], UP, "Neck1")
    b("Jaw", J['HINGE'], J['CHIN'], UP, "Head")
    for s, sfx in SIDES:
        m = lambda p: DB._m(p, s)
        b(f"Ear{sfx}", m(EAR_BASE), m(EAR_TIP), FWD, "Head")
        b(f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), UP, "Hips")
        b(f"Shin{sfx}", m(J['KNEE']), m(J['ANKLE']), UP, f"Thigh{sfx}")
        b(f"HindFoot{sfx}", m(J['ANKLE']), m(J['BALL']), UP, f"Shin{sfx}")
        b(f"HindToes{sfx}", m(J['BALL']), m(J['TOE']), UP, f"HindFoot{sfx}")
    for s, sfx in SIDES:
        DB.wing_bones(B, s, sfx, WS, parent="Chest")
    top = h(0, -0.27, 0.13)
    b("Socket_Head", top, (top[0], top[1], top[2] + 0.1), FWD, "Head")
    mouth = h(0, -0.40, 0.010)
    b("Socket_Mouth", mouth, (mouth[0], mouth[1], mouth[2] + 0.1), FWD, "Jaw")
    return B


WS.rest_bones = rest_bones


# ----------------------------------------------------------------------------------------- the fused fur body
TRUNK = [h(0, -0.215, 0.040) + (0.050, 0.045, 0.050), h(0, -0.160, 0.025) + (0.095, 0.065, 0.085),
         h(0, -0.070, 0.008) + (0.122, 0.074, 0.098), h(0, 0.040, -0.002) + (0.116, 0.068, 0.090),
         h(0, 0.150, -0.012) + (0.098, 0.060, 0.072), h(0, 0.255, -0.018) + (0.078, 0.050, 0.058),
         h(0, 0.340, -0.020) + (0.044, 0.036, 0.036)]
MUZZLE = [h(0, -0.300, 0.036) + (0.058, 0.046, 0.034), h(0, -0.360, 0.030) + (0.047, 0.038, 0.027),
          h(0, -0.405, 0.029) + (0.037, 0.031, 0.022), h(0, -0.433, 0.033) + (0.027, 0.025, 0.017)]
BLOBS = [  # centre, radii, mirrored, tilt (deg about X: + leans the top back; or Euler degrees (x, y, z), mirrored)
    (h(0, -0.190, 0.052), (0.086, 0.072, 0.066), False, 0),      # the neck's ruff (the mantle)
    (h(0.094, -0.132, 0.034), (0.046, 0.056, 0.040), True, 0),   # shoulders, where the arms come out
    (h(0.050, -0.100, -0.040), (0.062, 0.080, 0.050), True, 0),  # pectorals
    (h(0.074, 0.245, -0.034), (0.040, 0.050, 0.034), True, 0),   # thigh stumps
    (h(0, -0.285, 0.066), (0.072, 0.080, 0.068), False, 0),      # cranium
    (h(0, -0.268, -0.018), (0.050, 0.062, 0.040), False, 0),     # throat
    (h(0.047, -0.336, 0.018), (0.032, 0.042, 0.032), True, 0),   # cheeks
    (h(0.030, -0.357, 0.077), (0.030, 0.020, 0.011), True, (0, -22, -18)),   # brows, a scowl (lower inside)
    (h(0, -0.436, 0.049), (0.031, 0.013, 0.022), False, 25),     # the upturned nose pad (pug)
    (h(0, -0.428, 0.082), (0.017, 0.005, 0.030), False, 12),     # the nose leaf
]
EYE_C, EYE_N, EYE_R = h(0.044, -0.370, 0.066), (0.62, -0.66, 0.36), 0.0165
EAR_BASE, EAR_TIP = h(0.050, -0.262, 0.105), h(0.128, -0.226, 0.335)
EAR_FRONT = (0.35, -1.0, 0.05)
EAR_PROFILE = ((0.0, 0.040, 0.030), (0.30, 0.060, 0.040), (0.62, 0.052, 0.032), (0.88, 0.024, 0.014))


def fur_flow(P, N):
    """Fur lies back along the body (and back from the face)."""
    F = np.tile(np.array((0.0, 1.0, -0.15)), (len(P), 1))
    F = F - (F * N).sum(-1, keepdims=True) * N
    return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)


def _face(P):
    """1 on the bare face (muzzle, nose, round the eyes), 0 on the fur."""
    y, z = P[:, 1], P[:, 2] - H
    return smoothstep(-0.345, -0.385, y) * smoothstep(0.110, 0.090, z)


def _fur_amount(P, N):
    return 0.0028 * (1 - _face(P)) * (1 - 0.5 * smoothstep(-0.25, -0.30, P[:, 1]))


def _dec_weight(co):
    y, z = co.y, co.z - H
    face = 1.0 if (y < -0.30 and z > -0.03) else 0.0
    return 1.0 - 0.55 * face - 0.2 * float(y < -0.24)


def build_fur_body():
    bm = bmesh.new()
    loft(bm, TRUNK, up=UP, seg=16, per_seg=3, cap0=0.8, cap1=0.8)
    loft(bm, MUZZLE, up=UP, seg=16, per_seg=3, cap0=0.4, cap1=0.9, shape=0.85)
    for c, r, mirror, tilt in BLOBS:
        for s in ((1, -1) if mirror else (1,)):
            if isinstance(tilt, tuple):
                rot = Euler([math.radians(a) * k for a, k in zip(tilt, (1, s, s))]).to_matrix()
            else:
                rot = Matrix.Rotation(math.radians(-tilt), 3, 'X') if tilt else None
            ellipsoid(bm, (s * c[0], c[1], c[2]), r, rot=rot)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    fur = lambda co, no: beast_body.sculpt_fur(co, no, fur_flow, _fur_amount, seed=41, across=0.016,
                                               along_len=0.05)
    body, hi = beast_body.fuse_body(bm, PREFIX, VOXEL, BODY_TRIS, sculpts=(fur,), dec_weight=_dec_weight,
                                    seam_x=0.006, flat_z=-1.0, fillet_iters=50)
    import zwolf_body
    zwolf_body.tidy(body)
    return body, hi


# ----------------------------------------------------------------------------------------- pieces
def _chain(P, names, B, falloff=0.03):
    return DB.chain_weights(np.asarray(P), DB._bones_of(B, names), falloff)


def _tube(bm, pts, radii, seg=8, per_seg=1, cap0=0.6, cap1=0.6, up=UP, capk=2):
    rows = [tuple(p) + (r, r, r) for p, r in zip(pts, radii)]
    return loft(bm, rows, up=up, seg=seg, per_seg=per_seg, cap0=cap0, cap1=cap1, capk=capk)


def build_pieces(fur, B):
    """-> dragon_body.Acc: every piece with per-vertex weights; Acc.C holds each vertex's part name."""
    bml = bmesh.new()
    bml.from_mesh(fur.data)
    bvh = BVHTree.FromBMesh(bml)
    bml.free()
    acc = DB.Acc()
    LM = {}
    for s, sfx in SIDES:
        m = lambda p: np.array(DB._m(p, s))
        W = WING
        # the arm: from inside the shoulder to the knuckle
        pts = [m(W['root']), m(W['sho']), (m(W['sho']) + m(W['elb'])) / 2, m(W['elb']), (m(W['elb']) + m(W['wri'])) / 2,
               m(W['wri']), m(W['knu'])]
        arm = [f"WingScap{sfx}", f"WingArm{sfx}", f"WingForearm{sfx}", f"WingHand{sfx}"]
        acc.add(lambda bm: _tube(bm, pts, (0.034, 0.033, 0.026, 0.019, 0.012, 0.015, 0.011), seg=6),
                lambda P: _chain(P, arm, B, 0.025), 'bone')
        # fingers
        for i in range(len(SEGS)):
            fp = [m(p) for p in DB.finger_pts(i, WS)]
            names = [f"WingHand{sfx}"] + [f"WingF{i + 1}_{k + 1}{sfx}" for k in range(SEGS[i])]
            rr = np.linspace(0.0105, 0.0042, len(fp))
            acc.add(lambda bm: _tube(bm, fp, rr, seg=4, cap0=0.5, cap1=0.8, capk=1),
                    lambda P: _chain(P, names[1:], B, 0.02), 'bone')
        # the thumb and its claw
        th = [m(W['wri']), m(W['thumb'])]
        acc.add(lambda bm: _tube(bm, th, (0.012, 0.008), seg=4, cap0=0.5, cap1=0.5, capk=1), f"WingThumb{sfx}",
                'bone')
        tip = m(W['thumb'])
        d = np.array((0.10 * s, -0.75, -0.65))
        d /= np.linalg.norm(d)
        acc.add(lambda bm: cone(bm, tip - d * 0.006, tip + d * 0.040, 0.0075, seg=5, bend=(0, 0.004, -0.010)),
                f"WingThumb{sfx}", 'claw')
        # the hind leg, from inside the thigh stump to the ball of the foot
        legs = [f"Thigh{sfx}", f"Shin{sfx}", f"HindFoot{sfx}"]
        lp = [m(h(0.050, 0.225, -0.025)), m(J['HIP']), m(J['KNEE']), (m(J['KNEE']) + m(J['ANKLE'])) / 2,
              m(J['ANKLE']), m(J['BALL'])]
        acc.add(lambda bm: _tube(bm, lp, (0.030, 0.029, 0.019, 0.014, 0.013, 0.012), seg=5, cap0=0.6, cap1=0.6),
                lambda P: _chain(P, legs, B, 0.02), 'bone')
        # toes: four hooked claws from the ball, curled down
        for k in range(4):
            dx = (k - 1.5) * 0.011
            base = m(J['BALL']) + np.array((s * dx, 0.004, -0.002))
            tipp = m(J['TOE']) + np.array((s * dx * 1.5, -0.003 * abs(k - 1.5), -0.006))
            acc.add(lambda bm: cone(bm, base, tipp, 0.0055, seg=3), f"HindToes{sfx}", 'claw')
        # the ear: a big cup, its root sunk in the head
        acc.add(lambda bm: cup_ear(bm, m(EAR_BASE), m(EAR_TIP), DB._m(EAR_FRONT, s), profile=EAR_PROFILE,
                                   hollow=0.60), f"Ear{sfx}", 'ear')
        # the eye, on the game mesh's socket
        n = np.array(EYE_N) * np.array((s, 1, 1))
        n /= np.linalg.norm(n)
        e = m(EYE_C)
        hit = bvh.ray_cast(Vector(e + n * 0.04), Vector(-n), 0.08)[0]
        c = (np.array(hit) if hit is not None else e) - n * 0.0030
        LM['eye_' + sfx] = c
        acc.add(lambda bm: dome(bm, c, n, EYE_R, 0.0075, seg=10, rings=3), "Head", 'eye')
        # the upper fang hangs outside the lower jaw; the lower one stands inside the muzzle
        acc.add(lambda bm: cone(bm, m(h(0.0225, -0.403, 0.014)), m(h(0.0205, -0.410, -0.034)), 0.0068, seg=5,
                                bend=(0, 0.004, 0)), "Head", 'tooth')
        acc.add(lambda bm: cone(bm, m(h(0.0135, -0.400, 0.000)), m(h(0.0130, -0.407, 0.026)), 0.0052, seg=4),
                "Jaw", 'tooth_low')
        # the membranes (the dragon's Coons patches)
        n0 = len(acc.W)
        DB.build_membranes(acc, B, s, sfx, WS, n_finger=10, n_tip=5, n_lead=8)
        acc.C[n0:] = ['membrane'] * (len(acc.W) - n0)
    # the lower jaw
    acc.add(lambda bm: loft(bm, [h(0, -0.300, -0.002) + (0.038, 0.015, 0.018), h(0, -0.350, -0.006) + (0.033, 0.013, 0.016),
                                 h(0, -0.392, -0.006) + (0.025, 0.011, 0.012), h(0, -0.416, -0.002) + (0.014, 0.008, 0.008)],
                            up=UP, seg=10, per_seg=2, cap0=0.6, cap1=0.8, shape=0.9), "Jaw", 'jaw')
    return acc, LM


def build_body():
    """-> (BatBody: the fused fur first, then the pieces; its acc weights per piece vertex in body['piece_w'] are
    not stored: skin() takes them from the returned Acc), the Acc, BAT_BodyHi."""
    fur, hi = build_fur_body()
    B = rest_bones()
    acc, LM = build_pieces(fur, B)
    acc.bm.verts.index_update()
    verts = list(acc.bm.verts)
    tags = {}
    for v, part in zip(verts, acc.C):
        tags.setdefault(part, []).append(v)
    body, nfur, part_extra = beast_body.join_pieces(fur, acc.bm, tags, PREFIX, BODY)
    _write_info(body.data, np.concatenate([np.full(nfur, PART['fur']), part_extra[:, 0]]),
                np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
    for k, v in LM.items():
        body[k] = [float(c) for c in v]
    _membranes_up(body)
    return body, acc, hi


def _membranes_up(body):
    """The membranes' faces turned to face up in the bind pose (each Coons patch came out either way): one side
    for the lighting of the two-sided wing material."""
    part, _ = beast_body.read_info(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.normal_update()
    flip = [f for f in bm.faces if part[f.verts[0].index] == PART['membrane'] and f.normal.z < 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    bm.to_mesh(body.data)
    bm.free()


def tri_report(ob):
    return beast_body.tri_report(ob)


# ----------------------------------------------------------------------------------------- skinning
HEAT = ("Hips", "Spine1", "Chest", "Neck1", "Head", "ThighL", "ThighR", "WingScapL", "WingScapR", "WingArmL",
        "WingArmR")


def heat_weights(body, rig, n, bones=HEAT):
    """Heat-map weights for the first n vertices (the fused fur) from `bones`, solved on a copy of the fur alone
    (the membrane sheets and thin lofts stay out of the solve). -> per vertex {bone: w}"""
    import bmesh as _bm
    me = body.data.copy()
    tmp = bpy.data.objects.new("_bat_heat", me)
    bpy.context.scene.collection.objects.link(tmp)
    bm = _bm.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    _bm.ops.delete(bm, geom=[v for v in bm.verts if v.index >= n], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    tmp.vertex_groups.clear()
    ad = rig.data
    keep = {b.name: b.use_deform for b in ad.bones}
    for b in ad.bones:
        b.use_deform = b.name in bones
    for o in bpy.context.selected_objects:
        o.select_set(False)
    tmp.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for nm, d in keep.items():
        ad.bones[nm].use_deform = d
    names = {g.index: g.name for g in tmp.vertex_groups}
    out = [{names[g.group]: g.weight for g in v.groups if g.weight > 1e-4} for v in me.vertices]
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.meshes.remove(me)
    return out


def skin(body, rig, acc):
    """Heat on the fur (smoothed), the pieces' own weights from the Acc, 4 influences."""
    n = body["n_fur"]
    V = len(body.data.vertices)
    body.vertex_groups.clear()
    for m in [m for m in body.modifiers if m.type == 'ARMATURE']:
        body.modifiers.remove(m)
    W = heat_weights(body, rig, n) + list(acc.W)
    assert len(W) == V, (len(W), V)
    groups = {}
    for i, w in enumerate(W):
        for b, x in w.items():
            g = groups.get(b) or body.vertex_groups.get(b) or body.vertex_groups.new(name=b)
            groups[b] = g
            g.add([i], float(x), 'REPLACE')
    beast_rig.smooth_weights(body, np.arange(n), iterations=3, factor=0.5)
    beast_rig.clean_weights(body)
    rep = beast_rig.bind(body, rig)
    rep["fur_unweighted"] = sum(1 for i in range(n) if not W[i])
    return rep
