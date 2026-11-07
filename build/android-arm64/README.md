# Android ARM64 standalone runtime

Builds a native Android ARM64 ELF launcher linked to an Android-targeted shared CPython runtime. No Termux, Linux distribution, or host Python is needed at runtime.

## Runtime layout

```text
runtime/
├── bin/mtk
├── lib/libpython3.13.so
├── python/
│   ├── lib/python3.13/
│   └── site-packages/
└── app/
    ├── mtkclient/
    └── <entry-script.py>
```

This is a standalone runtime bundle, not a single-file statically linked executable. CPython and native extension modules remain shared components.

## Prerequisites

- Android NDK with ARM64 Clang.
- CPython cross-built for Android arm64-v8a with shared-library support.
- Android ARM64-compatible packages in a staged site-packages directory.
- A working CLI entry script.

```bash
export ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk/<version>"
export CPYTHON_ANDROID_PREFIX="$PWD/out/cpython-android-arm64"
export ANDROID_SITE_PACKAGES="$PWD/out/site-packages"
export ANDROID_API=24
export PYTHON_VERSION=3.13
export MTK_ENTRY_SCRIPT="path/to/cli_entry.py"
bash build/android-arm64/build.sh
```

The CPython prefix must contain include/python3.13/Python.h, lib/libpython3.13.so and lib/python3.13 including lib-dynload. Do not copy host Linux native extension modules into site-packages.

## Known integration blockers

The current root mtk.py is a Termux wrapper. It polls termux-usb and attempts to invoke mtk_main.py at the repository root, which is absent. mtkclient/Library/mtk_main.py defines Main but does not expose a standalone argparse entry point in the inspected source. The build therefore requires MTK_ENTRY_SCRIPT instead of falsely packaging the Termux wrapper as a working standalone CLI.

The current Port.py treats TERMUX_USB_FD as a byte-stream descriptor. That is not automatically equivalent to libusb's device/endpoint API. Adbify must provide a tested USB transport adapter or a compatible libusb integration. Validate enumeration, interface claim, control/bulk transfers, timeouts, disconnect handling, and descriptor lifetime on hardware before calling USB support complete.

This build target only stages a supplied Android CPython runtime and application and compiles the native launcher. It does not change MTK protocol behavior or perform device operations.

## Adbify Android USB integration

The MTKClient PyUSB backend now prefers Adbify's broker-enabled libraries on
Android. Adbify's existing library map exposes these absolute paths:

- `$PREFIX/lib/libusb.so`
- `$PREFIX/lib/libusb-1.0.so` (compatibility alias)
- `$PREFIX/lib/libusb_bridge.so`

The backend preloads `libusb_bridge.so` globally, then loads
`libusb.so` by absolute path and gives that exact path to PyUSB's libusb1
backend. This avoids accidentally loading a host/Termux libusb build.

Adbify should launch the MTKClient process with the following environment
(the default paths are discovered from `$PREFIX`, but explicit paths are
recommended for a production app):

```sh
export UNITOOL_LIBUSB_PATH="$PREFIX/lib/libusb.so"
export UNITOOL_LIBUSB_BRIDGE_PATH="$PREFIX/lib/libusb_bridge.so"
unset TERMUX_USB_FD
```

Do not set `TERMUX_USB_FD` for this transport. That legacy path in
`Port.py` treats a descriptor as a byte stream and cannot implement USB
interface claiming, control transfers, or endpoint-specific bulk transfers.
The Adbify broker-enabled libusb backend must provide those standard libusb
operations through its bridge after Android USB permission has been granted.

Basic backend smoke check:

```sh
python -c 'import usb.core; from mtkclient.Library.Connection.usblib import _create_libusb_backend; b=_create_libusb_backend(); print("backend:", bool(b)); print("devices:", [(hex(d.idVendor), hex(d.idProduct)) for d in usb.core.find(find_all=True, backend=b)])'
```

A successful backend load is not by itself proof of device I/O. On an Android
device, verify permission, enumeration, interface claim, one harmless
descriptor/control read, bulk IN/OUT, timeout behavior, disconnect handling,
and release/close. Do not report transport support as complete until these
checks pass with the actual Adbify APK and USB device.


## Build directly on an Android ARM64 device (Termux / Adbify)

For a device-native build, use `build-termux.sh`. This avoids accidentally
reusing an NDK compiler path from another host (for example, a
`darwin-x86_64` compiler path copied from a macOS build environment).

Install the native compiler and Python development environment first:

```sh
pkg update
pkg install clang binutils python -y
```

Install the Python packages required by this checkout into the same Python
environment that will be used for the build. The executable builder checks
these imports before compiling:

- `usb` (PyUSB)
- `serial` (pyserial)
- `colorama`
- `Crypto.Cipher.AES` and `Crypto.Hash.SHA256` (PyCryptodome)\n- `Cryptodome.Cipher.AES` and `Cryptodome.Hash.SHA256` (PyCryptodomeX)

If pip reports a compiler path under `darwin-x86_64` or another host that is
not the current Android device, do not reuse that cross-build virtual
environment. Use the native Termux Python environment and set its compiler
explicitly:

```sh
unset ANDROID_NDK_HOME ANDROID_NDK_ROOT NDK_HOME NDK_ROOT
unset _PYTHON_HOST_PLATFORM _PYTHON_SYSCONFIGDATA_NAME
export CC=clang
export CXX=clang++
export LDSHARED="clang -shared"
python -m pip install --no-build-isolation pyusb pyserial colorama pycryptodome pycryptodomex
```

Build the executable bundle:

```sh
chmod +x build/android-arm64/build-termux.sh
./build/android-arm64/build-termux.sh
```

The output is `dist/android-arm64/`. Run the generated launcher:

```sh
./dist/android-arm64/mtk --help
```

The native `bin/mtk` is an Android ARM64 ELF executable. It embeds CPython
through `libpython`, and the output directory contains the Python standard
library, installed site-packages, application source, and shared CPython
library. It does not require invoking the `python` command at runtime.
Android system libraries and any external shared libraries required by the
Termux Python build must still be available on the device; this is not a
statically linked, single-file binary. The bundle is built for the current
Android/Termux ABI and should be rebuilt for a different Python version or
application prefix.
