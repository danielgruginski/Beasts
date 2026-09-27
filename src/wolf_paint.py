"""UVs and the hand-painted coat of the wolf.

UVs: the fur body is cut along hidden lines (down the belly and throat and up between the hind legs, under the chin
and through the palate, the inside of each leg, the underside of the tail), the ears split front/back and the paw
soles cut off; islands come from the skin weights (head, trunk, each leg, tail). The jaw, tongue, teeth and eyes
carry the seams their builders marked. Angle-based unwrap, one texel density, the head, ears and eyes enlarged.

Texture: painted per texel like the spider's (Insectoids/src/spider_paint.py): Cycles bakes rest position, normal,
part id and AO into float images and numpy paints from those. Fur strokes follow the fur flow (wolf_body.fur_flow):
noise averaged along the flow, so the streaks run continuously across UV seams. Alpha holds smoothness.
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector
from beast_common import ROOT, smoothstep, fill_gutters, fbm, vnoise, hexc
import wolf_body as W
import beast_paint as BP
from beast_paint import (TEX_DIR, _interp_axis, _c, _mix, _streaks, bake_data, write_texture, game_material)


# ----------------------------------------------------------------------------------------- seams


def _spine_z(y):
    return 0.66 if y > -0.30 else 0.66 + (-0.30 - y) * 0.55


def _cut(region, c):
    """(face is on the slit side, which side of the slit). Unwarped face centre c."""
    x, y, z = c
    if region == 'trunk':
        return (z < _spine_z(y) - 0.02) or (y > 0.42 and z < 0.69), x > 0
    if region == 'head':
        return z < 0.83, x > 0
    if region == 'tail':
        return y < _interp_axis(z, W.TAIL), x > 0
    if region.startswith('fleg'):
        j = W.J
        return abs(x) < 0.095, y > _interp_axis(z, [j['SHO'], j['ELB'], j['WRI'], j['FPAW']])
    if region.startswith('hleg'):
        j = W.J
        return abs(x) < 0.095, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, W.hw_inv, margin, relax)


def uv_layout(ob, name="uv_layout_wolf", size=2048):
    return BP.uv_layout(ob, name, size)


UV_SCALE = {'head': 1.6, 'earL': 1.3, 'earR': 1.3, 'eye': 3.0, 'nose': 1.6, 'jaw': 1.3, 'tongue': 0.8,
            'tooth': 0.5, 'sole': 0.5, 'tail': 0.9}


# ----------------------------------------------------------------------------------------- data bakes


# ----------------------------------------------------------------------------------------- painting
COATS = {
    # grey (timber) wolf: charcoal saddle, buff-grey flanks, cinnamon legs and ears, cream underside and face
    'grey': dict(saddle='#35312d', grizzle='#8f877a', side='#8c8272', buff='#a89478', tawny='#9c7550',
                 cream='#dcd2bd', face_pale='#e3dccd', muzzle='#8e7a5f', mark='#221e1b', eye='#d9a12e'),
    # black wolf: near-black coat, grey muzzle and chest, yellow eyes
    'black': dict(saddle='#1a1918', grizzle='#3d3a37', side='#262422', buff='#34302c', tawny='#3b3530',
                  cream='#58534d', face_pale='#6c665e', muzzle='#3a3530', mark='#0f0e0d', eye='#e2b22e'),
    # white (arctic) wolf: cream all over, grey-buff saddle hint, pale amber eyes
    'white': dict(saddle='#c8c1b3', grizzle='#e6e1d7', side='#e2dccf', buff='#e3dac8', tawny='#d6c7aa',
                  cream='#eee9df', face_pale='#f2eee6', muzzle='#cfc3ab', mark='#4a433d', eye='#d9a84a'),
}
MOUTH = dict(nose='#191716', lip='#1d1918', gum='#6e3435', palate='#5a2a2c', tongue='#b4585c', tongue_dark='#8a3c42',
             tooth='#e9e1cc', tooth_root='#b8a78a', pupil='#0c0a09', eye_rim='#191512', pad='#2b2522',
             claw='#2a2420')


def paint(D, variant='grey'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MOUTH.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    on_jaw = D['on_jaw'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    Pu = W.hw_inv(P)
    x, y, z = Pu[:, 0], Pu[:, 1], Pu[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    fur = (part == W.PART['fur']) | (part == W.PART['jaw'])
    F = W.fur_flow(P, N)

    n_big = fbm(Pu * 6.0, 3, seed=11)
    n_mid = fbm(Pu * 18.0, 3, seed=12)
    s1 = _streaks(Pu, F, 21)                           # fine strokes
    s2 = _streaks(Pu, F, 22, across=0.022, length=0.07)  # clumps

    # ------------------------------------------------------------ base coat by region
    col = np.tile(C['side'], (n, 1)).astype(float)
    col = _mix(col, C['buff'], 0.45 + 0.35 * n_big)
    head = smoothstep(-0.64, -0.68, y)
    legs = smoothstep(0.44, 0.34, z) * (y < 0.46)
    tail = smoothstep(0.45, 0.50, y) * smoothstep(0.70, 0.66, z) * (ax < 0.12)
    # the saddle: dark over the back, from the ruff to the tail, frayed edge
    back = smoothstep(0.15, 0.65, nz + 0.25 * n_mid + 0.18 * n_big) * smoothstep(0.58, 0.70, z)
    saddle = back * smoothstep(-0.62, -0.48, y) * (1 - tail) * (1 - head)
    saddle = np.maximum(saddle, 0.8 * smoothstep(0.2, 0.7, nz) * smoothstep(-0.55, -0.45, y) * smoothstep(0.62, 0.72, z))
    col = _mix(col, C['saddle'], 0.85 * saddle)
    # grizzle: pale-tipped guard hairs through the dark
    griz = smoothstep(0.25, 0.7, s1) * (0.35 + 0.65 * saddle)
    col = _mix(col, C['grizzle'], 0.55 * griz)
    # cream underside, throat, chest, inner legs
    belly = smoothstep(-0.05, -0.55, nz + 0.2 * n_mid)
    medial = smoothstep(0.085, 0.065, ax) * smoothstep(0.55, 0.35, z)
    throat = smoothstep(0.72, 0.62, z) * smoothstep(-0.42, -0.55, y) * smoothstep(-0.2, -0.7, N[:, 1] + 0.3 * nz)
    pale = np.clip(np.maximum.reduce([belly, medial * 0.9, throat]), 0, 1) * (1 - tail * 0.7)
    col = _mix(col, C['cream'], 0.9 * pale)
    # cinnamon legs (outside), a dark stripe down the front of the forelegs, pale paws
    outer_leg = legs * (1 - medial)
    col = _mix(col, C['tawny'], 0.75 * outer_leg * (0.7 + 0.3 * n_mid))
    fore = (y < -0.1) * smoothstep(0.12, 0.18, z) * smoothstep(0.36, 0.30, z)
    stripe = fore * smoothstep(-0.45, -0.85, N[:, 1]) * smoothstep(0.6, 0.2, np.abs(N[:, 0]))
    col = _mix(col, C['mark'], 0.6 * stripe * (0.8 + 0.2 * n_mid))
    paws = smoothstep(0.075, 0.05, z)
    col = _mix(col, C['cream'], 0.7 * paws)
    # tail: grey, dark along the top, black tip, dark gland spot near the base
    tail_top = smoothstep(0.1, 0.6, N[:, 1] + 0.5 * nz)
    col = _mix(col, C['saddle'], 0.7 * tail * tail_top)
    col = _mix(col, C['mark'], tail * smoothstep(0.37, 0.31, z))
    gland = np.exp(-(((y - 0.53) / 0.03) ** 2 + ((z - 0.66) / 0.025) ** 2 + (x / 0.025) ** 2))
    col = _mix(col, C['mark'], 0.8 * gland)

    # ------------------------------------------------------------ face
    fcol = _mix(np.tile(C['side'], (n, 1)), C['buff'], 0.5 + 0.3 * n_mid)
    forehead = smoothstep(0.84, 0.88, z) * smoothstep(-0.80, -0.74, y)
    fcol = _mix(fcol, C['saddle'], 0.35 * forehead)
    fcol = _mix(fcol, C['muzzle'], smoothstep(-0.78, -0.82, y) * smoothstep(0.02, 0.5, nz))       # tawny muzzle top
    cheek = smoothstep(0.852, 0.832, z + 0.25 * (y + 0.78) * (y < -0.78)) * smoothstep(0.015, 0.035, ax)
    fcol = _mix(fcol, C['face_pale'], 0.95 * cheek * (0.85 + 0.15 * n_mid))                        # pale cheeks, lips
    fcol = _mix(fcol, C['face_pale'], 0.9 * smoothstep(-0.2, -0.6, nz) * smoothstep(-0.70, -0.76, y))   # under the jaw
    chin = smoothstep(0.80, 0.77, z)
    fcol = _mix(fcol, C['face_pale'], chin)
    e_l = np.array(D['eyes']['eye_L'])
    ec = W.hw_inv(e_l)
    dx, dy, dz = ax - ec[0], y - ec[1], z - ec[2]
    brow = np.exp(-((dx / 0.012) ** 2 + ((dy - 0.006) / 0.014) ** 2 + ((dz - 0.019) / 0.008) ** 2))   # pale eyebrow spot
    fcol = _mix(fcol, C['face_pale'], 0.8 * brow)
    tear = np.exp(-(((dz + 0.012 + 0.45 * (dy + 0.018))) / 0.004) ** 2) * (dy < 0.004) * (dy > -0.040) * (np.abs(dx) < 0.012)
    fcol = _mix(fcol, C['mark'], 0.55 * tear)
    rim = np.exp(-(dx ** 2 + dy ** 2 + dz ** 2) / (2 * 0.015 ** 2))
    fcol = _mix(fcol, C['mark'], 0.6 * rim)
    lip = (smoothstep(0.790, 0.782, z) * (y < -0.79) * smoothstep(0.3, -0.2, nz)
           * (part != W.PART['jaw']))                                                              # black lip line
    fcol = _mix(fcol, M['lip'], lip)
    col = np.where(fur[:, None], _mix(col, fcol, head), col)
    # ears: tawny backs with a dark rim, pale inside
    ear = smoothstep(0.915, 0.935, z) * (y > -0.73) * (y < -0.64)
    ear_front = smoothstep(-0.1, -0.5, N[:, 1])
    ecol = _mix(np.tile(C['tawny'], (n, 1)), C['saddle'], 0.35 + 0.3 * smoothstep(1.0, 1.03, z))
    ecol = _mix(ecol, C['cream'], ear_front * smoothstep(1.02, 0.99, z))
    ecol = _mix(ecol, C['mark'], ear_front * 0.4 * smoothstep(0.93, 0.96, z) * smoothstep(1.0, 0.97, z) *
                smoothstep(0.02, 0.0, np.abs(ax - 0.06)))
    col = np.where(fur[:, None], _mix(col, ecol, ear), col)

    # fur texture over all of it
    grain = 0.82 + 0.26 * s1 + 0.10 * s2
    col = col * grain[:, None]

    # ------------------------------------------------------------ mouth, nose, eyes
    smooth = np.full(n, 0.10)
    nose = part == W.PART['nose']
    nose_soft = np.exp(-(((x) / 0.022) ** 2 + ((y + 0.955) / 0.016) ** 2 + ((z - 0.836) / 0.018) ** 2))
    col = _mix(col, M['nose'], np.maximum(nose.astype(float), smoothstep(0.35, 0.6, nose_soft)))
    smooth = np.where(nose | (nose_soft > 0.6), 0.55, smooth)
    palate = (part == W.PART['fur']) & (y < -0.785) & (y > -0.912) & (z < 0.779) & (nz < -0.3) & (ax < 0.03)
    rugae = 0.85 + 0.15 * np.sin((y + 0.8) * 420)
    col = np.where(palate[:, None], M['palate'] * rugae[:, None], col)
    smooth = np.where(palate, 0.45, smooth)
    jawp = part == W.PART['jaw']
    inside = jawp & (nz > 0.45)
    col = np.where(inside[:, None], np.tile(M['gum'], (n, 1)), col)
    jaw_lip = jawp & ~inside & (z > 0.786)
    col = np.where(jaw_lip[:, None], np.tile(M['lip'], (n, 1)), col)
    smooth = np.where(inside, 0.45, smooth)
    tongue = part == W.PART['tongue']
    groove = smoothstep(0.004, 0.0, ax)
    tcol = _mix(np.tile(M['tongue'], (n, 1)), M['tongue_dark'], 0.5 * groove + 0.4 * smoothstep(0.3, -0.3, nz))
    col = np.where(tongue[:, None], tcol, col)
    smooth = np.where(tongue, 0.55, smooth)
    tooth = part == W.PART['tooth']
    root = np.where(on_jaw, smoothstep(0.778, 0.772, z), smoothstep(0.779, 0.785, z))
    col = np.where(tooth[:, None], _mix(np.tile(M['tooth'], (n, 1)), M['tooth_root'], root), col)
    smooth = np.where(tooth, 0.6, smooth)
    eye = part == W.PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            t = np.array((0, 1, 0.35))
            t = t - nv * t.dot(nv)
            t /= np.linalg.norm(t)
            b = np.cross(nv, t)
            d = P - c
            u = (d @ t) / (1.35 * W.EYE_R)
            v = (d @ b) / (0.72 * W.EYE_R)
            r = np.sqrt(u * u + v * v)
            iris = _mix(np.tile(C['eye'] * 1.1, (n, 1)), C['eye'] * 0.6, smoothstep(0.45, 0.74, r))
            ci = _mix(iris, M['pupil'], smoothstep(0.27, 0.21, np.sqrt((u * 1.0) ** 2 + (v * 1.0) ** 2)))
            ci = _mix(ci, M['eye_rim'], smoothstep(0.76, 0.86, r))
            hl = np.exp(-(((u + 0.25) / 0.12) ** 2 + ((v - 0.30) / 0.12) ** 2))
            ci = _mix(ci, np.ones(3), 0.9 * hl)
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.92, smooth)
    pads = fur & (z < 0.012) & (nz < -0.6)
    col = np.where(pads[:, None], np.tile(M['pad'], (n, 1)), col)
    # claws: dark tips at the front of each toe
    claw = fur & (z < 0.03) & (nz > -0.3) & (-N[:, 1] > 0.5)
    col = _mix(col, M['claw'], 0.7 * claw)

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


def build_texture(ob, hi=None, size=1024, variants=("grey", "black", "white")):
    D = bake_data(ob, size=size)
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Wolf" if v == "grey" else "T_Wolf_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "grey" else None, "M_Wolf"))
    return paths, float(D['valid'].mean())
