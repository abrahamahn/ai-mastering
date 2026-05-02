#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

plugins=("$@")
if [ "${#plugins[@]}" -eq 0 ]; then
  plugins=(soothe2 multipass alpha_master tape ozone9)
fi

for plugin in "${plugins[@]}"; do
  echo
  echo "===== $plugin ====="
  run_master discover "$plugin"
done
