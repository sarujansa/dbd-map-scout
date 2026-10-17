"""Info texts shown when the mouse rests on a button or checkbox (the Qt window shows them).

``attach_all(root, lookup)`` walks the UI model once after a tab or dialog is built and gives every
button/checkbox a tooltip whose text ``lookup(widget)`` returns (a string, a callable returning
one – for buttons whose label changes – or None); ``widget._dbdms_tip()`` is the text now. The texts themselves are in ``TIPS`` below,
keyed by the button label, so they stay in one place.
"""
from __future__ import annotations

from . import uimodel as ui
from .i18n import _, source

# German label -> German info text (buttons/checkboxes with a fixed label); both translated via i18n
TIPS = {
    # main window
    "Map-Namen oben einfügen (wie bei den mitgelieferten Karten)":
        "Schreibt den Map-Namen weiss mit Schatten über die Karte, im Stil der mitgelieferten Karten. Hat das Bild "
        "oben schon einen Namen, passiert nichts. Beim Drehen bleibt der Name aufrecht.",
    "Ton und Meldung, wenn eine Lobby gefunden wurde":
        "Spielt einen Hinweiston und zeigt eine Windows-Meldung, sobald DBD eine Lobby gefunden hat – praktisch, "
        "wenn du während der Suche etwas anderes machst.",
    "Erinnern, wenn der Lobby-Countdown abläuft und READY noch nicht gedrückt ist":
        "Noch einmal melden, wenn der Countdown der Lobby unter 15 s fällt und du READY nicht gedrückt hast.",
    "Nur wenn DBD nicht das aktive Fenster ist":
        "Keine Meldung, solange DBD im Vordergrund ist – dann siehst du die Lobby ja selbst.",
    "Einstellungen exportieren …": "Speichert alle Einstellungen in eine Datei: Hotkeys, Grösse und Drehung pro Map, "
                                   "eigene Map-Zuordnungen, Overlay, Regionen … Die Statistik (rounds.jsonl) gehört "
                                   "nicht dazu.",
    "Einstellungen importieren …": "Lädt eine exportierte Einstellungsdatei und startet das Programm neu. Fehlende "
                                   "Werte (ältere Sicherung) bekommen ihren Standard.",
    "Rückgängig": "Nimmt die letzte Änderung an Position oder Grösse zurück (Karte, Systemwerte, Musik) – auch "
                  "mit Strg+Z auf dieser Seite. Ein ganzes Ziehen zählt als ein Schritt.",
    "Position und Grösse je DBD-Fenstergrösse merken":
        "Merkt Position und Grösse aller Elemente getrennt für jede Grösse des DBD-Fensters (z. B. Vollbild "
        "3440×1440 und ein kleineres Fenster) und lädt sie automatisch, sobald DBD in dieser Grösse läuft.",
    "Karte darf grösser als der Balken werden (ragt dann ins Spielbild)":
        "Erlaubt jede Kartengrösse: Ist die Karte breiter als der schwarze Balken, bleibt sie an dessen Aussenrand "
        "und ragt ins Spielbild. Aus: Die Karte wird nie breiter als der Balken (auf 3440×1440 etwa 31 % der "
        "Bildhöhe).",
    "Meldung testen": "Zeigt die Meldung und spielt den Ton – so siehst du, wo sie erscheint.",
    "Killer": "Diese Runde als Killer-Runde zählen (falls die Erkennung falsch lag).",
    "Zuordnen": "Der markierte Name (Skin oder neuer Killer) zählt ab jetzt als der gewählte Killer – auch in allen "
                "bisherigen Runden.",
    "Ohne Karte: „Warte auf Map“ und Lobby-Status anzeigen":
        "Solange DBD läuft und keine Karte eingeblendet ist, zeigt das Overlay eine kleine Karte: „Warte auf "
        "Map“, darunter Suche/Lobby (z. B. „Suche läuft: 02:13 · Nurse“) oder die letzte Runde. Gilt nicht, "
        "wenn du die Karte selbst ausgeblendet hast.",
    "Etagen (Midwich) untereinander zeigen (aus: nur die untere)":
        "An: Karten mit Etagen (Midwich) zeigen alle Etagen untereinander, oben über unten – jede so groß wie "
        "eine normale Karte, soweit der Platz reicht. Aus: Sie starten mit der unteren Etage. Der Knopf „Etage“ "
        "oder der Hotkey schaltet jederzeit um.",
    "Eigene Bilanz auf der Map unter dem Timer (Stats-Seite)":
        "Zeigt unter dem Rundentimer, wie es dir auf dieser Map bisher ging: als Killer Ø Kills, als Survivor den "
        "Anteil Escapes – aus den Runden mit Daten der Stats-Seite, ab 3 Runden.",
    "Einrichtung starten": "Öffnet noch einmal die Einrichtung vom ersten Start: Spielsprache, Overlay-Position "
                           "und die wichtigsten Tasten.",
    "„Heute“: Runden, Spielzeit, Ø Kills/Entkommen, Uhrzeit":
        "Eine eigene Karte, solange eine Map im Match zu sehen ist: wie viele Runden du heute gespielt hast, wie "
        "lange, Ø Kills bzw. Entkommen laut Stats-Seite und die Uhrzeit. Position darunter, Grösse über den "
        "Grössenregler („Heute“ wählen).",
    "Dunkle Fläche hinter „Heute“":
        "Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter „Heute“.",
    "„Läuft gerade“: Titel, Interpret und Cover der Musik (Spotify, Browser … – nur während sie spielt)":
        "Liest Titel und Interpret aus der Windows-Mediensteuerung (dieselbe Liste wie beim Lautstärkeregler von "
        "Windows) – nur Anzeige, das Programm steuert nichts und speichert nichts.",
    "Fortschritt des Lieds zeigen (Zeit und Balken)":
        "Unter Titel und Künstler: wie weit das Lied ist, mit Balken und Länge – wie in Spotify.",
    "Zeile CPU (Temperatur, Last)":
        "Zeile in den Systemwerten an/aus. Die Warnungen „CPU/GPU DROSSELT“ erscheinen immer.",
    "Zeile GPU (Temperatur, Last)":
        "Zeile in den Systemwerten an/aus. Die Warnungen „CPU/GPU DROSSELT“ erscheinen immer.",
    "Zeile Hotspot / GPU-Speicher (HWiNFO)":
        "Zeile in den Systemwerten an/aus – Hotspot und Memory Junction kommen nur mit HWiNFO.",
    "Zeile VRAM":
        "Zeile in den Systemwerten an/aus.",
    "Zeile RAM":
        "Zeile in den Systemwerten an/aus.",
    "Vorlage anwenden":
        "Setzt Karte, Systemwerte, „Heute“ und Musik auf einmal auf die gewählte Anordnung. „Rückgängig“ holt "
        "die vorherige zurück.",
    "Weich ein- und ausblenden (Karte, Systemwerte, Heute)":
        "Karte, Systemwerte und „Heute“ blenden in einer Drittelsekunde ein und aus, statt hart zu erscheinen. "
        "Die Musik hat ihr eigenes Häkchen.",
    "Dunkle Fläche hinter Karte und Infos":
        "Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Karte, Timer und Infozeilen (auch hinter "
        "„Warte auf Map“) – gut lesbar über hellen Stellen im Spiel.",
    "Dunkle Fläche hinter den Systemwerten":
        "Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Systemwerten und „Heute“.",
    "Balken in der Farbe des Covers":
        "Der Fortschrittsbalken nimmt die Hauptfarbe des Albumcovers an, wie bei Spotify. Graue Cover: weiss.",
    "Restzeit statt Länge (−1:46)":
        "Rechts neben dem Balken steht, wie lange das Lied noch läuft, statt seiner Gesamtlänge.",
    "Dunkle Fläche hinter der Musikkarte":
        "Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Cover und Text – gut lesbar, wenn die "
        "Karte über hellen Stellen im Spiel liegt.",
    "Weich ein- und ausblenden (auch beim nächsten Lied)":
        "Die Musikkarte blendet in einer Drittelsekunde ein und aus, statt hart zu erscheinen – auch wenn ein "
        "neues Lied beginnt.",
    "Albumcover zeigen":
        "Das Bild zum Lied links neben Titel und Interpret – Windows liefert es mit; es bleibt nur im Speicher.",
    "OLED-Schwarz (echtes Schwarz statt Grau im Dark Mode)":
        "Hintergründe in echtem Schwarz statt Dunkelgrau – passt zu OLED-Bildschirmen und geht mit jeder "
        "Akzentfarbe. Im hellen Modus ohne Wirkung.",
    "Anordnung zurücksetzen": "Stellt die Kästen auf allen Seiten wieder in die ursprüngliche Reihenfolge.",
    "Zurück": "Zurück zu den Karten des Realms (Esc).",
    "Anzeigen": "Blendet die gewählte Map jetzt als Overlay ein – die Erkennung übernimmt beim nächsten Match "
                "wieder.",
    "Killer setzen": "Setzt den Killer nur für die markierte Runde und zählt sie als Killer-Runde – z. B. wenn sie "
                     "fälschlich als Survivor gezählt wurde oder der Name falsch gelesen wurde.",
    "Zuordnungen löschen": "Entfernt alle eigenen Killer-Zuordnungen; die Namen erscheinen wieder so, wie sie gelesen "
                           "wurden.",
    "Survivor": "Diese Runde als Survivor-Runde zählen (falls die Erkennung falsch lag).",
    "Custom Game": "Diese Runde als Custom Game zählen – sie fliesst dann nicht in die Wartezeit ein.",
    "Farming an/aus": "Diese Runde als Farming-Runde zählen bzw. wieder als normale Runde – Farming-Runden "
                      "erscheinen nur unter dem Filter „Farming“. Runden auf der Farming-Region (Einstellungen → "
                      "Mehr) bleiben Farming.",
    "Runden ohne Crossplay als Farming zählen": "Zeigt die Lobby die Weltkugel mit rotem Kreuz (Crossplay aus), "
                                                 "zählt die nächste Runde als Farming-Runde.",
    "Jede Runde mit OBS aufnehmen": "Das Programm startet die OBS-Aufnahme beim Map-Banner und stoppt sie beim "
                                    "erkannten Rundenende (obs-websocket, nur auf diesem PC). OBS muss laufen.",
    "Verbindung testen": "Verbindet sich einmal mit OBS und zeigt Version, Aufnahmezustand, Wiederholungspuffer "
                         "und ob der Aufnahmeordner erreichbar ist.",
    "Aufnahmeordner wählen …": "Ordner, in den OBS die Runden legt – z. B. auf der externen Platte. Gemerkt wird das "
                               "Laufwerk, nicht der Buchstabe: bekommt die Platte einen anderen, findet das "
                               "Programm den Ordner trotzdem.",
    "Wiederholungspuffer mit DBD starten und stoppen": "Das Programm startet den Wiederholungspuffer in OBS, sobald "
                                                       "DBD läuft, und stoppt ihn, wenn DBD zu ist – so kostet er "
                                                       "ausserhalb des Spiels nichts und du musst nicht daran denken.",
    "Vorlauf: Wiederholungspuffer von OBS beim Map-Banner sichern (Sekunden davor)":
        "Das Banner kommt erst ~40 s nach Matchbeginn. Läuft in OBS der Wiederholungspuffer, wird er beim Banner "
        "gespeichert – so fehlt der Anfang (Spawn) nicht. Die Datei liegt als „(Vorlauf)“ neben der Runde.",
    "Vorlauf und Runde zu einer Datei zusammenfügen": "Nach der Runde hängt ffmpeg den Vorlauf vorne an die Aufnahme "
                                                      "– ohne Neukodierung, in Sekunden, Bild und Ton bleiben wie "
                                                      "von OBS. Klappt es nicht, bleiben beide Dateien liegen.",
    "Aufnahmen einrichten …": "Öffnet die Einstellungen für die Aufnahmen mit OBS (Ordner, Verbindung).",
    "Farming-Runden im Unterordner „Farming“ ablegen": "Runden, die das Programm als Farming erkennt (Crossplay aus "
                                                        "oder die Farming-Region), landen im Unterordner „Farming“ "
                                                        "des Aufnahmeordners statt zwischen den normalen Runden. "
                                                        "Clips gehen immer in den Ordner „Clips“.",
    "Abspielen": "Spielt die markierte Aufnahme im Standard-Videoplayer ab.",
    "Im Explorer zeigen": "Öffnet den Explorer mit der markierten Datei.",
    "Behalten": "Eine behaltene Aufnahme wird nie fürs Aufräumen gelöscht, wenn die Platte Platz braucht. Nochmal "
                "drücken hebt es auf.",
    "Nicht mehr behalten": "Eine behaltene Aufnahme wird nie fürs Aufräumen gelöscht, wenn die Platte Platz braucht. "
                           "Nochmal drücken hebt es auf.",
    "Aufnahme löschen": "Löscht die markierte Aufnahme (und ihren Vorlauf) von der Platte – nach Rückfrage.",
    "Aufnahmeordner öffnen": "Öffnet den Aufnahmeordner im Explorer.",
    "Clip schneiden …": "Öffnet den Clip-Editor für die markierte Aufnahme: Vorschau, Zeitleiste mit Marken, Start/Ende "
                        "setzen, Ausschnitt als MP4 in den Ordner „Clips“ speichern.",
    "Drehen ↻": "Dreht die angezeigte Karte um 90° im Uhrzeigersinn (für jede Map gemerkt). Der Map-Name "
                "darüber bleibt aufrecht, die Zahlen in der Karte drehen sich mit.",
    "Scannen": "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen – falls die "
               "automatische Erkennung das Banner verpasst hat.",
    "Map wählen …": "Zur Seite Maps: eine Map von Hand anzeigen (Doppelklick oder „Anzeigen“). Beim nächsten "
                    "Match übernimmt die automatische Erkennung wieder.",
    "Bild hinzufügen …": "Eigenes Kartenbild für diese unbekannte Map anlegen – Name und Realm sind schon "
                         "eingetragen, der Hintergrund wird automatisch entfernt.",
    "Zuordnen …": "Der gelesene Name gehört zu einer vorhandenen Map (z. B. anders geschrieben)? Einmal "
                  "zuordnen – danach wird er automatisch erkannt.",
    "✕": "Hinweis ausblenden.",
    "Falsch erkannt": "Die erkannte Map stimmt nicht: Karte ausblenden, Timer zurücksetzen, die Runde wird nicht "
                      "gezählt. Geht auch im Spiel mit dem Hotkey (Standard Strg+Alt+X).",
    "Stimmt": "Die Map stimmt – Hinweis „unsicher“ ausblenden.",
    # maps tab
    "Server-Tab öffnen": "Zum Tab Server: dort „Anzeigen, mit welchem Server DBD verbunden ist“ anhaken – Region "
                         "und Ping stehen dann hier und im Overlay.",
    "Match-Daten einrichten …": "Zu Einstellungen → Mehr → Offizielle Match-Daten: einmal das Userscript in den "
                                "Browser, danach zählen Kills, Entkommen und Bloodpoints in der Statistik.",
    "Weitere 100 Runden anzeigen": "Die Liste zeigt die neuesten 100 Runden der Auswahl; jeder Klick hängt 100 "
                                   "ältere an.",
    "Als CSV exportieren …": "Speichert die Runden der aktuellen Filter als CSV (Semikolon, UTF-8) – mit Kills, "
                             "Entkommen und Bloodpoints, soweit ein Match der Stats-Seite zugeordnet ist.",
    "Alle Einstellungen zurücksetzen": "Setzt jede Einstellung auf die Auslieferung zurück (Overlay, Hotkeys, Erkennung, "
                                       "Server-Auswahl im Programm …). Runden, Match-Daten und eigene Bilder bleiben; "
                                       "das Programm startet danach neu. Vorher sichern: „Einstellungen exportieren“.",
    "Kartenbild hinzufügen …": "Eigenes Bild für eine Map wählen: vorhandenes Bild ersetzen oder neue Map "
                               "anlegen. Rand und Hintergrund werden automatisch entfernt.",
    # overlay tab
    "Für diese Map zurücksetzen": "Entfernt eigene Grösse und Drehung der angezeigten Map – danach gilt wieder "
                                  "der Schieberegler für alle Maps.",
    "Zurücksetzen": "Position wieder auf „automatisch“ stellen (auf Ultrawide im linken schwarzen Rand).",
    "Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)":
        "Auf breiten Monitoren bleibt die Karte im schwarzen Balken, in dem sie liegt, und wird bei Bedarf "
        "verkleinert. Mitten über dem Spiel platziert gilt keine Begrenzung.",
    "Karte anzeigen (aus: nur Timer, Ort und Ping)": "Aus: Das Overlay zeigt nur Rundentimer, Serverregion und Ping – "
                                                     "ohne Karte. Erkennung, Rundenende und Statistik laufen wie "
                                                     "gewohnt.",
    "Nur zeigen, wenn DBD das aktive Fenster ist": "Karte ausblenden, solange ein anderes Fenster "
                                                   "(Browser, Discord …) im Vordergrund ist.",
    "Map-Namen über der Karte anzeigen": "Zusätzliche Namenszeile über der Karte – die meisten Kartenbilder "
                                        "tragen den Namen schon selbst.",
    "Rundentimer unter der Karte anzeigen": "Zeit seit dem Einblenden der Karte, gross unter der Karte.",
    "Verbundenen Server unter der Karte anzeigen (Tab Server)":
        "Region und Ping des Spielservers unter der Karte. Braucht „Verbundener Spielserver“ im Tab Server.",
    "Transparenter Rand um die Karte": "Aus: Karte liegt auf einem dunklen Rechteck – besser lesbar über hellen "
                                       "Spielszenen.",
    # detection tab
    "Map beim Match-Start automatisch erkennen": "Liest das Map-Banner am Match-Anfang und blendet die "
                                                 "passende Karte ein. Aus: Map nur von Hand wählen.",
    "Overlay ausblenden, sobald ich nicht mehr in der Runde bin":
        "Blendet die Karte nach der Runde aus (Ergebnisbildschirm, Lobby, Ladebildschirm, DBD beendet).",
    "Overlay pausieren, solange ein DBD-Menü offen ist":
        "Karte verschwindet, solange der Mauszeiger im Spiel sichtbar ist (ESC-Menü), und kommt danach "
        "wieder.",
    "Auch erkennen, wenn andere Fenster über DBD liegen":
        "Fensteraufnahme wie bei OBS: erkennt das Banner auch, wenn DBD verdeckt ist. Nur solange DBD im "
        "Hintergrund ist.",
    "Debug-Bilder speichern (Ordner debug/)": "Speichert gelesene Banner und verkleinerte Bilder der Runde – "
                                              "nur zur Fehlersuche, kostet Speicherplatz.",
    "Bildschirm jetzt scannen": "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen.",
    "Diagnose kopieren": "Kopiert technische Infos (Fenster, Overlay, letzte Rundenende-Prüfungen) in die "
                         "Zwischenablage – zum Weitergeben bei Problemen.",
    # server tab
    "Anzeigen, mit welchem Server DBD verbunden ist":
        "Zeigt Region und Ping des Spielservers (liest nur Paketköpfe, nie Inhalte). Braucht "
        "Administratorrechte.",
    "Ping messen": "Misst den Ping zu allen AWS-Regionen (UDP-Beacon von Amazon GameLift).",
    "Auswahl anwenden": "Nur die angehakten Regionen erlauben – trägt die übrigen in die Windows-hosts-Datei "
                        "ein (fragt nach Administratorrechten).",
    "Alles freigeben": "Entfernt die Einträge des Programms aus der hosts-Datei – alle Regionen wieder "
                       "erlaubt.",
    # log tab
    "Leeren": "Log-Anzeige leeren (die Log-Datei bleibt).",
    "Log-Datei öffnen": "Öffnet dbdmapscout.log mit allen Details.",
    # settings tab
    "Dark Mode": "Dunkle oder helle Darstellung des Steuerfensters.",
    "Standard": "Alle Hotkeys auf die Voreinstellung zurücksetzen.",
    "Beim Minimieren in den Infobereich (neben der Uhr)":
        "Minimieren versteckt das Fenster im Infobereich; Doppelklick auf das Symbol holt es zurück.",
    "Mit Windows starten (im Infobereich, ohne Windows-Abfrage)":
        "Startet das Programm bei der Anmeldung im Infobereich. Nur als Administrator änderbar.",
    "Beim Start nach Updates suchen und installieren (GitHub)":
        "Holt beim Start über die Verknüpfung den neuen Stand von GitHub. Eigene Änderungen werden nie "
        "überschrieben.",
    "Jetzt nach Updates suchen": "Fragt GitHub, ob es eine neue Version gibt (nur bei diesem Klick). Installiert "
                                 "wird erst mit „Aktualisieren und neu starten“.",
    "Aktualisieren und neu starten": "Beendet das Programm und startet es über start.bat neu – dabei wird das "
                                     "Update installiert.",
    "Verlauf löschen": "Löscht alle gespeicherten Runden (Datei rounds.jsonl).",
    "Runde löschen": "Entfernt die markierte Runde aus der Statistik – z. B. eine Map, die mitten im Match falsch "
                     "erkannt wurde. Fragt vorher nach.",
    "Stats-Seite öffnen, wenn DBD beendet wird":
        "Schliesst du DBD nach mindestens einer Runde, öffnet das Programm stats.deadbydaylight.com im Browser. Das "
        "Userscript speichert dann die letzten 30 Matches, das Programm liest sie ein und löscht die Datei. Nie "
        "während DBD läuft.",
    "Userscript kopieren": "Kopiert das Userscript in die Zwischenablage. In Tampermonkey „Neues Skript erstellen“, "
                           "alles ersetzen und speichern. Es liest nur die Match-Liste, die die Seite selbst lädt – "
                           "keine Konto- oder Login-Daten – und schickt nichts irgendwohin.",
    "Meldung, wenn Match-Daten eingelesen und gelöscht wurden":
        "Zeigt unten rechts kurz, wie viele Matches gelesen wurden und dass die Datei gelöscht ist – nicht, solange "
        "DBD im Vordergrund ist. Im Log steht es immer.",
    "Stats-Seite öffnen": "Öffnet stats.deadbydaylight.com jetzt. Mit installiertem Userscript kommen die Matches "
                          "gleich danach an.",
    "Alle löschen": "Alle eigenen Map-Zuordnungen löschen (die Namen werden dann wieder als unbekannt "
                    "gemeldet).",
    "Programmordner öffnen": "Öffnet den Ordner des Programms im Explorer.",
    "Karten-Ordner öffnen": "Öffnet den Ordner mit den mitgelieferten Kartenbildern.",
    # dialogs
    "Bild wählen …": "PNG, JPG, WebP oder GIF auswählen – zum Beispiel ein Original mit Hintergrund.",
    "Bild einer vorhandenen Map ersetzen": "Dein Bild ersetzt das mitgelieferte Bild dieser Map (bzw. dieses "
                                           "Layouts). Löschen stellt das Original wieder her.",
    "Neue Map (fehlt im Programm)": "Legt eine neue Map an. Sie wird erkannt, wenn der Name so geschrieben ist "
                                    "wie im Map-Banner.",
    "Ordner öffnen": "Öffnet den Ordner user_maps mit deinen eigenen Kartenbildern.",
    "Eigenes Bild löschen": "Löscht dein Bild für die gewählte Map – danach gilt wieder das mitgelieferte.",
    "Speichern": "Bild umwandeln und speichern; die Karte wird sofort angezeigt.",
    "Abbrechen": "Schliessen, ohne etwas zu ändern.",
}
_PREFIX = [("Hintergrund entfernen", "Macht Dunkelblau (#282a42) und Graulila (#535781) der "
            "Community-Karten transparent, schneidet den gleichfarbigen Rand ab und bringt das Bild auf "
            "1280 px Höhe.")]


