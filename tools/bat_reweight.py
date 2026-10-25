"""BatWing re-weighted in place from dragon_body.build_membranes (2026-10-24: coons() kept a finger edge's corner
weight off the hand, so the membrane edges stay on their fingers): the same vertices, UVs and paint, matched to the
rebuilt patches by rest position (both layers of the two-sided wing take the same weights). Saves bat.blend.

    blender.exe -b --factory-startup blender/bat.blend --python tools/bat_reweight.py
"""
import os, sys
import bpy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from mathutils import Vector
from mathutils.kdtree import KDTree
import bat_body as BB, dragon_body as DB, beast_rig

B = BB.rest_bones()
acc = DB.Acc()
for s, sfx in BB.SIDES:
    DB.build_membranes(acc, B, s, sfx, BB.WS, n_finger=10, n_tip=5, n_lead=8)   # as bat_body.build_pieces
acc.bm.verts.ensure_lookup_table()
kd = KDTree(len(acc.bm.verts))
for i, v in enumerate(acc.bm.verts):
    kd.insert(v.co, i)
kd.balance()
wing = bpy.data.objects[BB.WING_OB]
worst = 0.0
new = []
for v in wing.data.vertices:
    co, i, d = kd.find(v.co)
    worst = max(worst, d)
    new.append(acc.W[i])
acc.bm.free()
if worst > 1e-3:
    raise RuntimeError(f"BatWing no longer matches build_membranes ({worst:.4f} m): rebuild the bat")
for g in list(wing.vertex_groups):
    wing.vertex_groups.remove(g)
groups = {}
for i, w in enumerate(new):
    for b, x in w.items():
        g = groups.get(b) or wing.vertex_groups.new(name=b)
        groups[b] = g
        g.add([i], float(x), 'REPLACE')
beast_rig.clean_weights(wing)
print("BATREWEIGHT", dict(verts=len(new), match_max=worst, report=beast_rig.weight_report(wing)))
bpy.ops.wm.save_mainfile()
print("SAVED", bpy.data.filepath)
