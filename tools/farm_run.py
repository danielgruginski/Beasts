"""Headless driver for the farm animals (src/farm_build.py):

    blender.exe -b --factory-startup --python tools/farm_run.py -- goat build review
    blender.exe -b blender/farm_goat.blend --python tools/farm_run.py -- goat clips sheets export

Steps, in the order given: build (model, rig, weights, UVs, coats), review (renders), testpose, clips, sheets,
lowest, export. The file is saved as blender/farm_<name>.blend after the steps (unless 'nosave').
"""
import os, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
name, steps = args[0], args[1:]
if name == "chicken":                          # the hen has her own body, rig and clips (chicken_build)
    import chicken_build as FB
else:
    import farm_build as FB
sp = FB.species(name)
t0 = time.time()
out = {}
for st in steps:
    t = time.time()
    if st == "build":
        body, arm, rep = FB.build_model(sp)
        out[st] = rep
    elif st == "review":
        out[st] = FB.review(sp)
    elif st == "testpose":
        out[st] = FB.review_test_pose(sp)
    elif st == "clips":
        out[st] = FB.build_clips(sp)
    elif st == "sheets":
        out[st] = FB.clip_sheets(sp)
    elif st == "lowest":
        out[st] = FB.lowest(sp)
    elif st == "export":
        out[st] = FB.export(sp)
    elif st == "body":
        body, arm, rep = FB.build_model(sp, paint=False, rig=False)
        out[st] = rep
    elif st == "closeups":
        out[st] = FB.head_closeups(sp)
    elif st == "heads":
        out[st] = FB.head_shots(sp)
    elif st == "coats":
        out[st] = FB.coat_shots(sp)
    elif st == "nosave":
        continue
    else:
        raise SystemExit("unknown step " + st)
    print(f"STEP {st} {time.time() - t:.1f}s")
if "nosave" not in steps:
    bpy.ops.wm.save_as_mainfile(filepath=FB.blend_path(name))
print("RESULT " + json.dumps(out, default=str))
print(f"DONE {time.time() - t0:.1f}s")
