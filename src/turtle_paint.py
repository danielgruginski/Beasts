"""UVs and the painted hide and shell of the giant turtle (the framework is beast_paint.py), 2026-10-23.

UVs: the skin is cut under the belly, neck and chin, down the inside of each leg and under the tail (regions from
the skin weights); the core under the shell is packed small (it barely shows). The carapace unwraps as one disc
(its builder cuts round the rim), the lip and inner dome as a strip, the plastron in halves.

Paint (my calls): the carapace dark olive-brown, each scute outlined by a dark groove with growth rings inside, the
keels' knobs worn paler, moss in the hollows and over the top, pale lichen and barnacle crusts toward the rim, mud
on the lower edge; the plastron dull yellow with dark seams; the skin dark olive-grey with a mottled head, a paler
yellowish throat and underside, scales on the legs, mud on the feet; a dark horn beak with paler cutting edges; a
pink mouth with the snapper's worm-like lure on the tongue; amber eyes with a dark star round the pupil.
"""
import math
import numpy as np
import beast_paint as BP
from beast_common import smoothstep, fbm, vnoise
from beast_paint import _c, _mix, bake_data, write_texture
from beast_body import PART
import turtle_body as TB


def _axis(rows, z):
    """x, y of a leg's axis at height z (rows top to bottom)."""
    zs = np.array([r[2] for r in rows])[::-1]
    return float(np.interp(z, zs, [r[0] for r in rows][::-1])), float(np.interp(z, zs, [r[1] for r in rows][::-1]))


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return z < 0.86, x > 0
    if region == 'head':
        return z < 0.80, x > 0
    if region.startswith('fleg'):
        ax, ay = _axis(TB.FLEG, z)
        return abs(x) < ax, y > ay
    if region.startswith('hleg'):
        ax, ay = _axis(TB.HLEG, z)
        return abs(x) < ax, y > ay
    if region == 'tail':
        return True, x > 0
    return None


UV_SCALE = {'head': 1.8, 'eye': 2.0, 'jaw': 1.4, 'shell': 1.15, 'claw': 0.5, 'trunk': 0.45, 'fleg': 0.9,
            'hleg': 0.9, 'tail': 0.8}
HIDDEN_K = {0.25: 0.12, 0.5: 0.45}                 # the inner dome (never seen), the plastron and bridges (from below)


def unwrap(ob, margin=0.003, relax=40):
    aux = TB.shell_aux(ob)
    fk = [HIDDEN_K.get(round(float(max(aux[v] for v in p.vertices)), 2), 1.0) for p in ob.data.polygons]
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax, island_scale=lambda i: fk[i])


C = dict(shell='#3a3424', shell_dark='#231f15', shell_light='#5e5536', groove='#15120c', knob='#7a6e4c',
         moss='#4a5a22', moss_dark='#2e3a14', lichen='#8a8e72', barnacle='#c8c2ae', mud='#4a3b28',
         plastron='#a08c52', plastron_seam='#4a3e22', skin='#4a4a36', skin_dark='#2b2b1e', skin_light='#6e6a48',
         throat='#9a8e5a', beak='#2c2720', beak_edge='#6e6450', mouth='#8a5a58', mouth_dark='#4a2a2a',
         lure='#d07a7c', claw='#2a241c', claw_tip='#5e5444', iris='#9a7a2a', pupil='#0a0806', star='#2a1e0a')


