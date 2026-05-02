#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTERING_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

DEFAULT_STYLE="tame Suno AI high-end distortion, wider stereo image, analog low-mid warmth, dynamic punch"

usage() {
  cat <<'EOF'
Abe Mastering quickstart

Usage:
  master-quickstart.sh [folder-or-wav]

Selection accepts:
  all       all listed source WAVs
  1         one file number
  1,3,5     multiple file numbers
  1-3       number range
  abe001    filename text match
EOF
}

is_source_wav() {
  local path="$1"
  local name
  name="$(basename "$path")"
  case "${name,,}" in
    *_ai_*|*_mastered.wav|*_original.wav|*_test_*.wav)
      return 1
      ;;
  esac
  return 0
}

load_source_wavs() {
  local input="$1"
  wavs=()

  if [ -f "$input" ]; then
    if is_source_wav "$input"; then
      wavs+=("$input")
    fi
    return
  fi

  while IFS= read -r -d '' path; do
    if is_source_wav "$path"; then
      wavs+=("$path")
    fi
  done < <(find "$input" -maxdepth 1 -type f \( -iname "*.wav" -o -iname "*.wave" \) -print0 | sort -z)
}

add_selection_index() {
  local index="$1"
  if [ "$index" -lt 1 ] || [ "$index" -gt "${#wavs[@]}" ]; then
    echo "  Skipping invalid number: $index"
    return
  fi
  selected_map["$((index - 1))"]=1
}

add_selection_token() {
  local token="$1"
  local start end i lower_token lower_name matches
  token="${token//[$'\t\r\n']/}"
  [ -z "$token" ] && return

  if [[ "${token,,}" == "all" ]]; then
    for i in "${!wavs[@]}"; do
      selected_map["$i"]=1
    done
    return
  fi

  if [[ "$token" =~ ^[0-9]+$ ]]; then
    add_selection_index "$token"
    return
  fi

  if [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    start="${BASH_REMATCH[1]}"
    end="${BASH_REMATCH[2]}"
    if [ "$start" -gt "$end" ]; then
      local tmp="$start"
      start="$end"
      end="$tmp"
    fi
    for ((i = start; i <= end; i++)); do
      add_selection_index "$i"
    done
    return
  fi

  lower_token="${token,,}"
  matches=0
  for i in "${!wavs[@]}"; do
    lower_name="$(basename "${wavs[$i]}")"
    lower_name="${lower_name,,}"
    if [[ "$lower_name" == *"$lower_token"* ]]; then
      selected_map["$i"]=1
      matches=$((matches + 1))
    fi
  done
  if [ "$matches" -eq 0 ]; then
    echo "  No filename matched: $token"
  fi
}

prompt_for_files() {
  local answer token i
  while true; do
    declare -gA selected_map=()
    read -r -p "Select file number(s), ranges, filename text, or all [all]: " answer
    answer="${answer:-all}"
    answer="${answer//,/ }"
    for token in $answer; do
      add_selection_token "$token"
    done

    selected_wavs=()
    for i in "${!wavs[@]}"; do
      if [ "${selected_map[$i]:-0}" = "1" ]; then
        selected_wavs+=("${wavs[$i]}")
      fi
    done
    if [ "${#selected_wavs[@]}" -gt 0 ]; then
      return
    fi
    echo "No files selected. Try examples: 1, 1-2, all, abe001"
  done
}

prompt_for_targets() {
  local answer token
  while true; do
    targets=()
    read -r -p "Target LUFS value(s) [-14]: " answer
    answer="${answer:-${MASTERING_PRIMARY_LUFS:--14}}"
    answer="${answer//,/ }"
    for token in $answer; do
      if [[ "$token" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
        targets+=("$token")
      else
        echo "  Invalid LUFS value: $token"
      fi
    done
    if [ "${#targets[@]}" -gt 0 ]; then
      return
    fi
  done
}

prompt_for_mode() {
  local answer
  while true; do
    read -r -p "Render length: full, loudest test, or first test [full]: " answer
    answer="${answer:-full}"
    case "${answer,,}" in
      full|f)
        render_mode="full"
        return
        ;;
      loudest|loudest-test|test|t)
        render_mode="loudest"
        return
        ;;
      first|first-test)
        render_mode="first"
        return
        ;;
      *)
        echo "Use full, loudest, or first."
        ;;
    esac
  done
}

prompt_for_local_models() {
  local answer
  read -r -p "Use CLAP/MERT local model scoring? [Y/n]: " answer
  case "${answer,,}" in
    n|no)
      use_local_models=0
      ;;
    *)
      use_local_models=1
      ;;
  esac
}

target_tag() {
  local value="$1"
  value="${value//-/m}"
  value="${value//./p}"
  printf "%slufs" "$value"
}

run_one_master() {
  local input_wav="$1"
  local target="$2"
  local input_dir stem stamp tag out_dir basename
  input_dir="$(dirname "$input_wav")"
  stem="$(basename "${input_wav%.*}")"
  stamp="$(date +%Y%m%d-%H%M%S)"
  tag="$(target_tag "$target")"

  if [ "${#targets[@]}" -gt 1 ]; then
    basename="${stem}_${tag}"
    out_dir="$input_dir/masters/${basename}_${stamp}"
  else
    basename="$stem"
    out_dir="$input_dir/masters/${stem}_${stamp}"
  fi

  cmd=("$MASTERING_ROOT/master.sh" "--target" "$target" "--jobs" "${MASTERING_JOBS:-2}")
  if [ "$use_local_models" = "0" ]; then
    cmd+=("--fast")
  else
    export MASTERING_LOCAL_MODELS=1
  fi
  if [ "$render_mode" != "full" ]; then
    cmd+=("--test" "$render_mode")
  fi
  cmd+=("$input_wav" "$out_dir" "$basename")

  echo
  echo "[Master] Rendering: $(basename "$input_wav") -> $target LUFS"
  echo "[Master] Output: $out_dir"
  if [ "${MASTERING_QUICKSTART_DRY_RUN:-0}" = "1" ]; then
    printf '[Master] Dry run:'
    printf ' %q' "${cmd[@]}"
    printf '\n'
  else
    "${cmd[@]}"
  fi
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

input="${1:-${ABE_PENDING_DIR:-/mnt/c/Production/music/Submission}}"
input="$(normalize_path_arg "$input")"

if [ ! -e "$input" ]; then
  echo "[Master] Input not found: $input" >&2
  exit 1
fi

if [ -d "$input" ]; then
  folder="$input"
else
  folder="$(dirname "$input")"
fi

echo "Abe Mastering"
echo "============="
echo "Folder: $folder"
echo

declare -a wavs=()
declare -a selected_wavs=()
declare -a targets=()
declare -a cmd=()
render_mode="full"
use_local_models=1

load_source_wavs "$input"

if [ "${#wavs[@]}" -eq 0 ]; then
  echo "[Master] No source WAV files found in: $folder" >&2
  exit 1
fi

for i in "${!wavs[@]}"; do
  printf "  [%d] %s\n" "$((i + 1))" "$(basename "${wavs[$i]}")"
done
echo

prompt_for_files
prompt_for_targets
prompt_for_mode
prompt_for_local_models

export MASTERING_QUICKSTART_STYLE="${MASTERING_QUICKSTART_STYLE:-$DEFAULT_STYLE}"

echo
echo "[Master] Selected ${#selected_wavs[@]} file(s), ${#targets[@]} target(s)."
for wav in "${selected_wavs[@]}"; do
  for target in "${targets[@]}"; do
    run_one_master "$wav" "$target"
  done
done

echo
echo "[Master] Done."
