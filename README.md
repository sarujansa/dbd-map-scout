# DbD Map Scout

*[English version: README.en.md](README.en.md)*

Map-Overlay für Dead by Daylight. Beim Match-Start wird der Map-Name automatisch erkannt und die passende Callout-Karte aus dem Ordner `maps/` eingeblendet. Die Karte liegt als eigenes, durchklickbares Fenster über dem Spiel.

**Sprache:** Das Programm zeigt Deutsch oder Englisch. Standardmässig richtet es sich nach der Windows-Sprache (Deutsch, wenn Windows auf Deutsch läuft, sonst Englisch). Umstellen unter **Einstellungen → Sprache und Darstellung → Sprache / Language**; wirkt nach dem nächsten Start.

## Installation (einmalig)

1. **Python installieren** (falls noch nicht vorhanden): <https://www.python.org/downloads/>, Version 3.12 oder neuer. Im Installer **„Add python.exe to PATH“** anhaken.
2. Ordner entpacken, z. B. nach `C:\Tools\dbd-map-scout`.
3. **`start.bat`** doppelklicken. Beim ersten Start wird eine eigene Python-Umgebung (`.venv`) angelegt und die Pakete werden installiert (ca. 1–2 Minuten, rund 250 MB). Danach startet das Programm direkt.
4. **Desktop-Verknüpfung:** Läuft das Programm einmal als Administrator (z. B. Rechtsklick auf `start.bat` → „Als Administrator ausführen“), richtet es sie **selbst** ein und erneuert sie nach Updates oder wenn du den Ordner verschiebst. Von Hand geht es mit **`verknuepfung_erstellen.bat`** (Windows fragt einmal nach Administratorrechten). Beides legt in der Windows-Aufgabenplanung die Aufgabe „DbD Map Scout“ an und „DbD Map Scout“ mit eigenem Symbol auf den Desktop: Die Verknüpfung startet das Programm als Administrator (nötig für „Verbunden mit“) **ohne Windows-Abfrage** und ohne Konsolenfenster. Rechtsklick → „An Taskleiste anheften“ geht auch.

**Infobereich und Autostart.** Minimiert verschwindet das Steuerfenster in den Infobereich neben der Uhr (Doppelklick öffnet es, Rechtsklick: Overlay ein/aus, Beenden). Unter **Einstellungen → Start und Infobereich** lässt sich einschalten, dass das Programm mit Windows startet – still im Infobereich, ohne Abfrage; es wartet dann einfach auf DBD. Das Umschalten geht, wenn das Programm über die Desktop-Verknüpfung läuft.

*Zur Sicherheit:* Eine Aufgabe „mit höchsten Rechten“ umgeht die Windows-Abfrage absichtlich – was im Programmordner liegt (auch per Update geholter Code), läuft dann ohne Nachfrage als Administrator. Wer das strenger will, legt den Ordner an einen Ort, in den nur Administratoren schreiben dürfen (z. B. unter `C:\Program Files`).

**Updates** kommen automatisch: Beim Start über `start.bat` bzw. die Desktop-Verknüpfung holt das Programm den neuen Stand von GitHub (nur wenn der Ordner ein Git-Klon auf `main` ist und du keine Programmdateien selbst geändert hast) und installiert geänderte Pakete nach. Offline oder bei eigenen Änderungen startet einfach die vorhandene Version. Was neu ist, steht danach im Log. Abschaltbar unter **Einstellungen → Updates**. Dort gibt es auch **„Jetzt nach Updates suchen“**: fragt GitHub (nur bei diesem Klick), zeigt „Kein Update“ oder die neue Version mit ihren Änderungen, und **„Aktualisieren und neu starten“** beendet das Programm, installiert das Update über `start.bat` und startet neu – auch wenn die Prüfung beim Start ausgeschaltet ist.

In DBD unter **Einstellungen → Grafik** den Anzeigemodus **„Fenster-Vollbild“** verwenden. Im exklusiven Vollbild kann Windows kein Fenster über dem Spiel anzeigen.

## Benutzung

Programm starten und DBD spielen. Wenn beim Match-Start unten links der Map-Name erscheint (z. B. „KOHLELAGER / DAS MACMILLAN-ANWESEN“), wird die Karte automatisch eingeblendet.

**Nach der Runde** verschwindet die Karte wieder. Erkannt wird das an:

