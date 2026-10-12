"""UVs, per-texel painting and materials for the ooze.

texel_bake rasterises a mesh's UV triangles in numpy (position, corner normal, face per texel), so the painters
work in 3D with no Cycles bakes. The shell's paint reads the distance field directly: local thickness (how far
the inside reaches along the inward normal), ambient occlusion (the field's classic 5-tap AO) and which pod a
texel belongs to.

T_Ooze.png           shell, 1024²: RGB colour, A opacity (thick core more opaque, pod tips and the skirt's edge
                     clearer: the hyaline ectoplasm). Smoothness is a material constant (wet: 0.9).
T_OozeContents.png   contents, 512²: RGB colour, A smoothness.
"""
import heapq, math, os
import numpy as np
import bpy, bmesh

from beast_common import ROOT, spline, fbm, vnoise, smoothstep, fill_gutters, hexc, srgb_to_lin, lin_to_srgb
import ooze_body as OB
import ooze_contents as OC

TEX = os.path.join(ROOT, "textures")
RAISED = {"Reach": (0, 0, -1.0), "Side": (0, 0, -1.0), "Probe": (0, 1.0, 0.3)}    # pod -> which side the seam runs


# ------------------------------------------------------------------ UVs

def _dijkstra(bm, a, b):
    """Edges of the shortest edge path from vert a to vert b."""
    dist = {a.index: 0.0}
    prev = {}
    pq = [(0.0, a.index)]
    verts = bm.verts
    while pq:
        d, i = heapq.heappop(pq)
        if i == b.index:
            break
        if d > dist.get(i, 1e9):
            continue
        v = verts[i]
        for e in v.link_edges:
            o = e.other_vert(v)
            nd = d + e.calc_length()
            if nd < dist.get(o.index, 1e9):
                dist[o.index] = nd
                prev[o.index] = (i, e)
                heapq.heappush(pq, (nd, o.index))
    out, i = [], b.index
    while i in prev:
        i, e = prev[i]
        out.append(e)
    return out


def _charts(bm, cap_nz=0.55, passes=3):
    """Face -> chart id: 0-3 the mass's sides (by azimuth), 4 its top cap, 5+ the pods (POD order).
    Faces go to the nearest piece of the shape; a majority filter evens the borders."""
    fc = np.array([f.calc_center_median()[:] for f in bm.faces])
    fn = np.array([f.normal[:] for f in bm.faces])
    D = OB.parts(fc)
    names = ["mass"] + list(OB.POD)
    which = np.argmin(np.stack([D[k] for k in names], 1), 1)
    az = np.arctan2(fc[:, 1] - 0.05, fc[:, 0])
    side = (np.floor((az + np.pi + np.pi / 4) / (np.pi / 2)).astype(int)) % 4
    chart = np.where(which == 0, np.where(fn[:, 2] > cap_nz, 4, side), 4 + which)
    for _ in range(passes):
        new = chart.copy()
        for f in bm.faces:
            nb = [chart[g.index] for e in f.edges for g in e.link_faces if g is not f]
            if nb:
                vals, cnt = np.unique(nb, return_counts=True)
                if cnt.max() * 2 > len(nb) and vals[cnt.argmax()] != chart[f.index]:
                    new[f.index] = vals[cnt.argmax()]
        chart = new
    for _ in range(6):                                  # stray bits (a face or a few) join their neighbours
        if not _absorb_strays(bm, chart):
            break
    return chart


