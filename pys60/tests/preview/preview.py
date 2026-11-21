# Drives RetroTorch through its screens and records each one's drawing
# (Python 2.7). Run via preview.sh, which renders the PNGs.
import sys, os, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "fake_s60"))
sys.path.insert(0, os.path.join(HERE, "rec"))      # recording graphics wins
sys.path.insert(0, os.path.join(HERE, "..", ".."))
os.chdir(tempfile.mkdtemp())
sys.retrotorch_test = 1
import appuifw, e32
import retrotorch
screens = []


def snap(app, name):
    app.draw()
    w, h = app.size()
    screens.append({"name": name, "size": [w, h], "ops": list(app.buf.ops)})


appuifw.app.screen = "large"
app = retrotorch.TorchApp()
app.canvas = appuifw.Canvas()
app.set_menu()
app.probe()
app.sel = 0
snap(app, "1-home")
app.src = app.sources[[s.key for s in app.sources].index("screen")]
app.open_source(app.src)
app.put("colour", 1)
app.player.update(app.level(), app.colour())
app.show_toast(u"Warm white")
snap(app, "2-screen-light")
app.toast = None
app.light_off()
app.go_control()
app.row = 2
snap(app, "3-screen-off")
app.back()
kp = app.sources[[s.key for s in app.sources].index("hwrm2")]
app.open_source(kp)
app.put("mode", "strobe")
app.put("timer", 5)
app.left = 299
app.row = 2
snap(app, "4-keypad-strobe")
app.back()
app.led.method = 1
app.open_source(app.led)
e32.run_for(1)
snap(app, "5-led-on")
json.dump(screens, open(os.environ["RT_OUT"] + "/screens.json", "w"))
