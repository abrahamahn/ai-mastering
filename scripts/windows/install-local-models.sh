#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

REQ_WIN="$(win_path "$MASTERING_ROOT/requirements-local-models.txt")"
powershell.exe -NoProfile -NonInteractive -Command "& '$(ps_escape "$WINDOWS_PYTHON")' -m pip install -r '$(ps_escape "$REQ_WIN")'"