- dem Ergebnisbildschirm (Knopf „CONTINUE“/„FORTFAHREN“),
- Lobby, Hauptmenü, Blutnetz und Shop (Währungsanzeige oben rechts),
- dem Ladebildschirm der nächsten Runde,
- einem geschlossenen DBD.

Auf Ultrawide-Monitoren zeigt DBD Ergebnisbildschirm und Menüs in voller Breite, das Match aber in 16:9 mit schwarzen Balken. Das Programm erkennt das und sucht CONTINUE und Währungsanzeige dann bis zum echten Bildschirmrand; im Match bleiben die Balken außen vor.

**In Menüs pausiert das Overlay.** DBD zeigt den Mauszeiger nur in Menüs (ESC-Menü, Ergebnisbildschirm, Lobby). Ist er ein paar Sekunden lang über dem DBD-Fenster sichtbar, blendet sich die Karte aus. Verschwindet er wieder, kommt sie zurück. Ist der Mauszeiger insgesamt eine Minute lang in einem Menü sichtbar, gilt die Runde als beendet.

**Rundentimer.** Der Timer läuft, solange eine Karte eingeblendet ist. Erscheint eine Karte (automatisch erkannt, manuell gewählt oder per Hotkey eingeblendet), beginnt er bei 00:00. Verschwindet sie (Rundenende erkannt oder manuell ausgeblendet), stoppt er. Er steht im Steuerfenster unter dem Map-Namen („Runde läuft: 07:32“, danach „Letzte Runde: 12:04“) und im Overlay groß und mittig direkt unter der Karte, gestaltet wie der Kartentitel: weiße Ziffern mit Schatten, ohne Kasten (abschaltbar im Tab Overlay). Beim Rundenende zählt der erste Hinweis darauf als Endzeit, z. B. das Erscheinen des Mauszeigers auf dem Ergebnisbildschirm, nicht erst der Moment, in dem die Erkennung sicher ist. Das kurze Ausblenden im ESC-Menü oder wenn ein anderes Fenster aktiv ist, hält den Timer nicht an, weil das Match weiterläuft. Ein Layout- oder Map-Wechsel bei eingeblendeter Karte setzt ihn nicht zurück. Ein neues Map-Banner startet immer eine neue Runde, auch wenn das Ende der vorigen nicht erkannt wurde.

Im Tab **Erkennung** zeigt die Zeile „Rundenende-Erkennung: …“ jederzeit, was das Programm gerade sieht, z. B. „im Match · Mauszeiger verborgen“. `Strg+Alt+M` holt eine ausgeblendete Karte sofort zurück.

Oben im Steuerfenster steht immer, woran das Programm gerade ist: **Wartet auf DBD**, **Wartet auf das nächste Match**, **Im Match: …**, **Im Menü – Karte pausiert** oder **Runde vorbei** (Probleme wie ein schwarzes Bild stehen dort in Rot). Technische Einzelheiten stehen im Tab Log.

**Hinweistexte:** Bleibt die Maus kurz auf einem Knopf oder Häkchen, erklärt ein kleiner Text, was er tut (samt Hotkey).

**Layout-Knopf:** Erscheint nur bei Maps mit mehreren Layouts (Coal Tower, Groaning Storehouse, Ironworks of Misery, Shelter Woods, Suffocation Pit, Mount Ormond Resort, Badham Preschool) und zeigt das angezeigte Layout, z. B. „Layout II von V ▸“. Ein Klick schaltet weiter. War die Erkennung beim Layout unsicher, steht „(unsicher)“ dahinter.

Das Steuerfenster ist in Tabs aufgeteilt. Passt ein Tab nicht ins Fenster, erscheint rechts eine Scrollbar (auch per Mausrad); das Fenster lässt sich dafür beliebig kleiner oder grösser ziehen:

