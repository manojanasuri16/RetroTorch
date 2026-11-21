#!/usr/bin/env python3
"""Character widths of the stand-in font (Noto Sans) for the preview renderer."""
import json, sys
from PIL import ImageFont
REG = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
out = {}
for bold in (0, 1):
    for size in range(10, 30):
        f = ImageFont.truetype((REG, BOLD)[bold], size)
        out["%d-%d" % (bold, size)] = {chr(c): f.getlength(chr(c)) for c in range(32, 0x2030)
                                       if c < 127 or c in (0x2026, 0x270e, 0x2191, 0xe9)}
json.dump(out, open(sys.argv[1], "w"))
