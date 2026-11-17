@echo off
REM ---------------------------------------------------------------
REM  call-log-maker - one-time environment setup (ASCII only)
REM  Creates .venv and installs required packages on first run.
REM ---------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYEXE="
py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  python --version >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
  echo.
  echo [ERROR] Python 3 was not found.
  echo         Install Python 3.9 or newer from https://www.python.org/downloads/windows/
  echo         During installation, tick "Add python.exe to PATH".
  echo.
  exit /b 1
)

%PYEXE% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
  echo.
  echo [ERROR] Python 3.9 or newer is required.
  echo.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating the Python environment in .venv ...
  %PYEXE% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create .venv
    exit /b 1
  )
)

set "VPY=.venv\Scripts\python.exe"

if not exist ".venv\.deps_ok" (
  echo [2/3] Installing required packages. This can take a few minutes on the first run...
  "%VPY%" -m pip install --upgrade pip
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed. Check your internet connection and try again.
    echo         Manual: .venv\Scripts\pip install faster-whisper python-docx
    echo.
    exit /b 1
  )
  echo ok> ".venv\.deps_ok"
) else (
  echo [2/3] Packages already installed.
)

echo [3/3] Ready.
exit /b 0
