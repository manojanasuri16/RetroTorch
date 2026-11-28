# PC tests for RetroTorch (Python 2.7 with the fakes in fake_s60/).
#   sh tests/run.sh
import os
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fake_s60"))
sys.path.insert(0, os.path.join(HERE, ".."))
TMP = tempfile.mkdtemp()
os.chdir(TMP)                       # the app writes E:\retrotorch.cfg here
sys.retrotorch_test = 1

import appuifw
import e32
import key_codes
import torchhw
import camera
import lights
import retrotorch

LOG = []
retrotorch.log = LOG.append
lights.set_logger(LOG.append)

failures = []


def check(cond, what):
    if not cond:
        failures.append(what)
        print("FAIL: " + what)


def new_app():
    for p in retrotorch.cfg_paths():
        if os.path.exists(p):
            os.remove(p)
    del torchhw.calls[:]
    del appuifw.notes[:]
    del appuifw.answers[:]
    del e32.timers[:]
    torchhw.state.update({"cam": 0, "polls": 0, "api": None, "flash": 0, "vf": 0, "opens": 0})
    torchhw.cam_fail[0] = 0
    appuifw.app.screen = "normal"
    lights.OFF.clear()
    lights._targets[0] = None
    app = retrotorch.TorchApp()
    app.canvas = appuifw.Canvas()
    app.set_menu()
    check(keys(app) == ["led", "screen", "all"], "before probing: %r" % keys(app))
    app.probe()
    return app


def keys(app):
    return [s.key for s in app.sources]


def no_paint_errors(where):
    bad = [l for l in LOG if str(l).startswith("paint") or str(l).startswith("key ")]
    check(not bad, where + ": errors logged: %r" % bad[:3])
    del LOG[:]


# ------------------------------------------------------------ patterns

steps = lights.morse_steps("SOS", 100)
ons = [ms for st, ms in steps if st]
check(ons == [100, 100, 100, 300, 300, 300, 100, 100, 100], "SOS on-times %r" % ons)
check(steps[-1] == (0, 700), "word gap at the end")
check(lights.pattern_steps("strobe", 10) == [(1, 50), (0, 50)], "strobe 10/s")
for d in range(0, 360, 7):
    c = lights.hue(d)
    check(0 <= c <= 0xFFFFFF, "hue %d -> %x" % (d, c))
check(lights.hue(0) == 0xFF0000 and lights.hue(120) == 0x00FF00 and lights.hue(240) == 0x0000FF,
      "hue primaries")
check(lights.dim(0xFFFFFF, 50) == 0x7F7F7F, "dim 50%")
for m in lights.SCREEN_MODES:
    st = lights.pattern_steps(m, 4, u"HELLO WORLD", 0xFFFFFF)
    check(len(st) > 0, "pattern %s empty" % m)
    for s, ms in st:
        check(type(ms) is int and ms >= 0, "pattern %s step ms %r" % (m, ms))

# ------------------------------------------------------------ sources

app = new_app()
check(keys(app) == ["led", "screen", "flash", "hwrm2", "all"], "sources %r" % keys(app))
check(app.status(app.led) == (1, u"Tap to set up (once)"), "led needs setup")
app.draw()
no_paint_errors("home")

# ------------------------------------------------------------ screen light

app.sel = keys(app).index("screen")
app.key("select")
check(app.screen == "full" and appuifw.app.screen == "full", "screen light goes full screen")
check(app.on == 1 and app.colour_now == 0xFFFFFF, "screen light white, on")
check(("on", 1, 100) in torchhw.calls, "display backlight at 100: %r" % torchhw.calls)
app.key("down")
check(app.level() == 90 and ("on", 1, 90) in torchhw.calls, "down dims to 90")
app.key("right")
check(app.colour_now == 0xFFE2B0, "right -> warm white, got %x" % app.colour_now)
app.key("#")
check(app.mode() == "strobe", "# cycles mode to strobe, got %s" % app.mode())
e32.run_for(1.0)
check(app.on == 1, "still on while strobing")
app.key("select")
check(app.screen == "control" and app.on == 0, "select turns it off")
check(("on", 1, 0) == torchhw.calls[-1], "display back to default: %r" % torchhw.calls[-3:])
no_paint_errors("screen light")
app.back()
check(app.screen == "home", "back to home")

