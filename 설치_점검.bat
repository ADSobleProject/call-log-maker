@echo off
REM ---------------------------------------------------------------
REM  Run this when something is wrong with the installation.
REM  It checks the Python environment, repairs .venv if needed and
REM  retries the optional audio packages, then prints a doctor report.
REM  If the audio packages cannot work on this PC's Python, it offers
REM  to install 64-bit Python 3.12 with winget (you can say no).
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

call "%~dp0_setup.bat" --repair --ask-install
set "RC=%ERRORLEVEL%"

echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m calllog doctor
)

echo.
pause
exit /b %RC%