def _absorb_strays(bm, chart, keep=30):
    """Each chart keeps its largest connected piece; smaller pieces under `keep` faces go to the neighbouring
    chart they share most edges with. -> whether anything changed."""
    seen = np.full(len(chart), -1)
    comps = []
    for f in bm.faces:
        if seen[f.index] >= 0:
            continue
        cid = len(comps)
        st, comp = [f], [f.index]
        seen[f.index] = cid
        while st:
            g = st.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if seen[h.index] < 0 and chart[h.index] == chart[g.index]:
                        seen[h.index] = cid
                        comp.append(h.index)
                        st.append(h)
        comps.append(comp)
    biggest = {}
    for cid, comp in enumerate(comps):
        c = chart[comp[0]]
        if c not in biggest or len(comp) > len(comps[biggest[c]]):
            biggest[c] = cid
    changed = False
    for cid, comp in enumerate(comps):
        c = chart[comp[0]]
        if biggest[c] == cid or len(comp) >= keep:
            continue
        nb = [chart[h.index] for i in comp for e in bm.faces[i].edges for h in e.link_faces
              if chart[h.index] != c]
        if nb:
            vals, cnt = np.unique(nb, return_counts=True)
            chart[comp] = vals[cnt.argmax()]
            changed = True
    return changed


