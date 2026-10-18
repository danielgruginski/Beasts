"""The war mammoth's driver tack (2026-10-18): what an orc driver sits on. Daniel: "orc mammoth riders"; his pick, a
single driver on the neck (not a howdah crew, not a back saddle). One mesh on MammothRig, MammothTack, its own
texture (T_MammothTack 512) painted by warg_tack's painter (cloth, leather, rope):

  - the rug: thick red felt with an ochre border, draped over the dip between the head's dome and the shoulder hump
    and down both sides of the neck;
  - the foot rope: a thick hemp rope round the neck just behind the ears (the driver's feet tuck under it, as a
    mahout's do), a second rope round the neck behind the rug holding it down;
  - the grip: a short rope loop standing up from the foot rope in front of the rug, for the driver's left fist;
  - Socket_Driver (a bone on Neck1, mammoth_body.rest_bones) is where the driver's root sits, on the rug.

Fitted like the warg's tack: every point is a ray cast onto the fur (mammoth_body's fused hide, not the hair), lifted
off it; the weights copy the skin's where it was cast. Point attribute "info" as warg_tack.
"""
import bpy, math
import numpy as np
from mathutils import Vector
import warg_tack as WT
from warg_tack import _Build, band, patch, ring, _skin, _fur_bvh, _on
from beast_common import mesh_obj, get_coll, remove_obj

SKIN = WT.SKIN
RUG = dict(y=(-1.56, -1.08), phi=74, rows=9, cols=13, top=0.045)     # world y; degrees round the neck from the top
FOOT_Y = -1.65                                                        # the foot rope, behind the ears
BACK_Y = -1.06
GRIP_W, GRIP_H = 0.13, 0.11                                           # the left fist's rope loop, half-width / height
REACH = 1.4


def _neck_centre(y):
    """The neck's axis (world) at y: under the top, roughly half the neck's depth down."""
    top = float(np.interp(y, (-1.75, -1.60, -1.45, -1.30, -1.10), (3.17, 3.14, 2.98, 2.83, 2.95)))
    return Vector((0.0, y, top - 0.55))


def _round(bvh, y, phi):
    """The fur round the neck axis at y, phi degrees from the top toward the left (+x)."""
    c = _neck_centre(y)
    t = math.radians(phi)
    d = Vector((math.sin(t), 0.0, math.cos(t)))
    return _on(bvh, c + d * REACH, c)


def _rope(B, bvh, y, phis, lift, bind=None):
    pts, nrm = [], []
    for phi in phis:
        p, n = _round(bvh, y, phi)
        if p is not None:
            pts.append(p)
            nrm.append(n)
    closed = abs((phis[-1] - phis[0]) % 360) < 1e-6
    if closed:
        pts, nrm = pts[:-1], nrm[:-1]
    band(B, pts, nrm, 0.045, 0.030, lift, 'rope', bind or (lambda k, p: (SKIN, p)), closed=closed)
    return pts, nrm


