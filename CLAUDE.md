# DbD Map Scout – Projektkontext für Claude Code

Map-Overlay für Dead by Daylight (Windows). Erkennt beim Match-Start den Map-Namen per OCR und blendet die passende Callout-Karte aus `maps/` als klickdurchlässiges Overlay ein. Außerdem: Ausblenden nach der Runde bzw. Pause in Menüs, und ein Tab „Server“ zur Regionswahl über die hosts-Datei und Anzeige des verbundenen Spielservers (Ideen von „Make Your Choice“). Oberfläche und Log: **Deutsch und Englisch** (`i18n.py`, Einstellung `ui_language`, „auto“ = Windows-Sprache). Doku: Deutsch (`README.md`) + Englisch (`README.en.md`). Code und Kommentare: Englisch.

## Harte Regeln (nicht verhandelbar)

Das Programm muss „regelkonform“ zu Dead by Daylight bleiben. Konkret:

- **Keine Eingaben ans Spiel** (kein SendInput, keine Tastatur-/Maus-Simulation, keine Automatisierung).
- **Kein Zugriff auf den Spielprozess** – nicht einmal `OpenProcess`, kein Speicherlesen, keine Injection, keine Modul-/Handle-Abfragen mit PID.
- **Keine Spieldateien** lesen oder schreiben (auch nicht `GameUserSettings.ini`, Splash-Screen, Movies).
- Erlaubt sind nur: **Bildschirmpixel** (mss/BitBlt) und – nur solange DBD im Hintergrund ist – die **Fensteraufnahme per Windows Graphics Capture** (wie OBS „Fensteraufnahme“, Bild kommt vom Windows-Compositor; `wincapture.py`, Bibliothek windows-capture **2.0.1 fest**, geprüft: importiert kein OpenProcess/GetWindowThreadProcessId/Hooks/Eingaben – bei Versionswechsel erneut prüfen; nie `PrintWindow`, das schickt Nachrichten ans Spiel), Fensterinfos (Titel, Klasse `UnrealWindow`, Position über EnumWindows), **Mauszeiger-Status** (`GetCursorInfo`, wie OBS), die **Windows-hosts-Datei** (nur Tab „Server“, nur GameLift-Namen) und **Paketköpfe des Netzwerkverkehrs** (nur Tab „Server“, Anzeige „Verbunden mit“; vom Nutzer ausdrücklich gewünscht, wie in Make Your Choice). Beim Mitschnitt: nur IPv4/UDP-Kopffelder (Adressen, Ports) lesen, **nie Paketinhalte**, nichts senden, nichts speichern außer der temporären Ergebnisdatei (Server-IP **nicht** ins Logfile, nur die Region), kein Treiber (Raw-Socket `SIO_RCVALL`), **nur Modus `RCVALL_IPLEVEL`** (eigener Verkehr; nie `RCVALL_ON`/Promiscuous, auch nicht als Rückfall), keine Zuordnung über die PID des Spiels.
- Map-Erkennung und Overlay bauen **keine Internetverbindung** auf (Ausnahme nur für Updates, auf Wunsch des Nutzers: im Starter `start.bat` → `update.py` per `git fetch` von GitHub, abschaltbar; im Programm **nur auf Klick** „Jetzt nach Updates suchen“ – `update.check()`, nur `git fetch` von GitHub, installiert nichts; installiert wird immer im Starter nach Neustart); nur der Server-Tab pingt AWS-GameLift (UDP 7770 / ICMP) und löst DNS auf (auch Reverse-DNS der Spielserver-Adresse). Während „Verbunden mit“ läuft, alle 5 s ein Ping an den Beacon der verbundenen Region (`gamelift-ping.<region>.api.aws`) – **nie Pakete an den Spielserver selbst**.
- Neue Features, die gegen diese Regeln verstoßen würden: nicht umsetzen, sondern nachfragen.

## Setup des Nutzers (wichtig für Tests und Schwellenwerte)

- Monitor Samsung G5, **3440×1440**; DBD (Epic Games Store) im Modus **Fenster-Vollbild**.
- DBD rendert **16:9 = 2560×1440 zentriert**, schwarze Balken links/rechts je 440 px. Alle UI-Positionen daher relativ zum 16:9-Viewport rechnen (`detector.viewport()`), nie relativ zur vollen Fensterbreite.
- Spielsprache Englisch (EN/DE sind standardmäßig aktiv). Spielt oft Killer, auch Custom Games mit Bots.
- Overlay-Standardposition „automatisch“ = im linken schwarzen Balken.