| Tab | Inhalt |
|---|---|
| **Maps** | alle Karten nach Realm, Suche, Doppelklick zeigt eine Karte; „Kartenbild hinzufügen …“ für eigene Bilder |
| **Overlay** | Position (Vorgabe oder Schieberegler horizontal/vertikal, 0 % = links/oben, 100 % = rechts/unten), Grösse, Deckkraft, Anzeigeoptionen |
| **Erkennung** | Automatik, Ausblenden nach der Runde, Pause in Menüs, Spielsprache; eingeklappt unter „Erweitert“: Fensteraufnahme, Scans pro Sekunde, Live-Status, Debug-Bilder, Diagnose |
| **Server** | oben der verbundene Spielserver, darunter Serverregionen mit Ping, per hosts-Datei sperren oder freigeben (siehe unten) |
| **Log** | Meldungen mit Kategorien *Erkennung*, *Overlay*, *System*, *Fehler*, einzeln ein-/ausblendbar |
| **Statistik** | deine Runden, filterbar nach Zeitraum (heute, diese Woche, dieser Monat, dieses Jahr) und Serverregion: Anzahl, Ø Dauer, Gesamtzeit; pro Map Runden, Ø und längste Dauer (Spalten anklickbar zum Sortieren); pro Serverregion Runden, Ø Dauer, Anteil und Ø Ping (Median je Runde, nur mit „Verbundener Spielserver“); die letzten 100 Runden mit Datum, Dauer und Serverregion. Gezählt wird vom erkannten Map-Banner bis zum erkannten Rundenende (ab 1 Minute; ohne erkanntes Ende wird die Runde nicht gezählt). Zusätzlich filterbar nach **Rolle** (Killer, Survivor, Custom Games) und mit **Wartezeit in der Lobby**: Ø, Median, kürzeste und längste Suche, aufgeteilt nach Wochentag, Uhrzeit (3-Stunden-Blöcke) oder Region. Als Killer merkt sich jede Runde auch den **Killer** (Name unter dem Lobby-Knopf): eigene Tabelle mit Runden, Ø Dauer und häufigster Map je Killer, und Filter **Killer** – z. B. welche Maps du mit der Nurse wie oft bekommst und wie lange die Runden dauern. Lag die Rollenerkennung daneben: Runde unter „Letzte Runden“ markieren und mit **Killer / Survivor / Custom Game** korrigieren. Wurde das Ende einer Runde nicht erkannt, zählt sie nicht – die Statistik sagt dann „⚠ Nicht gezählt: 2 × …“, damit du weisst, dass Runden fehlen. Nur lokal in `rounds.jsonl`, „Verlauf löschen“ entfernt alles |
| **Einstellungen** | Sprache, Dark Mode, Hotkeys ändern, Start/Infobereich, Updates, eigene Zuordnungen, Ordner öffnen |

**Position „automatisch“:** Läuft DBD mit 16:9-Bild auf einem breiteren Monitor (z. B. 3440×1440 mit schwarzen Rändern), landet die Karte im linken schwarzen Rand und wird so skaliert, dass sie hineinpasst. Sonst erscheint sie oben links. Sobald du einen Positions-Regler bewegst oder die Karte mit der Maus verschiebst, gilt „eigene Position“. „Zurücksetzen“ stellt wieder „automatisch“ ein.

**Wartezeit und Rolle:** Außerhalb des Matchs schaut das Programm einmal pro Sekunde auf den Knopf unten rechts in der Lobby. CANCEL mit „EST.“ darunter heißt: Die Suche läuft (DBD zeigt die bisherige Wartezeit selbst an, die wird übernommen). READY bzw. CANCEL ohne „EST.“ heißt: Die Lobby ist gefunden, die Wartezeit steht fest. Steht unter dem Knopf der Killername, spielst du Killer, sonst Survivor; steht gar nichts darunter, ist es ein Custom Game (keine Wartezeit). Auf dem Ergebnisbildschirm bestätigen die Kategorien (BRUTALITY … bzw. OBJECTIVES …) die Rolle. Das Hauptfenster zeigt „Suche läuft: 02:13 · Nurse“ bzw. „Rolle: Nurse · Wartezeit 02:13“ (als Survivor „Survivor“). Der Killername wird mit einer Liste der Killer abgeglichen; ein neuer Killer, der dort noch fehlt, wird so übernommen, wie er dasteht – nie einem falschen zugeordnet. Eine abgebrochene Suche zählt nicht. Im Match wird nichts davon geprüft.

**Meldung, wenn die Lobby gefunden ist:** Hinweiston plus eigenes kleines Hinweisfenster unten rechts („Lobby gefunden – nach 04:12 – READY drücken.“; über allen Fenstern, nimmt keinem Fenster den Fokus, erscheint auch bei „Nicht stören“ – Windows-Meldungen würden dann verschluckt; „Meldung testen“ zeigt es), und eine Erinnerung, wenn der Lobby-Countdown unter 15 s fällt und READY noch nicht gedrückt ist. Standardmäßig nur, solange DBD nicht das aktive Fenster ist – du kannst also während der Suche etwas anderes machen. Abschaltbar unter Einstellungen → Benachrichtigungen. Es geht nichts ans Spiel. Erkannt werden die englischen Texte des Spiels.

