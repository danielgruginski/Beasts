"""UVs and the painted coat of the red deer stag (the framework is beast_paint.py), 2026-10-11.

UV cuts: along the underside of the belly, chest, neck and throat and up under the tail, under the jaw, inside the
legs (the grafted lower legs are part of the fused body: each leg is one island with its shoulder or haunch); the
shells (jaw, eyes, ears, hooves, antlers) keep the seams their builders marked. The fused body opens like a hide.

Coat 'red' (autumn): grey-brown flanks, russet over the back, a faint darker line down the spine, the neck dark
grey-brown and the mane darker in long locks (paler tips, dark partings: the texture carries its shagginess), the
belly, inner legs and the rump patch cream to buff (the patch edged darker above, the tail's upper side dark), darker
lower legs, a grey-brown face with a pale ring round the eye, a dark preorbital gland, a dark muzzle and black nose
pad, a pale chin, ears pale inside with dark rims, dark hooves; antlers brown and grooved, darker at the burr, the
tines' tips worn pale. Strands follow deer_body.fur_flow. The material is matte (`matte`).
"""
import bpy
import numpy as np
from beast_common import smoothstep, fbm, vnoise
import deer_body as DB
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture, polyline_t
from beast_body import PART


def _neck_z(y):
    return float(np.interp(-y, [-r[1] for r in DB.NECK], [r[2] for r in DB.NECK]))


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':                                  # belly, chest, neck and throat, up under the tail
        return (z < 0.80) or (y > 0.64 and z < 1.02) or (y < -0.55 and z < _neck_z(y)), x > 0
    if region == 'head':                                   # under the jaw (head space)
        h = DB.hx_inv(np.array(c))
        return h[2] < -0.10 and abs(x) < 0.10, x > 0
    if region == 'tail':                                   # the side against the rump
        return y < _interp_axis(z, DB.TAIL) + 0.005, x > 0
    j = DB.J
    if region.startswith('fleg'):
        return abs(x) < 0.15, y > _interp_axis(z, [j['SCAP'], j['SHO'], j['ELB'], j['WRI']])
    if region.startswith('hleg'):
        return abs(x) < 0.14, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


UV_SCALE = {'head': 1.6, 'ear': 1.3, 'eye': 2.0, 'nose': 1.6, 'jaw': 1.2, 'antler': 0.8, 'leg': 1.1, 'claw': 0.7,
            'hair': 0.8, 'tail': 1.0}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


def uv_layout(ob, name="uv_layout_deer", size=2048):
    return BP.uv_layout(ob, name, size)


COATS = {
    'red': dict(back='#8e5c3e', flank='#9a8068', light='#bba48c', neck='#6a5a4c', mane='#43362c', mane_tip='#8a7866',
                belly='#dccdb0', buff='#c2a684', rump='#e0cfad', edge='#33261c', legs='#4e3e32', face='#8e7a66',
                muzzle='#2d241e', chin='#e0d6c4', iris='#22140a', tail='#5e4432'),
}
MISC = dict(nose='#121010', lip='#1a1614', mouth='#4e2c2c', hoof='#1d1916', hoof_light='#4c443c', antler='#76603f',
            antler_dark='#3a2c1d', antler_tip='#e8dec6', pupil='#050404', ear_in='#d8ccb6')


def _tube_t(P, rows):
    """Arc position 0..1 along an antler tube, the distance to its centre line and the direction it runs there."""
    Q = np.array([r[:3] for r in rows], float)
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    best = np.full(len(P), 1e9)
    t = np.zeros(len(P))
    d = np.zeros((len(P), 3))
    for i in range(len(Q) - 1):
        a, ab = Q[i], Q[i + 1] - Q[i]
        u = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        dist = np.linalg.norm(P - (a + u[:, None] * ab), axis=1)
        m = dist < best
        best[m] = dist[m]
        t[m] = (cum[i] + u[m] * seg[i]) / cum[-1]
        d[m] = ab / seg[i]
    return t, best, d