## Starten, Testen

```bat
start.bat                 :: legt beim 1. Mal .venv an und installiert requirements.txt
start_debug.bat           :: mit Konsole
.venv\Scripts\python -m dbdmapscout                         :: normal
.venv\Scripts\python -m dbdmapscout --simulate ORDNER       :: spielt Screenshots statt Bildschirm ab (0,8 s/Bild)
.venv\Scripts\python -m dbdmapscout --test BILD.png ...     :: Banner-Erkennung auf Screenshots
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest -q tests
```

- Tests immer laufen lassen nach Änderungen an `detector.py`, `matchend.py`, `hostsedit.py`, `regions.py`, `netwatch.py`, `connwatch.py`, `roundtimer.py`, `wincapture.py`.
- Pakete: `update.py --deps` (von `start.bat` bei jedem Start) installiert `requirements.txt` bzw. `requirements-extra.txt` neu, sobald sich die Datei geändert hat (SHA-256 in `.venv\*.sha256`). `requirements-extra.txt` (windows-capture) immer mit `--no-deps`: das Paket verlangt `opencv-python`, das Projekt nutzt `opencv-python-headless` – beide zusammen zerstören `cv2`.
- Update beim Start: `update.py` (nur Standardbibliothek, als Skript aufgerufen) zieht auf `main` per Fast-Forward nach – nie bei eigenen Änderungen, anderem Zweig, eigenen Commits, offline. Exit-Code 3 = aktualisiert → `start.bat` startet sich **in derselben Zeile** neu (cmd liest .bat-Dateien während der Ausführung weiter; eine geänderte `start.bat` darf nicht an alter Byte-Position weitergelesen werden). Diese Zeile nicht aufteilen. Ergebnis in `.venv\update_status.txt`, die App zeigt es im Log.
- GitHub Actions (`.github/workflows/tests.yml`) führt pyflakes + pytest bei jedem PR unter Linux aus – PRs erst mergen, wenn der Haken grün ist.
- Tests dürfen **niemals die echte hosts-Datei** anfassen. `hostsedit.hosts_path()` ignoriert die Test-Variable `DBDMS_HOSTS_FILE` unter Windows absichtlich (Sicherheit des Admin-Helfers) – Schreibtests laufen daher nur über `hostsedit.build()` / `apply_job` mit reinen Text-/Temp-Dateien bzw. unter Linux/CI. Nicht „reparieren“.
- `settings.json`, `dbdmapscout.log`, `diagnose.txt`, `debug/` sind Laufzeitdateien, nicht committen.

## Architektur (dbdmapscout/)

