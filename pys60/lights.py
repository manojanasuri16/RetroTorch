# RetroTorch light sources and patterns (Python for S60 1.4.5 / Python 2.2).
#
# Every light the N79 has is a "source" with the same small interface:
#   name, info, can_dim, colours, modes
#   available()        1 yes, 0 no
#   set(on, level)     level 1..100 (ignored when can_dim is 0)
#   close()
# The patterns (steady, strobe, SOS, Morse...) are run by Player, which
# switches a source on and off with an e32.Ao_timer.
#
# Light hardware:
#   screen   - the display: full-screen colour + backlight intensity
#   keypad   - keypad backlight            (HWRM target 0x2, native module)
#   extras   - any other HWRM light target the phone reports (custom targets)
#   led      - the camera's dual LED as a steady "video light" (native, ECam)
#   flash    - the same LED fired as a photo flash (PyS60 camera module;
#              works without the native module, but only as slow bursts)
#
# Python 2.2: no conditional expressions, enumerate, sorted, generators.

import e32

try:
    import torchhw
    NATIVE_ERR = None
except:
    import sys
    torchhw = None
    NATIVE_ERR = str(sys.exc_info()[1])

# CHWRMLight::TLightTarget
T_DISPLAY = 0x1
T_KEYPAD = 0x2
T_DISPLAY2 = 0x4
T_KEYPAD2 = 0x8
TARGET_NAMES = {0x1: u"Display", 0x2: u"Keypad", 0x4: u"Cover display",
                0x8: u"Cover keypad", 0x10: u"Extra light 1", 0x20: u"Extra light 2",
                0x40: u"Extra light 3", 0x80: u"Extra light 4"}

# CCamera::TFlash
F_NONE = 0x0
F_AUTO = 0x1
F_FORCED = 0x2
F_FILLIN = 0x4
F_REDEYE = 0x8
F_SLOWFRONT = 0x10
F_SLOWREAR = 0x20
F_MANUAL = 0x40
F_VIDEOLIGHT = 0x80
FLASH_NAMES = [(F_AUTO, u"auto"), (F_FORCED, u"forced"), (F_FILLIN, u"fill-in"),
               (F_REDEYE, u"red-eye"), (F_SLOWFRONT, u"slow front sync"),
               (F_SLOWREAR, u"slow rear sync"), (F_MANUAL, u"manual"),
               (F_VIDEOLIGHT, u"video light (torch)")]

CAM_STATES = [u"closed", u"reserving", u"powering on", u"ready", u"failed"]

_log = [None]


def set_logger(f):
    _log[0] = f


def log(msg):
    if _log[0] is not None:
        try:
            _log[0](msg)
        except:
            pass


class LoggedNative:
    """Wraps the native module: logs each call before it is made (the log is
    flushed per line), so if native code takes the app down, the last log line
    names the call. Each function is logged for its first 6 calls only."""

    def __init__(self, mod):
        self.mod = mod
        self.counts = {}

    def __getattr__(self, name):
        f = getattr(self.mod, name)
        if not callable(f):
            return f

        def call(*args, **kw):
            n = self.counts.get(name, 0) + 1
            self.counts[name] = n
            if n <= 6 and name != "log":
                log("native> %s%s" % (name, repr(args)))
            r = apply(f, args, kw)
            if n <= 6 and name != "log":
                log("native< %s = %s" % (name, repr(r)))
            return r
        return call


if torchhw is not None:
    torchhw = LoggedNative(torchhw)


def native_log():
    """Moves the native module's log lines into the app log."""
    if torchhw is None:
        return
    try:
        t = torchhw.log()
    except:
        return
    if t:
        for line in t.split("\n"):
            if line:
                log("native: " + line)


def flash_text(mask):
    if mask is None or mask < 0:
        return u"unknown"
    out = []
    for bit, name in FLASH_NAMES:
        if mask & bit:
            out.append(name)
    if not out:
        return u"none"
    return u", ".join(out)


def targets_text(mask):
    if mask is None or mask < 0:
        return u"unknown"
    out = []
    bit = 1
    while bit <= 0x80:
        if mask & bit:
            out.append(TARGET_NAMES.get(bit, u"0x%x" % bit))
        bit = bit * 2
    if not out:
        return u"none"
    return u", ".join(out)


