"""Fake PyS60 graphics for PC tests: records drawn text, checks arguments."""
FONT_ANTIALIAS = 16
FONT_BOLD = 1
drawn = []          # every text() call: (x, y, text)


def _font_w(font):
    if isinstance(font, tuple):
        return max(int(font[1] or 14) * 7 // 15, 4)
    return 7


class Image(object):
    def __init__(self, size, mode="RGB16"):
        self.size = tuple(size)
        self.mode = mode

    @staticmethod
    def new(size, mode="RGB16"):
        assert len(size) == 2 and size[0] > 0 and size[1] > 0, size
        return Image(size, mode)

    @staticmethod
    def open(path):
        data = open(path, "rb").read()
        assert data[:2] == "\xff\xd8" and data[-2:] == "\xff\xd9", "not a JPEG"
        return Image((8, 8))

    def resize(self, size, callback=None, keepaspect=0):
        return Image(size)

    def _xy(self, coords):
        for v in coords:
            if isinstance(v, tuple):
                for c in v:
                    assert isinstance(c, (int, long)), coords
            else:
                assert isinstance(v, (int, long)), coords

    def clear(self, colour=0xffffff):
        pass

    def text(self, xy, text, fill=0, font=None):
        assert isinstance(text, unicode), repr(text)
        self._xy(xy)
        drawn.append((xy[0], xy[1], text))

    def measure_text(self, text, font=None, maxwidth=-1, maxadvance=-1):
        cw = _font_w(font)
        n = len(text)
        if maxwidth >= 0:
            n = min(n, maxwidth // cw)
        return ((0, -10, len(text) * cw, 3), len(text) * cw, n)

    def rectangle(self, coords, fill=None, outline=None, width=1):
        self._xy(coords)

    def ellipse(self, coords, fill=None, outline=None, width=1):
        self._xy(coords)

    def line(self, coords, outline=None, width=1, fill=None):
        self._xy(coords)

    def polygon(self, coords, fill=None, outline=None, width=1):
        for p in coords:
            self._xy(p)

    def blit(self, img, target=(0, 0), source=None, mask=None, scale=0):
        if mask is not None:
            assert mask.size == img.size, (mask.size, img.size)
