"""UVs and the painted coat of the cave bear (the framework is beast_paint.py).

UV cuts: along the underside of the belly, chest and throat and up under the tail, under the jaw, inside each leg;
the soles are separate islands, and the shells (jaw, tongue, teeth, eyes, ears, claws, hair) keep the seams their
builders marked.

Coat 'cave': dark brown, the coarse locks tipped grizzled tan on the hump and mane, darker legs, a lighter brown
muzzle, black nose pad and lips, cave dust on the paws, long pale claws darkening at the root, old claw-mark scars
across the face and one shoulder. 'old': the same bear gone grey (an older male). Strands follow bear_body.fur_flow;
on the fringes and clumps they darken toward the root (info.b).
"""
import numpy as np
from beast_common import smoothstep, fbm, vnoise
import bear_body as BB
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture, polyline_t, segments
from beast_body import PART


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 0.72) or (y > 0.85 and z < 1.00) or (y < -0.72 and z < 0.95), x > 0
    if region == 'head':                                   # under the jaw and throat (head space)
        h = BB.hx_inv(np.array(c))
        return h[2] < -0.24 and abs(x) < 0.12, x > 0
    if region == 'tail':
        return y > _interp_axis(z, BB.TAIL) - 0.01, x > 0
    j = BB.J
    if region.startswith('fleg'):
        return abs(x) < 0.30, y > _interp_axis(z, [j['SHO'], j['ELB'], j['WRI'], j['FPAW']])
    if region.startswith('hleg'):
        return abs(x) < 0.29, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


UV_SCALE = {'head': 1.6, 'ear': 1.3, 'eye': 2.5, 'nose': 1.6, 'jaw': 1.3, 'tongue': 0.8, 'tooth': 0.8, 'claw': 0.9,
            'hair': 0.9, 'tail': 1.0, 'sole': 0.4}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


def uv_layout(ob, name="uv_layout_bear", size=2048):
    return BP.uv_layout(ob, name, size)


COATS = {
    'cave': dict(root='#1a120c', base='#36261a', light='#7d6146', hump='#9a8063', legs='#20160f', muzzle='#6a5039',
                 iris='#6b3a12'),
    'old': dict(root='#1f1a16', base='#4a4038', light='#a49a8c', hump='#bdb4a6', legs='#2a2420', muzzle='#857868',
                iris='#5a3a1a'),
}
MISC = dict(skin='#1c1614', skin_light='#3d3330', pad='#262020', nostril='#0a0808', inner='#4a2226', gum='#5c2a2e',
            tongue='#8a4a4e', tooth='#e8dfc6', tooth_root='#a89a78', claw='#ddd1b4', claw_root='#3b322b',
            dust='#8a8070', scar='#9b8a7a', pupil='#080605')

# old claw-mark scars: three parallel rakes across the left of the face (head space) and one shoulder (body)
FACE_SCARS = [((0.140, -0.20, 0.09), (0.080, -0.42, -0.08)), ((0.160, -0.22, 0.05), (0.100, -0.44, -0.12)),
              ((0.175, -0.25, 0.00), (0.120, -0.46, -0.16))]
BODY_SCARS = [((-0.48, -0.60, 1.15), (-0.50, -0.28, 0.95)), ((-0.49, -0.56, 1.08), (-0.51, -0.25, 0.88))]


