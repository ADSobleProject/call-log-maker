@echo off
REM ---------------------------------------------------------------
REM  Keep this window open: new files in the input folder are converted
REM  automatically (checks every 3 seconds). Press Ctrl+C to stop.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

call "%~dp0_setup.bat"
if errorlevel 1 goto :end

echo.
".venv\Scripts\python.exe" -m calllog watch
echo.
pause
exit /b 0

:end
echo.
pause
exit /b 1
