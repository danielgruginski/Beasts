"""UVs and the painted plumage of the golden eagle (the framework is beast_paint.py), 2026-10-24.

UVs: the fused body is cut along the belly and up the breast, under the chin and the tail coverts, and down the back
of each trouser (the regions come from the skin weights); the pieces keep the seams their builders marked; every
feather card is an island of its own. One 1024 texture for the whole bird, RGB colour, A smoothness.

Paint, per texel from Cycles bakes of the rest position, normal, part id, AO and -- on the cards -- the card's own
coordinates (u across the vane, -1 leading edge .. +1 trailing edge; v root -> tip; the kind and index of the feather;
the 'root' point attribute, baked like beast_coat's roots):
- the body: feathers as scallops, a jittered 3D lattice squeezed along the feather flow (longer than wide), each
  feather's tip with a paler fringe, the hackles streaked;
- the cards: a dark tip, barred bases, the shaft, darker vane edges, a pale fringe on the coverts' tips;
- the bare parts: a horn beak with a dark hook and a yellow cere, the eye, the toes with their scutes, black talons.

Presets (my calls; Daniel can overrule): 'golden' (adult golden eagle: dark brown, a golden crown and nape, tawny
trousers and wing-covert bar, flight feathers greyer and barred at the base with a dark trailing band, the tail barred
grey-brown with a broad dark tip, a faint pale patch at the base of the inner primaries; amber-brown eye; the tarsus
feathered to the toes) and 'bald' (dark brown body and wings, white head, neck and tail, yellow beak, cere and feet,
pale yellow eye, the lower tarsus bare).

Revision 2026-10-24: the hackles tawny gold (#9a7a3c) on the hind crown, nape and hindneck only, fading into a dark
forehead, brow and face; the beak painted by its own (h, t): the cere a yellow saddle over the base (the nostril in
it), horn darkening to the hook, a thin dark cutting edge, the lower mandible in the beak's colours (no dark bar),
a soft yellow gape back to below the eye's front; the eyeball: iris (dark amber-brown / pale yellow), a darker rim,
the pupil, the brow's shadow over its top, a thin soft lid; the wing's flesh painted as small dark coverts (no flesh
strip); subtler bars on the remiges and the tail; low-contrast greater coverts; the scapulars the back's brown; the
trousers only round the legs (the old mask painted the whole underside tawny).
"""
import numpy as np
import beast_paint as BP
from beast_common import smoothstep, fbm, vnoise, _hash3
from beast_paint import _c, _mix, _streaks, bake_data, write_texture
from beast_body import PART
import eagle_body as EB


def _cut(region, c):
    x, y, z = c
    if region == 'trunk':
        return (z < 0.300) or (y < -0.165 and z < 0.350), x > 0
    if region == 'head':
        return z < 0.380 and y < -0.27, x > 0
    if region == 'tail':
        return z < 0.345, x > 0
    if region.startswith('hleg'):
        ax = float(np.interp(z, (0.13, 0.32), (0.080, 0.035)))
        ay = float(np.interp(z, (0.13, 0.27, 0.32), (0.032, -0.005, 0.030)))
        return y > ay, abs(x) > ax
    return None


UV_SCALE = {'head': 2.0, 'eye': 2.4, 'beak': 1.7, 'jaw': 1.2, 'feather': 0.85, 'wing': 0.8, 'foot': 1.2,
            'claw': 0.8}


def unwrap(ob, margin=0.0025, relax=30):
    return BP.unwrap(ob, _cut, UV_SCALE, None, margin, relax)


