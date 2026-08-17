@echo off
setlocal

set "ROOT=%~dp0"
set "SCRIPT=%ROOT%start-qa-review.ps1"

if not exist "%SCRIPT%" (
  echo Missing launcher: %SCRIPT%
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"

if errorlevel 1 (
  echo.
  echo Launch failed. Check the message above or send a screenshot.
  pause
  exit /b 1
)

echo.
echo Launch commands sent. Keep the backend and frontend windows open.
echo Open this URL if the browser did not open automatically:
echo http://127.0.0.1:4183/
echo.
pause
