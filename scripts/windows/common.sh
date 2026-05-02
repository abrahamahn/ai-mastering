#!/usr/bin/env bash
# Shared WSL -> Windows helpers for the mastering app scripts.

WINDOWS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERING_ROOT="$(cd "$WINDOWS_SCRIPT_DIR/../.." && pwd)"

_remember_env_override() {
  local name="$1"
  if [ "${!name+x}" = "x" ]; then
    eval "__ABE_ENV_${name}_SET=1"
    eval "__ABE_ENV_${name}_VALUE=\${$name}"
  else
    eval "__ABE_ENV_${name}_SET=0"
    eval "__ABE_ENV_${name}_VALUE="
  fi
}

_restore_env_override() {
  local name="$1"
  local set_var="__ABE_ENV_${name}_SET"
  local value_var="__ABE_ENV_${name}_VALUE"
  if [ "${!set_var:-0}" = "1" ]; then
    export "$name=${!value_var}"
  fi
}

for _name in \
  WINDOWS_PYTHON \
  MASTERING_JOBS \
  MASTERING_LOCAL_MODELS \
  MASTERING_LOCAL_MODELS_OFFLINE \
  MASTERING_MODEL_DEVICE \
  MASTERING_MODEL_CLIP_SECONDS \
  MASTERING_LEGACY_CANDIDATES \
  MASTERING_APOLLO \
  MASTERING_APOLLO_ONLY \
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
  TRANSFORMERS_CACHE; do
  _remember_env_override "$_name"
done

if [ -f "$MASTERING_ROOT/.env.local" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$MASTERING_ROOT/.env.local"
  set +a
fi

for _name in \
  WINDOWS_PYTHON \
  MASTERING_JOBS \
  MASTERING_LOCAL_MODELS \
  MASTERING_LOCAL_MODELS_OFFLINE \
  MASTERING_MODEL_DEVICE \
  MASTERING_MODEL_CLIP_SECONDS \
  MASTERING_LEGACY_CANDIDATES \
  MASTERING_APOLLO \
  MASTERING_APOLLO_ONLY \
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
  TRANSFORMERS_CACHE; do
  _restore_env_override "$_name"
done
unset _name

WINDOWS_PYTHON="${WINDOWS_PYTHON:-python.exe}"
MASTER_PY_WIN="$(wslpath -w "$MASTERING_ROOT/master.py")"

ps_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

trim_path_arg() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf "%s" "$value"
}

normalize_path_arg() {
  local value
  value="$(trim_path_arg "$1")"
  if [[ "$value" =~ ^[A-Za-z]:[\\/] ]]; then
    wslpath -u "$value"
    return
  fi
  local slashified="${value//\\//}"
  if [[ "$slashified" == /mnt/* ]]; then
    value="$slashified"
  fi
  printf "%s" "$value"
}

win_path() {
  wslpath -w "$(normalize_path_arg "$1")"
}

build_master_command() {
  local command
  command="& '$(ps_escape "$WINDOWS_PYTHON")' '$(ps_escape "$MASTER_PY_WIN")'"
  for arg in "$@"; do
    command="${command} '$(ps_escape "$arg")'"
  done
  printf "%s" "$command"
}

run_master() {
  powershell.exe -NoProfile -NonInteractive -Command "$(build_master_command "$@")"
}

run_master_with_env_prefix() {
  local env_prefix="$1"
  shift
  powershell.exe -NoProfile -NonInteractive -Command "${env_prefix}$(build_master_command "$@")"
}

build_env_prefix() {
  local prefix=""
  local name
  local value
  for name in "$@"; do
    value="${!name:-}"
    if [ -n "$value" ]; then
      prefix="${prefix}\$env:${name}='$(ps_escape "$value")'; "
    fi
  done
  printf "%s" "$prefix"
}

append_reference_dir_env() {
  local prefix="$1"
  if [ -n "${MASTERING_REFERENCE_DIR:-}" ]; then
    local reference_dir="$MASTERING_REFERENCE_DIR"
    if [[ "$reference_dir" = /* ]]; then
      reference_dir="$(win_path "$reference_dir")"
    fi
    prefix="${prefix}\$env:MASTERING_REFERENCE_DIR='$(ps_escape "$reference_dir")'; "
  fi
  printf "%s" "$prefix"
}
