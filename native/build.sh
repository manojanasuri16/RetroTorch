#!/bin/sh
# Builds torchhw.pyd (S60 3rd Edition FP2) and torchhw_fp1.pyd (FP1) into out/.
# Run ../../symbian-sdk/setup.sh once first.
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
cp "$EPOCROOT/epoc32/release/gcce/urel/torchhw.pyd" "$EPOCROOT/epoc32/release/gcce/urel/torchhw_fp1.pyd" \
   "$EPOCROOT/epoc32/release/gcce/urel/retrotorch_rscfix.exe" out/
ls -la out
