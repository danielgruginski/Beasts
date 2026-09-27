"""UVs and the painted coats of the giant rat (the framework is beast_paint.py).

UV cuts: down the belly and throat and up the rump, under the chin and through the palate, inside each leg; the paw
soles and the tail (its own shell) are separate islands.

Coats: 'brown' (sewer rat, the default), 'black', 'plague' (pale, mangy bald patches, red eyes). Fur strokes follow
rat_body.fur_flow; ears, hands, feet, nose and the ringed tail are pink-grey skin.
"""
import numpy as np
from beast_common import smoothstep, fbm
import rat_body as RB
import rat_rig
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture
from beast_body import PART


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 0.26) or (y > 0.27 and z < 0.30), x > 0
    if region == 'head':
        return z < 0.268, x > 0
    if region == 'tail':
        return z < 0.2, x > 0
    j = RB.J
    if region.startswith('fleg'):
        return abs(x) < 0.068, y > _interp_axis(z, [j['SHO'], j['ELB'], j['WRI'], j['FPAW']])
    if region.startswith('hleg'):
        return abs(x) < 0.085, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


UV_SCALE = {'head': 1.5, 'earL': 1.3, 'earR': 1.3, 'eye': 3.0, 'nose': 1.5, 'jaw': 1.2, 'tooth': 1.5, 'whisker': 0.3,
            'tail': 1.0, 'sole': 0.5}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, RB.hw_inv, margin, relax)


def uv_layout(ob, name="uv_layout_rat", size=2048):
    return BP.uv_layout(ob, name, size)


COATS = {
    'brown': dict(back='#54432f', grizzle='#9a8670', side='#78634c', belly='#b4a68f', face='#6c5a47',
                  skin='#c28f85', skin_dark='#8c6059', tail='#b98f86', tail_dark='#86625b', tooth='#dc9a36',
                  eye='#0b0909', glint='#7a1a12', mange=0.0),
    'black': dict(back='#1b1918', grizzle='#3e3935', side='#24211f', belly='#57504a', face='#22201e',
                  skin='#8c6c67', skin_dark='#5d4643', tail='#7a605c', tail_dark='#54423e', tooth='#d6a24a',
                  eye='#090707', glint='#651410', mange=0.0),
    'plague': dict(back='#9b9282', grizzle='#c9c1b0', side='#aca392', belly='#cbc3b2', face='#a19988',
                   skin='#b8908a', skin_dark='#86605a', tail='#b18a83', tail_dark='#7c5b55', tooth='#c8b060',
                   eye='#c0160f', glint='#ff6a4a', mange=1.0),
}
MISC = dict(nose='#c98f8c', nostril='#4a2624', gum='#6a3235', palate='#5c2b2e', claw='#2a2220', whisker='#2c2724',
            pupil='#050404')