**Nur Infos ohne Karte:** Im Tab Overlay „Karte anzeigen“ ausschalten – dann zeigt das Overlay bei Rundenbeginn nur Rundentimer, Serverregion und Ping (an derselben Stelle, im selben Stil). Erkennung, Ausblenden nach der Runde, Menü-Pause und Statistik laufen unverändert weiter.

**Karte drehen:** Knopf **Drehen ↻** im Hauptfenster oder `Strg+Alt+R` dreht die angezeigte Karte um 90° im Uhrzeigersinn, damit sie so liegt, wie du dir die Map vorstellst. Die Drehung wird pro Map gemerkt (Tab Overlay: „Für diese Map zurücksetzen“). Der Map-Name über der Karte bleibt aufrecht; die Zahlen und Beschriftungen in der Karte drehen sich mit, weil sie Teil des Bildes sind. Alle mitgelieferten Karten haben den Namen oben im selben Stil; nur bei Midwich (animiertes GIF mit eigenem Hintergrund) dreht sich der Name mit. Eine Karte, die sich automatisch mit der Kamera dreht, gibt es nicht: Den Blickwinkel kennt nur das Spiel selbst, und dessen Speicher wird nicht gelesen.

**Im schwarzen Rand halten** (Tab Overlay, standardmäßig an): Auf Ultrawide bleibt die Karte bei jeder Position im Balken, in dem sie liegt – „oben/unten links“ im linken, „oben/unten rechts“ im rechten Balken, eine eigene Position in dem Balken, in dem sie beginnt. Ist sie zu breit, wird sie verkleinert, statt ins Spielbild zu ragen. Eine bewusst mitten über dem Spiel platzierte Karte bleibt unverändert. Abschalten, wenn die Karte grösser sein darf als der Rand.

Das Overlay ist ein eigenes, natives Windows-Fenster: immer im Vordergrund, durchklickbar, und es nimmt dem Spiel nie den Fokus weg.

**Erkennung, wenn andere Fenster über DBD liegen.** Normalerweise wird der Bildschirm aufgenommen – liegt ein anderes Fenster über DBD, sieht das Programm dieses Fenster. Ist DBD nicht das aktive Fenster, nutzt das Programm deshalb die **Fensteraufnahme von Windows** (Windows Graphics Capture, dieselbe Technik wie OBS „Fensteraufnahme“): Windows liefert das Bild des DBD-Fensters, egal was darüber liegt. Das Spiel wird dabei nicht angefasst. Ist DBD wieder 5 Sekunden aktiv, geht es zurück zur sparsameren Bildschirmaufnahme. Minimiert geht nichts. Abschaltbar im Tab Erkennung („Auch erkennen, wenn andere Fenster über DBD liegen“). Das nötige Zusatzpaket installiert `start.bat` beim nächsten Start einmalig; klappt das nicht, läuft alles wie bisher über die Bildschirmaufnahme. Die Zeile „Aufnahme“ in der Diagnose zeigt, welche Quelle gerade genutzt wird.

| Hotkey | Funktion |
|---|---|
| `Strg+Alt+M` | Overlay ein/aus |
| `Strg+Alt+V` | Layout-Variante wechseln (z. B. Coal Tower ↔ Coal Tower II) |
| `Strg+Alt+S` | Bildschirm scannen (falls die automatische Erkennung den Banner verpasst hat) |
| `Strg+Alt+←` / `→` | vorherige / nächste Map |
| `Strg+Alt+↑` / `↓` | Overlay grösser / kleiner – gilt für die angezeigte Map und wird pro Map gemerkt (Tab Overlay: „Für diese Map zurücksetzen“; der Schieberegler „Grösse“ ist die Standardgrösse für alle anderen) |
| `Strg+Alt+P` | Position ändern (Overlay mit der Maus ziehen, Mausrad = Grösse, nochmals drücken = fertig) |
| `Strg+Alt+R` | angezeigte Karte um 90° drehen (pro Map gemerkt) |

**Einstellungen sichern:** Einstellungen → Sicherung → „Einstellungen exportieren …“ speichert alles (Hotkeys, Grösse und Drehung pro Map, eigene Map-Zuordnungen, Overlay, Regionen) in eine Datei, „… importieren …“ lädt sie wieder und startet das Programm neu. Die Statistik gehört nicht dazu.

