#!/usr/bin/env python3
"""Read-only USB visibility diagnostic for UniTool/Adbify MTK transport."""

import argparse
import sys

import usb.core
import usb.util

from mtkclient.config.usb_ids import default_ids
from mtkclient.Library.Connection.usblib import _create_libusb_backend


def _is_supported_mtk(device):
    products = default_ids.get(device.idVendor)
    return products is not None and device.idProduct in products


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Enumerate USB devices through the configured PyUSB/libusb backend."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show every USB device, not only supported MediaTek IDs.",
    )
    args = parser.parse_args(argv)

    try:
        backend = _create_libusb_backend()
    except Exception as exc:
        print("USB backend initialization failed: {}".format(exc), file=sys.stderr)
        return 2

    if backend is None:
        print("No libusb backend is available.", file=sys.stderr)
        return 2

    print("USB backend initialized.")
    try:
        devices = list(usb.core.find(find_all=True, backend=backend) or [])
    except Exception as exc:
        print("USB enumeration failed: {}".format(exc), file=sys.stderr)
        return 2

    if not devices:
        print("No USB devices are visible to this process.")
        print("Check the UniTool USB permission and broker session.")
        return 1

    matches = []
    for device in devices:
        supported = _is_supported_mtk(device)
        if supported:
            matches.append(device)
        if not (args.all or supported):
            continue

        label = "MediaTek-supported" if supported else "other USB device"
        print(
            "{} VID={:04X} PID={:04X} device_class=0x{:02X}".format(
                label, device.idVendor, device.idProduct, device.bDeviceClass
            )
        )

        # Descriptor inspection only: do not claim interfaces, detach drivers,
        # send control/bulk transfers, or alter device state.
        try:
            for config in device:
                for interface in config:
                    endpoints = []
                    for endpoint in interface:
                        direction = (
                            "IN"
                            if usb.util.endpoint_direction(endpoint.bEndpointAddress)
                            == usb.util.ENDPOINT_IN
                            else "OUT"
                        )
                        transfer = usb.util.endpoint_type(endpoint.bmAttributes)
                        endpoints.append(
                            "{}:0x{:02X}/type{}".format(
                                direction, endpoint.bEndpointAddress, transfer
                            )
                        )
                    print(
                        "  config={} interface={} class=0x{:02X} endpoints={}".format(
                            config.bConfigurationValue,
                            interface.bInterfaceNumber,
                            interface.bInterfaceClass,
                            ", ".join(endpoints) if endpoints else "none",
                        )
                    )
        except Exception as exc:
            print("  Descriptor details unavailable: {}".format(exc))

    print("Visible devices: {}; supported MTK devices: {}".format(
        len(devices), len(matches)
    ))
    if not matches:
        print("No supported MediaTek VID/PID is currently visible.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
