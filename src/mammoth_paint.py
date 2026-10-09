"""UVs and the painted coat of the woolly mammoth (the framework is beast_paint.py).

UV cuts: along the underside of the belly, chest and throat and up under the tail, under the jaw, down the back of the
trunk, inside each leg; the soles are separate islands, and the shells (lip, tusks, eyes, ears, hair) keep the seams
their builders marked.

Coat 'brown': a reddish brown, the long guard hair tipped ginger, darker on the legs and under the belly, a dark
short-haired face and trunk ringed with wrinkles, the trunk's tip bare grey skin, old ivory tusks (stained at the
root, banded, the worn tips paler), grey soles, pale toenails, mud on the feet. 'dark': the same mammoth nearly black-
brown. Strands follow mammoth_body.fur_flow; on the fringes and clumps they darken toward the root (info.b).
"""
import numpy as np
from beast_common import smoothstep, fbm, vnoise
import mammoth_body as MB
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture, polyline_t
from beast_body import PART


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 1.30) or (y > 1.10 and z < 1.95) or (y < -1.40 and z < 1.75), x > 0
    if region == 'head':                                   # under the jaw and throat
        return z < 1.95 and abs(x) < 0.15 and y > -2.12, x > 0
    if region == 'proboscis':                              # down the back of the trunk
        yc = np.interp(-z, [-r[2] for r in MB.TRUNK_ROWS], [r[1] for r in MB.TRUNK_ROWS])
        return y > yc, x > 0
    if region == 'tail':
        return y > _interp_axis(z, MB.TAIL) - 0.01, x > 0
    j = MB.J
    if region.startswith('fleg'):
        return abs(x) < 0.55, y > _interp_axis(z, [j['SHO'], j['ELB'], j['WRI'], j['FPAW']])
    if region.startswith('hleg'):
        return abs(x) < 0.54, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


UV_SCALE = {'head': 1.4, 'proboscis': 1.3, 'ear': 1.2, 'eye': 2.0, 'jaw': 1.0, 'tusk': 0.7, 'hair': 0.8,
            'tail': 0.8, 'sole': 0.3}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


def uv_layout(ob, name="uv_layout_mammoth", size=2048):
    return BP.uv_layout(ob, name, size)


