"""UVs and the painted hide of the giant bat (the framework is beast_paint.py), 2026-10-23.

UVs: the fur body is cut along the belly and throat and under the chin (the regions come from the skin weights:
head, trunk, the thigh stumps); the lofts, cones, ears and eyes keep the seams their builders marked; each membrane
patch is its own island, at about half the body's texel density. One 1024 texture for all of it (the wings are
split into their own object after painting only to get a two-sided material).

Paint (my calls): dark brown-black fur lying back along the body, grizzled, with a rusty mantle over the neck and
shoulders and a greyer belly; the bare face dark grey-brown, the pug nose pad near-black with pink nostrils, a dark
nose leaf; the ears dark leather outside, pinkish inside with the cross ridges of a bat's ear; the wings dark
leather, near-black along the arm and fingers, lighter and redder toward the trailing edge where the membrane is
thin, with veins branching off the bones and fine creases along the fingers; ivory fangs, a dark red mouth, black
eyes with a red glint, dark claws with pale tips.
"""
import numpy as np
import beast_paint as BP
from beast_common import smoothstep, fbm, vnoise
from beast_paint import _c, _mix, _streaks, bake_data, write_texture
from beast_body import PART
import bat_body as BB

H = BB.H


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return z < H - 0.005, x > 0
    if region == 'head':
        return z < H + 0.030 and y > -0.40, x > 0
    if region.startswith('hleg'):
        return True, z > H - 0.03
    return None


UV_SCALE = {'head': 2.3, 'eye': 2.4, 'ear': 1.1, 'jaw': 1.5, 'tooth': 0.7, 'claw': 0.5, 'bone': 0.35,
            'membrane': 0.5}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


FUR = dict(back='#211915', grizzle='#5a4838', side='#2c221c', belly='#3e342e', mantle='#5a3220',
           mantle_tip='#8a5634')
SKIN = dict(face='#4a3832', face_dark='#2a1e1b', nose='#140e0e', nostril='#7a4a48', leaf='#2a1e1c',
            ear_out='#2a201e', ear_in='#6a4a46', ear_ridge='#402c2a', leather='#2e2422', leather_thin='#5a3a32',
            leather_red='#6e3a2e', vein='#1a1212', bone='#1e1715', knuckle='#3a2e2a', claw='#161212',
            claw_tip='#7a7064', tooth='#e8dcc0', tooth_root='#a89466', mouth='#5a1e1e', mouth_dark='#2a0e0e',
            gum='#4a1a1e', pupil='#060404', iris='#7a1208', glint='#f0d8c8')


