#!/usr/bin/env python3
"""Command-line entry point for MTKClient."""

import sys

from mtkclient.mtk import main


if __name__ == "__main__":
    sys.exit(main() or 0)
