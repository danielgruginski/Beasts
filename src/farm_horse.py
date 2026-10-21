"""Horse (farm animal, 2026-10-20): a medieval rouncey, 1.45 m, on farm_body.Hoofed with its own proportions.

An everyday riding and draught horse of the time: 1.45 m at the withers (about 14 hands), body length about the
withers height, high withers, a deep girth and round barrel tucking up into the flank, round muscled hindquarters, a
thick crested neck carried up, the mane a raised crest painted as hair falling to the right and a painted forelock, a
long head with wide jowls, a straight face and a soft muzzle, upright ears, big eyes, strong legs (muscled forearm and
gaskin, flat knees, thick cannons, knobby fetlocks, short sloping pasterns) on big flared hooves, a full tail of hair
falling close to the buttocks. Oval pupils. Coats: 'bay' (red-brown, black mane, tail and lower legs), 'chestnut'
(red, a blaze and white hind socks), 'grey' (dapple grey, dark legs), 'black'.
"""
import numpy as np
from mathutils import Vector
from beast_common import loft, smoothstep, vnoise, fbm
from beast_body import PART
import farm_body
from farm_paint import _mix, _streaks

FACE_K, FACE_FROM = 0.85, -0.11       # the face in front of the eyes, shortened (Daniel: "too long"): head-space y


def _face(y):
    """Head-space y with the face (in front of FACE_FROM, the eyes) shortened by FACE_K."""
    return y if y > FACE_FROM else FACE_FROM + (y - FACE_FROM) * FACE_K


