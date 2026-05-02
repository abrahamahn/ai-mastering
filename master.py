#!/usr/bin/env python3
"""Compatibility entry point for the standalone mastering app."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    src = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(src))

    from mastering_app.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
