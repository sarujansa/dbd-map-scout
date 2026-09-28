@echo off
rem Legt "DbD Map Scout" mit Symbol auf den Desktop (startet als Administrator).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst einmal start.bat ausfuehren - die Ersteinrichtung legt .venv an.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m dbdmapscout.icon "%~dp0dbdmapscout.ico"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verknuepfung_erstellen.ps1" -Root "%~dp0."
if errorlevel 1 (
  echo Die Verknuepfung konnte nicht erstellt werden.
  pause
  exit /b 1
)
echo.
echo Fertig. Tipp: Rechtsklick auf die Verknuepfung - "An Taskleiste anheften".
pause