COATS = {
    'brown': dict(root='#1e120a', base='#55331b', light='#9a6638', tips='#c8935a', legs='#3a2414', face='#4a2e1c',
                  iris='#4a2a12'),
    'dark': dict(root='#100a07', base='#2e2017', light='#5e4633', tips='#866c52', legs='#1e150e', face='#2a1d15',
                 iris='#3a2412'),
}
MISC = dict(skin='#57504a', skin_dark='#2c2724', lip='#2a2524', inside='#6a4a48', ivory='#d9c9a0',
            ivory_root='#6e5230', ivory_band='#b09a6c', nail='#9a9282', mud='#5a4632', pupil='#080605')


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
    ht = D['aux'].ravel()[idx]                         # hair: root (0) to tip (1)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    hair = part == PART['hair']
    furp = part == PART['fur']
    fur = furp | hair | (part == PART['ear'])
    F = MB.fur_flow(P, N)
    n_big = fbm(P * 1.5, 3, seed=51)
    n_mid = fbm(P * 6.0, 3, seed=52)
    s1 = _streaks(P, F, 61, across=0.012, length=0.12, steps=9)
    s2 = _streaks(P, F, 62, across=0.035, length=0.26, steps=7)
    prob = part == PART['proboscis']
    tt = np.where(furp, MB.trunk_t(P), -1.0)           # down the trunk 0..1 (the tube and the stump), -1 elsewhere
    if prob.any():
        tt[prob] = polyline_t(P[prob], MB.TRUNK_ROWS)[0]

    # ------------------------------------------------------------ the coat
    top = smoothstep(0.0, 0.8, nz + 0.25 * n_big)
    col = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.25 * top + 0.15 * smoothstep(0.0, 0.6, n_big))
    hump = np.exp(-((x / 0.70) ** 2 + ((y + 0.85) / 0.80) ** 2 + ((z - 3.0) / 0.45) ** 2))
    tipsm = smoothstep(0.25, 0.75, s1) * (0.30 + 0.70 * top)
    col = _mix(col, C['tips'], 0.55 * tipsm * (0.40 + 0.60 * hump))           # ginger tips, most on the hump
    legs = smoothstep(1.05, 0.55, z) * (ax > 0.25)
    col = _mix(col, C['legs'], 0.65 * legs)
    col = _mix(col, C['root'], 0.35 * smoothstep(1.50, 1.25, z) * (1 - legs))  # under the belly
    col = _mix(col, C['root'], 0.65 * smoothstep(-0.15, -0.60, s2))            # dark partings between the locks
    hcol = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.15 + 0.20 * top + 0.35 * smoothstep(0.45, 1.0, ht))
    hcol = _mix(hcol, C['tips'], (0.30 + 0.35 * hump) * smoothstep(0.5, 1.0, ht))
    hcol = _mix(hcol, C['root'], 0.45 * smoothstep(0.30, 0.0, ht))
    hcol = _mix(hcol, C['legs'], 0.5 * smoothstep(1.0, 0.6, z) * (ax > 0.30))   # the shins' hair, darker
    col = np.where(hair[:, None], hcol, col)
    # the face and trunk: short dark hair; wrinkle rings across the trunk; its tip bare grey skin
    face = smoothstep(-1.95, -2.15, y) * smoothstep(2.75, 2.45, z) * furp
    col = _mix(col, C['face'], 0.70 * face)
    trunk = tt >= 0
    tcol = _mix(np.tile(C['face'], (n, 1)), C['light'], 0.30 * smoothstep(0.2, 0.8, s1))
    rings = 0.5 + 0.5 * np.sin(tt * 2 * np.pi * 30 + 5.0 * n_mid + 3.0 * n_big)       # uneven wrinkles
    tcol = tcol * (0.86 + 0.14 * smoothstep(0.30, 0.85, rings) * (0.5 + 0.5 * smoothstep(-0.2, 0.4, n_mid)))[:, None]
    bare = smoothstep(0.80, 0.97, tt) ** 1.5
    tcol = _mix(tcol, M['skin'] * (0.85 + 0.2 * n_mid[:, None]), bare)
    col = np.where(trunk[:, None], tcol, col)
    tipn = trunk & (tt > 0.93) & (N[:, 1] > 0.3)       # the nostrils' opening, under the curled tip
    col = np.where(tipn[:, None], M['skin_dark'] * 0.6, col)
    for sfx in ('L', 'R'):                                       # dark rings round the eyes
        c = np.array(D['eyes']['eye_' + sfx])
        ring = smoothstep(MB.EYE_R * 2.6, MB.EYE_R * 1.1, np.linalg.norm(P - c, axis=1)) * fur
        col = _mix(col, C['root'], 0.6 * ring)
    # the lower lip: hairy like the face outside, a paler inside
    jaw = part == PART['jaw']
    lipc = np.where((nz > 0.5)[:, None], M['inside'], C['face'] * 0.8)
    col = np.where(jaw[:, None], lipc, col)
    # ears: furry outside, darker inside the cup
    earp = part == PART['ear']
    Fe = np.stack([np.sign(x), -0.35 * np.ones(n), np.zeros(n)], -1)            # each ear's hollow, as built
    Fe = Fe / np.linalg.norm(Fe, axis=1, keepdims=True)
    inside = earp & ((N * Fe).sum(1) > 0.30)
    col = np.where(earp[:, None], _mix(np.tile(C['base'], (n, 1)), C['light'], 0.3 * smoothstep(0.3, 0.8, s1)), col)
    col = np.where(inside[:, None], _mix(np.tile(C['base'], (n, 1)), C['root'], 0.15), col)   # furry, barely darker
    # feet: grey soles, pale toenails, mud
    nails = np.zeros(n)
    for kind in ('F', 'H'):
        for s in (1, -1):
            for p in MB.toenails(kind, s):
                d = np.sqrt(((P - p) ** 2 / np.array((0.050, 0.036, 0.046)) ** 2).sum(1))
                nails = np.maximum(nails, smoothstep(1.15, 0.90, d))
    nails = nails * furp
    mud = smoothstep(0.42, 0.12, z) * smoothstep(-0.3, 0.3, fbm(P * 5.0, 3, seed=73)) * fur
    col = _mix(col, M['mud'], 0.55 * mud)
    col = _mix(col, M['nail'] * (0.85 + 0.25 * n_mid[:, None]), nails)
    soles = furp & (z < 0.03) & (nz < -0.5)
    col = np.where(soles[:, None], M['skin_dark'], col)
    grain = np.where(trunk | jaw | (nails > 0.5), 0.92 + 0.12 * n_mid, 0.78 + 0.30 * s1 + 0.12 * s2)
    col = col * grain[:, None]
    smooth = np.where(nails > 0.5, 0.35, np.where(jaw, 0.30, 0.10))
    smooth = np.where(bare > 0.5, 0.25, smooth)

    # ------------------------------------------------------------ tusks and eyes
    tusk = part == PART['tusk']
    if tusk.any():
        tl, tdist = polyline_t(np.stack([ax, y, z], -1), MB.TUSK)
        band = 0.5 + 0.5 * np.sin(tl * 2 * np.pi * 9 + 3.0 * vnoise(P * 4.0, seed=81))
        ic = _mix(np.tile(M['ivory_root'], (n, 1)), M['ivory'], smoothstep(0.02, 0.30, tl))
        ic = _mix(ic, M['ivory_band'], 0.35 * smoothstep(0.55, 0.9, band) * smoothstep(0.1, 0.3, tl))
        ic = _mix(ic, M['ivory'] * 1.05, smoothstep(0.80, 1.0, tl))              # worn, paler tips
        ic = ic * (0.95 + 0.06 * vnoise(P * np.array([12, 12, 12]), seed=82))[:, None]
        col = np.where(tusk[:, None], ic, col)
        smooth = np.where(tusk, 0.50, smooth)
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            dd = P - c
            dd = dd - np.outer(dd @ nv, nv)
            rr = np.linalg.norm(dd, axis=1) / MB.EYE_R
            ci = _mix(np.tile(C['iris'], (n, 1)), C['iris'] * 0.45, smoothstep(0.35, 0.8, rr))
            ci = _mix(ci, M['pupil'], smoothstep(0.45, 0.28, rr))
            ci = _mix(ci, M['pupil'], smoothstep(0.85, 1.0, rr))
            hl = np.array((-0.25, -0.45, 0.86))
            spec = smoothstep(0.93, 0.975, N @ (hl / np.linalg.norm(hl)))
            ci = _mix(ci, np.ones(3), 0.9 * spec)
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.95, smooth)

    # ------------------------------------------------------------ painted light
    light = 0.74 + 0.36 * (nz * 0.5 + 0.5)
    aot = 0.38 + 0.62 * np.clip(ao, 0, 1)
    aot = np.where(hair, 0.55 + 0.45 * aot, aot)
    aot = np.where(tusk, 0.75 + 0.25 * aot, aot)
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.06)[:, None] * np.array([0.25, 0.2, 0.3])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("brown", "dark")):
    D = bake_data(ob, size=size, ao_dist=0.45)
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Mammoth" if v == "brown" else "T_Mammoth_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "brown" else None, "M_Mammoth"))
    return paths, float(D['valid'].mean())
