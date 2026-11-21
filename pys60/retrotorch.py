# RetroTorch: a torch for Python for S60 1.4.5 (Nokia N79 and other S60
# 3rd Edition phones). Uses every light the phone has: the screen (any
# colour, brightness, effects), the camera's dual LED as a steady torch or
# as flash bursts, the keypad light and any extra lights the phone reports.
#
# Written for Python 2.2: no enumerate/sorted/sets/generators, no
# conditional expressions, no "with", no "except X as e". The file also
# parses as Python 3 so it can be checked on a PC (tools/check_py22.py).

import sys
import appuifw
import e32
import graphics
import key_codes

VERSION = u"1.2.0"  # single source of truth: build_sis.sh reads this
APP = u"RetroTorch"

_LOGFILE = None
for _d in ["E:\\", "C:\\Data\\", "C:\\"]:
    try:
        _name = _d + "retrotorch_log.txt"
        _mode = "a"
        try:
            import os as _os
            if _os.path.getsize(_name) > 40000:
                _mode = "w"
        except:
            pass
        _LOGFILE = open(_name, _mode)
        break
    except:
        pass


def log(msg):
    if _LOGFILE is None:
        return
    try:
        try:
            import time as _t
            msg = _t.strftime("%H:%M:%S ") + msg
        except:
            pass
        if type(msg) is type(u""):
            msg = msg.encode("utf-8")
        _LOGFILE.write(msg + "\n")
        _LOGFILE.flush()
    except:
        pass


def err_text():
    return str(sys.exc_info()[1])


import lights
lights.set_logger(log)

# --------------------------------------------------------------- look

BG = 0x101214
PANEL = 0x1C1F23
PANEL_SEL = 0x2C3138
TEXT = 0xF2F2F2
GREY = 0x8A9099
DARK = 0x50565E
YELLOW = 0xFFD43B
YELLOW_DIM = 0x6B5A1A
RED = 0xE5484D
GREEN = 0x46C35A

try:
    _AA = graphics.FONT_ANTIALIAS
    _BOLD = graphics.FONT_BOLD
except:
    _AA = 0
    _BOLD = 0

FONTS = {
    "title": (None, 18, _BOLD | _AA),
    "name": (None, 15, _BOLD | _AA),
    "text": (None, 14, _AA),
    "small": (None, 12, _AA),
    "big": (None, 24, _BOLD | _AA),
}
FALLBACK = {"title": "title", "name": "title", "text": "normal", "small": "dense",
            "big": "title"}
_font_ok = [None]


def font(name):
    if _font_ok[0] == 0:
        return FALLBACK[name]
    return FONTS[name]


def check_fonts(img):
    """Scalable fonts given as (name, size, flags) need S60 3rd FP1+."""
    if _font_ok[0] is not None:
        return
    try:
        img.text((0, 10), u"x", fill=0, font=FONTS["text"])
        img.measure_text(u"x", font=FONTS["text"])
        _font_ok[0] = 1
    except:
        _font_ok[0] = 0


def width(g, text, f):
    try:
        return g.measure_text(text, font=font(f))[1]
    except:
        return len(text) * 7


def fit(g, text, f, maxw):
    """text cut to maxw pixels, with an ellipsis."""
    if width(g, text, f) <= maxw:
        return text
    while len(text) > 1 and width(g, text + u"...", f) > maxw:
        text = text[:-1]
    return text + u"..."


# --------------------------------------------------------------- settings

def cfg_paths():
    return ["E:\\retrotorch.cfg", "C:\\Data\\retrotorch.cfg"]


def load_cfg():
    for p in cfg_paths():
        try:
            f = open(p, "r")
            d = eval(f.read(), {"__builtins__": {}})
            f.close()
            if type(d) is type({}):
                return d
        except:
            pass
    return {}


def save_cfg(d):
    for p in cfg_paths():
        try:
            f = open(p, "w")
            f.write(repr(d))
            f.close()
            return
        except:
            pass


# Crash guard: before touching risky hardware the app writes its name to this
# file and deletes it afterwards. If the file is still there at the next start,
# that hardware took the app down, so it is switched off (lights.OFF).
PROBE_FILES = ["C:\\Data\\retrotorch_probe.txt", "E:\\retrotorch_probe.txt"]
HW_NAMES = {"lights": u"Native lights (keypad, extra lights, brightness)",
            "camera": u"Camera module (flash bursts)",
            "led": u"LED torch (native camera)"}


def probe_begin(name):
    log("guard: begin " + name)
    for p in PROBE_FILES:
        try:
            f = open(p, "w")
            f.write(name)
            f.close()
            return
        except:
            pass


