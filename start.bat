@echo off
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.venv"
if exist "%VENV%\installed.ok" goto update

echo === DbD Map Scout: Ersteinrichtung (einmalig, ca. 2-4 Minuten) ===
rem Python 3.12 bis 3.14: fuer neuere gibt es noch nicht alle Pakete (onnxruntime, pywinrt). Der Launcher
rem "py" nimmt gezielt eine passende Version, auch wenn daneben eine neuere installiert ist (Eingabe aus
rem nul: nie auf eine Rueckfrage des Python-Installationsmanagers warten).
set "PY="
for %%V in (3.14 3.13 3.12) do if not defined PY (py -%%V -c "pass" <nul >nul 2>nul && set "PY=py -%%V")
if not defined PY (python -c "import sys; sys.exit(not (3, 12) <= sys.version_info[:2] <= (3, 14))" <nul >nul 2>nul && set "PY=python")
if not defined PY goto nopython

rem Eine abgebrochene Ersteinrichtung (kein installed.ok) neu beginnen, z. B. mit einer anderen Python-Version
if exist "%VENV%" rd /s /q "%VENV%"
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
if not defined DBDMS_UPDATED ("%VENV%\Scripts\python.exe" "%~dp0dbdmapscout\update.py" & if errorlevel 3 (set "DBDMS_UPDATED=1" & cmd /c "".\%~nx0" %*" & exit /b))

rem Pakete nachinstallieren, wenn sich requirements.txt / requirements-extra.txt geaendert haben
rem (Zusatzpaket ohne Abhaengigkeiten, siehe requirements-extra.txt). Fehlschlag: Start trotzdem.
"%VENV%\Scripts\python.exe" "%~dp0dbdmapscout\update.py" --deps

:run
if /i "%~1"=="debug" (
  "%VENV%\Scripts\python.exe" -m dbdmapscout
  pause
  exit /b 0
)
rem "tray": Autostart mit Windows (Aufgabe "DbD Map Scout (Autostart)") - im Infobereich starten
set "ARGS="
if /i "%~1"=="tray" set "ARGS=--tray"
start "" "%VENV%\Scripts\pythonw.exe" -m dbdmapscout %ARGS%
exit /b 0

:nopython
echo.
echo Kein passendes Python gefunden: DbD Map Scout braucht Python 3.12, 3.13 oder 3.14.
echo Fuer Python 3.15 und neuer gibt es noch nicht alle Pakete (z. B. onnxruntime fuer die Texterkennung).
where py >nul 2>nul && (echo Installiert: & py --list <nul)
echo.
echo Python 3.14 zusaetzlich installieren - eine neuere Version darf daneben bleiben:
echo   im Terminal "py install 3.14" (Python-Installationsmanager) oder
echo   https://www.python.org/downloads/ und im Installer "Add python.exe to PATH" anhaken.
echo Danach start.bat erneut starten.
pause
exit /b 1

:piperror
echo.
echo Die Installation der Pakete ist fehlgeschlagen (Internetverbindung?).
echo Ordner .venv loeschen und start.bat erneut starten.
pause
exit /b 1
