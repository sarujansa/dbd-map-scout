@echo off
rem Einrichtung (einmalig): Programmsymbol, Aufgabe "DbD Map Scout" in der Windows-Aufgabenplanung
rem (startet als Administrator OHNE Nachfrage) und Desktop-Verknuepfung, die diese Aufgabe startet.
rem Das Anlegen der Aufgabe braucht selbst Administratorrechte - Windows fragt dafuer einmal.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst einmal start.bat ausfuehren - die Ersteinrichtung legt .venv an.
  pause
  exit /b 1
)
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)
".venv\Scripts\python.exe" -m dbdmapscout.autostart install
if errorlevel 1 (
  echo.
  echo Einrichtung fehlgeschlagen - Meldung oben.
  pause
  exit /b 1
)
echo.
echo Fertig. Die Verknuepfung "DbD Map Scout" auf dem Desktop startet ohne Windows-Abfrage.
echo Mit Windows starten: im Programm unter Einstellungen einschalten.
pause
