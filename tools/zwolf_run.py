"""Headless driver for the zombie wolf (src/zwolf_build.py):

    blender.exe -b --factory-startup --python tools/zwolf_run.py -- build review clips lowest export
    blender.exe -b --factory-startup blender/zombie_wolf.blend --python tools/zwolf_run.py -- review game closeups

Steps, in the order given: build (model, rig, weights, UVs, coats), body (the body alone), paint (the coats again on
the built model, same UVs), review (EEVEE renders of the bind pose), game (the game camera from four sides), coats (one
render per coat), testpose, clips, lowest, sheets (Workbench contact sheets), closeups (EEVEE clip frames round the
wound and the face), export. The file is saved as blender/zombie_wolf.blend afterwards (unless 'nosave').
"""
import os, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import bpy
import zwolf_build as ZB

steps = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
t0 = time.time()
out = {}
for st in steps:
    t = time.time()
    if st == "build":
        body, arm, rep = ZB.build_model()
        out[st] = rep
    elif st == "body":
        body, arm, rep = ZB.build_model(paint=False, rig=False)
        out[st] = rep
    elif st == "paint":
        out[st] = ZB.repaint()
    elif st == "review":
        out[st] = ZB.review()
    elif st == "coats":
        out[st] = ZB.coat_shots()
    elif st == "game":
        out[st] = ZB.game_shots()
    elif st == "testpose":
        out[st] = ZB.review_test_pose()
    elif st == "clips":
        out[st] = ZB.build_clips()
    elif st == "lowest":
        out[st] = ZB.lowest()
    elif st == "sheets":
        out[st] = ZB.clip_sheets()
    elif st == "closeups":
        out[st] = ZB.closeups()
    elif st == "export":
        out[st] = ZB.export()
    elif st == "nosave":
        continue
    else:
        raise SystemExit("unknown step " + st)
    print(f"STEP {st} {time.time() - t:.1f}s", flush=True)
if "nosave" not in steps:
    bpy.ops.wm.save_as_mainfile(filepath=ZB.blend_path())
print("RESULT " + json.dumps(out, default=str))
print(f"DONE {time.time() - t0:.1f}s")
