# RetroTorch

A torch app for the **Nokia N79** and other S60 3rd Edition phones. Its main light is the **camera's LED flash as a steady torch**, and it can also use every other light the phone has: the screen in any colour, the keypad light, and any extra lights the phone reports.

| | |
|---|---|
| **Phones** | Nokia S60 3rd Edition (FP1/FP2); written for and tested on a Nokia N79 |
| **Needs** | Python for S60 1.4.5 |
| **Install** | Phone memory or memory card (tested on the N79 from the memory card) |

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install](#install)
- [Using RetroTorch](#using-retrotorch)
- [Troubleshooting](#troubleshooting)
- [Memory card](#memory-card)
- [How it works](#how-it-works)
- [More apps for the Nokia N79](#more-apps-for-the-nokia-n79)
- [Building](#building)
- [Project layout](#project-layout)

## Features

| Light | What it does |
|---|---|
| **LED torch** (default) | The camera's dual LED as a steady light, plus strobe, SOS, Morse and beacon. A one-time setup finds the way that lights the LED on your phone. |
| **Screen light** | The whole screen in 10 colours (white, warm white, red night-vision, amber and more) with brightness control. Effects: steady, strobe, SOS, Morse, beacon, heartbeat, police, rainbow, candle, disco, warning. |
| **Flash bursts** | Fires the LED as a photo flash, about one burst every two seconds. Works even without the native module. |
| **Keypad light** | The keypad backlight, dimmable, with the same blink patterns. |
| **Extra lights** | Any other light the phone reports (the N79 has one: "Extra light 4"). |
| **All lights** | Everything at once, for the most light. |

Also:
- **Opens straight into the LED torch.** *Options → Turn on at start* chooses another light, or the list.
- **Auto-off timer:** 1 to 60 minutes.
- **Morse messages:** any text, flashed on any light.
- **Crash guard:** if a piece of hardware ever makes the app close, RetroTorch switches that piece off at the next start and tells you. *Options → Retry all hardware* turns it back on.
- **Hardware info:** lists the lights and camera flash modes your phone reports.

## Requirements

**RetroTorch does not need a hacked phone to install or run its features.** Every binary in the package (the Python app, the `torchhw.pyd` module and its native helper) is built with only user-grantable capabilities (NetworkServices, LocalServices, ReadUserData, WriteUserData, UserEnvironment; checked in the built files and in `pys60/build_sis.sh`), and the package is self-signed. On a stock S60 3rd Edition phone, set *Software installation* to **All** and *Online certificate check* to **Off** (App. mgr. > Options > Settings) so it accepts the self-signed package. The `torchhw.pyd` module talks to the camera LED and lights with only these capabilities; whether every light works on a stock phone has not been tested.

**Only the memory-card option uses the hack.** To start from a different drive than Python, the installer runs a small helper that writes into `\resource`, which needs an unlocked phone (Easy Hack Kit: EasyHackKit 2.0, which installs **RomPatcher+**, with **Open4All rp+** ticked and applied before you install; see the [unlock guide](https://github.com/manojanasuri16/symbian-unlock-guide)). Without it you will see **"Update error"** or **"requested application access not granted"** if the phone refuses that step, or the app closes at once when run from a different drive than Python. Fix: install RetroTorch on the same drive as Python for S60, with no hack needed.

(Tested on a hacked N79 only; the "stock phone" statement comes from the capability check above, not from a test on a stock phone.)

## Install

Download from the **[latest release](https://github.com/manojanasuri16/RetroTorch/releases/latest)**:

- **`RetroTorch.sis`**: the installer asks for **phone memory or memory card**. Either works, wherever Python for S60 is installed (see [Memory card](#memory-card)).

You need **Python for S60 1.4.5** (`PythonForS60_1_4_5_3rdEd.sis`) installed first. It's also attached to the [RetroSend releases](https://github.com/manojanasuri16/RetroSend/releases/latest).

On the phone:

1. **Menu → Applications → App. mgr. → Options → Settings**: *Software installation* **All**, *Online certificate check* **Off**.
2. Copy the `.sis` to the phone and open it in **File manager**.
3. Accept the one "untrusted supplier" warning (RetroTorch is self-signed).

## Using RetroTorch

### First start: LED setup
Phones differ in how their camera LED can be kept on, so the first time you use the LED torch, RetroTorch tries up to 9 ways. It starts with the way that works on the N79 ("Video mode, video light"). After each one, it asks **"LED on?"**:

- Look at the flash on the back, wait a second, then pick **"YES, the LED is on"** only if it's lit.
- Otherwise pick **"No, still dark"** and it tries the next way.

It remembers the way that worked. *Options → LED setup* runs it again.

### Keys

| Where | Key | Action |
|---|---|---|
| List | Up / Down, Select, or **1-9** | Choose a light and turn it on |
| Light screen | **Select** or **0** | On / off |
| | Up / Down | Choose a setting (mode, brightness, colour, speed, auto-off) |
| | Left / Right | Change it |
| | **\*** / **#** | SOS / strobe |
| Screen light (full screen) | Up / Down | Brightness |
| | Left / Right | Colour |
| | **\*** / **#** | Previous / next effect |
| | any other key | Off |

The right softkey goes back to the list, and exits from the list.

## Troubleshooting

- **The app does nothing when opened.** Check that Python for S60 1.4.5 is installed. If RetroTorch is on a different drive from Python and your phone isn't unlocked, see [Memory card](#memory-card).
- **The LED torch never lights.** Run *Options → LED setup* again and wait a second after each try before answering. If none of the 9 ways work, send `E:\retrotorch_log.txt` in an issue.
- **"RetroTorch closed last time while using …".** The crash guard switched that hardware off. *Options → Retry all hardware* turns it back on.
- **A log** of every step is kept in `E:\retrotorch_log.txt` (or `C:\Data\`).

## Memory card

A Python for S60 1.4.5 app on a **different drive from Python itself** normally closes at once, without a message. When the app starts, Python's `appuifw` module loads its resource file `\resource\apps\appuifwmodule.rsc` from the **app's** drive, but Python for S60 only installs that file on its own drive.

RetroTorch handles this itself. Its package includes a copy of the file and a tiny native program, `retrotorch_rscfix.exe`, that the installer runs once after installing. If the file is missing on the drive RetroTorch went to, the program copies it there. So RetroTorch works from phone memory or the memory card, with Python for S60 on either. (A Python-side fix can't work: PyS60 loads `appuifw` before it runs any of the app's Python code.)

- Tested on a Nokia N79, with RetroTorch, RetroSend and RetroTele all installed on the memory card and Python for S60 in phone memory.
- Writing into `\resource` needs an **unlocked phone** (e.g. the Open4All patch). On a phone that isn't unlocked, install RetroTorch on the same drive as Python, or copy `appuifwmodule.rsc` (attached to the release) into `resource\apps\` on the app's drive with the phone in USB *Mass storage* mode.
- A `.sis` can't install the file: the phone refuses with "Update error", because it would "eclipse" Python's own copy on the other drive.
- The same fix works for any Python for S60 1.4.5 app: see [`pys60/card/README.md`](pys60/card/README.md), [`native/rscfix/rscfix.cpp`](native/rscfix/rscfix.cpp) and [`pys60/tools/py2sis_rscfix.py`](pys60/tools/py2sis_rscfix.py).

## How it works

Python for S60 can't control the phone's lights, so RetroTorch includes a small native module, **`torchhw.pyd`** (C++, in `native/`), that gives Python:

- **HWRM Light API** (`CHWRMLight`): the display, keypad and extra light targets, with intensity and hardware blinking.
- **ECam** (`CCamera`, `CCameraAdvancedSettings`): the camera's flash modes, including `EFlashVideoLight`, plus the viewfinder and video capture.

Things learned on a real N79:

- The camera reports **video light** as a supported flash mode, and setting it returns no error. But the LED stays dark until the camera is in **video mode** (video capture prepared, viewfinder running off screen); then the video light comes on.
- **Touching the camera while the screen is being drawn** (even counting cameras, or importing PyS60's `camera` module) closes the app without any Python error. RetroTorch only touches hardware after the UI is up, inside the crash guard.
- The N79's light targets are `0x83`: display, keypad and custom target 4.

## More apps for the Nokia N79

- **[RetroSend](https://github.com/manojanasuri16/RetroSend)**: send and receive files and text with the LocalSend app on phones and computers, over Wi-Fi.
- **[RetroTele](https://github.com/manojanasuri16/RetroTele)**: a Telegram client that talks to Telegram directly, no PC or proxy needed.

Like this app, both are Python for S60 1.4.5 apps that install to phone memory or the memory card.

## Building

You need Linux, plus [RetroSend](https://github.com/manojanasuri16/RetroSend)'s `tools/` folder checked out next to this repository (its `setup.sh` provides ensymble and Python 2.7).

```sh
# PC tests (Python 2.7 with fake S60 modules) and screenshots
sh pys60/tests/run.sh
sh pys60/tests/preview/preview.sh /tmp/retrotorch-preview

# native module: first set up the Symbian toolchain next to the repository
cp -r tools/symbian-sdk ../symbian-sdk && sh ../symbian-sdk/setup.sh
sh native/build.sh            # -> native/out/torchhw.pyd, retrotorch_rscfix.exe

# package -> pys60/dist/RetroTorch.sis
sh pys60/build_sis.sh
```

`setup.sh` downloads and builds a Symbian C++ toolchain: [GnuPoc](https://www.martin.st/symbian/), the CodeSourcery GCCE 3.4.3 compiler, the S60 3rd Edition FP2 SDK, the PyS60 1.4.5 SDK plugin and the ECam advanced settings API (the SDKs come from [archive.org](https://archive.org/details/nokia_sdks_n_dev_tools)). It also patches the 2010-era tools to build on a modern Linux. It needs `unshield`.

The app is written for Python 2.2 (`pys60/tools/check_py22.py` and `check_ints.py` enforce this).

## Project layout

```
native/              C++ (Symbian): torchhw.pyd and retrotorch_rscfix.exe
  src/torchhw.cpp    HWRM lights and the camera LED, for Python
  rscfix/rscfix.cpp  run on install: puts appuifwmodule.rsc on the app's drive
  group/             Symbian build files (bld.inf, .mmp)
  eabi/              export list (inittorchhw at ordinal 1)
pys60/
  retrotorch.py      the app (UI, settings, LED setup, crash guard)
  lights.py          light sources and patterns
  launcher.py        installed as default.py; loads the app, logs errors
  card/              appuifwmodule.rsc and notes on memory-card installs
  build_sis.sh       builds both .sis packages
  tools/             Python 2.2 checks, py2sis_rscfix.py (adds the run-on-install exe)
  tests/             PC tests and screenshot preview
tools/symbian-sdk/   Symbian toolchain setup (copy next to the repository)
```

## License

MIT, see [LICENSE](LICENSE). Third-party components keep their own licences.
