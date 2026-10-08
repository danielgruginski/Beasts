"""UVs and the painted coat of the woolly rhino (the framework is beast_paint.py).

UV cuts: along the underside of the belly, chest and throat and up under the tail, under the jaw, inside each leg;
the soles are separate islands, and the shells (chin, horns, eyes, spear, clumps and fringes) keep the seams their
builders marked.

Coat 'woolly': a mammoth's coat, dark chestnut at the roots and on the lower body, sun-bleached tawny tips and a
ginger hump; shorter greyer hair on the face, bare dark-grey lips and chin; mud caked on the legs and the skirt's
hem; old pale scars on the snout and flanks; dark horns with growth bands and a worn pale tip; blood matted round the
spear. Strands follow rhino_body.fur_flow; on the clumps and fringes they also darken toward the root (info.b).
"""
import numpy as np
from beast_common import smoothstep, fbm, vnoise
import rhino_body as RB
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture
from beast_body import PART


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 0.95) or (y > 0.95 and z < 1.30) or (y < -0.85 and z < 1.10), x > 0
    if region == 'head':                                   # under the jaw and throat (head space)
        h = RB.hx_inv(np.array(c))
        return h[2] < -0.36 and abs(x) < 0.14, x > 0
    if region == 'tail':
        return y > _interp_axis(z, RB.TAIL) - 0.01, x > 0
    j = RB.J
    if region.startswith('fleg'):
        return abs(x) < 0.31, y > _interp_axis(z, [j['SHO'], j['ELB'], j['WRI'], j['FPAW']])
    if region.startswith('hleg'):
        return abs(x) < 0.32, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
    return None


UV_SCALE = {'head': 1.5, 'ear': 1.3, 'eye': 2.5, 'jaw': 1.3, 'horn': 1.3, 'spear': 1.4, 'hair': 0.9,
            'tail': 1.0, 'sole': 0.4}


def unwrap(ob, margin=0.003, relax=40):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


def uv_layout(ob, name="uv_layout_rhino", size=2048):
    return BP.uv_layout(ob, name, size)


COATS = {
    'woolly': dict(root='#24190f', base='#4c3320', light='#8d6a42', hump='#a27b4b', face='#5c4b3d',
                   skin='#3b3532', skin_light='#6b605a', mud='#3f3226', mud_dry='#5e4f3e', hoof='#6c604f',
                   horn_base='#271f19', horn_mid='#664c31', horn_tip='#c4ad82', iris='#8e4c14', blood='#3e140f'),
}
MISC = dict(pupil='#090605', nostril='#141010', inner='#3a2422', scar='#a08a78', wood='#8f7a5a', wood_dark='#5f4f3b',
            iron='#3a3938', rust='#6b3d22', leather='#4b2f1e')


def _polyline_t(P, rows):
    """Arc position 0..1 along a polyline of rows (x, y, z, ...) for points P, and the distance to it."""
    Q = np.array([r[:3] for r in rows], float)
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    best = np.full(len(P), 1e9)
    t = np.zeros(len(P))
    for i in range(len(Q) - 1):
        a, d = Q[i], Q[i + 1] - Q[i]
        u = np.clip(((P - a) @ d) / (d @ d), 0, 1)
        dist = np.linalg.norm(P - (a + u[:, None] * d), axis=1)
        m = dist < best
        best[m] = dist[m]
        t[m] = (cum[i] + u[m] * seg[i]) / cum[-1]
    return t, best


def _segments(P, segs, width):
    """1 on thin lines (scars): segs = [(a, b)], distance < width, soft edge."""
    out = np.zeros(len(P))
    for a, b in segs:
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        u = np.clip(((P - a) @ d) / (d @ d), 0, 1)
        dist = np.linalg.norm(P - (a + u[:, None] * d), axis=1)
        out = np.maximum(out, smoothstep(width, width * 0.4, dist) * np.sin(np.pi * np.clip(u, 0.02, 0.98)) ** 0.3)
    return out


# old scars: (start, end); the snout ones in head space, the flank ones on the body
SNOUT_SCARS = [((0.15, -0.58, -0.10), (0.14, -0.76, -0.20)), ((0.12, -0.62, -0.02), (0.08, -0.70, 0.00)),
               ((-0.15, -0.52, -0.14), (-0.14, -0.70, -0.24))]
