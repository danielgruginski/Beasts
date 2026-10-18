"""The hydra's head (2026-10-17), one design for all three necks: the dragon's finished head, scaled down.

Daniel chose three heads ("Three heads is better, I think. The proportions are good"). A first head of its own
(simple profiles) came back with every problem the dragon's face had been through: a straight jaw line, a flat
snout... Daniel: "The hydra head has the very same issues that existed on the dragon head. I was expecting you to
base the mesh on the finished dragon head." So this is dragon_head's melted field and mesh -- the jaw line, the curved
snout, the hanging lip, the lids, the masseter weights -- at SCALE, without what made it a dragon: the horns, the
crown and cheek spikes, the jaw hooks and the frill (all separate pieces on the dragon, simply not added here).

What the hydra adds: the pleated gill fans behind the jaws (the brief: "more aquatic like, no spikes, no wings"), its
own colours, and teeth that answer two of the dragon's parked head notes -- a row varied in size, spacing and lean
with a gap and a broken tooth (the dragon's "perfect line"), the showing front teeth coming out from under the lip's
edge instead of through its side. The dragon itself is not changed.

Head space: metres, the poll (the neck's end) at the origin, the snout toward -Y, left +X -- hydra_body's local head
frame (head_matrix places it on each neck). Dragon head space times SCALE.
"""
import math
import numpy as np
import bmesh
from mathutils import Vector

from beast_common import cone, smoothstep
import dragon_head as DH

SCALE = 0.80                        # the dragon's head is 1.42 m to the snout tip; the hydra's 1.14 m
TARGET_TRIS = 8000                  # per head (the dragon's is 12k); three of them

HINGE = tuple(np.array(DH.HINGE) * SCALE)
CHIN_TIP = tuple(np.array(DH.CHIN_TIP) * SCALE)
MOUTH = tuple(np.array(DH.MOUTH) * SCALE)
SNOUT_TIP = (0.0, -1.42 * SCALE, -0.04 * SCALE)

# the gill fin behind each jaw (hydra head space): a rounded, pleated fan (a fish's, not a frill of spines): its root
# along the back of the cheek, opening back and out over an arc, the edge gently scalloped; sea green at the root,
# coral at the edge
GILL = dict(root=(0.24, 0.05, -0.04), back=(0.50, 0.87, 0.0), up=(0.0, 0.0, 1.0), radius=0.38,
            arc=(-75.0, 70.0), pleats=5, pleat=0.022)

COL = dict(back="1f4a44", belly="c9c08a", mouth="5a2a2a", tooth="e8e2cc", eye="e8d040", pupil="0c0a06",
           gill="c06a58", fin="2f6e66", tongue="8a4a44")


# ----------------------------------------------------------------------------------------- colours (dragon space)
def head_colors(P, rgb):
    """dragon_head.head_colors with the hydra's palette (no horns): the mouth's lining along the slit, the pale band
    under the jaw, the back colour elsewhere. P in dragon head space."""
    y, z = P[:, 1], P[:, 2]
    mouth = (y < DH.Y_CORNER + 0.02) & (y > -1.33) & (np.abs(np.abs(z - DH.lip(y)) - DH.gap(y) / 2) < 0.008) & \
        (np.abs(P[:, 0]) < DH.at(DH.JAW, y, 1) - 0.03)
    k = smoothstep(DH.at(DH.JAW, y, 3) + 0.10, DH.at(DH.JAW, y, 3) + 0.03, z) * (z < DH.lip(y) - 0.05)
    back, belly = np.array(rgb(COL["back"])), np.array(rgb(COL["belly"]))
    return [rgb(COL["mouth"]) if mouth[i] else tuple(back * (1 - k[i]) + belly * k[i]) for i in range(len(P))]


