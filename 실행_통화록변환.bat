@echo off
REM ---------------------------------------------------------------
REM  Double-click this file to convert every file in the input folder.
REM  First run: prepares .venv (see _setup.bat).
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
".venv\Scripts\python.exe" -m calllog batch
set "RC=%ERRORLEVEL%"

if exist "output" start "" "%~dp0output"
echo.
pause
exit /b %RC%

:end
echo.
echo Setup did not finish. Read the messages above.
pause
exit /b 1