def unwrap_shell(ob):
    """Charts (_charts: the pods, a top cap, four sides) cut along their borders, plus a slit along each raised
    pod's underside from where it leaves the body to its tip, so the tubes unroll instead of crumpling."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    chart = _charts(bm)
    for e in bm.edges:
        e.seam = False
        if len(e.link_faces) == 2:
            a, b = e.link_faces
            if chart[a.index] != chart[b.index]:
                e.seam = True
    co = np.array([v.co[:] for v in bm.verts])
    names = list(OB.POD)
    for name, side in RAISED.items():
        own = 5 + names.index(name)
        in_pod = np.zeros(len(co), bool)
        for f in bm.faces:
            if chart[f.index] == own:
                for v in f.verts:
                    in_pod[v.index] = True
        c = spline(OB.POD[name]["pts"], 6)
        side = np.asarray(side, float)
        targets = []
        for k in range(len(c) // 3, len(c)):
            T = c[min(k + 1, len(c) - 1), :3] - c[max(k - 1, 0), :3]
            T /= np.linalg.norm(T)
            s = side - T * (side @ T)
            s /= np.linalg.norm(s)
            targets.append(c[k, :3] + s * c[k, 3])
        T = c[-1, :3] - c[-2, :3]
        targets.append(c[-1, :3] + T / np.linalg.norm(T) * c[-1, 3])                      # over the tip
        idx = []
        for t in targets:
            i = int(np.argmin(np.linalg.norm(co - t, axis=1)))
            if in_pod[i] and (not idx or idx[-1] != i):
                idx.append(i)
        # the slit has to start on the chart's border, or the unwrap sees a hole (and fills it)
        rim = {v.index for e in bm.edges if e.seam for v in e.verts if in_pod[v.index]}
        if idx and rim and idx[0] not in rim:
            r = np.array(sorted(rim))
            idx.insert(0, int(r[np.argmin(np.linalg.norm(co[r] - co[idx[0]], axis=1))]))
        for i, j in zip(idx[:-1], idx[1:]):
            for e in _dijkstra(bm, bm.verts[i], bm.verts[j]):
                e.seam = True
    bm.to_mesh(me)
    bm.free()
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    _unwrap(ob, margin=0.006)
    _pack(ob, margin=0.006)


class _Edit:
    """Edit mode on ob alone (active and selected in the view layer), back to object mode on exit."""

    def __init__(self, ob):
        self.ob = ob

    def __enter__(self):
        vl = bpy.context.view_layer
        if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in vl.objects:
            o.select_set(False)
        self.ob.hide_set(False)
        self.ob.select_set(True)
        vl.objects.active = self.ob
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        return self

    def __exit__(self, *a):
        bpy.ops.object.mode_set(mode='OBJECT')
        self.ob.select_set(False)


def unwrap_contents(ob):
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    with _Edit(ob):
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01, area_weight=0.0,
                                 scale_to_bounds=False)
        bpy.ops.uv.average_islands_scale()
    # texel share by how much a piece shows through the jelly: the skull and bones most, the blurry nucleus and
    # the vacuoles least
    me = ob.data
    part = np.empty(len(me.polygons), np.int32)
    me.attributes["part"].data.foreach_get("value", part)
    weight = {OC.PART["bone"]: 1.7, OC.PART["blade"]: 1.3, OC.PART["grip"]: 1.3, OC.PART["brass"]: 1.3,
              OC.PART["helm"]: 1.1, OC.PART["coin"]: 1.4, OC.PART["nucleus"]: 0.55, OC.PART["vacuole"]: 0.6}
    uv = me.uv_layers.active.uv
    co = np.empty(len(me.loops) * 2)
    uv.foreach_get("vector", co)
    co = co.reshape(-1, 2)
    lp = np.empty(len(me.loops), np.int64)
    for p in me.polygons:
        lp[p.loop_start:p.loop_start + p.loop_total] = p.index
    s = np.vectorize(lambda k: weight.get(int(k), 1.0))(part)[lp]
    co = 0.5 + (co - 0.5) * s[:, None]
    uv.foreach_set("vector", co.ravel())
    _pack(ob, margin=0.01)


def _unwrap(ob, margin):
    with _Edit(ob):
        bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, margin=margin)
        bpy.ops.uv.average_islands_scale()


def _pack(ob, margin):
    with _Edit(ob):
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(margin=margin, rotate=True)
        bpy.ops.mesh.select_all(action='DESELECT')


# ------------------------------------------------------------------ texel bake

def texel_bake(ob, size):
    """-> mask (size, size) bool, P (.., 3) world position, N (.., 3) corner normal, F (..) polygon index; image
    rows bottom-up like bpy pixels."""
    me = ob.data
    me.calc_loop_triangles()
    lt = me.loop_triangles
    n = len(lt)
    L = np.empty(n * 3, np.int64)
    lt.foreach_get("loops", L)
    L = L.reshape(n, 3)
    PI = np.empty(n, np.int64)
    lt.foreach_get("polygon_index", PI)
    nl = len(me.loops)
    UV = np.empty(nl * 2)
    me.uv_layers.active.uv.foreach_get("vector", UV)
    UV = UV.reshape(nl, 2)
    LV = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", LV)
    CO = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", CO)
    M = np.array(ob.matrix_world)
    CO = CO.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    CN = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", CN)
    CN = CN.reshape(nl, 3) @ np.linalg.inv(M[:3, :3])
    P = np.zeros((size, size, 3), np.float32)
    N = np.zeros((size, size, 3), np.float32)
    F = np.full((size, size), -1, np.int32)
    for t in range(n):
        uv = UV[L[t]] * size - 0.5
        lo = np.maximum(np.floor(uv.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(uv.max(0)).astype(int), size - 1)
        if (hi < lo).any():
            continue
        xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
        a, b, c = uv
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        ins = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not ins.any():
            continue
        W = np.stack([w0[ins], w1[ins], w2[ins]], 1)
        yy, xx = ys[ins], xs[ins]
        P[yy, xx] = W @ CO[LV[L[t]]]
        nn = W @ CN[L[t]]
        N[yy, xx] = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
        F[yy, xx] = PI[t]
    return F >= 0, P, N, F


def _save(name, rgba, mask, size):
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (size, size):
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, size, size, alpha=True)
    img.colorspace_settings.name = 'sRGB'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    fill_gutters(img, mask)
    img.update()                                     # refresh the GPU copy (renders used stale pixels)
    os.makedirs(TEX, exist_ok=True)
    img.filepath_raw = os.path.join(TEX, name + ".png")
    img.file_format = 'PNG'
    img.save()
    return img


# ------------------------------------------------------------------ shell paint

SHELL_PAL = dict(core="#2c5a12", mid="#4f8c1c", thin="#a6d455", crevice="#173208", streak="#3a7014",
                 fleck="#c8e47a")


def _pod_membership(P):
    """-> (weight of the nearest pod, its tangent at the texel) from the pods' centre lines."""
    best = np.full(P.shape[0], 1e9)
    tan = np.zeros_like(P)
    for name, pod in OB.POD.items():
        c = spline(pod["pts"], 6)
        for a, b in zip(c[:-1], c[1:]):
            ab = b[:3] - a[:3]
            t = np.clip(((P - a[:3]) @ ab) / (ab @ ab), 0, 1)
            q = a[:3] + t[:, None] * ab
            r = a[3] + (b[3] - a[3]) * t
            d = np.linalg.norm(P - q, axis=1) - r
            m = d < best
            best[m] = d[m]
            tan[m] = ab / np.linalg.norm(ab)
    w = 1 - smoothstep(0.0, 0.18, best)
    return w, tan


