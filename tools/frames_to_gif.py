"""Frames rendered by dragon_build.clip_frames (renders/clip_<Clip>_<cam>/####.png) -> an animated GIF.

    py tools/frames_to_gif.py renders/clip_Walk_34 renders/dragon_Walk.gif --step 2 [--width 420]

`step` is the frame step the frames were rendered with (30 fps clips): it sets the GIF's frame time.
"""
import argparse, os
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("out")
ap.add_argument("--step", type=int, default=2)
ap.add_argument("--width", type=int, default=0)
a = ap.parse_args()
names = sorted(n for n in os.listdir(a.folder) if n.endswith(".png"))
frames = []
for n in names:
    im = Image.open(os.path.join(a.folder, n)).convert("RGB")
    if a.width:
        im = im.resize((a.width, round(im.height * a.width / im.width)), Image.LANCZOS)
    frames.append(im.quantize(colors=200, method=Image.Quantize.MEDIANCUT))
frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=round(1000 * a.step / 30), loop=0,
               optimize=True)
print(a.out, len(frames), "frames", os.path.getsize(a.out) // 1024, "KB")
