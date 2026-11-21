#!/bin/sh
# One-time setup of a Symbian C++ toolchain for S60 3rd FP2 (Nokia N79) on Linux,
# with GnuPoc (https://www.martin.st/symbian/). Downloads are in downloads/:
#   gnu-csl-arm-2005Q1C-arm-none-symbianelf-i686-pc-linux-gnu.tar.bz2  (GCCE 3.4.3)
#   gnupoc-package-1.22.tar.gz
#   S60_3rd_FP2_SDK_v1_1_1.zip   (= S60_SDK_3.2_v1.1.1_en.zip, archive.org)
#   PyS60_1.4.5.zip              (its SDK plugin: Python.h, python222.dso)
# Needs: unshield (sudo pacman -S unshield), zlib, openssl, flex, bison, lib32-glibc.
set -e
cd "$(dirname "$0")"
TOP=$(pwd)
which unshield >/dev/null || { echo "install unshield first: sudo pacman -S unshield"; exit 1; }

# 1. compiler (prebuilt 32-bit Linux binaries)
[ -x csl-gcc/bin/arm-none-symbianelf-gcc ] || {
  mkdir -p csl-gcc; tar xjf downloads/gnu-csl-arm-2005Q1C-arm-none-symbianelf-i686-pc-linux-gnu.tar.bz2 -C csl-gcc; }
csl-gcc/bin/arm-none-symbianelf-gcc --version | head -1

# 2. native SDK tools (elf2e32, rcomp, makesis, ...) built from GnuPoc source.
# That code is from ~2010: wrap the host compilers with old-standard flags.
mkdir -p compat-bin
printf '#!/bin/sh\nexec /usr/bin/g++ -std=gnu++98 -fpermissive -w -fcommon "$@"\n' > compat-bin/g++
printf '#!/bin/sh\nexec /usr/bin/gcc -std=gnu89 -w -fcommon -Wno-error=implicit-function-declaration -Wno-error=int-conversion -Wno-error=incompatible-pointer-types "$@"\n' > compat-bin/gcc
cp compat-bin/g++ compat-bin/c++; cp compat-bin/gcc compat-bin/cc
chmod +x compat-bin/*
export PATH="$TOP/compat-bin:$PATH"
[ -d gnupoc/gnupoc-package-1.22 ] || { mkdir -p gnupoc; tar xzf downloads/gnupoc-package-1.22.tar.gz -C gnupoc; }
# (makesis is skipped: it needs OpenSSL 1.0, and ensymble makes the .sis anyway)
if [ ! -x csl-gcc/bin/elf2e32 ]; then
  T=gnupoc/gnupoc-package-1.22/tools
  grep -v 'makesis-4' $T/install_eka2_tools | grep -v 'petran-1.1.0 &&' | grep -v 'bmconv-1.1.0-2 &&' |
    grep -v 'rcomp-7.0.1 &&' | grep -v 'make-3.81' > $T/install_eka2_tools_nosis
  ln -sf /usr/bin/make "$TOP/csl-gcc/bin/extmake"   # patched make 3.81 is only for icon makefiles
  [ -x csl-gcc/bin/uidcrc ] || (cd $T/petran-1.1.0 && make && cp e32uid/uidcrc "$TOP/csl-gcc/bin")
  [ -x csl-gcc/bin/bmconv ] || (cd $T/bmconv-1.1.0-2 && make && cp src/bmconv "$TOP/csl-gcc/bin")
  [ -x csl-gcc/bin/rcomp ] || (cd $T/rcomp-7.0.1 && make && cp src/rcomp "$TOP/csl-gcc/bin")
  (cd $T && sed -i 's#\$0 != "./install_eka2_tools"#0 = 1#' install_eka2_tools_nosis && sh ./install_eka2_tools_nosis "$TOP/csl-gcc")
fi

# 3. the S60 3.2 SDK, unpacked and patched for Linux
[ -d s60_32/epoc32 ] || (cd gnupoc/gnupoc-package-1.22/sdks &&
  ./install_gnupoc_s60_32 "$TOP/downloads/S60_3rd_FP2_SDK_v1_1_1.zip" "$TOP/s60_32")
[ -x gnupoc-bin/abld ] || (cd gnupoc/gnupoc-package-1.22/sdks && ./install_wrapper "$TOP/gnupoc-bin")
# the wrapper looks for the compiler in ~/csl-gcc; point it here
sed -i "s#^EKA2TOOLS=.*#EKA2TOOLS=$TOP/csl-gcc/bin#" gnupoc-bin/gnupoc-common.sh
# old SDK perl uses defined(%hash), an error in modern perl
find s60_32/epoc32/tools -name "*.pm" -o -name "*.pl" | xargs perl -pi -e 's/\bdefined\s*\(\s*([%@])/(\1/g; s/\bdefined\s+([%@])/\1/g'

# 4. PyS60 1.4.5 SDK plugin: headers and python222.dso
if [ ! -f s60_32/epoc32/include/python/Python.h ]; then
  mkdir -p pys60-sdk-src && cd pys60-sdk-src
  unzip -qo ../downloads/PyS60_1.4.5.zip PythonForS60_1_4_5_SDK_3rdEd.zip
  unzip -qo PythonForS60_1_4_5_SDK_3rdEd.zip
  mkdir -p files && unzip -qo PythonForS60_SDK_3rdEd/sdk_files.zip -d files
  cp -r files/epoc32/include/python ../s60_32/epoc32/include/
  cp files/epoc32/release/armv5/lib/python222*.dso ../s60_32/epoc32/release/armv5/lib/
  cd ..
fi
echo "Symbian toolchain ready: EPOCROOT=$TOP/s60_32/"

# 5. ECam advanced settings (CCameraAdvancedSettings: flash modes incl. video light),
#    from the FP2 API Plug-In Pack (not in the public SDK)
if [ ! -f s60_32/epoc32/include/ecamadvancedsettings.h ]; then
  [ -f downloads/S60_3rd_Ed_SDK_FP2_API_Plug-In_Pack_LLA_1_3.zip ] || tools/pget.sh \
    https://archive.org/download/nokia_sdks_n_dev_tools/S60_3rd_Ed_SDK_FP2_API_Plug-In_Pack_LLA_1_3.zip \
    downloads/S60_3rd_Ed_SDK_FP2_API_Plug-In_Pack_LLA_1_3.zip 16
  mkdir -p apipack/x/adv && unzip -qo downloads/S60_3rd_Ed_SDK_FP2_API_Plug-In_Pack_LLA_1_3.zip \
    SymbianOnboardCameraAdvancedSettingsAPI.zip -d apipack
  unzip -qo apipack/SymbianOnboardCameraAdvancedSettingsAPI.zip -d apipack/x/adv
  cp apipack/x/adv/epoc32/include/* s60_32/epoc32/include/
  cp apipack/x/adv/epoc32/release/armv5/lib/* s60_32/epoc32/release/armv5/lib/
fi
