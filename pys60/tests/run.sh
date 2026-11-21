#!/bin/sh
# Python 2.2 checks, then the PC tests with Python 2.7.
set -e
cd "$(dirname "$0")/.."
PY2=../../retrosend/tools/mamba/py27/bin/python2
python3 tools/check_py22.py retrotorch.py launcher.py lights.py
python3 tools/check_ints.py retrotorch.py launcher.py lights.py
"$PY2" tests/test_app.py