| Datei | Aufgabe |
|---|---|
| `__main__.py` | Start, Single-Instance-Mutex, Logging, `--simulate`/`--test` |
| `app.py` | Tk-Steuerfenster (Tabs Maps/Overlay/Erkennung/Server/Log/Einstellungen), verbindet alles; Events kommen über `self.events` (Queue) im `_poll` an. Jeder Tab steckt in `_scroll_tab()` (Canvas + Scrollbar, nur vertikal; innen mindestens Fensterhöhe, damit Listen/Log mitwachsen; Mausrad scrollt den Tab, außer über Treeview/Text/Combobox). Mindestbreite = breitester Tab-Inhalt – lange Texte daher immer mit `wraplength` |
| `worker.py` | Hintergrund-Thread: Aufnahme → Banner-Erkennung → Rundenende; postet Events (`detected`, `unknown`, `menu`, `match_end`, `watch_info`, `warn`, …). Im Match (`tracker.in_trial`, kein Banner) gedrosselt auf `IN_MATCH_RATE` = 1 Scan/s |
| `detector.py` | Banner: Trennlinie finden → Text ausschneiden → OCR-Scoring gegen Katalog → `Accumulator`. Rundenende: `OutOfMatchWatcher.observe()` (CONTINUE, Währung, Ladebalken) |
| `matchend.py` | `MatchEndTracker` – reine Logik (testbar): Menü-Pause per Mauszeiger, Rundenende-Latch, Scharfschalten bei manueller Map |
| `status.py` | `user_state()` – reine Logik: Statuszeile oben für Spieler (Wartet auf DBD / nächstes Match / Im Match / Menü / Runde vorbei; Worker-Probleme wie „schwarz“ gewinnen immer). Technische Worker-Texte nur noch ins Log |
| `roundtimer.py` | `RoundTimer` – reine Logik: läuft, solange eine Karte eingeblendet ist; neue Map-Erkennung startet neu (außer dasselbe Banner < 90 s) |
| `ocr.py` | PP-OCRv4-Erkennungsnetz (ONNX) + `LexiconScorer` (CTC-Forward über alle Kandidaten) |
| `catalog.py`, `maps.json`, `textnorm.py` | Map-/Realm-Namen (9 Sprachen), Varianten, Bildpfade. Aliasse aus `maps.json` plus eigene Zuordnungen des Nutzers (`settings.json` → `user_aliases`, Dialog „Zuordnen …“ nach einem `unknown`-Event; `alias_problem()` verhindert Konflikte, Realm-Prüfung bleibt) |
| `capture.py` | DBD-Fenster finden, mss-Aufnahme, `cursor_state()`; öffnet nie den Spielprozess |
| `wincapture.py` | Fensteraufnahme (WGC) für DBD im Hintergrund: `CapturePolicy` (reine Logik: an, sobald DBD nicht aktiv; aus nach 5 s aktiv), `WindowCapture` (kopiert nur die angefragte Region im Rückruf; falsche Bildgröße/keine Bilder → `None` → Worker nimmt mss). Bilder daraus enthalten das eigene Overlay nicht → kein Ausschwärzen |
| `layout.py` | reine Logik: Overlay im schwarzen Balken halten (`bar_side`, `clamp_x`); gilt für alle Positionen, solange `keep_in_bar` an ist; „automatisch“ immer. Mitten über dem Spiel platziert → keine Begrenzung |
| `mapimage.py` | reine Bildlogik für eigene Kartenbilder: Rand abschneiden, Hintergrundfarben `#282a42`/`#535781` (10 % euklidisch) transparent, 1280 px hoch, WebP; GIF unverändert. Ziel `user_maps/` (gitignored, sonst blockiert das Update) |
| `picturedlg.py` | Dialog „Kartenbild hinzufügen …“ (Tab Maps, Leiste „unbekannte Map“): vorhandene Map/Layout ersetzen oder neue Map (Name + Realm-Ordner), Vorschau, „Eigenes Bild löschen“. `catalog.py`: Bild in `user_maps/` mit gleichem relativem Pfad (beliebige Endung) ersetzt das mitgelieferte, sonst neue `custom:`-Map |
| `overlay_win32.py` / `overlay.py` | natives Layered-Window-Overlay (WS_EX_TRANSPARENT/NOACTIVATE) / Tk-Fallback |
| `regions.py` | Server-Tab: Regionstabelle (Namen), Ping (UDP-Beacon, DNS ohne hosts), `run_job()` startet Helfer per UAC |
| `hostsedit.py` | Admin-Helfer (UAC): schreibt nur den eigenen markierten Abschnitt der hosts-Datei. Nur Standardbibliothek, gestartet mit `pythonw -I -S`. Erlaubt nur Namen aus `MANAGED` (fest codiert) |
| `netwatch.py` | Admin-Teil „Verbunden mit“: Raw-Socket (`RCVALL_IPLEVEL`, kein Rückfall), zählt UDP-Pakete je öffentlicher Gegenstelle, schreibt jede Sekunde die aktivsten in eine Ergebnisdatei. Nur Standardbibliothek. Läuft als Thread, wenn das Programm schon Admin ist, sonst als Helfer per UAC (`pythonw -I -S`). Beendet sich, wenn die Steuerdatei fehlt, „stop“ sagt oder 20 s nicht aufgefrischt wurde |
| `connwatch.py` | startet `netwatch`, liest die Ergebnisdatei, wählt den Spielserver (≥ 10 Pakete/s, Reverse-DNS = AWS EC2), bestimmt die Region aus dem DNS-Namen und misst den Ping zum Beacon dieser Region (Median der letzten 3, alle 5 s). `IdlePause`: läuft DBD 30 s nicht, pausiert der Mitschnitt (nur als Admin, da Neustart dann ohne UAC) und startet mit DBD neu |
| `update.py` | Update beim Start + Paket-Abgleich (siehe „Starten, Testen“); Tests mit echten Git-Repos in `tests/test_update.py` |
| `restart.py` | „Aktualisieren und neu starten“: startet Helfer `python -m dbdmapscout --restart` und beendet das Programm; der Helfer wartet, bis der Single-Instance-Mutex weg ist (sonst sind Paketdateien für pip noch belegt; nach 30 s Abbruch statt zweiter Kopie), dann `start.bat` mit `DBDMS_FORCE_UPDATE=1` (installiert auch bei ausgeschaltetem Start-Update) |
| `icon.py` | Programmsymbol, gezeichnet (kein Binärfile im Repo): `python -m dbdmapscout.icon PFAD.ico` → `dbdmapscout.ico` (gitignored) |
| `autostart.py` | Aufgabenplanung statt UAC: Aufgabe „DbD Map Scout“ (auf Abruf, Desktop-Verknüpfung = `schtasks /run`) und „DbD Map Scout (Autostart)“ (bei Anmeldung, `start.bat tray` → `--tray`), beide `RunLevel Highest`, Aktion `cmd /c start "" /min start.bat` (Updates/Pakete laufen weiter). PowerShell per `-EncodedCommand`. Die App richtet Aufgabe, Symbol und Verknüpfung als Admin **selbst** ein (`autostart.ensure()` beim Start im Thread): beim ersten Mal, nach Ordnerwechsel, fehlender Aufgabe oder wenn `SETUP_VERSION` steigt (in `settings.json`: `setup_version`, `setup_root`) – **bei Änderungen an Aufgabe/Verknüpfung/Symbol `SETUP_VERSION` erhöhen**. Eine absichtlich gelöschte Verknüpfung wird nicht bei jedem Start neu angelegt. Notlösung von Hand: `verknuepfung_erstellen.bat` (holt sich Adminrechte) → `python -m dbdmapscout.autostart install`. Autostart-Schalter in den Einstellungen nur als Admin änderbar. Bewusster Kompromiss: Aufgabe umgeht UAC – was im Programmordner liegt, läuft als Admin |
| `tray.py` | Symbol im Infobereich (pystray 0.19.5, LGPL, eigener Thread); Menüaktionen nur als Event (`("tray", …)`) in die Queue, nie Tk aus dem Tray-Thread. Minimieren → `withdraw` (nur `<Unmap>` des Hauptfensters) |
| `hotkeys.py` | globale Hotkeys (RegisterHotKey) + `combo_from_keys()` für die Aufnahme per Tastendruck (Buchstaben/Ziffern nur mit Strg/Alt; Windows-keycode für Shift+Ziffer). Während der Aufnahme werden die globalen Hotkeys abgemeldet, sonst kommt die Kombination nie im Fenster an |
| `tooltip.py` | Hinweistexte beim Überfahren: Texte zentral in `TIPS` (nach Knopfbeschriftung), `attach_all()` nach dem Aufbau des Fensters bzw. jedes Dialogs; Knöpfe mit wechselnder Beschriftung über `App._tip_lookup`. **Neue Knöpfe/Häkchen brauchen einen Eintrag** (`tooltip.missing()` muss leer bleiben) |
| `i18n.py`, `i18n_en.py` | Übersetzung: deutscher Text im Code ist der Schlüssel, `_("… {name}", name=x)` (benannte Platzhalter, nie f-Strings in `_()`), `N_()` markiert Texte in Listen/Tabellen, die später mit `_()` angezeigt werden. Englisch in `i18n_en.EN`. **Jeder neue UI-/Log-Text braucht einen Eintrag** – `tests/test_i18n.py` prüft Vollständigkeit, Platzhalter, unübersetzte `text=`-Literale und dass `_` nie lokal überschrieben wird (`path, _ = …` ist verboten). Interne Schlüssel (Rundenende-Gründe, Regionsnamen, hosts-Zustände, Log-Kategorien) bleiben deutsch und werden erst bei der Anzeige übersetzt. `update.py` hat eine eigene kleine Tabelle (läuft vor dem Programm). Tests laufen mit `DBDMS_LANG=de` (`tests/conftest.py`). Nicht übersetzt: Diagnose-Text, Admin-Helfer (`hostsedit.py`, `netwatch.py`), `--help` |
| `fullscan.py`, `hotkeys.py`, `diagnose.py`, `theme.py`, `config.py` | Vollbild-Scan, globale Hotkeys, Diagnose-Text, Dark Mode, Einstellungen (+ Migrationen, `SETTINGS_VERSION`) |

