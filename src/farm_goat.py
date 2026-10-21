"""Goat (farm animal, 2026-10-20): the red deer's body (farm_body.Hoofed) scaled to a 0.68 m nanny goat.

A medieval village goat: 0.68 m at the withers, about 1.0 m nose to rump, a deep barrel (the rumen), a straight back
and a sloping rump, sturdy legs on small cloven hooves, a slim neck carried up, a short head with a straight face,
horizontal ears, scimitar horns sweeping back over the neck, a beard on the chin, a short tail flicked up. Pupils
are horizontal bars. Coats: 'chamois' (bay with a black dorsal stripe, belly, legs and face stripes), 'white', 'pied'
(black patches on white).
"""
import numpy as np
from mathutils import Vector
from beast_common import loft, smoothstep
from beast_body import PART
import farm_body
from farm_paint import _mix, _streaks, patches, horns


class Goat(farm_body.Hoofed):
    NAME, PREFIX = "Goat", "GOT"
    KX, KY, KL, KB = 0.62, 0.62, 0.58, 0.60
    KH = (1.15, 0.86, 1.0)
    VOXEL, BODY_TRIS = 0.006, 2400

    TAIL = [(0, 0.690, 1.030), (0, 0.745, 1.075), (0, 0.775, 1.120)]
    TAIL_R = ((0.040, 0.026, 0.024), (0.034, 0.022, 0.020), (0.024, 0.016, 0.014))
    POLL = (0.0, -0.91, 1.42)
    HEAD_PITCH = 48.0
    EYE_R = 0.030
    EYE_N_H = (0.80, -0.40, 0.30)
    EYE_AXIS = (0.0, 1.0, 0.22)                # a level almond (the deer's slants up toward the poll)
    EAR_BASE_H = (0.058, -0.012, 0.030)
    EAR_DIR = (0.92, -0.12, -0.10)            # out to the side, a little forward and down
    EAR_LEN = 0.20
    EAR_PROFILE = ((0.0, 0.026, 0.020), (0.30, 0.042, 0.026), (0.65, 0.038, 0.022), (0.90, 0.020, 0.013))
    EAR_FRONT = (0.0, -0.75, -0.55)           # the hollow faces forward and down
    TRUNK_ROWS = [(-0.62, 0.95, 0.115, 0.150, 0.190), (-0.50, 0.96, 0.175, 0.225, 0.300),
                  (-0.32, 0.95, 0.205, 0.230, 0.320), (-0.10, 0.94, 0.230, 0.205, 0.320),
                  (0.10, 0.94, 0.225, 0.195, 0.285), (0.26, 0.95, 0.195, 0.190, 0.225),
                  (0.42, 0.97, 0.180, 0.180, 0.200), (0.57, 0.96, 0.155, 0.165, 0.180),
                  (0.68, 0.94, 0.095, 0.120, 0.130)]
    NECK = [(0, -0.42, 0.98, 0.150, 0.165, 0.205), (0, -0.57, 1.08, 0.124, 0.128, 0.165),
            (0, -0.70, 1.20, 0.100, 0.098, 0.128), (0, -0.80, 1.30, 0.086, 0.080, 0.100),
            (0, -0.87, 1.37, 0.076, 0.068, 0.086)]
    NECK_BONES = [(0, -0.52, 1.050), (0, -0.65, 1.160), (0, -0.76, 1.270)]
    MANE = 0.0
    ATTACK = True                             # the butt
    LEG_T = 1.15
    HOOF_K = 1.25
    # scimitar horns: up off the poll, sweeping back over the neck, diverging (D, body axes from the base)
    HORN_BASE_H = (0.034, -0.075, 0.072)
    HORN = [(0.0, 0.0, -0.025, 0.026), (0.004, 0.008, 0.020, 0.027), (0.022, 0.060, 0.105, 0.022),
            (0.046, 0.150, 0.165, 0.017), (0.070, 0.250, 0.175, 0.011), (0.086, 0.325, 0.140, 0.004)]
    # the beard hangs from the chin (D, body axes from under the chin): flat across, a tuft to a point
    BEARD_AT_H = (0.0, -0.285, -0.168)
    BEARD = [(0.0, -0.010, 0.012, 0.022, 0.016, 0.016), (0.0, 0.000, -0.040, 0.027, 0.022, 0.020),
             (0.0, 0.016, -0.095, 0.020, 0.016, 0.015), (0.0, 0.034, -0.140, 0.005, 0.005, 0.005)]

    COATS = {
        'chamois': dict(back='#6e4126', flank='#7d4a2b', light='#9a6440', belly='#2a201a', tail='#1c1612',
                        legs='#1e1814', edge='#15100c', face='#7a4a2c', muzzle='#3a2a20', chin='#33261e',
                        iris='#c8962a', stripe='#17120e', beard='#1e1814'),
        'white': dict(back='#ddd5c4', flank='#e6dfd0', light='#f3eee4', belly='#d6ccb8', tail='#ddd5c4',
                      legs='#d2c8b5', edge='#8e8272', face='#e6dfd0', muzzle='#cdbcaa', chin='#e3dbcb',
                      iris='#c8962a', nose='#8a6e66', hoof='#5a5048', hoof_light='#9a8c7c', beard='#e3dbcb',
                      horn='#b0a48e', horn_dark='#6e6352'),
        'pied': dict(back='#e3dccd', flank='#e9e3d6', light='#f4f0e6', belly='#dcd3c1', tail='#2a2420',
                     legs='#dcd3c1', edge='#3a322c', face='#e9e3d6', muzzle='#c4b2a2', chin='#e3dbcb',
                     iris='#c8962a', patch='#24201c', nose='#3a302c', beard='#2a2420'),
    }
    MISC = dict(horn='#74685a', horn_dark='#3a3229', horn_tip='#b8ab94', ear_in='#a88c74')

    def extra_pieces(self, bm, bvh, tags):
        c = self.hx(self.BEARD_AT_H)
        rows = [tuple(c + np.array(r[:3])) + tuple(r[3:]) for r in self.BEARD]
        tags['hair'] = loft(bm, rows, up=(0, -1, 0), seg=8, per_seg=2, cap0=0.4, cap1=0.3, capk=2)

    def skin_extra(self, body, rig, part):
        from beast_rig import set_rigid
        set_rigid(body, np.nonzero(part == PART['hair'])[0], "Jaw")       # the beard rides on the chin

    # ------------------------------------------------------------------ paint
    def coat_pattern(self, ctx, col):
        C, P, x, y, z, nz = ctx['C'], ctx['P'], ctx['x'], ctx['y'], ctx['z'], ctx['nz']
        if 'stripe' in C:                     # the dorsal stripe, from the withers to the tail
            d = np.exp(-(x / 0.040) ** 2) * smoothstep(0.35, 0.8, nz) * smoothstep(-0.55, -0.40, y)
            col = _mix(col, C['stripe'], 0.85 * d)
            sh = smoothstep(0.92, 0.80, z) * smoothstep(-0.60, -0.45, y) * smoothstep(-0.25, -0.38, y)   # the
            col = _mix(col, C['stripe'], 0.5 * sh * ctx['furp'])            # dark shoulder band, faint
        if 'patch' in C:
            pm = patches(P, 31, 2.4, 0.05) * ctx['furp']
            pm = np.maximum(pm, ctx['legp'] * patches(P, 37, 3.0, 0.15))
            col = _mix(col, C['patch'], pm)
        return col

    def face_pattern(self, ctx, fcol):
        C = ctx['C']
        if 'stripe' in C:                     # Alpine face stripes: from over the eye down to the muzzle
            hx, hy, hz = np.abs(ctx['hx']), ctx['hy'], ctx['hz']
            line = np.exp(-((hx - (0.055 - 0.06 * (-hy - 0.10))) / 0.020) ** 2) * smoothstep(-0.06, -0.14, hy)
            fcol = _mix(fcol, C['stripe'], 0.85 * line * smoothstep(-0.12, -0.04, hz))
        if 'patch' in C:
            fcol = _mix(fcol, C['patch'], patches(ctx['P'], 41, 3.0, 0.25))
        return fcol

    def paint_pieces(self, ctx, col, smooth):
        part, P, M, C = ctx['part'], ctx['P'], ctx['M'], ctx['C']
        col, smooth = horns(self, ctx, col, smooth)
        beard = part == PART['hair']
        if beard.any():
            s3 = _streaks(P, np.tile((0.0, 0.2, -1.0), (len(P), 1)), 95, across=0.006, length=0.10, steps=9)
            bc = np.tile(C['beard'], (len(P), 1)) * (0.75 + 0.45 * s3)[:, None]
            col = np.where(beard[:, None], bc, col)
        return col, smooth


SP = Goat()