def paint(D, variant='cave'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MISC.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    on_jaw = D['on_jaw'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    ht = D['aux'].ravel()[idx]                         # hair: root (0) to tip (1)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    hair = part == PART['hair']
    fur = (part == PART['fur']) | hair | (part == PART['ear']) | (part == PART['jaw'])
    F = BB.fur_flow(P, N)
    n_big = fbm(P * 2.5, 3, seed=31)
    n_mid = fbm(P * 9.0, 3, seed=32)
    s1 = _streaks(P, F, 41, across=0.009, length=0.08, steps=9)
    s2 = _streaks(P, F, 42, across=0.026, length=0.18, steps=7)
    Hs = BB.hx_inv(P)                                  # head space
    hy, hz = Hs[:, 1], Hs[:, 2]

    # ------------------------------------------------------------ the coat
    top = smoothstep(0.0, 0.8, nz + 0.25 * n_big)
    col = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.30 * top)
    hump = np.exp(-((x / 0.45) ** 2 + ((y + 0.50) / 0.55) ** 2 + ((z - 1.32) / 0.35) ** 2))
    grizzle = smoothstep(0.20, 0.70, s1) * (0.35 + 0.65 * top)
    col = _mix(col, C['hump'], 0.75 * grizzle * (0.35 + 0.65 * hump))       # frosted tips, most on the hump and mane
    legs = smoothstep(0.62, 0.35, z) * (ax > 0.12)
    col = _mix(col, C['legs'], 0.7 * legs)
    col = _mix(col, C['root'], 0.30 * smoothstep(0.78, 0.55, z) * (1 - legs) * smoothstep(-0.05, 0.10, hy))   # under the belly
    col = _mix(col, C['root'], 0.65 * smoothstep(-0.15, -0.60, s2))            # dark partings between the locks
    hcol = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.15 + 0.25 * top + 0.35 * smoothstep(0.45, 1.0, ht))
    hcol = _mix(hcol, C['hump'], (0.35 + 0.4 * hump) * smoothstep(0.4, 1.0, ht))
    hcol = _mix(hcol, C['root'], 0.40 * smoothstep(0.30, 0.0, ht))
    col = np.where(hair[:, None], hcol, col)
    # face: a lighter muzzle, darker round the eyes, black nose pad and lips
    face = smoothstep(0.05, -0.05, hy) * (1 - hair) * (part != PART['ear'])
    muzzle = smoothstep(-0.30, -0.42, hy) * face
    col = _mix(col, C['muzzle'], 0.75 * muzzle)
    col = np.where((part == PART['jaw'])[:, None], np.tile(C['muzzle'] * 0.95, (n, 1)), col)    # the chin, like the muzzle
    dn = np.sqrt((ax / 0.072) ** 2 + ((hy + 0.600) / 0.050) ** 2 + ((hz + 0.070) / 0.058) ** 2)
    pad = smoothstep(1.12, 0.92, dn) * (part == PART['fur']) + (part == PART['nose'])     # the nose pad's own shape
    pad = np.clip(pad, 0, 1)
    col = _mix(col, M['pad'] * (0.85 + 0.15 * n_mid[:, None]), pad)
    nostril = np.exp(-(((ax - 0.026) / 0.013) ** 2 + ((hy + 0.628) / 0.013) ** 2 + ((hz + 0.072) / 0.014) ** 2))
    col = _mix(col, M['nostril'], smoothstep(0.35, 0.8, nostril))
    lips = (smoothstep(-0.185, -0.200, hz) * smoothstep(-0.240, -0.222, hz) * smoothstep(-0.18, -0.24, hy) * face *
            (part != PART['jaw']))                                     # the upper lip's edge, a band
    jawp = (part == PART['jaw']).astype(float)
    lips = np.maximum(lips, jawp * smoothstep(-0.225, -0.205, hz))
    col = _mix(col, M['skin'], lips)
    Nh = BB.hx_inv(N + BB.HEAD.pivot)                  # normals in head space
    mouth = (part == PART['jaw']) & (Nh[:, 2] > 0.4) & (hz > -0.215)
    mouth |= (part == PART['fur']) & (hy < -0.18) & (hz < -0.18) & (Nh[:, 2] < -0.5) & (np.abs(x) < 0.045)  # palate
    col = np.where(mouth[:, None], np.tile(M['gum'], (n, 1)), col)
    tongue = part == PART['tongue']
    col = np.where(tongue[:, None], M['tongue'] * (0.85 + 0.25 * n_mid[:, None]), col)
    for sfx in ('L', 'R'):                                       # dark rings round the eyes
        c = np.array(D['eyes']['eye_' + sfx])
        ring = smoothstep(BB.EYE_R * 2.4, BB.EYE_R * 1.1, np.linalg.norm(P - c, axis=1)) * fur
        col = _mix(col, C['root'], 0.6 * ring)
    # ears: dark skin inside the cup, fur outside
    earp = part == PART['ear']
    Fe = BB.hx_dir(np.stack([0.45 * np.sign(x), -np.ones(n), 0.1 * np.ones(n)], -1))   # each ear's hollow faces
    Fe = Fe / np.linalg.norm(Fe, axis=1, keepdims=True)                                  # this way (as built)
    inside = earp & ((N * Fe).sum(1) > 0.30)
    ecol = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.20 + 0.35 * smoothstep(0.3, 0.8, s1))
    col = np.where(earp[:, None], ecol, col)
    icol = _mix(np.tile(C['root'], (n, 1)), C['base'], 0.35 + 0.35 * smoothstep(0.2, 0.8, s1))
    col = np.where(inside[:, None], icol, col)
    # scars: pale hairless rakes
    scar = np.maximum(segments(Hs * np.array((1, 1, 1)), FACE_SCARS, 0.009) * face, segments(P, BODY_SCARS, 0.012))
    col = _mix(col, M['scar'], 0.85 * scar * (1 - hair))
    # cave dust on the paws
    dust = smoothstep(0.24, 0.10, z) * smoothstep(-0.3, 0.3, fbm(P * 7.0, 3, seed=63)) * fur
    col = _mix(col, M['dust'], 0.45 * dust)
    soles = fur & (z < 0.03) & (nz < -0.5)
    col = np.where(soles[:, None], M['pad'] * 1.2, col)
    grain = np.where((lips > 0.5) | (pad > 0.5), 0.92 + 0.12 * n_mid, 0.78 + 0.30 * s1 + 0.12 * s2)
    col = col * grain[:, None]
    smooth = np.where(pad > 0.5, 0.55, np.where(lips > 0.5, 0.25, 0.10))           # a wet nose
    smooth = np.where(tongue | mouth, 0.55, smooth)

    # ------------------------------------------------------------ teeth and claws
    tooth = part == PART['tooth']
    if tooth.any():
        tip = np.where(on_jaw, smoothstep(-0.21, -0.18, hz), smoothstep(-0.21, -0.25, hz))
        tc = _mix(np.tile(M['tooth_root'], (n, 1)), M['tooth'], 0.4 + 0.6 * tip)
        col = np.where(tooth[:, None], tc, col)
        smooth = np.where(tooth, 0.6, smooth)
    claw = part == PART['claw']
    if claw.any():
        tips = []
        for kind in ('F', 'H'):
            for s in (1, -1):
                tips += BB.toe_tips(kind, s)
        T = np.array(tips)
        d = np.min(np.linalg.norm(P[claw][:, None, :] - T[None], axis=2), axis=1)
        k = smoothstep(0.0, 0.06, d)                    # from the root out to the tip
        cc = _mix(np.tile(M['claw_root'], (claw.sum(), 1)), M['claw'], 0.25 + 0.75 * k)
        cc = cc * (0.88 + 0.2 * vnoise(P[claw] * np.array([60, 20, 60]), seed=77))[:, None]
        col[claw] = cc
        smooth[claw] = 0.45
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            dd = P - c
            dd = dd - np.outer(dd @ nv, nv)
            rr = np.linalg.norm(dd, axis=1) / BB.EYE_R
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
    light = np.where(part == PART['jaw'], 0.90, light)                     # the chin faces down: less painted shade
    aot = 0.38 + 0.62 * np.clip(ao, 0, 1)
    aot = np.where(hair, 0.55 + 0.45 * aot, aot)
    aot = np.where(part == PART['jaw'], 0.60 + 0.40 * aot, aot)          # the chin sits in the head's shadow
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.06)[:, None] * np.array([0.25, 0.2, 0.3])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("cave", "old")):
    D = bake_data(ob, size=size, ao_dist=0.25)
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Bear" if v == "cave" else "T_Bear_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "cave" else None, "M_Bear"))
    return paths, float(D['valid'].mean())
