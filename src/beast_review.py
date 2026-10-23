"""Headless build and review helpers for the creatures built in their own files in a background Blender (2026-10-23:
the giant bat, the giant turtle and the leech; tools/creature_run.py drives them). The zombie wolf's zwolf_build does
the same things for itself.

- new_scene: the factory file's one scene renamed after the creature, the shared lights, ground and cameras, EEVEE;
- game cameras: the game's view, 22 m away at 50 degrees pitch with a vertical fov of 30 (GAME);
- add_wolf: the grey wolf (WolfBody on WolfRig, bind pose) appended from blender/beasts.blend, for scale;
- sheets: renders tiled into one PNG (rows = cameras, columns = frames), game-camera crops blown up;
- lowest: the lowest vertex of the skinned meshes per clip;
- motion_trace: a clip looped three times the way Unity plays root motion (the GameObject follows Motion, the
  skeleton plays in place on top of it): travel and speed per loop, Motion's turn (must stay 0), the frame-to-frame
  step of the tracked bones across the loop seam against the steps inside the loop.
"""
import bpy, math, os
import numpy as np
from mathutils import Vector, Matrix
from beast_common import ROOT, get_coll
import beast_scene

GAME = dict(dist=22.0, pitch=50.0, fov=30.0, res=620)
RENDERS = os.path.join(ROOT, "renders")


def eevee(scn):
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scn.render.engine = eng
            return eng
        except TypeError:
            pass
    return scn.render.engine


def new_scene(name, prefix, lift=0.0):
    """The file's one scene renamed `name`, the factory startup's cube, light and camera removed, the shared lights,
    ground and cameras (prefix + CAM_*), EEVEE."""
    scn = bpy.context.scene
    scn.name = name
    for n in ("Cube", "Light", "Camera"):
        ob = bpy.data.objects.get(n)
        if ob is not None:
            bpy.data.objects.remove(ob, do_unlink=True)
    beast_scene.setup_scene(name, prefix=prefix, lift=lift)
    eevee(scn)
    return scn


def cam(scn, name, loc, target, **kw):
    return beast_scene._cam(scn, name, loc, target, **kw)


def game_cam(scn, name, az, target):
    """The game's camera: GAME['dist'] away at GAME['pitch'], vertical fov GAME['fov'], from azimuth az (deg; 0 = in
    front of the creature, 90 = its left side)."""
    a, p = math.radians(az), math.radians(GAME['pitch'])
    t = Vector(target)
    loc = t + Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * GAME['dist']
    c = beast_scene._cam(scn, name, tuple(loc), tuple(t))
    c.data.sensor_fit = 'VERTICAL'
    c.data.lens = c.data.sensor_height / 2 / math.tan(math.radians(GAME['fov']) / 2)
    return c


def game_cams(scn, prefix, target, azimuths=(90, -90, 30, 210)):
    return [game_cam(scn, f"{prefix}CAM_Game{i}", az, target).name for i, az in enumerate(azimuths)]


# ----------------------------------------------------------------------------------------- the wolf for scale
WOLF = ("WolfBody", "WolfRig")


def add_wolf(prefix, at=(1.4, 0.0, 0.0), yaw=0.0):
    """The grey wolf appended from blender/beasts.blend (read only) into <prefix>Scale, in its bind pose at `at`
    turned `yaw` degrees; its images re-pointed at textures/. -> the wolf's body object."""
    body = bpy.data.objects.get("WolfBody")
    if body is None:
        path = os.path.join(ROOT, "blender", "beasts.blend")
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n in WOLF]
        coll = get_coll(prefix + "Scale")
        for ob in dst.objects:
            if ob is not None and ob.name not in coll.objects:
                coll.objects.link(ob)
        body = bpy.data.objects.get("WolfBody")
    rig = bpy.data.objects.get("WolfRig")
    for img in bpy.data.images:
        fp = bpy.path.abspath(img.filepath) if img.filepath else ""
        if img.filepath and not os.path.exists(fp):
            alt = os.path.join(ROOT, "textures", os.path.basename(img.filepath.replace("\\", "/")))
            if os.path.exists(alt):
                img.filepath = alt
                img.reload()
    if rig is not None:
        if rig.animation_data:
            rig.animation_data.action = None
        for pb in rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        rig.location = at
        rig.rotation_euler = (0, 0, math.radians(yaw))
        rig.hide_render = True
    elif body is not None:
        body.location = at
    bpy.context.view_layer.update()
    return body


def show_wolf(on):
    for n in WOLF:
        ob = bpy.data.objects.get(n)
        if ob is not None and n == "WolfBody":
            ob.hide_render = not on