Hotkeys lassen sich unter **Einstellungen → Hotkeys** ändern: Feld anklicken und die neue Kombination drücken (Esc bricht ab, Entf schaltet den Hotkey aus, „Standard“ stellt alle zurück). Buchstaben und Ziffern brauchen Strg oder Alt, damit der Hotkey nicht das normale Tippen blockiert; doppelt belegte Kombinationen werden abgelehnt. Alle Einstellungen landen in `settings.json`.

**Spielsprache:** Standardmässig werden englische und deutsche Map-Namen erkannt. Wenn DBD auf Französisch, Spanisch, Italienisch, Polnisch, Portugiesisch oder Türkisch läuft, die Sprache im Steuerfenster anhaken (Tab Erkennung). Das ist unabhängig von der Sprache des Programms selbst.

## Serverregion wählen (wie „Make Your Choice“)

Im Tab **Server** stehen alle Serverregionen von DBD (AWS GameLift) mit ihrem aktuellen Ping. Du hakst die Regionen an, auf denen du spielen willst, und drückst **Auswahl anwenden**. Alle anderen Regionen werden in der Windows-**hosts-Datei** gesperrt: Ihre Servernamen zeigen dann auf 0.0.0.0, DBD erreicht sie nicht und sucht Matches nur noch in den erlaubten Regionen. **Alles freigeben** entfernt die Sperren wieder.

- **Administratorrechte:** Die hosts-Datei ist eine Windows-Systemdatei. Deshalb fragt Windows beim Anwenden und beim Freigeben nach. Nur dieser Schreibvorgang läuft mit Administratorrechten, das Programm selbst nicht (außer du startest es als Administrator oder nutzt die Anzeige des verbundenen Servers, siehe unten).
- **DBD danach neu starten.** Die Region wird beim Spielstart festgelegt.
- **Was genau geschrieben wird:** Nur ein eigener, markierter Abschnitt („DbD Map Scout: server regions“). Vor der ersten Änderung wird die Originaldatei als `hosts.dbdmapscout-backup` daneben gesichert. Einträge von „Make Your Choice“ oder anderen Tools für dieselben Server werden beim Anwenden entfernt, weil sie die Auswahl sonst überschreiben würden. Das Programm fragt vorher nach.
- **Ping:** Gemessen wird wie im Spiel über die UDP-Ping-Beacons von GameLift (Port 7770), notfalls per normalem Ping. Die Namen werden direkt beim DNS-Server aufgelöst, deshalb gibt es auch für gesperrte Regionen einen Wert. Gemessen wird nur, wenn der Tab offen ist oder du „Ping messen“ drückst.
- **Grenzen:** Mit VPN unzuverlässig. Anders als der „Enforced“-Modus von Make Your Choice setzt das Programm keine Firewall-Regeln. DBD kann deshalb in seltenen Fällen trotzdem auf eine andere Region ausweichen, meist N. Virginia. Die Sperren bleiben aktiv, auch wenn das Programm geschlossen ist. Beim Start meldet das Log, wenn Regionen gesperrt sind.
- **Nicht übernommen** aus Make Your Choice: Firewall-Modus, eigener Splash-Screen und Trailer überspringen (verändern Spieldateien), Warteschlangen-Anzeige über den Fremddienst Dead by Queue.

### Verbundener Spielserver („Connected to“)

Mit dem Häkchen **Verbundenen Spielserver anzeigen** im Tab Server zeigt das Programm, mit welchem Server DBD gerade verbunden ist, z. B. „Verbunden mit: Frankfurt (3.120.45.67)“. Zwischen den Matches steht dort „Warte auf Match …“. Die Anzeige erscheint auch im Hauptfenster unter dem Rundentimer und im Overlay unter dem Timer als grüner Punkt mit der Region („● FRANKFURT“, ohne IP, abschaltbar im Tab Overlay), darunter der Ping („PING 24 MS“, grün bis 60 ms, gelb bis 120 ms, rot darüber), und das Log meldet jeden neuen Server mit seiner Region. Liegt er außerhalb deiner Regionsauswahl, steht das dabei. Die IP-Adresse steht nur live im Fenster und wird nicht ins Logfile geschrieben.