# strobe timing on the keypad light
del torchhw.calls[:]
app.sel = keys(app).index("hwrm2")
app.key("select")
app.put("mode", "strobe")
app.put("speed", 4)
app.restart()
del torchhw.calls[:]
e32.run_for(1.0)
ons = [c for c in torchhw.calls if c[0] == "on" and c[1] == 2]
offs = [c for c in torchhw.calls if c[0] == "off" and c[1] == 2]
check(len(ons) in (4, 5) and len(offs) in (4, 5), "4 flashes/s: %d on %d off" % (len(ons), len(offs)))
app.back()
check(torchhw.calls[-1] == ("off", 2), "keypad off when leaving: %r" % torchhw.calls[-2:])
no_paint_errors("keypad")

# ------------------------------------------------------------ LED setup

# tried in LED_TRY_ORDER: method 2 no, method 0 no, method 1 yes
appuifw.answers[:] = [0, 0, 1]
app.sel = keys(app).index("led")
app.key("select")
e32.run_for(1)                         # the camera powers on asynchronously
check(app.led.method == 1, "LED method 1 chosen, got %r" % app.led.method)
check(retrotorch.load_cfg().get("led_method") == 1, "LED method saved")
check(app.on == 1, "LED on after setup")
check(torchhw.state["flash"] == lights.F_VIDEOLIGHT, "video light mode set")
check(("flash", 0x80, 1) in torchhw.calls, "advanced-settings method used")
app.key("select")
check(app.on == 0 and torchhw.state["cam"] == 0, "LED off closes the camera")
app.key("select")
e32.run_for(1)
check(app.on == 1 and torchhw.state["flash"] == 0x80, "LED back on without setup")
app.key("*")
check(app.mode() == "sos", "* = SOS")
e32.run_for(3.0)
app.back()
check(torchhw.state["cam"] == 0, "camera released on back")
no_paint_errors("led")

# the video-recording way starts the viewfinder and video frames, then the light
del torchhw.calls[:]
app.led.open(2, lambda ok, msg: None)
e32.run_for(1)
app.led.apply(3, 1)
check(("vf", 1) in torchhw.calls and ("video", 2) in torchhw.calls and
      ("flash", 0x80, 0) in torchhw.calls, "video recording method: %r" % torchhw.calls)
app.led.apply(3, 0)
check(torchhw.calls[-2:] == [("video", 0), ("vf", 0)], "video method off: %r" % torchhw.calls[-3:])
app.led.shut()

# camera in use by another app
app2 = new_app()
app2.cfg["led_method"] = 0
app2.led.method = 0
torchhw.cam_fail[0] = 1
app2.open_source(app2.led)
e32.run_for(1)
check(app2.on == 0, "no light when the camera fails")
check(appuifw.notes and appuifw.notes[-1][0] == "error" and
      appuifw.notes[-1][1].find(u"in use") >= 0, "camera busy note: %r" % appuifw.notes[-1:])
torchhw.cam_fail[0] = 0

# ------------------------------------------------------------ auto-off

app = new_app()
app.src = app.sources[keys(app).index("hwrm2")]
app.put("timer", 1)
app.open_source(app.src)
check(app.left == 60, "timer set to 60 s")
e32.run_for(30)
check(app.on == 1 and app.left == 30, "30 s left, got %d" % app.left)
e32.run_for(31)
check(app.on == 0, "auto-off after a minute")
check(e32.inactivity_resets[0] > 20, "backlight kept awake")
no_paint_errors("auto-off")

# ------------------------------------------------------------ flash bursts

del camera.photos[:]
app.back()
app.sel = keys(app).index("flash")
app.key("select")
e32.run_for(6)
check(len(camera.photos) >= 2, "photo flash fired %d times" % len(camera.photos))
check(camera.photos and camera.photos[0][2] == "forced" and camera.photos[0][1] == (160, 120),
      "forced flash, smallest size: %r" % camera.photos[:1])
app.back()

# ------------------------------------------------------------ morse, menus

app.sel = keys(app).index("screen")
app.key("select")
app.key("select")                      # off again, on the control screen
appuifw.answers[:] = [u"HI"]
app.edit_morse()
check(app.mode() == "morse" and app.get("morse", None) == u"HI", "morse text saved")
rows = [r[0] for r in app.control_rows()]
check(u"Message" in rows, "message row shown: %r" % rows)
appuifw.answers[:] = [2]
app.menu_colour()
check(app.get("colour", 0) == 2, "colour menu")
app.draw()
no_paint_errors("control screen")

