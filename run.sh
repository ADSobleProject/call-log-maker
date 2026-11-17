#!/usr/bin/env bash
# macOS / Linux: convert every file in input/ (one run)
set -euo pipefail
export PYTHONUNBUFFERED=1
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.9+ 가 필요합니다. https://www.python.org/downloads/ 에서 설치해 주세요." >&2
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/3] 가상환경을 만듭니다 (.venv) ..."
  "$PY" -m venv .venv
fi
VPY=".venv/bin/python"

if [ ! -f ".venv/.deps_ok" ]; then
  echo "[2/3] 필요한 패키지를 설치합니다 (첫 실행만, 몇 분 걸릴 수 있습니다) ..."
  "$VPY" -m pip install --upgrade pip
  "$VPY" -m pip install -r requirements.txt
  touch .venv/.deps_ok
else
  echo "[2/3] 패키지 설치 확인 완료"
fi
echo "[3/3] 준비 완료"

"$VPY" -m calllog batch
RC=$?

if [ -d output ]; then
  if command -v open >/dev/null 2>&1; then open output || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open output || true
  fi
fi
exit $RC
