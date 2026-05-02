"""Shared filesystem paths for the standalone mastering app."""
from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
PRESETS_DIR = APP_ROOT / "presets"
