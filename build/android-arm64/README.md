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