_targets = [None]

# Hardware the app must not touch, because it crashed the app before
# ("lights", "camera", "led"); filled in by the app from its settings.
OFF = {}
# (begin, end) functions the app sets: begin(name) marks that risky hardware
# work has started, end(name) that it finished without taking the app down.
GUARD = [None, None]


def guard(begin, name):
    f = GUARD[0]
    if not begin:
        f = GUARD[1]
    if f is not None:
        try:
            f(name)
        except:
            pass


def light_targets():
    """The HWRM light targets (bit mask), asked once and remembered."""
    if torchhw is None or OFF.has_key("lights"):
        return -1
    if _targets[0] is None:
        try:
            _targets[0] = torchhw.light_targets()
        except:
            _targets[0] = -1
    return _targets[0]


def camera_count():
    """Number of cameras, from PyS60's own camera module (the native camera
    code is only touched when the LED torch is used)."""
    if OFF.has_key("camera"):
        return 1
    try:
        import camera
        return camera.cameras_available()
    except:
        return 1


# --------------------------------------------------------------- colours

COLOURS = [
    (u"White", 0xFFFFFF),
    (u"Warm white", 0xFFE2B0),
    (u"Red (night vision)", 0xFF0000),
    (u"Amber", 0xFFA000),
    (u"Yellow", 0xFFFF00),
    (u"Green", 0x00FF00),
    (u"Cyan", 0x00FFFF),
    (u"Blue", 0x0040FF),
    (u"Purple", 0xC000FF),
    (u"Pink", 0xFF60C0),
]


def dim(colour, level):
    """Scales an RGB colour to level percent (screen light without native)."""
    r = (colour >> 16) & 0xFF
    g = (colour >> 8) & 0xFF
    b = colour & 0xFF
    r = r * level / 100
    g = g * level / 100
    b = b * level / 100
    return r * 65536 + g * 256 + b


# --------------------------------------------------------------- patterns
# A pattern is a list of steps (state, ms). state is 0 (off) or 1 (on);
# for the screen it may also be an RGB colour. Patterns repeat forever.

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
    "!": "-.-.--", "/": "-..-.", "@": ".--.-.", "-": "-....-", "=": "-...-",
}


def morse_steps(text, unit=200):
    steps = []
    words = text.upper().split()
    wi = 0
    while wi < len(words):
        word = words[wi]
        ci = 0
        while ci < len(word):
            code = MORSE.get(word[ci], "")
            k = 0
            while k < len(code):
                if code[k] == ".":
                    steps.append((1, unit))
                else:
                    steps.append((1, unit * 3))
                if k < len(code) - 1:
                    steps.append((0, unit))      # gap inside a letter
                k = k + 1
            if code and ci < len(word) - 1:
                steps.append((0, unit * 3))      # gap between letters
            ci = ci + 1
        steps.append((0, unit * 7))              # gap between words
        wi = wi + 1
    if not steps:
        steps = [(0, 1000)]
    return steps


STROBE_SPEEDS = [1, 2, 4, 6, 8, 10, 12]          # flashes per second


def pattern_steps(mode, speed=4, morse_text=u"SOS", colour=0xFFFFFF):
    if mode == "steady":
        return [(1, 0)]
    if mode == "strobe":
        half = 500 / speed
        return [(1, half), (0, half)]
    if mode == "sos":
        return morse_steps("SOS", 180)
    if mode == "morse":
        try:
            t = morse_text.encode("ascii", "ignore")
        except:
            t = "SOS"
        return morse_steps(t, 200)
    if mode == "beacon":
        return [(1, 120), (0, 1880)]
    if mode == "heartbeat":
        return [(1, 120), (0, 160), (1, 120), (0, 1100)]
    if mode == "police":
        return [(0xFF0000, 90), (0, 50), (0xFF0000, 90), (0, 50), (0xFF0000, 90), (0, 130),
                (0x0030FF, 90), (0, 50), (0x0030FF, 90), (0, 50), (0x0030FF, 90), (0, 130)]
    if mode == "rainbow":
        out = []
        i = 0
        while i < 36:
            out.append((hue(i * 10), 80))
            i = i + 1
        return out
    if mode == "candle":
        # warm flicker; fixed sequence so it needs no random module
        levels = [100, 92, 97, 85, 100, 78, 95, 88, 100, 70, 90, 98, 83, 100, 94, 76]
        out = []
        i = 0
        while i < len(levels):
            out.append((dim(0xFFB040, levels[i]), 70 + (i * 37) % 90))
            i = i + 1
        return out
    if mode == "disco":
        cols = [0xFF0000, 0x00FF00, 0x0040FF, 0xFFFF00, 0xFF00FF, 0x00FFFF, 0xFFFFFF, 0xFF8000]
        out = []
        i = 0
        while i < len(cols):
            out.append((cols[(i * 5) % len(cols)], 125))
            i = i + 1
        return out
    if mode == "warning":
        return [(0xFFA000, 400), (0, 400)]
    return [(1, 0)]


