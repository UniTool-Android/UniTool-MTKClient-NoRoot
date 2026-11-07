#!/usr/bin/env bash
# Build the MTKClient native Android ARM64 launcher from inside Termux.
# The output is a relocatable runtime bundle, not a statically linked single ELF.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT_DIR:-${ROOT}/dist/android-arm64}"
PYTHON="${PYTHON:-python}"
CC="${CC:-clang}"
PREFIX="${PREFIX:-}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v "$PYTHON" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON"
command -v "$CC" >/dev/null 2>&1 || fail "Android clang not found: $CC"
[[ -n "$PREFIX" && -d "$PREFIX/lib" ]] || fail "Run inside Termux/Adbify with PREFIX set."
[[ "$(uname -m)" == "aarch64" ]] || fail "This build script must run on Android ARM64 (aarch64)."

# Do not inherit cross-build settings from a macOS/Linux CI environment.
unset ANDROID_NDK_HOME ANDROID_NDK_ROOT NDK_HOME NDK_ROOT ANDROID_NDK_HOST_TAG
unset _PYTHON_HOST_PLATFORM _PYTHON_SYSCONFIGDATA_NAME
export CC
export CXX="${CXX:-clang++}"
export LDSHARED="${LDSHARED:-clang -shared}"

eval "$("$PYTHON" - <<'PY'
import shlex, sysconfig
values = {
    "PYVER": sysconfig.get_python_version(),
    "PYTHON_INCLUDE": sysconfig.get_path("include"),
    "PYTHON_STDLIB": sysconfig.get_path("stdlib"),
    "PYTHON_SITE": sysconfig.get_path("purelib"),
    "PYTHON_PLATLIB": sysconfig.get_path("platlib"),
    "PYTHON_LDLIBRARY": sysconfig.get_config_var("LDLIBRARY") or "",
}
for k, v in values.items():
    print(f"{k}={shlex.quote(str(v or ''))}")
PY
)"

[[ -f "$ROOT/build/android-arm64/launcher.c" ]] || fail "launcher.c missing"
[[ -f "$ROOT/mtk.py" ]] || fail "mtk.py entry point missing"
[[ -f "$PYTHON_INCLUDE/Python.h" ]] || fail "Python development headers missing at $PYTHON_INCLUDE"
[[ -d "$PYTHON_STDLIB" ]] || fail "Python standard library missing at $PYTHON_STDLIB"
[[ -d "$PYTHON_SITE" ]] || fail "Python site-packages missing at $PYTHON_SITE"

# Verify required Python imports before compiling the native launcher.
"$PYTHON" - <<'PY'
import importlib
modules = ("usb", "serial", "colorama", "Crypto.Cipher.AES", "Crypto.Hash.SHA256", "Cryptodome.Cipher.AES", "Cryptodome.Hash.SHA256")
failed = []
for name in modules:
    try:
        importlib.import_module(name)
        print("OK:", name)
    except Exception as exc:
        failed.append((name, str(exc)))
if failed:
    for name, error in failed:
        print(f"MISSING: {name}: {error}")
    raise SystemExit("Install the missing Android/Termux Python packages before building.")
PY

LIBPY="$PREFIX/lib/$PYTHON_LDLIBRARY"
[[ -f "$LIBPY" ]] || fail "libpython not found: $LIBPY (install the matching Termux Python package)"

rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/lib" "$OUT/python/lib" "$OUT/python/site-packages" "$OUT/app"
cp -a "$PYTHON_STDLIB" "$OUT/python/lib/python$PYVER"
cp -a "$PYTHON_SITE/." "$OUT/python/site-packages/"
if [[ "$PYTHON_PLATLIB" != "$PYTHON_SITE" && -d "$PYTHON_PLATLIB" ]]; then
  cp -an "$PYTHON_PLATLIB/." "$OUT/python/site-packages/"
fi
cp "$LIBPY" "$OUT/lib/"
cp -a "$ROOT/mtkclient" "$OUT/app/mtkclient"
cp "$ROOT/mtk.py" "$OUT/app/mtk.py"
[[ ! -d "$ROOT/payloads" ]] || cp -a "$ROOT/payloads" "$OUT/app/"
[[ ! -d "$ROOT/mtkclient/Loader" ]] || true

# Build an Android ELF executable that embeds CPython and runs the bundled
# application. The binary links to the bundled libpython, not to python3.
"$CC" -std=c11 -O2 -fPIE -pie \
  -I"$PYTHON_INCLUDE" \
  "$ROOT/build/android-arm64/launcher.c" \
  -L"$OUT/lib" -lpython"$PYVER" \
  -Wl,-rpath,'$ORIGIN/../lib' \
  -Wl,--enable-new-dtags \
  -o "$OUT/bin/mtk"

if command -v llvm-readelf >/dev/null 2>&1; then
  llvm-readelf -h "$OUT/bin/mtk" | grep -q 'AArch64' || fail "Output is not AArch64 ELF"
elif command -v readelf >/dev/null 2>&1; then
  readelf -h "$OUT/bin/mtk" | grep -q 'AArch64' || fail "Output is not AArch64 ELF"
fi

cat > "$OUT/BUILD-INFO.txt" <<EOF
Target: Android arm64-v8a
Build host: Termux / Android aarch64
Python: $PYVER
Executable: bin/mtk
Entry point: app/mtk.py
Runtime: bundled Python standard library, site-packages and libpython
EOF

cat > "$OUT/mtk" <<EOF
#!/system/bin/sh
HERE="\$(CDPATH= cd -- "\$(dirname -- "\$0")" && pwd)"
export PYTHONHOME="\$HERE/python"
export LD_LIBRARY_PATH="\$HERE/lib:$PREFIX/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
exec "\$HERE/bin/mtk" "\$HERE/app/mtk.py" "\$@"
EOF
chmod 755 "$OUT/bin/mtk" "$OUT/mtk"

printf '\nBuild complete: %s\n' "$OUT"
printf 'Executable: %s/bin/mtk\n' "$OUT"
printf 'Run: %s/mtk --help\n' "$OUT"