## Wichtige Designentscheidungen (nicht ohne Grund ändern)

- **Erkennung**: nicht Text raten, sondern für jeden bekannten Namen die Wahrscheinlichkeit berechnen (Lexikon-Scoring) und über mehrere Frames kombinieren. Unbekannter Text darf nie auf eine falsche Map abgebildet werden.
- **Rundenende – Fehlalarme sind schlimmer als verpasste Erkennungen.** Ein Overlay, das mitten im Match verschwindet, ist der schlimmste Fehler. Darum:
  - Screen-Hinweise brauchen 2 Blicke in Folge (CONTINUE mit sehr gutem Fit: 1), Ladebildschirm 3 Blicke **und** stilles Bild (sonst lösen Reparatur-/Heilbalken aus).
  - Mauszeiger-Hinweis erst nutzen, wenn beim Map-Banner der Zeiger nachweislich versteckt war (`cursor_proven`).
  - Menü-Latch zählt nur Zeit, in der DBD aktiv und der Zeiger sichtbar ist (60 s).
  - Regionen nie in die schwarzen Balken ausdehnen (FPS-Anzeigen, Benachrichtigungen). Ausnahme: `detector.fills_bars()` – Ergebnisbildschirm, Lobby und Menüs nutzen auf Ultrawide die **volle Fensterbreite** (CONTINUE und Währung sitzen am echten rechten Rand, x ≈ 2800–3300). Nur wenn beide Balken selbst Bild enthalten (im Match sind sie schwarz), reichen CONTINUE-/Währungsregion bis zum Fensterrand.
  - Eigenes Overlay wird vor jeder Auswertung aus dem Bild geschwärzt (`worker._mask_overlay`).