def hue(deg):
    """HSV hue (0..359) at full saturation and value, as RGB."""
    deg = deg % 360
    x = (deg % 60) * 255 / 60
    seg = deg / 60
    if seg == 0:
        return 0xFF0000 + x * 256
    if seg == 1:
        return (255 - x) * 65536 + 0xFF00
    if seg == 2:
        return 0xFF00 + x
    if seg == 3:
        return (255 - x) * 256 + 0xFF
    if seg == 4:
        return x * 65536 + 0xFF
    return 0xFF0000 + (255 - x)


MODE_NAMES = {
    "steady": u"Steady", "strobe": u"Strobe", "sos": u"SOS", "morse": u"Morse message",
    "beacon": u"Beacon", "heartbeat": u"Heartbeat", "police": u"Police",
    "rainbow": u"Rainbow", "candle": u"Candle", "disco": u"Disco", "warning": u"Warning",
}
BLINK_MODES = ["steady", "strobe", "sos", "morse", "beacon", "heartbeat"]
SCREEN_MODES = BLINK_MODES + ["police", "rainbow", "candle", "disco", "warning"]


# --------------------------------------------------------------- sources

class Source:
    key = "?"
    name = u"?"
    info = u""
    can_dim = 0
    colours = 0          # 1: the source shows a colour (screen)
    modes = BLINK_MODES
    slow = 0             # 1: each "on" takes a second or more (photo flash)

    def available(self):
        return 1

    def prepare(self, done):
        """Gets the hardware ready, then calls done(ok, message)."""
        done(1, u"")

    def set(self, on, level=100, colour=None):
        pass

    def close(self):
        pass


class ScreenSource(Source):
    """The display. The UI paints the colour; this sets the backlight."""
    key = "screen"
    name = u"Screen light"
    info = u"Any colour, brightness, effects"
    can_dim = 1
    colours = 1
    modes = SCREEN_MODES

    def __init__(self):
        self.native = 0          # set by probe(), after the UI is up

    def probe(self):
        m = light_targets()
        if m > 0 and m & T_DISPLAY:
            self.native = 1

    def set(self, on, level=100, colour=None):
        try:
            e32.reset_inactivity()
        except:
            pass
        if not self.native:
            return
        try:
            if on:
                torchhw.light_on(T_DISPLAY, level)
            else:
                # back to the phone's own display light
                torchhw.light_on(T_DISPLAY, 0)
        except:
            log("screen light: error")

    def close(self):
        if self.native:
            try:
                torchhw.light_on(T_DISPLAY, 0)
            except:
                pass


class HwrmSource(Source):
    """A light the HWRM Light API controls (keypad, extra targets)."""

    def __init__(self, target, name, info):
        self.target = target
        self.key = "hwrm%d" % target
        self.name = name
        self.info = info
        self.can_dim = 1
        self.is_on = 0

    def available(self):
        m = light_targets()
        if m > 0 and m & self.target:
            return 1
        return 0

    def set(self, on, level=100, colour=None):
        if torchhw is None:
            return
        try:
            if on:
                err = torchhw.light_on(self.target, level)
            else:
                err = torchhw.light_off(self.target)
            if err:
                log("light 0x%x on=%d error %d" % (self.target, on, err))
            self.is_on = on
        except:
            log("light 0x%x: exception" % self.target)

    def close(self):
        if self.is_on:
            self.set(0)
        # hand the light back to the phone's normal control
        try:
            torchhw.light_on(self.target, 0, 1)
            torchhw.light_off(self.target)
        except:
            pass


