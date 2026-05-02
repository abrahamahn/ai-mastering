#!/usr/bin/env bash
# Simple front door for the committed mastering chain.
#
# Common usage:
#   ./master.sh
#   ./master.sh song.wav
#   ./master.sh /mnt/c/Production/music/Submission/song.wav
#   ./master.sh /mnt/c/Production/music/Submission
#   ./master.sh --apollo /mnt/c/Production/music/Submission/song.wav
#   ./master.sh --apollo-only /mnt/c/Production/music/Submission/song.wav
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
  ./master.sh --apollo <input-wav>
  ./master.sh --apollo-only <input-wav>

Options:
  --apollo      enable Apollo restoration candidates for this run
  --apollo-only run only Apollo restoration; skip VST mastering candidates
  --no-apollo   disable Apollo even if MASTERING_APOLLO=1 is set
  --fast        disable OpenAI judging and optional CLAP/MERT local model scoring
  --jobs N      parallel candidate render jobs
  --target N    target LUFS, default from MASTERING_PRIMARY_LUFS or -14
  --reuse-output
                write directly to <input folder>/masters instead of a timestamped run folder

Defaults:
  no args       newest source WAV in /mnt/c/Production/music/Submission
  output dir    <input folder>/masters/<basename>_<timestamp>
  basename      input filename without .wav

Examples:
  ./master.sh /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --apollo /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --apollo-only --fast /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --apollo --fast /mnt/c/Production/music/Submission/abe002_mulholland.wav
  ./master.sh --jobs 2 /mnt/c/Production/music/Submission/abe002_mulholland.wav
  MASTERING_REFERENCE_DIR=/mnt/c/Production/music/references ./master.sh
EOF
}

apollo_flag=""
reuse_output=0
positionals=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --apollo)
      apollo_flag="1"
      shift
      ;;
    --apollo-only)
      apollo_flag="1"
      export MASTERING_APOLLO_ONLY=1
      shift
      ;;
    --no-apollo)
      apollo_flag="0"
      shift
      ;;
    --fast)
      export MASTERING_LOCAL_MODELS=0
      export MASTERING_OPENAI_JUDGE=0
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
if [ "$apollo_flag" = "1" ]; then
  export MASTERING_APOLLO=1
elif [ "$apollo_flag" = "0" ]; then
  export MASTERING_APOLLO=0
fi

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

echo "[master] Source:  $input_wav"
echo "[master] Output:  $out_dir"
echo "[master] Name:    $basename"
echo ""

"$SCRIPT_DIR/ai-render.sh" "$input_wav" "$out_dir" "$basename" "$target_lufs" "$style"
