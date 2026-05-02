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

input_path="$1"
out_dir="$2"
basename="$3"
target_lufs="${4:--14}"
if [ "$#" -ge 5 ]; then
  style="${*:5}"
else
  style="bright open pop EDM mastering in the style of Chainsmokers"
fi

mkdir -p "$out_dir"

env_prefix="$(build_env_prefix \
  OPENAI_API_KEY \
  MASTERING_LOCAL_MODELS \
  MASTERING_LOCAL_MODELS_OFFLINE \
  MASTERING_MODEL_DEVICE \
  MASTERING_MODEL_CLIP_SECONDS \
  MASTERING_CLAP \
  MASTERING_CLAP_MODEL \
  MASTERING_CLAP_WEIGHT \
  MASTERING_MERT \
  MASTERING_MERT_MODEL \
  MASTERING_MERT_PRESERVATION_WEIGHT \
  MASTERING_MERT_REFERENCE_WEIGHT \
  HF_HOME \
  HF_HUB_CACHE \
  TRANSFORMERS_CACHE)"
env_prefix="$(append_reference_dir_env "$env_prefix")"

local_models_args=()
case "${MASTERING_LOCAL_MODELS:-}" in
  1|true|TRUE|yes|YES|on|ON)
    local_models_args=(--local-models)
    ;;
esac

run_master_with_env_prefix "$env_prefix" ai-render \
  --input "$(win_path "$input_path")" \
  --out-dir "$(win_path "$out_dir")" \
  --basename "$basename" \
  "--target-lufs=$target_lufs" \
  --style "$style" \
  "${local_models_args[@]}" \
  --json-out "$(win_path "$out_dir/ai-mastering-report.json")"
