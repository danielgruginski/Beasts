"""Before/after sheets from two folders of renders (system Python with Pillow, not Blender), 2026-10-24 (the eagle's
revision): one column per view, the before row on top, the after row below, each tile labelled.

    py tools/before_after.py <before dir> <after dir> <out.png> <title> <name[:label]> ...   [--scale 0.5]

A name is a file name without .png, looked up in both folders.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
scale = 0.5
if "--scale" in args:
    i = args.index("--scale")
    scale = float(args[i + 1])
    del args[i:i + 2]
before, after, out, title = args[:4]
views = [a.split(":", 1) if ":" in a else (a, a) for a in args[4:]]
try:
    font = ImageFont.truetype("arial.ttf", 22)
    big = ImageFont.truetype("arialbd.ttf", 26)
except OSError:
    font = big = ImageFont.load_default()
tiles = []
for name, label in views:
    pair = [Image.open(os.path.join(d, name + ".png")).convert("RGB") for d in (before, after)]
    w, h = pair[0].size
    pair = [im.resize((int(w * scale), int(h * scale)), Image.LANCZOS) for im in pair]
    tiles.append((label, pair))
tw, th = tiles[0][1][0].size
pad, head, side = 6, 44, 110
W = side + len(tiles) * (tw + pad) + pad
H = head + 2 * (th + pad) + pad
sheet = Image.new("RGB", (W, H), (32, 32, 34))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 10), title, fill=(235, 235, 235), font=big)
for r, lab in enumerate(("before", "after")):
    d.text((10, head + r * (th + pad) + th // 2 - 12), lab, fill=(235, 235, 235), font=big)
for c, (label, pair) in enumerate(tiles):
    x = side + pad + c * (tw + pad)
    for r, im in enumerate(pair):
        y = head + pad + r * (th + pad)
        sheet.paste(im, (x, y))
        d.rectangle((x, y, x + tw - 1, y + 28), fill=(0, 0, 0))
        d.text((x + 6, y + 3), label, fill=(240, 240, 240), font=font)
sheet.save(out)
print(out, sheet.size)