PRESETS = {   # 2026-10-24: tawny-gold hackles (not lemon), darker trousers and coverts, subtler bars on the remiges
    'golden': dict(body='#3b2a1d', fringe='#634a31', nape='#9a7a3c', nape_dark='#563c20', face='#2a1e16',
                   trouser='#5e4630', trouser_dark='#3f2e1d', vent='#5e4630', covert='#46342a',
                   covert_dark='#30231a', under='#2b2018',
                   flight='#241b15', flight_base='#3a3129', flight_bar='#211913', bar_k=0.45, patch='#bdb4a2',
                   patch_k=0.10, gcov='#33251a', gcov_base='#443427', tail='#231b15', tail_base='#5c5040',
                   tail_bar='#2f261d', tail_bar_k=0.50, white='#f1eee6', head_white=0.0, tail_white=0.0,
                   beak='#626a71', beak_tip='#1c1c1f', cere='#d9a92c', lower='#6f777e', gape='#d8a83a',
                   iris='#5a3210', iris_in='#76481b', foot='#d9aa2e', scute='#a07418', tarsus_bare=0.0,
                   claw='#141414', lid='#2a2018', lid_k=0.45, brow=0.65),
    'bald': dict(body='#3a2518', fringe='#553a27', nape='#3a2518', nape_dark='#2e1e14', face='#3a2518',
                 trouser='#3e281a', trouser_dark='#2c1c12', vent='#3a2518', covert='#40291b',
                 covert_dark='#2a1b12', under='#2c1c12',
                 flight='#211913', flight_base='#3a2e24', flight_bar='#1e1611', bar_k=0.45, patch='#3a2e24',
                 patch_k=0.0, gcov='#33241a', gcov_base='#40301f', tail='#ece8de', tail_base='#ece8de',
                 tail_bar='#ece8de', tail_bar_k=0.0, white='#f1eee6', head_white=1.0, tail_white=1.0,
                 beak='#e3ae2a', beak_tip='#d29a1e', cere='#e8b934', lower='#e0aa2a', gape='#e8b934',
                 iris='#eadf9c', iris_in='#f4ecc2', foot='#e6b630', scute='#b8861c', tarsus_bare=1.0,
                 claw='#161412', lid='#d6b85a', lid_k=0.30, brow=0.35),
}