- **Administratorrechte:** Das Mitlesen des Netzwerkverkehrs braucht sie. Startest du das Programm als Administrator, läuft es ohne Nachfrage. Sonst fragt Windows bei jedem Programmstart einmal nach, solange das Häkchen gesetzt ist.
- **Was gelesen wird:** Nur die Kopfdaten der Netzwerkpakete (IP-Adressen und Ports), nie deren Inhalt. Es kommt nur der Verkehr deines eigenen PCs an: Die Netzwerkkarte wird nicht in den Promiscuous-Modus versetzt, der auch fremde Pakete im Netz annimmt. Unterstützt Windows das nicht, bleibt die Anzeige aus, statt auf diesen Modus auszuweichen. Es wird nichts gesendet, nichts verändert und nichts gespeichert. Das Spiel wird dabei nicht angefasst, und es braucht keinen Zusatztreiber wie Npcap.
- **Wie der Server erkannt wird:** Ein laufendes Match tauscht ständig viele UDP-Pakete mit seinem Server aus. Die Region steht im Namen, den AWS für die Server-Adresse vergibt (Reverse-DNS, z. B. `…eu-central-1.compute.amazonaws.com`). Andere Programme mit viel UDP-Verkehr wie Sprachchat werden ignoriert, weil sie nicht auf AWS-Servern laufen.
- **Ping:** Gemessen wird wie im Tab Server und wie DBD selbst: alle 5 Sekunden ein kleines UDP-Paket an den GameLift-Ping-Beacon der verbundenen Region, angezeigt wird der Mittelwert (Median) der letzten drei Messungen. Der Spielserver selbst bekommt keine Pakete. Er steht im selben Rechenzentrum, der Wert entspricht also praktisch dem Spiel-Ping.
- **Sparsam:** Läuft DBD 30 Sekunden nicht (z. B. während eines Downloads), pausiert der Mitschnitt und startet automatisch wieder, sobald DBD läuft – nur wenn das Programm als Administrator läuft, sonst würde jeder Neustart eine Windows-Abfrage auslösen.
- **Grenzen:** Mit VPN kann die Anzeige fehlen. Ohne Administratorrechte, zum Beispiel bei einer abgelehnten Windows-Abfrage, bleibt sie aus.
- **Am sichersten:** Das Programm normal starten statt als Administrator, dann läuft nur der kleine Mitschnitt-Helfer mit Adminrechten (eine Windows-Abfrage pro Start). Wer ganz auf Nummer sicher gehen will, lässt das Häkchen aus – für Map-Erkennung und Overlay wird der Mitschnitt nicht gebraucht.

## So funktioniert die Erkennung

1. Etwa 5× pro Sekunde wird nur der Bereich unten links des DBD-Fensters aufgenommen, wie bei einer Bildschirmaufnahme. Ist die Map erkannt und das Match läuft, sinkt das auf 1× pro Sekunde (spart Leistung für das Spiel); nach dem Rundenende geht es wieder auf den vollen Takt.
2. Gesucht wird die **dünne Trennlinie** zwischen Map-Name und Realm. Sie ist ein sehr eindeutiges Merkmal und kostet nur wenige Millisekunden. Solange sie nicht zu sehen ist, läuft keine OCR.
3. Ist sie da, werden die Textzeile darüber (Map-Name, auch zweizeilig) und darunter (Realm) genau ausgeschnitten. Das funktioniert unabhängig von Auflösung, UI-Skalierung und Monitorformat.
4. Ein Texterkennungsmodell (PaddleOCR PP-OCRv4, läuft lokal) liefert pro Buchstabe Wahrscheinlichkeiten. Statt daraus Text zu raten, wird für **jeden bekannten Map-Namen berechnet, wie wahrscheinlich genau dieser Name ist**, zusammen mit dem Realm. Deshalb stören Hintergrund, Nebel und Apostrophe kaum, und „COAL TOWER“ lässt sich von „COAL TOWER II“ unterscheiden.
5. Die Ergebnisse mehrerer Bilder werden kombiniert. Unbekannter Text (z. B. eine neue Map ohne Bild) wird nicht auf eine falsche Map abgebildet, sondern im Log gemeldet.

**Unbekannte Map zuordnen.** Liest das Programm einen Map-Namen, den es nicht kennt (z. B. nach einem DBD-Update oder bei anderer Schreibweise), erscheint im Hauptfenster „Unbekannte Map gelesen: „…““ mit dem Knopf **Zuordnen …**. Dort die richtige Map wählen (ein Vorschlag ist vorausgewählt) – der gelesene Name wird ab sofort erkannt. Die Zuordnungen stehen in `settings.json` und bleiben bei Updates erhalten; der Realm wird weiterhin geprüft. Löschen unter **Einstellungen → Eigene Map-Zuordnungen**.