class Horse(farm_body.Hoofed):
    NAME, PREFIX = "Horse", "HRS"
    # Rebuilt on horse proportions (2026-10-20, Daniel: "the horse still needs serious improvements"): the deer's
    # tables made a long flat barrel, a llama's neck and deer legs. A plain 1.2x warp now, the tables a 1.21 m horse
    # in deer units: body length = withers height, the girth at half of it, knee 0.28, hock 0.32, fetlock 0.12.
    KX, KY, KL, KB = 1.20, 1.08, 1.20, 1.20                 # y shorter: body length = withers height
    KH = (0.95, 1.16, 1.12)
    VOXEL, BODY_TRIS = 0.006, 3400
    CREASE_DEG = 40
    FILLET = 35                               # keep the throatlatch's notch behind the jowl

    J = dict(SCAP=(0.100, -0.38, 1.130), SHO=(0.160, -0.62, 0.800), ELB=(0.160, -0.42, 0.640),
             WRI=(0.150, -0.442, 0.345), FPAW=(0.145, -0.455, 0.145), FTOE=(0.142, -0.570, 0.008),
             HIP=(0.120, 0.40, 1.000), KNEE=(0.160, 0.30, 0.700), HOCK=(0.138, 0.560, 0.400),
             HPAW=(0.135, 0.540, 0.145), HTOE=(0.132, 0.425, 0.008))
    TAIL = [(0, 0.660, 1.020), (0, 0.730, 0.900), (0, 0.770, 0.660), (0, 0.770, 0.400)]
    TAIL_R = None
    TAIL_TUBE = [(0, 0.620, 1.020, 0.035, 0.035, 0.035), (0, 0.680, 1.000, 0.040, 0.042, 0.042),
                 (0, 0.730, 0.900, 0.046, 0.048, 0.048), (0, 0.760, 0.720, 0.055, 0.058, 0.058),
                 (0, 0.770, 0.520, 0.058, 0.058, 0.058), (0, 0.770, 0.400, 0.045, 0.045, 0.045),
                 (0, 0.765, 0.340, 0.016, 0.016, 0.016)]                 # a full rope of hair to the hocks
    POLL = (0.0, -0.95, 1.49)
    HEAD_PITCH = 66.0                         # the face hangs nearly upright off an arched neck
    HEAD_LEN = -_face(-0.39)
    EYE0_H = (0.086, -0.108, 0.010)            # high, at the head's widest, under a bony brow
    EYE_N_H = (0.86, -0.30, 0.30)
    EYE_R = 0.034
    JOWL = (-0.055, -0.128, 0.092)            # (y, z, radius) head space: the jowl's disc, its top below the eye
    EYE_AXIS = (0.0, 1.0, 0.20)
    EYE_LONG, EYE_SHORT = 1.05, 0.92
    EYE_INSET, EYE_DOME = 0.004, 0.011       # large, set into the head, not a bulging dome
    EYE_RING = 0.35                           # a thin lid line, not the deer's dark ring
    NOSE_C, NOSE_R = (0.0, -0.30, -0.06), (0.001, 0.001, 0.001)   # no nose pad: a horse has a soft muzzle
    NOSTRIL_H = (0.031, _face(-0.364), -0.036)      # the nostrils (left), on the muzzle's front corners
    EAR_BASE_H = (0.040, -0.012, 0.030)       # on the skull's top sides at the poll, the base just inside it
                                              # (set for the old head angle they floated 2.5 cm above it)
    EAR_DIR = (0.10, 0.06, 0.99)              # small, upright, close together
    EAR_LEN = 0.13
    EAR_PROFILE = ((0.0, 0.034, 0.026), (0.35, 0.044, 0.030), (0.70, 0.030, 0.020), (0.94, 0.008, 0.006))
    EAR_FRONT = (0.25, -1.0, 0.0)
    TRUNK_ROWS = [(-0.66, 0.90, 0.140, 0.160, 0.170), (-0.52, 0.92, 0.200, 0.250, 0.280),   # breast, girth: deep
                  (-0.35, 0.93, 0.225, 0.255, 0.290), (-0.12, 0.93, 0.245, 0.240, 0.285),   # a round barrel
                  (0.10, 0.94, 0.245, 0.230, 0.260), (0.28, 0.96, 0.230, 0.220, 0.205),     # the flank tucks up
                  (0.42, 0.97, 0.235, 0.220, 0.200), (0.56, 0.95, 0.200, 0.205, 0.220),     # croup and buttocks
                  (0.66, 0.92, 0.120, 0.140, 0.150)]
    NECK = [(0, -0.45, 0.98, 0.170, 0.220, 0.280), (0, -0.57, 1.13, 0.150, 0.190, 0.200),   # an arched neck:
            (0, -0.66, 1.29, 0.130, 0.165, 0.110), (0, -0.76, 1.41, 0.105, 0.120, 0.045),   # the crest curves
            (0, -0.88, 1.46, 0.085, 0.095, 0.032)]                                          # forward over the
    # poll and the throat comes in high and thin, behind the jowl (with the head upright the jowl sits behind the
    # poll: a fuller throat swallowed it)
    NECK_BONES = [(0, -0.50, 1.060), (0, -0.62, 1.210), (0, -0.74, 1.370)]
    HIPS = ((0, 0.40, 1.000), (0, 0.66, 0.980))
    SPINE = [(0, 0.40, 1.020), (0, 0.10, 1.060), (0, -0.20, 1.080), (0, -0.50, 1.060)]
    BACK_SOCKET = (0, -0.15, 1.240)
    BODY_C = (0.0, -0.05, 0.93)
    TRUNK_BLOBS = [((0, -0.40, 1.16), (0.060, 0.200, 0.070), 0, False),           # the withers
                   ((0.170, -0.46, 0.92), (0.075, 0.170, 0.260), -30, True),     # the shoulder, sloping
                   ((0.080, -0.64, 0.82), (0.080, 0.080, 0.110), 0, True),       # the breast's two muscles
                   ((0.160, -0.43, 0.74), (0.080, 0.110, 0.110), 0, True),       # the upper arm to the elbow
                   ((0.120, 0.44, 1.05), (0.110, 0.200, 0.160), 0, True),        # the croup's muscle
                   ((0.130, 0.55, 0.86), (0.085, 0.100, 0.180), 0, True),        # the buttock and hamstring
                   ((0.170, 0.30, 0.78), (0.060, 0.080, 0.100), 0, True)]        # the stifle, forward in the flank
    FRONT_STUMP = [(0.160, -0.43, 0.78, 0.085, 0.090, 0.090), (0.160, -0.42, 0.66, 0.080, 0.085, 0.090),
                   (0.155, -0.43, 0.56, 0.062, 0.070, 0.060), (0.152, -0.435, 0.47, 0.052, 0.060, 0.050)]
    HIND_STUMP = [(0.150, 0.36, 0.86, 0.090, 0.100, 0.120), (0.155, 0.40, 0.72, 0.080, 0.090, 0.110),
                  (0.145, 0.50, 0.60, 0.058, 0.060, 0.075), (0.140, 0.515, 0.51, 0.048, 0.050, 0.060)]
    # the lower legs: a muscled forearm into a flat broad knee, a cannon with the tendon behind, a knobby fetlock,
    # a short sloping pastern, the coronet inside the hoof; the hind: the gaskin into a sharp hock
    FRONT_LEG = [(0.152, -0.437, 0.495, 0.050, 0.055, 0.050), (0.150, -0.440, 0.400, 0.040, 0.042, 0.040),
                 (0.150, -0.442, 0.345, 0.044, 0.042, 0.042), (0.148, -0.444, 0.290, 0.036, 0.030, 0.040),
                 (0.146, -0.446, 0.200, 0.033, 0.028, 0.040), (0.145, -0.455, 0.145, 0.040, 0.036, 0.046),
                 (0.143, -0.490, 0.090, 0.034, 0.032, 0.034), (0.142, -0.510, 0.060, 0.040, 0.042, 0.040)]
    HIND_LEG = [(0.140, 0.515, 0.535, 0.046, 0.048, 0.058), (0.138, 0.555, 0.420, 0.042, 0.040, 0.055),
                (0.137, 0.565, 0.390, 0.036, 0.034, 0.050), (0.136, 0.550, 0.300, 0.033, 0.028, 0.040),
                (0.135, 0.545, 0.200, 0.033, 0.028, 0.040), (0.135, 0.540, 0.145, 0.040, 0.036, 0.046),
                (0.133, 0.505, 0.090, 0.034, 0.032, 0.034), (0.132, 0.485, 0.060, 0.040, 0.042, 0.040)]
    SEAM = {'F': 0.530, 'H': 0.565}
    FOOT = {'F': (0.142, -0.510), 'H': (0.132, 0.485)}
    GRAFT_NEAR = 0.12
    BELLY_CUT = 0.80
    LEG_T = LEG_T_LOW = 1.0
    HOOF, DEWCLAWS = 'solid', False
    HOOF_UP, HOOF_CAPS = (0, -1, 0), (0.4, 0.0)

    def hoof_rows(self, kind, s):
        """A horse's hoof: a flared cylinder from the coronet to a flat sole, the wall sloping forward."""
        x0, y0 = self.FOOT[kind]
        x = s * x0
        return [[(x, y0 - 0.004, 0.075, 0.040, 0.046, 0.036), (x, y0 - 0.012, 0.040, 0.050, 0.060, 0.044),
                 (x, y0 - 0.016, 0.006, 0.054, 0.066, 0.046)]]

    # The head as a wedge (head space): deepest at the big flat cheek, a straight face line, tapering to a smaller
    # soft muzzle; the bottom line climbs from the cheek's round edge to the lips. (y, top, bottom, half width)
    HEAD_PROFILE = [(0.03, 0.050, -0.105, 0.060), (-0.04, 0.055, -0.175, 0.072), (-0.12, 0.045, -0.165, 0.072),
                    (-0.20, 0.025, -0.115, 0.062), (-0.28, 0.008, -0.090, 0.050), (-0.34, -0.004, -0.088, 0.050),
                    (-0.38, -0.012, -0.090, 0.047)]     # a short wedge: a deep jowl, a small muzzle
    HEAD_ROWS = [(_face(y), (t + b) / 2, w, (t - b) / 2, (t - b) / 2) for y, t, b, w in HEAD_PROFILE]
    HEAD_SHAPE = 0.85
    HEAD_CAP = 0.45
    HEAD_BLOBS = [((0, -0.060, 0.004), (0.086, 0.095, 0.052), False),            # the cranium, a flat forehead
                  ((0, 0.010, -0.090), (0.040, 0.050, 0.040), False),            # the throatlatch, narrow
                  ((0.066, -0.055, -0.128), (0.042, 0.092, 0.092), True),        # the jowl: a big round disc, standing out
                  ((0.036, _face(-0.352), -0.032), (0.022, 0.030, 0.026), True),  # the nostril's flared rim
                  ((0.026, _face(-0.372), -0.078), (0.028, 0.034, 0.024), True)]  # the rounded upper lip
    HINGE_H = (0.0, -0.07, -0.112)
    JAW_SCALE = 0.35                          # the fused lips only part a little (wider stretched them into a curtain)
    JAW_PIECE = False                         # the lower jaw is skin to the lips: fused, moved by its weights (a
    JAW_H = [(0, -0.10, -0.150, 0.044, 0.030, 0.034), (0, -0.18, -0.118, 0.040, 0.024, 0.026),   # separate jaw
             (0, -0.26, -0.100, 0.036, 0.020, 0.020), (0, -0.34, -0.098, 0.032, 0.020, 0.022)]   # showed as a plank)
    JAW_H = [(x, _face(y), z, a, b, c) for x, y, z, a, b, c in JAW_H]
    MOUTH_LINE = tuple((_face(y), z) for y, z in ((-0.39, -0.090), (-0.33, -0.092), (-0.27, -0.094)))  # the lips

    def jaw_weight(self):
        ys = np.array([p[0] for p in self.MOUTH_LINE])[::-1]
        zs = np.array([p[1] for p in self.MOUTH_LINE])[::-1]

        def fn(cu):
            H = self.hx_inv(cu)
            line = np.interp(H[:, 1], ys, zs)
            return (smoothstep(line + 0.006, line - 0.010, H[:, 2]) * smoothstep(-0.16, -0.26, H[:, 1]) *
                    smoothstep(0.075, 0.05, np.abs(H[:, 0])) *          # bounded on every side: with the head
                    smoothstep(line - 0.090, line - 0.060, H[:, 2]) *     # upright, belly skin between the forelegs
                    smoothstep(-0.48, -0.44, H[:, 1]))                    # fell inside it and grazed with the head
        return fn

    def sculpt_face(self, co, no):
        """Eye sockets under the brow; the nostrils: deep comma-shaped dents on the muzzle's front corners."""
        from beast_body import _gauss
        out = co.copy()
        H = self.hx_inv(co)
        Pm = np.stack([np.abs(H[:, 0]), H[:, 1], H[:, 2]], -1)
        out -= no * (0.008 * _gauss(Pm, self.EYE0_H, (0.022, 0.022, 0.016)))[:, None]
        nx, ny, nz = self.NOSTRIL_H
        out -= no * (0.016 * _gauss(Pm, (nx - 0.004, ny, nz), (0.010, 0.014, 0.016)))[:, None]
        out -= no * (0.008 * _gauss(Pm, (nx + 0.004, ny + 0.012, nz + 0.018), (0.008, 0.012, 0.010)))[:, None]  # its curl
        return out

    MANE = 0.0
    TAIL_HANGS, TAIL_SWING = True, 0.45
    FUR_BASE = 0.0015
    PUPIL = 'oval'
    EAR_RIM = 0.4
    GRAZE = ((-74, -12, -10), 88, 0.08, 0.0)  # the neck reaches forward and down from its base, nearly straight
    GRAZE_PITCH = -16                         # (the deer's bends folded the horse's thick neck into a U)
    COAT_ON_TRUNK = (0.84, 1.02, 0.20)        # the croup's muscle rides on the spine (the thigh heaved it up)

    # The mane is the body itself (as the deer's): a raised crest fused along the top of the neck, painted as hair
    # falling to the right, the forelock painted on the forehead. A separate blade read as a black stick floating
    # over the crest from behind.
    def extra_parts(self, bm):
        pts = list(self.crest_line(10, 0.90)) + [np.array((0.0, -0.40, 1.17))]
        n = len(pts)
        rows = [(0.0, p[1], p[2], 0.035 + 0.012 * np.sin(np.pi * i / (n - 1)), 0.040 * np.sin(np.pi * (0.1 + 0.8 * i / (n - 1))) + 0.012,
                 0.030) for i, p in enumerate(pts)]
        loft(bm, rows, up=(0, 0, 1), seg=12, per_seg=2, cap0=0.6, cap1=0.6)

    def mane_mask(self, P):
        """1 on the mane (D): along the crest, falling further down the right side; 0 elsewhere."""
        Q = self.crest_line(24, 1.0)
        d = np.full(len(P), 1e9)
        for a_, b_ in zip(Q[:-1], Q[1:]):
            ab = b_ - a_
            u = np.clip(((P - a_) @ ab) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.linalg.norm(P - (a_ + np.outer(u, ab)), axis=1))
        w = np.where(P[:, 0] < 0, 0.120, 0.072) + 0.025 * vnoise(P * 18.0, seed=73)
        return smoothstep(w, w - 0.02, d) * smoothstep(-0.30, -0.42, P[:, 1])

    def forelock_mask(self, ctx):
        hx, hy, hz = np.abs(ctx['hx']), ctx['hy'], ctx['hz']
        w = 0.045 - 0.16 * np.clip(-hy - 0.02, 0, None)
        return smoothstep(w, w - 0.012, hx) * smoothstep(0.03, 0.0, hy) * smoothstep(-0.20, -0.15, hy) *             smoothstep(-0.01, 0.03, hz)

    def _hair_col(self, ctx, flow):
        st = _streaks(ctx['P'], np.tile(flow, (ctx['n'], 1)), 82, across=0.005, length=0.10, steps=9)
        return np.tile(ctx['C']['mane'], (ctx['n'], 1)) * (0.70 + 0.50 * st)[:, None]

    COATS = {
        'bay': dict(back='#5e321a', flank='#6a3a1e', light='#82502e', belly='#6a4028', tail='#151210',
                    legs='#16120f', edge='#0e0b09', face='#5e321a', muzzle='#2a1c14', chin='#4a2e1e',
                    iris='#2a1a0e', mane='#141110'),
        'chestnut': dict(back='#7e3e1c', flank='#8a4622', light='#a45c32', belly='#8e5232', tail='#8a4a26',
                         legs='#7a4022', edge='#2e1a0e', face='#7e3e1c', muzzle='#5a3424', chin='#8a5a3e',
                         iris='#2a1a0e', mane='#94522a', blaze='#ece6dc', sock='#ece6dc', nose='#6a4a42'),
        'grey': dict(back='#a8a49c', flank='#b2aea6', light='#cfccc4', belly='#c4c0b8', tail='#d6d2ca',
                     legs='#4a4642', edge='#24221f', face='#9a968e', muzzle='#3a3634', chin='#8e8a84',
                     iris='#2a1a0e', mane='#dcd8d0', dapple='#6e6a64'),
        'black': dict(back='#1c1816', flank='#201b18', light='#36302b', belly='#26201c', tail='#100e0d',
                      legs='#141210', edge='#0a0908', face='#1e1a17', muzzle='#141110', chin='#2a2420',
                      iris='#2a1a0e', mane='#0e0c0b'),
    }
    MISC = dict(hoof='#2a2420', hoof_light='#5a5048', ear_in='#3a2e26')

    # ------------------------------------------------------------------ relief (a normal map, T_Horse_Normal)
    RELIEF_STRENGTH = 5.0

    @staticmethod
    def _seg_dist(P, pts):
        """Distance from P to a polyline through pts (left side: P's x should be |x|)."""
        d = np.full(len(P), 1e9)
        for a, b in zip(pts[:-1], pts[1:]):
            a, b = np.asarray(a, float), np.asarray(b, float)
            ab = b - a
            u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.linalg.norm(P - (a + np.outer(u, ab)), axis=1))
        return d

    def relief(self, ctx):
        """The forms a sculpt would carry: the jowl's raised disc and its rim, the nostrils' hollows and flared rims,
        the eyelids and the brow, the neck's crest muscle and jugular groove, the shoulder blade, the triceps' back
        edge, the chest's division and the hamstring line. Heights roughly -1..1 (D units, tens of mm wide)."""
        P, N, furp = ctx['P'], ctx['N'], ctx['furp'] | ctx['legp']
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        Pm = np.stack([np.abs(x), y, z], -1)
        hx, hy, hz = np.abs(ctx['hx']), ctx['hy'], ctx['hz']
        h = np.zeros(len(P))
        # the jowl: a raised round disc with a groove round its edge, on the sides of the head
        jy, jz, jrad = self.JOWL
        jr = np.sqrt(((hy - jy) / jrad) ** 2 + ((hz - jz) / jrad) ** 2)
        side = smoothstep(0.03, 0.06, hx) * smoothstep(0.30, 0.20, -hy)
        h += side * (0.40 * smoothstep(1.00, 0.65, jr) - 0.45 * np.exp(-((jr - 1.03) / 0.09) ** 2))   # (in URP a
                                                                                                    # harder rim read
                                                                                                    # as an ear-muff)
        # the nostrils: deep hollows, the flared rim round them
        nx, ny, nz = self.NOSTRIL_H
        dn = np.sqrt(((hx - nx) / 0.012) ** 2 + ((hy - ny) / 0.016) ** 2 + ((hz - nz) / 0.020) ** 2)
        h += -1.2 * np.exp(-dn ** 2) + 0.45 * np.exp(-((dn - 1.7) / 0.5) ** 2)
        # the eyes: a raised lid ring, the brow's ridge above, a soft hollow above the brow
        for sfx in ('L', 'R'):
            c = np.array(ctx['D']['eyes']['eye_' + sfx])
            d = np.linalg.norm(P - c, axis=1) / self.EYE_R
            on = (x > 0) if sfx == 'L' else (x <= 0)
            above = np.clip((P - c) @ np.array(self.hx_dir((0.0, 0.3, 1.0))), 0, None) / self.EYE_R
            h += on * (0.6 * np.exp(-((d - 1.18) / 0.16) ** 2) + 0.35 * np.exp(-((d - 1.7) / 0.35) ** 2) *
                       smoothstep(0.2, 0.9, above) - 0.3 * np.exp(-((d - 2.6) / 0.5) ** 2) * smoothstep(0.5, 1.5, above))
        # the neck: the jugular groove low on its side and the muscle above it, from behind the jowl to the chest
        rows = [r for r in self.NECK]
        jug = [(r[3] * 0.62, r[1] + 0.02, r[2] - r[5] * 0.45) for r in rows]
        dj = self._seg_dist(Pm, jug)
        zj = np.interp(-y, [-p[1] for p in jug], [p[2] for p in jug])
        body = np.zeros(len(P))                    # the body's forms, doubled below (fewer texels than the head)
        body += -0.7 * np.exp(-(dj / 0.020) ** 2) + 0.35 * np.exp(-((dj - 0.050) / 0.025) ** 2) *             smoothstep(-0.01, 0.02, z - zj)          # (a hard step here drew a crack across the neck)
        # the crest's muscle: a raised band just under the mane on both sides
        cr = self.crest_line(16, 0.85)
        dc = self._seg_dist(Pm, [(abs(p[0]) + 0.06, p[1], p[2] - 0.03) for p in cr])
        body += 0.35 * np.exp(-(dc / 0.035) ** 2)
        # the shoulder blade: a raised plate from the withers down to the point of the shoulder, its back edge (the
        # triceps line) grooved down to the elbow, a groove where the neck meets its front edge
        J = self.J
        a, b = np.array(J['SCAP']) + np.array((0.06, 0, 0)), np.array(J['SHO']) + np.array((0.02, 0.05, 0.05))
        ab = b - a
        u = np.clip(((Pm - a) @ ab) / (ab @ ab), 0, 1)
        dsc = np.linalg.norm(Pm - (a + np.outer(u, ab)), axis=1)
        body += 0.45 * smoothstep(0.075, 0.04, dsc) * smoothstep(0.10, 0.13, np.abs(x))
        tri = [(0.18, -0.33, 1.02), (0.19, -0.37, 0.84), (0.17, -0.40, 0.68)]
        body += -0.6 * np.exp(-(self._seg_dist(Pm, tri) / 0.018) ** 2)
        front = [(0.14, -0.44, 1.12), (0.17, -0.56, 0.96), (0.17, -0.66, 0.80)]
        body += -0.45 * np.exp(-(self._seg_dist(Pm, front) / 0.020) ** 2)
        # the chest's division between the two breast muscles; the hamstring line down the back of the thigh
        body += -0.5 * np.exp(-(x / 0.014) ** 2) * smoothstep(-0.58, -0.64, y) * smoothstep(0.62, 0.70, z) *             smoothstep(0.95, 0.88, z)
        ham = [(0.15, 0.62, 0.98), (0.17, 0.60, 0.80), (0.15, 0.53, 0.62)]
        body += -0.5 * np.exp(-(self._seg_dist(Pm, ham) / 0.020) ** 2)
        head = smoothstep(0.10, 0.0, hy) * smoothstep(-0.30, -0.24, hz)   # (the head's own forms stay as they are)
        return (h + 2.0 * body * (1 - head)) * furp

    def coat_pattern(self, ctx, col):
        C, P, z, y = ctx['C'], ctx['P'], ctx['z'], ctx['y']
        if 'dapple' in C:                      # dapple grey: a dark net round paler spots, fading on the legs
            v = vnoise(P * 11.0, seed=71) * 0.7 + vnoise(P * 23.0, seed=72) * 0.3
            net = smoothstep(0.10, -0.15, v) * smoothstep(0.45, 0.65, z) * ctx['furp']
            col = _mix(col, C['dapple'], 0.65 * net)
        if 'sock' in C:                        # white hind socks
            sock = (y > 0) * smoothstep(0.30, 0.24, z + 0.03 * ctx['n_mid']) * (ctx['furp'] | ctx['legp'])
            col = _mix(col, C['sock'], sock)
        mm = self.mane_mask(P) * ctx['furp']
        col = _mix(col, self._hair_col(ctx, (-0.4, 0.2, -1.0)), mm)
        ctx['mane'] = mm
        tp = ctx['part'] == PART['tail']
        if tp.any():
            st = _streaks(P, np.tile((0.0, 0.25, -1.0), (len(P), 1)), 81, across=0.006, length=0.14, steps=9)
            tc = np.tile(C['tail'], (len(P), 1)) * (0.75 + 0.45 * st)[:, None]
            col = np.where(tp[:, None], tc, col)
        return col

    def face_pattern(self, ctx, fcol):
        C = ctx['C']
        if 'blaze' in C:
            hx, hy, hz = np.abs(ctx['hx']), ctx['hy'], ctx['hz']
            w = 0.022 + 0.018 * smoothstep(-0.15, -0.40, hy)
            blaze = smoothstep(w, w - 0.008, hx) * smoothstep(-0.06, -0.10, hy) * smoothstep(-0.44, -0.40, hy)
            fcol = _mix(fcol, C['blaze'], blaze * smoothstep(-0.02, 0.03, hz + 0.08 * (-hy)))
        hx, hy, hz = np.abs(ctx['hx']), ctx['hy'], ctx['hz']
        nx, ny, nz = self.NOSTRIL_H
        nos = np.exp(-(((hx - nx) / 0.012) ** 2 + ((hy - ny) / 0.016) ** 2 + ((hz - nz) / 0.020) ** 2))
        fcol = _mix(fcol, C['muzzle'] * 0.45, smoothstep(0.25, 0.7, nos))          # the nostrils, dark openings
        jy, jz, jrad = self.JOWL
        jr = np.sqrt(((hy - jy) / jrad) ** 2 + ((hz - jz) / jrad) ** 2)              # the jowl's round edge:
        fcol = _mix(fcol, C['muzzle'], 0.30 * smoothstep(0.80, 0.95, jr) * smoothstep(1.12, 0.97, jr) *   # a soft
                    smoothstep(0.03, 0.06, hx))                                                          # shadow
        lips = smoothstep(-0.086, -0.096, hz) * smoothstep(-0.30, -0.34, hy)
        fcol = _mix(fcol, C['muzzle'] * 0.6, 0.6 * lips)
        fcol = _mix(fcol, self._hair_col(ctx, (0.0, -0.3, -1.0)), ctx['mane'])      # the mane up to the poll
        return _mix(fcol, self._hair_col(ctx, (0.0, -1.0, -0.3)), self.forelock_mask(ctx))

SP = Horse()
