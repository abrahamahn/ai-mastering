#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 3 ]; then
  echo "Usage: ./scripts/windows/render.sh <input-wav> <out-dir> <basename> [targets]"
  echo "Example: ./scripts/windows/render.sh /mnt/c/path/to/song.wav /mnt/c/path/to/output master-test -14,-12"
  exit 2
fi

input_path="$1"
out_dir="$2"
basename="$3"
if [ "$#" -ge 4 ]; then
  targets="${*:4}"
  targets="${targets//[[:space:]]/}"
else
  targets="-14,-12"
fi

mkdir -p "$out_dir"

run_master render \
  --input "$(win_path "$input_path")" \
  --out-dir "$(win_path "$out_dir")" \
  --basename "$basename" \
  "--targets=$targets" \
  --json-out "$(win_path "$out_dir/mastering-report.json")"
