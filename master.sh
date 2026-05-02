#!/usr/bin/env bash
# Simple front door for the committed mastering chain.
#
# Common usage:
#   ./master.sh
#   ./master.sh song.wav
#   ./master.sh /mnt/c/Production/music/Submission/song.wav
#   ./master.sh /mnt/c/Production/music/Submission
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$ROOT_DIR/scripts/windows"
# shellcheck source=scripts/windows/common.sh
. "$SCRIPT_DIR/common.sh"

DEFAULT_DIR="${ABE_PENDING_DIR:-/mnt/c/Production/music/Submission}"
target_lufs="${MASTERING_PRIMARY_LUFS:--14}"
style="${MASTERING_QUICKSTART_STYLE:-bright open pop EDM mastering in the style of Chainsmokers}"

usage() {
  cat <<'EOF'
Usage:
  ./master.sh
  ./master.sh <input-wav>
  ./master.sh <folder>
  ./master.sh <input-wav> <out-dir> [basename]

Defaults:
  no args       newest source WAV in /mnt/c/Production/music/Submission
  output dir    <input folder>/masters
  basename      input filename without .wav

Examples:
  ./master.sh /mnt/c/Production/music/Submission/abe002_mulholland.wav
  MASTERING_LOCAL_MODELS=0 ./master.sh
  MASTERING_REFERENCE_DIR=/mnt/c/Production/music/references ./master.sh
  MASTERING_APOLLO=1 MASTERING_APOLLO_REPO=/mnt/c/path/to/Apollo ./master.sh
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

find_newest_wav() {
  local dir="$1"
  local found=""
  while IFS= read -r -d '' f; do
    local name
    name="$(basename "$f")"
    if [[ "$name" =~ _ai_best\.wav$|_original\.wav$|_mastered\.wav$ ]]; then
      continue
    fi
    if [[ "$name" =~ _(classic_chain|streaming_loud_open|streaming_polish_plus|preserve_open|bright_open_edm|punch_warm|punch_warm_dynamic|controlled_shimmer|deharsh_gullfoss|analog_warm_punch|musical_restore|ai_artifact_repair|dynamic_punch_image|inflator_weiss_density|emotional_vocal|tight_competitive)\.wav$ ]]; then
      continue
    fi
    found="$f"
    break
  done < <(find "$dir" -maxdepth 1 -iname "*.wav" -printf '%T@ %p\0' 2>/dev/null | sort -z -rn | cut -z -d' ' -f2-)
  printf "%s" "$found"
}

arg="${1:-$DEFAULT_DIR}"
arg="$(normalize_path_arg "$arg")"

if [ -d "$arg" ]; then
  input_wav="$(find_newest_wav "$arg")"
  if [ -z "$input_wav" ]; then
    echo "[master] No source WAV found in: $arg" >&2
    exit 1
  fi
elif [ -f "$arg" ]; then
  input_wav="$arg"
else
  echo "[master] Input not found: $arg" >&2
  exit 1
fi

input_dir="$(dirname "$input_wav")"
out_dir="$(normalize_path_arg "${2:-$input_dir/masters}")"
basename="${3:-$(basename "${input_wav%.*}")}"

echo "[master] Source:  $input_wav"
echo "[master] Output:  $out_dir"
echo "[master] Name:    $basename"
echo ""

"$SCRIPT_DIR/ai-render.sh" "$input_wav" "$out_dir" "$basename" "$target_lufs" "$style"