def _cells(P, F, size, seed, stretch=0.62):
    """Feathers: a jittered 3D lattice in a space squeezed along the flow F (so the feathers come out longer than
    wide). -> (F2 - F1 in cell units: small at a feather's border, the offset from the feather's centre along the flow
    (+ toward its tip), a random 0..1 per feather)."""
    Q = P / size
    Q = Q + F * (Q * F).sum(-1, keepdims=True) * (stretch - 1.0)
    base = np.floor(Q).astype(np.int64)
    n = len(P)
    f1, f2 = np.full(n, 9.0), np.full(n, 9.0)
    along, rnd = np.zeros(n), np.zeros(n)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array((dx, dy, dz))
                j = np.stack([_hash3(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], -1)
                d = Q - (c + 0.15 + 0.7 * j)
                dist = np.sqrt((d * d).sum(-1))
                closer = dist < f1
                f2 = np.where(closer, f1, np.minimum(f2, dist))
                along = np.where(closer, (d * F).sum(-1), along)
                rnd = np.where(closer, _hash3(c[:, 0], c[:, 1], c[:, 2], seed + 7), rnd)
                f1 = np.where(closer, dist, f1)
    return f2 - f1, along, rnd


def _scallop(P, F, size, seed):
    edge, along, rnd = _cells(P, F, size, seed)
    fringe = smoothstep(0.16, 0.03, edge) * smoothstep(-0.05, 0.30, along)
    centre = smoothstep(0.35, 0.05, np.abs(along)) * smoothstep(0.05, 0.30, edge)
    return fringe, centre, rnd


def _trousers(P):
    """1 on the trousers (2026-10-24: within 5.5 cm of the thigh -> shin line, below the flank), 0 on the belly and
    flanks (the old mask, everything below z 0.30, painted the whole underside tawny)."""
    J = EB.J
    pts = [np.array(J[k], float) for k in ('HIP', 'KNEE', 'ANKLE')]
    Q = P * np.array((1.0, 1.0, 1.0))
    Q[:, 0] = np.abs(Q[:, 0])
    d = np.full(len(P), 9.0)
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        t = np.clip((Q - a) @ ab / (ab @ ab), 0, 1)
        d = np.minimum(d, np.linalg.norm(Q - (a + t[:, None] * ab), axis=1))
    low = np.maximum(smoothstep(0.255, 0.225, P[:, 2]), smoothstep(0.050, 0.075, Q[:, 0]) * smoothstep(0.30, 0.27, P[:, 2]))
    return smoothstep(0.062, 0.046, d) * low


def paint(D, preset='golden'):
    C = {k: (_c(v) if isinstance(v, str) else v) for k, v in PRESETS[preset].items()}
    valid = D['valid']
    Hh, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = np.clip(D['ao'].ravel()[idx], 0, 1)
    R = D['root'].reshape(-1, 3)[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    n = len(P)
    nz = N[:, 2]
    col = np.tile(C['body'], (n, 1))
    smooth = np.full(n, 0.16)
    big = fbm(P * 7.0, 3, seed=71)

    # ---------------------------------------------------------------- the body (fused) and the wing's flesh
    furp = part == PART['fur']
    wing = part == PART['wing']
    soft = furp | wing
    if soft.any():
        Ps, Ns = P[soft], N[soft]
        F = EB.flow(Ps, Ns)
        head = smoothstep(-0.250, -0.285, Ps[:, 1])
        legs = _trousers(Ps)
        fr1, ce1, r1 = _scallop(Ps, F, 0.017, 72)
        fr2, ce2, r2 = _scallop(Ps, F, 0.0085, 73)
        k = np.clip(head + legs * 0.6 + wing[soft], 0, 1)
        fr, ce, rr = fr1 * (1 - k) + fr2 * k, ce1 * (1 - k) + ce2 * k, r1 * (1 - k) + r2 * k
        st = _streaks(Ps, F, 74, across=0.0022, length=0.016, steps=6)
        ys, zs, xs = Ps[:, 1], Ps[:, 2], np.abs(Ps[:, 0])
        c = np.tile(C['body'], (len(Ps), 1)) * (0.84 + 0.30 * rr)[:, None]
        # the hind crown, nape and hindneck: tawny-gold hackles streaked with dark centres, fading forward into the
        # dark forehead and brow and down into the dark neck (2026-10-24: they were lemon yellow over the whole head)
        zc = np.interp(ys, (-0.32, -0.30, -0.26, -0.22, -0.19, -0.16), (0.404, 0.400, 0.392, 0.378, 0.366, 0.360))
        nape = (smoothstep(-0.318, -0.294, ys) * smoothstep(-0.145, -0.200, ys) *
                smoothstep(-0.006, 0.016, zs - zc) * (1 - wing[soft]))
        nape = nape * (0.80 + 0.20 * smoothstep(-0.29, -0.25, ys))
        nc = _mix(np.tile(C['nape'], (len(Ps), 1)), C['nape_dark'], 0.50 * smoothstep(0.35, 0.75, st) + 0.25 * ce)
        c = _mix(c, nc, nape)
        face = smoothstep(-0.298, -0.318, ys) * smoothstep(0.018, 0.0, zs - zc)
        c = _mix(c, C['face'], 0.6 * face)
        trouser = legs * (1 - wing[soft])
        tc = _mix(np.tile(C['trouser'], (len(Ps), 1)), C['trouser_dark'], 0.45 * smoothstep(0.4, 0.8, st) + 0.2 * ce)
        c = _mix(c, tc, trouser)
        vent = smoothstep(0.08, 0.13, ys) * smoothstep(0.345, 0.325, zs) * (1 - wing[soft])
        c = _mix(c, C['vent'], 0.75 * vent)
        # the wing's flesh: the upper coverts (the pale carpal bar of a golden eagle) on top, dark under the wing
        if wing.any():
            wm = wing[soft]
            # (2026-10-24) lesser and marginal coverts: small dark scallops with tawny edges, no flesh-coloured bar
            top = smoothstep(-0.2, 0.3, Ns[:, 2])
            wc = _mix(np.tile(C['covert'], (len(Ps), 1)), C['covert_dark'], 0.40 + 0.35 * ce - 0.25 * fr)
            wc = _mix(wc, C['fringe'], 0.30 * fr)
            wu = _mix(np.tile(C['under'], (len(Ps), 1)), C['covert_dark'], 0.35 * fr + 0.15 * ce)
            wc = _mix(wu, wc, top)
            c = np.where(wm[:, None], wc, c)
        # white head and tail coverts (the bald preset)
        if C['head_white'] > 0:
            hw = smoothstep(-0.195, -0.225, ys) * (1 - wing[soft])
            wcol = _mix(np.tile(C['white'], (len(Ps), 1)), _c('#cfc9bd'), 0.35 * fr + 0.15 * (1 - rr))
            c = _mix(c, wcol, hw)
        if C['tail_white'] > 0:
            tw = smoothstep(0.105, 0.135, ys) * (1 - wing[soft])
            c = _mix(c, np.tile(C['white'], (len(Ps), 1)) * (0.92 + 0.08 * rr)[:, None], tw)
        # fringes on every feather's tip (lighter on dark feathers, a shade darker on white ones)
        light = 1 - C['head_white'] * smoothstep(-0.195, -0.225, ys)
        c = _mix(c, C['fringe'], 0.35 * fr * light * (1 - nape) * (1 - trouser * 0.5))
        c = _mix(c, C['nape'], 0.20 * fr * nape)
        c = c * (0.90 + 0.12 * st)[:, None]
        # the brow's shadow over the eye (the stern look) and a thin, soft lid round the eyeball
        for sx, sfx in ((1, 'L'), (-1, 'R')):
            e0 = np.array(D['eyes']['eye_' + sfx])
            ne = np.array(EB.EYE_N) * np.array((sx, 1, 1))
            de = Ps - e0
            brow = (smoothstep(0.022, 0.010, np.abs(de[:, 1] + 0.002)) * smoothstep(0.004, 0.010, de[:, 2]) *
                    smoothstep(0.020, 0.012, de[:, 2]) * smoothstep(0.012, 0.030, sx * Ps[:, 0]))
            c = _mix(c, C['face'] * 0.6, C['brow'] * brow)
            along = de @ ne
            r = np.linalg.norm(de - along[:, None] * ne, axis=1)
            lid = smoothstep(0.0098, 0.0080, r) * smoothstep(0.0050, 0.0064, r) * smoothstep(-0.006, -0.001, along)
            c = _mix(c, C['lid'], C['lid_k'] * lid)
        # the gape: soft yellow skin along the mouth line from the beak back to below the eye's front
        a0, a1 = np.array((-0.341, 0.3862)), np.array((-0.311, 0.3890))
        q = np.stack([ys, zs], -1) - a0
        ab = a1 - a0
        tt = np.clip(q @ ab / (ab @ ab), 0, 1)
        dist = np.linalg.norm(q - tt[:, None] * ab, axis=1)
        gape = smoothstep(0.0030, 0.0008, dist) * smoothstep(1.0, 0.55, tt) * smoothstep(0.009, 0.015, xs)
        c = _mix(c, C['gape'], 0.60 * gape)
        col[soft] = c
        smooth[soft] = 0.14 + 0.06 * rr

    # ---------------------------------------------------------------- feather cards
    card = part == PART['feather']
    if card.any():
        u, v, fid = R[card, 0], np.clip(R[card, 1], 0, 1), R[card, 2]
        kind = np.floor(fid + 1e-3).astype(int)
        ki = np.rint((fid - kind) * 100).astype(int)
        m = len(u)
        rr = _hash3(kind, ki, (x[card] > 0).astype(np.int64), 81)
        au = np.abs(u)
        wob = 0.06 * vnoise(np.stack([u * 2.0, v * 6.0, kind * 3.0 + ki], -1), seed=82)
        flight = (kind == 1) | (kind == 2) | (kind == 3)
        tail = kind == 7
        c = np.tile(C['flight'], (m, 1))
        # flight feathers: greyer, barred bases; a dark trailing band; a faint pale patch on the inner primaries
        base = _mix(np.tile(C['flight_base'], (m, 1)), C['flight'], smoothstep(0.45, 0.85, v + wob))
        nb = np.where(kind == 1, 7.0, 6.0)
        bars = 0.5 + 0.5 * np.sin(2 * np.pi * (v * nb + 0.18 * au + wob * 3 + rr))
        bar = smoothstep(0.62, 0.90, bars) * smoothstep(0.78, 0.55, v) * (0.55 + 0.45 * (u > 0))
        base = _mix(base, C['flight_bar'], C['bar_k'] * bar)
        patch = (((kind == 1) & (ki <= 5)) | ((kind == 2) & (ki <= 4))) * smoothstep(0.42, 0.18, v) * (u > -0.2)
        base = _mix(base, C['patch'], C['patch_k'] * patch)
        c = np.where(flight[:, None], base, c)
        # tail: barred grey-brown, a broad dark band at the tip (golden); white (bald)
        tb = _mix(np.tile(C['tail_base'], (m, 1)), C['tail_bar'],
                  C['tail_bar_k'] * smoothstep(0.6, 0.9, 0.5 + 0.5 * np.sin(2 * np.pi * (v * 5.0 + 0.25 * au + wob * 4 + rr))) *
                  smoothstep(0.75, 0.6, v))
        tb = _mix(tb, C['tail'], smoothstep(0.66, 0.76, v + wob))
        if C['tail_white'] > 0:
            tb = np.tile(C['white'], (m, 1)) * (0.90 + 0.08 * rr + 0.04 * v)[:, None]
        c = np.where(tail[:, None], tb, c)
        # coverts: dark centres, paler bases, a pale fringe round the tip
        cov = (kind == 4) | (kind == 5) | (kind == 6)
        # (2026-10-24) low contrast: folded, the stacked coverts' bases and edges read as steps
        gc = _mix(np.tile(C['gcov_base'], (m, 1)), C['gcov'], 0.55 + 0.45 * smoothstep(0.10, 0.50, v + wob))
        gc = _mix(gc, C['fringe'], 0.35 * smoothstep(0.82, 0.98, v) + 0.10 * smoothstep(0.75, 1.0, au))
        c = np.where(cov[:, None], gc, c)
        # scapulars: the back's own dark brown, darker centres, a pale fringe at the tip
        scap = kind == 8
        sc = _mix(np.tile(C['body'], (m, 1)), C['body'] * 0.78, 0.5 * smoothstep(0.25, 0.65, v + wob))
        sc = _mix(sc, C['fringe'], 0.5 * smoothstep(0.82, 0.98, v) + 0.25 * smoothstep(0.8, 1.0, au))
        c = np.where(scap[:, None], sc, c)
        # shaft, vane edges, a little life
        sw = 0.07 * (1 - 0.6 * v)
        shaft = smoothstep(sw, sw * 0.4, au)
        white = tail & (C['tail_white'] > 0)
        c = _mix(c, np.where(white[:, None], _c('#c8c2b6'), _c('#8a7a62')), 0.45 * shaft * smoothstep(0.05, 0.2, v))
        c = c * (1.0 - 0.08 * smoothstep(0.75, 1.0, au) * (1 - white))[:, None]
        var = np.where(cov | scap, 0.05, 0.10)                 # less card-to-card change on the coverts
        c = c * (1.0 - var + var * rr + 0.05 * vnoise(np.stack([u * 1.5, v * 30.0, ki * 1.0], -1), seed=83))[:, None]
        col[card] = c
        smooth[card] = 0.20 + 0.08 * shaft

    # ---------------------------------------------------------------- bare parts
    # (2026-10-24) the beak by its own coordinates (R: h 0 cutting edge .. 1 ridge, t 0 base .. 1 tip): horn darkening
    # to the hook, the yellow cere over the base (its front edge slanting back down the sides), the nostril, a thin dark
    # cutting edge; the lower mandible in the same colours (no dark bar), yellowish at the gape
    beak = part == PART['beak']
    if beak.any():
        h, t = R[beak, 0], R[beak, 1]
        bc = _mix(np.tile(C['beak'], (beak.sum(), 1)), C['beak_tip'], smoothstep(0.30, 0.72, t))
        edge = 0.115 + 0.075 * h
        cere = smoothstep(edge + 0.022, edge - 0.008, t)
        bc = _mix(bc, C['cere'], cere)
        nos = smoothstep(1.0, 0.55, np.hypot((t - 0.105) / 0.030, (h - 0.62) / 0.10))
        bc = _mix(bc, _c('#2a1c10'), 0.85 * nos)
        bc = _mix(bc, C['beak_tip'] * 0.7, 0.55 * smoothstep(0.07, 0.015, h) * (1 - cere))
        col[beak] = bc
        smooth[beak] = 0.55 - 0.15 * cere
    jaw = part == PART['jaw']
    if jaw.any():
        h, t = R[jaw, 0], R[jaw, 1]
        jc = _mix(np.tile(C['lower'], (jaw.sum(), 1)), C['beak_tip'], smoothstep(0.40, 0.85, t))
        jc = _mix(jc, C['gape'], 0.65 * smoothstep(0.32, 0.10, t))
        jc = _mix(jc, C['beak_tip'] * 0.7, 0.5 * smoothstep(0.90, 0.98, h))
        col[jaw] = jc
        smooth[jaw] = 0.50
    eye = part == PART['eye']
    if eye.any():
        ec = np.tile(_c('#050404'), (n, 1))
        for sfx, sx in (('L', 1), ('R', -1)):
            c0 = np.array(D['eyes']['eye_' + sfx])
            ne = np.array(EB.EYE_N) * np.array((sx, 1, 1))
            ne /= np.linalg.norm(ne)
            upv = np.array((0.0, 0.0, 1.0)) - ne[2] * ne
            upv /= np.linalg.norm(upv)
            d = P - c0
            along = d @ ne
            r = np.linalg.norm(d - along[:, None] * ne, axis=1) / EB.EYE_R     # 0 the axis .. 1 the cap's rim
            e2 = _mix(np.tile(C['iris_in'], (n, 1)), C['iris'], smoothstep(0.30, 0.48, r))
            e2 = _mix(e2, C['iris'] * 0.55, smoothstep(0.55, 0.72, r))         # the iris' dark outer edge
            e2 = _mix(e2, _c('#060505'), smoothstep(0.30, 0.25, r))           # the pupil
            e2 = e2 * (1.0 - 0.35 * smoothstep(0.0, 0.5, (d @ upv) / EB.EYE_R))[:, None]   # the brow's shadow
            side = (x > 0) if sx > 0 else (x <= 0)
            ec = np.where(side[:, None], e2, ec)
        col[eye] = ec[eye]
        smooth[eye] = 0.92
    foot = part == PART['foot']
    if foot.any():
        zf, Pf = z[foot], P[foot]
        ball = np.array(EB.J['BALL'])
        bx = np.stack([ball[0] * np.sign(x[foot]), np.full(foot.sum(), ball[1])], -1)
        dist = np.linalg.norm(Pf[:, :2] - bx, axis=1)
        scutes = smoothstep(0.55, 0.95, 0.5 + 0.5 * np.sin(2 * np.pi * dist / 0.0065))
        fcol = _mix(np.tile(C['foot'], (foot.sum(), 1)), C['scute'], 0.45 * scutes * smoothstep(-0.2, 0.4, nz[foot]))
        reti = smoothstep(0.1, 0.0, np.abs(vnoise(Pf * 420.0, seed=84)))
        fcol = _mix(fcol, C['scute'], 0.35 * reti)
        sock = EB.J['ANKLE'][2] + (EB.J['BALL'][2] - EB.J['ANKLE'][2]) * EB.TARSUS_SOCK   # the sock's end
        bare_top = 0.034 + (sock - 0.002 - 0.034) * C['tarsus_bare']        # feathered above this height
        feathered = smoothstep(bare_top - 0.006, bare_top + 0.006, zf)
        F2 = np.tile(np.array((0.0, 0.2, -1.0)), (foot.sum(), 1))
        st = _streaks(Pf, F2 / np.linalg.norm(F2[0]), 85, across=0.0018, length=0.012, steps=5)
        fe = _mix(np.tile(C['trouser'], (foot.sum(), 1)), C['trouser_dark'], 0.5 * smoothstep(0.35, 0.8, st))
        col[foot] = _mix(fcol, fe, feathered)
        smooth[foot] = 0.32 * (1 - feathered) + 0.14 * feathered
    claw = part == PART['claw']
    if claw.any():
        col[claw] = _mix(np.tile(C['claw'], (claw.sum(), 1)), _c('#4a4642'),
                         0.25 * smoothstep(0.2, 0.9, vnoise(P[claw] * 300, seed=86) * 0.5 + 0.5))
        smooth[claw] = 0.62

    # ---------------------------------------------------------------- light and AO baked in, gently
    light = 0.88 + 0.18 * (nz * 0.5 + 0.5)
    aot = 0.60 + 0.40 * ao
    shaded = col * (light * aot)[:, None]
    shaded = np.where(card[:, None], col * (0.86 + 0.14 * ao)[:, None], shaded)
    shaded = np.where(eye[:, None], col, shaded)
    out = np.zeros((Hh * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(Hh * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(Hh, Wd, 3), sm.reshape(Hh, Wd)


TEX = {'golden': "T_Eagle", 'bald': "T_Eagle_Bald"}
MAT = {'golden': "M_Eagle", 'bald': "M_Eagle_Bald"}


def build_textures(ob, size=1024, D=None):
    """Both presets: T_Eagle (golden), T_Eagle_Bald, materials M_Eagle / M_Eagle_Bald (back faces culled: the cards
    have an underside of their own). M_Eagle ends up on the body. -> (paths, coverage)"""
    import bpy, deer_paint
    D = D if D is not None else bake_data(ob, size=size, ao_dist=0.10, roots=True)
    paths = []
    for name in ('bald', 'golden'):
        col, smooth = paint(D, name)
        paths.append(write_texture(D, col, smooth, TEX[name], ob, MAT[name]))
        m = bpy.data.materials[MAT[name]]
        deer_paint.matte(m)
        m.use_backface_culling = True
        m.use_fake_user = True                     # the preset not on the body survives the save
    return paths[::-1], float(D['valid'].mean())


def use_preset(name):
    import bpy
    ob = bpy.data.objects[EB.BODY]
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials[MAT[name]])
