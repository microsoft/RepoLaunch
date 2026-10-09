#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 CASE_JSON REPOSITORY_CHECKOUT [OUTPUT_ROOT]" >&2
  exit 64
fi

case_json=$1
repository_checkout=$2
output_root=${3:-.change2task}

change2task validate-case "$case_json"
change2task build-case "$case_json" \
  --repository-cache "$repository_checkout" \
  --run-root "$output_root" \
  --output "$output_root/outcome.json"
