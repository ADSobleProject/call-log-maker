#!/usr/bin/env bash
# macOS / Linux: convert only the files passed as arguments
set -uo pipefail
export PYTHONUNBUFFERED=1
cd "$(dirname "$0")"

if [ "$#" -eq 0 ]; then
  echo "사용법: ./drag_and_drop.sh <녹음파일 또는 txt> [더 많은 파일...]"
  exit 1
fi

PY="${PYTHON:-python3}"
if [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/.deps_ok" ]; then
  "$PY" setup_env.py || exit 1
fi

".venv/bin/python" -m calllog files "$@"
RC=$?
if [ -d output ]; then
  if command -v open >/dev/null 2>&1; then open output || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open output || true
  fi
fi
exit $RC