def paint_shell(ob, size=1024, name="T_Ooze", pal=None):
    pal = dict(SHELL_PAL, **(pal or {}))
    C = {k: srgb_to_lin(hexc(v)) for k, v in pal.items()}
    mask, P, N, F = texel_bake(ob, size)
    p, n = P[mask].astype(float), N[mask].astype(float)
    # thickness: the deepest the field gets along the inward normal
    thick = np.zeros(len(p))
    for s in (0.04, 0.08, 0.14, 0.22, 0.32, 0.45, 0.6, 0.8):
        thick = np.maximum(thick, -OB.field(p - n * s, noise=False))
    thick = np.clip(thick, 0, 1)
    # AO from the field
    ao = np.zeros(len(p))
    for k, s in enumerate((0.03, 0.07, 0.12, 0.18, 0.26)):
        ao += (s - OB.field(p + n * s, noise=False, floor=False)) * (0.5 ** k) / s
    ao = np.clip(1 - 0.55 * ao / 1.94, 0, 1)
    podw, tan = _pod_membership(p)
    # cytoplasm streaming: noise stretched along the pods
    q = p - 0.85 * tan * (tan * p).sum(1, keepdims=True)
    streak = fbm(q * 7.0, 3, 21) * podw + fbm(p * 3.5, 3, 22) * (1 - podw)
    blot = fbm(p * 2.2, 3, 23)
    fl = vnoise(p * 38.0, 24)

    t_thin = smoothstep(0.06, 0.32, thick)                 # 0 at tips and the skirt's edge, 1 in the mass
    t_core = smoothstep(0.30, 0.65, thick)
    col = C["thin"] * (1 - t_thin)[:, None] + C["mid"] * t_thin[:, None]
    col = col * (1 - t_core)[:, None] + C["core"] * t_core[:, None]
    col = col * (1 + 0.18 * blot)[:, None]
    sk = smoothstep(0.15, 0.55, streak)[:, None] * 0.55
    col = col * (1 - sk) + C["streak"] * sk
    cr = (1 - smoothstep(0.55, 0.95, ao))[:, None]
    col = col * (1 - cr) + C["crevice"] * cr
    col = col * (0.75 + 0.25 * ao)[:, None]
    fleck = smoothstep(0.86, 0.95, fl)[:, None] * 0.35 * (1 - t_core)[:, None]
    col = col * (1 - fleck) + C["fleck"] * fleck
    alpha = 0.19 + 0.20 * t_thin + 0.10 * t_core + 0.10 * (1 - ao) + 0.03 * blot
    alpha = np.clip(alpha, 0.14, 0.6)

    rgba = np.zeros((size, size, 4), np.float32)
    rgba[..., 3] = 1.0
    rgba[mask, :3] = lin_to_srgb(col)
    rgba[mask, 3] = alpha
    img = _save(name, rgba, mask, size)
    return img, dict(coverage=float(mask.mean()), thick=(float(thick.min()), float(np.median(thick)), float(thick.max())),
                     alpha=(float(alpha.min()), float(np.median(alpha)), float(alpha.max())))


# ------------------------------------------------------------------ contents paint