def build_tack(body=None, rig=None):
    body = body or bpy.data.objects["MammothBody"]
    rig = rig or bpy.data.objects.get("MammothRig")
    bvh = _fur_bvh(body)
    B = _Build()
    skin = lambda p: (SKIN, p)
    # the rug
    ry, rp = RUG['y'], RUG['phi']
    grid = []
    for y in np.linspace(ry[0], ry[1], RUG['rows']):
        row = []
        for phi in np.linspace(-rp, rp, RUG['cols']):
            row.append(_round(bvh, float(y), float(phi)))
        grid.append(row)
    for i in range(len(grid)):                          # a miss takes its neighbour's point
        for j in range(len(grid[0])):
            if grid[i][j][0] is None:
                k = min(range(len(grid[0])), key=lambda jj: abs(jj - j) if grid[i][jj][0] is not None else 99)
                grid[i][j] = grid[i][k]
    patch(B, grid, lambda i, j: RUG['top'], 'cloth', skin, base=0.004)
    # the ropes round the neck: the foot rope behind the ears, one behind the rug
    ring_phis = list(np.linspace(180.0, 540.0, 29))      # from under the neck round: the UV seam hides below
    front, fn = _rope(B, bvh, FOOT_Y, ring_phis, 0.006)
    _rope(B, bvh, BACK_Y, ring_phis, RUG['top'] + 0.004)
    # the grip: a loop standing up off the foot rope at the top, leaning back toward the driver
    p0, n0 = _round(bvh, FOOT_Y, 0.0)
    base = p0 + n0 * 0.03
    pts = []
    for k in range(9):
        a = math.pi * k / 8
        pts.append(base + Vector((-GRIP_W * math.cos(a), 0.06 * math.sin(a), GRIP_H * math.sin(a))))
    nrm = [Vector((0, 1, 0.4)).normalized()] * len(pts)
    band(B, pts, nrm, 0.030, 0.026, 0.0, 'rope', (SKIN, p0), bottom=True)
    B.bm.verts.index_update()
    bind = [B.bind[v] for v in sorted(B.bind, key=lambda v: v.index)]
    remove_obj("MammothTack")
    coll = get_coll("MAM_Body") if "MAM_Body" in bpy.data.collections else body.users_collection[0]
    bm = B.bm
    bm.verts.ensure_lookup_table()
    info = {v.index: B.info[v] for v in bm.verts}
    ob = mesh_obj("MammothTack", bm, coll, recalc=False)
    att = ob.data.color_attributes.new("info", 'FLOAT_COLOR', 'POINT')
    rgba = np.zeros((len(ob.data.vertices), 4), np.float32)
    for i, (part, along, across) in info.items():
        rgba[i] = (part / 255.0, along, across, 1.0)
    att.data.foreach_set('color', rgba.ravel())
    for p in ob.data.polygons:
        p.use_smooth = True
    if rig is not None:
        _skin(ob, body, rig, bind)
    return ob


def unwrap(ob):
    """UVs from the stored coordinates (smart-UV cut the rug into odd islands and gave the 5 m ropes most of the
    sheet): the rug is one sheet (across, along) in the top 70 %; each rope a strip below it (along, across) --
    foot rope, back rope, grip."""
    me = ob.data
    att = me.color_attributes["info"]
    buf = np.empty(len(me.vertices) * 4, np.float32)
    att.data.foreach_get('color', buf)
    info = buf.reshape(-1, 4)
    part = np.rint(info[:, 0] * 255).astype(int)
    co = np.array([v.co[:] for v in me.vertices])
    cloth = part == WT.TACK_PART['cloth']
    amax = max(float(info[cloth, 1].max()), 1e-3)
    strip = np.where(np.abs(co[:, 1] - FOOT_Y) < 0.12, 0, np.where(np.abs(co[:, 1] - BACK_Y) < 0.2, 1, 2))
    lmax = {k: max(float(info[(part == WT.TACK_PART['rope']) & (strip == k), 1].max(initial=0.0)), 1e-3)
            for k in (0, 1, 2)}
    uv = np.zeros((len(me.vertices), 2))
    for i in range(len(me.vertices)):
        a, c = float(info[i, 1]), float(info[i, 2])
        if cloth[i]:
            uv[i] = (0.01 + 0.98 * c, 0.30 + 0.69 * a / amax)
        else:
            k = int(strip[i])
            uv[i] = (0.01 + 0.98 * a / lmax[k], 0.01 + 0.095 * k + 0.08 * c)
    layer = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        layer.data[loop.index].uv = uv[loop.vertex_index]


def build_texture(ob, size=512):
    import beast_paint as BP
    D = BP.bake_data(ob, size=size, ao_dist=0.2)
    col, smooth, hgt = WT.paint_tack(D)
    p_n, nrm = BP.write_normal_map(D, hgt, "T_MammothTack_Normal", strength=3.0)
    p = BP.write_texture(D, col, smooth, "T_MammothTack", ob, "M_MammothTack", normal=nrm)
    return [p, p_n]


def build(body=None, rig=None, size=512):
    """Tack -> UVs -> texture. -> (MammothTack, report)"""
    ob = build_tack(body, rig)
    unwrap(ob)
    tex = build_texture(ob, size)
    return ob, dict(tris=WT.tri_count(ob), textures=tex)
