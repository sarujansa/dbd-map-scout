@echo off
rem Screenshots (PNG/JPG) auf diese Datei ziehen: zeigt, was die Erkennung darin liest.
cd /d "%~dp0"
if not exist ".venv\installed.ok" (
  echo Bitte zuerst start.bat einmal ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m dbdmapscout --test %*
pause
