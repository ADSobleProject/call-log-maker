#!/usr/bin/env bash
# macOS / Linux: convert every file in input/ (one run)
set -uo pipefail
export PYTHONUNBUFFERED=1
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.9+ 가 필요합니다. https://www.python.org/downloads/ 에서 설치해 주세요." >&2
  exit 1
fi

# .venv 준비(필수 패키지 중심). 음성 패키지는 setup_env.py 가 따로 시도한다.
if [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/.deps_ok" ]; then
  "$PY" setup_env.py || exit 1
fi

".venv/bin/python" -m calllog batch
RC=$?

if [ -d output ]; then
  if command -v open >/dev/null 2>&1; then open output || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open output || true
  fi
fi
exit $RC
