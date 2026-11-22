# Memory-card installs of Python for S60 1.4.5 apps

A Python for S60 1.4.5 app installed on the **memory card** closes at once,
without showing or logging anything, unless the card has a copy of
`\resource\apps\appuifwmodule.rsc`.

**Why:** when a PyS60 1.4.5 app starts, the `appuifw` module loads its resource
file `\resource\apps\appuifwmodule.rsc` from the **app's** drive
(`appuifwmodule.cpp`: `TParse::Set(KAppuiFwRscFile, &AppFullName(), NULL)`).
Python for S60 installs that file only on its own drive, normally phone memory
(C:). For an app on the card, the lookup on E: fails, `import appuifw` fails, and
the app closes before it can do anything.

**Fix in RetroTorch:** the package ships a copy in `\resource\retrotorch\` and a
tiny native program, `retrotorch_rscfix.exe` (`native/rscfix/rscfix.cpp`), that
the installer runs once after installing (SIS "run on install", added by
`tools/py2sis_rscfix.py`). If the file is missing on the app's drive, it copies
it there. That needs an unlocked phone (writing to `\resource` is normally
reserved for TCB). Tested on a Nokia N79: app on the memory card, Python for
S60 in phone memory.

A fix in the app's Python code can't work: PyS60's app framework loads
`appuifw` before it runs any of the app's Python files.

**By hand** (phone not unlocked): copy `appuifwmodule.rsc` to
`\resource\apps\` on the app's drive:

- with the phone connected by USB in *Mass storage* mode (the card shows up as
  a drive on the PC), copy it into the card's `resource/apps/` folder, or
- with a file manager on the phone that can write to `E:\resource\`.

It can't be done with a `.sis` installer: the phone refuses with
"Update error", because a file on the card with the same name as Python's file
in phone memory would "eclipse" it, and the installer forbids that.

Installing Python for S60 itself on the memory card also works for card apps,
but then Python apps in phone memory stop starting, for the same reason in
reverse.

The file in `tree/resource/apps/` is Python for S60 1.4.5's own
`appuifwmodule.rsc` (from `PythonForS60_1_4_5_3rdEd.sis`, SHA-1
`6ddbdda8857eeef598dde4ec2afdb2550c20f82b`; Python for S60 is Apache 2.0
licensed).