def _shell_fields(P):
    """For carapace texels: the outline angle and radial fraction (0 apex .. 1 rim), and a scute id and the
    distance to the nearest scute border (m), the scutes laid out like a turtle's: five vertebrals down the middle,
    four costals a side between staggered borders, marginals round the rim."""
    S = TB.SHELL
    ax, ay = S['apex'][0], S['apex'][1]
    x, y = P[:, 0], P[:, 1]
    phi = np.arctan2(x - ax, -(y - ay)) % (2 * np.pi)
    rim = np.array([TB._rim_xy(p) for p in np.linspace(0, 2 * np.pi, 361)])
    k = np.clip((phi / (2 * np.pi) * 360).astype(int), 0, 359)
    rd = np.hypot(rim[k, 0] - ax, rim[k, 1] - ay)
    r = np.hypot(x - ax, y - ay) / np.maximum(rd, 1e-6)
    ax_ = np.abs(x)
    vb = 0.24 + 0.05 * np.cos(np.clip(y / 1.2, -1, 1) * np.pi)            # the vertebrals' half width: widest mid-shell
    # vertebral borders: chevrons pointing forward; costal borders fan out from the vertebrals toward the rim
    yv = np.array(TB.SCUTE_Y)
    bv = (yv[:-1] + yv[1:]) / 2
    bc = np.array([-0.58, -0.14, 0.30, 0.72])
    kc = np.array([-0.55, -0.18, 0.18, 0.55])
    d_border = np.full(len(P), 9.0)
    sid = np.zeros(len(P), int)
    mar = r > 0.80
    d_border = np.minimum(d_border, np.abs(r - 0.80) * 1.1)                  # marginals' inner border
    vert = (ax_ < vb) & ~mar
    cost = (ax_ >= vb) & ~mar
    for b in bv:
        d_border = np.where(vert, np.minimum(d_border, np.abs(y - (b + 0.25 * ax_)) / 1.03), d_border)
    for b, kk in zip(bc, kc):
        d = np.abs(y - (b + kk * (ax_ - vb))) / math.sqrt(1 + kk * kk)
        d_border = np.where(cost, np.minimum(d_border, d), d_border)
    d_border = np.where(~mar, np.minimum(d_border, np.abs(ax_ - vb)), d_border)
    nm = 24                                                                  # marginals: radial borders
    seg = phi / (2 * np.pi) * nm
    dm = np.abs(seg - np.round(seg)) * (2 * np.pi / nm) * rd
    d_border = np.where(mar, np.minimum(d_border, dm), d_border)
    sid = np.where(vert, np.searchsorted(bv, y) + 1, sid)
    yc = y - kc[np.clip(np.searchsorted(bc, y), 0, 3)] * (ax_ - vb)
    sid = np.where(cost, 10 + np.searchsorted(bc, yc) + 20 * (x > 0), sid)
    sid = np.where(mar, 100 + np.floor(seg + 0.5).astype(int) % nm, sid)
    return phi, r, sid, d_border