def probe_end(name):
    log("guard: end " + name)
    import os
    for p in PROBE_FILES:
        try:
            os.remove(p)
        except:
            pass


def probe_crashed():
    """Name of the hardware that was being touched when the app last died."""
    import os
    for p in PROBE_FILES:
        try:
            f = open(p, "r")
            name = f.read().strip()
            f.close()
            os.remove(p)
            return name
        except:
            pass
    return None


lights.GUARD[0] = probe_begin
lights.GUARD[1] = probe_end

AUTO_OFF = [0, 1, 2, 5, 10, 15, 30, 60]       # minutes, 0 = never
LEVELS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]


# --------------------------------------------------------------- app

class TorchApp:
    def __init__(self):
        self.lock = e32.Ao_lock()
        self.cfg = load_cfg()
        self.sources = []
        self.screen = "home"         # "home", "control", "full"
        self.sel = 0                 # home: selected source
        self.top = 0                 # home: first visible row
        self.row = 0                 # control: selected setting row
        self.src = None              # source on the control screen
        self.on = 0
        self.colour_now = 0          # what the screen light shows right now
        self.toast = None
        self.toast_gen = 0
        self.left = 0                # auto-off: seconds left (0 = no timer)
        self.busy = None             # text shown while preparing hardware
        self.canvas = None
        self.buf = None
        self.player = lights.Player(self.on_state)
        self.tick_timer = e32.Ao_timer()
        self.toast_timer = e32.Ao_timer()
        self.ticking = 0
        self.crashed = probe_crashed()
        off = self.cfg.get("off", [])
        if self.crashed and self.crashed not in off:
            log("last run died while using: " + self.crashed + " -> switched off")
            off.append(self.crashed)
            self.cfg["off"] = off
            save_cfg(self.cfg)
        for name in off:
            lights.OFF[name] = 1
        if self.cfg.get("led_v") != lights.LED_VERSION:
            # the list of LED methods changed: the saved choice means nothing now
            self.cfg["led_method"] = None
            self.cfg["led_v"] = lights.LED_VERSION
            save_cfg(self.cfg)
        self.probed = 0
        self.drawn = 0
        self.bat = u""
        self.build_sources()

    # ---------------------------------------------------------- sources

    def build_sources(self):
        """At start only the screen light, LED (untouched) and All: no hardware
        is asked anything until the UI is up (see probe())."""
        self.screen_src = lights.ScreenSource()
        self.led = lights.LedSource(self.cfg.get("led_method"))
        self.flash = lights.PhotoFlashSource()
        self.sources = [self.led, self.screen_src,
                        lights.AllSource([self.screen_src, self.led])]

    def probe(self):
        """Asks the hardware what it has, one guarded step at a time."""
        if self.probed:
            return
        self.probed = 1
        out = [self.led, self.screen_src]     # the LED torch is the main light
        if not lights.OFF.has_key("camera"):
            probe_begin("camera")
            ok = self.flash.available()
            probe_end("camera")
            if ok:
                out.append(self.flash)
        mask = -1
        if lights.torchhw is not None and not lights.OFF.has_key("lights"):
            probe_begin("lights")
            mask = lights.light_targets()
            self.screen_src.probe()
            probe_end("lights")
        log("native module: %s, light targets: %s (0x%x)" % (
            str(lights.NATIVE_ERR or "loaded"), lights.targets_text(mask), mask & 0xFFFF))
        extras = []
        if mask > 0:
            bit = 2
            while bit <= 0x80:
                if mask & bit:
                    if bit == lights.T_KEYPAD:
                        extras.append(lights.HwrmSource(bit, u"Keypad light",
                                                        u"Keypad backlight, dimmable"))
                    else:
                        extras.append(lights.HwrmSource(bit, lights.TARGET_NAMES[bit],
                                                        u"Light target 0x%x" % bit))
                bit = bit * 2
        out = out + extras
        parts = [self.screen_src, self.led] + extras
        out.append(lights.AllSource(parts))
        keep = self.sources[self.sel].key
        self.sources = out
        for i in range(len(out)):
            if out[i].key == keep:
                self.sel = i
        names = []
        for s in out:
            names.append(s.key)
        log("sources: " + ", ".join(names))

    def get(self, key, default):
        k = self.src.key + "." + key
        return self.cfg.get(k, self.cfg.get(key, default))

    def put(self, key, value):
        self.cfg[self.src.key + "." + key] = value
        save_cfg(self.cfg)

    def mode(self):
        m = self.get("mode", "steady")
        if m not in self.src.modes:
            m = self.src.modes[0]
        return m

    def level(self):
        return self.get("level", 100)

    def colour(self):
        i = self.get("colour", 0)
        if i < 0 or i >= len(lights.COLOURS):
            i = 0
        return lights.COLOURS[i][1]

    def speed(self):
        return self.get("speed", 4)

    # ---------------------------------------------------------- ui setup

    def run(self):
        log("ui: start")
        appuifw.app.title = APP
        log("ui: title")
        appuifw.app.exit_key_handler = self.back
        self.set_screen_mode("large")
        log("ui: screen large")
        self.canvas = appuifw.Canvas(redraw_callback=self.on_redraw)
        log("ui: canvas")
        appuifw.app.body = self.canvas
        log("ui: body")
        c = self.canvas
        c.bind(key_codes.EKeyUpArrow, lambda self=self: self.key("up"))
        c.bind(key_codes.EKeyDownArrow, lambda self=self: self.key("down"))
        c.bind(key_codes.EKeyLeftArrow, lambda self=self: self.key("left"))
        c.bind(key_codes.EKeyRightArrow, lambda self=self: self.key("right"))
        c.bind(key_codes.EKeySelect, lambda self=self: self.key("select"))
        for ch in "0123456789*#":
            try:
                c.bind(ord(ch), lambda self=self, ch=ch: self.key(ch))
            except:
                pass
        log("ui: menu")
        self.set_menu()
        log("ui: first draw")
        self.draw()
        log("ui: ready")
        self.tick_timer.after(0.3, self.after_start)
        self.lock.wait()

    def after_start(self):
        """Runs once the UI is on screen: probes the hardware, then turns on
        the light chosen in Options > Turn on at start."""
        try:
            self.probe()
        except:
            log("probe: " + err_text())
            self.trace()
        self.read_battery()
        log("battery: " + self.bat.encode("utf-8"))
        self.draw()
        if self.crashed:
            appuifw.note(u"RetroTorch closed last time while using: " +
                         HW_NAMES.get(self.crashed, unicode(self.crashed)) +
                         u". It is now switched off (Options > Retry all hardware).", "info")
        start = self.cfg.get("start", "led")      # the LED torch, unless changed
        for s in self.sources:
            if s.key == start and self.status(s)[0]:
                log("start: turning on " + start)
                self.open_source(s)

    def set_menu(self):
        if self.screen == "home":
            appuifw.app.menu = [
                (u"Turn on", lambda self=self: self.key("select")),
                (u"Turn on at start", self.menu_start),
                (u"LED setup", self.led_setup),
                (u"Hardware info", self.show_info),
                (u"Retry all hardware", self.retry_hardware),
                (u"Help", self.help),
                (u"About", self.about),
                (u"Exit", self.quit)]
        else:
            items = [(u"On / off", self.toggle), (u"Mode", self.menu_mode)]
            if self.src.colours:
                items.append((u"Colour", self.menu_colour))
            if self.src.can_dim:
                items.append((u"Brightness", self.menu_level))
            items.append((u"Morse message", self.edit_morse))
            items.append((u"Auto-off timer", self.menu_timer))
            if self.src.key == "led":
                items.append((u"LED setup", self.led_setup))
            items.append((u"Back", self.back))
            items.append((u"Exit", self.quit))
            appuifw.app.menu = items

    def set_screen_mode(self, mode):
        try:
            if appuifw.app.screen != mode:
                appuifw.app.screen = mode
        except:
            pass

    # ---------------------------------------------------------- drawing

    def size(self):
        try:
            return self.canvas.size
        except:
            return (240, 292)

    def on_redraw(self, rect):
        if self.buf is not None and self.buf.size == self.size():
            try:
                self.canvas.blit(self.buf)
                return
            except:
                pass
        self.draw()

    def draw(self):
        if self.canvas is None:
            return
        if not self.drawn:
            log("draw: first (%s)" % self.screen)
        w, h = self.size()
        if self.buf is None or self.buf.size != (w, h):
            self.buf = graphics.Image.new((w, h))
        g = self.buf
        check_fonts(g)
        try:
            if self.screen == "full":
                self.paint_full(g, w, h)
            elif self.screen == "control":
                self.paint_control(g, w, h)
            else:
                self.paint_home(g, w, h)
        except:
            log("paint: " + err_text())
        try:
            self.canvas.blit(g)
        except:
            pass
        if not self.drawn:
            self.drawn = 1
            log("draw: first done")

    def header(self, g, w, title, sub):
        g.rectangle((0, 0, w, 40), fill=PANEL)
        g.text((10, 24), title, fill=TEXT, font=font("title"))
        if sub:
            g.text((w - 10 - width(g, sub, "small"), 24), sub, fill=GREY, font=font("small"))

    def battery(self):
        return self.bat              # read by read_battery(), never while drawing

    def read_battery(self):
        try:
            import sysinfo
            self.bat = u"%d%%" % sysinfo.battery()
        except:
            self.bat = u""

    def bulb(self, g, cx, cy, r, colour):
        g.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)

    def paint_home(self, g, w, h):
        g.clear(BG)
        self.header(g, w, APP, self.battery())
        rh = 46
        y0 = 46
        rows = (h - y0 - 20) / rh
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + rows:
            self.top = self.sel - rows + 1
        i = self.top
        while i < len(self.sources) and i < self.top + rows:
            s = self.sources[i]
            y = y0 + (i - self.top) * rh
            if i == self.sel:
                g.rectangle((4, y, w - 4, y + rh - 4), fill=PANEL_SEL)
            ok, status = self.status(s)
            col = YELLOW
            if not ok:
                col = DARK
            self.bulb(g, 24, y + rh / 2 - 2, 11, col)
            tc = TEXT
            if not ok:
                tc = GREY
            g.text((44, y + 18), fit(g, s.name, "name", w - 54), fill=tc, font=font("name"))
            g.text((44, y + 35), fit(g, status, "small", w - 54), fill=GREY, font=font("small"))
            i = i + 1
        g.text((10, h - 6), u"Select: turn on", fill=DARK, font=font("small"))
        self.paint_toast(g, w, h)

    def status(self, s):
        """(usable, one-line status) for the home list."""
        if s.key == "led":
            if lights.OFF.has_key("led"):
                return (0, u"Switched off: it crashed the app")
            if lights.torchhw is None:
                return (0, u"Needs torchhw module (see Hardware info)")
            if not s.available():
                return (0, u"No camera found")
            if s.method is None:
                return (1, u"Tap to set up (once)")
            return (1, lights.LED_METHODS[s.method][-1])
        if s.key == "screen":
            if s.native:
                return (1, s.info)
            return (1, u"Any colour, effects (brightness: colour only)")
        return (1, s.info)

    def paint_control(self, g, w, h):
        g.clear(BG)
        sub = self.battery()
        if self.left > 0:
            sub = u"off in %d:%02d  %s" % (self.left / 60, self.left % 60, sub)
        self.header(g, w, self.src.name, sub)
        cx = w / 2
        cy = 40 + 48
        lit = self.on and self.colour_now
        if self.on:
            ring = YELLOW
        else:
            ring = DARK
        self.bulb(g, cx, cy, 40, ring)
        inner = PANEL
        if lit:
            inner = YELLOW
            if self.src.colours and self.colour_now not in (0, 1):
                inner = self.colour_now
        elif self.on:
            inner = YELLOW_DIM
        self.bulb(g, cx, cy, 33, inner)
        label = u"OFF"
        lc = GREY
        if self.on:
            label = u"ON"
            lc = BG
            if not lit:
                lc = TEXT
        if self.busy:
            label = self.busy
            lc = TEXT
        g.text((cx - width(g, label, "big") / 2, cy + 9), label, fill=lc, font=font("big"))
        y = cy + 48
        rows = self.control_rows()
        if self.row >= len(rows):
            self.row = len(rows) - 1
        i = 0
        while i < len(rows):
            name, value = rows[i]
            ry = y + i * 26
            if ry + 24 > h - 12:
                break
            vw = width(g, value, "text")
            if i == self.row:
                g.rectangle((4, ry, w - 4, ry + 24), fill=PANEL_SEL)
                g.text((w - 18, ry + 17), u">", fill=GREY, font=font("text"))
                g.text((w - 26 - vw - 14, ry + 17), u"<", fill=GREY, font=font("text"))
            g.text((12, ry + 17), name, fill=GREY, font=font("text"))
            g.text((w - 26 - vw, ry + 17), value, fill=TEXT, font=font("text"))
            i = i + 1
        g.text((10, h - 4), u"Select: on/off   Up/Down: setting", fill=DARK, font=font("small"))
        self.paint_toast(g, w, h)

    def control_rows(self):
        rows = [(u"Mode", lights.MODE_NAMES[self.mode()])]
        if self.src.can_dim:
            rows.append((u"Brightness", u"%d%%" % self.level()))
        if self.src.colours:
            rows.append((u"Colour", lights.COLOURS[self.get("colour", 0)][0]))
        if self.mode() == "strobe" and not self.src.slow:
            rows.append((u"Speed", u"%d / s" % self.speed()))
        if self.mode() == "morse":
            rows.append((u"Message", fit_plain(self.get("morse", u"SOS"), 12)))
        t = self.get("timer", 0)
        tv = u"never"
        if t:
            tv = u"%d min" % t
        rows.append((u"Auto-off", tv))
        return rows

    def paint_full(self, g, w, h):
        c = self.colour_now
        if c == 1:
            c = self.colour()
        if not self.screen_src.native and c:
            c = lights.dim(c, self.level())
        g.clear(c)
        self.paint_toast(g, w, h)

    def paint_toast(self, g, w, h):
        if not self.toast:
            return
        tw = width(g, self.toast, "text") + 20
        x = (w - tw) / 2
        y = h - 60
        g.rectangle((x, y, x + tw, y + 28), fill=0x202020)
        g.text((x + 10, y + 19), self.toast, fill=0xFFFFFF, font=font("text"))

    def show_toast(self, text):
        self.toast = text
        self.toast_gen = self.toast_gen + 1
        gen = self.toast_gen

        def clear(self=self, gen=gen):
            if self.toast_gen == gen:
                self.toast = None
                self.draw()
        try:
            self.toast_timer.cancel()
        except:
            pass
        self.toast_timer.after(1.5, clear)
        self.draw()

    # ---------------------------------------------------------- keys

    def key(self, k):
        try:
            if self.screen == "home":
                self.key_home(k)
            elif self.screen == "full":
                self.key_full(k)
            else:
                self.key_control(k)
        except:
            log("key %s: %s" % (k, err_text()))
            self.trace()

    def key_home(self, k):
        n = len(self.sources)
        if k == "up":
            self.sel = (self.sel - 1) % n
        elif k == "down":
            self.sel = (self.sel + 1) % n
        elif k == "select" or k == "right":
            self.open_source(self.sources[self.sel])
            return
        elif len(k) == 1 and k in "123456789" and int(k) <= n:   # 2.2: 'in' takes one char
            self.sel = int(k) - 1
            self.open_source(self.sources[self.sel])
            return
        self.draw()

    def key_control(self, k):
        rows = self.control_rows()
        if k == "up":
            self.row = (self.row - 1) % len(rows)
        elif k == "down":
            self.row = (self.row + 1) % len(rows)
        elif k == "left" or k == "right":
            d = 1
            if k == "left":
                d = -1
            self.change(rows[self.row][0], d)
            return
        elif k == "select" or k == "0" or k == "5":
            if rows[self.row][0] == u"Message":
                self.edit_morse()
            else:
                self.toggle()
            return
        elif k == "*":
            self.put("mode", "sos")
            self.restart()
            return
        elif k == "#":
            self.put("mode", "strobe")
            self.restart()
            return
        self.draw()

    def key_full(self, k):
        if k == "up" or k == "down":
            self.step_level(k == "up")
            self.show_toast(u"Brightness %d%%" % self.level())
        elif k == "left" or k == "right":
            d = 1
            if k == "left":
                d = -1
            self.change(u"Colour", d)
            self.show_toast(lights.COLOURS[self.get("colour", 0)][0])
        elif k == "*" or k == "#":
            modes = self.src.modes
            i = 0
            if self.mode() in modes:
                i = modes.index(self.mode())
            d = 1
            if k == "*":
                d = -1
            self.put("mode", modes[(i + d) % len(modes)])
            self.restart()
            self.show_toast(lights.MODE_NAMES[self.mode()])
        else:
            self.light_off()
            self.go_control()

    def change(self, row, d):
        if row == u"Mode":
            modes = self.src.modes
            i = 0
            if self.mode() in modes:
                i = modes.index(self.mode())
            self.put("mode", modes[(i + d) % len(modes)])
            if self.mode() == "morse" and not self.cfg.has_key(self.src.key + ".morse"):
                self.put("morse", u"SOS")
            self.restart()
        elif row == u"Brightness":
            self.step_level(d > 0)
        elif row == u"Colour":
            n = len(lights.COLOURS)
            self.put("colour", (self.get("colour", 0) + d) % n)
            self.player.update(self.level(), self.colour())
            self.restart_if_pattern()
        elif row == u"Speed":
            sp = lights.STROBE_SPEEDS
            i = 0
            if self.speed() in sp:
                i = sp.index(self.speed())
            i = max(0, min(len(sp) - 1, i + d))
            self.put("speed", sp[i])
            self.restart()
        elif row == u"Auto-off":
            t = self.get("timer", 0)
            i = 0
            if t in AUTO_OFF:
                i = AUTO_OFF.index(t)
            self.put("timer", AUTO_OFF[(i + d) % len(AUTO_OFF)])
            if self.on:
                self.left = self.get("timer", 0) * 60
        elif row == u"Message":
            self.edit_morse()
            return
        self.draw()

    def step_level(self, up):
        lv = self.level()
        i = 0
        while i < len(LEVELS) - 1 and LEVELS[i] < lv:
            i = i + 1
        if up:
            i = min(len(LEVELS) - 1, i + 1)
        else:
            i = max(0, i - 1)
        self.put("level", LEVELS[i])
        self.player.update(self.level(), self.colour())
        self.draw()

    # ---------------------------------------------------------- light

    def open_source(self, s):
        ok, status = self.status(s)
        if not ok:
            appuifw.note(status, "info")
            if s.key == "led":
                self.show_info()
            return
        self.src = s
        self.row = 0
        self.go_control()
        self.light_on()

    def go_control(self):
        self.screen = "control"
        self.set_screen_mode("large")
        self.set_menu()
        self.draw()

    def toggle(self):
        if self.on:
            self.light_off()
        else:
            self.light_on()
        self.draw()

    def restart(self):
        if self.on:
            self.player.stop(0)
            self.start_pattern()
        self.draw()

    def restart_if_pattern(self):
        if self.on and self.mode() != "steady":
            self.restart()

    def light_on(self):
        s = self.src
        if s.key == "led" and s.method is None:
            self.led_setup()
            if s.method is None:
                return
        self.busy = u"..."
        self.draw()

        def ready(ok, msg, self=self, s=s):
            self.busy = None
            if self.src is not s or self.screen == "home":
                return
            if not ok:
                if msg:
                    appuifw.note(msg, "error")
                self.draw()
                return
            self.on = 1
            self.left = self.get("timer", 0) * 60
            self.start_ticks()
            if s.colours and s.key == "screen":
                self.screen = "full"
                self.set_screen_mode("full")
                self.set_menu()
            self.start_pattern()
            self.draw()
        s.prepare(ready)

    def start_pattern(self):
        steps = lights.pattern_steps(self.mode(), self.speed(),
                                     self.get("morse", u"SOS"), self.colour())
        if self.src.slow:
            steps = [(1, 1500), (0, 500)]
            if self.mode() == "beacon":
                steps = [(1, 1000), (0, 3000)]
        self.player.start(self.src, steps, self.level(), self.colour())

    def light_off(self):
        self.player.stop()
        self.on = 0
        self.left = 0
        self.colour_now = 0
        if self.src is not None and self.src.key in ("led", "all", "flash"):
            self.src.close()       # releases the camera so other apps can use it

    def on_state(self, colour):
        self.colour_now = colour
        if self.screen == "full" or self.screen == "control":
            self.draw()

    # once a second: auto-off countdown and keeping the backlight on
    def start_ticks(self):
        if self.ticking:
            return
        self.ticking = 1
        self.tick_timer.after(1, self.tick)

    def tick(self):
        if not self.on:
            self.ticking = 0
            return
        try:
            e32.reset_inactivity()
        except:
            pass
        if self.left % 30 == 0:
            self.read_battery()
        if self.left > 0:
            self.left = self.left - 1
            if self.left == 0:
                log("auto-off")
                self.light_off()
                if self.screen == "full":
                    self.go_control()
                self.draw()
                self.ticking = 0
                return
            if self.screen == "control":
                self.draw()
        self.tick_timer.after(1, self.tick)

    # ---------------------------------------------------------- LED setup

    def led_setup(self):
        """Tries each way of lighting the LED and asks if it worked."""
        led = self.led
        if lights.torchhw is None:
            appuifw.note(u"The torchhw module is missing", "error")
            return
        if self.on and self.src is not None:
            self.light_off()
        appuifw.note(u"LED setup: RetroTorch will try a few ways to light the LED. "
                     u"Look at the flash on the back.", "info")
        result = [None]
        i = 0
        while i < len(lights.LED_METHODS):
            api = lights.LED_METHODS[i][0]
            label = lights.LED_METHODS[i][-1]
            box = [None]
            lk = e32.Ao_lock()

            def done(ok, msg, box=box, lk=lk):
                box[0] = (ok, msg)
                lk.signal()
            led.open(api, done)
            lk.wait()
            ok, msg = box[0]
            log("LED setup %d (%s): open ok=%d %s" % (i, label.encode("utf-8"), ok,
                                                      msg.encode("utf-8")))
            if ok:
                err = 0
                try:
                    err = led.apply(i, 1)
                except:
                    log("LED setup apply: " + err_text())
                    err = -1
                e32.ao_sleep(0.6)
                log("LED setup %d: apply error %d" % (i, err))
                if err == 0:
                    # a list, not a Yes/No query: the joystick press answered
                    # "Yes" by accident in v1.0.5
                    ans = appuifw.popup_menu([u"No, still dark", u"YES, the LED is on",
                                              u"Stop testing"],
                                             u"LED on? (%d of %d)" % (i + 1, len(lights.LED_METHODS)))
                    log("LED setup %d: answer %s" % (i, repr(ans)))
                    try:
                        led.apply(i, 0)
                    except:
                        pass
                    if ans == 1:
                        result[0] = i
                        break
                    if ans == 2:
                        break
            else:
                if msg and msg.find(u"in use") >= 0:
                    appuifw.note(msg, "error")
                    break
            i = i + 1
        led.shut()
        led.method = result[0]
        self.cfg["led_method"] = result[0]
        save_cfg(self.cfg)
        if result[0] is None:
            appuifw.note(u"No steady LED mode worked on this phone. Use Flash bursts, "
                         u"or send me retrotorch_log.txt.", "info")
        else:
            appuifw.note(u"LED torch ready: " + lights.LED_METHODS[result[0]][-1], "conf")
        self.draw()

    # ---------------------------------------------------------- menus

    def menu_mode(self):
        modes = self.src.modes
        names = []
        for m in modes:
            names.append(lights.MODE_NAMES[m])
        i = appuifw.popup_menu(names, u"Mode")
        if i is not None:
            self.put("mode", modes[i])
            if modes[i] == "morse":
                self.edit_morse()
            self.restart()

    def menu_colour(self):
        names = []
        for n, c in lights.COLOURS:
            names.append(n)
        i = appuifw.popup_menu(names, u"Colour")
        if i is not None:
            self.put("colour", i)
            self.player.update(self.level(), self.colour())
            self.restart_if_pattern()
            self.draw()

    def menu_level(self):
        names = []
        for lv in LEVELS:
            names.append(u"%d%%" % lv)
        i = appuifw.popup_menu(names, u"Brightness")
        if i is not None:
            self.put("level", LEVELS[i])
            self.player.update(self.level(), self.colour())
            self.draw()

    def menu_timer(self):
        names = []
        for t in AUTO_OFF:
            if t:
                names.append(u"%d min" % t)
            else:
                names.append(u"Never")
        i = appuifw.popup_menu(names, u"Turn off after")
        if i is not None:
            self.put("timer", AUTO_OFF[i])
            if self.on:
                self.left = AUTO_OFF[i] * 60
            self.draw()

    def menu_start(self):
        names = [u"Nothing (show the list)"]   # default when not set: LED torch
        keys = ["none"]
        for s in self.sources:
            names.append(s.name)
            keys.append(s.key)
        i = appuifw.popup_menu(names, u"Turn on at start")
        if i is not None:
            self.cfg["start"] = keys[i]
            save_cfg(self.cfg)
            appuifw.note(u"At start: " + names[i], "conf")

    def edit_morse(self):
        t = appuifw.query(u"Morse message (A-Z, 0-9)", "text", self.get("morse", u"SOS"))
        if t:
            self.put("morse", t)
            self.put("mode", "morse")
            self.restart()

    # ---------------------------------------------------------- info

    def show_info(self):
        lines = []
        lines.append(u"RetroTorch %s" % VERSION)
        try:
            lines.append(u"Python for S60 %s, S60 %s" % (e32.pys60_version,
                                                          str(e32.s60_version_info)))
        except:
            pass
        if lights.torchhw is None:
            lines.append(u"Native module: MISSING (%s)" % lights.NATIVE_ERR)
            lines.append(u"Without it: screen light and flash bursts only.")
        else:
            try:
                lines.append(u"Native module: torchhw v%d" % lights.torchhw.version())
            except:
                lines.append(u"Native module: torchhw (version unknown)")
            m = lights.light_targets()
            lines.append(u"")
            lines.append(u"Light targets (HWRM): " + lights.targets_text(m))
            try:
                if not lights.OFF.has_key("camera"):
                    probe_begin("camera")
                    lines.append(u"Cameras: %d" % lights.camera_count())
                    probe_end("camera")
            except:
                pass
            if self.led.method is None:
                lines.append(u"LED torch: not set up")
            else:
                lines.append(u"LED torch: " + lights.LED_METHODS[self.led.method][-1])
            if self.on:
                lines.append(u"(turn the light off to probe the camera)")
            elif lights.OFF.has_key("led"):
                lines.append(u"(native camera switched off)")
            else:
                lines = lines + self.probe_camera()
        try:
            if lights.OFF.has_key("camera"):
                raise RuntimeError("switched off")
            import camera
            lines.append(u"")
            lines.append(u"PyS60 camera flash modes: " +
                         unicode(", ".join(camera.flash_modes())))
            camera.release()
        except:
            lines.append(u"PyS60 camera module: " + unicode(err_text()))
        off = self.cfg.get("off", [])
        if off:
            lines.append(u"")
            lines.append(u"Switched off after a crash:")
            for name in off:
                lines.append(u"  " + HW_NAMES.get(name, unicode(name)))
        lines.append(u"")
        lines.append(u"Log: E:\\retrotorch_log.txt")
        log("info:\n" + u"\n".join(lines).encode("utf-8"))
        self.text_view(u"Hardware info", u"\n".join(lines))

    def probe_camera(self):
        out = []
        for api in [2, 1]:
            box = [None]
            lk = e32.Ao_lock()

            def done(ok, msg, box=box, lk=lk):
                box[0] = (ok, msg)
                lk.signal()
            self.led.open(api, done)
            lk.wait()
            ok, msg = box[0]
            if ok:
                st = self.led.state()
                out.append(u"ECam %d flash modes: %s" % (api, lights.flash_text(st[2])))
                if api == 2:
                    out.append(u"ECam 2 advanced flash modes: %s" % lights.flash_text(st[3]))
            else:
                out.append(u"ECam %d: %s" % (api, msg))
            self.led.shut()
        return out

    def text_view(self, title, text):
        old_menu = appuifw.app.menu
        old_body = appuifw.app.body
        old_exit = appuifw.app.exit_key_handler
        t = appuifw.Text()
        t.set(text)
        lk = e32.Ao_lock()
        appuifw.app.body = t
        appuifw.app.title = title
        appuifw.app.menu = [(u"Back", lk.signal)]
        appuifw.app.exit_key_handler = lk.signal
        lk.wait()
        appuifw.app.body = old_body
        appuifw.app.menu = old_menu
        appuifw.app.exit_key_handler = old_exit
        appuifw.app.title = APP
        self.draw()

    def retry_hardware(self):
        off = self.cfg.get("off", [])
        if not off:
            appuifw.note(u"Nothing is switched off.", "info")
            return
        self.cfg["off"] = []
        save_cfg(self.cfg)
        appuifw.note(u"Switched back on. Restart RetroTorch to use it.", "conf")

    def help(self):
        self.text_view(u"Help", u"\n".join([
            u"Home: Up/Down choose a light, Select (or 1-9) turns it on.",
            u"",
            u"Light screen: Select or 0 turns it on/off. Up/Down pick a setting, "
            u"Left/Right change it. * = SOS, # = strobe.",
            u"",
            u"Screen light: the screen fills with colour. Up/Down brightness, "
            u"Left/Right colour, * and # change the effect, any other key turns it off.",
            u"",
            u"LED torch: the camera's LED as a steady light. The first time, "
            u"LED setup asks you whether the LED lit up, and remembers what works.",
            u"",
            u"Flash bursts: fires the camera flash like taking photos. Works without "
            u"the native module but is slow.",
            u"",
            u"Keypad light and extra lights: the phone's other lights, dimmable.",
            u"",
            u"All lights: everything at once, for the most light.",
            u"",
            u"Options > Turn on at start: open the app straight into a light.",
        ]))

    def about(self):
        appuifw.note(u"RetroTorch %s\nEvery light on your N79" % VERSION, "info")

    # ---------------------------------------------------------- exit

    def back(self):
        if self.screen == "home":
            self.quit()
            return
        self.light_off()
        self.screen = "home"
        self.set_screen_mode("large")
        self.set_menu()
        self.draw()

    def quit(self):
        log("exit")
        try:
            self.light_off()
        except:
            pass
        for s in self.sources:
            try:
                s.close()
            except:
                pass
        try:
            if lights.torchhw is not None:
                lights.native_log()
                lights.torchhw.close()
        except:
            pass
        save_cfg(self.cfg)
        self.lock.signal()

    def trace(self):
        try:
            import traceback
            log("".join(apply(traceback.format_exception, sys.exc_info())))
        except:
            pass


def fit_plain(t, n):
    if len(t) > n:
        return t[:n - 1] + u"..."
    return t


def main():
    log("== RetroTorch %s start" % VERSION.encode("utf-8"))
    app = TorchApp()
    try:
        app.run()
    except:
        log("crash: " + err_text())
        app.trace()
        try:
            appuifw.note(u"RetroTorch error: " + unicode(err_text()), "error")
        except:
            pass
        app.quit()
    appuifw.app.set_exit()


if not getattr(sys, "retrotorch_test", 0):   # the PC tests import without running
    main()
