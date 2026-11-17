#!/usr/bin/env bash
# macOS / Linux: watch input/ and convert new files automatically
set -euo pipefail
export PYTHONUNBUFFERED=1
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -x ".venv/bin/python" ]; then
  "$PY" -m venv .venv
  ".venv/bin/python" -m pip install -r requirements.txt
  touch .venv/.deps_ok
fi

exec ".venv/bin/python" -m calllog watch
