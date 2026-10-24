"""Headless glTF export of creatures for the Godot pack (src/beast_gdx.py):

    blender.exe -b --factory-startup blender/beasts.blend --python tools/godot_export.py -- wolf rat rhino bear deer mammoth ooze
    blender.exe -b --factory-startup blender/dragon.blend --python tools/godot_export.py -- dragon
    blender.exe -b --factory-startup blender/farm_goat.blend --python tools/godot_export.py -- goat

Each name runs its build module's own export() (src/<name>_build.py; zwolf for the zombie wolf, farm_build for the
farm animals, chicken_build for the hen) with the FBX writer swapped for beast_gdx.export_glb, so the rig, meshes,
clips and texture prefix are the ones Unity gets. The creature must be in the .blend opened. Nothing is saved.
"""
import os, sys, json, time, importlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import beast_export, beast_gdx

MODULES = {"zombiewolf": "zwolf_build", "zwolf": "zwolf_build", "chicken": "chicken_build"}
FARM = {"goat", "sheep", "cow", "horse", "pig"}


def via_build(name):
    """runs <name>_build.export() and catches what it hands the FBX writer; exports that as glTF instead"""
    cap = {}

    def model(rig_name="WolfRig", meshes=("WolfBody",), name="Wolf", tex_prefix="T_Wolf"):
        cap.update(rig=rig_name, meshes=tuple(meshes), name=name, tex=tex_prefix)
        return []

    def clips(anim, rig_name="WolfRig", name="Wolf"):
        cap["anim"] = anim
        return []

    real = beast_export.export_model, beast_export.export_clips
    beast_export.export_model, beast_export.export_clips = model, clips
    try:
        if name in FARM:
            fb = importlib.import_module("farm_build")
            fb.export(fb.species(name))
        else:
            importlib.import_module(MODULES.get(name, name + "_build")).export()
    finally:
        beast_export.export_model, beast_export.export_clips = real
    return beast_gdx.export_glb(cap["anim"], cap["rig"], cap["meshes"], cap["name"], cap["tex"])


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not args:
    raise SystemExit("usage: godot_export.py -- <creature> ...")
for a in args:
    t = time.time()
    files = via_build(a.lower())
    print("GDXCREATURE " + json.dumps({"creature": os.path.basename(files[0])[:-4], "seconds": round(time.time() - t, 1),
                                       "files": [os.path.basename(f) for f in files]}), flush=True)
