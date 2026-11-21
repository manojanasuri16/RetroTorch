#!/bin/sh
# Renders RetroTorch's screens to PNGs (needs python3 + Pillow and Noto Sans).
#   sh tests/preview/preview.sh [out_dir]
set -e
cd "$(dirname "$0")"
OUT=${1:-/tmp/retrotorch-preview}
mkdir -p "$OUT"
python3 widths.py "$OUT/widths.json"
RT_WIDTHS="$OUT/widths.json" RT_OUT="$OUT" ../../../../retrosend/tools/mamba/py27/bin/python2 preview.py
python3 render.py "$OUT/screens.json" "$OUT"
