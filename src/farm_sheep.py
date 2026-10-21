"""Sheep (farm animal, 2026-10-20): the red deer's body (farm_body.Hoofed) under a fleece, a 0.67 m ewe.

A medieval village ewe, unimproved and hornless: 0.67 m at the withers in full fleece, the fleece one fused volume
over the trunk, the neck, the tops of the legs and a cap on the poll, sculpted into lumps (staples) and painted with
curls; a bare face with a slightly Roman nose, ears held out to the sides under the cap, thin bare legs below the knees
and hocks, a long woolly tail (undocked). Horizontal bar pupils. Coats: 'white' (cream fleece, pale face and legs),
'black' (dark brown fleece), 'grey' (grey fleece, a dark face and legs).
"""
import numpy as np
from beast_common import smoothstep, vnoise
from beast_body import _gauss
import farm_body
from farm_paint import _mix

WOOL = 0.075                        # the fleece's thickness over the deer's trunk (D)


class Sheep(farm_body.Hoofed):
    NAME, PREFIX = "Sheep", "SHP"
    KX, KY, KL, KB = 0.70, 0.60, 0.48, 0.62
    KH = (1.05, 0.86, 1.05)
    VOXEL, BODY_TRIS = 0.006, 3000

    TAIL = [(0, 0.740, 1.000), (0, 0.820, 0.840), (0, 0.840, 0.640)]
    TAIL_R = ((0.070, 0.060, 0.060), (0.060, 0.052, 0.052), (0.046, 0.040, 0.040))
    POLL = (0.0, -0.92, 1.36)
    HEAD_PITCH = 50.0
    EYE_R = 0.028
    EYE_N_H = (0.82, -0.36, 0.25)
    EYE_AXIS = (0.0, 1.0, 0.15)
    EAR_BASE_H = (0.072, -0.010, 0.020)
    EAR_DIR = (0.95, -0.05, -0.28)           # out to the side and a little down
    EAR_LEN = 0.17
    EAR_PROFILE = ((0.0, 0.024, 0.018), (0.30, 0.040, 0.024), (0.65, 0.036, 0.020), (0.90, 0.018, 0.012))
    EAR_FRONT = (0.0, -0.55, -0.85)
    TRUNK_ROWS = [(y, z, a + WOOL, b + WOOL, c + WOOL * 0.8) for y, z, a, b, c in farm_body.Hoofed.TRUNK_ROWS]
    TRUNK_ROWS[0] = (-0.66, 0.95, 0.180, 0.200, 0.240)
    TRUNK_ROWS[-1] = (0.72, 0.93, 0.150, 0.170, 0.180)
    NECK = [(0, -0.42, 0.98, 0.230, 0.240, 0.290), (0, -0.57, 1.06, 0.210, 0.215, 0.255),
            (0, -0.70, 1.15, 0.185, 0.180, 0.210), (0, -0.80, 1.24, 0.150, 0.145, 0.160),
            (0, -0.87, 1.31, 0.110, 0.105, 0.115)]
    NECK_BONES = [(0, -0.52, 1.040), (0, -0.65, 1.130), (0, -0.76, 1.220)]
    # the fleece down to mid forearm and gaskin: the stumps' tops fat with wool, their ends bare (the graft)
    FRONT_STUMP = [(0.150, -0.42, 0.80, 0.110, 0.115, 0.115), (0.150, -0.41, 0.69, 0.100, 0.105, 0.108),
                   (0.147, -0.43, 0.60, 0.050, 0.058, 0.052), (0.146, -0.434, 0.52, 0.041, 0.048, 0.042)]
    HIND_STUMP = [(0.138, 0.38, 0.86, 0.120, 0.125, 0.135), (0.145, 0.38, 0.73, 0.105, 0.110, 0.125),
                  (0.140, 0.41, 0.64, 0.052, 0.060, 0.080), (0.137, 0.44, 0.565, 0.043, 0.049, 0.066)]
    GRAFT_NEAR = 0.10
    MANE = 0.0
    TAIL_HANGS, TAIL_SWING = True, 0.6
    LEG_T = 1.0
    LEG_T_LOW = 1.05
    HOOF_K = 1.25
    BELLY_CUT = 0.76
    COAT_ON_TRUNK = (0.62, 0.80, 0.25)        # the fleece over the leg tops rides on the spine
    SIDE_REST = 0.23
    GRAZE = ((-40, -36, -26), 70, 0.08, 0.0)

    HEAD_ROWS = [(0.03, -0.050, 0.070, 0.066, 0.090), (-0.05, -0.040, 0.084, 0.086, 0.108),
                 (-0.13, -0.040, 0.078, 0.080, 0.106), (-0.22, -0.050, 0.064, 0.066, 0.092),   # the Roman nose: the
                 (-0.31, -0.066, 0.052, 0.054, 0.078), (-0.38, -0.080, 0.046, 0.046, 0.066),   # top line bulges, the
                 (-0.42, -0.088, 0.042, 0.040, 0.058)]                                         # lip line the deer's

    COATS = {
        'white': dict(back='#d9cfb8', flank='#ddd3bd', light='#ece5d4', belly='#c8bca4', tail='#d6ccb4',
                      legs='#cfc3ae', edge='#7a6e60', face='#d8ccb8', muzzle='#c2ae9c', chin='#d8ccb8',
                      iris='#b89a5a', wool_dark='#9c8f78', nose='#7e625c', hoof='#4e463e', hoof_light='#8a7e70',
                      lip='#6e5650'),
        'black': dict(back='#2c2420', flank='#30271f', light='#4a3c32', belly='#261f1a', tail='#2a221d',
                      legs='#231c18', edge='#120e0b', face='#2a221c', muzzle='#1e1814', chin='#2a221c',
                      iris='#b89a5a', wool_dark='#140f0c'),
        'grey': dict(back='#8a8378', flank='#918a7e', light='#aaa396', belly='#7a7368', tail='#857e72',
                     legs='#2a2420', edge='#15110e', face='#2c2622', muzzle='#1e1916', chin='#3a332c',
                     iris='#b89a5a', wool_dark='#5a544a', ear_in='#3a322c'),
    }
    MISC = dict(ear_in='#b8a08c', mouth='#2e2420')
    JAW_H = [(x, y, z + dz, a, b, c) for (x, y, z, a, b, c), dz in zip(farm_body.Hoofed.JAW_H, (0, 0.004, 0.008, 0.010))]
    COAT_STYLE = 'wool'
    EAR_RIM = 0.25

    # ------------------------------------------------------------------ the fleece
    def extra_head_parts(self, bm):
        from beast_body import ellipsoid
        ellipsoid(bm, (0, -0.02, 0.040), (0.105, 0.110, 0.085))        # the wool cap on the poll

    def wool_mask(self, P):
        """1 on the fleece (D): the trunk, the neck, the tops of the legs, the tail and a cap on the poll."""
        H = self.hx_inv(P)
        inhead = smoothstep(0.10, 0.02, H[..., 1]) * smoothstep(-0.32, -0.26, H[..., 2])
        cap = inhead * smoothstep(0.035, 0.075, H[..., 2]) * smoothstep(-0.20, -0.12, H[..., 1])
        legs = smoothstep(0.585, 0.640, P[..., 2])
        return np.clip(legs * (1 - inhead) + cap, 0, 1)

    def fur_amount(self, P, N):
        A = np.full(len(P), 0.0015)
        return A * (1 - 0.75 * self.face_mask(P))

    def sculpt_fur(self, co, no, seed=23):
        """Short hair on the face and legs; on the fleece, lumps (the staples), bigger on the back and flanks."""
        out = super().sculpt_fur(co, no, seed)
        w = self.wool_mask(co)
        lumps = vnoise(co * 22.0, seed=61) * 0.65 + vnoise(co * 47.0, seed=62) * 0.35
        d = 0.024 * w * smoothstep(-0.25, 0.65, lumps)
        return out + no * d[:, None]

    def coat_pattern(self, ctx, col):
        C, P = ctx['C'], ctx['P']
        w = self.wool_mask(P) * (ctx['furp'] | ctx['hair'])
        curl = vnoise(P * 70.0, seed=96) * 0.6 + vnoise(P * 150.0, seed=97) * 0.4
        lumps = vnoise(P * 22.0, seed=61) * 0.65 + vnoise(P * 47.0, seed=62) * 0.35
        wc = _mix(np.tile(C['back'], (ctx['n'], 1)), C['light'], 0.15 * smoothstep(0.3, 0.9, curl))
        wc = _mix(wc, C['wool_dark'], 0.35 * smoothstep(0.10, -0.40, lumps))          # the gaps between staples
        wc = _mix(wc, C['belly'], 0.5 * ctx['belly'])
        ctx['wool'], ctx['wool_col'] = w, wc
        return _mix(col, wc, w)

    def face_pattern(self, ctx, fcol):
        return _mix(fcol, ctx['wool_col'], ctx['wool'])        # the cap and the neck stay fleece


SP = Sheep()
