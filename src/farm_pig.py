"""Pig (farm animal, 2026-10-20): the red deer's body (farm_body.Hoofed) made into a medieval village pig, 0.7 m.

A pig of the time, half wild in look: 0.7 m at the withers, about 1.3 m snout to rump, a front-heavy barrel with a
straight back and a sloping rump, a short thick neck running into a long tapering head with a flat snout disc, small
eyes, pricked ears tipped forward, a crest of bristles from the poll along the back, a thin tail with a curl, short
legs on small cloven hooves with big dewclaws. Round pupils, a skin-and-bristle coat. Coats: 'pink' (pale with a few
dark spots), 'saddleback' (black with a white belt over the shoulders), 'black', 'brown' (wild-type, grizzled).
"""
import numpy as np
from mathutils import Vector
from beast_common import loft, smoothstep, vnoise
from beast_body import PART
import farm_body
from farm_paint import _mix, _streaks, patches


class Pig(farm_body.Hoofed):
    NAME, PREFIX = "Pig", "PIG"
    KX, KY, KL, KB = 0.85, 0.78, 0.48, 0.81
    KH = (1.0, 0.85, 1.0)
    VOXEL, BODY_TRIS = 0.006, 2800
    CREASE_DEG = 40

    TAIL = [(0, 0.700, 0.920), (0, 0.765, 0.875), (0, 0.775, 0.775)]
    TAIL_R = None
    TAIL_TUBE = [(0, 0.650, 0.930, 0.026, 0.026, 0.026), (0, 0.710, 0.920, 0.022, 0.022, 0.022),
                 (0, 0.758, 0.888, 0.019, 0.019, 0.019), (0, 0.790, 0.840, 0.017, 0.017, 0.017),
                 (0, 0.772, 0.800, 0.015, 0.015, 0.015), (0, 0.748, 0.818, 0.013, 0.013, 0.013),
                 (0, 0.752, 0.772, 0.010, 0.010, 0.010)]                  # a curl at the end
    POLL = (0.0, -0.84, 1.09)
    HEAD_PITCH = 26.0
    HEAD_LEN = 0.35
    HINGE_H = (0.0, -0.07, -0.110)
    EYE0_H = (0.070, -0.120, 0.030)
    EYE_N_H = (0.80, -0.45, 0.40)
    EYE_R = 0.021
    NOSE_C, NOSE_R = (0.0, -0.346, -0.058), (0.056, 0.014, 0.050)          # the snout's flat disc
    EAR_BASE_H = (0.055, -0.030, 0.075)
    EAR_DIR = (0.35, -0.45, 0.82)             # pricked, tipped forward
    EAR_LEN = 0.15
    EAR_PROFILE = ((0.0, 0.036, 0.020), (0.35, 0.046, 0.024), (0.70, 0.030, 0.016), (0.92, 0.010, 0.006))
    EAR_FRONT = (0.30, -1.0, 0.35)
    TRUNK_ROWS = [(-0.66, 0.95, 0.150, 0.170, 0.210), (-0.52, 0.96, 0.210, 0.210, 0.300),
                  (-0.32, 0.97, 0.230, 0.220, 0.315), (-0.10, 0.97, 0.230, 0.210, 0.310),
                  (0.10, 0.96, 0.220, 0.200, 0.300), (0.28, 0.95, 0.200, 0.190, 0.260),
                  (0.44, 0.93, 0.180, 0.180, 0.220), (0.58, 0.90, 0.150, 0.160, 0.180),
                  (0.68, 0.87, 0.090, 0.110, 0.120)]
    NECK = [(0, -0.45, 0.96, 0.200, 0.200, 0.270), (0, -0.58, 0.99, 0.180, 0.180, 0.240),
            (0, -0.70, 1.03, 0.150, 0.150, 0.190), (0, -0.78, 1.06, 0.120, 0.120, 0.150),
            (0, -0.83, 1.08, 0.100, 0.100, 0.120)]
    NECK_BONES = [(0, -0.52, 1.000), (0, -0.64, 1.030), (0, -0.74, 1.060)]
    TRUNK_BLOBS = [((0, -0.40, 1.12), (0.090, 0.22, 0.080), 0, False),          # the withers, high (front-heavy)
                   ((0.150, -0.47, 0.90), (0.075, 0.150, 0.230), -36, True),    # shoulder blade
                   ((0.150, -0.45, 0.76), (0.070, 0.110, 0.110), 0, True),      # upper arm
                   ((0.135, 0.44, 0.84), (0.080, 0.180, 0.220), 0, True)]       # the ham
    HEAD_ROWS = [(0.03, -0.040, 0.095, 0.085, 0.115), (-0.06, -0.040, 0.100, 0.090, 0.115),
                 (-0.14, -0.050, 0.078, 0.066, 0.088), (-0.22, -0.058, 0.062, 0.054, 0.068),
                 (-0.29, -0.060, 0.056, 0.050, 0.058), (-0.33, -0.060, 0.056, 0.050, 0.056)]   # a short snout
    HEAD_SHAPE = 0.95
    HEAD_BLOBS = [((0, -0.04, 0.020), (0.085, 0.090, 0.070), False),             # the cranium
                  ('nose', None, False),
                  ((0, -0.02, -0.110), (0.080, 0.080, 0.070), False),            # the jowls, heavy
                  ((0.062, -0.110, 0.040), (0.018, 0.030, 0.012), True),         # brow
                  ((0.065, -0.080, -0.080), (0.045, 0.080, 0.060), True),        # cheek
                  ((0.042, -0.160, -0.098), (0.034, 0.060, 0.032), True),
                  ((0.040, -0.150, -0.128), (0.036, 0.075, 0.030), True)]        # the jawline: skin over the jaw's back        # ... to the mouth's corner
    JAW_H = [(0, -0.10, -0.135, 0.050, 0.030, 0.040), (0, -0.17, -0.124, 0.044, 0.026, 0.032),
             (0, -0.24, -0.114, 0.036, 0.020, 0.024), (0, -0.29, -0.106, 0.028, 0.016, 0.018)]
    FACE_Y = (0.02, -0.47)
    MANE = 0.0
    FUR_BASE = 0.0015
    LEG_T = 1.35
    LEG_T_LOW = 1.10
    HOOF_K = 1.3
    PUPIL = 'round'
    COAT_STYLE = 'bristle'
    EAR_RIM = 0.3

    CADENCE = 0.95
    RUN = (3.0, 0.5)
    RUN_NECK = ((-6, -4, 0), 10)
    GRAZE = ((-26, -22, -14), 18, 0.06, 0.0)  # rooting: the snout down in the soil
    GRAZE_PITCH = -6
    UP_HIGH = ((10, 4, 0), 4)
    CALL_HEAD, CALL_JAW = 12, 14
    LIE_NECK = ((-6, -4, -2), 6)
    DEATH_HEAD_ROLL = 25

    def crest_rows(self, bvh):
        """The bristle crest: a low blade from the poll along the neck and the back to mid-trunk (D), seated on the
        body by rays cast down onto it (crest_line plus trunk heights left it floating over the withers)."""
        poll = self.crest_line(2)[0]
        ys = np.linspace(poll[1] + 0.02, 0.05, 9)
        pts = []
        for y in ys:
            hit = bvh.ray_cast(Vector((0.0, float(y), 2.5)), Vector((0, 0, -1)), 5.0)[0]
            if hit is not None:
                pts.append((0.0, float(y), hit.z))
        n = len(pts)
        return [(0.0, y, z - 0.010, 0.016, 0.030 * np.sin(np.pi * (0.15 + 0.85 * i / (n - 1))) + 0.008, 0.012)
                for i, (x, y, z) in enumerate(pts)]

    def extra_pieces(self, bm, bvh, tags):
        tags['hair'] = loft(bm, self.crest_rows(bvh), up=(0, 0, 1), seg=6, per_seg=2, cap0=0.4, cap1=0.4, capk=2)

    def skin_extra(self, body, rig, part):
        import farm_rig
        farm_rig.copy_nearest_skin(body, np.nonzero(part == PART['hair'])[0])

    COATS = {
        'pink': dict(back='#c89a8a', flank='#d2a696', light='#e2bcae', belly='#d8aa9c', tail='#c89a8a',
                     legs='#c08e7e', edge='#6a4a40', face='#cc9e8e', muzzle='#c08a7c', chin='#d8aea0',
                     iris='#3a2a1e', spot='#3e3430', crest='#b08a7a', nose='#c07a70', hoof='#5a4a40',
                     hoof_light='#8a7a6e', ear_in='#d89a8e', lip='#9a6a60'),
        'saddleback': dict(back='#24201e', flank='#2a2522', light='#3e3632', belly='#2a2522', tail='#24201e',
                           legs='#2a2522', edge='#0e0c0b', face='#26221f', muzzle='#24201e', chin='#2e2925',
                           iris='#3a2a1e', belt='#d8c8bc', crest='#1a1716'),
        'black': dict(back='#22201e', flank='#282422', light='#3a3430', belly='#2a2624', tail='#22201e',
                      legs='#24201e', edge='#0e0c0b', face='#24201e', muzzle='#201c1a', chin='#2c2724',
                      iris='#3a2a1e', crest='#141211'),
        'brown': dict(back='#4a3a2e', flank='#5a4636', light='#7a6450', belly='#4e3e32', tail='#3e3026',
                      legs='#2e241c', edge='#1a140f', face='#4e3c30', muzzle='#3a2c22', chin='#5a4a3c',
                      iris='#3a2a1e', crest='#2a2018', grizzle='#9a8a74'),
    }
    MISC = dict(nose='#3a2a26', ear_in='#5a443a', lip='#3a2e2a')

    def coat_pattern(self, ctx, col):
        C, P, x, y, z = ctx['C'], ctx['P'], ctx['x'], ctx['y'], ctx['z']
        fur = ctx['furp'] | ctx['legp']
        if 'spot' in C:
            col = _mix(col, C['spot'], 0.85 * patches(P, 61, 3.2, 0.42) * fur)
        if 'belt' in C:                       # the white belt over the shoulders and down the forelegs
            belt = smoothstep(-0.20, -0.30, y) * smoothstep(-0.66, -0.56, y + 0.10 * ctx['n_mid'])
            belt = np.maximum(belt, smoothstep(-0.25, -0.33, y) * smoothstep(0.75, 0.6, z) * (y < -0.30))
            col = _mix(col, C['belt'], belt * fur)
        if 'grizzle' in C:                    # pale bristle tips through the coat
            col = _mix(col, C['grizzle'], 0.35 * smoothstep(0.30, 0.65, ctx['s1']) * fur)
        tp = ctx['part'] == PART['tail']
        col = np.where(tp[:, None], _mix(col, C['tail'], 0.6), col)
        return col

    def paint_pieces(self, ctx, col, smooth):
        part, P, C = ctx['part'], ctx['P'], ctx['C']
        hair = part == PART['hair']
        if hair.any():
            st = _streaks(P, np.tile((0.0, 0.6, 0.8), (len(P), 1)), 83, across=0.004, length=0.06, steps=7)
            hc = np.tile(C['crest'], (len(P), 1)) * (0.70 + 0.50 * st)[:, None]
            col = np.where(hair[:, None], hc, col)
        return col, smooth


SP = Pig()
