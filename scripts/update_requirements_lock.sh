#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

uv pip compile src/main/requirements.in \
  -o src/main/requirements.txt \
  --universal \
  --custom-compile-command "uv pip compile src/main/requirements.in -o src/main/requirements.txt --universal" \
  "$@"
