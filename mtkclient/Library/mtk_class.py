#!/usr/bin/env python3
"""Core MediaTek client state and connection setup."""

import logging
import os
from struct import unpack

from mtkclient.config.usb_ids import default_ids
from mtkclient.config.payloads import PathConfig
from mtkclient.Library.pltools import PLTools
from mtkclient.Library.mtk_preloader import Preloader
from mtkclient.Library.DA.mtk_daloader import DAloader
from mtkclient.Library.Port import Port
from mtkclient.Library.gui_utils import LogBase, logsetup
from mtkclient.Library.error import ErrorHandler


class Mtk(metaclass=LogBase):
    def __init__(self, config, loglevel=logging.INFO, serialportname: str = None, preinit=True):
        self.config = config
        self.pathconfig = PathConfig()
        self.__logger, self.info, self.debug, self.warning, self.error = logsetup(
            self, None, loglevel, config.gui
        )
        self.eh = ErrorHandler()

        # TERMUX_USB_FD is a brokered USB descriptor, not a serial device path.
        # USB access is provided by the configured Adbify libusb/PyUSB backend.
        self.serialportname = serialportname

        if preinit:
            self.setup(config.vid, config.pid, config.interface, serialportname)

    @staticmethod
    def _make_portconfig(vid=None, pid=None, interface=None):
        """Return the dictionary shape consumed by UsbClass."""
        if vid is None or pid is None or vid == -1 or pid == -1:
            return default_ids

        selected_interface = interface if interface is not None else -1
        return {vid: {pid: selected_interface}}

    def setup(self, vid=None, pid=None, interface=None, serialportname: str = None):
        # Only an explicitly supplied serial port uses SerialClass. Android's
        # TERMUX_USB_FD is intentionally not interpreted as serialportname.
        portconfig = self._make_portconfig(vid, pid, interface)
        self.port = Port(
            mtk=self,
            portconfig=portconfig,
            serialportname=serialportname,
            loglevel=self.__logger.level,
        )
        self.preloader = Preloader(self, self.__logger.level)
        self.daloader = DAloader(self, self.__logger.level)

    def parse_preloader(self, preloader):
        if isinstance(preloader, str) and os.path.exists(preloader):
            with open(preloader, "rb") as rf:
                data = rf.read()
        else:
            data = preloader

        data = bytearray(data)
        if len(data) >= 0x34 and data[:4] == b"\x4d\x4d\x4d\x01":
            jump_offset = unpack("<I", data[0x30:0x34])[0]
            daaddr = unpack("<I", data[0x1C:0x20])[0] + jump_offset
            return daaddr, data[jump_offset:]

        return self.config.chipconfig.da_payload_addr, data

    def bypass_security(self):
        plt = PLTools(self, self.__logger.level)
        payload_path = self.config.payloadfile or os.path.join(
            self.pathconfig.get_payloads_path(), "generic_patcher_payload.bin"
        )
        if os.path.exists(payload_path):
            return plt.runpayload(filename=payload_path)
        self.error("Security payload not found: %s", payload_path)
        return False

    def crasher(self, display=True, mode=None):
        plt = PLTools(self, self.__logger.level)
        modes = [mode] if mode is not None else range(3)
        for crash_mode in modes:
            try:
                plt.crash(crash_mode)
                if self.preloader.init():
                    return True
            except Exception as err:
                self.debug("Crash attempt %s failed: %s", crash_mode, err)
        return False

    def run_exploit(self, mode=None):
        """Invoke the selected PLTools exploit strategy."""
        plt = PLTools(self, self.__logger.level)
        try:
            return plt.run_exploit(mode) if mode else plt.run_exploit()
        except Exception as err:
            self.error("Exploit failed: %s", err)
            return False

    def get_device_info(self):
        """Return hardware information obtained by the preloader protocol."""
        return self.preloader.get_hw_info()
