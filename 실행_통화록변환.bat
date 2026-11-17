@echo off
REM ---------------------------------------------------------------
REM  Double-click this file to convert every file in the input folder.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

call "%~dp0_setup.bat"
if errorlevel 1 goto :end

echo.
".venv\Scripts\python.exe" -m calllog batch
set "RC=%ERRORLEVEL%"

if exist "output" start "" "%~dp0output"
echo.
pause
exit /b %RC%

:end
echo.
pause
exit /b 1