# ------------------------------------------------------------ info, start

appuifw.app.body = None
app.text_view_orig = app.text_view
shown = []
app.text_view = lambda title, text: shown.append(text)
app.show_info()
check(shown and shown[0].find(u"Display, Keypad") >= 0, "info lists light targets: %r" %
      shown[:1])
check(shown and shown[0].find(u"video light") >= 0, "info lists flash modes")

app.cfg["start"] = "screen"
retrotorch.save_cfg(app.cfg)
a3 = retrotorch.TorchApp()
check(a3.cfg.get("start") == "screen", "start option saved")

# ------------------------------------------------------------ no native module

lights.torchhw = None
a4 = new_app()
check(keys(a4) == ["led", "screen", "flash", "all"], "without native: %r" % keys(a4))
check(a4.status(a4.led)[0] == 0, "LED marked unusable without native")
a4.sel = keys(a4).index("screen")
a4.key("select")
check(a4.on == 1, "screen light works without native")
a4.draw()
no_paint_errors("no native")
a4.quit()
lights.torchhw = torchhw

# ------------------------------------------------------------ FP1 native build

# torchhw_fp1.pyd (S60 3rd Edition FP1: N82, N95) has the HWRM lights but no
# camera code at all, so the LED torch must not be offered and a fresh install
# starts on the screen light instead.
real_apis = torchhw.cam_apis
torchhw.cam_apis = lambda: 0
check(lights.cam_apis() == 0 and lights.cam_api_list() == [], "FP1: no camera APIs")
check(lights.led_methods() == [], "FP1: no LED methods to try")
check(lights.default_start() == "screen", "FP1: screen light is the default start")
a9 = new_app()
check(keys(a9) == ["led", "screen", "flash", "hwrm2", "all"], "FP1 sources: %r" % keys(a9))
check(a9.status(a9.led)[0] == 0 and a9.status(a9.led)[1].find(u"no camera video light") >= 0,
      "FP1: LED unusable, got %r" % (a9.status(a9.led),))
del appuifw.notes[:]
a9.led_setup()
check(appuifw.notes and appuifw.notes[-1][1].find(u"xenon") >= 0,
      "FP1: LED setup explains why: %r" % (appuifw.notes[-1:],))
a9.after_start()
check(a9.src is a9.screen_src and a9.on == 1, "FP1: starts on the screen light")
a9.back()
no_paint_errors("fp1")
check(a9.status(a9.sources[keys(a9).index("hwrm2")])[0] == 1, "FP1: keypad light still offered")
torchhw.cam_apis = real_apis

# ------------------------------------------------------------ default start

# a fresh install opens straight into the LED torch (set up: turns it on)
a7 = new_app()
a7.led.method = 0
a7.after_start()
e32.run_for(1)
check(a7.src is a7.led and a7.on == 1, "LED torch on at start by default")
a7.back()
# switched off after a crash: no LED at start, and no error note
a8 = new_app()
lights.OFF["led"] = 1
del appuifw.notes[:]
a8.after_start()
check(a8.src is None and not appuifw.notes, "unusable LED is skipped at start: %r" % appuifw.notes)
lights.OFF.clear()

# ------------------------------------------------------------ crash guard

# the app died while asking the native lights: next start switches them off
retrotorch.probe_begin("lights")
a5 = new_app()
check("lights" in a5.cfg.get("off", []), "crashed hardware recorded: %r" % a5.cfg.get("off"))
check(keys(a5) == ["led", "screen", "flash", "all"], "no native lights after crash: %r" % keys(a5))
check(a5.crashed == "lights", "crash remembered for the note")
check(retrotorch.probe_crashed() is None, "marker cleared")
del appuifw.notes[:]
appuifw.answers[:] = [2]               # LED setup starts by default: "Stop testing"
a5.after_start()
check(appuifw.notes and appuifw.notes[0][1].find(u"Native lights") >= 0, "crash note: %r" % appuifw.notes)
a5.retry_hardware()
check(a5.cfg.get("off") == [], "retry clears the switched-off list")
# a normal LED session leaves no marker behind
a6 = new_app()
a6.led.method = 0
a6.open_source(a6.led)
e32.run_for(1)
a6.back()
check(retrotorch.probe_crashed() is None, "no marker after a normal LED session")

shutil.rmtree(TMP, True)
if failures:
    print("%d failure(s)" % len(failures))
    sys.exit(1)
print("all app tests passed")