def tip_for_label(text: str):
    """Info text for a (translated) label – the table is keyed by the German label."""
    key = source(text)
    if key in TIPS:
        return _(TIPS[key])
    for prefix, tip in _PREFIX:
        if key.startswith(prefix):
            return _(tip)
    return None


def _resolver(text):
    """The text now: tooltips of buttons whose label changes are callables."""
    return lambda: (text() if callable(text) else text) or ""


TIPPABLE = (ui.Button, ui.Checkbutton, ui.Radiobutton)


def attach_all(root, lookup=None):
    """Tooltip for every button/checkbox below ``root`` that has none yet.
    ``lookup(widget)`` may return a text/callable for widgets not covered by the label table."""
    count = 0
    stack = [root]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if not isinstance(w, TIPPABLE) or getattr(w, "_dbdms_tip", None):
            continue
        text = lookup(w) if lookup else None
        if text is None:
            text = tip_for_label(str(w.cget("text")))
        if text:
            w._dbdms_tip = _resolver(text)
            count += 1
    return count


def missing(root):
    """Buttons/checkboxes without a tooltip (labels) – used by the test to keep the table complete."""
    out, stack = [], [root]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if isinstance(w, TIPPABLE) and not getattr(w, "_dbdms_tip", None):
            out.append(str(w.cget("text")))
    return out
