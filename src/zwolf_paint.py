"""UVs and the painted coats of the zombie wolf.

UVs: the wolf's (wolf_paint._cut: seams down the belly and throat, under the chin, inside the legs, under the tail;
ears front/back, paw soles), the same region scales; the rib bars (PART['bone']) at 0.9.

Texture: painted per texel from the bakes (beast_paint.bake_data), like the wolf's, in three coats on the same UVs:
T_ZombieWolf (grey: the grey wolf's coat gone dull, dirty and greenish), T_ZombieWolf_Dark (a black wolf's),
T_ZombieWolf_Pale (a white wolf's, yellowed). A = smoothness. What makes it read as undead at the game camera is big
and high-contrast:
  - bald, grey-green rotting skin (zwolf_body.BALD, the same mask that keeps the fur sculpt off it) with bruises, green
    rot and dark veins; the fur matted dark round each patch;
  - ribs drawn down both flanks (strong through the bald skin), the spine's processes, hip points and pin bones
    picked out pale;
  - the torn flank: a near-black cavity, wet red walls, a pale torn edge, a crust of dried blood and drips under it,
    a bruised halo; the rib bars bone-pale, stained where they go into the flesh; the haunch's torn patch the same;
  - milky white eyes in dark, sunken sockets; dark gums and yellow teeth under the drawn-back lips, blood crusted round
    the mouth and down the throat; the torn ear's edge crusted.
"""
import bpy, math
import numpy as np
from beast_common import smoothstep, fbm, vnoise
from beast_body import PART
import beast_paint as BP
from beast_paint import _c, _mix, _streaks, bake_data, write_texture
import wolf_paint
import zwolf_body as Z

UV_SCALE = dict(wolf_paint.UV_SCALE, bone=0.9)


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, wolf_paint._cut, UV_SCALE, Z.hw_inv, margin, relax)


COATS = {
    # the grey wolf's coat (wolf_paint 'grey') dulled, darker and dirty, with a green cast
    'grey': dict(saddle='#33302b', grizzle='#7d786a', side='#6c675c', buff='#787061', tawny='#6a5b47',
                 cream='#8b8572', face='#6a655a', muzzle='#524a3f', mark='#1c1916', dirt='#4a4434'),
    # a black wolf's
    'dark': dict(saddle='#121110', grizzle='#3b3834', side='#24221f', buff='#2c2925', tawny='#2e2924',
                 cream='#423e37', face='#2c2a26', muzzle='#262220', mark='#0b0a09', dirt='#29261d'),
    # a white wolf's, yellowed and grimy
    'pale': dict(saddle='#6b675d', grizzle='#a5a091', side='#8c8779', buff='#968f7c', tawny='#837862',
                 cream='#a49d8b', face='#95907f', muzzle='#776d5f', mark='#2c2924', dirt='#5a5440'),
}
# the rot, the same for every coat (the Humans repo's zombies are #7f8b72 / #8e9680, their bones #d8cfb4)
ROT = dict(skin='#7f8b72', skin2='#8e9680', rot='#56663a', bruise='#4c3b4b', vein='#323d31', blood='#3a1311',
           wet='#5e1813', flesh='#7d2c26', cavity='#140707', bone='#d8cfb4', bone_dark='#7f7357', edge='#a08e80',
           crust='#2b1310', eye='#d2d8d1', eye_dim='#8d9a99', gum='#4a1d24', lip='#1b1617', palate='#3c1a1f',
           tooth='#c8b88e', tooth_root='#5f4c33', tongue='#6a4a52', tongue_dark='#463037', nose='#2b2727',
           pad='#29231f', claw='#26201b')


def _rib_shade(ph):
    """Light from above on rib bars across the flank: + on each rib's upper edge, - in the groove under it. ph: the
    rib phase (u - round(u)), + upward."""
    hl = np.exp(-((ph - 0.10) / 0.15) ** 2)
    sh = np.exp(-((ph + 0.32) / 0.14) ** 2) + 0.6 * np.exp(-((np.abs(ph) - 0.5) / 0.10) ** 2)
    return hl, sh


