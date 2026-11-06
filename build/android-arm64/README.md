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
