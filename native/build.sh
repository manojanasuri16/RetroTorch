#!/bin/sh
# Builds torchhw.pyd (GCCE, release) into out/. Run ../../symbian-sdk/setup.sh once first.
set -e
cd "$(dirname "$0")"
SDK=$(cd ../../symbian-sdk && pwd)
export EPOCROOT=$SDK/s60_32/
export PATH=$SDK/gnupoc-bin:$SDK/csl-gcc/bin:$PATH
cd group
bldmake bldfiles
abld build gcce urel
cd ..
mkdir -p out
cp "$EPOCROOT/epoc32/release/gcce/urel/torchhw.pyd" out/
ls -la out
