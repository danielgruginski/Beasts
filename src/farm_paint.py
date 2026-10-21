"""UVs and the painted coats of the hoofed farm animals: deer_paint's recipe for a farm_body.Hoofed (2026-10-20).

UV cuts as the deer's (under the belly, chest, neck and throat, up under the tail, under the jaw, inside the legs),
read in D units through W_inv. The painter also works in D (the baked rest positions go through W_inv), with the
species' palette (sp.COATS[name]) and its hooks:
  sp.coat_pattern(ctx, col)  -> col   patches, socks, blazes, belts (after the base coat, before the face)
  sp.paint_pieces(ctx, col, smooth)   the species' own shells (horns, beard, mane, wool locks)
ctx holds the masks the generic painter made (P in D, N, part masks, head space, noise and fur strokes).
Pupils: sp.PUPIL 'bar' (goat, sheep), 'oval' (cow, horse), 'round' (pig). Coat texture: sp.COAT_STYLE 'sleek' (deer
strokes), 'wool' (curls), 'bristle' (skin with sparse hair).
"""
import bpy
import numpy as np
from beast_common import smoothstep, fbm, vnoise
import beast_paint as BP
from beast_paint import _interp_axis, _c, _mix, _streaks, bake_data, write_texture, polyline_t
from beast_body import PART


def make_cut(sp):
    def neck_z(y):
        return float(np.interp(-y, [-r[1] for r in sp.NECK], [r[2] for r in sp.NECK]))

    def cut(region, c):
        x, y, z = c
        if region == 'trunk':
            return ((z < sp.BELLY_CUT) or (y > sp.TAIL[0][1] - 0.05 and z < sp.TAIL[0][2] - 0.02) or
                    (y < sp.NECK[0][1] - 0.13 and z < neck_z(y))), x > 0
        if region == 'head':
            h = sp.hx_inv(np.array(c))
            return h[2] < sp.JAW_H[0][2] + 0.05 and abs(x) < 0.10, x > 0
        if region == 'tail':
            return y < _interp_axis(z, sp.TAIL) + 0.005, x > 0
        j = sp.J
        if region.startswith('fleg'):
            return abs(x) < j['SHO'][0], y > _interp_axis(z, [j['SCAP'], j['SHO'], j['ELB'], j['WRI']])
        if region.startswith('hleg'):
            return abs(x) < j['HIP'][0] + 0.02, y > _interp_axis(z, [j['HIP'], j['KNEE'], j['HOCK'], j['HPAW']])
        return None
    return cut


UV_SCALE = {'head': 1.6, 'ear': 1.3, 'eye': 2.0, 'nose': 1.6, 'jaw': 1.2, 'horn': 0.9, 'leg': 1.1, 'claw': 0.7,
            'hair': 0.8, 'tail': 1.0}


def unwrap(sp, ob, margin=0.003, relax=40):
    return BP.unwrap(ob, make_cut(sp), dict(UV_SCALE, **sp.UV_SCALE), sp.W_inv, margin, relax)


MISC = dict(nose='#121010', lip='#1a1614', mouth='#4e2c2c', hoof='#1d1916', hoof_light='#4c443c', pupil='#050404',
            ear_in='#d8ccb6', horn='#8a7c66', horn_dark='#3e352a', horn_tip='#d8ccb0')