def _wound_colours(col, smooth, e, m, R, n_a, n_b, rim_w=0.06, dent=None):
    """A torn hole of elliptical distance e (< 1 inside), mask m: a dark cavity, wet red walls, a pale torn edge, a
    crust of dried blood round it and a bruised halo. dent: how deep the mesh really is sunk there (0..1), so the
    inside is painted only where the hole is. -> (col, smooth)"""
    floor = smoothstep(0.80, 0.55, e)
    inside = smoothstep(1.0, 0.94, e)
    if dent is not None:
        inside = inside * smoothstep(0.05, 0.20, dent)
        floor = floor * smoothstep(0.30, 0.60, dent)
    wcol = _mix(np.tile(R['flesh'], (len(e), 1)), R['wet'], 0.5 + 0.5 * n_a)
    wcol = _mix(wcol, R['cavity'], floor * (0.85 + 0.15 * n_b))
    halo = smoothstep(2.0, 1.25, e) * (1 - inside)
    col = _mix(col, R['bruise'], 0.55 * halo * m * (0.7 + 0.3 * n_a))
    crust = smoothstep(1.42, 1.10, e + 0.08 * n_b) * (1 - inside)
    col = _mix(col, R['crust'], 0.85 * crust * m)
    edge = np.exp(-((e - 1.02 - 0.03 * n_a) / rim_w) ** 2)
    col = _mix(col, R['edge'], 0.8 * edge * m)
    col = _mix(col, wcol, inside * m)
    smooth = np.where(m & (inside > 0.5), 0.55, np.where(m & (crust > 0.5), 0.30, smooth))
    return col, smooth


