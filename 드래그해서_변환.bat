@echo off
REM ---------------------------------------------------------------
REM  Drag recording / text files onto this file to convert them.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
REM Hide the noisy huggingface_hub symlink warning on Windows.
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

if "%~1"=="" (
  echo.
  echo Drag audio files ^(.m4a .mp3 .wav .ogg .flac^) or text files ^(.txt^)
  echo onto this file to convert them into call-log documents.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" goto :setup
if not exist ".venv\.deps_ok" goto :setup
REM Audio packages installed by an older version: verify once (fixes a
REM mismatched audio library such as av 19) and then stay fast.
if not exist ".venv\.audio_ok" goto :run
findstr /C:"probe" ".venv\.audio_ok" >nul 2>nul
if errorlevel 1 goto :setup
goto :run

:setup
call "%~dp0_setup.bat"
if errorlevel 1 goto :end

:run
echo.
".venv\Scripts\python.exe" -m calllog files %*
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