def paint_contents(ob, size=512, name="T_OozeContents"):
    mask, P, N, F = texel_bake(ob, size)
    me = ob.data
    part_f = np.empty(len(me.polygons), np.int32)
    me.attributes["part"].data.foreach_get("value", part_f)
    piece_f = np.empty(len(me.polygons), np.int32)
    me.attributes["piece"].data.foreach_get("value", piece_f)
    p, n = P[mask].astype(float), N[mask].astype(float)
    part = part_f[F[mask]]
    piece = piece_f[F[mask]]
    pl = OC.placements()
    col = np.zeros((len(p), 3))
    smooth = np.zeros(len(p))
    hx = lambda h: srgb_to_lin(hexc(h))
    n1 = fbm(p * 14.0, 3, 31)
    n2 = fbm(p * 40.0, 2, 32)
    n3 = fbm(p * 5.0, 3, 33)

    def put(m, c, s):
        col[m] = c[m] if np.ndim(c) == 2 else c
        smooth[m] = s[m] if np.ndim(s) == 1 else s

    # nucleus: dark wine red (it reads against the green as the weak spot), mottled
    m = part == OC.PART["nucleus"]
    t = smoothstep(-0.2, 0.5, n1)[:, None]
    put(m, hx("#3a0f1c") * (1 - t) + hx("#7a2a3a") * t, 0.6)
    # bone: aged, pitted, acid-stained; dark orbits and nose on the skull
    m = part == OC.PART["bone"]
    t = smoothstep(-0.1, 0.6, n2)[:, None]
    bone = hx("#cdbd8c") * (1 - 0.35 * t) + hx("#8d7c4f") * 0.35 * t
    st = smoothstep(0.1, 0.5, n3)[:, None]
    bone = bone * (1 - 0.5 * st) + hx("#9aa45a") * 0.5 * st
    sk = [k for k, it in enumerate(pl) if it[0] == "skull"][0]
    ms = m & (piece == sk)
    if ms.any():
        Mi = np.linalg.inv(np.array(pl[sk][4]))
        loc = (p[ms] @ Mi[:3, :3].T + Mi[:3, 3]) / 1.25
        dark = np.zeros(ms.sum())
        for s in (-1, 1):
            d = np.linalg.norm(loc - np.array([s * 0.031, -0.099, -0.002]), axis=1)
            dark = np.maximum(dark, 1 - smoothstep(0.022, 0.034, d))
        d = np.linalg.norm((loc - np.array([0, -0.113, -0.042])) / np.array([0.012, 0.02, 0.019]), axis=1)
        dark = np.maximum(dark, 1 - smoothstep(0.9, 1.5, d))
        teeth = smoothstep(0.003, 0.0, np.abs(loc[:, 2] + 0.068)) * (loc[:, 1] < -0.06)
        b = bone[ms] * (1 - dark)[:, None] + hx("#20180c") * dark[:, None]
        b = b * (1 - 0.6 * teeth)[:, None] + hx("#3a3020") * (0.6 * teeth)[:, None]
        bone[ms] = b
    put(m, bone, 0.35)
    # blade: rust over grey iron
    m = part == OC.PART["blade"]
    t = smoothstep(-0.3, 0.3, n1 + 0.4 * n2)[:, None]
    put(m, hx("#6e6c66") * (1 - t) + hx("#7b3a18") * t, (0.45 - 0.3 * t[:, 0]))
    put(part == OC.PART["grip"], hx("#3b2414") * (0.85 + 0.3 * n2)[:, None], 0.25)
    put(part == OC.PART["brass"], hx("#8c6a2b") * (0.85 + 0.3 * n1)[:, None], 0.5)
    m = part == OC.PART["helm"]
    t = smoothstep(-0.1, 0.5, n1)[:, None]
    put(m, hx("#5c5850") * (1 - t) + hx("#7a3c1a") * t, (0.4 - 0.25 * t[:, 0]))
    put(part == OC.PART["coin"], hx("#d6a83a") * (0.9 + 0.2 * n2)[:, None], 0.8)
    m = part == OC.PART["vacuole"]
    rim = smoothstep(0.2, 0.8, 1 - np.abs(n[:, 2]))[:, None]
    put(m, hx("#e2f0a8") * (1 - 0.4 * rim) + hx("#7da040") * 0.4 * rim, 0.9)

    rgba = np.zeros((size, size, 4), np.float32)
    rgba[..., 3] = 0.3
    rgba[mask, :3] = lin_to_srgb(col)
    rgba[mask, 3] = smooth
    img = _save(name, rgba, mask, size)
    return img, dict(coverage=float(mask.mean()))


