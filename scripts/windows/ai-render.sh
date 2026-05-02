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

env_prefix="$(build_env_prefix \
  OPENAI_API_KEY \
  MASTERING_JOBS \
  MASTERING_LOCAL_MODELS \
  MASTERING_LOCAL_MODELS_OFFLINE \
  MASTERING_MODEL_DEVICE \
  MASTERING_MODEL_CLIP_SECONDS \
  MASTERING_LEGACY_CANDIDATES \
  MASTERING_APOLLO \
  MASTERING_APOLLO_REPO \
  MASTERING_APOLLO_PYTHON \
  MASTERING_APOLLO_SCRIPT \
  MASTERING_APOLLO_COMMAND \
  MASTERING_APOLLO_ARGS \
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

apollo_args=()
case "${MASTERING_APOLLO:-}" in
  1|true|TRUE|yes|YES|on|ON)
    apollo_args=(--apollo)
    ;;
esac

run_master_with_env_prefix "$env_prefix" ai-render \
  --input "$(win_path "$input_path")" \
  --out-dir "$(win_path "$out_dir")" \
  --basename "$basename" \
  "--target-lufs=$target_lufs" \
  "--jobs=$jobs" \
  --style "$style" \
  "${local_models_args[@]}" \
  "${apollo_args[@]}" \
  --json-out "$(win_path "$out_dir/ai-mastering-report.json")"
