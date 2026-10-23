"""UVs and the painted skin of the leech (the framework is beast_paint.py), 2026-10-23.

UVs: every seam comes from the builder (no skin regions: the leech has no heat-weighted part): down the belly, round
the body at two rings (three short pieces pack better than one 1.8 m strip), round the lip (the cup is its own
island); the teeth and the rear disc carry their lofts' seams.

Paint (my calls; a medicinal leech made big and swampy): the back dark olive to black, two rows of rusty orange spots
along it and a thin broken pale stripe down the middle, the sides olive, the belly a mottled yellow-olive with black
blotches; fine dark rings every 12.5 mm (the annuli) with pale sensory dots on every fifth; five pairs of eye spots on
the head; a dark red cup inside the oral sucker, pale teeth, a black throat; wet and glossy all over.
"""
import math
import numpy as np
import beast_paint as BP
from beast_common import smoothstep, fbm, vnoise
from beast_paint import _c, _mix, bake_data, write_texture
from beast_body import PART
import leech_body as LB

UV_SCALE = {'fur': 1.0, 'tooth': 0.5, 'sucker': 0.6}


def unwrap(ob, margin=0.004, relax=30):
    return BP.unwrap(ob, lambda region, c: None, UV_SCALE, None, margin, relax)


C = dict(back='#14170e', back2='#262a14', side='#3a3e1c', belly='#6e6a30', belly_dark='#1c1a10', spot='#a8501c',
         spot_edge='#4a2210', stripe='#9a8a4a', ring='#0a0b06', papilla='#9a9a6a', eye='#000000',
         lip='#3a2224', cup='#5a1414', throat='#0a0404', tooth='#d8cca0', tooth_root='#8a7a50',
         disc='#4a4824', disc_rim='#222010')