Hinweis zu Varianten: Seit Patch 8.6.0 sind die II/III-Layouts (MacMillan II, Ormond II/III, Badham II–V) nur noch in Custom Games spielbar. Bei unsicherer Lesung wird deshalb leicht das Standard-Layout bevorzugt. `Strg+Alt+V` oder der Layout-Knopf wechselt manuell.

### Wie gut ist die Erkennung?

Getestet mit echten DBD-Screenshots und mit nachgebauten Map-Bannern auf echten Spielhintergründen. Nachgebaut heisst: Roboto-Schrift, Geometrie von echten 4K-Screenshots abgemessen, EN/DE, Nebel, Schnee, Einblend-Animation.

| Test | Ergebnis |
|---|---|
| echte Banner-Screenshots (2 Maps × 5 Auflösungen × 2 Hintergründe) | 20/20 richtig |
| alle 56 Bilder × EN/DE, gemischte Auflösungen 720p–4K + Ultrawide | 112/112 richtige Map inkl. Layout |
| dasselbe mit sehr unruhigen Hintergründen | 112/112 richtige Map, 1× falsches Layout (Badham II → I) |
| Bildschirme ohne Banner (Lobby, Menüs, Gameplay, Endscreen) | 0 Fehlalarme bei 319 Bildern |
| Banner mit unbekannten Map-Namen | 0 von 120 fälschlich einer Map zugeordnet |
| Vergleich mit dem Ansatz von dbd-map-overlay (nachgebaut), 1440p, einzelnes Bild mit voll sichtbarem Banner | 55/56 statt 44/56, ca. 0,1 s statt 1,5–3 s pro Bild |

Die synthetischen Tests ersetzen keinen Praxistest. Wenn eine Map in echten Runden nicht erkannt wird, helfen die Debug-Bilder (siehe unten) beim Nachschärfen.

## Eigene / neue Karten

- **Eigenes Kartenbild (empfohlen):** Tab Maps → „Kartenbild hinzufügen …“ (oder nach einem nicht erkannten Banner „Bild hinzufügen …“). Bild wählen, dann entweder das Bild einer vorhandenen Map ersetzen oder eine neue Map anlegen (Name so, wie er im Banner steht, und Realm). Das Programm schneidet den Rand ab, macht den Hintergrund der Community-Karten (Dunkelblau `#282a42`, Graulila `#535781`, 10 % Toleranz) transparent, bringt das Bild auf 1280 px Höhe und speichert es als WebP in `user_maps/`. Mit „Map-Namen oben einfügen“ (standardmäßig an) schreibt es den Namen wie bei den mitgelieferten Karten über die Karte (weiss mit Schatten, Schrift Fira Sans ExtraBold); hat das Bild oben schon einen Namen, bleibt es dabei. Eine Vorschau zeigt vorher/nachher. Animierte GIFs werden unverändert übernommen. `user_maps/` wird von Git ignoriert, das Update beim Start funktioniert also weiter. Eigene Bilder haben Vorrang vor den mitgelieferten; „Eigenes Bild löschen“ stellt das Original wieder her.
- **Neues Bild von Hand ergänzen:** Datei in einen Unterordner von `user_maps/` (oder `maps/`) legen, benannt nach dem Map-Namen, wie er im Spiel steht, z. B. `user_maps/Neuer Realm/Neue Map.png`. Das Programm erkennt sie dann automatisch (englischer Name bzw. der Name aus der Datei). Bilder in `maps/` gelten als eigene Änderung und halten das automatische Update an.
- **Bild austauschen:** Datei in `maps/` ersetzen oder in `maps.json` den Pfad unter `variants` ändern.
- **Zusätzliche Schreibweise:** in `maps.json` bei der Map `"aliases": ["ANDERER NAME"]` ergänzen.

## Wenn etwas nicht klappt

