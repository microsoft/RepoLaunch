#!/usr/bin/env bash
set -euo pipefail

destination="${CHANGE2TASK_SKILL_DIR:-$HOME/.cursor/skills/change2task}"
source_dir=""
raw_base="${CHANGE2TASK_RAW_BASE:-https://raw.githubusercontent.com/microsoft/RepoLaunch/change2task/.cursor/skills/change2task}"

usage() {
  cat <<'EOF'
Usage: install_skill.sh [--destination DIR] [--source DIR]

Installs the Change2Task agent skill. Without --source, files are downloaded
from the public change2task branch.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --destination)
      destination=$2
      shift 2
      ;;
    --source)
      source_dir=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT

if [[ -n "$source_dir" ]]; then
  test -f "$source_dir/SKILL.md"
  test -f "$source_dir/reference.md"
  cp "$source_dir/SKILL.md" "$temporary/SKILL.md"
  cp "$source_dir/reference.md" "$temporary/reference.md"
else
  command -v curl >/dev/null
  curl -fsSL "$raw_base/SKILL.md" -o "$temporary/SKILL.md"
  curl -fsSL "$raw_base/reference.md" -o "$temporary/reference.md"
fi

grep -q '^name: change2task$' "$temporary/SKILL.md"
grep -q '^description: ' "$temporary/SKILL.md"

mkdir -p "$destination"
install -m 0644 "$temporary/SKILL.md" "$destination/SKILL.md"
install -m 0644 "$temporary/reference.md" "$destination/reference.md"

printf 'Installed Change2Task skill at %s\n' "$destination"
