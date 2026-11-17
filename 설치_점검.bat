@echo off
REM ---------------------------------------------------------------
REM  Run this when something is wrong with the installation.
REM  It checks the Python environment, repairs .venv if needed and
REM  retries the optional audio packages, then prints a doctor report.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

call "%~dp0_setup.bat" --repair
set "RC=%ERRORLEVEL%"

echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m calllog doctor
)

echo.
pause
exit /b %RC%
