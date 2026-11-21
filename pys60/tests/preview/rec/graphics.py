"""Recording stand-in for PyS60 graphics (Python 2): every drawing call is
stored so tests/preview/render.py can paint it with PIL."""
import json, os
FONT_ANTIALIAS = 16
FONT_BOLD = 1
WIDTHS = json.load(open(os.environ["RT_WIDTHS"]))
_n = [0]


def _fontkey(font):
    if isinstance(font, tuple):
        bold = 0
        if font[2] and font[2] & FONT_BOLD:
            bold = 1
        return bold, int(font[1] or 15)
    return {"title": (1, 17), "dense": (0, 13)}.get(font, (0, 15))


def advance(text, font):
    bold, size = _fontkey(font)
    t = WIDTHS["%d-%d" % (bold, size)]
    w = 0.0
    for c in text:
        w += t.get(c, size * 0.55)
    return w


class Image(object):
    def __init__(self, size, mode="RGB16", path=None):
        self.size = tuple(size)
        self.mode = mode
        self.ops = []
        self.path = path

    @staticmethod
    def new(size, mode="RGB16"):
        return Image(size, mode)

    @staticmethod
    def open(path):
        _n[0] += 1
        p = os.path.join(os.environ["RT_OUT"], "img%d%s" % (_n[0], os.path.splitext(path)[1]))
        open(p, "wb").write(open(path, "rb").read())
        try:
            import struct as _st
            d = open(p, "rb").read(32)
            if d[:4] == "\x89PNG":
                w, h = _st.unpack(">II", d[16:24])
                return Image((w, h), path=p)
        except Exception:
            pass
        return Image((40, 40), path=p)

    def resize(self, size, callback=None, keepaspect=0):
        return Image(size, path=self.path)

    def clear(self, colour=0xffffff):
        self.ops = [("clear", colour)]

    def text(self, xy, text, fill=0, font=None):
        assert isinstance(text, unicode), repr(text)
        self.ops.append(("text", list(xy), text, fill, _fontkey(font)))

    def measure_text(self, text, font=None, maxwidth=-1, maxadvance=-1):
        adv = advance(text, font)
        n = len(text)
        if maxwidth >= 0:
            n = 0
            w = 0.0
            for c in text:
                w += advance(c, font)
                if w > maxwidth:
                    break
                n += 1
        return ((0, -12, int(adv), 4), int(adv + 0.5), n)

    def rectangle(self, coords, fill=None, outline=None, width=1):
        self.ops.append(("rect", list(coords), fill, outline))

    def ellipse(self, coords, fill=None, outline=None, width=1):
        self.ops.append(("ellipse", list(coords), fill, outline))

    def line(self, coords, outline=None, width=1, fill=None):
        self.ops.append(("line", list(coords), outline, width))

    def polygon(self, coords, fill=None, outline=None, width=1):
        self.ops.append(("poly", [list(p) for p in coords], fill, outline))

    def blit(self, img, target=(0, 0), source=None, mask=None, scale=0):
        if img.path:
            src = None
            if source is not None:
                src = [list(source[0]), list(source[1])]
            self.ops.append(("photo", img.path, list(img.size), list(target), mask is not None,
                             src))
        else:
            self.ops.extend(img.ops)
