#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

download_args=()
if [ "${1:-}" = "--download" ]; then
  download_args=(--download)
fi

env_prefix="$(build_env_prefix \
  MASTERING_LOCAL_MODELS_OFFLINE \
  MASTERING_MODEL_DEVICE \
  MASTERING_MODEL_CLIP_SECONDS \
  MASTERING_CLAP \
  MASTERING_CLAP_MODEL \
  MASTERING_MERT \
  MASTERING_MERT_MODEL \
  HF_HOME \
  HF_HUB_CACHE \
  TRANSFORMERS_CACHE)"
env_prefix="$(append_reference_dir_env "$env_prefix")"

run_master_with_env_prefix "$env_prefix" models-check "${download_args[@]}"
