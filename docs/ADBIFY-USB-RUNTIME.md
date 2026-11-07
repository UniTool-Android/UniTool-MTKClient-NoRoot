# Adbify USB runtime integration

The Android ARM64 MTKClient backend locates Adbify's libraries using the absolute paths exported by the Adbify terminal:

- `UNITOOL_LIBUSB_PATH=$PREFIX/lib/libusb.so`
- `UNITOOL_LIBUSB_BRIDGE_PATH=$PREFIX/lib/libusb_bridge.so`

The PyUSB backend preloads the bridge with `RTLD_GLOBAL`, then opens Adbify's libusb by absolute path. Both handles are retained for the backend lifetime. Non-Android PyUSB backend selection remains unchanged.

## Important limitation

This configures library selection and loading only. The Adbify repository currently packages `libusb_bridge.so` as a binary without its source, exported ABI/header, IPC protocol, or an app-side USB permission/session service. Therefore, do not claim that Android USB permission brokerage or device I/O works until that contract is supplied and tested.

Android USB permission is granted to the Adbify app UID through `UsbManager`; environment variables and loading a shared object do not transfer that permission to a child process by themselves.

## Runtime verification

From an Adbify terminal session, verify both paths exist and point to the expected app-private files:

```sh
test -r "$UNITOOL_LIBUSB_PATH"
test -r "$UNITOOL_LIBUSB_BRIDGE_PATH"
printf '%s\n' "$UNITOOL_LIBUSB_PATH" "$UNITOOL_LIBUSB_BRIDGE_PATH"
```

A successful file check or `dlopen()` is not a USB hardware test. Full validation requires a granted Android USB session and successful enumerate/claim/control/bulk/disconnect tests.
