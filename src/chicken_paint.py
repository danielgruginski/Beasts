"""UVs and the painted plumage of the hen (the framework is beast_paint.py), 2026-10-20.

UV cuts: under the belly and up the front of the neck, under the chin, inside the drumsticks; the shells keep the
seams their lofts marked. Plumage: rows of feathers (each row's edge darker) laid along the body, the hackles on the
neck lighter and streaked, the wings' coverts in bands, the tail darker; a red comb, wattles and face round the eye,
a horn-yellow beak and yellow shanks, an orange eye. Coats: 'brown' (red-brown hen, golden hackles, dark tail),
'white', 'black' (a green sheen on the tail and wings).
"""
import numpy as np
import beast_paint as BP
from beast_common import smoothstep, fbm, vnoise
from beast_paint import _c, _mix, _streaks, bake_data, write_texture
from beast_body import PART
import chicken_body as CB


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 0.15) or (y < -0.075 and z < 0.33 and abs(x) < 0.03), x > 0
    if region == 'head':
        return z < 0.352 and abs(x) < 0.03, x > 0
    if region == 'tail':
        return y > 0.12, x > 0
    if region.startswith('hleg'):
        return abs(x) < 0.045, y > 0.02
    return None


UV_SCALE = {'head': 1.8, 'eye': 2.0, 'whisker': 1.3, 'horn': 1.2, 'jaw': 1.0, 'claw': 0.8, 'hair': 1.0, 'tail': 1.0}


def unwrap(ob, margin=0.004, relax=30):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


COATS = {
    'brown': dict(body='#8c4a22', breast='#9a5a2e', hackle='#c8842e', wing='#7a3c1a', covert='#5a2a12',
                  tail='#2a1c16', edge='#3a1c0c', down='#a87a52'),
    'white': dict(body='#ebe5d8', breast='#efe9dd', hackle='#f2ecdf', wing='#e4ddcf', covert='#d8d0c0',
                  tail='#e0d8c9', edge='#b8ae9c', down='#f2ede3'),
    'black': dict(body='#1e1c20', breast='#222024', hackle='#2a282c', wing='#1c1e22', covert='#202a26',
                  tail='#16201c', edge='#0c0b0d', down='#3a3638'),
}
MISC = dict(comb='#c42418', comb_dark='#7a1410', face='#c4483a', beak='#d6b04c', beak_dark='#9a7a30',
            leg='#d8b040', leg_dark='#a07a20', iris='#d0701a', pupil='#060504')


