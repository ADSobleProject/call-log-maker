@echo off
REM ---------------------------------------------------------------
REM  call-log-maker - environment setup (ASCII only)
REM  Finds a Python here, then hands the real work to setup_env.py:
REM    - creates (or repairs) .venv
REM    - installs required packages (python-docx) first
REM    - tries the optional audio packages (faster-whisper) separately
REM  Options are passed through: _setup.bat --repair / --core-only / --check
REM ---------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "BOOT="
py -3 --version >nul 2>nul && set "BOOT=py -3"
if not defined BOOT (
  python -c "import sys" >nul 2>nul && set "BOOT=python"
)
if not defined BOOT (
  python3 -c "import sys" >nul 2>nul && set "BOOT=python3"
)
if not defined BOOT (
  echo.
  echo [ERROR] Python was not found on this PC.
  echo         Install 64-bit Python 3.12, then run this file again:
  echo             winget install -e --id Python.Python.3.12
  echo         Or get "Windows installer (64-bit)" 3.12 from
  echo             https://www.python.org/downloads/windows/
  echo         Tick "Add python.exe to PATH" during installation.
  echo.
  exit /b 1
)

%BOOT% "%~dp0setup_env.py" %*
exit /b %ERRORLEVEL%