# ----------------------------------------------------------------------------------------- images
def load(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a


def save(a, name):
    h, w = a.shape[:2]
    img = bpy.data.images.new("_rv_sheet", w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(a, np.float32).ravel())
    path = os.path.join(RENDERS, name + ".png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


def shot(cam_name, name, res=900):
    scn = bpy.context.scene
    return beast_scene.shot(cam_name, name, engine=scn.render.engine, res=res)


def game_sheet(cams, out, crop=200, k=3):
    """Each game camera at the game's pixel size (renders/<out>_<i>.png) and one sheet of their middles blown up xk
    (nearest), so the pixels the player gets can be judged: renders/<out>.png."""
    res = GAME['res']
    tiles = []
    for i, c in enumerate(cams):
        a = load(shot(c, f"{out}_{i}", res=res))
        c0 = (res - crop) // 2
        a = a[c0:c0 + crop, c0:c0 + crop]
        tiles.append(np.repeat(np.repeat(a, k, 0), k, 1))
    half = (len(tiles) + 1) // 2
    while len(tiles) < 2 * half:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.concatenate([np.concatenate(tiles[half:], 1), np.concatenate(tiles[:half], 1)], 0)
    return save(sheet, out)


def frames_sheet(anim, rig_name, clip, frames, cams, out, res=420, follow=True):
    """Clip frames rendered from each camera (rows = cameras, columns = frames; the scene's engine), the cameras
    moving with the Root bone (the clips play in place; Motion carries the travel), or with a bone: follow = a bone
    name (a face close-up through a dive). -> renders/<out>.png"""
    scn = bpy.context.scene
    rig = bpy.data.objects[rig_name]
    anim.use(clip)
    rows = []
    for cam_name in cams:
        c = bpy.data.objects[cam_name]
        home = c.location.copy()
        row = []
        scn.frame_set(0)
        b0 = (rig.matrix_world @ rig.pose.bones[follow].head) if isinstance(follow, str) else None
        for f in frames:
            scn.frame_set(f)
            if isinstance(follow, str):
                c.location = home + (rig.matrix_world @ rig.pose.bones[follow].head - b0)
            elif follow:
                off = rig.matrix_world @ rig.pose.bones["Root"].head
                c.location = home + Vector((off.x, off.y, 0))
            row.append(load(shot(cam_name, "_rv_tile", res=res)))
        c.location = home
        rows.append(np.concatenate(row, axis=1))
    anim.clear()
    return save(np.concatenate(rows[::-1], axis=0), out)


# ----------------------------------------------------------------------------------------- checks
def _eval_co(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def lowest(anim, meshes, names=None, step=2):
    """The lowest vertex (world z) of the skinned meshes per clip, sampled every `step` frames and at the end.
    -> {clip: (lowest, frame)}"""
    scn = bpy.context.scene
    obs = [bpy.data.objects[m] for m in meshes]
    out = {}
    for n in (names or anim.CLIPS):
        anim.use(n)
        N = int(bpy.data.actions[anim.action_name(n)]["frames"])
        lo, at = 9.0, 0
        for f in sorted(set(list(range(0, N + 1, step)) + [N])):
            scn.frame_set(f)
            z = min(float(_eval_co(o)[:, 2].min()) for o in obs)
            if z < lo:
                lo, at = z, f
        out[n] = (round(lo, 3), at)
    anim.clear()
    return out


def motion_trace(anim, rig_name, clip, bones=("Head",), loops=3, fps=30):
    """A moving clip played `loops` times as Unity plays it: the GameObject follows the Motion bone's travel, the
    skeleton plays on top. -> dict: travel per loop (m, Blender axes; the front is -Y), speed (m/s), Motion's largest
    turn from its rest orientation (deg; must be 0: Unity would turn the creature), and per tracked bone the largest
    frame-to-frame step change at the loop seams against the largest inside the loop (a snap shows as a big seam
    value)."""
    scn = bpy.context.scene
    rig = bpy.data.objects[rig_name]
    anim.use(clip, rig)
    N = int(bpy.data.actions[anim.action_name(clip)]["frames"])
    rest_m = rig.data.bones["Motion"].matrix_local.to_quaternion()
    mot, pos, turn = [], {b: [] for b in bones}, 0.0
    for f in range(N + 1):
        scn.frame_set(f)
        pm = rig.pose.bones["Motion"].matrix
        mot.append(np.array(pm.translation))
        turn = max(turn, math.degrees(pm.to_quaternion().rotation_difference(rest_m).angle))
        for b in bones:
            pos[b].append(np.array(rig.pose.bones[b].head))
    anim.clear(rig)
    mot = np.array(mot)
    travel = mot[N] - mot[0]
    out = dict(frames=N, travel=[round(float(x), 4) for x in travel],
               speed=round(float(np.linalg.norm(travel)) / (N / fps), 3), motion_turn_deg=round(turn, 4))
    for b in bones:
        P = np.array(pos[b])
        world = []
        for k in range(loops):
            for f in range(N):
                world.append(k * travel + (mot[f] - mot[0]) + P[f])
        world.append(loops * travel + P[N] + (mot[N] - mot[0]) - travel)
        W = np.array(world)
        step = np.diff(W, axis=0)
        dstep = np.linalg.norm(np.diff(step, axis=0), axis=1)        # the change of velocity frame to frame
        seams = [k * N - 1 for k in range(1, loops)]
        inner = np.delete(dstep, seams)
        out[b] = dict(seam=round(float(dstep[seams].max()), 4), inner=round(float(inner.max()), 4),
                      pose_gap=round(float(np.linalg.norm(P[N] - P[0])), 4))
    return out


def uv_png(ob, name, tex=None, size=1024):
    import farm_paint
    return farm_paint.uv_png(ob, os.path.join(RENDERS, name + ".png"), size=size, tex=tex)


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def low_parts(anim, meshes, clip, frame, below=0.0, top=8):
    """Which vertices go under `below` at a clip's frame: -> [(z, mesh, part, strongest bone)] lowest first."""
    from beast_body import read_info, PART
    names = {v: k for k, v in PART.items()}
    anim.use(clip)
    bpy.context.scene.frame_set(frame)
    out = []
    for m in meshes:
        ob = bpy.data.objects[m]
        co = _eval_co(ob)
        part, _ = read_info(ob)
        gn = {g.index: g.name for g in ob.vertex_groups}
        for i in np.argsort(co[:, 2])[:top]:
            if co[i, 2] >= below:
                break
            v = ob.data.vertices[int(i)]
            g = max(v.groups, key=lambda g: g.weight, default=None)
            out.append((round(float(co[i, 2]), 3), m, names.get(int(part[i]), '?'), gn.get(g.group) if g else None))
    anim.clear()
    return sorted(out)[:top]


def uv_overlap(objs, size=512):
    """Texels covered by more than one UV island (over the given objects, which share one texture): -> (count,
    [(island a part, island b part, texels)]). Islands are face groups joined across non-seam UV-continuous edges."""
    import bmesh
    from beast_body import read_info, PART
    names = {v: k for k, v in PART.items()}
    owner = np.full((size, size), -1, np.int64)
    clash = {}
    base = 0
    labels = {}
    for ob in objs:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        bm.faces.ensure_lookup_table()
        part, _ = read_info(ob)
        parent = list(range(len(bm.faces)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            f0, f1 = e.link_faces
            ok = True
            for v in e.verts:
                u0 = next(l[uv].uv for l in f0.loops if l.vert is v)
                u1 = next(l[uv].uv for l in f1.loops if l.vert is v)
                if (u0 - u1).length > 1e-5:
                    ok = False
            if ok:
                parent[find(f0.index)] = find(f1.index)
        for f in bm.faces:
            isl = base + find(f.index)
            labels[isl] = names.get(int(part[f.verts[0].index]), '?') + "@" + ob.name
            pts = [l[uv].uv for l in f.loops]
            for i in range(1, len(pts) - 1):
                tri = np.array([pts[0], pts[i], pts[i + 1]]) * size
                x0, y0 = np.floor(tri.min(0)).astype(int)
                x1, y1 = np.ceil(tri.max(0)).astype(int)
                xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1, size)), np.arange(max(y0, 0), min(y1, size)))
                if xs.size == 0:
                    continue
                px, py = xs.ravel() + 0.5, ys.ravel() + 0.5
                a, b, c = tri
                d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(d) < 1e-12:
                    continue
                l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
                l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
                inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
                for x, y in zip(xs.ravel()[inside], ys.ravel()[inside]):
                    o = owner[y, x]
                    if o == -1:
                        owner[y, x] = isl
                    elif o != isl:
                        k = (min(o, isl), max(o, isl))
                        clash[k] = clash.get(k, 0) + 1
        base += len(bm.faces)
        bm.free()
    out = sorted(((labels[a], labels[b], n) for (a, b), n in clash.items()), key=lambda t: -t[2])
    return sum(n for *_, n in out), out[:12]