def paint(D, variant='brown'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MISC.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    n = len(P)
    nz = N[:, 2]
    furp = part == PART['fur']
    wing = part == PART['hair']
    tail = part == PART['tail']
    F = CB._flow(P, N)
    s1 = _streaks(P, F, 93, across=0.002, length=0.012, steps=7)
    n_big = fbm(P * 20.0, 3, seed=91)
    # feathers in scallops: rows along the body, each row split into rounded feather tips across it
    t = (P @ np.array((0.0, 1.0, -0.35))) * 60.0 + 0.4 * vnoise(P * 60.0, seed=94)
    u = np.arctan2(z - 0.21, np.abs(x) + 1e-4) * 0.09 * 60.0           # around the body, in feather widths
    u = u + 0.5 * (np.floor(t) % 2)                                     # alternate rows offset half a feather
    fu = u - np.floor(u)
    row = t - np.floor(t)
    edge = smoothstep(0.66, 0.90, row + 0.20 * (1 - np.cos(2 * np.pi * fu)) * 0.5)
    col = np.tile(C['body'], (n, 1))
    col = _mix(col, C['breast'], smoothstep(-0.02, -0.07, y) * smoothstep(0.30, 0.20, z))
    col = _mix(col, C['down'], 0.6 * smoothstep(0.15, 0.12, z) * furp)
    neck = smoothstep(-0.04, -0.07, y) * smoothstep(0.26, 0.30, z) * smoothstep(0.37, 0.34, z) * furp
    col = _mix(col, C['hackle'], 0.85 * neck)
    col = _mix(col, C['edge'], 0.28 * edge * furp * (1 - neck))
    col = _mix(col, C['hackle'] * 0.7, 0.35 * neck * smoothstep(0.1, 0.5, s1))       # hackles streaked
    # wings: bands of coverts across, the flight feathers darker toward the tip
    wt = (y + 0.06) / 0.18
    bands = 0.5 + 0.5 * np.sin(wt * 2 * np.pi * 4 + 3 * (0.25 - z))
    wc = _mix(np.tile(C['wing'], (n, 1)), C['covert'], 0.45 * smoothstep(0.55, 0.9, bands))
    wc = _mix(wc, C['tail'], 0.5 * smoothstep(0.55, 1.0, wt))
    col = np.where(wing[:, None], wc, col)
    tc = _mix(np.tile(C['tail'], (n, 1)), C['edge'], 0.3 * smoothstep(0.2, 0.6, s1))
    col = np.where(tail[:, None], tc, col)
    col = _mix(col, C['tail'], 0.6 * smoothstep(0.10, 0.14, y) * smoothstep(0.24, 0.28, z) * furp)  # tail coverts
    # the face: bare red skin round the eye and down to the wattles
    face = (furp * smoothstep(-0.110, -0.122, y) * smoothstep(0.338, 0.350, z) * smoothstep(0.392, 0.380, z) *
            smoothstep(0.006, 0.016, np.abs(x)))                         # bare red skin round the eye
    col = _mix(col, M['face'], 0.85 * face)
    grain = np.where(furp | wing | tail, 0.86 + 0.22 * s1 + 0.06 * n_big, 1.0)
    col = col * grain[:, None]
    smooth = np.full(n, 0.12)
    red = part == PART['whisker']
    col = np.where(red[:, None], _mix(np.tile(M['comb'], (n, 1)), M['comb_dark'], 0.4 * smoothstep(0.2, -0.6, nz)), col)
    smooth = np.where(red, 0.35, smooth)
    beak = (part == PART['horn']) | (part == PART['jaw'])
    bc = _mix(np.tile(M['beak'], (n, 1)), M['beak_dark'], smoothstep(-0.150, -0.138, y))
    col = np.where(beak[:, None], bc, col)
    smooth = np.where(beak, 0.45, smooth)
    claw = part == PART['claw']
    sc = vnoise(P * 400.0, seed=95)                                     # scales on the shanks
    lc = _mix(np.tile(M['leg'], (n, 1)), M['leg_dark'], 0.25 + 0.25 * smoothstep(0.0, 0.6, sc))
    col = np.where(claw[:, None], lc, col)
    smooth = np.where(claw, 0.35, smooth)
    eye = part == PART['eye']
    if eye.any():
        ec = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            r = np.linalg.norm(P - c, axis=1) / CB.EYE_R
            ci = _mix(np.tile(M['iris'], (n, 1)), M['pupil'], smoothstep(0.42, 0.32, r))
            ci = _mix(ci, M['pupil'], smoothstep(0.85, 1.0, r))
            side = (x > 0) if sfx == 'L' else (x <= 0)
            ec = np.where(side[:, None], ci, ec)
        col = np.where(eye[:, None], ec, col)
        smooth = np.where(eye, 0.95, smooth)
    light = 0.86 + 0.22 * (nz * 0.5 + 0.5)
    aot = 0.60 + 0.40 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None]
    shaded = np.where(eye[:, None], col, shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=512, variants=("brown", "white", "black")):
    import bpy, deer_paint
    D = bake_data(ob, size=size, ao_dist=0.05)
    paths = []
    for i, v in enumerate(variants):
        col, smooth = paint(D, v)
        name = "T_Chicken" if i == 0 else "T_Chicken_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if i == 0 else None, "M_Chicken"))
    deer_paint.matte(bpy.data.materials["M_Chicken"])
    return paths, float(D['valid'].mean())