# ----------------------------------------------------------------------------------------- teeth (dragon space)
def _rand(i, salt):
    h = (i * 374761393 + salt * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def build_teeth(bm, upper=True):
    """dragon_head's tooth layout, varied: each tooth a little longer or shorter, nudged along the gum, leaning a
    little, one missing and one broken off per side (the dragon's row reads as "a perfect line"). The showing front
    teeth root inside the hanging lip, further in, and come out from under its edge (the dragon's canine pokes out
    through the side of the lip)."""
    teeth = DH.UPPER_TEETH if upper else [(y, L, r, False) for y, L, r in DH.LOWER_TEETH]
    for s in (1, -1):
        salt = (1 if upper else 2) * 10 + (1 if s > 0 else 2)
        gap_i = 6 if s > 0 else 8                         # a missing tooth (back in the row, not a showing one)
        broken_i = 4 if s > 0 else 5
        for i, (y, L, r, shows) in enumerate(teeth):
            if i == gap_i:
                continue
            a, b, c = _rand(i, salt), _rand(i, salt + 3), _rand(i, salt + 7)
            y = y + 0.025 * (a - 0.5) * (0 if shows else 1)
            L = L * (0.80 + 0.40 * b) * (0.45 if i == broken_i else 1.0)
            lean = 0.12 * (c - 0.5)
            lz, g = float(DH.lip(y)), float(DH.gap(y)) / 2
            if upper:
                if shows:                                   # inside the hanging lip, out from under its edge
                    x = s * (float(DH.at(DH.MUZZLE, y, 1)) - 0.052)
                else:
                    x = s * (float(DH.at(DH.JAW, y, 1)) - 0.09)
                base, tip = (x, y, lz + g + 0.03), (x * 1.01, y + 0.012, lz - L)
                bend = (s * lean * L, 0.25 * L, 0)
            else:
                x = s * (float(DH.at(DH.JAW, y, 1)) - 0.07)
                base, tip = (x, y, lz - g - 0.03), (x, y - 0.010, lz + L)
                bend = (s * lean * L, 0.20 * L, 0)
            cone(bm, base, tip, r * (0.9 + 0.2 * b), seg=6, bend=bend)


# ----------------------------------------------------------------------------------------- gills (hydra space)
def build_gill(bm, s, n_r=6, n_a=36):
    """The gill fin: a fan from its root over GILL's arc, pleated (waves across the fan, growing outward), the edge
    rounded and gently scalloped between the pleats. -> per-vertex 0 (root) .. 1 (edge), for the colour"""
    G = GILL
    root = np.array(G["root"]) * (s, 1, 1)
    d1 = np.array(G["back"], float) * (s, 1, 1)
    d1 /= np.linalg.norm(d1)
    d2 = np.array(G["up"], float)
    d2 -= d1 * (d1 @ d2)
    d2 /= np.linalg.norm(d2)
    nrm = np.cross(d1, d2)
    a0, a1 = (math.radians(a) for a in G["arc"])
    out, rings = [0.0], []
    vr = bm.verts.new(Vector(root))
    for i in range(1, n_r + 1):
        u = i / n_r
        ring = []
        for j in range(n_a + 1):
            v = j / n_a
            th = a0 + (a1 - a0) * v
            wave = math.sin(v * math.pi * 2 * G["pleats"])
            R = G["radius"] * (0.92 + 0.08 * abs(math.cos(v * math.pi * G["pleats"]))) * \
                (0.75 + 0.25 * math.sin(math.pi * v))
            p = root + R * u * (math.cos(th) * d1 + math.sin(th) * d2) + nrm * G["pleat"] * wave * u ** 1.3
            ring.append(bm.verts.new(Vector(p)))
            out.append(u)
        rings.append(ring)
    for j in range(n_a):
        bm.faces.new((vr, rings[0][j], rings[0][j + 1]))
    for i in range(n_r - 1):
        for j in range(n_a):
            bm.faces.new((rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]))
    return out


# ----------------------------------------------------------------------------------------- assembly
_SKIN = {}


def skin(rgb, rebuild=False):
    """The dragon's melted head (built once, shared by every neck), in hydra head space. -> dict(V, F, jaw, cols,
    rep)"""
    if rebuild or not _SKIN:
        bm, dense = DH.build_head_mesh(target=TARGET_TRIS)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        P = np.array([v.co[:] for v in bm.verts])            # dragon head space
        F = [[v.index for v in f.verts] for f in bm.faces]
        _SKIN.update(V=P * SCALE, F=F, jaw=DH.jaw_weight(P), cols=head_colors(P, rgb),
                     rep=dict(dense_tris=dense, tris=len(F), bridges=DH.bridges(bm)))
        bm.free()
    return _SKIN


def build(acc, fins, M, nid, rgb):
    """One head into the body's Acc (and its gill fins into `fins`), placed by M (hydra head space -> body),
    weighted to Head<nid> / Jaw<nid>. -> report"""
    S = skin(rgb)
    hb, jb = f"Head{nid}", f"Jaw{nid}"
    W = [{jb: float(w), hb: 1.0 - float(w)} if 0.0 < w < 1.0 else {(jb if w >= 1.0 else hb): 1.0} for w in S["jaw"]]
    _add_arrays(acc, M, S["V"], S["F"], W, S["cols"])

    def shell(target, fn, bone, color, scale=SCALE):
        tmp = bmesh.new()
        out = fn(tmp)
        n = len(tmp.verts)
        if color == "eye":
            cols = [rgb(COL["pupil"]) if p else rgb(COL["eye"]) for p in out]
        elif color == "gill":                                   # sea green at the root to coral at the edge
            a, b = np.array(rgb(COL["fin"])), np.array(rgb(COL["gill"]))
            cols = [tuple(a * (1 - t) + b * t) for t in smoothstep(0.35, 1.0, np.array(out))]
        else:
            cols = [rgb(color)] * n
        _add_bm(target, M, tmp, [{bone: 1.0}] * n, cols, scale)

    shell(acc, lambda bm: build_teeth(bm, True), hb, COL["tooth"])
    shell(acc, lambda bm: build_teeth(bm, False), jb, COL["tooth"])
    shell(acc, DH.build_tongue, jb, COL["tongue"])
    for s in (1, -1):
        shell(acc, lambda bm, s=s: DH.build_eye(bm, s), hb, "eye")
        shell(fins, lambda bm, s=s: build_gill(bm, s), hb, "gill", scale=1.0)
    return dict(S["rep"])


def _xf(M, P):
    R = np.array(M.to_3x3())
    t = np.array(M.translation)
    return P @ R.T + t


def _add_arrays(acc, M, V, F, weights, cols):
    Q = _xf(M, V)

    def build(target):
        vmap = [target.verts.new(Vector(q)) for q in Q]
        for f in F:
            try:
                target.faces.new([vmap[i] for i in f])
            except ValueError:
                pass
        return weights
    acc.add(build, None, cols)


def _add_bm(acc, M, bm, weights, cols, scale=SCALE):
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    V = np.array([v.co[:] for v in bm.verts]).reshape(-1, 3) * scale
    F = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    _add_arrays(acc, M, V, F, weights, cols)
