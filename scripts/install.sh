#!/usr/bin/env bash
set -euo pipefail

prefix="${CHANGE2TASK_INSTALL_ROOT:-$HOME/.local/share/change2task}"
bin_dir="${CHANGE2TASK_BIN_DIR:-$HOME/.local/bin}"
skill_dir="${CHANGE2TASK_SKILL_DIR:-$HOME/.cursor/skills/change2task}"
source_root=""
repository="${CHANGE2TASK_REPOSITORY:-git+https://github.com/microsoft/RepoLaunch.git@change2task}"
python_bin="${PYTHON:-python3}"

usage() {
  cat <<'EOF'
Usage: install.sh [--prefix DIR] [--bin-dir DIR] [--skill-dir DIR]
                  [--source-root DIR]

Installs the Change2Task CLI in an isolated virtual environment and installs
the Change2Task Agent Skill. No administrator privileges are required.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      prefix=$2
      shift 2
      ;;
    --bin-dir)
      bin_dir=$2
      shift 2
      ;;
    --skill-dir)
      skill_dir=$2
      shift 2
      ;;
    --source-root)
      source_root=$2
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

command -v "$python_bin" >/dev/null
"$python_bin" -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --upgrade pip

if [[ -n "$source_root" ]]; then
  source_root=$(cd "$source_root" && pwd)
  "$prefix/venv/bin/python" -m pip install "$source_root"
  bash "$source_root/scripts/install_skill.sh" \
    --source "$source_root/.cursor/skills/change2task" \
    --destination "$skill_dir"
else
  command -v curl >/dev/null
  "$prefix/venv/bin/python" -m pip install "$repository"
  temporary=$(mktemp)
  trap 'rm -f "$temporary"' EXIT
  curl -fsSL \
    "https://raw.githubusercontent.com/microsoft/RepoLaunch/change2task/scripts/install_skill.sh" \
    -o "$temporary"
  bash "$temporary" --destination "$skill_dir"
fi

mkdir -p "$bin_dir"
ln -sfn "$prefix/venv/bin/change2task" "$bin_dir/change2task"

"$bin_dir/change2task" --help >/dev/null

printf 'Installed Change2Task CLI: %s/change2task\n' "$bin_dir"
printf 'Installed Change2Task Skill: %s\n' "$skill_dir"
case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) printf 'Add %s to PATH to invoke change2task directly.\n' "$bin_dir" ;;
esac
