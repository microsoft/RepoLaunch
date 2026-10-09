#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
change2task case-schema --output "$project_root/schemas/task-case.schema.json"