- Events mit `gen` (Map-Generation) – veraltete `menu`/`match_end` für eine alte Map werden ignoriert.
- hosts-Datei: latin-1 lesen/schreiben (byte-genau), nur an LF splitten, Backup `hosts.dbdmapscout-backup` vor der ersten Änderung, Fremdeinträge (Make Your Choice) werden ersetzt. Ergebnisdatei wird vom normalen Prozess vorab angelegt (sonst nach Admin-Schreiben nicht lesbar).
- Bewusst **nicht** umgesetzt: Firewall-Modus, Spieldatei-Änderungen, Dead-by-Queue-API. („Verbunden mit“ per Paketköpfen ist seit 1.5.0 drin, auf Wunsch des Nutzers.)
- Make Your Choice ist GPL-3.0: **keinen Code daraus übernehmen**, nur eigene Umsetzungen. Karten-/Realm-Namen stammen aus LucaFontanot/dbd-map-overlay (Apache-2.0), siehe `THIRD_PARTY.md`.

## Fehlersuche mit echten Daten

- Tab Erkennung → Zeile „Rundenende-Erkennung: …“ zeigt live den Zustand.
- „Diagnose kopieren“: Fenster/Overlay-Infos + letzte Rundenende-Prüfungen (CONTINUE-Fit, Währungsgruppen, Ladebalken, Mauszeiger).
- „Debug-Bilder speichern“: Banner-Crops in `debug/`, verkleinerte Vollbilder während der Runde in `debug/frames/`. Solche echten 3440×1440-Bilder sind die beste Grundlage, um Schwellenwerte zu tunen – Änderungen an Schwellen immer gegen Spiel-Screenshots (Match, ESC-Menü) auf Fehlalarme prüfen.

## Offene Ideen (vom Nutzer noch nicht entschieden)

Halten-zum-Anzeigen-Taste, Etagen-Hotkey (Midwich), Autostart mit DBD + Tray-Icon, .exe-Build (vorerst verworfen: Updates per git pull, Virenscanner-Fehlalarme, Admin-Helfer bräuchten Umbau – Desktop-Verknüpfung reicht), Ausblenden im Zuschauermodus, „Match Details“ als zweite Erkennungsquelle.

## Arbeitsweise

- Nutzer: Saru, antwortet auf Deutsch, will direkte, kritische, technisch präzise Antworten.
- Vor größeren Umbauten kurz Plan nennen; nach Änderungen Tests laufen lassen und bei UI-Änderungen das Programm einmal starten.
- Versionsnummer in `dbdmapscout/__init__.py` erhöhen und README anpassen, wenn sich Verhalten ändert.