def paint(D):
    Cc = {k: _c(v) for k, v in C.items()}
    valid = D['valid']
    Hh, Wd = valid.shape
    idx = np.nonzero(valid.ravel())[0]
    P = D['P'].reshape(-1, 3)[idx]
    N = D['N'].reshape(-1, 3)[idx]
    part = D['part'].ravel()[idx]
    ao = D['ao'].ravel()[idx]
    aux = D['aux'].ravel()[idx]
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    n = len(P)
    nz = N[:, 2]
    u = LB.y_of(0.0) - y                                    # arc position from the rear tip (rest pose: straight)
    hw = np.array([LB.half_width(v) for v in np.clip(u, 0, LB.L0)])
    xs = x / np.maximum(hw, 1e-3)                           # across the body: -1 .. 1
    big = fbm(P * 4.0, 3, seed=101)
    mid = fbm(P * 14.0, 3, seed=102)
    col = np.zeros((n, 3))
    smooth = np.full(n, 0.55)

    body = part == PART['fur']
    cup = body & (u > LB.L0 - 0.004) & (np.abs(y - LB.y_of(LB.L0)) < 0.07) & (N[:, 1] > -0.2)   # the cup faces in
    back = smoothstep(-0.1, 0.5, nz)
    belly = smoothstep(0.0, -0.6, nz)
    bc = _mix(np.tile(Cc['back'], (n, 1)), Cc['back2'], 0.5 * smoothstep(-0.2, 0.6, big))
    bc = _mix(bc, Cc['side'], (1 - back) * (1 - belly) * 0.8)
    blot = smoothstep(0.15, 0.45, fbm(P * 9.0, 2, seed=103))
    bel = _mix(np.tile(Cc['belly'], (n, 1)), Cc['belly_dark'], 0.85 * blot)
    bc = _mix(bc, bel, belly)
    # the rows of rusty spots either side of the midline, the broken pale stripe
    k = np.round((u - 0.10) / 0.11)
    du = (u - 0.10 - k * 0.11) / 0.040
    for sx in (1, -1):
        dx = (xs - sx * 0.42) / 0.16
        spot = smoothstep(1.0, 0.6, np.sqrt(du * du + dx * dx) + 0.15 * mid) * back
        bc = _mix(bc, Cc['spot_edge'], spot)
        bc = _mix(bc, Cc['spot'], smoothstep(0.75, 0.3, np.sqrt(du * du + dx * dx) + 0.15 * mid) * back)
    stripe = smoothstep(0.07, 0.03, np.abs(xs)) * back * smoothstep(-0.1, 0.3, np.sin(u * 2 * math.pi / 0.09 + 2 * mid))
    bc = _mix(bc, Cc['stripe'], 0.7 * stripe * smoothstep(0.12, 0.25, u) * smoothstep(LB.L0 - 0.08, LB.L0 - 0.18, u))
    # the annuli: thin dark rings, pale dots on every fifth
    fr = (u / 0.0125) % 1.0
    ring = smoothstep(0.22, 0.0, np.abs(fr - 0.5) * 2 - 0.55)
    bc = _mix(bc, Cc['ring'], 0.45 * ring)
    fifth = smoothstep(0.004, 0.0015, np.abs(((u + 0.00625) % 0.0625) - 0.03125))
    dots = smoothstep(0.55, 0.85, vnoise(np.stack([x * 120, u * 40, z * 120], 1), seed=104))
    bc = _mix(bc, Cc['papilla'], 0.7 * fifth * dots * (1 - belly))
    # eye spots: five pairs on the head's top
    eyes = np.zeros(n)
    for i in range(5):
        eu = LB.L0 - 0.020 - i * 0.012
        for sx in (1, -1):
            d = np.hypot((u - eu) / 0.004, (xs - sx * (0.18 + 0.07 * i)) / 0.06)
            eyes = np.maximum(eyes, smoothstep(1.0, 0.6, d))
    bc = _mix(bc, Cc['eye'], eyes * back)
    lip = smoothstep(LB.L0 - 0.03, LB.L0 - 0.005, u)
    bc = _mix(bc, Cc['lip'], 0.8 * lip)
    cc = _mix(np.tile(Cc['cup'], (n, 1)), Cc['throat'], smoothstep(0.012, 0.050, LB.y_of(LB.L0) - y + 0.0) * 1.0)
    bc = np.where(cup[:, None], cc, bc)
    col = np.where(body[:, None], bc, col)
    smooth = np.where(body, 0.62 + 0.12 * back - 0.25 * ring * 0.0, smooth)
    tooth = part == PART['tooth']
    if tooth.any():
        tc = _mix(np.tile(Cc['tooth_root'], (n, 1)), Cc['tooth'], smoothstep(0.0, 0.6, vnoise(P * 200.0, seed=105) * 0.5 + 0.5))
        col = np.where(tooth[:, None], tc, col)
        smooth = np.where(tooth, 0.5, smooth)
    disc = part == PART['sucker']
    if disc.any():
        dc = _mix(np.tile(Cc['disc'], (n, 1)), Cc['disc_rim'], 0.6 * smoothstep(0.012, 0.02, z) + 0.4 * blot)
        col = np.where(disc[:, None], dc, col)
        smooth = np.where(disc, 0.5, smooth)
    light = 0.86 + 0.20 * (nz * 0.5 + 0.5)
    aot = 0.55 + 0.45 * np.clip(ao, 0, 1)
    shaded = col * (light * aot)[:, None]
    out = np.zeros((Hh * Wd, 3))
    out[idx] = np.clip(shaded, 0, 1)
    sm = np.zeros(Hh * Wd)
    sm[idx] = np.clip(smooth, 0, 1)
    return out.reshape(Hh, Wd, 3), sm.reshape(Hh, Wd)


def build_texture(ob, size=1024):
    D = bake_data(ob, size=size, ao_dist=0.10)
    col, smooth = paint(D)
    path = write_texture(D, col, smooth, "T_Leech", ob, "M_Leech")
    return [path], float(D['valid'].mean())