def _seg_dist(P, a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    u = np.clip(((P - a) @ d) / (d @ d), 0, 1)
    return np.linalg.norm(P - (a + u[:, None] * d), axis=1), u


def _wing_lines(P):
    """For membrane texels (rest positions): the distance to the nearest bone (arm, fingers, flank and leg) and how
    far toward the free edge they lie (0 on a bone .. 1 far from all of them)."""
    B = BB.rest_bones()
    segs = []
    for s, sfx in BB.SIDES:
        names = ["WingArm", "WingForearm", "WingHand", "WingThumb"]
        for i in range(len(BB.SEGS)):
            names += [f"WingF{i + 1}_{k + 1}" for k in range(BB.SEGS[i])]
        for n in names:
            h, fr, L, par, d = B[n + sfx]
            segs.append((np.array(h), np.array(h + fr.col[1] * L)))
        fl = [np.array(BB.DB._m(p, s)) for p in BB.FLANK]
        segs += list(zip(fl[:-1], fl[1:]))
    best = np.full(len(P), 9.0)
    for a, b in segs:
        d, _ = _seg_dist(P, a, b)
        best = np.minimum(best, d)
    return best


def paint(D):
    S = {k: _c(v) for k, v in SKIN.items()}
    Fc = {k: _c(v) for k, v in FUR.items()}
    valid = D['valid']
    Hh, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2] - H
    ax = np.abs(x)
    n = len(P)
    nz = N[:, 2]
    furp = part == PART['fur']
    F = BB.fur_flow(P, N)
    s1 = _streaks(P, F, 51, across=0.0035, length=0.022, steps=7)
    s2 = _streaks(P, F, 52, across=0.0080, length=0.040, steps=5)
    big = fbm(P * 9.0, 3, seed=53)

    # ---- fur: dark back, greyer belly, the rusty mantle, grizzled strokes
    col = np.tile(Fc['back'], (n, 1))
    belly = smoothstep(0.1, -0.6, nz) * smoothstep(0.04, -0.04, z)
    col = _mix(col, Fc['side'], 0.6 * smoothstep(0.3, -0.2, nz))
    col = _mix(col, Fc['belly'], 0.75 * belly)
    mantle = (smoothstep(-0.06, -0.14, y) * smoothstep(-0.30, -0.24, y) * smoothstep(-0.03, 0.02, z) *
              (0.75 + 0.25 * big))
    col = _mix(col, Fc['mantle'], 0.85 * mantle)
    col = _mix(col, Fc['mantle_tip'], 0.45 * mantle * smoothstep(0.1, 0.6, s1))
    crown = smoothstep(-0.24, -0.30, y) * smoothstep(0.04, 0.08, z)
    col = _mix(col, Fc['grizzle'], (0.42 + 0.25 * crown) * smoothstep(0.15, 0.70, s1) * (1 - mantle) * (1 - belly * 0.5))
    col = col * (0.78 + 0.30 * s2 + 0.05 * big)[:, None]

    # ---- the bare face
    face = BB._face(P)
    fc = _mix(np.tile(S['face'], (n, 1)), S['face_dark'], 0.5 * smoothstep(-0.40, -0.44, y))
    col = _mix(col, fc, face * furp)
    nose = smoothstep(0.030, 0.018, np.linalg.norm((P - np.array(BB.h(0, -0.437, 0.049))) / (1.0, 0.6, 0.8), axis=1))
    col = _mix(col, S['nose'], nose * furp)
    for sx in (1, -1):
        no = np.linalg.norm(P - np.array(BB.h(sx * 0.011, -0.447, 0.050)), axis=1)
        col = _mix(col, S['nostril'], 0.8 * smoothstep(0.0065, 0.0035, no) * furp)
    leaf = smoothstep(0.016, 0.009, np.linalg.norm((P - np.array(BB.h(0, -0.429, 0.079))) / (1.0, 0.45, 1.6), axis=1))
    col = _mix(col, S['leaf'], leaf * furp)
    # the eyes' sockets dark, the lip line dark
    for sfx in ('L', 'R'):
        e = np.array(D['eyes']['eye_' + sfx])
        de = np.linalg.norm(P - e, axis=1)
        col = _mix(col, S['face_dark'], 0.7 * smoothstep(0.030, 0.016, de) * furp)
    lip = furp * smoothstep(0.012, 0.004, np.abs(z - 0.004)) * smoothstep(-0.31, -0.34, y)
    col = _mix(col, S['mouth_dark'], 0.7 * lip)
    under = furp * smoothstep(-0.002, -0.010, z) * smoothstep(-0.33, -0.36, y) * smoothstep(0.042, 0.030, ax)
    col = _mix(col, S['mouth'], 0.8 * under)        # the palate, seen when the jaw opens
    smooth = np.full(n, 0.14)
    smooth = np.where(furp, 0.12 + 0.20 * face + 0.35 * nose, smooth)

    # ---- ears: leather outside, pink with ridges inside (the hollow faces forward)
    ear = part == PART['ear']
    if ear.any():
        Eb = np.array(BB.EAR_BASE)
        t_up = np.clip((z - (Eb[2] - H)) / 0.23, 0, 1)
        inside = smoothstep(0.1, -0.5, N[:, 1])
        ridge = 0.5 + 0.5 * np.sin(t_up * 2 * np.pi * 9)
        ec = _mix(np.tile(S['ear_out'], (n, 1)), S['ear_in'], 0.8 * inside * smoothstep(0.0, 0.25, t_up))
        ec = _mix(ec, S['ear_ridge'], 0.45 * inside * smoothstep(0.55, 0.95, ridge))
        ec = _mix(ec, S['ear_out'], smoothstep(0.85, 1.0, t_up))
        col = np.where(ear[:, None], ec, col)
        smooth = np.where(ear, 0.30, smooth)

    # ---- membranes and the bones in them
    mem = part == PART['membrane']
    if mem.any():
        dist = np.full(n, 9.0)
        dist[mem] = _wing_lines(P[mem])
        thin = smoothstep(0.02, 0.16, dist)
        vein_n = np.abs(fbm(P * np.array((14.0, 14.0, 14.0)), 3, seed=57))
        veins = smoothstep(0.06, 0.0, vein_n) * smoothstep(0.01, 0.05, dist) * smoothstep(0.30, 0.10, dist)
        crease = 0.5 + 0.5 * np.sin(vnoise(P * 6.0, seed=58) * 3 + (x * 0.6 + y) * 90.0)
        mc = _mix(np.tile(S['leather'], (n, 1)), S['leather_thin'], 0.75 * thin)
        mc = _mix(mc, S['leather_red'], 0.35 * thin * (0.6 + 0.4 * big))
        mc = _mix(mc, S['vein'], 0.55 * veins)
        mc = mc * (0.90 + 0.10 * crease * thin)[:, None]
        mc = _mix(mc, S['bone'], 0.6 * smoothstep(0.03, 0.008, dist))
        col = np.where(mem[:, None], mc, col)
        smooth = np.where(mem, 0.30 + 0.08 * (1 - thin), smooth)
    bone = part == PART['bone']
    if bone.any():
        knob = 0.5 + 0.5 * vnoise(P * 60.0, seed=59)
        bc = _mix(np.tile(S['bone'], (n, 1)), S['knuckle'], 0.30 * smoothstep(0.6, 0.9, knob))
        col = np.where(bone[:, None], bc, col)
        smooth = np.where(bone, 0.30, smooth)
    claw = part == PART['claw']
    if claw.any():
        cc = _mix(np.tile(S['claw'], (n, 1)), S['claw_tip'], 0.55 * smoothstep(0.4, 0.9, vnoise(P * 80, seed=60) * 0.3 + 0.6))
        col = np.where(claw[:, None], cc, col)
        smooth = np.where(claw, 0.45, smooth)
    tooth = part == PART['tooth']
    if tooth.any():
        root = smoothstep(0.004, 0.016, np.abs(z - 0.004))
        tc = _mix(np.tile(S['tooth_root'], (n, 1)), S['tooth'], root)
        col = np.where(tooth[:, None], tc, col)
        smooth = np.where(tooth, 0.55, smooth)
    jaw = part == PART['jaw']
    if jaw.any():
        top = smoothstep(0.35, 0.75, nz)
        jaw_half = np.interp(y, (-0.416, -0.392, -0.350, -0.300), (0.014, 0.025, 0.033, 0.038))
        inner = top * smoothstep(0.85, 0.60, ax / np.maximum(jaw_half, 1e-3))
        jc = _mix(np.tile(S['face'], (n, 1)), S['face_dark'], 0.6 * smoothstep(0.2, -0.6, nz))
        jc = _mix(jc, S['mouth'], inner)
        jc = _mix(jc, S['gum'], 0.7 * top * (1 - inner) * smoothstep(0.3, 0.6, nz))
        col = np.where(jaw[:, None], jc, col)
        smooth = np.where(jaw, 0.30 + 0.2 * top, smooth)
    eye = part == PART['eye']
    if eye.any():
        ec = np.tile(S['pupil'], (n, 1))
        for sfx, sx in (('L', 1), ('R', -1)):
            c = np.array(D['eyes']['eye_' + sfx])
            n_eye = np.array(BB.EYE_N) * np.array((sx, 1, 1))
            n_eye /= np.linalg.norm(n_eye)
            gl = c + n_eye * 0.007 + np.array((0, -0.002, 0.006))
            g = smoothstep(0.0028, 0.0010, np.linalg.norm(P - gl, axis=1))
            r = np.linalg.norm(P - c, axis=1)
            e2 = _mix(np.tile(S['iris'], (n, 1)), S['pupil'], smoothstep(0.0060, 0.0045, r))
            e2 = _mix(e2, S['pupil'], smoothstep(0.0120, 0.0150, r))
            e2 = _mix(e2, S['glint'], 0.85 * g)
            side = (x > 0) if sx > 0 else (x <= 0)
            ec = np.where(side[:, None], e2, ec)
        col = np.where(eye[:, None], ec, col)
        smooth = np.where(eye, 0.92, smooth)

    light = 0.86 + 0.20 * (nz * 0.5 + 0.5)
    aot = 0.55 + 0.45 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None]
    shaded = np.where((eye | mem)[:, None], col * (0.80 + 0.20 * aot)[:, None], shaded)
    out = np.zeros((Hh * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(Hh * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(Hh, Wd, 3), sm.reshape(Hh, Wd)


def build_texture(ob, size=1024):
    """T_Bat (RGB colour, A smoothness) and the material M_Bat."""
    import bpy, deer_paint
    D = bake_data(ob, size=size, ao_dist=0.12)
    col, smooth = paint(D)
    path = write_texture(D, col, smooth, "T_Bat", ob, "M_Bat")
    deer_paint.matte(bpy.data.materials["M_Bat"])
    return [path], float(D['valid'].mean())
