# ensymble py2sis for a memory-card (E:) install that actually starts.
#
# PyS60 1.4.5 apps installed on the memory card never start on the N79: all
# files land on E:, but default.py is never run (no log at all). PyS60 looks
# for default.py on the drive the system reports for the app, which seems to
# be C: for card installs. So this build installs everything to E: as usual
# and, in addition, the small launcher (default.py) to C:\private\<uid>\. The
# launcher looks for the app's modules on both C: and E:.
#
# Usage: python2 py2sis_card.py ENSYMBLE_SRC_DIR <py2sis options...> (use --drive=E)
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + "/ensymble")   # its modules import "utils"
from ensymble.actions import py2sis

writer = py2sis.sisfile.SimpleSISWriter
orig = writer.addfile


def addfile(self, contents, target=None, *args, **kw):
    orig(self, contents, target, *args, **kw)
    print "  file %s" % target
    t = (target or u"").lower()
    if t.startswith(u"e:\\private\\") and t.endswith(u"\\default.py"):
        copy = u"C" + target[1:]
        orig(self, contents, copy, *args, **kw)
        print "  file %s (launcher copy in phone memory)" % copy

writer.addfile = addfile
py2sis.run("ensymble.py", sys.argv[2:])
