"""Headless driver for the creatures built in files of their own (2026-10-23: the giant bat, the giant turtle and the
leech; src/<name>_build.py, blender/<name>.blend):

    blender.exe -b --factory-startup --python tools/creature_run.py -- bat build review game clips lowest trace sheets closeups export
    blender.exe -b --factory-startup blender/bat.blend --python tools/creature_run.py -- bat paint review

The first argument names the creature (bat, turtle, leech); every other one is a step, run in the order given:
build (model, rig, weights, UVs, paint), paint (the paint again on the built model, same UVs), review (EEVEE renders
of the bind pose), game (the game camera, alone and beside the wolf), clips, lowest (the lowest vertex per clip),
trace (the moving clips looped as Unity plays root motion), sheets (contact sheets per clip), closeups (EEVEE clip
frames), export. The file is saved as blender/<name>.blend afterwards (unless 'nosave'). Open .blend files with
--factory-startup too, so the user's add-ons stay out.
"""
import os, sys, time, json, importlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not args:
    raise SystemExit("usage: creature_run.py -- <bat|turtle|leech> <steps...>")
M = importlib.import_module(args[0] + "_build")
steps = args[1:]
t0 = time.time()
out = {}
for st in steps:
    if st == "nosave":
        continue
    t = time.time()
    fn = getattr(M, st, None)
    if fn is None:
        raise SystemExit("unknown step " + st)
    out[st] = fn()
    print(f"STEP {st} {time.time() - t:.1f}s", flush=True)
    print("STEPRESULT " + st + " " + json.dumps(out[st], default=str), flush=True)
if "nosave" not in steps:
    bpy.ops.wm.save_as_mainfile(filepath=M.blend_path())
print(f"DONE {time.time() - t0:.1f}s")