# Ways of switching the LED on as a steady light, tried in this order by
# the setup wizard. (camera api, flash method, viewfinder, video, label)
#   api 2 = CCamera::New2L (extended flash modes such as video light)
#   api 1 = CCamera::NewL (classic)
#   method 0 = CCamera::SetFlashL, 1 = CCameraAdvancedSettings::SetFlashMode,
#          2 = forced photo flash instead of the video light
#   video 0 = no, 1 = video capture prepared, 2 = video frames running
# On the N79 the video light mode is accepted without error but the LED stays
# dark while the camera is idle (v1.0.5 log), so the live-camera ways go first.
LED_VERSION = 2
LED_METHODS = [
    (2, 0, 1, 0, u"Camera live, video light"),
    (2, 1, 1, 0, u"Camera live, video light (advanced)"),
    (2, 0, 1, 1, u"Video mode, video light"),
    (2, 0, 1, 2, u"Video recording, video light"),
    (2, 1, 1, 2, u"Video recording, video light (advanced)"),
    (1, 0, 1, 1, u"Classic camera, video mode"),
    (2, 0, 0, 0, u"Video light setting only"),
    (2, 1, 0, 0, u"Video light setting only (advanced)"),
    (2, 2, 1, 0, u"Camera live, forced flash"),
]


class LedSource(Source):
    """The camera's LED as a steady torch (needs the native module)."""
    key = "led"
    name = u"LED torch"
    info = u"Camera flash LED, steady light"

    def __init__(self, method=None):
        self.method = method       # index into LED_METHODS, None until set up
        self.opened = None         # (api) of the open camera
        self.is_on = 0
        self.timer = None

    def available(self):
        # No camera calls here: this is asked while the screen is drawn, and
        # touching the camera then took the whole app down on the N79.
        if torchhw is None or OFF.has_key("led"):
            return 0
        return 1

    def state(self):
        try:
            return torchhw.cam_state()
        except:
            return (0, 0, 0, -1, 0)

    def open(self, api, done):
        """Opens camera 0 with the given API; done(ok, message) when ready."""
        if self.opened == api and self.state()[0] == 3:
            done(1, u"")
            return
        self.shut()
        guard(1, "led")
        err = torchhw.cam_open(0, api)
        if err:
            native_log()
            done(0, u"camera error %d" % err)
            return
        self.opened = api
        self.wait_ready(done, 0)

    def wait_ready(self, done, tries):
        st = self.state()
        if st[0] == 3:
            native_log()
            log("camera ready, flash modes %s / adv %s" % (flash_text(st[2]), flash_text(st[3])))
            done(1, u"")
            return
        if st[0] == 4 or tries > 50:
            native_log()
            self.shut()
            if st[1] == -14:
                done(0, u"The camera is in use by another app")
            else:
                done(0, u"Camera failed (state %d, error %d)" % (st[0], st[1]))
            return
        if self.timer is None:
            self.timer = e32.Ao_timer()

        def again(self=self, done=done, tries=tries):
            self.wait_ready(done, tries + 1)
        self.timer.after(0.1, again)

    def prepare(self, done):
        if self.method is None:
            done(0, u"setup")
            return
        api = LED_METHODS[self.method][0]
        self.open(api, done)

    def apply(self, method, on):
        api, how, vf, video, label = LED_METHODS[method]
        if how == 2:
            mode = F_FORCED
            how = 0
        else:
            mode = F_VIDEOLIGHT
        err = 0
        if on:
            if vf:
                err = torchhw.cam_viewfinder(1)
            if video:
                e = torchhw.cam_video(video)
                if e:
                    err = e
            e = torchhw.cam_flash(mode, how)
            if e:
                err = e
        else:
            torchhw.cam_flash(F_NONE, how)
            if video:
                torchhw.cam_video(0)
            if vf:
                torchhw.cam_viewfinder(0)
        native_log()
        return err

    def set(self, on, level=100, colour=None):
        if self.method is None or torchhw is None:
            return
        try:
            e32.reset_inactivity()
        except:
            pass
        try:
            self.apply(self.method, on)
            self.is_on = on
        except:
            log("led: exception")

    def shut(self):
        if self.timer is not None:
            try:
                self.timer.cancel()
            except:
                pass
        if self.opened is not None:
            try:
                torchhw.cam_flash(F_NONE, 0)
            except:
                pass
            try:
                torchhw.cam_close()
            except:
                pass
            native_log()
        guard(0, "led")
        self.opened = None
        self.is_on = 0

    def close(self):
        self.shut()


