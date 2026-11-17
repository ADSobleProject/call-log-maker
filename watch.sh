#!/usr/bin/env bash
# macOS / Linux: watch input/ and convert new files automatically
set -euo pipefail
export PYTHONUNBUFFERED=1
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/.deps_ok" ]; then
  "$PY" setup_env.py
fi

exec ".venv/bin/python" -m calllog watch
