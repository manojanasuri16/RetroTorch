#!/usr/bin/env python3
"""Paints screens recorded by preview.py (JSON) into PNGs and one sheet."""
import json, sys, os
from PIL import Image, ImageDraw, ImageFont
REG = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
S = 2
fonts = {}


def col(c):
    c = c or 0
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def font(bold, size):
    k = (bold, size)
    if k not in fonts:
        fonts[k] = ImageFont.truetype((REG, BOLD)[bold], size * S)
    return fonts[k]


def paint(screen):
    w, h = screen["size"]
    im = Image.new("RGB", (w * S, h * S), "white")
    d = ImageDraw.Draw(im)
    sc = lambda v: [x * S for x in v]
    for op in screen["ops"]:
        k = op[0]
        if k == "clear":
            d.rectangle([0, 0, w * S, h * S], fill=col(op[1]))
        elif k == "rect":
            if op[2] is not None:
                d.rectangle(sc(op[1]), fill=col(op[2]))
            if op[3] is not None:
                d.rectangle(sc(op[1]), outline=col(op[3]))
        elif k == "ellipse":
            d.ellipse(sc(op[1]), fill=None if op[2] is None else col(op[2]),
                      outline=None if op[3] is None else col(op[3]))
        elif k == "line":
            d.line(sc(op[1]), fill=col(op[2]), width=op[3] * S)
        elif k == "poly":
            d.polygon([tuple(sc(p)) for p in op[1]], fill=col(op[2]))
        elif k == "text":
            (x, y), text, fill, (bold, size) = op[1], op[2], op[3], op[4]
            d.text((x * S, y * S), text, fill=col(fill), font=font(bold, size), anchor="ls")
        elif k == "photo":
            path, size, target, masked = op[1:5]
            src = op[5] if len(op) > 5 else None
            ph = Image.open(path).convert("RGB")
            if src:
                (sx, sy), (ex, ey) = src
                ph = ph.crop((sx, sy, ex, ey)).resize(((ex - sx) * S, (ey - sy) * S))
            else:
                ph = ph.resize((size[0] * S, size[1] * S))
            m = Image.new("L", ph.size, 0)
            ImageDraw.Draw(m).ellipse([0, 0, ph.size[0], ph.size[1]], fill=255)
            im.paste(ph, (target[0] * S, target[1] * S), m if masked else None)
    return im


screens = json.load(open(sys.argv[1]))
out = sys.argv[2]
ims = []
for s in screens:
    im = paint(s)
    im.save(os.path.join(out, s["name"] + ".png"))
    ims.append(im)
pad = 16
W = sum(i.size[0] for i in ims) + pad * (len(ims) + 1)
H = max(i.size[1] for i in ims) + pad * 2
sheet = Image.new("RGB", (W, H), (40, 40, 40))
x = pad
for i in ims:
    sheet.paste(i, (x, pad))
    x += i.size[0] + pad
sheet.save(os.path.join(out, "sheet.png"))
print("wrote", len(ims), "screens and sheet.png to", out)
