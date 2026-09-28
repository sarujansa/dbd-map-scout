@echo off
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.venv"
if exist "%VENV%\installed.ok" goto update

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

:update
rem Neuen Stand von GitHub holen (dbdmapscout\update.py: nur auf main, nur ohne eigene Aenderungen,
rem nur Nachziehen). Exit-Code 3 = aktualisiert. Weil cmd diese Datei waehrend der Ausfuehrung
rem weiterliest, das Update sie aber geaendert haben kann, startet sie sich IN DERSELBEN ZEILE neu.
if not defined DBDMS_UPDATED ("%VENV%\Scripts\python.exe" "%~dp0dbdmapscout\update.py" & if errorlevel 3 (set "DBDMS_UPDATED=1" & cmd /c ""%~f0" %*" & exit /b))

rem Pakete nachinstallieren, wenn sich requirements.txt / requirements-extra.txt geaendert haben
rem (Zusatzpaket ohne Abhaengigkeiten, siehe requirements-extra.txt). Fehlschlag: Start trotzdem.
"%VENV%\Scripts\python.exe" "%~dp0dbdmapscout\update.py" --deps

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
