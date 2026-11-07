#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME}"
: "${CPYTHON_ANDROID_PREFIX:?Set CPYTHON_ANDROID_PREFIX to Android ARM64 CPython prefix}"
: "${ANDROID_SITE_PACKAGES:?Set ANDROID_SITE_PACKAGES}"
: "${MTK_ENTRY_SCRIPT:?Set MTK_ENTRY_SCRIPT to a valid Python CLI entry script}"
API="${ANDROID_API:-24}"
PYVER="${PYTHON_VERSION:-3.13}"
OUT="${OUT_DIR:-${ROOT}/dist/android-arm64}"
HOST_TAG="${ANDROID_NDK_HOST_TAG:-linux-x86_64}"
TC="${ANDROID_NDK_HOME}/toolchains/llvm/prebuilt/${HOST_TAG}"
CC="${TC}/bin/aarch64-linux-android${API}-clang"
STRIP="${TC}/bin/llvm-strip"
INC="${CPYTHON_ANDROID_PREFIX}/include/python${PYVER}"
LIB="${CPYTHON_ANDROID_PREFIX}/lib/libpython${PYVER}.so"
STD="${CPYTHON_ANDROID_PREFIX}/lib/python${PYVER}"
for p in "$CC" "$STRIP" "$INC/Python.h" "$LIB" "$STD" "$ANDROID_SITE_PACKAGES" "${ROOT}/${MTK_ENTRY_SCRIPT}"; do
  [[ -e "$p" ]] || { echo "Missing build input: $p" >&2; exit 1; }
done
rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/lib" "$OUT/python/lib" "$OUT/python/site-packages" "$OUT/app"
cp -a "$STD" "$OUT/python/lib/"
cp -a "$ANDROID_SITE_PACKAGES/." "$OUT/python/site-packages/"
# Bundle the Termux/Bionic shared-library dependencies extracted from the
# official aarch64 packages. Keep symlinks so SONAME resolution remains valid.
find "$CPYTHON_ANDROID_PREFIX/lib" -maxdepth 1 \( -type f -o -type l \) \
  \( -name "*.so" -o -name "*.so.*" \) -exec cp -a -t "$OUT/lib/" {} +
cp -a "$LIB" "$OUT/lib/"
cp -a "$ROOT/mtkclient" "$OUT/app/"
cp "${ROOT}/${MTK_ENTRY_SCRIPT}" "$OUT/app/"
[[ ! -d "$ROOT/src" ]] || cp -a "$ROOT/src" "$OUT/app/"
[[ ! -f "$ROOT/stage2.py" ]] || cp "$ROOT/stage2.py" "$OUT/app/"
"$CC" -std=c11 -O2 -fPIE -pie -I"$INC" "$ROOT/build/android-arm64/launcher.c" \
  -L"${CPYTHON_ANDROID_PREFIX}/lib" -lpython"${PYVER}" \
  -Wl,-rpath,'$ORIGIN/../lib' -o "$OUT/bin/mtk"
"$STRIP" "$OUT/bin/mtk"
printf 'Target: Android arm64-v8a\nAPI: %s\nCPython: %s\nEntry: %s\n' "$API" "$PYVER" "$MTK_ENTRY_SCRIPT" > "$OUT/BUILD-INFO.txt"
printf 'Bundled shared libraries: %s\\n' "$(find "$OUT/lib" -maxdepth 1 -name '*.so*' | wc -l)" >> "$OUT/BUILD-INFO.txt"
echo "Staged runtime: $OUT"
echo "Run: $OUT/bin/mtk <entry-script.py> --help"