def paint(D, variant='red'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MISC.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    ht = D['aux'].ravel()[idx]                         # the fringes: root (0) to tip (1)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    hair = part == PART['hair']
    furp = part == PART['fur']
    legp = furp & (z < 0.585)                         # the grafted lower legs (fur ids, see deer_body)
    jawp = part == PART['jaw']
    earp = part == PART['ear']
    nosep = part == PART['nose']
    fur = furp | legp | hair | earp | jawp | nosep
    F = DB.fur_flow(P, N)
    n_big = fbm(P * 3.0, 3, seed=91)
    n_mid = fbm(P * 10.0, 3, seed=92)
    s1 = _streaks(P, F, 93, across=0.006, length=0.05, steps=9)
    s2 = _streaks(P, F, 94, across=0.018, length=0.12, steps=7)
    s3 = _streaks(P, F, 95, across=0.009, length=0.18, steps=11)          # the mane's long locks
    Hs = DB.hx_inv(P)                                  # head space
    hy, hz = Hs[:, 1], Hs[:, 2]
    head = (smoothstep(0.06, -0.02, hy) * smoothstep(-0.66, -0.58, hy) * smoothstep(-0.30, -0.22, hz) *
            smoothstep(0.24, 0.16, hz) * smoothstep(0.18, 0.13, ax)) * (furp | nosep | jawp)

    # ------------------------------------------------------------ the coat
    top = smoothstep(0.0, 0.85, nz + 0.20 * n_big)
    col = _mix(np.tile(C['flank'], (n, 1)), C['back'], 0.70 * top)                  # grey-brown, russet on the back
    col = _mix(col, C['light'], 0.25 * smoothstep(0.1, 0.7, n_big) * (1 - top))    # warmer patches low on the flanks
    col = _mix(col, C['light'], 0.35 * smoothstep(0.15, 0.55, s1))                  # paler hair tips through it
    dorsal = (np.exp(-(x / 0.035) ** 2) * smoothstep(0.3, 0.8, nz) * smoothstep(-0.45, -0.30, y) *
              smoothstep(0.70, 0.60, y))
    col = _mix(col, C['edge'], 0.35 * dorsal)
    # the neck and the mane: grey-brown, the mane darker, down onto the brisket, in long locks (paler tips, dark
    # partings) that carry the shagginess
    neck = smoothstep(-0.42, -0.62, y) * smoothstep(0.74, 0.86, z) * (1 - legp) * (1 - head)
    mane = DB.mane_mask(P) * (1 - legp)
    col = _mix(col, C['neck'], 0.85 * neck)
    col = _mix(col, C['mane'], 0.85 * mane)
    locks = np.maximum(neck * 0.6, mane)
    col = _mix(col, C['mane_tip'], 0.55 * locks * smoothstep(0.10, 0.50, s3))
    col = _mix(col, C['mane'] * 0.55, 0.70 * locks * smoothstep(-0.10, -0.45, s3))
    # belly and inner thighs: buff to cream
    belly = (smoothstep(-0.20, -0.70, nz + 0.15 * n_mid) * smoothstep(0.92, 0.80, z) * smoothstep(-0.52, -0.38, y) *
             furp * ~legp)
    col = _mix(col, C['buff'], 0.85 * belly)
    col = _mix(col, C['belly'], 0.6 * belly * smoothstep(-0.55, -0.85, nz))
    inner_thigh = smoothstep(0.115, 0.075, ax) * smoothstep(0.92, 0.78, z) * smoothstep(0.24, 0.39, y) * furp * ~legp
    col = _mix(col, C['buff'], 0.8 * inner_thigh)
    # the rump patch: pale round the tail, edged darker over the top and down the sides
    e = np.sqrt((x / 0.150) ** 2 + ((z - 0.960) / 0.175) ** 2 * (z > 0.96) + ((z - 0.960) / 0.230) ** 2 * (z <= 0.96))
    rear = smoothstep(0.46, 0.64, y) * furp
    en = e + 0.10 * n_mid + 0.05 * s2
    edge = smoothstep(0.84, 1.0, en) * smoothstep(1.30, 1.06, en) * rear * smoothstep(0.80, 0.94, z)
    col = _mix(col, C['edge'], 0.55 * edge)
    patch = smoothstep(1.02, 0.80, en) * rear
    col = _mix(col, C['rump'], 0.92 * patch)
    tt, td = polyline_t(P, DB.TAIL)
    tail = smoothstep(0.056, 0.046, td) * smoothstep(0.15, 0.30, tt) * furp
    tail_back = tail * smoothstep(-0.1, 0.5, N[:, 1] + 0.5 * nz)           # the tail's upper side dark, so it
    col = _mix(col, C['tail'], 0.85 * tail_back)                           # reads against the patch
    # legs: the inner side buff, darker below the knees and hocks, darkest at the fetlocks and pasterns
    cxf = DB.leg_centre(DB.FRONT_LEG, z)[0]
    cxh = DB.leg_centre(DB.HIND_LEG, z)[0]
    cx = np.where(y < 0, cxf, cxh)
    inner = smoothstep(cx + 0.004, cx - 0.014, ax) * furp * smoothstep(0.68, 0.56, z)    # soft: no line at the graft
    col = _mix(col, C['buff'], 0.75 * inner * smoothstep(0.22, 0.40, z))
    low = smoothstep(0.52, 0.30, z) * (legp | furp)
    col = _mix(col, C['legs'], 0.85 * low * (1 - 0.4 * inner))
    col = _mix(col, C['edge'], 0.55 * smoothstep(0.17, 0.11, z) * legp)

    # ------------------------------------------------------------ the face
    fcol = _mix(np.tile(C['face'], (n, 1)), C['neck'], 0.45 * smoothstep(-0.06, 0.06, hz))      # greyer forehead
    muzzle = smoothstep(-0.26, -0.35, hy)
    fcol = _mix(fcol, C['muzzle'], 0.85 * muzzle)
    under = smoothstep(-0.07, -0.13, hz) * smoothstep(-0.10, -0.20, hy) * smoothstep(0.35, -0.2, N[:, 2] + 0.3)
    fcol = _mix(fcol, C['chin'], 0.55 * under * (1 - muzzle))                                    # pale under the jaw line
    for sfx in ('L', 'R'):
        c = np.array(D['eyes']['eye_' + sfx])
        d = np.linalg.norm(P - c, axis=1)
        fcol = _mix(fcol, C['chin'], 0.55 * smoothstep(DB.EYE_R * 2.3, DB.EYE_R * 1.4, d))      # pale ring
        fcol = _mix(fcol, C['edge'], 0.8 * smoothstep(DB.EYE_R * 1.45, DB.EYE_R * 1.05, d))     # dark rim
    gland = np.exp(-(((ax - 0.062) / 0.010) ** 2 + ((hy + 0.190) / 0.024) ** 2 + ((hz + 0.036) / 0.010) ** 2))
    fcol = _mix(fcol, C['edge'], 0.9 * smoothstep(0.2, 0.6, gland))                              # preorbital gland
    col = np.where((furp | nosep)[:, None], _mix(col, fcol, head), col)
    dn = np.linalg.norm((np.stack([ax, hy, hz], -1) - DB.NOSE_C) / np.array(DB.NOSE_R), axis=1)
    pad = np.clip(smoothstep(1.25, 1.0, dn) * (furp | nosep) + nosep, 0, 1)                      # the nose pad
    col = _mix(col, M['nose'] * (0.85 + 0.15 * n_mid[:, None]), pad)
    lip = smoothstep(-0.130, -0.140, hz) * smoothstep(-0.160, -0.150, hz) * smoothstep(-0.22, -0.28, hy) * furp
    col = _mix(col, M['lip'], 0.9 * lip)                                                         # the upper lip's edge
    # the lower jaw: its sides like the face, the chin pale (its tip and underside), a dark lip line along its top,
    # the mouth's inside (a pale band along the whole side read as teeth)
    Nh = N @ np.stack([DB.hx_dir((1, 0, 0)), DB.hx_dir((0, 1, 0)), DB.hx_dir((0, 0, 1))], -1)     # head-space normals
    chin = smoothstep(-0.34, -0.39, hy) * smoothstep(-0.3, -0.7, Nh[:, 1])            # the chin's front, pale
    jcol = _mix(np.tile(C['face'], (n, 1)), C['muzzle'], np.maximum(muzzle, 0.6))     # dark like the muzzle (a
    jcol = _mix(jcol, C['chin'], 0.85 * chin)                          # pale line along it read as a toothpick)
    jcol = _mix(jcol, M['lip'], smoothstep(-0.162, -0.152, hz))
    jcol = np.where((Nh[:, 2] > 0.6)[:, None], M['mouth'], jcol)
    col = np.where(jawp[:, None], jcol, col)
    # ears: furred backs, dark rims and tips, pale hair inside the cup
    Fe = np.stack([DB.EAR_FRONT[0] * np.sign(x), DB.EAR_FRONT[1] * np.ones(n), DB.EAR_FRONT[2] * np.ones(n)], -1)
    Fe /= np.linalg.norm(Fe, axis=1, keepdims=True)
    inside = earp & ((N * Fe).sum(1) > 0.30)
    et = np.zeros(n)
    for s in (1, -1):
        base, tip = DB.ear_rows(s)
        A = (tip - base) / np.linalg.norm(tip - base)
        et = np.where((x > 0) == (s > 0), ((P - base) @ A) / DB.EAR_LEN, et)
    ecol = _mix(np.tile(C['face'], (n, 1)), C['neck'], 0.4 + 0.3 * smoothstep(0.3, 0.8, s1))
    ecol = _mix(ecol, C['edge'], 0.75 * smoothstep(0.78, 0.95, et))
    icol = _mix(np.tile(M['ear_in'], (n, 1)), C['face'], 0.25 * smoothstep(0.2, 0.8, s1))
    icol = _mix(icol, C['edge'], 0.85 * smoothstep(0.82, 0.96, et))
    col = np.where(earp[:, None], np.where(inside[:, None], icol, ecol), col)

    grain = np.where(pad > 0.5, 0.92 + 0.12 * n_mid, 0.80 + 0.36 * s1 + 0.14 * s2 + 0.12 * locks * s3)
    col = col * np.where(fur, grain, 1.0)[:, None]
    smooth = np.where(pad > 0.5, 0.55, np.where(jawp, 0.14, 0.10))     # a wet nose (shiny lips read as teeth)

    # ------------------------------------------------------------ hooves, antlers, eyes
    claw = part == PART['claw']
    if claw.any():
        hc = _mix(np.tile(M['hoof'], (n, 1)), M['hoof_light'], 0.25 * smoothstep(0.03, 0.0, z) + 0.15 * n_mid)
        col = np.where(claw[:, None], hc, col)
        smooth = np.where(claw, 0.35, smooth)
    ant = part == PART['antler']
    if ant.any():
        Pa = P[ant]
        best = np.full(len(Pa), 1e9)
        ta = np.zeros(len(Pa))
        da = np.zeros((len(Pa), 3))
        beam = np.zeros(len(Pa), bool)
        for s in (1, -1):
            for name, rows in DB.antler_tubes(s):
                t, dist, d = _tube_t(Pa, rows)
                dist = dist - 0.5 * np.array([r[3] for r in rows]).mean()      # tines are thinner than the beam
                m = dist < best
                best[m], ta[m], da[m] = dist[m], t[m], d[m]
                beam[m] = name == 'beam'
        groove = _streaks(Pa, da, 97, across=0.004, length=0.05, steps=7)
        ac = _mix(np.tile(M['antler'], (len(Pa), 1)), M['antler_dark'], 0.55 * smoothstep(-0.05, -0.45, groove))
        ac = _mix(ac, M['antler_dark'], 0.75 * beam * smoothstep(0.12, 0.02, ta))           # the burr, darker
        knob = vnoise(Pa * 140.0, seed=98)
        ac = _mix(ac, M['antler_dark'] * 0.7, 0.5 * beam * smoothstep(0.15, 0.05, ta) * smoothstep(0.1, 0.6, knob))
        tips = np.where(beam, smoothstep(0.80, 0.98, ta), smoothstep(0.50, 0.92, ta))
        ac = _mix(ac, M['antler_tip'], tips * (0.85 + 0.15 * smoothstep(-0.3, 0.3, groove)))
        ac = ac * (0.92 + 0.10 * vnoise(Pa * 40.0, seed=99))[:, None]
        col[ant] = ac
        smooth[ant] = 0.25 + 0.25 * tips
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            t, b = DB.eye_axes(nv)
            dd = P - c
            u = (dd @ t) / (DB.EYE_LONG * DB.EYE_R)
            v = (dd @ b) / (DB.EYE_SHORT * DB.EYE_R)
            rr = np.sqrt(u * u + v * v)
            ci = _mix(np.tile(C['iris'], (n, 1)), C['iris'] * 0.45, smoothstep(0.30, 0.75, rr))
            ci = _mix(ci, M['pupil'], smoothstep(0.42, 0.26, np.sqrt((u * 0.8) ** 2 + v ** 2)))   # wide pupil
            ci = _mix(ci, M['pupil'], smoothstep(0.82, 0.98, rr))
            catch = np.exp(-(((u + 0.30) / 0.14) ** 2 + ((v - 0.28) / 0.12) ** 2))     # a painted catchlight: the
            ci = _mix(ci, np.ones(3), 0.9 * smoothstep(0.35, 0.7, catch))            # matte coat has no gloss
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.95, smooth)

    # ------------------------------------------------------------ painted light (lighter than the wolf's: the engine
    # lights it again, and the stag rendered far darker than its texture)
    light = 0.84 + 0.24 * (nz * 0.5 + 0.5)
    light = np.where(jawp, 0.92, light)                                    # the chin faces down: less painted shade
    aot = 0.55 + 0.45 * np.clip(ao, 0, 1)
    aot = np.where(jawp, 0.70 + 0.30 * aot, aot)
    aot = np.where(ant, 0.84 + 0.16 * aot, aot)                            # no dark collars at the tines' roots
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.06)[:, None] * np.array([0.25, 0.2, 0.3])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("red",)):
    D = bake_data(ob, size=size, ao_dist=0.25)
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Deer" if v == "red" else "T_Deer_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "red" else None, "M_Deer"))
    matte(bpy.data.materials["M_Deer"])
    return paths, float(D['valid'].mean())


def matte(m):
    """Fur, not plastic: the viewport (Workbench) roughness and specular, and a low specular on the BSDF (its
    roughness comes from the texture's alpha). The defaults (0.4, 0.5) rendered the coat glossy and dark."""
    m.roughness = 1.0
    m.specular_intensity = 0.0
    m.metallic = 0.0
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    for name, v in (('Specular IOR Level', 0.15), ('Specular', 0.15)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = v
            break
