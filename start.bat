@echo off
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.venv"
if exist "%VENV%\installed.ok" goto run

echo === DbD Map Scout: Ersteinrichtung (einmalig, ca. 1-2 Minuten) ===
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython

%PY% -m venv "%VENV%"
if errorlevel 1 goto nopython
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto piperror
echo ok> "%VENV%\installed.ok"

:run
if /i "%~1"=="debug" (
  "%VENV%\Scripts\python.exe" -m dbdmapscout
  pause
  exit /b 0
)
start "" "%VENV%\Scripts\pythonw.exe" -m dbdmapscout
exit /b 0

:nopython
echo.
echo Python wurde nicht gefunden.
echo Bitte Python 3.12 oder neuer von https://www.python.org/downloads/ installieren
echo und im Installer "Add python.exe to PATH" anhaken. Danach start.bat erneut starten.
pause
exit /b 1

:piperror
echo.
echo Die Installation der Pakete ist fehlgeschlagen (Internetverbindung?).
echo Ordner .venv loeschen und start.bat erneut starten.
pause
exit /b 1
