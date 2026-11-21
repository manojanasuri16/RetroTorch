# RetroTorch starter (installed as default.py by build_sis.sh).
# Kept tiny on purpose: it imports the real app (rtorch_app.py, shipped next to
# it) so that any error while loading -- out of memory, a missing module, a
# syntax error -- is shown on screen and logged instead of the app silently
# not opening. Python 2.2 compatible.
import sys
import os
import appuifw
import e32

UID = "e7a3d5c4"


def _log(msg):
    for d in ["E:\\", "C:\\Data\\", "C:\\"]:
        try:
            f = open(d + "retrotorch_log.txt", "a")
            f.write(msg + "\n")
            f.close()
            return
        except:
            pass


_log("")
_log("== starter running, python " + sys.version.split(" ")[0])

_here = None
for _drive in ["C", "E"]:
    _p = _drive + ":\\private\\" + UID + "\\"
    if os.path.exists(_p + "rtorch_app.py"):
        _here = _p
        if _p not in sys.path:
            sys.path.insert(0, _p)
_log("starter: app folder " + str(_here))


def _fail(where):
    _t = str(sys.exc_info()[1])
    try:
        import traceback
        _t = "".join(apply(traceback.format_exception, sys.exc_info()))
    except:
        pass
    _log("LAUNCH ERROR in " + where + ":\n" + _t)
    try:
        appuifw.note(unicode("RetroTorch could not start (" + where + "): " +
                             str(sys.exc_info()[1]), "latin-1"), "error")
        appuifw.query(u"Error details (also in retrotorch_log.txt)", "text",
                      unicode(_t, "latin-1"))
    except:
        pass


_ok = 1
# load the helper modules one by one, so the log shows which one fails
for _m in ["lights"]:
    if _ok:
        _log("starter: loading " + _m)
        try:
            __import__(_m)
            _log("starter: " + _m + " ok")
        except:
            _fail(_m)
            _ok = 0

if _ok:
    _log("starter: loading rtorch_app")
    try:
        import rtorch_app  # runs the app
    except:
        _fail("rtorch_app")