def paint(D, variant='brown'):
    C = {k: (_c(v) if isinstance(v, str) else v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MISC.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    on_jaw = D['on_jaw'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    Pu = RB.hw_inv(P)
    x, y, z = Pu[:, 0], Pu[:, 1], Pu[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    fur = (part == PART['fur']) | (part == PART['jaw'])
    F = RB.fur_flow(P, N)
    n_big = fbm(Pu * 9.0, 3, seed=31)
    n_mid = fbm(Pu * 28.0, 3, seed=32)
    s1 = _streaks(Pu, F, 41, across=0.007, length=0.025)
    s2 = _streaks(Pu, F, 42, across=0.016, length=0.05)

    # ------------------------------------------------------------ coat
    col = _mix(np.tile(C['side'], (n, 1)), C['back'], smoothstep(0.1, 0.7, nz + 0.25 * n_big))
    col = _mix(col, C['grizzle'], 0.5 * smoothstep(0.3, 0.75, s1) * smoothstep(-0.2, 0.5, nz))
    col = _mix(col, C['belly'], smoothstep(-0.05, -0.5, nz + 0.2 * n_mid) * smoothstep(0.30, 0.20, z))
    head = smoothstep(-0.34, -0.40, y)
    col = _mix(col, C['face'], 0.6 * head)
    snout = smoothstep(-0.47, -0.53, y)
    col = _mix(col, C['face'] * 1.25, 0.5 * snout)                       # greyer, lighter snout
    ec = RB.hw_inv(np.array(D['eyes']['eye_L']))
    rim = np.exp(-((ax - ec[0]) ** 2 + (y - ec[1]) ** 2 + (z - ec[2]) ** 2) / (2 * 0.013 ** 2))
    col = _mix(col, C['back'] * 0.6, 0.5 * rim)
    # pink-grey skin: hands and feet, ears, the tail
    limb = smoothstep(0.075, 0.045, z) * (ax > 0.03)
    ear = smoothstep(0.335, 0.35, z) * (y > -0.40) * (y < -0.36) * (ax > 0.03)
    skin = np.clip(np.maximum(limb, ear), 0, 1)
    scol = _mix(np.tile(C['skin'], (n, 1)), C['skin_dark'], 0.3 + 0.3 * n_mid)
    scol = _mix(scol, C['skin'] * 1.08, ear * smoothstep(-0.1, -0.6, N[:, 1]))          # the inside of the ears
    col = np.where(fur[:, None], _mix(col, scol, skin), col)
    claw = limb * smoothstep(-0.3, -0.7, N[:, 1]) * ((y < -0.285) | ((y < 0.07) & (y > 0.0)))
    col = _mix(col, M['claw'], 0.8 * claw)
    # plague: bald, scabby patches
    if C['mange'] > 0:
        patch = smoothstep(0.25, 0.4, fbm(Pu * 7.0, 3, seed=55)) * (1 - skin)
        col = _mix(col, _mix(np.tile(C['skin'], (n, 1)), C['skin_dark'], 0.5 + 0.5 * n_mid), patch)
        scab = patch * smoothstep(0.35, 0.6, fbm(Pu * 40.0, 2, seed=56))
        col = _mix(col, np.array([0.33, 0.13, 0.11]), 0.7 * scab)
    grain = np.where(skin > 0.5, 0.95 + 0.08 * n_mid, 0.80 + 0.28 * s1 + 0.10 * s2)
    col = col * grain[:, None]

    # ------------------------------------------------------------ pieces
    smooth = np.where(skin > 0.5, 0.30, 0.10)
    tail = part == PART['tail']
    if tail.any():
        t = rat_rig._tail_param(P[tail])
        top = smoothstep(-0.2, 0.6, N[tail, 2])
        rings = 0.5 + 0.5 * np.sin(t * 2 * np.pi * 9.0 * (1 + 0.12 * t))
        tc = _mix(np.tile(C['tail'], (tail.sum(), 1)), C['tail_dark'], 0.25 + 0.35 * top + 0.25 * rings)
        tc = _mix(tc, C['back'], 0.5 * smoothstep(1.2, 0.0, t))                        # furred where it leaves the rump
        col[tail] = tc
        smooth[tail] = 0.38
    nose = part == PART['nose']
    nsoft = np.exp(-(((x) / 0.016) ** 2 + ((y + 0.600) / 0.012) ** 2 + ((z - 0.277) / 0.014) ** 2))
    col = _mix(col, M['nose'], np.maximum(nose.astype(float), smoothstep(0.35, 0.6, nsoft)))
    nostril = np.exp(-(((ax - 0.006) / 0.003) ** 2 + ((y + 0.607) / 0.003) ** 2 + ((z - 0.279) / 0.003) ** 2))
    col = _mix(col, M['nostril'], nostril)
    smooth = np.where(nose | (nsoft > 0.5), 0.5, smooth)
    palate = (part == PART['fur']) & (y < -0.44) & (z < 0.25) & (nz < -0.3) & (ax < 0.02)
    col = np.where(palate[:, None], np.tile(M['palate'], (n, 1)), col)
    jawp = part == PART['jaw']
    inside = jawp & (nz > 0.45)
    col = np.where(inside[:, None], np.tile(M['gum'], (n, 1)), col)
    col = np.where((jawp & ~inside)[:, None], _mix(col, C['belly'], 0.5), col)
    tooth = part == PART['tooth']
    if tooth.any():
        tip = np.where(on_jaw, smoothstep(0.245, 0.258, z), smoothstep(0.252, 0.240, z))
        front = smoothstep(0.0, -0.6, N[:, 1])
        tcol = _mix(np.tile(C['tooth'] * 0.85, (n, 1)), C['tooth'], front)
        tcol = _mix(tcol, np.array([0.93, 0.88, 0.74]), 0.5 * tip)
        col = np.where(tooth[:, None], tcol, col)
        smooth = np.where(tooth, 0.65, smooth)
    wh = part == PART['whisker']
    col = np.where(wh[:, None], np.tile(M['whisker'], (n, 1)), col)
    smooth = np.where(wh, 0.3, smooth)
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            d = P - c
            d = d - np.outer(d @ nv, nv)
            r = np.linalg.norm(d, axis=1) / RB.EYE_R
            ci = _mix(np.tile(C['eye'], (n, 1)), M['pupil'], smoothstep(0.45, 0.2, r))
            ci = _mix(ci, C['glint'], 0.8 * smoothstep(0.55, 0.85, r) * smoothstep(1.0, 0.85, r))    # red rim
            hl_dir = np.array((-0.2, -0.5, 0.84))
            spec = smoothstep(0.93, 0.975, (N @ (hl_dir / np.linalg.norm(hl_dir))))
            ci = _mix(ci, np.ones(3), 0.9 * spec)
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.95, smooth)
    pads = fur & (z < 0.008) & (nz < -0.6)
    col = np.where(pads[:, None], _mix(col, C['skin_dark'], 0.8), col)

    # ------------------------------------------------------------ painted light
    light = 0.76 + 0.34 * (nz * 0.5 + 0.5)
    aot = 0.42 + 0.58 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.08)[:, None] * np.array([0.25, 0.2, 0.35])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("brown", "black", "plague")):
    D = bake_data(ob, size=size, ao_dist=0.15)
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Rat" if v == "brown" else "T_Rat_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "brown" else None, "M_Rat"))
    return paths, float(D['valid'].mean())
