#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

if [ "$#" -lt 3 ]; then
  echo "Usage: ./scripts/windows/ai-render.sh <input-wav> <out-dir> <basename> [target-lufs] [style]"
  echo "Example: ./scripts/windows/ai-render.sh /mnt/c/path/to/song.wav /mnt/c/path/to/output ai-test -14 \"bright open pop EDM like Chainsmokers\""
  exit 2
fi

input_path="$(normalize_path_arg "$1")"
out_dir="$(normalize_path_arg "$2")"
basename="$(trim_path_arg "$3")"
target_lufs="$(trim_path_arg "${4:--14}")"
jobs="$(trim_path_arg "${MASTERING_JOBS:-2}")"
if [ "$#" -ge 5 ]; then
  style="${*:5}"
else
  style="bright open pop EDM mastering in the style of Chainsmokers"
fi

mkdir -p "$out_dir"
echo "[ai-render] Input:  $input_path"
echo "[ai-render] Output: $out_dir"

env_prefix="$(build_env_prefix "${MASTERING_ENV_KEYS[@]}")"
env_prefix="$(append_reference_dir_env "$env_prefix")"

local_models_args=()
case "${MASTERING_LOCAL_MODELS:-}" in
  1|true|TRUE|yes|YES|on|ON)
    local_models_args=(--local-models)
    ;;
esac

apollo_args=()
case "${MASTERING_APOLLO:-}" in
  1|true|TRUE|yes|YES|on|ON)
    apollo_args=(--apollo)
    ;;
esac
case "${MASTERING_APOLLO_ONLY:-}" in
  1|true|TRUE|yes|YES|on|ON)
    apollo_args=(--apollo --apollo-only)
    ;;
esac

openai_args=()
case "${MASTERING_OPENAI_JUDGE:-}" in
  1|true|TRUE|yes|YES|on|ON)
    openai_args=(--ai)
    ;;
esac

run_master_with_env_prefix "$env_prefix" ai-render \
  --input "$(win_path "$input_path")" \
  --out-dir "$(win_path "$out_dir")" \
  --basename "$basename" \
  "--target-lufs=$target_lufs" \
  "--jobs=$jobs" \
  --style "$style" \
  "${openai_args[@]}" \
  "${local_models_args[@]}" \
  "${apollo_args[@]}" \
  --json-out "$(win_path "$out_dir/ai-mastering-report.json")"
