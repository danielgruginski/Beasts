"""Cow (farm animal, 2026-10-20): the red deer's body (farm_body.Hoofed) made into a small medieval cow, 1.1 m.

A village cow of the time, small and hardy: 1.1 m at the withers, about 2.0 m nose to tail head, a deep wide barrel,
a straight back with the hook and pin bones showing, a thick neck carried level with a dewlap under it, a big boxy
head hung low with a broad wet muzzle, short horns curving out and up, ears held out under them, an udder, sturdy
legs on broad cloven hooves, a tail set high and hanging to the hocks with a switch of long hair. Oval pupils.
Coats: 'brown' (dark brown, a pale ring round the muzzle), 'red' (red-brown), 'pied' (black patches on white).
"""
import numpy as np
from beast_common import loft, smoothstep
from beast_body import PART, ellipsoid, _gauss
import farm_body
from farm_paint import _mix, _streaks, patches, horns

UDDER = ((0, 0.29, 0.665), (0.080, 0.100, 0.075))         # (D) centre, radii: a separate shell (fused, the leg
                                                          # graft's stump cut ate into it)


class Cow(farm_body.Hoofed):
    NAME, PREFIX = "Cow", "COW"
    KX, KY, KL, KB = 1.30, 1.15, 0.80, 1.25
    KH = (1.0, 0.97, 1.0)
    VOXEL, BODY_TRIS = 0.006, 3200
    CREASE_DEG = 35                           # a shallow decimation crease across the back opened into a crack

    TAIL = [(0, 0.805, 1.060), (0, 0.865, 0.820), (0, 0.875, 0.560)]       # set high, behind the pin bones
    TAIL_R = None                                                          # the tail is a clean tube:
    TAIL_TUBE = [(0, 0.745, 1.075, 0.050, 0.044, 0.044), (0, 0.805, 1.060, 0.046, 0.040, 0.040),
                 (0, 0.850, 0.900, 0.034, 0.030, 0.030), (0, 0.868, 0.720, 0.028, 0.026, 0.026),
                 (0, 0.875, 0.580, 0.024, 0.022, 0.022)]
    POLL = (0.0, -0.88, 1.15)
    HEAD_PITCH = 56.0
    HEAD_LEN = 0.44
    HEAD_SHAPE = 0.8
    EYE0_H = (0.088, -0.130, -0.004)
    EYE_N_H = (0.86, -0.32, 0.25)
    EYE_R = 0.027
    EYE_AXIS = (0.0, 1.0, 0.10)
    NOSE_C, NOSE_R = (0.0, -0.442, -0.072), (0.066, 0.024, 0.050)
    EAR_BASE_H = (0.080, -0.030, 0.008)
    EAR_DIR = (0.95, 0.05, -0.15)
    EAR_LEN = 0.20
    EAR_PROFILE = ((0.0, 0.030, 0.022), (0.30, 0.054, 0.030), (0.65, 0.050, 0.026), (0.90, 0.026, 0.016))
    EAR_FRONT = (0.0, -0.90, -0.30)
    TRUNK_ROWS = [(-0.64, 0.95, 0.140, 0.165, 0.200), (-0.50, 0.96, 0.195, 0.190, 0.320),
                  (-0.32, 0.96, 0.220, 0.185, 0.335), (-0.10, 0.95, 0.240, 0.190, 0.345),
                  (0.10, 0.95, 0.245, 0.190, 0.330), (0.28, 0.96, 0.232, 0.180, 0.280),
                  (0.44, 0.98, 0.226, 0.160, 0.235), (0.60, 0.98, 0.190, 0.150, 0.205),
                  (0.72, 0.96, 0.120, 0.120, 0.150)]
    NECK = [(0, -0.40, 0.97, 0.200, 0.200, 0.270), (0, -0.55, 1.00, 0.180, 0.170, 0.260),
            (0, -0.68, 1.05, 0.150, 0.140, 0.215), (0, -0.78, 1.09, 0.122, 0.112, 0.165),
            (0, -0.85, 1.12, 0.100, 0.090, 0.120)]
    NECK_BONES = [(0, -0.52, 1.030), (0, -0.64, 1.060), (0, -0.75, 1.090)]
    TRUNK_BLOBS = [((0, -0.56, 0.78), (0.130, 0.11, 0.15), 0, False),            # the brisket
                   ((0.150, -0.47, 0.90), (0.070, 0.150, 0.230), -36, True),     # shoulder blade
                   ((0.150, -0.45, 0.76), (0.068, 0.110, 0.110), 0, True),       # upper arm
                   ((0.150, 0.46, 0.86), (0.085, 0.190, 0.240), 0, True),        # the haunch
                   ((0.190, 0.40, 1.075), (0.050, 0.060, 0.045), 0, True),       # the hook bone
                   ((0.085, 0.68, 1.050), (0.040, 0.045, 0.040), 0, True),       # the pin bone
                   ((0, -0.66, 0.84), (0.050, 0.140, 0.100), 0, False),          # the dewlap
                   ((0, -0.52, 0.74), (0.055, 0.110, 0.080), 0, False)]
    HEAD_ROWS = [(0.03, -0.050, 0.076, 0.070, 0.090), (-0.05, -0.045, 0.094, 0.088, 0.105),
                 (-0.13, -0.050, 0.086, 0.078, 0.100), (-0.22, -0.060, 0.073, 0.064, 0.088),
                 (-0.31, -0.070, 0.068, 0.056, 0.080), (-0.38, -0.076, 0.070, 0.054, 0.076),
                 (-0.43, -0.080, 0.066, 0.050, 0.070)]
    HEAD_BLOBS = [((0, -0.05, 0.010), (0.085, 0.090, 0.070), False),             # the cranium
                  ('nose', None, False),
                  ((0, -0.02, 0.048), (0.095, 0.050, 0.038), False),            # the poll ridge between the horns
                  ((0, -0.03, -0.125), (0.060, 0.080, 0.065), False),            # throat latch
                  ((0.068, -0.120, 0.018), (0.022, 0.034, 0.014), True),         # brow
                  ((0.062, -0.110, -0.105), (0.048, 0.085, 0.066), True),        # the big cheek (masseter)
                  ((0.054, -0.210, -0.128), (0.040, 0.080, 0.042), True),        # ... to the mouth's corner
                  ((0.036, -0.395, -0.132), (0.036, 0.048, 0.026), True)]        # the broad upper lip
    JAW_H = [(0, -0.10, -0.150, 0.054, 0.032, 0.042), (0, -0.21, -0.152, 0.056, 0.030, 0.034),
             (0, -0.31, -0.154, 0.056, 0.028, 0.030), (0, -0.40, -0.152, 0.052, 0.024, 0.024)]
    MANE = 0.0
    FUR_BASE = 0.0020
    LEG_T = 1.6
    LEG_T_LOW = 0.95
    HOOF_K = 1.7
    GRAFT_NEAR = 0.14
    HORN_BASE_H = (0.078, -0.020, 0.055)
    HORN = [(0.0, 0.0, -0.010, 0.030), (0.035, 0.000, 0.005, 0.029), (0.090, -0.010, 0.035, 0.022),
            (0.135, -0.030, 0.090, 0.015), (0.150, -0.055, 0.150, 0.006)]
    SWITCH = [(0, 0.875, 0.620, 0.030, 0.030, 0.030), (0, 0.878, 0.540, 0.046, 0.040, 0.040),
              (0, 0.880, 0.450, 0.034, 0.030, 0.030), (0, 0.880, 0.390, 0.006, 0.006, 0.006)]

    CADENCE = 1.15
    RUN = (3.0, 0.6)
    RUN_NECK = ((-12, -8, -2), 30)
    GRAZE = ((-34, -28, -18), 50, 0.08, 0.0)
    GRAZE_PITCH = -8
    UP_HIGH = ((14, 4, -2), -10)
    CALL_HEAD, CALL_JAW = 30, 22
    SIDE_REST = 0.34
    LIE_NECK = ((-8, -6, -2), 10)
    EAR_SWING = 0.7

    COATS = {
        'brown': dict(back='#4a3324', flank='#553b29', light='#6e5038', belly='#5a4230', tail='#3a281c',
                      legs='#3a2a1e', edge='#1e150f', face='#4a3324', muzzle='#3a2a1e', chin='#8a7462',
                      iris='#2a1a10', ring='#b8a48c', switch='#1e1610', udder='#a07a6a'),
        'red': dict(back='#7a3e22', flank='#86462a', light='#a05e3a', belly='#8a5236', tail='#6a3620',
                    legs='#6a3a24', edge='#2e1a10', face='#7e4226', muzzle='#6a3a24', chin='#a8825e',
                    iris='#2a1a10', ring='#c8a888', switch='#3a2014', udder='#c49080', nose='#5e3a32'),
        'pied': dict(back='#e2dccf', flank='#e8e2d6', light='#f3efe6', belly='#dcd4c4', tail='#e2dccf',
                     legs='#dcd4c4', edge='#3a322c', face='#e8e2d6', muzzle='#c8b8a8', chin='#e2dccf',
                     iris='#2a1a10', patch='#1e1a17', ring='#e8e2d6', switch='#e8e2d6', udder='#d8aca0',
                     nose='#6e5a54'),
    }
    MISC = dict(horn='#d6ccb4', horn_dark='#9a8e78', horn_tip='#2a241e', ear_in='#a08470')
    PUPIL = 'oval'

    def extra_pieces(self, bm, bvh, tags):
        from beast_common import cone
        tags['hair'] = loft(bm, self.SWITCH, up=(0, -1, 0), seg=8, per_seg=2, cap0=0.3, cap1=0.3, capk=2)
        before = set(bm.verts)
        c = np.array(UDDER[0])
        (cx, cy, cz), (rx, ry, rz) = UDDER                 # a clean loft: beast_body.ellipsoid's poles (made for the
        loft(bm, [(0, cy + ry * t, cz, rx * k, rz * k * 0.8, rz * k)   # voxel fuse) made the heat solve singular
                  for t, k in ((-0.95, 0.45), (-0.6, 0.85), (0.0, 1.0), (0.6, 0.85), (0.95, 0.45))],
             up=(0, 0, 1), seg=12, per_seg=2, cap0=0.6, cap1=0.6, capk=2)
        for sx in (1, -1):
            for sy in (1, -1):
                base = c + np.array((sx * 0.035, sy * 0.040, -0.055))
                cone(bm, tuple(base), tuple(base + np.array((0, 0, -0.045))), 0.012, seg=5)
        tags['whisker'] = [v for v in bm.verts if v not in before]          # (part id 'whisker': the udder)

    def skin_extra(self, body, rig, part):
        import beast_rig
        from beast_rig import set_rigid
        set_rigid(body, np.nonzero(part == PART['hair'])[0], "Tail2")      # the switch on the tail's end
        set_rigid(body, np.nonzero(part == PART['whisker'])[0], "Spine1")  # the udder on the trunk

    def udder_mask(self, P):
        return np.exp(-0.5 * (np.linalg.norm((P - UDDER[0]) / (np.array(UDDER[1]) * 1.05), axis=1) / 0.55) ** 4)

    # ------------------------------------------------------------------ paint
    def coat_pattern(self, ctx, col):
        C, P = ctx['C'], ctx['P']
        if 'patch' in C:
            pm = patches(P, 53, 1.8, 0.0) * ctx['furp']
            col = _mix(col, C['patch'], pm)
        ud = ctx['part'] == PART['whisker']
        col = _mix(col, C['udder'], 0.85 * np.maximum(self.udder_mask(P) * ctx['furp'], ud))
        return col

    def face_pattern(self, ctx, fcol):
        C = ctx['C']
        hy, hz, ax = ctx['hy'], ctx['hz'], np.abs(ctx['hx'])
        dn = np.linalg.norm((np.stack([ax, hy, hz], -1) - self.NOSE_C) / (np.array(self.NOSE_R) * 1.9), axis=1)
        fcol = _mix(fcol, C['ring'], 0.75 * smoothstep(1.25, 1.0, dn))              # the pale ring round the muzzle
        if 'patch' in C:
            fcol = _mix(fcol, C['patch'], patches(ctx['P'], 59, 2.6, 0.15))
        return fcol

    def paint_pieces(self, ctx, col, smooth):
        col, smooth = horns(self, ctx, col, smooth, ridges=0, root_dark=0.0, tip_from=0.55)
        part, P, C = ctx['part'], ctx['P'], ctx['C']
        sw = part == PART['hair']
        if sw.any():
            s3 = _streaks(P, np.tile((0.0, 0.0, -1.0), (len(P), 1)), 95, across=0.005, length=0.10, steps=9)
            bc = np.tile(C['switch'], (len(P), 1)) * (0.75 + 0.45 * s3)[:, None]
            col = np.where(sw[:, None], bc, col)
        return col, smooth


SP = Cow()