SCARS = [
         ((0.56, -0.15, 1.05), (0.55, 0.20, 0.90)), ((0.57, 0.05, 1.12), (0.57, 0.30, 1.04)),
         ((-0.58, 0.35, 1.10), (-0.56, 0.62, 0.95))]


def paint(D, variant='woolly'):
    C = {k: _c(v) for k, v in COATS[variant].items()}
    M = {k: _c(v) for k, v in MISC.items()}
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    ht = D['aux'].ravel()[idx]                         # clumps: root (0) to tip (1)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    hair = part == PART['hair']
    fur = (part == PART['fur']) | hair | (part == PART['ear'])
    F = RB.fur_flow(P, N)
    n_big = fbm(P * 2.5, 3, seed=31)
    n_mid = fbm(P * 9.0, 3, seed=32)
    s1 = _streaks(P, F, 41, across=0.010, length=0.09, steps=9)
    s2 = _streaks(P, F, 42, across=0.030, length=0.20, steps=7)

    # ------------------------------------------------------------ the coat
    top = smoothstep(0.0, 0.8, nz + 0.25 * n_big)
    col = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.55 * top)
    hump = np.exp(-(((x) / 0.45) ** 2 + ((y + 0.55) / 0.55) ** 2 + ((z - 1.75) / 0.35) ** 2))
    col = _mix(col, C['hump'], 0.75 * hump * smoothstep(-0.2, 0.5, nz))
    low = smoothstep(1.05, 0.55, z)                                       # darker under the belly and on the skirt
    col = _mix(col, C['root'], 0.45 * low)
    # strands: light tips of the coarse locks, dark partings between them
    col = _mix(col, C['light'] * 1.05, 0.35 * smoothstep(0.25, 0.75, s1) * (0.4 + 0.6 * top))
    col = _mix(col, C['root'], 0.55 * smoothstep(-0.2, -0.65, s2))
    # clumps and fringes: dark at the root, bleached at the tip
    hcol = _mix(np.tile(C['base'], (n, 1)), C['light'], 0.25 + 0.35 * top + 0.4 * smoothstep(0.45, 1.0, ht))
    hcol = _mix(hcol, C['hump'], 0.6 * hump)
    hcol = _mix(hcol, C['root'], 0.35 * smoothstep(0.30, 0.0, ht))
    col = np.where(hair[:, None], hcol, col)
    # face: short, greyer hair; bare grey skin on the muzzle, lips and chin
    Hs = RB.hx_inv(P)                                                      # head space
    hy, hz = Hs[:, 1], Hs[:, 2]
    face = smoothstep(0.05, -0.08, hy) * (1 - hair) * (part != PART['ear'])
    fur = fur | (part == PART['jaw'])                                      # the chin is furry too
    col = _mix(col, C['face'], 0.75 * face)
    lips = smoothstep(-0.72, -0.80, hy) * smoothstep(-0.12, -0.20, hz)                  # the front of the lip
    lips = np.maximum(lips, smoothstep(-0.25, -0.29, hz) * smoothstep(-0.55, -0.62, hy))  # its edge to the corner
    jawp = (part == PART['jaw']).astype(float)
    chin_lip = jawp * smoothstep(-0.315, -0.295, hz)                       # only the lip's rim   # the lower lip's edge
    muzzle = np.maximum(lips * face, chin_lip)
    wrinkle = 0.5 + 0.5 * np.sin(hz * 140.0 + 6.0 * n_mid)                 # skin folds across the lips
    skin = _mix(np.tile(C['skin'], (n, 1)), C['skin_light'], 0.25 + 0.25 * n_mid + 0.15 * wrinkle)
    col = _mix(col, skin, muzzle)
    nostril = np.exp(-(((ax - 0.085) / 0.018) ** 2 + ((hy + 0.900) / 0.018) ** 2 + ((hz + 0.170) / 0.024) ** 2))
    col = _mix(col, M['nostril'], smoothstep(0.35, 0.8, nostril))
    Nh = RB.hx_inv(N + RB.HEAD_PIVOT)                                      # normals in head space
    mouth = (part == PART['jaw']) & (Nh[:, 2] > 0.4)                         # inside of the lower lip
    mouth |= (part == PART['fur']) & (hy < -0.645) & (hz < -0.28) & (Nh[:, 2] < -0.5)   # the palate
    col = np.where(mouth[:, None], np.tile(M['inner'], (n, 1)), col)
    # ears: dark skin inside, hair on the rims (already coat)
    earp = part == PART['ear']
    Pm = np.stack([ax, y, z], -1)
    t_ear, d_ear = _polyline_t(Pm, RB.EAR)
    inside = earp & (d_ear < 0.034) & (N[:, 1] < 0.2)                         # the scooped front
    col = np.where(earp[:, None], _mix(np.tile(C['base'], (n, 1)), C['light'], 0.3 + 0.4 * t_ear), col)
    col = np.where(inside[:, None], _mix(np.tile(M['inner'], (n, 1)), C['skin_light'], 0.2 * n_mid), col)
    # scars: pale, hairless lines
    scar = np.maximum(_segments(P, SCARS, 0.012), _segments(Hs, SNOUT_SCARS, 0.012) * face)
    col = _mix(col, C['skin_light'] * 1.15, 0.85 * scar * (1 - hair))
    # mud: caked on the legs, the feet and the skirt's hem, drier and paler at the top of the splashes
    mud_line = 0.42 + 0.08 * n_big
    mud = smoothstep(mud_line, mud_line - 0.12, z) * smoothstep(-0.35, 0.25, fbm(P * 6.0, 3, seed=61))
    mud = np.maximum(mud, smoothstep(0.18, 0.05, z) * (1 - (part == PART['spear'])))
    mcol = _mix(np.tile(C['mud'], (n, 1)), C['mud_dry'], smoothstep(0.1, 0.35, z) + 0.3 * n_mid)
    col = _mix(col, mcol, 0.85 * mud * fur)
    # feet: dark skin toes, pale hoof nails at the front
    feet = fur & (z < 0.11)
    for key in ('FPAW', 'HPAW'):
        fx, fy, _ = RB.J[key]
        nail = (np.abs(ax - fx) < 0.15) & (y < fy - 0.07) & (y > fy - 0.20) & (z < 0.075) & (z > 0.012) & (N[:, 1] < -0.35)
        col = np.where((nail & feet)[:, None], _mix(np.tile(C['hoof'], (n, 1)), C['mud'], 0.35 * mud), col)
    grain = np.where(muzzle > 0.5, 0.94 + 0.10 * n_mid, 0.78 + 0.30 * s1 + 0.12 * s2)
    col = col * grain[:, None]
    smooth = np.where(muzzle > 0.5, 0.25, 0.10)
    smooth = np.where(mud > 0.5, 0.05, smooth)

    # ------------------------------------------------------------ blood round the spear
    e = np.asarray(D['eyes'].get('spear_entry', RB.SPEAR_AIM))
    r = np.linalg.norm(P - e, axis=1)
    drip = smoothstep(0.16, 0.0, np.abs(x - e[0]) * 2.5 + np.maximum(z - e[2], 0) * 3) * (z < e[2]) * \
        smoothstep(e[2] - 0.45, e[2] - 0.05, z) * smoothstep(0.2, 0.6, vnoise(P * np.array([30, 30, 4]), seed=71))
    blood = np.maximum(smoothstep(0.13, 0.04, r + 0.03 * n_mid), drip * (y > e[1] - 0.12) * (y < e[1] + 0.12))
    col = _mix(col, C['blood'], 0.9 * blood * fur)
    smooth = np.where(blood * fur > 0.5, 0.45, smooth)

    # ------------------------------------------------------------ horns
    horn = part == PART['horn']
    if horn.any():
        Ph = P[horn]
        t1, d1 = _polyline_t(Ph, RB.HORN1)
        t2, d2 = _polyline_t(Ph, RB.HORN2)
        front = d1 < d2
        t = np.where(front, t1, t2)
        bands = 0.5 + 0.5 * np.sin(t * 38.0 + 2.0 * fbm(Ph * 12.0, 2, seed=81))           # growth rings
        fib = _streaks(Ph, np.tile(np.array([0.0, -0.45, 0.89]), (len(Ph), 1)), 82, across=0.006, length=0.12)
        hc = _mix(np.tile(C['horn_base'], (len(Ph), 1)), C['horn_mid'], smoothstep(0.05, 0.55, t))
        hc = _mix(hc, C['horn_tip'], smoothstep(0.55, 0.98, t))
        hc = _mix(hc, C['horn_base'], 0.35 * bands * smoothstep(0.85, 0.3, t))
        hc = hc * (0.85 + 0.25 * fib)[:, None]
        wear = smoothstep(-0.3, -0.8, N[horn, 1]) * smoothstep(0.3, 0.8, t)      # the front edge rubbed pale
        hc = _mix(hc, C['horn_tip'] * 1.08, 0.4 * wear)
        col[horn] = hc
        smooth[horn] = 0.35 + 0.35 * smoothstep(0.5, 1.0, t)

    # ------------------------------------------------------------ eyes
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            d = P - c
            d = d - np.outer(d @ nv, nv)
            rr = np.linalg.norm(d, axis=1) / RB.EYE_R
            ci = _mix(np.tile(C['iris'], (n, 1)), C['iris'] * 0.45, smoothstep(0.35, 0.8, rr))
            ci = _mix(ci, M['pupil'], smoothstep(0.42, 0.25, rr))
            ci = _mix(ci, M['pupil'], smoothstep(0.85, 1.0, rr))                         # dark rim
            hl = np.array((-0.25, -0.45, 0.86))
            spec = smoothstep(0.93, 0.975, N @ (hl / np.linalg.norm(hl)))
            ci = _mix(ci, np.ones(3), 0.9 * spec)
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.95, smooth)
        for sfx in ('L', 'R'):                                                             # bare skin ring
            c = np.array(D['eyes']['eye_' + sfx])
            ring = smoothstep(RB.EYE_R * 2.2, RB.EYE_R * 1.1, np.linalg.norm(P - c, axis=1)) * fur
            col = _mix(col, C['skin'] * 1.1, 0.8 * ring)

    # ------------------------------------------------------------ the spear
    sp = part == PART['spear']
    if sp.any():
        Ps = P[sp]
        u = (Ps - e) @ RB.SPEAR_DIR
        wood = _mix(np.tile(M['wood'], (len(Ps), 1)), M['wood_dark'],
                    0.5 + 0.5 * _streaks(Ps, np.tile(RB.SPEAR_DIR, (len(Ps), 1)), 91, across=0.004, length=0.15))
        wood = _mix(wood, np.array([0.55, 0.55, 0.52]), 0.25 * smoothstep(0.3, 0.6, u))       # weathered grey
        iron = _mix(np.tile(M['iron'], (len(Ps), 1)), M['rust'], smoothstep(0.0, 0.6, fbm(Ps * 40.0, 3, seed=92)))
        leather = np.tile(M['leather'], (len(Ps), 1)) * (0.85 + 0.2 * vnoise(Ps * 80.0, seed=93))[:, None]
        is_iron = u < 0.125
        is_wrap = (u >= 0.12) & (u < 0.18) & (np.linalg.norm((Ps - e) - np.outer(u, RB.SPEAR_DIR), axis=1) > 0.0215)
        sc = np.where(is_iron[:, None], iron, np.where(is_wrap[:, None], leather, wood))
        sc = _mix(sc, C['blood'], 0.7 * smoothstep(0.06, -0.02, u))                           # bloodied at the wound
        sc = _mix(sc, np.array([0.80, 0.72, 0.56]), 0.6 * smoothstep(0.58, 0.64, u))         # fresh splinters
        col[sp] = sc
        smooth[sp] = np.where(is_iron, 0.45, 0.15)

    # ------------------------------------------------------------ painted light
    light = 0.74 + 0.36 * (nz * 0.5 + 0.5)
    aot = 0.38 + 0.62 * np.clip(ao, 0, 1)
    aot = np.where(hair, 0.55 + 0.45 * aot, aot)                           # the shells' own AO is too dark
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.06)[:, None] * np.array([0.25, 0.2, 0.3])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def build_texture(ob, size=1024, variants=("woolly",)):
    D = bake_data(ob, size=size, ao_dist=0.30)
    if "spear_entry" in ob.keys():
        D['eyes']['spear_entry'] = np.array(ob["spear_entry"])
    paths = []
    for v in variants:
        col, smooth = paint(D, v)
        name = "T_Rhino" if v == "woolly" else "T_Rhino_" + v.title()
        paths.append(write_texture(D, col, smooth, name, ob if v == "woolly" else None, "M_Rhino"))
    return paths, float(D['valid'].mean())
