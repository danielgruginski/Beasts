"""Farm animals with hooves (goat, sheep, cow, horse, pig): the red deer's body recipe as a class (2026-10-20).

Daniel's rule: a creature like an approved one starts from its finished parts. The red deer (deer_body) is the
approved hoofed body, so every hoofed farm animal is built by the deer's code: fused trunk, neck, head and leg
stumps, clean lofted lower legs grafted onto the stumps, a separate jaw, eyes, cupped ears and hooves.

Two frames:
  - "deer units" (D): every table and mask is written in the deer's metres (withers 1.2 m, the shoulder at y -0.56,
    the rump at y 0.75). A species overrides the deer's tables (Hoofed's class attributes) in these units, so the
    deer's masks, seams and leg graft still fit;
  - the real animal (R): W() warps D to R at the very end of the build (and the bones): per-axis scales, the legs
    (below ZB) scaled by KL and the body above by KB, blended over ZW. W_inv() takes positions back; the rig's masks,
    the UV cuts and the painter read D through it.
The head is modelled in head space (beast_body.HeadFrame), additionally scaled by KH (head space axes) before it is
hung from the poll, so the deer's head-space masks keep fitting a shorter or broader head.

A species is a subclass (farm_goat.Goat ...) overriding tables and hooks: extra_parts (fused into the body: udder,
dewlap, wool), extra_pieces (separate shells: horns, beard, mane), fur_amount / fur_flow, the dec weight.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from beast_common import loft, cone, dome, spline, smoothstep
import beast_body
from beast_body import PART, ellipsoid, _gauss, _write_info, _mx, HeadFrame, cup_ear
from deer_body import _zip, _snap, RIM_K


def _frame(head, ydir, zhint):
    y = Vector(ydir).normalized()
    z = Vector(zhint)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    return Vector(head), Matrix((x, y, z)).transposed()


class Hoofed:
    NAME = "Deer"
    PREFIX = "DER"
    # ------------------------------------------------------------------ the warp D -> R
    KX, KY, KL, KB = 1.0, 1.0, 1.0, 1.0
    ZB, ZW = 0.70, 0.12                 # where the legs' scale KL turns into the body's KB (D), blend half width
    KH = (1.0, 1.0, 1.0)                # head-space scale (x across, y along: - toward the nose, z up)
    VOXEL, BODY_TRIS = 0.006, 2600      # (D units) the fuse's voxel and the fused body's triangle target

    # ------------------------------------------------------------------ landmarks (D), the deer's
    J = dict(SCAP=(0.090, -0.36, 1.130), SHO=(0.150, -0.56, 0.860), ELB=(0.150, -0.40, 0.680),
             WRI=(0.143, -0.445, 0.380), FPAW=(0.138, -0.450, 0.130), FTOE=(0.135, -0.525, 0.008),
             HIP=(0.120, 0.44, 0.980), KNEE=(0.145, 0.36, 0.730), HOCK=(0.132, 0.505, 0.455),
             HPAW=(0.127, 0.494, 0.130), HTOE=(0.125, 0.420, 0.008))
    TAIL = [(0, 0.690, 1.040), (0, 0.790, 0.975), (0, 0.820, 0.860)]
    TAIL_R = ((0.046, 0.030, 0.028), (0.042, 0.028, 0.026), (0.030, 0.020, 0.018))
    POLL, HEAD_PITCH = (0.0, -0.93, 1.47), 42.0
    HINGE_H = (0.0, -0.08, -0.115)
    EYE0_H = (0.082, -0.140, -0.010)
    EYE_N_H = (0.76, -0.50, 0.30)       # the eye's facing (head space)
    EYE_R, EYE_LONG, EYE_SHORT = 0.026, 1.15, 0.86
    EYE_INSET, EYE_DOME = 0.003, 0.012  # the eye sunk this far into the socket, the dome's height (for EYE_R 0.026)
    JAW_SCALE = 1.0                     # x the clips' jaw opening (farm_anim)
    JAW_PIECE = True                    # False: the lower jaw is part of the fused head, moved by its weights
    EYE_AXIS = None                     # the almond's long axis in D (body space), or None: the deer's (head space)
    NOSE_C, NOSE_R = (0.0, -0.432, -0.083), (0.046, 0.020, 0.042)
    EAR_BASE_H = (0.064, -0.005, 0.042)
    EAR_DIR = (0.72, 0.22, 0.66)        # D, normalised
    EAR_LEN = 0.19
    EAR_PROFILE = ((0.0, 0.038, 0.026), (0.30, 0.056, 0.034), (0.62, 0.052, 0.030), (0.88, 0.030, 0.018))
    EAR_FRONT = (0.20, -1.0, 0.10)
    EAR_HOLLOW = 0.55
    HEAD_LEN = 0.43                     # the Head bone, poll to nose (head space)

    TRUNK_ROWS = [(-0.62, 0.95, 0.120, 0.150, 0.190), (-0.50, 0.96, 0.185, 0.230, 0.305),
                  (-0.32, 0.95, 0.215, 0.235, 0.320), (-0.10, 0.94, 0.225, 0.210, 0.290),
                  (0.10, 0.94, 0.210, 0.195, 0.230), (0.26, 0.95, 0.185, 0.190, 0.190),
                  (0.42, 0.96, 0.190, 0.185, 0.195), (0.57, 0.95, 0.165, 0.170, 0.180),
                  (0.68, 0.93, 0.100, 0.125, 0.135)]
    NECK = [(0, -0.42, 0.98, 0.165, 0.180, 0.240), (0, -0.57, 1.08, 0.150, 0.150, 0.250),
            (0, -0.70, 1.21, 0.128, 0.120, 0.215), (0, -0.80, 1.32, 0.104, 0.095, 0.170),
            (0, -0.88, 1.42, 0.084, 0.075, 0.110)]
    NECK_UP = (0, 0, 1)
    # (centre, radii, rotation about X in degrees, mirrored to both sides)
    TRUNK_BLOBS = [((0, -0.40, 1.13), (0.075, 0.20, 0.075), 0, False),          # the withers
                   ((0, -0.56, 0.80), (0.110, 0.10, 0.14), 0, False),           # the brisket
                   ((0.150, -0.47, 0.90), (0.070, 0.150, 0.230), -36, True),    # shoulder blade
                   ((0.150, -0.45, 0.76), (0.065, 0.110, 0.110), 0, True),      # upper arm, to the elbow
                   ((0.135, 0.46, 0.86), (0.080, 0.190, 0.240), 0, True),       # the haunch
                   ((0.148, 0.30, 0.81), (0.050, 0.070, 0.070), 0, True)]       # flank fold to the stifle
    HEAD_ROWS = [(0.03, -0.050, 0.068, 0.064, 0.090), (-0.05, -0.045, 0.086, 0.085, 0.105),
                 (-0.13, -0.050, 0.080, 0.075, 0.098), (-0.22, -0.062, 0.066, 0.058, 0.080),
                 (-0.31, -0.074, 0.056, 0.048, 0.070), (-0.38, -0.082, 0.052, 0.045, 0.066),
                 (-0.42, -0.085, 0.049, 0.044, 0.062)]
    HEAD_SHAPE = 0.9
    HEAD_CAP = 0.4                      # the head loft's front cap (lower = a blunter muzzle)
    HEAD_BLOBS = [((0, -0.05, 0.010), (0.075, 0.090, 0.070), False),             # the cranium
                  ('nose', None, False),                                         # the nose pad (NOSE_C, NOSE_R)
                  ((0, -0.03, -0.125), (0.052, 0.075, 0.062), False),            # throat latch
                  ((0.064, -0.122, 0.014), (0.020, 0.034, 0.013), True),         # brow over the eye
                  ((0.054, -0.110, -0.105), (0.042, 0.080, 0.062), True),        # cheek
                  ((0.046, -0.200, -0.128), (0.036, 0.075, 0.040), True),        # ... to the mouth's corner
                  ((0.024, -0.392, -0.136), (0.030, 0.045, 0.022), True)]        # deep upper lip over the jaw
    JAW_H = [(0, -0.10, -0.150, 0.044, 0.032, 0.040), (0, -0.21, -0.152, 0.046, 0.030, 0.032),
             (0, -0.31, -0.154, 0.044, 0.028, 0.028), (0, -0.39, -0.154, 0.038, 0.024, 0.022)]

    FRONT_STUMP = [(0.150, -0.42, 0.80, 0.057, 0.064, 0.064), (0.150, -0.41, 0.70, 0.055, 0.062, 0.066),
                   (0.147, -0.43, 0.60, 0.046, 0.054, 0.048), (0.146, -0.434, 0.52, 0.041, 0.048, 0.042)]
    HIND_STUMP = [(0.138, 0.38, 0.86, 0.062, 0.074, 0.082), (0.145, 0.36, 0.74, 0.060, 0.072, 0.088),
                  (0.140, 0.41, 0.64, 0.048, 0.055, 0.077), (0.137, 0.44, 0.565, 0.043, 0.049, 0.066)]
    FRONT_LEG = [(0.145, -0.435, 0.525, 0.039, 0.045, 0.040), (0.144, -0.44, 0.44, 0.031, 0.036, 0.031),
                 (0.143, -0.445, 0.375, 0.033, 0.037, 0.032), (0.141, -0.447, 0.270, 0.022, 0.024, 0.023),
                 (0.138, -0.450, 0.130, 0.026, 0.028, 0.032), (0.136, -0.475, 0.075, 0.022, 0.024, 0.023),
                 (0.135, -0.492, 0.048, 0.026, 0.030, 0.026)]
    HIND_LEG = [(0.136, 0.45, 0.570, 0.039, 0.044, 0.058), (0.134, 0.475, 0.515, 0.030, 0.034, 0.042),
                (0.132, 0.505, 0.455, 0.029, 0.031, 0.040), (0.130, 0.500, 0.350, 0.022, 0.024, 0.024),
                (0.127, 0.494, 0.130, 0.026, 0.028, 0.032), (0.126, 0.472, 0.075, 0.022, 0.024, 0.023),
                (0.125, 0.455, 0.048, 0.026, 0.030, 0.026)]
    LEG_T = 1.0                         # the legs' radii (stumps and lower legs) x this (D)
    LEG_T_LOW = 1.0                     # the lower legs' radii x this as well
    SEAM = {'F': 0.565, 'H': 0.610}
    FOOT = {'F': (0.135, -0.492), 'H': (0.125, 0.455)}
    GRAFT_NEAR = 0.11
    HOOF = 'cloven'                     # or 'solid' (the horse)
    HOOF_K = 1.0                        # the hooves' size x this (D)
    DEWCLAWS = True
    HOOF_UP, HOOF_CAPS = (0, 0, 1), (0.5, 0.5)     # the hoof lofts' up and end caps (a vertical hoof: (0, -1, 0))

    # bones (D)
    HIPS = ((0, 0.44, 1.000), (0, 0.70, 0.975))
    SPINE = [(0, 0.44, 1.020), (0, 0.14, 1.050), (0, -0.20, 1.070), (0, -0.52, 1.050)]   # Spine1, Spine2, Chest
    NECK_BONES = [(0, -0.52, 1.050), (0, -0.66, 1.180), (0, -0.78, 1.310)]              # Neck1..3 heads
    BACK_SOCKET = (0, -0.15, 1.220)
    BODY_C = (0.0, -0.05, 0.95)         # the trunk's pivot for the clips

    # masks (head space unless said)
    FACE_Y = (0.02, -0.62)              # the face mask runs from the poll's front to beyond the nose
    FUR_BASE = 0.0025
    MANE = 0.045                        # the throat mane's sculpt amount (0 = none)

    def __init__(self):
        self.HEAD = HeadFrame(self.POLL, self.HEAD_PITCH)
        self.KHv = np.array(self.KH, float)
        zs = np.linspace(-0.5, 4.0, 4501)
        slope = self.KL + (self.KB - self.KL) * smoothstep(self.ZB - self.ZW, self.ZB + self.ZW, zs)
        zr = np.concatenate([[0], np.cumsum(0.5 * (slope[1:] + slope[:-1]) * np.diff(zs))])
        zr -= np.interp(0.0, zs, zr)
        self._zs, self._zr = zs, zr
        self.LM = {}
        self.scale_legs()
        self.EAR_DIRv = np.array(self.EAR_DIR, float) / np.linalg.norm(self.EAR_DIR)
        self.EYE_N = self.hx_dir(np.array(self.EYE_N_H) / np.linalg.norm(self.EYE_N_H))
        self.EYE0 = self.hx(np.array(self.EYE0_H))
        self.HINGE = tuple(self.hx(self.HINGE_H))
        self.THROAT = self.throat_line()
        if self.LIE_DROP is None:
            self.LIE_DROP = 0.53 * self.KL
        if self.SIDE_REST is None:
            self.SIDE_REST = 0.26 * self.KX

    def scale_legs(self):
        t, tl = self.LEG_T, self.LEG_T * self.LEG_T_LOW
        sc = lambda rows, k: [r[:3] + tuple(v * k for v in r[3:6]) for r in rows]
        self.FRONT_STUMP_T, self.HIND_STUMP_T = sc(self.FRONT_STUMP, t), sc(self.HIND_STUMP, t)
        self.FRONT_LEG_T, self.HIND_LEG_T = sc(self.FRONT_LEG, tl), sc(self.HIND_LEG, tl)

    # ------------------------------------------------------------------ frames
    def W(self, P):
        P = np.asarray(P, float)
        return np.stack([P[..., 0] * self.KX, P[..., 1] * self.KY, np.interp(P[..., 2], self._zs, self._zr)], -1)

    def W_inv(self, Q):
        Q = np.asarray(Q, float)
        return np.stack([Q[..., 0] / self.KX, Q[..., 1] / self.KY, np.interp(Q[..., 2], self._zr, self._zs)], -1)

    def hx(self, P):
        """head space -> D"""
        return self.HEAD.hx(np.asarray(P, float) * self.KHv)

    def hx_inv(self, Q):
        """D -> head space"""
        return self.HEAD.hx_inv(Q) / self.KHv

    def hx_dir(self, v):
        d = self.HEAD.hx_dir(np.asarray(v, float) * self.KHv)
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def ear_rows(self, s):
        base = self.hx(np.array(self.EAR_BASE_H) * np.array((s, 1, 1)))
        return base, base + self.EAR_DIRv * np.array((s, 1, 1)) * self.EAR_LEN

    def eye_axes(self, n, axis=None):
        if axis is not None:
            t = np.asarray(axis, float)
        elif self.EYE_AXIS is not None:
            t = np.asarray(self.EYE_AXIS, float)
        else:
            t = self.hx_dir(np.array((0.0, 1.0, 0.30)))
        t = t - n * (t @ n)
        t /= np.linalg.norm(t)
        return t, np.cross(n, t)

    # ------------------------------------------------------------------ parts (D)
    def build_trunk(self, bm):
        loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in self.TRUNK_ROWS], up=(0, 0, 1), seg=28, cap0=0.6, cap1=0.6)
        loft(bm, self.NECK, self.NECK_UP, 24, 4, 0.5, 0.5)
        for c, r, rot, mirror in self.TRUNK_BLOBS:
            for s in ((1, -1) if mirror else (1,)):
                ellipsoid(bm, (s * c[0], c[1], c[2]), r,
                          rot=Matrix.Rotation(math.radians(rot), 3, 'X') if rot else None)
        for s in (1, -1):
            for rows in (self.FRONT_STUMP_T, self.HIND_STUMP_T):
                loft(bm, [(s * r[0],) + r[1:] for r in rows], up=(0, -1, 0), seg=16, cap0=0.5, cap1=0.7)
        if self.TAIL_R:
            loft(bm, [tuple(p) + tuple(r) for p, r in zip(self.TAIL, self.TAIL_R)], up=(0, 1, 0), seg=12,
                 cap0=0.4, cap1=0.8)
        self.extra_parts(bm)

    def extra_parts(self, bm):
        """Species: more volumes fused into the body (D)."""

    def build_head(self, bm):
        before = set(bm.verts)
        loft(bm, [(0, y, z, a, b, c) for y, z, a, b, c in self.HEAD_ROWS], up=(0, 0, 1), seg=24, cap0=0.5,
             cap1=self.HEAD_CAP, shape=self.HEAD_SHAPE)
        for c, r, mirror in self.HEAD_BLOBS:
            if c == 'nose':
                c, r = self.NOSE_C, self.NOSE_R
            for s in ((1, -1) if mirror else (1,)):
                ellipsoid(bm, (s * c[0], c[1], c[2]), r)
        if not self.JAW_PIECE:              # the lower jaw fused into the head (the horse): skin to the lips
            loft(bm, self.JAW_H, up=(0, 0, 1), seg=12, per_seg=2, cap0=0.5, cap1=0.6, capk=2, shape=0.85)
        self.extra_head_parts(bm)
        new = [v for v in bm.verts if v not in before]
        for v in new:
            v.co = Vector(self.hx(v.co[:]))

    def extra_head_parts(self, bm):
        """Species: more head volumes, in head space (fused)."""

    # ------------------------------------------------------------------ the legs' graft (D)
    def leg_loft(self, rows, s):
        return ([(s * r[0],) + r[1:] for r in rows], (0, -1, 0), 8, 2, 0.0, 0.3, 2, 1.0, 0.0 if s > 0 else math.pi)

    def _ellipse(self, c, rows, theta, k=RIM_K):
        a, b, cb = (r * k for r in rows[0][3:6])
        dx, dy = math.cos(theta), math.sin(theta)
        rf = b if dy < 0 else cb
        r = 1.0 / math.hypot(dx / a, dy / rf)
        return Vector((c.x + dx * r, c.y + dy * r, c.z))

    def graft_legs(self, ob):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        legs = []
        for kind, rows in (('F', self.FRONT_LEG_T), ('H', self.HIND_LEG_T)):
            zc = self.SEAM[kind]
            for s in (1, -1):
                c = Vector((s * rows[0][0], rows[0][1], zc))
                near = lambda p: math.hypot(p.x - c.x, p.y - c.y) < self.GRAFT_NEAR and p.z < zc + 0.08
                dead = [f for f in bm.faces if any(v.co.z < zc for v in f.verts) and near(f.calc_center_median())]
                bmesh.ops.delete(bm, geom=dead, context='FACES')
                rim = self._rim(bm, near)
                for v in rim:
                    v.co = self._ellipse(c, rows, math.atan2(v.co.y - c.y, v.co.x - c.x))
                vs = loft(bm, *self.leg_loft(rows, s))
                pole = vs[-2]
                top = vs[:8]
                bmesh.ops.delete(bm, geom=[pole], context='VERTS')
                _zip(bm, list(rim), top, c)
                tube = set(vs) - {pole}
                legs += list(tube)
                zone = lambda p: near(p) and zc - 0.06 < p.z < zc + 0.08
                tris = [f for f in bm.faces if len(f.verts) == 3 and all(zone(v.co) for v in f.verts)]
                bmesh.ops.beautify_fill(bm, faces=tris, edges=list({e for f in tris for e in f.edges}))
                relax = [v for v in bm.verts if v not in tube and zone(v.co)]
                for _ in range(4):
                    bmesh.ops.smooth_vert(bm, verts=relax, factor=0.5, use_axis_x=True, use_axis_y=True,
                                          use_axis_z=True)
        bad = {f for e in bm.edges if len(e.link_faces) > 2 for f in e.link_faces}   # the zip doubled a face
        if bad:                                                  # onto an edge (the cow): drop them, refill below
            bmesh.ops.delete(bm, geom=list(bad), context='FACES_ONLY')
        left = [e for e in bm.edges if e.is_boundary]           # slivers the zip missed (a rim loop pinched into a
        if left:                                                 # figure 8): small holes, filled
            bmesh.ops.holes_fill(bm, edges=left, sides=12)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.verts.index_update()
        idx = [v.index for v in legs if v.is_valid]
        bm.to_mesh(ob.data)
        bm.free()
        return np.array(idx)

    @staticmethod
    def _rim(bm, near):
        """The stump's cut rim: the longest boundary loop near the leg. Deleting the stump's faces can also open small
        holes beside it (the flank fold, the cow's udder); those are filled, or they stayed open (2026-10-20)."""
        edges = {e for e in bm.edges if e.is_boundary and any(near(v.co) for v in e.verts)}
        loops, seen = [], set()
        for e0 in list(edges):
            if e0 in seen:
                continue
            loop, stack = [], [e0]
            while stack:
                e = stack.pop()
                if e in seen:
                    continue
                seen.add(e)
                loop.append(e)
                stack += [x for v in e.verts for x in v.link_edges if x.is_boundary and x not in seen]
            loops.append(loop)
        loops.sort(key=len, reverse=True)
        for small in loops[1:]:
            bmesh.ops.holes_fill(bm, edges=small, sides=0)
        return {v for e in loops[0] for v in e.verts} if loops else set()

    def leg_centre(self, rows, z):
        zs = np.array([r[2] for r in rows])[::-1]
        return (np.interp(z, zs, np.array([r[0] for r in rows])[::-1]),
                np.interp(z, zs, np.array([r[1] for r in rows])[::-1]))

    # ------------------------------------------------------------------ hooves (D)
    def hoof_rows(self, kind, s):
        """Loft rows of the hoof's horn: two pointed claws (cloven) or one rounded hoof (solid)."""
        x0, y0 = self.FOOT[kind]
        k = self.HOOF_K
        if self.HOOF == 'solid':
            x = s * x0
            return [[(x, y0 + 0.024 * k, 0.026 * k, 0.026 * k, 0.020 * k, 0.026 * k),
                     (x, y0 - 0.004 * k, 0.026 * k, 0.034 * k, 0.026 * k, 0.026 * k),
                     (x, y0 - 0.030 * k, 0.012 * k, 0.026 * k, 0.012 * k, 0.012 * k)]]
        out = []
        for side in (1, -1):
            x, xi = s * (x0 + side * 0.0135 * k), s * (x0 + side * 0.0080 * k)
            out.append([(x, y0 + 0.020 * k, 0.024 * k, 0.012 * k, 0.022 * k, 0.024 * k),
                        (x, y0 - 0.010 * k, 0.022 * k, 0.0135 * k, 0.024 * k, 0.022 * k),
                        (xi, y0 - 0.044 * k, 0.007 * k, 0.0065 * k, 0.007 * k, 0.007 * k)])
        return out

    def dewclaws(self, kind, s):
        rows = self.FRONT_LEG_T if kind == 'F' else self.HIND_LEG_T
        fet = min(rows, key=lambda r: abs(r[2] - 0.130))
        fx, fy, fz = fet[:3]
        back = fy + fet[5]
        k = self.HOOF_K
        return [((s * (fx + side * 0.015 * k), back - 0.006, 0.112), (s * (fx + side * 0.017 * k), back + 0.018 * k,
                                                                       0.084)) for side in (1, -1)]

    # ------------------------------------------------------------------ fur
    def throat_line(self, k=1.0, n=40):
        rows = spline(self.NECK, 3)
        P = rows[:, :3]
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        U = np.array(self.NECK_UP, float)
        out = []
        for i in range(len(P)):
            N = U - (U @ T[i]) * T[i]
            N /= np.linalg.norm(N)
            out.append(P[i] - N * rows[i, 5] * k)
        out = np.array(out)[::-1]
        seg = np.linalg.norm(np.diff(out, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        u = np.linspace(0, cum[-1], n)
        return np.stack([np.interp(u, cum, out[:, j]) for j in range(3)], -1)

    def crest_line(self, n=12, k=1.0):
        """Points along the top of the neck (the neck loft's crest side at k of its radius), poll to withers (D)."""
        rows = spline(self.NECK, 3)
        P = rows[:, :3]
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        U = np.array(self.NECK_UP, float)
        out = []
        for i in range(len(P)):
            N = U - (U @ T[i]) * T[i]
            N /= np.linalg.norm(N)
            out.append(P[i] + N * rows[i, 4] * k)
        out = np.array(out)[::-1]
        seg = np.linalg.norm(np.diff(out, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        u = np.linspace(0, cum[-1], n)
        return np.stack([np.interp(u, cum, out[:, j]) for j in range(3)], -1)

    def mane_mask(self, P):
        """1 under the throat and down the neck's underside to the brisket (D)."""
        Q = self.THROAT[(self.THROAT[:, 1] > self.NECK[-1][1] - 0.09) & (self.THROAT[:, 1] < self.NECK[0][1] - 0.20)]
        d = np.full(len(P), 1e9)
        for a, b in zip(Q[:-1], Q[1:]):
            ab = b - a
            u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.linalg.norm(P - (a + np.outer(u, ab)), axis=1))
        return np.exp(-0.5 * (d / 0.090) ** 2)

    def fur_flow(self, P, N):
        x = P[..., 0]
        one = np.ones_like(x)
        top = np.stack([0 * x, one, -0.30 * one], -1)
        hang = np.stack([0 * x, 0.30 * one, -one], -1)
        w_top = smoothstep(0.30, 0.80, N[..., 2])
        F = top * w_top[..., None] + hang * (1 - w_top[..., None])
        face = np.broadcast_to(self.hx_dir((0.0, 1.0, 0.10)), P.shape)
        w_face = self.face_mask(P)
        F = F * (1 - w_face[..., None]) + face * w_face[..., None]
        F = F - (F * N).sum(-1, keepdims=True) * N
        return F / np.maximum(np.linalg.norm(F, axis=-1, keepdims=True), 1e-6)

    def face_mask(self, P):
        H = self.hx_inv(P)
        y0, y1 = self.FACE_Y
        return (smoothstep(y0, y0 - 0.08, H[..., 1]) * smoothstep(y1, y1 + 0.07, H[..., 1]) *
                smoothstep(-0.26, -0.20, H[..., 2]) * smoothstep(0.20, 0.14, H[..., 2]) *
                smoothstep(0.16, 0.12, np.abs(H[..., 0])))

    def fur_amount(self, P, N):
        A = np.full(len(P), self.FUR_BASE)
        if self.MANE:
            A = A + self.MANE * self.mane_mask(P)
        A = A * (1 - 0.75 * self.face_mask(P))
        return A

    def sculpt_fur(self, co, no, seed=23):
        return beast_body.sculpt_fur(co, no, self.fur_flow, self.fur_amount, seed=seed, across=0.045, along_len=0.13)

    def sculpt_face(self, co, no):
        """Eye sockets under the brow, nostrils."""
        out = co.copy()
        H = self.hx_inv(co)
        Pm = np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1)
        out -= no * (0.010 * _gauss(Pm, self.EYE0_H, (0.024, 0.024, 0.018)))[:, None]
        nc = np.array(self.NOSE_C)
        out -= no * (0.009 * _gauss(Pm, (0.026, nc[1] - 0.014, nc[2] - 0.007), (0.009, 0.008, 0.011)))[:, None]
        return out

    def dec_weight(self, co):
        """0 = keep, 1 = decimate freely: the face, the tail and the legs' stumps keep relatively more."""
        h = self.hx_inv(np.array(co[:]))
        face = h[1] < 0.06 and abs(h[0]) < 0.14 and -0.24 < h[2] < 0.16
        tail = co.y > self.TAIL[0][1] - 0.05 and co.z > self.TAIL[-1][2] - 0.06 and abs(co.x) < 0.08
        ax = abs(co.x)
        fx, fy = self.FRONT_STUMP[0][0], self.FRONT_STUMP[0][1]
        hx_, hy = self.HIND_STUMP[0][0], self.HIND_STUMP[0][1]
        legs = ((math.hypot(ax - fx, co.y - fy) < 0.12 * self.LEG_T and self.SEAM['F'] - 0.1 < co.z <
                 self.FRONT_STUMP[0][2] + 0.06) or
                (math.hypot(ax - hx_, co.y - hy) < 0.14 * self.LEG_T and self.SEAM['H'] - 0.1 < co.z <
                 self.HIND_STUMP[0][2] + 0.02))
        return 1.0 - 0.45 * float(face) - 0.20 * float(tail) - 0.35 * float(legs)

    CREASE_DEG = 55                     # decimation creases sharper than this are relaxed (the deer's slit down the back)

    def relax_creases(self, ob, deg=None, passes=4):
        deg = deg or self.CREASE_DEG
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        lim = math.radians(deg)
        for _ in range(passes):
            bm.normal_update()
            vs = set()
            for e in bm.edges:
                if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > lim:
                    vs.update(v for v in e.verts if self.face_mask(np.array([v.co[:]]))[0] < 0.5)
            if not vs:
                break
            for v in vs:
                ring = [e.other_vert(v).co for e in v.link_edges]
                v.co = v.co * 0.4 + sum(ring, Vector()) / len(ring) * 0.6
        bm.to_mesh(ob.data)
        bm.free()

    def build_fur_body(self, fillet_iters=60):
        bm = bmesh.new()
        self.build_trunk(bm)
        self.build_head(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        body, hi = beast_body.fuse_body(bm, self.PREFIX, self.VOXEL, self.BODY_TRIS,
                                        sculpts=(self.sculpt_face, self.sculpt_fur), dec_weight=self.dec_weight,
                                        seam_x=0.015, flat_z=-1.0, fillet_iters=fillet_iters)
        self.relax_creases(body)
        return body, hi

    # ------------------------------------------------------------------ separate pieces (D)
    def build_pieces(self, low):
        bml = bmesh.new()
        bml.from_mesh(low.data)
        bvh = BVHTree.FromBMesh(bml)
        bml.free()
        bm = bmesh.new()
        tags = {}
        before = set(bm.verts)
        if self.JAW_PIECE:
            tags['jaw'] = loft(bm, self.JAW_H, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.5, cap1=0.6, capk=2,
                               shape=0.85)
        for v in [v for v in bm.verts if v not in before]:
            v.co = Vector(self.hx(v.co[:]))
        eyes = []
        for s in (1, -1):
            n = self.EYE_N * np.array((s, 1, 1))
            c = _snap(bvh, self.EYE0 * np.array((s, 1, 1)), n, 0.06) - n * self.EYE_INSET
            self.LM['eye_L' if s > 0 else 'eye_R'] = c
            self.LM['eye_n_L' if s > 0 else 'eye_n_R'] = n
            vs = dome(bm, c, n, self.EYE_R, self.EYE_DOME * self.EYE_R / 0.026, seg=12, rings=3)
            t, b = (Vector(v) for v in self.eye_axes(n))
            nv, cv = Vector(n), Vector(c)
            for v in vs:
                d = v.co - cv
                v.co = cv + t * (d.dot(t) * self.EYE_LONG) + b * (d.dot(b) * self.EYE_SHORT) + nv * d.dot(nv)
            eyes += vs
        tags['eye'] = eyes
        ears = []
        for s in (1, -1):
            base, tip = self.ear_rows(s)
            ears += cup_ear(bm, base, tip, (s * self.EAR_FRONT[0], self.EAR_FRONT[1], self.EAR_FRONT[2]),
                            self.EAR_PROFILE, hollow=self.EAR_HOLLOW)
        tags['ear'] = ears
        claws = []
        for s in (1, -1):
            for kind in ('F', 'H'):
                for R in self.hoof_rows(kind, s):
                    claws += loft(bm, R, up=self.HOOF_UP, seg=6 if self.HOOF == 'cloven' else 10, per_seg=1,
                                  cap0=self.HOOF_CAPS[0], cap1=self.HOOF_CAPS[1], capk=1, shape=0.8)
                if self.DEWCLAWS:
                    for base, tip in self.dewclaws(kind, s):
                        claws += cone(bm, base, tip, 0.008 * self.HOOF_K, seg=4)
        tags['claw'] = claws
        if self.TAIL_TUBE:                   # a clean tube (fused and decimated, a long thin tail went flat)
            tags['tail'] = loft(bm, self.TAIL_TUBE, up=(0, 1, 0), seg=8, per_seg=3, cap0=0.0, cap1=0.6, capk=2)
        if self.HORN_BASE_H is not None:
            tags['horn'] = self.build_horns(bm)
        self.extra_pieces(bm, bvh, tags)
        return bm, tags

    def extra_pieces(self, bm, bvh, tags):
        """Species: more separate shells (D): tags[part name] += their BMVerts."""

    # ------------------------------------------------------------------ the whole body
    def build_body(self):
        """-> (<Name>Body in R, <PREFIX>_BodyHi). Built in D, warped by W at the end."""
        fur, hi = self.build_fur_body()
        legs = self.graft_legs(fur)
        nfur = len(fur.data.vertices)
        co = np.array([v.co[:] for v in fur.data.vertices])
        H = self.hx_inv(co)
        nose = np.linalg.norm((np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1) - self.NOSE_C) /
                              (np.array(self.NOSE_R) * 1.25), axis=1) < 1.0
        bm, tags = self.build_pieces(fur)
        body, nfur, part_extra = beast_body.join_pieces(fur, bm, tags, self.PREFIX, self.NAME + "Body")
        part_fur = np.where(nose, PART['nose'], PART['fur'])
        body["leg_verts"] = [int(i) for i in legs]
        _write_info(body.data, np.concatenate([part_fur, part_extra[:, 0]]),
                    np.concatenate([np.zeros(nfur), part_extra[:, 1]]))
        for k, v in self.LM.items():                 # D: the painter reads the eyes in D
            body[k] = [float(c) for c in v]
        me = body.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        me.vertices.foreach_set('co', self.W(co.reshape(-1, 3)).ravel())
        me.update()
        hico = np.empty(len(hi.data.vertices) * 3)
        hi.data.vertices.foreach_get('co', hico)
        hi.data.vertices.foreach_set('co', self.W(hico.reshape(-1, 3)).ravel())
        hi.data.update()
        return body, hi

    def tri_report(self, ob):
        out = beast_body.tri_report(ob)
        legs = set(ob.get("leg_verts", []))
        k = sum(len(p.vertices) - 2 for p in ob.data.polygons if all(v in legs for v in p.vertices))
        out['fur'] -= k
        out['leg'] = k
        return out

    # ------------------------------------------------------------------ skeleton (built in D, warped)
    def rest_bones(self):
        """name -> (head, Matrix3 frame, length, parent, deform) in R; the deer's names and conventions."""
        T = {}

        def bone(name, head, tail, zhint, parent, deform=True):
            T[name] = (np.array(head, float), np.array(tail, float), zhint, parent, deform)
        UP, FWD = (0, 0, 1), (0, -1, 0)
        head_up = tuple(self.hx_dir((0, 0, 1)))
        h0, h1 = self.hx((0, 0.0, -0.05)), self.hx((0, -self.HEAD_LEN, -0.05))
        bone("Hips", *self.HIPS, UP, "Root")
        bone("Spine1", self.SPINE[0], self.SPINE[1], UP, "Hips")
        bone("Spine2", self.SPINE[1], self.SPINE[2], UP, "Spine1")
        bone("Chest", self.SPINE[2], self.SPINE[3], UP, "Spine2")
        nb = list(self.NECK_BONES) + [tuple(h0)]
        par = "Chest"
        for i in range(3):
            bone(f"Neck{i + 1}", nb[i], nb[i + 1], UP, par)
            par = f"Neck{i + 1}"
        bone("Head", h0, h1, head_up, "Neck3")
        jaw_tip = self.JAW_H[-1]
        bone("Jaw", self.HINGE, self.hx((0, jaw_tip[1], jaw_tip[2] - 0.011)), head_up, "Head")
        par = "Hips"
        for i in range(len(self.TAIL) - 1):
            bone(f"Tail{i + 1}", self.TAIL[i], self.TAIL[i + 1], (0, 1, 0.3), par)
            par = f"Tail{i + 1}"
        J = self.J
        for s, sfx in ((1, "L"), (-1, "R")):
            m = (lambda p: p) if s > 0 else _mx
            base, tip = self.ear_rows(s)
            bone(f"Ear{sfx}", base, tip, FWD, "Head")
            bone(f"Scapula{sfx}", m(J['SCAP']), m(J['SHO']), FWD, "Chest")
            bone(f"UpperArm{sfx}", m(J['SHO']), m(J['ELB']), FWD, f"Scapula{sfx}")
            bone(f"Forearm{sfx}", m(J['ELB']), m(J['WRI']), FWD, f"UpperArm{sfx}")
            bone(f"FrontPaw{sfx}", m(J['WRI']), m(J['FPAW']), FWD, f"Forearm{sfx}")
            bone(f"FrontToes{sfx}", m(J['FPAW']), m(J['FTOE']), UP, f"FrontPaw{sfx}")
            bone(f"Thigh{sfx}", m(J['HIP']), m(J['KNEE']), FWD, "Hips")
            bone(f"Shin{sfx}", m(J['KNEE']), m(J['HOCK']), FWD, f"Thigh{sfx}")
            bone(f"HindFoot{sfx}", m(J['HOCK']), m(J['HPAW']), FWD, f"Shin{sfx}")
            bone(f"HindToes{sfx}", m(J['HPAW']), m(J['HTOE']), UP, f"HindFoot{sfx}")
        top = self.hx((0, -0.08, 0.10))
        mouth = self.hx((0, -0.72 * self.HEAD_LEN, -0.160))
        up = np.array((0, 0, 0.1))
        bone("Socket_Head", top, top + up, FWD, "Head")
        bone("Socket_Mouth", mouth, mouth + up, FWD, "Jaw")
        bone("Socket_Back", self.BACK_SOCKET, np.array(self.BACK_SOCKET) + up, FWD, "Spine2")
        self.extra_bones(bone)
        up_fwd = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))).transposed()
        B = {"Root": (Vector((0, 0, 0)), up_fwd, 0.4, None, False),
             "Motion": (Vector((0, 0, 0)), up_fwd.copy(), 0.3, None, True)}
        for name, (h, t, zh, par, deform) in T.items():
            hr, tr = Vector(self.W(h)), Vector(self.W(t))
            if name.startswith("Socket_"):            # sockets keep their 0.1 m length, straight up
                tr = hr + Vector((0, 0, 0.1))
            hh, fr = _frame(hr, tr - hr, zh)
            B[name] = (hh, fr, (tr - hr).length, par, deform)
        return B

    def extra_bones(self, bone):
        """Species: more bones / sockets: bone(name, head, tail, zhint, parent) in D."""

    # ------------------------------------------------------------------ horns (D): clean lofted tubes, rigid on Head
    HORN_BASE_H = None                  # head space (left), or None: no horns
    HORN = []                           # (dx out, dy back, dz up, radius) from the base, in body axes (D)
    HORN_SEG = 8

    def horn_rows(self, s):
        p = self.hx(np.array(self.HORN_BASE_H) * np.array((s, 1, 1)))
        m = np.array((s, 1, 1))
        return [tuple(p + np.array(r[:3]) * m) + (r[3],) for r in self.HORN]

    def build_horns(self, bm):
        vs = []
        if self.HORN_BASE_H is None:
            return vs
        for s in (1, -1):
            R = [r[:3] + (r[3], r[3], r[3]) for r in self.horn_rows(s)]
            d = np.array(R[-1][:3]) - np.array(R[0][:3])
            up = (0, 0, 1) if abs(d[2]) < 0.7 * np.linalg.norm(d) else (0, -1, 0)
            vs += loft(bm, R, up=up, seg=self.HORN_SEG, per_seg=3, cap0=0.0, cap1=0.5, capk=2)
        return vs

    # ------------------------------------------------------------------ clip settings (farm_anim), the deer's
    CADENCE = 1.0                       # x the clips' lengths after the sqrt(KL) scaling
    EAR_SWING, TAIL_SWING = 1.0, 1.0
    TAIL_FLOOR = None                   # (R) per tail bone, the lowest its end goes (beast_anim's tail drag)
    TAIL_HANGS = False                  # a long hanging tail stays hanging when the trunk tips (farm_anim._tail)
    GRAZE = ((-44, -40, -30), 76, 0.10, 0.0)      # neck pitches, head pitch, chest drop (x KB), head tilt
    GRAZE_PITCH = -13
    UP_HIGH = ((18, 4, -2), -3)
    CALL_HEAD, CALL_JAW = 22, 24
    RUN = (3.80, 1.0)                   # stride (x KL), back flex
    RUN_NECK = ((-26, -14, -4), 50)
    LIE_NECK = ((-16, -14, -6), 18)
    LIE_DROP = None                     # (R) the trunk sinks this far lying on its belly; None: 0.53 x KL
    SIDE_REST = None                    # (R) the trunk's centre height lying on its side; None: 0.26 x KX
    DEATH_HEAD_ROLL = 20
    ATTACK = False

    # ------------------------------------------------------------------ painter and rig defaults (farm_paint, farm_rig)
    COAT_ON_TRUNK = None                # (z0, z1, least) in D: see farm_rig._coat_on_trunk
    BELLY_CUT = 0.80                    # (D) the trunk's UV cut runs below this
    UV_SCALE = {}
    MISC = {}
    COATS = {}
    PUPIL = 'bar'
    COAT_STYLE = 'sleek'
    EAR_RIM = 0.75
    EYE_RING = 0.8                      # the dark rim painted round the eye (the deer's)

    def coat_pattern(self, ctx, col):
        return col

    def face_pattern(self, ctx, fcol):
        return fcol

    def paint_pieces(self, ctx, col, smooth):
        return col, smooth

    def wool_mask(self, P):
        return np.zeros(len(P))

    TAIL_TUBE = None                    # (D) loft rows of a separate tail tube (PART tail), root inside the rump

    def jaw_weight(self):
        """Species: fn(D positions) -> how much each skin vertex follows the jaw, or None for farm_rig's (the jowls'
        bottoms; the jaw itself is a separate piece)."""
        return None

    def skin_extra(self, body, rig, part):
        """Species: weights of its own shells (after the generic skin)."""