def paint(D):
    Cc = {k: _c(v) for k, v in C.items()}
    valid = D['valid']
    Hh, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    n = len(P)
    nz = N[:, 2]
    big = fbm(P * 2.2, 3, seed=81)
    mid = fbm(P * 7.0, 3, seed=82)
    fine = fbm(P * 30.0, 2, seed=83)
    col = np.zeros((n, 3))
    smooth = np.full(n, 0.12)

    # ---- the shell
    shell = part == PART['shell']
    aux = D['aux'].ravel()[idx]
    plast = shell & (aux > 0.4) & (ax < 0.78)
    bridge = shell & (aux > 0.4) & ~plast
    cara = shell & (aux < 0.4)
    if cara.any():
        phi, r, sid, db = _shell_fields(P)
        top = cara & (nz > -0.2)
        rnd = np.array([(math.sin(s * 12.9898) * 43758.5453) % 1.0 for s in range(200)])
        tone = rnd[np.clip(sid, 0, 199)]
        sc = _mix(np.tile(Cc['shell'], (n, 1)), Cc['shell_dark'], 0.35 * tone + 0.25 * smoothstep(0.2, 0.7, big))
        rings = 0.5 + 0.5 * np.sin(db * 2 * np.pi / 0.045 + 3.0 * mid)
        sc = _mix(sc, Cc['shell_light'], 0.14 * smoothstep(0.7, 0.95, rings) * smoothstep(0.03, 0.10, db))
        groove = smoothstep(0.022, 0.006, db + 0.004 * fine)
        sc = _mix(sc, Cc['groove'], 0.85 * groove)
        relief = TB.relief_np(x, y, np.clip(r, 0, 1))
        sc = _mix(sc, Cc['knob'], 0.55 * smoothstep(0.06, 0.11, relief) * top)
        moss = top * smoothstep(0.05, 0.45, fbm(P * 3.5, 3, seed=84) + 0.25 * (1 - r)) * (1 - 0.6 * groove)
        moss_c = _mix(np.tile(Cc['moss'], (n, 1)), Cc['moss_dark'], smoothstep(-0.3, 0.6, fine))
        sc = _mix(sc, moss_c, 0.85 * moss)
        crust = top * smoothstep(0.62, 0.95, r) * smoothstep(0.30, 0.60, fbm(P * 5.0, 2, seed=85))
        dots = smoothstep(0.62, 0.80, vnoise(P * 90.0, seed=86)) * smoothstep(0.1, 0.5, fbm(P * 20.0, 2, seed=89))
        sc = _mix(sc, Cc['lichen'], 0.35 * crust)
        sc = _mix(sc, Cc['barnacle'], 0.75 * crust * dots)
        low = cara & ((nz < -0.2) | (z < 0.70))
        sc = _mix(sc, Cc['mud'], 0.55 * smoothstep(0.85, 0.60, z) * (0.6 + 0.4 * big))
        sc = _mix(sc, Cc['shell_dark'], 0.5 * low)
        col = np.where(cara[:, None], sc, col)
        smooth = np.where(cara, 0.18 + 0.15 * groove - 0.1 * moss, smooth)
    if (plast | bridge).any():
        seams_y = np.abs(((y + 0.98) / 0.40) % 1.0 - 0.5) * 0.40
        pc = _mix(np.tile(Cc['plastron'], (n, 1)), Cc['mud'], 0.35 + 0.3 * smoothstep(0.0, 0.6, big))
        pc = _mix(pc, Cc['plastron_seam'], 0.8 * (smoothstep(0.018, 0.006, ax) + smoothstep(0.016, 0.006, seams_y)))
        col = np.where((plast | bridge)[:, None], pc, col)
        smooth = np.where(plast | bridge, 0.2, smooth)

    # ---- the skin
    skin = part == PART['fur']
    if skin.any():
        sk = _mix(np.tile(Cc['skin'], (n, 1)), Cc['skin_dark'], 0.45 * smoothstep(-0.1, 0.6, mid))
        scales = smoothstep(0.15, 0.55, vnoise(P * 34.0, seed=87))
        sk = _mix(sk, Cc['skin_light'], 0.30 * scales)
        sk = _mix(sk, Cc['skin_dark'], 0.25 * (1 - scales) * smoothstep(0.3, 0.7, fine + 0.5))
        under = smoothstep(0.0, -0.6, nz) * smoothstep(0.95, 0.80, z) * smoothstep(-0.6, -0.9, y)
        sk = _mix(sk, Cc['throat'], 0.65 * under)
        head = smoothstep(-1.42, -1.52, y)
        mott = smoothstep(0.25, 0.55, fbm(P * 18.0, 2, seed=88))
        sk = _mix(sk, Cc['skin_dark'], 0.45 * head * mott)
        sk = _mix(sk, Cc['mud'], 0.6 * smoothstep(0.30, 0.05, z) * (0.6 + 0.4 * big))
        # the upper beak: horn from the face forward, below the nostrils' line, its cutting edge paler
        beak = smoothstep(-1.80, -1.86, y) * (z < 0.90 + 0.25 * (y + 1.86))
        sk = _mix(sk, Cc['beak'], 0.9 * beak)
        edge = beak * smoothstep(0.80, 0.78, z)
        sk = _mix(sk, Cc['beak_edge'], 0.6 * edge)
        lipline = beak * smoothstep(0.775, 0.765, z) * (nz < 0.2)
        sk = _mix(sk, Cc['pupil'], 0.6 * lipline)
        palate = smoothstep(-1.55, -1.62, y) * smoothstep(0.80, 0.77, z) * smoothstep(0.16, 0.10, ax) * (nz < -0.3)
        sk = _mix(sk, Cc['mouth_dark'], 0.8 * palate)
        for sx in (1, -1):                                   # nostrils at the snout's tip
            d = np.linalg.norm(P - np.array((sx * 0.022, -2.015, 0.875)), axis=1)
            sk = _mix(sk, Cc['pupil'], smoothstep(0.016, 0.009, d))
        col = np.where(skin[:, None], sk, col)
        smooth = np.where(skin, 0.14 + 0.2 * beak, smooth)
    jaw = part == PART['jaw']
    if jaw.any():
        topj = smoothstep(0.3, 0.7, nz)
        half = np.interp(y, (-1.985, -1.90, -1.74, -1.56, -1.47), (0.034, 0.088, 0.142, 0.168, 0.12))
        inner = topj * smoothstep(0.62, 0.42, ax / np.maximum(half, 1e-3))
        horn = smoothstep(-1.80, -1.87, y)              # the lower beak's horn in front; skin behind it
        jskin = _mix(np.tile(Cc['skin'], (n, 1)), Cc['skin_dark'], 0.5 * smoothstep(0.25, 0.55, fbm(P * 18.0, 2, seed=88)))
        jskin = _mix(jskin, Cc['throat'], 0.5 * smoothstep(0.0, -0.7, nz))
        jc = _mix(jskin, Cc['beak'], horn)
        jc = _mix(jc, Cc['mouth_dark'], 0.8 * topj * (1 - inner) * smoothstep(0.85, 0.62, ax / np.maximum(half, 1e-3)))
        jc = _mix(jc, Cc['beak_edge'], 0.4 * topj * smoothstep(0.70, 0.90, ax / np.maximum(half, 1e-3)) * horn)
        jc = _mix(jc, Cc['mouth'], inner)
        lure = smoothstep(0.030, 0.012, np.hypot(x * 1.6, y + 1.80))   # the worm-like lure on the tongue
        jc = _mix(jc, Cc['lure'], inner * lure)
        col = np.where(jaw[:, None], jc, col)
        smooth = np.where(jaw, 0.3 + 0.25 * inner, smooth)
    claw = part == PART['claw']
    if claw.any():
        cc = _mix(np.tile(Cc['claw'], (n, 1)), Cc['claw_tip'], 0.6 * smoothstep(0.045, 0.015, z))
        col = np.where(claw[:, None], cc, col)
        smooth = np.where(claw, 0.35, smooth)
    eye = part == PART['eye']
    if eye.any():
        ec = np.zeros((n, 3))
        for sfx, sx in (('L', 1), ('R', -1)):
            c = np.array(D['eyes']['eye_' + sfx])
            ne = np.array(TB.EYE_N) * np.array((sx, 1, 1))
            ne /= np.linalg.norm(ne)
            v = P - c
            v = v - (v @ ne)[:, None] * ne
            rr = np.linalg.norm(v, axis=1) / TB.EYE_R
            ang = np.arctan2(v[:, 2], v[:, 1])
            star = smoothstep(0.55, 0.85, np.abs(np.cos(2 * ang))) * smoothstep(0.85, 0.3, rr)
            e2 = _mix(np.tile(Cc['iris'], (n, 1)), Cc['star'], 0.75 * star)
            e2 = _mix(e2, Cc['pupil'], smoothstep(0.30, 0.22, rr))
            e2 = _mix(e2, Cc['skin_dark'], smoothstep(0.85, 1.0, rr))
            side = (x > 0) if sx > 0 else (x <= 0)
            ec = np.where(side[:, None], e2, ec)
        col = np.where(eye[:, None], ec, col)
        smooth = np.where(eye, 0.9, smooth)

    light = 0.84 + 0.22 * (nz * 0.5 + 0.5)
    aot = 0.55 + 0.45 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None]
    shaded = np.where(eye[:, None], col, shaded)
    out = np.zeros((Hh * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(Hh * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(Hh, Wd, 3), sm.reshape(Hh, Wd)


def build_texture(ob, size=1024):
    import bpy, deer_paint
    D = bake_data(ob, size=size, ao_dist=0.35)
    col, smooth = paint(D)
    path = write_texture(D, col, smooth, "T_Turtle", ob, "M_Turtle")
    deer_paint.matte(bpy.data.materials["M_Turtle"])
    return [path], float(D['valid'].mean())