def paint(D, sp, variant):
    coat = sp.COATS[variant]
    C = {k: _c(v) for k, v in coat.items()}
    M = {k: _c(v) for k, v in dict(MISC, **sp.MISC).items()}
    M.update({k: C[k] for k in coat if k in MISC})        # a coat may bring its own nose, hooves, horns
    valid = D['valid']
    H, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    PR = D['P'].reshape(-1, 3)[idx]
    P = sp.W_inv(PR)                                   # the painter works in D
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    nz = N[:, 2]
    n = len(P)
    hair = part == PART['hair']
    furp = part == PART['fur']
    seam_z = min(sp.SEAM.values())
    legp = furp & (z < seam_z + 0.02)
    jawp = part == PART['jaw']
    earp = part == PART['ear']
    nosep = part == PART['nose']
    tailp = part == PART['tail']                      # a separate tail tube (the cow's)
    fur = furp | legp | hair | earp | jawp | nosep | tailp
    F = sp.fur_flow(P, N)
    n_big = fbm(P * 3.0, 3, seed=91)
    n_mid = fbm(P * 10.0, 3, seed=92)
    s1 = _streaks(P, F, 93, across=0.006, length=0.05, steps=9)
    s2 = _streaks(P, F, 94, across=0.018, length=0.12, steps=7)
    Hs = sp.hx_inv(P)
    hx_, hy, hz = Hs[:, 0], Hs[:, 1], Hs[:, 2]
    L = sp.HEAD_LEN
    head = sp.face_mask(P) * (furp | nosep | jawp)
    head = np.maximum(head, (smoothstep(0.06, -0.02, hy) * smoothstep(-L - 0.25, -L - 0.17, hy) *
                             smoothstep(-0.30, -0.22, hz) * smoothstep(0.24, 0.16, hz) *
                             smoothstep(0.18, 0.13, np.abs(hx_))) * (furp | nosep | jawp))

    # ------------------------------------------------------------ the coat
    top = smoothstep(0.0, 0.85, nz + 0.20 * n_big)
    col = _mix(np.tile(C['flank'], (n, 1)), C['back'], 0.70 * top)
    col = _mix(col, C['light'], 0.25 * smoothstep(0.1, 0.7, n_big) * (1 - top))
    col = _mix(col, C['light'], 0.30 * smoothstep(0.15, 0.55, s1))
    belly = (smoothstep(-0.20, -0.70, nz + 0.15 * n_mid) * smoothstep(sp.BELLY_CUT + 0.12, sp.BELLY_CUT, z) *
             smoothstep(sp.NECK[0][1] - 0.10, sp.NECK[0][1] + 0.04, y) * furp * ~legp)
    col = _mix(col, C['belly'], 0.85 * belly)
    tt, td = polyline_t(P, sp.TAIL)
    tail = np.maximum(smoothstep(0.070, 0.050, td) * smoothstep(0.10, 0.30, tt) * furp, tailp)
    col = _mix(col, C['tail'], 0.85 * tail)
    cxf = sp.leg_centre(sp.FRONT_LEG_T, z)[0]
    cxh = sp.leg_centre(sp.HIND_LEG_T, z)[0]
    cx = np.where(y < 0, cxf, cxh)
    inner = smoothstep(cx + 0.004, cx - 0.014, ax) * furp * smoothstep(0.68, 0.56, z)
    col = _mix(col, C['belly'], 0.45 * inner * smoothstep(0.22, 0.40, z))
    low = smoothstep(seam_z - 0.05, seam_z - 0.27, z) * (legp | furp)
    col = _mix(col, C['legs'], 0.85 * low * (1 - 0.4 * inner))
    col = _mix(col, C['edge'], 0.45 * smoothstep(0.17, 0.11, z) * legp)
    ctx = dict(P=P, PR=PR, N=N, part=part, x=x, y=y, z=z, ax=ax, nz=nz, n=n, furp=furp, legp=legp, hair=hair,
               jawp=jawp, earp=earp, nosep=nosep, head=head, hy=hy, hz=hz, hx=hx_, n_big=n_big, n_mid=n_mid, s1=s1,
               s2=s2, top=top, belly=belly, tail=tail, low=low, inner=inner, C=C, M=M, D=D, F=F)
    col = sp.coat_pattern(ctx, col)

    # ------------------------------------------------------------ the face
    fcol = _mix(np.tile(C['face'], (n, 1)), C['back'], 0.30 * smoothstep(-0.06, 0.06, hz))
    muzzle = smoothstep(-0.62 * L, -0.80 * L, hy)
    fcol = _mix(fcol, C['muzzle'], 0.85 * muzzle)
    jtop = sp.JAW_H[0][2]
    under = smoothstep(jtop + 0.08, jtop + 0.02, hz) * smoothstep(-0.10, -0.20, hy) * smoothstep(0.35, -0.2, N[:, 2] + 0.3)
    fcol = _mix(fcol, C['chin'], 0.55 * under * (1 - muzzle))
    for sfx in ('L', 'R'):
        c = np.array(D['eyes']['eye_' + sfx])
        d = np.linalg.norm(P - c, axis=1)
        fcol = _mix(fcol, C['edge'], sp.EYE_RING * smoothstep(sp.EYE_R * 1.45, sp.EYE_R * 1.05, d))
    ctx['fcol'] = fcol
    fcol = sp.face_pattern(ctx, fcol)
    col = np.where((furp | nosep)[:, None], _mix(col, fcol, head), col)
    dn = np.linalg.norm((np.stack([ax, hy, hz], -1) - sp.NOSE_C) / np.array(sp.NOSE_R), axis=1)
    pad = np.clip(smoothstep(1.25, 1.0, dn) * (furp | nosep) + nosep, 0, 1)
    col = _mix(col, M['nose'] * (0.85 + 0.15 * n_mid[:, None]), pad)
    Nh = N @ np.stack([sp.hx_dir((1, 0, 0)), sp.hx_dir((0, 1, 0)), sp.hx_dir((0, 0, 1))], -1)
    chin = smoothstep(-0.78 * L, -0.90 * L, hy) * smoothstep(-0.3, -0.7, Nh[:, 1])
    jcol = _mix(np.tile(C['face'], (n, 1)), C['muzzle'], np.maximum(muzzle, 0.6))
    jcol = _mix(jcol, C['chin'], 0.85 * chin)
    jcol = _mix(jcol, M['lip'], smoothstep(jtop - 0.008, jtop + 0.002, hz))
    jcol = np.where(((Nh[:, 2] > 0.6) & (hy < -0.50 * L))[:, None], M['mouth'], jcol)   # the jaw's back, in the
                                                                                         # cheek, stays face colour
    col = np.where(jawp[:, None], jcol, col)
    Fe = np.stack([sp.EAR_FRONT[0] * np.sign(x), sp.EAR_FRONT[1] * np.ones(n), sp.EAR_FRONT[2] * np.ones(n)], -1)
    Fe /= np.linalg.norm(Fe, axis=1, keepdims=True)
    inside = earp & ((N * Fe).sum(1) > 0.30)
    et = np.zeros(n)
    for s in (1, -1):
        base, tip = sp.ear_rows(s)
        A = (tip - base) / np.linalg.norm(tip - base)
        et = np.where((x > 0) == (s > 0), ((P - base) @ A) / sp.EAR_LEN, et)
    ecol = _mix(np.tile(C['face'], (n, 1)), C['back'], 0.3 + 0.3 * smoothstep(0.3, 0.8, s1))
    ecol = _mix(ecol, C['edge'], sp.EAR_RIM * smoothstep(0.78, 0.95, et))
    icol = _mix(np.tile(M['ear_in'], (n, 1)), C['face'], 0.25 * smoothstep(0.2, 0.8, s1))
    icol = _mix(icol, C['edge'], sp.EAR_RIM * smoothstep(0.82, 0.96, et))
    col = np.where(earp[:, None], np.where(inside[:, None], icol, ecol), col)
    ctx.update(et=et, ear_inside=inside, pad=pad)

    style = sp.COAT_STYLE
    if style == 'wool':
        curl = vnoise(P * 70.0, seed=96) * 0.6 + vnoise(P * 150.0, seed=97) * 0.4
        wool = sp.wool_mask(P) * fur
        grain = np.where(wool > 0.5, 0.91 + 0.10 * smoothstep(0.25, 0.85, curl) + 0.05 * s2,
                         0.82 + 0.30 * s1 + 0.12 * s2)
    elif style == 'bristle':
        grain = 0.94 + 0.10 * n_mid + 0.10 * smoothstep(0.35, 0.70, s1)
    else:
        grain = 0.80 + 0.36 * s1 + 0.14 * s2
    grain = np.where(pad > 0.5, 0.92 + 0.12 * n_mid, grain)
    col = col * np.where(fur, grain, 1.0)[:, None]
    smooth = np.where(pad > 0.5, 0.55, np.where(jawp, 0.14, 0.10))

    # ------------------------------------------------------------ hooves, the species' pieces, eyes
    claw = part == PART['claw']
    if claw.any():
        hc = _mix(np.tile(M['hoof'], (n, 1)), M['hoof_light'], 0.25 * smoothstep(0.03, 0.0, z) + 0.15 * n_mid)
        col = np.where(claw[:, None], hc, col)
        smooth = np.where(claw, 0.35, smooth)
    col, smooth = sp.paint_pieces(ctx, col, smooth)
    eye = part == PART['eye']
    if eye.any():
        ecol = np.zeros((n, 3))
        for sfx in ('L', 'R'):
            c = np.array(D['eyes']['eye_' + sfx])
            nv = np.array(D['eyes']['eye_n_' + sfx])
            t, b = sp.eye_axes(nv)
            dd = P - c
            u = (dd @ t) / (sp.EYE_LONG * sp.EYE_R)
            v = (dd @ b) / (sp.EYE_SHORT * sp.EYE_R)
            rr = np.sqrt(u * u + v * v)
            ci = _mix(np.tile(C['iris'], (n, 1)), C['iris'] * 0.55, smoothstep(0.30, 0.85, rr))
            t2, b2 = sp.eye_axes(nv, (0.0, 1.0, 0.0))       # pupils lie level with the ground, not the face
            u2, v2 = (dd @ t2) / sp.EYE_R, (dd @ b2) / sp.EYE_R
            if sp.PUPIL == 'bar':                     # goats and sheep: a horizontal slot
                pm = smoothstep(0.66, 0.54, np.abs(u2)) * smoothstep(0.20, 0.12, np.abs(v2))
            elif sp.PUPIL == 'oval':
                pm = smoothstep(0.50, 0.38, np.sqrt((u2 * 0.75) ** 2 + (v2 * 1.6) ** 2))
            else:
                pm = smoothstep(0.34, 0.24, rr)
            ci = _mix(ci, M['pupil'], pm)
            ci = _mix(ci, M['pupil'], smoothstep(0.82, 0.98, rr))
            catch = np.exp(-(((u + 0.30) / 0.14) ** 2 + ((v - 0.28) / 0.12) ** 2))
            ci = _mix(ci, np.ones(3), 0.9 * smoothstep(0.35, 0.7, catch))
            side = (P[:, 0] > 0) if sfx == 'L' else (P[:, 0] <= 0)
            ecol = np.where(side[:, None], ci, ecol)
        col = np.where(eye[:, None], ecol, col)
        smooth = np.where(eye, 0.95, smooth)

    # ------------------------------------------------------------ painted light (the deer's: lighter than the wolf's)
    light = 0.84 + 0.24 * (nz * 0.5 + 0.5)
    light = np.where(jawp, 0.92, light)
    aot = 0.55 + 0.45 * np.clip(ao, 0, 1)
    aot = np.where(jawp, 0.70 + 0.30 * aot, aot)
    aot = np.where(part == PART['horn'], 0.80 + 0.20 * aot, aot)
    shaded = col * (light * aot)[:, None] + ((1 - aot) * 0.06)[:, None] * np.array([0.25, 0.2, 0.3])
    shaded = np.where(eye[:, None], col * (0.9 + 0.1 * aot[:, None]), shaded)
    out = np.zeros((H * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(H * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(H, Wd, 3), sm.reshape(H, Wd)


def horns(sp, ctx, col, smooth, ridges=14, root_dark=0.3, tip_from=0.65):
    """Horn colour along each horn (PART horn, sp.horn_rows): base colour, growth ridges, a darker root, the tip
    toward horn_tip."""
    part, P, M = ctx['part'], ctx['P'], ctx['M']
    horn = part == PART['horn']
    if not horn.any():
        return col, smooth
    Ph = P[horn]
    t = np.zeros(len(Ph))
    best = np.full(len(Ph), 1e9)
    for s in (1, -1):
        rows = np.array(sp.horn_rows(s))
        for i in range(len(rows) - 1):
            a, ab = rows[i, :3], rows[i + 1, :3] - rows[i, :3]
            u = np.clip(((Ph - a) @ ab) / (ab @ ab), 0, 1)
            d = np.linalg.norm(Ph - (a + u[:, None] * ab), axis=1)
            m = d < best
            best[m] = d[m]
            t[m] = (i + u[m]) / (len(rows) - 1)
    rid = 0.5 + 0.5 * np.sin(t * 2 * np.pi * ridges) if ridges else np.zeros(len(Ph))
    hc = _mix(np.tile(M['horn'], (len(Ph), 1)), M['horn_dark'], 0.35 * rid * 0.6 + root_dark * smoothstep(0.2, 0.0, t))
    hc = _mix(hc, M['horn_tip'], smoothstep(tip_from, 0.98, t))
    col[horn] = hc
    smooth[horn] = 0.30
    return col, smooth


def patches(P, seed, scale=2.2, thresh=0.0, soft=0.06, warp=0.35):
    """Piebald patches (D): 1 inside a patch. Domain-warped noise so the edges wander."""
    q = P * scale
    q = q + warp * np.stack([fbm(P * 4.0, 2, seed=seed + k) for k in (1, 2, 3)], -1)
    v = fbm(q, 3, seed=seed)
    return smoothstep(thresh - soft, thresh + soft, v)


def build_texture(sp, ob, size=1024, variants=None):
    """T_<Name>.png for the first coat, T_<Name>_<Coat>.png for the others; the material M_<Name>."""
    D = bake_data(ob, size=size, ao_dist=0.25 * sp.KB)
    paths = []
    names = variants or list(sp.COATS)
    for i, v in enumerate(names):
        col, smooth = paint(D, sp, v)
        name = f"T_{sp.NAME}" if i == 0 else f"T_{sp.NAME}_{v.title()}"
        paths.append(write_texture(D, col, smooth, name, ob if i == 0 else None, f"M_{sp.NAME}"))
    import deer_paint
    deer_paint.matte(bpy.data.materials[f"M_{sp.NAME}"])
    return paths, float(D['valid'].mean())


def uv_png(ob, path, size=1024, tex=None):
    """A UV layout PNG drawn without the GPU (headless Blender can't run uv.export_layout): the edges over the
    texture (or grey)."""
    import numpy as np
    me = ob.data
    uv = me.uv_layers.active.data
    img = np.full((size, size, 3), 0.15, np.float32)
    if tex is not None:
        im = bpy.data.images.load(tex, check_existing=True)
        w, h = im.size
        a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[:, :, :3]
        ys = (np.arange(size) * h / size).astype(int)
        xs = (np.arange(size) * w / size).astype(int)
        img = a[ys][:, xs] * 0.8
    for p in me.polygons:
        pts = [uv[l].uv for l in p.loop_indices]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            k = int(max(abs(b.x - a.x), abs(b.y - a.y)) * size) + 2
            t = np.linspace(0, 1, k)
            px = np.clip(((a.x + (b.x - a.x) * t) * (size - 1)).astype(int), 0, size - 1)
            py = np.clip(((a.y + (b.y - a.y) * t) * (size - 1)).astype(int), 0, size - 1)
            img[py, px] = (1.0, 1.0, 0.3)
    out = bpy.data.images.new("_uvpng", size, size)
    rgba = np.concatenate([img, np.ones((size, size, 1), np.float32)], -1)
    out.pixels.foreach_set(rgba.ravel())
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    return path