class PhotoFlashSource(Source):
    """Fires the LED as a photo flash with PyS60's camera module.
    Each flash takes a photo (thrown away), so it is a slow burst."""
    key = "flash"
    name = u"Flash bursts"
    info = u"Photo flash, one burst at a time"
    modes = ["strobe", "beacon"]
    slow = 1

    def __init__(self):
        self.cam = None
        self.size = None
        self.mode = None

    def available(self):
        if OFF.has_key("camera"):
            return 0
        try:
            import camera
        except:
            return 0
        try:
            modes = camera.flash_modes()
        except:
            return 0
        if "forced" in modes:
            return 1
        return 0

    def set(self, on, level=100, colour=None):
        if not on:
            return
        try:
            import camera
            if self.size is None:
                sizes = camera.image_sizes()
                self.size = sizes[-1]          # the smallest is quickest
                self.mode = camera.image_modes()[0]
            camera.take_photo(mode=self.mode, size=self.size, flash="forced")
        except:
            import sys
            log("photo flash: " + str(sys.exc_info()[1]))

    def close(self):
        try:
            import camera
            camera.release()
        except:
            pass


class AllSource(Source):
    """Every steady light at once: screen (the UI paints it), LED, keypad
    and extra lights."""
    key = "all"
    name = u"All lights"
    info = u"Screen, LED, keypad and extras at once"
    can_dim = 1
    colours = 1
    modes = BLINK_MODES

    def __init__(self, parts):
        self.parts = parts

    def prepare(self, done):
        led = None
        for p in self.parts:
            if p.key == "led" and p.method is not None:
                led = p
        if led is None:
            done(1, u"")
            return

        def after(ok, msg, done=done):
            done(1, u"")                       # the others work without the LED
        led.prepare(after)

    def set(self, on, level=100, colour=None):
        for p in self.parts:
            if p.key == "led" and p.method is None:
                continue
            p.set(on, level, colour)

    def close(self):
        for p in self.parts:
            p.close()


# --------------------------------------------------------------- player

class Player:
    """Runs a pattern on a source. on_state(state) is called on every step
    so the UI can repaint (the screen light shows the colour)."""

    def __init__(self, on_state):
        self.on_state = on_state
        self.timer = e32.Ao_timer()
        self.source = None
        self.steps = None
        self.i = 0
        self.level = 100
        self.colour = 0xFFFFFF
        self.running = 0
        self.gen = 0

    def start(self, source, steps, level, colour):
        self.stop(0)
        self.source = source
        self.steps = steps
        self.level = level
        self.colour = colour
        self.i = 0
        self.running = 1
        self.gen = self.gen + 1
        self.step(self.gen)

    def update(self, level, colour):
        """New brightness or colour while running."""
        self.level = level
        self.colour = colour
        if self.running and len(self.steps) == 1:
            self.source.set(1, level, colour)
            self.on_state(self.state_colour(1))

    def state_colour(self, state):
        if state == 1:
            return self.colour
        return state

    def step(self, gen):
        if not self.running or gen != self.gen:
            return
        state, ms = self.steps[self.i]
        on = 0
        if state:
            on = 1
        colour = self.state_colour(state)
        self.source.set(on, self.level, colour)
        self.on_state(colour)
        if ms <= 0:
            return                              # steady: nothing to time
        self.i = (self.i + 1) % len(self.steps)

        def nxt(self=self, gen=gen):
            self.step(gen)
        try:
            self.timer.cancel()
        except:
            pass
        self.timer.after(ms / 1000.0, nxt)

    def stop(self, notify=1):
        was = self.running
        self.running = 0
        self.gen = self.gen + 1
        try:
            self.timer.cancel()
        except:
            pass
        if was and self.source is not None:
            self.source.set(0)
            if notify:
                self.on_state(0)