- **Karte ist nicht zu sehen:** Im Steuerfenster „Overlay testen“ drücken. Die Karte erscheint dann 10 Sekunden lang an ihrer normalen Position, auch wenn sie sonst gerade ausgeblendet wäre (nochmal drücken – „Test beenden“ – blendet sie sofort wieder aus). War vorher keine Karte eingeblendet, ist nach dem Test auch wieder keine zu sehen. Bleibt sie unsichtbar, „Diagnose kopieren“ drücken und den Text weitergeben. Er enthält Fensterposition, Fensterstil und Z-Reihenfolge gegenüber DBD.
- **Map wird nicht erkannt:** Im Steuerfenster „Debug-Bilder speichern“ aktivieren und ein Match starten. Im Ordner `debug/` landen dann die Bilder, die das Programm gesehen hat, samt gelesenem Text.
- **Karte verschwindet nach der Runde nicht:** Im Tab Erkennung auf die Zeile „Rundenende-Erkennung“ schauen. Direkt danach „Diagnose kopieren“ drücken: Der Text enthält die letzten Prüfungen (was bei „CONTINUE“, Währung und Ladebalken gelesen wurde und ob der Mauszeiger sichtbar war). Mit „Debug-Bilder speichern“ landen während der Runde außerdem verkleinerte Bildschirmfotos in `debug/frames/`.
- **Eigene Screenshots testen:** Screenshots mit sichtbarem Map-Banner (Win+Druck) auf `screenshot_testen.bat` ziehen. Das Fenster zeigt dann, was erkannt wird.
- **Fehlermeldungen sehen:** `start_debug.bat` startet mit Konsole. Ausserdem gibt es die Protokolldatei `dbdmapscout.log`.
- **„Aufnahme ist schwarz“:** DBD auf „Fenster-Vollbild“ stellen. Bei aktiviertem Windows-HDR kann die Aufnahme ebenfalls Probleme machen.
- **Hotkey geht nicht:** Das Log meldet, wenn ein anderes Programm die Kombination belegt. In `settings.json` eine andere wählen.

## Regeln / Fair Play

Das Programm wurde bewusst so gebaut, dass es **nicht mit dem Spiel interagiert**:

- keine Tastatur- oder Mauseingaben ans Spiel, keine Automatisierung von Spielaktionen,
- kein Zugriff auf den Spielprozess (kein Speicherlesen, keine Injection, nicht einmal ein Prozess-Handle), keine Netzwerkverbindung zum Spiel,
- keine Spieldateien werden gelesen oder verändert,
- gelesen werden nur Bildschirmpixel (wie bei OBS/Discord) und ob der Windows-Mauszeiger gerade sichtbar ist (dieselbe Systeminfo, mit der OBS den Zeiger in Aufnahmen zeichnet). Genutzt wird nur der Map-Name, den das Spiel allen anzeigt,
- angezeigt wird eine statische Community-Karte, keine versteckten Informationen (keine Generatoren, keine Positionen),
- Map-Erkennung und Overlay bauen keine Internetverbindung auf (Updates: nur im Starter und auf Knopfdruck „Jetzt nach Updates suchen“, nur GitHub), die Texterkennung läuft komplett lokal. Nur der Tab **Server** misst auf Wunsch den Ping zu den GameLift-Servern von AWS.
- Der Tab **Server** verändert nicht das Spiel, sondern die Windows-hosts-Datei. Das ist eine Systemeinstellung, die für den ganzen PC gilt und jederzeit mit „Alles freigeben“ rückgängig gemacht werden kann. BHVR hat Region-Tools wie „Make Your Choice“ weder offiziell erlaubt noch verboten. Auch hier gilt: Nutzung auf eigene Verantwortung.

BHVRs [Game Rules](https://forums.bhvr.com/dead-by-daylight/kb/articles/139-game-rules) verbieten Drittsoftware, die einen „unfair advantage that wasn't intended by the game“ verschafft, sofern sie nicht freigegeben ist. Eine offizielle Freigabe für Map-Overlays gibt es nicht. Die Entscheidung liegt bei BHVR, Nutzung auf eigene Verantwortung. In Turnieren oder Ligen gelten deren eigene Regeln.

## Aufbau

```
start.bat               Start (richtet beim ersten Mal alles ein)
start_debug.bat         Start mit Konsole
screenshot_testen.bat   Screenshots per Drag & Drop testen
maps/                   Kartenbilder
maps.json               Zuordnung Bild ↔ Ingame-Namen (EN/DE/FR/ES/IT/PL/PT/TR), Realm, Varianten
models/                 OCR-Modelle (PP-OCRv4, ONNX)
dbdmapscout/            Programmcode (Python); hostsedit.py schreibt die hosts-Datei (einziger Teil mit Adminrechten)
tests/                  Selbsttests (optional: pip install pytest, dann python -m pytest tests)
```

Lizenzen und Quellen: siehe `THIRD_PARTY.md`.
