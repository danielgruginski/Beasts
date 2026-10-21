"""Horse (farm animal, 2026-10-20): the red deer's body (farm_body.Hoofed) made into a medieval rouncey, 1.45 m.

An everyday riding and draught horse of the time: 1.45 m at the withers (about 14 hands), a deep chest and round
barrel, prominent withers, a long neck carried up with a crest, a mane lying on its right side and a forelock, a long
head with wide jowls and a tapering face, small upright pointed ears, big eyes, long legs on solid hooves (no
dewclaws), a long hair tail from a short dock. Oval pupils. Coats: 'bay' (red-brown, black mane, tail and lower legs),
'chestnut' (red, a blaze and white hind socks), 'grey' (dapple grey, dark legs), 'black'.
"""
import numpy as np
from mathutils import Vector
from beast_common import loft, smoothstep, vnoise, fbm
from beast_body import PART
import farm_body
from farm_paint import _mix, _streaks


class Horse(farm_body.Hoofed):
    NAME, PREFIX = "Horse", "HRS"
    KX, KY, KL, KB = 1.20, 1.18, 1.19, 1.37
    KH = (0.92, 1.05, 1.0)
    HEAD_CAP = 0.35
    VOXEL, BODY_TRIS = 0.006, 3000
    CREASE_DEG = 40

    TAIL = [(0, 0.700, 1.040), (0, 0.800, 0.920), (0, 0.860, 0.700), (0, 0.880, 0.480)]
    TAIL_R = None
    TAIL_TUBE = [(0, 0.660, 1.050, 0.040, 0.040, 0.040), (0, 0.720, 1.040, 0.046, 0.044, 0.044),
                 (0, 0.800, 0.930, 0.060, 0.050, 0.050), (0, 0.855, 0.720, 0.080, 0.062, 0.062),
                 (0, 0.875, 0.520, 0.070, 0.052, 0.052), (0, 0.880, 0.420, 0.030, 0.024, 0.024)]
    POLL = (0.0, -0.93, 1.47)
    HEAD_PITCH = 52.0
    HEAD_LEN = 0.45
    EYE0_H = (0.084, -0.115, -0.006)
    EYE_N_H = (0.86, -0.30, 0.30)
    EYE_R = 0.030
    EYE_AXIS = (0.0, 1.0, 0.20)
    NOSE_C, NOSE_R = (0.0, -0.452, -0.092), (0.058, 0.030, 0.050)
    EAR_BASE_H = (0.045, -0.002, 0.052)
    EAR_DIR = (0.25, 0.08, 0.96)              # upright, a little out
    EAR_LEN = 0.14
    EAR_PROFILE = ((0.0, 0.028, 0.020), (0.35, 0.036, 0.024), (0.70, 0.026, 0.018), (0.92, 0.010, 0.008))
    EAR_FRONT = (0.25, -1.0, 0.0)
    TRUNK_ROWS = [(-0.62, 0.96, 0.120, 0.160, 0.200), (-0.50, 0.97, 0.180, 0.225, 0.315),
                  (-0.32, 0.96, 0.210, 0.215, 0.330), (-0.10, 0.95, 0.230, 0.200, 0.320),
                  (0.10, 0.95, 0.225, 0.195, 0.290), (0.26, 0.96, 0.205, 0.190, 0.235),
                  (0.42, 0.97, 0.205, 0.190, 0.205), (0.57, 0.96, 0.180, 0.175, 0.190),
                  (0.68, 0.94, 0.110, 0.130, 0.140)]
    NECK = [(0, -0.42, 1.00, 0.150, 0.190, 0.230), (0, -0.57, 1.10, 0.130, 0.165, 0.190),
            (0, -0.70, 1.22, 0.110, 0.140, 0.150), (0, -0.80, 1.33, 0.090, 0.110, 0.110),
            (0, -0.87, 1.42, 0.076, 0.085, 0.085)]
    HEAD_ROWS = [(0.03, -0.050, 0.072, 0.064, 0.100), (-0.05, -0.045, 0.086, 0.082, 0.115),    # wide jowls and
                 (-0.13, -0.050, 0.080, 0.072, 0.096), (-0.22, -0.058, 0.072, 0.062, 0.086),   # forehead, the face
                 (-0.31, -0.065, 0.066, 0.055, 0.080), (-0.38, -0.070, 0.063, 0.052, 0.077),   # a wedge tapering
                 (-0.43, -0.074, 0.060, 0.050, 0.072)]                                         # evenly to the muzzle
    HEAD_SHAPE = 0.85
    HEAD_BLOBS = [((0, -0.05, 0.010), (0.082, 0.090, 0.070), False),             # the cranium
                  ('nose', None, False),
                  ((0, -0.03, -0.125), (0.056, 0.080, 0.066), False),            # throat latch
                  ((0.066, -0.122, 0.012), (0.020, 0.034, 0.013), True),         # brow
                  ((0.066, -0.175, -0.060), (0.022, 0.085, 0.030), True),        # the facial crest under the eye
                  ((0.062, -0.090, -0.100), (0.050, 0.090, 0.070), True),        # the jowl (the big cheek)
                  ((0.044, -0.220, -0.128), (0.036, 0.080, 0.040), True),        # ... to the mouth's corner
                  ((0.030, -0.412, -0.146), (0.030, 0.042, 0.026), True),        # the upper lip
                  ((0.040, -0.240, -0.158), (0.040, 0.130, 0.044), True)]        # the jawline: skin over the jaw's back
    JAW_H = [(0, -0.10, -0.150, 0.048, 0.032, 0.040), (0, -0.21, -0.158, 0.048, 0.030, 0.034),
             (0, -0.31, -0.162, 0.050, 0.028, 0.032), (0, -0.38, -0.158, 0.044, 0.024, 0.026)]   # the chin tucked in
    MANE = 0.0
    TAIL_HANGS, TAIL_SWING = True, 0.45
    FUR_BASE = 0.0015
    LEG_T = 1.20
    LEG_T_LOW = 1.15
    HOOF, HOOF_K, DEWCLAWS = 'solid', 1.55, False
    PUPIL = 'oval'
    EAR_RIM = 0.4
    GRAZE = ((-46, -42, -32), 72, 0.08, 0.0)

    def mane_rows(self):
        """The mane: a blade from the poll to the withers, rooted along the crest and leaning out over the right side
        of the neck (D): (x, y, z, thickness, above, hanging)."""
        top = [tuple(p) for p in self.crest_line(8, 0.96)] + [(0.0, -0.36, 1.17)]
        n = len(top)
        rows = []
        for i, (x, y, z) in enumerate(top):
            t = i / (n - 1)
            hang = 0.05 + 0.10 * np.sin(np.pi * min(1.0, t * 1.15)) ** 0.7
            rows.append((-0.026, y, z - 0.010, 0.028, 0.048, hang + 0.02))
        return rows

    FORELOCK_H = [(0, -0.005, 0.070, 0.032, 0.008, 0.010), (0, -0.065, 0.050, 0.036, 0.008, 0.010),
                  (0, -0.120, 0.030, 0.030, 0.007, 0.009), (0, -0.165, 0.016, 0.012, 0.005, 0.005)]   # flat on the
                                                                                                 # forehead

    def extra_pieces(self, bm, bvh, tags):
        hair = loft(bm, self.mane_rows(), up=(-0.5, 0.0, 0.87), seg=8, per_seg=2, cap0=0.5, cap1=0.5, capk=2)
        before = set(bm.verts)
        loft(bm, self.FORELOCK_H, up=(0, 0, 1), seg=8, per_seg=2, cap0=0.3, cap1=0.3, capk=2)
        new = [v for v in bm.verts if v not in before]
        for v in new:
            v.co = Vector(self.hx(v.co[:]))
        tags['hair'] = hair + new

    def skin_extra(self, body, rig, part):
        import farm_rig
        farm_rig.copy_nearest_skin(body, np.nonzero(part == PART['hair'])[0])

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
        return fcol

    def paint_pieces(self, ctx, col, smooth):
        part, P, C = ctx['part'], ctx['P'], ctx['C']
        hair = part == PART['hair']
        if hair.any():
            st = _streaks(P, np.tile((-0.3, 0.2, -1.0), (len(P), 1)), 82, across=0.005, length=0.10, steps=9)
            hc = np.tile(C['mane'], (len(P), 1)) * (0.70 + 0.50 * st)[:, None]
            col = np.where(hair[:, None], hc, col)
            smooth = np.where(hair, 0.22, smooth)
        return col, smooth


SP = Horse()
