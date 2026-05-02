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
style="${MASTERING_QUICKSTART_STYLE:-tame Suno AI high-end distortion, wider stereo image, analog low-mid warmth, dynamic punch}"

usage() {
  cat <<'EOF'
Usage:
  ./master.sh
  ./master.sh <input-wav>
  ./master.sh <folder>
  ./master.sh <input-wav> <out-dir> [basename]
  ./master.sh --test <input-wav>

Options:
  --fast        disable optional CLAP/MERT local model scoring
  --jobs N      parallel candidate render jobs
  --target N    target LUFS, default from MASTERING_PRIMARY_LUFS or -14
  --no-test     render the full song even when MASTERING_TEST=1
  --test [MODE] render a short diagnostic clip instead of the full song.
                MODE can be loudest (default, 30s) or first (45s)
  --test-first  shortcut for --test first
  --test-loudest
                shortcut for --test loudest
  --test-seconds N
                override test clip duration in seconds
  --reuse-output
                write directly to <input folder>/masters instead of a timestamped run folder

Defaults:
  no args       newest source WAV in /mnt/c/Production/music/Submission
  output dir    <input folder>/masters/<basename>_<timestamp>
  basename      input filename without .wav

Examples:
  ./master.sh /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --test --fast /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --test first --fast /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --jobs 2 /mnt/c/Production/music/Submission/abe002_mulholland.wav
  MASTERING_REFERENCE_DIR=/mnt/c/Production/music/references ./master.sh
EOF
}

reuse_output=0
test_mode=""
test_seconds="${MASTERING_TEST_SECONDS:-}"
case "${MASTERING_TEST:-}" in
  1|true|TRUE|yes|YES|on|ON)
    test_mode="${MASTERING_TEST_MODE:-loudest}"
    ;;
esac
case "$test_mode" in
  first45) test_mode="first" ;;
  loudest30) test_mode="loudest" ;;
esac
positionals=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --fast)
      export MASTERING_LOCAL_MODELS=0
      shift
      ;;
    --jobs)
      if [ -z "${2:-}" ]; then
        echo "[master] --jobs requires a value" >&2
        exit 2
      fi
      export MASTERING_JOBS="$2"
      shift 2
      ;;
    --target)
      if [ -z "${2:-}" ]; then
        echo "[master] --target requires a value" >&2
        exit 2
      fi
      target_lufs="$2"
      shift 2
      ;;
    --no-test)
      test_mode=""
      test_seconds=""
      shift
      ;;
    --test)
      test_mode="${MASTERING_TEST_MODE:-loudest}"
      if [ -n "${2:-}" ] && [[ "$2" != -* ]] && [[ "$2" =~ ^(first|first45|loudest|loudest30)$ ]]; then
        case "$2" in
          first|first45) test_mode="first" ;;
          loudest|loudest30) test_mode="loudest" ;;
        esac
        shift 2
      else
        shift
      fi
      ;;
    --test-first)
      test_mode="first"
      shift
      ;;
    --test-loudest)
      test_mode="loudest"
      shift
      ;;
    --test-seconds)
      if [ -z "${2:-}" ]; then
        echo "[master] --test-seconds requires a value" >&2
        exit 2
      fi
      test_seconds="$2"
      shift 2
      ;;
    --reuse-output)
      reuse_output=1
      shift
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        positionals+=("$1")
        shift
      done
      ;;
    -*)
      echo "[master] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      positionals+=("$1")
      shift
      ;;
  esac
done
set -- "${positionals[@]}"

find_newest_wav() {
  local dir="$1"
  local found=""
  while IFS= read -r -d '' f; do
    local name
    name="$(basename "$f")"
    if [[ "$name" =~ _ai_|_original\.wav$|_mastered\.wav$ ]]; then
      continue
    fi
    found="$f"
    break
  done < <(find "$dir" -maxdepth 1 -iname "*.wav" -printf '%T@ %p\0' 2>/dev/null | sort -z -rn | cut -z -d' ' -f2-)
  printf "%s" "$found"
}

arg="${1:-$DEFAULT_DIR}"
arg="$(normalize_path_arg "$arg")"
if [ ! -e "$arg" ] && [[ "$arg" != */* ]] && [ -f "$DEFAULT_DIR/$arg" ]; then
  arg="$DEFAULT_DIR/$arg"
fi

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
basename="${3:-$(basename "${input_wav%.*}")}"
if [ -n "${2:-}" ]; then
  out_dir="$(normalize_path_arg "$2")"
elif [ "$reuse_output" = "1" ]; then
  out_dir="$input_dir/masters"
else
  run_stamp="$(date +%Y%m%d-%H%M%S)"
  out_dir="$input_dir/masters/${basename}_${run_stamp}"
fi

if [ -n "$test_mode" ]; then
  case "$test_mode" in
    first)
      test_seconds="${test_seconds:-45}"
      ;;
    loudest)
      test_seconds="${test_seconds:-30}"
      ;;
    *)
      echo "[master] Invalid --test mode: $test_mode (use first or loudest)" >&2
      exit 2
      ;;
  esac

  mkdir -p "$out_dir"
  test_basename="${basename}_test_${test_mode}${test_seconds}s"
  test_input_wav="$out_dir/${test_basename}.wav"
  echo "[master] Test mode: $test_mode ${test_seconds}s"
  run_master clip-test \
    --input "$(win_path "$input_wav")" \
    --output "$(win_path "$test_input_wav")" \
    --mode "$test_mode" \
    --seconds "$test_seconds"
  input_wav="$test_input_wav"
  basename="$test_basename"
fi

echo "[master] Source:  $input_wav"
echo "[master] Output:  $out_dir"
echo "[master] Name:    $basename"
echo ""

"$SCRIPT_DIR/ai-render.sh" "$input_wav" "$out_dir" "$basename" "$target_lufs" "$style"
