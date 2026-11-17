@echo off
REM ---------------------------------------------------------------
REM  Drag recording / text files onto this file to convert them.
REM ---------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

if "%~1"=="" (
  echo.
  echo Drag audio files ^(.m4a .mp3 .wav .ogg .flac^) or text files ^(.txt^)
  echo onto this file to convert them into call-log documents.
  echo.
  pause
  exit /b 1
)

call "%~dp0_setup.bat"
if errorlevel 1 goto :end

echo.
".venv\Scripts\python.exe" -m calllog files %*
set "RC=%ERRORLEVEL%"

if exist "output" start "" "%~dp0output"
echo.
pause
exit /b %RC%

:end
echo.
pause
exit /b 1