# ------------------------------------------------------------------ materials (Blender preview of the Unity look)

def _img_node(nt, img, loc):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.location = loc
    return t


def shell_material(img, name="M_Ooze", smoothness=0.9, fresnel=0.45, glow=0.06):
    """Principled, colour + opacity from T_Ooze, opacity raised toward the silhouette (fresnel), a faint inner glow
    in the colour so the shadowed side isn't black; dithered so the back faces and contents show in order."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (350, 0)
    t = _img_node(nt, img, (-400, 100))
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-400, -250)
    lw.inputs["Blend"].default_value = 0.5
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = 'MULTIPLY_ADD'
    mul.use_clamp = True
    mul.location = (0, -200)
    mul.inputs[1].default_value = fresnel
    nt.links.new(lw.outputs["Facing"], mul.inputs[0])
    nt.links.new(t.outputs["Alpha"], mul.inputs[2])
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(mul.outputs[0], b.inputs["Alpha"])
    nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = glow
    b.inputs["Roughness"].default_value = 1 - smoothness
    b.inputs["IOR"].default_value = 1.35
    nt.links.new(b.outputs[0], out.inputs[0])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = 'DITHERED'
    m.use_backface_culling = False
    m.use_transparent_shadow = True                   # a partial shadow by the opacity, not a solid one
    m.diffuse_color = (0.35, 0.65, 0.15, 0.5)
    m.roughness = 1 - smoothness
    return m


def contents_material(img, name="M_OozeContents"):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (300, 0)
    t = _img_node(nt, img, (-300, 0))
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    inv.location = (50, -200)
    nt.links.new(t.outputs["Alpha"], inv.inputs[1])
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(inv.outputs[0], b.inputs["Roughness"])
    nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = (0.6, 0.55, 0.4, 1)
    return m


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def uv_layout(ob, name):
    """Write renders/uv_layout_<name>.png."""
    path = os.path.join(ROOT, "renders", f"uv_layout_{name}.png")
    with _Edit(ob):
        bpy.ops.uv.export_layout(filepath=path, export_all=True, modified=False, mode='PNG', size=(1024, 1024),
                                 opacity=0.25)
    return path


def check_sheet(tex_name, layout_name, out_name):
    """renders/<out_name>.png: the texture with its UV layout drawn over it, and its alpha channel beside it."""
    def load(p):
        im = bpy.data.images.load(p, check_existing=False)
        a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)
        bpy.data.images.remove(im)
        return a
    t = load(os.path.join(TEX, tex_name + ".png"))
    lay = load(os.path.join(ROOT, "renders", f"uv_layout_{layout_name}.png"))
    k = max(1, lay.shape[0] // t.shape[0])
    lay = lay[::k, ::k]
    a = lay[..., 3:4] * 0.5
    rgb = t[..., :3] * (1 - a) + lay[..., :3] * a
    one = np.ones_like(rgb[..., :1])
    sheet = np.concatenate([np.concatenate([rgb, one], 2), np.concatenate([np.repeat(t[..., 3:4], 3, 2), one], 2)], 1)
    h, w = sheet.shape[:2]
    im = bpy.data.images.new("_check", w, h, alpha=True)
    im.pixels.foreach_set(sheet.ravel())
    path = os.path.join(ROOT, "renders", out_name + ".png")
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    return path
