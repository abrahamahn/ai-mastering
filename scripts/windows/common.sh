#!/usr/bin/env bash
# Shared WSL -> Windows helpers for the mastering app scripts.

WINDOWS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERING_ROOT="$(cd "$WINDOWS_SCRIPT_DIR/../.." && pwd)"

if [ -f "$MASTERING_ROOT/.env.local" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$MASTERING_ROOT/.env.local"
  set +a
fi

WINDOWS_PYTHON="${WINDOWS_PYTHON:-python.exe}"
MASTER_PY_WIN="$(wslpath -w "$MASTERING_ROOT/master.py")"

ps_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

win_path() {
  wslpath -w "$1"
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
