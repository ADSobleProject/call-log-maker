@echo off
REM ---------------------------------------------------------------
REM  Keep this window open: new files in the input folder are converted
REM  automatically (checks every 1.5 seconds). Press Ctrl+C to stop.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

if not exist ".venv\Scripts\python.exe" goto :setup
if not exist ".venv\.deps_ok" goto :setup
goto :run

:setup
call "%~dp0_setup.bat"
if errorlevel 1 goto :end

:run
echo.
".venv\Scripts\python.exe" -m calllog watch
echo.
pause
exit /b 0

:end
echo.
echo Setup did not finish. Read the messages above.
pause
exit /b 1