def paint(D, variant='grey'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    R = {k: _c(v) for k, v in ROT.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    on_jaw = D['on_jaw'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    Pu = Z.hw_inv(P)
    x, y, z = Pu[:, 0], Pu[:, 1], Pu[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    fur = (part == PART['fur']) | (part == PART['jaw'])
    furb = part == PART['fur']
    F = Z.fur_flow(P, N)

    n_big = fbm(Pu * 6.0, 3, seed=11)
    n_mid = fbm(Pu * 18.0, 3, seed=12)
    n_fine = fbm(Pu * 55.0, 2, seed=13)
    s1 = _streaks(Pu, F, 21)                                      # fine strokes
    s2 = _streaks(Pu, F, 22, across=0.022, length=0.07)           # clumps
    s3 = _streaks(Pu, F, 24, across=0.026, length=0.16, steps=9)  # matted locks

    # ------------------------------------------------------------ the coat: the wolf's layout, dull and dirty
    col = np.tile(C['side'], (n, 1)).astype(float)
    col = _mix(col, C['buff'], 0.40 + 0.35 * n_big)
    head = smoothstep(-0.64, -0.68, y)
    legs = smoothstep(0.44, 0.34, z) * (y < 0.46)
    tail = smoothstep(0.45, 0.50, y) * smoothstep(0.70, 0.66, z) * (ax < 0.12)
    back = smoothstep(0.15, 0.65, nz + 0.25 * n_mid + 0.18 * n_big) * smoothstep(0.58, 0.70, z)
    saddle = back * smoothstep(-0.62, -0.48, y) * (1 - tail) * (1 - head)
    col = _mix(col, C['saddle'], 0.85 * saddle)
    col = _mix(col, C['grizzle'], 0.35 * smoothstep(0.25, 0.7, s1) * (0.35 + 0.65 * saddle))
    belly = smoothstep(-0.05, -0.55, nz + 0.2 * n_mid)
    medial = smoothstep(0.085, 0.065, ax) * smoothstep(0.55, 0.35, z)
    throat = smoothstep(0.72, 0.62, z) * smoothstep(-0.42, -0.55, y) * smoothstep(-0.2, -0.7, N[:, 1] + 0.3 * nz)
    pale = np.clip(np.maximum.reduce([belly, medial * 0.9, throat]), 0, 1) * (1 - tail * 0.7)
    col = _mix(col, C['cream'], 0.75 * pale)
    col = _mix(col, C['tawny'], 0.6 * legs * (1 - medial) * (0.7 + 0.3 * n_mid))
    tail_top = smoothstep(0.1, 0.6, N[:, 1] + 0.5 * nz)
    col = _mix(col, C['saddle'], 0.6 * tail * tail_top)
    # dirt: muddy legs and paws, grime blotches all over, the belly caked
    dirt = smoothstep(0.05, 0.45, fbm(Pu * 9.0, 3, seed=31)) * 0.55
    dirt = np.maximum(dirt, 0.85 * smoothstep(0.20, 0.06, z) * (0.7 + 0.3 * n_mid))
    dirt = np.maximum(dirt, 0.5 * belly * smoothstep(-0.2, 0.3, n_mid))
    col = _mix(col, C['dirt'], dirt)
    # matted: dark partings between clumped locks, their crests a little lighter
    col = _mix(col, C['mark'], 0.38 * smoothstep(-0.04, -0.30, s3))
    col = _mix(col, C['grizzle'], 0.14 * smoothstep(0.12, 0.40, s3) * smoothstep(-0.3, 0.5, nz))

    # ------------------------------------------------------------ face
    fcol = _mix(np.tile(C['face'], (n, 1)), C['buff'], 0.3 + 0.15 * n_mid)
    forehead = smoothstep(0.84, 0.88, z) * smoothstep(-0.80, -0.74, y)
    fcol = _mix(fcol, C['saddle'], 0.4 * forehead)
    fcol = _mix(fcol, C['muzzle'], smoothstep(-0.78, -0.82, y) * smoothstep(0.02, 0.5, nz))
    fcol = _mix(fcol, C['cream'], 0.45 * smoothstep(-0.2, -0.6, nz) * smoothstep(-0.70, -0.76, y))   # under the jaw
    e_l = np.array(D['eyes']['eye_L'])
    ec = Z.hw_inv(e_l)
    dx, dy, dz = ax - ec[0], y - ec[1], z - ec[2]
    socket = np.exp(-(dx ** 2 + dy ** 2 + dz ** 2) / (2 * 0.021 ** 2))       # sunken, bruised, dark
    fcol = _mix(fcol, R['bruise'] * 0.7, 0.55 * smoothstep(0.25, 0.6, socket))
    fcol = _mix(fcol, C['mark'], 0.85 * smoothstep(0.55, 0.85, socket))
    tear = np.exp(-(((dz + 0.012 + 0.45 * (dy + 0.018))) / 0.005) ** 2) * (dy < 0.004) * (dy > -0.045) * (np.abs(dx) < 0.013)
    fcol = _mix(fcol, C['mark'], 0.6 * tear)
    col = np.where(fur[:, None], _mix(col, fcol, head), col)
    # ears: dark backs, grey-pink skin inside (bald)
    ear = smoothstep(0.915, 0.935, z) * (y > -0.73) * (y < -0.64)
    ear_front = smoothstep(-0.1, -0.5, N[:, 1])
    ecol = _mix(np.tile(C['tawny'], (n, 1)), C['saddle'], 0.5 + 0.3 * smoothstep(1.0, 1.03, z))
    ecol = _mix(ecol, R['skin2'] * 0.85, 0.8 * ear_front * smoothstep(1.02, 0.97, z))
    col = np.where(fur[:, None], _mix(col, ecol, ear), col)

    grain = 0.80 + 0.30 * s1 + 0.14 * s2
    col = col * grain[:, None]
    smooth = np.full(n, 0.06)

    # ------------------------------------------------------------ bald, rotting skin
    b = Z.bald(Pu, edge=(0.30, 0.62)) * furb
    scol = _mix(np.tile(R['skin'], (n, 1)), R['skin2'], 0.5 + 0.5 * n_mid)
    scol = _mix(scol, R['rot'], 0.35 * smoothstep(0.10, 0.55, fbm(Pu * 17.0, 3, seed=51)))
    scol = _mix(scol, R['bruise'], 0.38 * smoothstep(0.10, 0.65, fbm(Pu * 13.0, 3, seed=52)))
    vein = 1 - np.abs(fbm(Pu * 30.0, 3, seed=53))
    scol = _mix(scol, R['vein'], 0.40 * smoothstep(0.945, 0.99, vein))
    scol = scol * (0.86 + 0.20 * fbm(Pu * 70.0, 2, seed=54))[:, None]          # fine mottling
    scol = scol * (1 - 0.30 * tail)[:, None]                                    # the tail's end: a dark rat's tail
    # the fur thins out into the skin in strands round each patch (a hard edge read as a sticker)
    skin_w = smoothstep(0.30, 0.72, b + 0.35 * s1 + 0.15 * s2)
    col = _mix(col, C['mark'], 0.22 * smoothstep(0.0, 0.35, b) * (1 - skin_w))
    col = _mix(col, scol, skin_w)
    smooth = np.where(skin_w > 0.5, 0.22, smooth)

    # ribs down both flanks, the spine's processes, the hip points, pin bones and shoulder blades
    u = Z.rib_u(y, z)
    ph = u - np.round(u)
    ribz = (smoothstep(-0.41, -0.35, y) * smoothstep(0.03, -0.03, y) * smoothstep(0.45, 0.52, z) *
            smoothstep(0.71, 0.66, z) * smoothstep(0.05, 0.075, ax) * furb)
    hl, sh = _rib_shade(ph)
    k = ribz * (0.25 + 0.75 * skin_w)
    col = _mix(col, R['bone'] * 0.85, 0.32 * k * hl)
    col = _mix(col, R['crust'] * 0.6, 0.42 * k * sh)
    tz = Z.top_z(y)
    pv = (y + 0.36) / Z.SPINE_STEP
    pph = pv - np.round(pv)
    ridge = furb * smoothstep(-0.38, -0.34, y) * smoothstep(0.44, 0.40, y) * np.exp(-(x / 0.016) ** 2) * smoothstep(-0.03, -0.005, z - tz)
    col = _mix(col, R['bone'] * 0.8, 0.55 * ridge * np.exp(-(pph / 0.22) ** 2) * (0.4 + 0.6 * b))
    col = _mix(col, R['crust'] * 0.5, 0.45 * ridge * np.exp(-((np.abs(pph) - 0.5) / 0.14) ** 2))
    for s in (1, -1):
        for c, r in (((0.058, 0.285, float(Z.top_z(0.285)) - 0.004), (0.016, 0.022, 0.012)),
                     ((0.040, 0.474, 0.660), (0.014, 0.014, 0.014)),
                     ((0.100, -0.330, 0.690), (0.010, 0.016, 0.060))):
            g = np.exp(-0.5 * (((x - s * c[0]) / r[0]) ** 2 + ((y - c[1]) / r[1]) ** 2 + ((z - c[2]) / r[2]) ** 2))
            col = _mix(col, R['bone'] * 0.85, 0.5 * g * furb * (0.4 + 0.6 * b))

    # ------------------------------------------------------------ the wounds
    e, side = Z.wound_e(Pu)
    wm = side & furb
    col, smooth = _wound_colours(col, smooth, e, wm, R, n_mid, n_big, dent=D['aux'].ravel()[idx])
    c = Z.WOUND['c']
    drip = (smoothstep(0.30, 0.75, vnoise(np.stack([y * 80.0, x * 5.0, z * 2.5], -1), seed=61)) *
            smoothstep(c[2] - 0.03, c[2] - 0.06, z) * smoothstep(c[2] - 0.20, c[2] - 0.09, z) *
            smoothstep(Z.WOUND['ry'] * 0.95, Z.WOUND['ry'] * 0.5, np.abs(y - c[1])) * (e > 1.0))
    col = _mix(col, R['crust'], 0.8 * drip * wm)
    g, gside = Z.gash_e(Pu)
    col, smooth = _wound_colours(col, smooth, g * 1.0, gside & furb, R, n_mid, n_big, rim_w=0.08)

    # ------------------------------------------------------------ mouth, gums, blood
    # the drawn-back upper lip: a black edge, the gum showing under it down to the teeth's roots
    lz = Z.lip_z(y)
    side_m = (part == PART['fur']) & (y < -0.775) & (ax > 0.010)
    gum = side_m & (z < lz + 0.004) & (z > 0.776)
    lipl = side_m & (z >= lz + 0.004) & (z < lz + 0.009) & (nz < 0.6)
    col = np.where(gum[:, None], R['gum'] * (0.85 + 0.2 * n_fine)[:, None], col)
    col = np.where(lipl[:, None], np.tile(R['lip'], (n, 1)), col)
    smooth = np.where(gum, 0.40, smooth)
    palate = furb & (y < -0.785) & (y > -0.92) & (z < Z.LIP_UP + 0.004) & (nz < -0.3) & (ax < 0.03)
    col = np.where(palate[:, None], np.tile(R['palate'], (n, 1)), col)
    jawp = part == PART['jaw']
    inside = jawp & (nz > 0.45)
    jaw_gum = jawp & ~inside & (z > 0.783)                 # the lower lip pulled down off the teeth: bare gum
    col = np.where((inside | jaw_gum)[:, None], np.tile(R['gum'], (n, 1)), col)
    smooth = np.where(inside | jaw_gum, 0.40, smooth)
    # blood crusted round the mouth, the chin, and down the throat
    mouth_blood = (smoothstep(-0.85, -0.90, y) * smoothstep(0.81, 0.79, z) +
                   0.8 * smoothstep(-0.70, -0.66, y) * smoothstep(-0.52, -0.58, y) * smoothstep(0.035, 0.015, ax) *
                   smoothstep(0.66, 0.70, z) * smoothstep(0.80, 0.76, z))
    mouth_blood = mouth_blood * smoothstep(-0.1, 0.4, fbm(Pu * 30.0, 2, seed=63))
    col = _mix(col, R['crust'], 0.75 * mouth_blood * (fur & ~inside & ~gum & ~jaw_gum))
    # the torn ear's edges, crusted
    bE, TE, NE, SE, LE = Z._ear_frame(-1)
    rel = Pu - bE
    te, se = (rel @ TE) / LE, rel @ SE
    widthe = np.interp(te, (0.0, 0.39, 0.73, 1.0), (0.040, 0.032, 0.020, 0.008))
    on_ear = (x < -0.015) & (te > 0.25) & (np.abs(se) < widthe + 0.01) & (np.abs(rel @ NE) < 0.03) & furb
    tc, th, dep = Z.EAR_NOTCH
    torn = np.maximum(smoothstep(Z.EAR_TOP[0] - 0.10, Z.EAR_TOP[0] - 0.02, te),
                      (se > dep - 0.002) * smoothstep(th * 1.1, th * 0.6, np.abs(te - tc)))
    col = _mix(col, R['crust'], 0.85 * torn * on_ear)

    # ------------------------------------------------------------ the pieces
    nose = part == PART['nose']
    nose_soft = np.exp(-(((x) / 0.022) ** 2 + ((y + 0.955) / 0.016) ** 2 + ((z - 0.836) / 0.018) ** 2))
    ncol = R['nose'] * (0.8 + 0.35 * smoothstep(0.2, 0.6, n_fine))[:, None]       # dry, cracked
    col = _mix(col, ncol, np.maximum(nose.astype(float), smoothstep(0.35, 0.6, nose_soft)))
    smooth = np.where(nose | (nose_soft > 0.6), 0.18, smooth)
    tongue = part == PART['tongue']
    tcol = _mix(np.tile(R['tongue'], (n, 1)), R['tongue_dark'], 0.5 * smoothstep(0.004, 0.0, ax) + 0.4 * smoothstep(0.3, -0.3, nz))
    col = np.where(tongue[:, None], tcol, col)
    smooth = np.where(tongue, 0.40, smooth)
    tooth = part == PART['tooth']
    root = np.where(on_jaw, smoothstep(0.790, 0.782, z), smoothstep(0.790, 0.800, z))
    tc_ = _mix(np.tile(R['tooth'], (n, 1)), R['tooth_root'], root)
    tc_ = _mix(tc_, R['tooth_root'], 0.35 * smoothstep(0.1, 0.6, n_fine))         # grime
    col = np.where(tooth[:, None], tc_, col)
    smooth = np.where(tooth, 0.40, smooth)
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c_ = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            t = np.array((0, 1, 0.35))
            t = t - nv * t.dot(nv)
            t /= np.linalg.norm(t)
            bb = np.cross(nv, t)
            d = P - c_
            uu = (d @ t) / (1.30 * Z.EYE_R)
            vv = (d @ bb) / (0.80 * Z.EYE_R)
            r = np.sqrt(uu * uu + vv * vv)
            ci = np.tile(R['eye'], (n, 1))                                  # milky: a clouded iris, no pupil to speak of
            ci = _mix(ci, R['eye_dim'], 0.35 * np.exp(-((r - 0.48) / 0.12) ** 2))
            ci = _mix(ci, R['eye_dim'] * 0.8, 0.25 * smoothstep(0.24, 0.12, r))
            ci = _mix(ci, R['lip'], smoothstep(0.80, 0.92, r))
            hl = np.exp(-(((uu + 0.25) / 0.12) ** 2 + ((vv - 0.30) / 0.12) ** 2))
            ci = _mix(ci, np.ones(3), 0.6 * hl)
            sel = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(sel[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.55, smooth)
    bone = part == PART['bone']
    if bone.any():
        eb, _ = Z.wound_e(Pu)
        bcol = _mix(np.tile(R['bone'], (n, 1)), R['bone_dark'], 0.30 * smoothstep(0.0, 0.6, n_fine))
        bcol = _mix(bcol, R['bone_dark'], smoothstep(0.70, 0.92, eb))              # stained going into the flesh
        bcol = _mix(bcol, R['wet'], 0.6 * smoothstep(0.82, 0.98, eb))
        col = np.where(bone[:, None], bcol, col)
        smooth = np.where(bone, 0.25, smooth)
    pads = fur & (z < 0.012) & (nz < -0.6)
    col = np.where(pads[:, None], np.tile(R['pad'], (n, 1)), col)
    claw = fur & (z < 0.03) & (nz > -0.3) & (-N[:, 1] > 0.5)
    col = _mix(col, R['claw'], 0.7 * claw)

    # ------------------------------------------------------------ painted light (the wolf's)
    light = 0.76 + 0.34 * (nz * 0.5 + 0.5)
    aot = 0.42 + 0.58 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.08)[:, None] * np.array([0.25, 0.2, 0.35])
    shaded = np.where(eye[:, None], col * (0.92 + 0.08 * aot[:, None]), shaded)

    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("grey", "dark", "pale")):
    """T_ZombieWolf (grey), T_ZombieWolf_Dark, T_ZombieWolf_Pale; the material M_ZombieWolf (the first)."""
    D = bake_data(ob, size=size)
    paths = []
    for i, v in enumerate(variants):
        col, smooth = paint(D, v)
        name = "T_ZombieWolf" if i == 0 else "T_ZombieWolf_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if i == 0 else None, "M_ZombieWolf"))
    m = bpy.data.materials.get("M_ZombieWolf")
    if m is not None:                               # Workbench sheets: matte, like the deer's (the BSDF is untouched)
        m.roughness, m.specular_intensity, m.metallic = 1.0, 0.0, 0.0
    return paths, float(D['valid'].mean())
