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


class Horse(farm_body.Hoofed):
    NAME, PREFIX = "Horse", "HRS"
    # Rebuilt on horse proportions (2026-10-20, Daniel: "the horse still needs serious improvements"): the deer's
    # tables made a long flat barrel, a llama's neck and deer legs. A plain 1.2x warp now, the tables a 1.21 m horse
    # in deer units: body length = withers height, the girth at half of it, knee 0.28, hock 0.32, fetlock 0.12.
    KX, KY, KL, KB = 1.20, 1.08, 1.20, 1.20                 # y shorter: body length = withers height
    KH = (0.92, 1.16, 1.12)
    VOXEL, BODY_TRIS = 0.006, 3400
    CREASE_DEG = 40

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
    POLL = (0.0, -0.94, 1.47)
    HEAD_PITCH = 52.0
    HEAD_LEN = 0.45
    EYE0_H = (0.084, -0.118, 0.008)            # high, at the head's widest, under a bony brow
    EYE_N_H = (0.86, -0.30, 0.30)
    EYE_R = 0.030
    EYE_AXIS = (0.0, 1.0, 0.20)
    NOSE_C, NOSE_R = (0.0, -0.30, -0.06), (0.001, 0.001, 0.001)   # no nose pad: a horse has a soft muzzle
    NOSTRIL_H = (0.034, -0.418, -0.048)       # the nostrils (left), on the muzzle's front corners
    EAR_BASE_H = (0.044, 0.000, 0.052)
    EAR_DIR = (0.22, 0.10, 0.97)              # upright, a little out
    EAR_LEN = 0.16
    EAR_PROFILE = ((0.0, 0.032, 0.024), (0.35, 0.042, 0.028), (0.70, 0.032, 0.022), (0.92, 0.012, 0.010))
    EAR_FRONT = (0.25, -1.0, 0.0)
    TRUNK_ROWS = [(-0.66, 0.90, 0.140, 0.160, 0.170), (-0.52, 0.92, 0.200, 0.250, 0.280),   # breast, girth: deep
                  (-0.35, 0.93, 0.225, 0.255, 0.290), (-0.12, 0.93, 0.245, 0.240, 0.285),   # a round barrel
                  (0.10, 0.94, 0.245, 0.230, 0.260), (0.28, 0.96, 0.230, 0.220, 0.205),     # the flank tucks up
                  (0.42, 0.97, 0.235, 0.220, 0.200), (0.56, 0.95, 0.200, 0.205, 0.220),     # croup and buttocks
                  (0.66, 0.92, 0.120, 0.140, 0.150)]
    NECK = [(0, -0.45, 0.98, 0.170, 0.220, 0.280), (0, -0.60, 1.10, 0.150, 0.180, 0.220),   # deep at the base,
            (0, -0.72, 1.22, 0.135, 0.165, 0.165), (0, -0.82, 1.33, 0.108, 0.130, 0.115),   # a thick crest,
            (0, -0.89, 1.42, 0.085, 0.095, 0.085)]                                          # a fine throatlatch
    NECK_BONES = [(0, -0.50, 1.060), (0, -0.65, 1.180), (0, -0.78, 1.310)]
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
    HEAD_PROFILE = [(0.03, 0.055, -0.120, 0.068), (-0.05, 0.052, -0.162, 0.090), (-0.13, 0.040, -0.152, 0.080),
                    (-0.22, 0.022, -0.124, 0.062), (-0.31, 0.004, -0.110, 0.054), (-0.38, -0.010, -0.112, 0.056),
                    (-0.43, -0.020, -0.116, 0.052)]
    HEAD_ROWS = [(y, (t + b) / 2, w, (t - b) / 2, (t - b) / 2) for y, t, b, w in HEAD_PROFILE]
    HEAD_SHAPE = 0.85
    HEAD_CAP = 0.45
    HEAD_BLOBS = [((0, -0.060, 0.004), (0.086, 0.095, 0.052), False),            # the cranium, a flat forehead
                  ((0, 0.000, -0.098), (0.044, 0.060, 0.048), False),            # the throatlatch, narrow
                  ((0.068, -0.118, 0.022), (0.018, 0.034, 0.012), True),         # the brow over the eye, soft
                  ((0.064, -0.070, -0.092), (0.034, 0.085, 0.072), True),        # the cheek: a big flat round plate
                  ((0.066, -0.175, -0.050), (0.020, 0.080, 0.026), True),        # the facial crest under the eye
                  ((0.040, -0.405, -0.042), (0.024, 0.036, 0.030), True),        # the nostril's rim
                  ((0.028, -0.418, -0.094), (0.032, 0.040, 0.028), True),        # the rounded upper lip
                  ((0.040, -0.200, -0.132), (0.040, 0.120, 0.036), True)]        # the jawline: skin over the jaw's back
    HINGE_H = (0.0, -0.07, -0.112)
    JAW_H = [(0, -0.10, -0.146, 0.046, 0.030, 0.038), (0, -0.21, -0.134, 0.044, 0.028, 0.030),
             (0, -0.31, -0.124, 0.042, 0.026, 0.026), (0, -0.40, -0.124, 0.036, 0.026, 0.030)]   # rising, a round chin

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
    GRAZE = ((-58, -12, -10), 80, 0.08, 0.0)  # the neck reaches forward and down from its base, nearly straight
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
        lips = smoothstep(-0.098, -0.108, hz) * smoothstep(-0.36, -0.40, hy)
        fcol = _mix(fcol, C['muzzle'] * 0.6, 0.6 * lips)
        fcol = _mix(fcol, self._hair_col(ctx, (0.0, -0.3, -1.0)), ctx['mane'])      # the mane up to the poll
        return _mix(fcol, self._hair_col(ctx, (0.0, -1.0, -0.3)), self.forelock_mask(ctx))

SP = Horse()
