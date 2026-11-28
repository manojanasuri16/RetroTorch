#!/bin/sh
# Builds the native S60 3rd Edition app: dist/RetroTorch.sis
# (needs Python for S60 1.4.5 on the phone).
# Includes the native light module (../native/out/torchhw.pyd, made by
# ../native/build.sh) when it exists; without it the app still works with the
# screen light and flash bursts only.
# One package, dist/RetroTorch.sis: the installer asks for phone memory or the
# memory card. It works on either drive, wherever Python for S60 is installed:
# retrotorch_rscfix.exe, run once by the installer, puts appuifw's resource
# file on the app's drive (see card/README.md and tools/py2sis_rscfix.py).
set -e
cd "$(dirname "$0")"
TOOLS=../../retrosend/tools
PY=$TOOLS/mamba/py27/bin/python2
ENS=$TOOLS/ensymble/src/ensymble.py
# the version lives in retrotorch.py (VERSION = u"x.y.z"); bump it for every release
VERSION=$(sed -n 's/^VERSION = u"\([0-9.]*\)".*/\1/p' retrotorch.py)
[ -n "$VERSION" ] || { echo "VERSION not found in retrotorch.py"; exit 1; }
echo "building RetroTorch $VERSION"
mkdir -p build dist cert

# Self-signed certificate, valid 2008-2037 so it also installs when the
# phone's date is set back. Keep the key private (cert/ is not committed).
if [ ! -f cert/retrotorch_key.pem ]; then
  openssl req -x509 -newkey rsa:1024 -sha1 -nodes \
    -not_before 20080101000000Z -not_after 20371231000000Z \
    -subj "/CN=RetroTorch/O=RetroTorch" \
    -keyout cert/retrotorch_key.pem -out cert/retrotorch_cert.pem
  openssl rsa -in cert/retrotorch_key.pem -traditional -out cert/retrotorch_key.pem
fi

MODULES="lights.py"
python3 tools/check_py22.py retrotorch.py launcher.py $MODULES
python3 tools/check_ints.py retrotorch.py launcher.py $MODULES

# Files go to \private\e7a3d5c4\; the native module to \sys\bin\.
rm -rf build/app && mkdir -p build/app
cp launcher.py build/app/default.py
cp retrotorch.py build/app/rtorch_app.py
cp $MODULES build/app/
EXTRAS=""
# Both native builds go in: torchhw.pyd for S60 3rd Edition FP2, torchhw_fp1.pyd
# for FP1 phones (N82, N95), which cannot load the FP2 camera APIs. The app
# loads whichever one works (pys60/lights.py).
for m in torchhw torchhw_fp1; do
  if [ -f ../native/out/$m.pyd ]; then
    mkdir -p build/app/root/sys/bin
    cp ../native/out/$m.pyd build/app/root/sys/bin/
    echo "including native module $m.pyd"
  fi
done
if [ -f ../native/out/retrotorch_rscfix.exe ]; then
  mkdir -p build/app/root/sys/bin build/app/root/resource/retrotorch
  cp ../native/out/retrotorch_rscfix.exe build/app/root/sys/bin/
  cp card/tree/resource/apps/appuifwmodule.rsc build/app/root/resource/retrotorch/
  echo "including retrotorch_rscfix.exe (any-drive install)"
fi
if [ -d build/app/root ]; then
  EXTRAS="--extrasdir=root"
fi
if [ ! -f ../native/out/torchhw.pyd ] && [ ! -f ../native/out/torchhw_fp1.pyd ]; then
  echo "WARNING: no native module built (native/build.sh): screen light and flash bursts only"
fi

OPTS="--uid=0xE7A3D5C4 --appname=RetroTorch --version=$VERSION \
  --caption=RetroTorch --shortcaption=RetroTorch --vendor=RetroTorch --icon=icon.svg \
  --caps=LocalServices+NetworkServices+ReadUserData+WriteUserData+UserEnvironment \
  --heapsize=4k,4M $EXTRAS --cert=cert/retrotorch_cert.pem --privkey=cert/retrotorch_key.pem"

rm -f dist/RetroTorch-card.sis dist/PyS60-CardSupport.sis dist/appuifwmodule.rsc
$PY tools/py2sis_rscfix.py "$(dirname $ENS)" $OPTS --drive=any build/app dist/RetroTorch.sis \
  </dev/null >build/py2sis.log
grep "rscfix" build/py2sis.log
cat build/py2sis.log | grep -i warn || true
echo "built dist/RetroTorch.sis"
ls -la dist
