"""English texts: German original (the key in the code) -> English.

Placeholders ({map}, {error}, …) must stay the same – tests/test_i18n.py checks that every
text in the code is here and that the placeholders match.
"""

EN = {
    # ------------------------------------------------------------------ start
    "DbD Map Scout läuft bereits.": "DbD Map Scout is already running.",
    "Start fehlgeschlagen:": "Start failed:",
    "Starte …": "Starting …",
    "Kein Windows: Fenstersuche, Hotkeys und Click-Through sind nur unter Windows aktiv.":
        "Not Windows: window search, hotkeys and click-through only work on Windows.",
    "Bereit. {n} Maps geladen, Spielsprachen: {langs}.": "Ready. {n} maps loaded, game languages: {langs}.",
    "Automatisch (Windows-Sprache)": "Automatic (Windows language)",

    # ------------------------------------------------------------------ lists / keys
    "Erkennung": "Detection",
    "Overlay": "Overlay",
    "System": "System",
    "Fehler": "Error",
    "automatisch": "automatic",
    "oben links": "top left",
    "oben rechts": "top right",
    "unten links": "bottom left",
    "unten rechts": "bottom right",
    "eigene Position": "custom position",
    "Overlay ein/aus": "Overlay on/off",
    "Layout-Variante": "Layout variant",
    "Bildschirm scannen": "Scan screen",
    "Vorherige Map": "Previous map",
    "Nächste Map": "Next map",
    "Grösser": "Bigger",
    "Kleiner": "Smaller",
    "Mit Maus verschieben": "Move with mouse",

    # ------------------------------------------------------------------ main window
    "Noch keine Map": "No map yet",
    "Wird beim Match-Start automatisch erkannt.": "Detected automatically when a match starts.",
    "Overlay ausblenden": "Hide overlay",
    "Overlay einblenden": "Show overlay",
    "Scannen": "Scan",
    "Overlay testen": "Test overlay",
    "Test beenden": "End test",
    "Bild hinzufügen …": "Add picture …",
    "Zuordnen …": "Assign …",
    "Server": "Server",
    "Einstellungen": "Settings",
    "Layout {n} von {total}": "Layout {n} of {total}",
    "(unsicher)": "(unsure)",
    "manuell gewählt": "chosen by hand",
    "per Scan gefunden": "found by scan",
    "Runde läuft: {time}": "Round running: {time}",
    "Letzte Runde: {time}": "Last round: {time}",
    "Unbekannte Map gelesen: „{text}“": "Unknown map read: “{text}”",

    # ------------------------------------------------------------------ status line
    "Im Menü – Karte pausiert ({map})": "In a menu – map paused ({map})",
    "Runde vorbei – wartet auf das nächste Match": "Round over – waiting for the next match",
    "Karte ausgeblendet ({map})": "Map hidden ({map})",
    "Wartet auf DBD": "Waiting for DBD",
    "DBD läuft – automatische Erkennung ist aus (Map von Hand wählen)":
        "DBD is running – automatic detection is off (choose the map by hand)",
    "Wartet auf das nächste Match": "Waiting for the next match",
    "Simulation – wartet auf das Map-Banner": "Simulation – waiting for the map banner",
    "Im Match: {map}": "In match: {map}",
    "Karte eingeblendet": "Map shown",

    # ------------------------------------------------------------------ tab maps
    "Suche": "Search",
    "Doppelklick zeigt die Map. Die Erkennung übernimmt beim nächsten Match wieder.":
        "Double-click shows the map. Detection takes over again at the next match.",
    "Kartenbild hinzufügen …": "Add map picture …",
    "eigenes Bild für eine Map (Hintergrund wird entfernt)": "your own picture for a map (background is removed)",
    "Eigene Bilder": "Own pictures",

    # ------------------------------------------------------------------ tab overlay
    "Position": "Position",
    "Vorgabe": "Preset",
    "Zurücksetzen": "Reset",
    "Horizontal": "Horizontal",
    "Vertikal": "Vertical",
    "Mit der Maus verschieben": "Move with the mouse",
    "Fertig": "Done",
    "0 % = links/oben, 100 % = rechts/unten": "0 % = left/top, 100 % = right/bottom",
    "Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)":
        "Keep the map in the black bar (ultrawide: never over the game picture)",
    "Darstellung": "Appearance",
    "Grösse": "Size",
    "Karte anzeigen (aus: nur Timer, Ort und Ping)": "Show the map (off: only timer, location and ping)",
    "Karte im Overlay eingeblendet.": "Map shown in the overlay.",
    "Karte im Overlay aus – es werden nur Timer, Ort und Ping angezeigt.":
        "Map in the overlay off – only timer, location and ping are shown.",
    "nichts anzuzeigen": "nothing to show",
    "Aus: Das Overlay zeigt nur Rundentimer, Serverregion und Ping – ohne Karte. Erkennung, Rundenende und "
    "Statistik laufen wie gewohnt.":
        "Off: the overlay shows only the round timer, server region and ping – without the map. Detection, end of "
        "round and statistics work as usual.",
    "Für diese Map zurücksetzen": "Reset for this map",
    "eigene Grösse {n} % (Hotkeys/Mausrad)": "own size {n} % (hotkeys/mouse wheel)",
    "gedreht um {deg}°": "turned by {deg}°",
    # lobby: search, waiting time, role
    "Killer": "Killer",
    "Survivor": "Survivor",
    "Rolle": "Role",
    "Rolle: {role}": "Role: {role}",
    "Alle Rollen": "All roles",
    "Custom Game": "Custom game",
    "Custom Games": "Custom games",
    "Custom Game – keine Wartezeit.": "Custom game – no waiting time.",
    "Suche läuft: {time}": "Searching: {time}",
    "Suche nach einem Match gestartet.": "Started searching for a match.",
    "Suche abgebrochen.": "Search cancelled.",
    "Lobby gefunden nach {time}{role}.": "Lobby found after {time}{role}.",
    "Lobby gefunden{role}.": "Lobby found{role}.",
    "Wartezeit {time}": "waited {time}",
    "Ergebnisbildschirm: gespielt als {role}.": "Results screen: played as {role}.",
    "Wartezeit in der Lobby": "Waiting time in the lobby",
    "Rolle der markierten Runde:": "Role of the selected round:",
    "Benachrichtigungen": "Notifications",
    "⚠ Nicht gezählt: {n} × Rundenende nicht erkannt (die nächste Map kam, bevor das Ende erkannt wurde). "
    "Zuletzt: {map}, {when}.":
        "⚠ Not counted: {n} × end of round not detected (the next map came before the end was detected). "
        "Last: {map}, {when}.",
    "Runde auf {map} nicht gezählt: ihr Ende wurde nicht erkannt.":
        "Round on {map} not counted: its end was not detected.",
    "Sicherung": "Backup",
    "Einstellungen exportieren …": "Export settings …",
    "Einstellungen importieren …": "Import settings …",
    "Einstellungen exportieren": "Export settings",
    "Einstellungen importieren": "Import settings",
    "Export fehlgeschlagen: {error}": "Export failed: {error}",
    "Einstellungen gesichert: {path}": "Settings saved: {path}",
    "Das ist keine Einstellungsdatei von DbD Map Scout ({error}).":
        "This is not a DbD Map Scout settings file ({error}).",
    "Alle Einstellungen durch die aus der Datei ersetzen? Das Programm startet danach neu.":
        "Replace all settings with the ones from the file? The program restarts afterwards.",
    "Einstellungen importiert aus {path}.": "Settings imported from {path}.",
    "Bitte das Programm jetzt neu starten.": "Please restart the program now.",
    "Speichert alle Einstellungen in eine Datei: Hotkeys, Grösse und Drehung pro Map, eigene Map-Zuordnungen, "
    "Overlay, Regionen … Die Statistik (rounds.jsonl) gehört nicht dazu.":
        "Saves all settings to a file: hotkeys, size and rotation per map, own map assignments, overlay, "
        "regions … The statistics (rounds.jsonl) are not part of it.",
    "Lädt eine exportierte Einstellungsdatei und startet das Programm neu. Fehlende Werte (ältere Sicherung) "
    "bekommen ihren Standard.":
        "Loads an exported settings file and restarts the program. Missing values (older backup) get their "
        "default.",
    "Ton und Meldung, wenn eine Lobby gefunden wurde": "Sound and notification when a lobby was found",
    "Erinnern, wenn der Lobby-Countdown abläuft und READY noch nicht gedrückt ist":
        "Remind me when the lobby countdown runs out and READY is not pressed yet",
    "Nur wenn DBD nicht das aktive Fenster ist": "Only when DBD is not the active window",
    "Die Meldung erscheint unten rechts über allen Fenstern – auch bei „Nicht stören“ – und nimmt dem aktiven "
    "Fenster nicht den Fokus. Klick darauf schliesst sie.":
        "The notification appears bottom right above all windows – also with \"Do not disturb\" – and does not "
        "take the focus from the active window. Click it to close it.",
    "Meldung testen": "Test notification",
    "Zeigt die Meldung und spielt den Ton – so siehst du, wo sie erscheint.":
        "Shows the notification and plays the sound – so you see where it appears.",
    "Lobby gefunden": "Lobby found",
    "nach {time}": "after {time}",
    "READY drücken.": "Press READY.",
    "Lobby startet gleich": "Lobby starts soon",
    "Noch {n} s – READY ist noch nicht gedrückt.": "{n} s left – READY is not pressed yet.",
    "Lobby-Countdown läuft ab, READY ist noch nicht gedrückt.": "Lobby countdown is running out, READY is not pressed.",
    "Ø Ping": "Ø ping",
    "Spielt einen Hinweiston und zeigt eine Windows-Meldung, sobald DBD eine Lobby gefunden hat – praktisch, wenn "
    "du während der Suche etwas anderes machst.":
        "Plays a sound and shows a Windows notification as soon as DBD has found a lobby – handy if you do something "
        "else while searching.",
    "Noch einmal melden, wenn der Countdown der Lobby unter 15 s fällt und du READY nicht gedrückt hast.":
        "Notify again when the lobby countdown drops below 15 s and you have not pressed READY.",
    "Keine Meldung, solange DBD im Vordergrund ist – dann siehst du die Lobby ja selbst.":
        "No notification while DBD is in front – then you see the lobby yourself.",
    "Rolle für {map} ({when}) auf {role} geändert.": "Role for {map} ({when}) changed to {role}.",
    "Rolle konnte nicht gespeichert werden: {error}": "Could not save the role: {error}",
    "Diese Runde als Killer-Runde zählen (falls die Erkennung falsch lag).":
        "Count this round as a killer round (if the detection was wrong).",
    "Diese Runde als Survivor-Runde zählen (falls die Erkennung falsch lag).":
        "Count this round as a survivor round (if the detection was wrong).",
    "Diese Runde als Custom Game zählen – sie fliesst dann nicht in die Wartezeit ein.":
        "Count this round as a custom game – it is then left out of the waiting time.",
    "Ø {avg} · Median {median} · kürzeste {min} · längste {max} ({n} Runden)":
        "Ø {avg} · median {median} · shortest {min} · longest {max} ({n} rounds)",
    "Noch keine Wartezeiten in dieser Auswahl.": "No waiting times in this selection yet.",
    "nach Wochentag": "by weekday",
    "nach Uhrzeit": "by time of day",
    "nach Region": "by region",
    "Wann/Wo": "When/where",
    "Ø Wartezeit": "Ø wait",
    "Kürzeste": "Shortest",
    "Warten": "Wait",
    "Uhr": "h",
    "Montag": "Monday",
    "Dienstag": "Tuesday",
    "Mittwoch": "Wednesday",
    "Donnerstag": "Thursday",
    "Freitag": "Friday",
    "Samstag": "Saturday",
    "Sonntag": "Sunday",
    "Gemessen von „CANCEL“ (Suche läuft) bis zur gefundenen Lobby – nur wenn das Programm die Suche gesehen hat. "
    "Custom Games haben keine Wartezeit.":
        "Measured from \"CANCEL\" (searching) until the lobby is found – only if the program saw the search. "
        "Custom games have no waiting time.",
    "Map-Namen oben einfügen (wie bei den mitgelieferten Karten)":
        "Put the map name on top (like the supplied maps)",
    "Das Bild hat oben schon einen Namen – es wird keiner hinzugefügt.":
        "The picture already has a name on top – none is added.",
    "Schreibt den Map-Namen weiss mit Schatten über die Karte, im Stil der mitgelieferten Karten. Hat das Bild "
    "oben schon einen Namen, passiert nichts. Beim Drehen bleibt der Name aufrecht.":
        "Writes the map name in white with a shadow above the map, in the style of the supplied maps. If the "
        "picture already has a name on top, nothing happens. The name stays upright when the map is rotated.",
    "Drehen ↻": "Rotate ↻",
    "Karte drehen": "Rotate map",
    "{map} um {deg}° gedreht.": "{map} turned by {deg}°.",
    "Drehung für {map} entfernt.": "Rotation for {map} removed.",
    "Dreht die angezeigte Karte um 90° im Uhrzeigersinn (für jede Map gemerkt). Der Map-Name darüber bleibt "
    "aufrecht, die Zahlen in der Karte drehen sich mit.":
        "Turns the map on display by 90° clockwise (remembered for each map). The map name above it stays "
        "upright, the numbers inside the map turn with it.",
    "Eigene Grösse für {map} entfernt – es gilt wieder der Schieberegler.":
        "Own size for {map} removed – the slider applies again.",
    "Entfernt eigene Grösse und Drehung der angezeigten Map – danach gilt wieder der Schieberegler für alle "
    "Maps.":
        "Removes the own size and rotation of the map on display – the slider for all maps applies again.",
    "Deckkraft": "Opacity",
    "Nur zeigen, wenn DBD das aktive Fenster ist": "Only show while DBD is the active window",
    "Map-Namen über der Karte anzeigen": "Show the map name above the map",
    "Rundentimer unter der Karte anzeigen": "Show the round timer below the map",
    "Verbundenen Server unter der Karte anzeigen (Tab Server)": "Show the connected server below the map (Server tab)",
    "Transparenter Rand um die Karte": "Transparent edge around the map",

    # ------------------------------------------------------------------ tab detection
    "Automatik": "Automatic",
    "Map beim Match-Start automatisch erkennen": "Detect the map automatically when a match starts",
    "Overlay ausblenden, sobald ich nicht mehr in der Runde bin": "Hide the overlay as soon as I am out of the round",
    "erkennt Ergebnisbildschirm, Lobby/Menüs, Ladebildschirm und geschlossenes DBD":
        "detects the results screen, lobby/menus, loading screen and DBD being closed",
    "Overlay pausieren, solange ein DBD-Menü offen ist": "Pause the overlay while a DBD menu is open",
    "erkannt am sichtbaren Mauszeiger (ESC-Menü, Ergebnisbildschirm, Lobby)":
        "detected by the visible mouse pointer (ESC menu, results screen, lobby)",
    "Spielsprache (Map-Namen)": "Game language (map names)",
    "Erweitert": "Advanced",
    "Erweitert (Fehlersuche, Technik)": "Advanced (troubleshooting, technical)",
    "Auch erkennen, wenn andere Fenster über DBD liegen": "Also detect when other windows cover DBD",
    "Fensteraufnahme wie bei OBS, nur solange DBD im Hintergrund ist":
        "window capture like OBS, only while DBD is in the background",
    "Scans/Sek.": "Scans/sec.",
    "Rundenende-Erkennung: {state}": "End-of-round detection: {state}",
    "Debug-Bilder speichern (Ordner debug/)": "Save debug pictures (folder debug/)",
    "Bildschirm jetzt scannen": "Scan the screen now",
    "Diagnose kopieren": "Copy diagnostics",

    # ------------------------------------------------------------------ tab server
    "Verbundener Spielserver": "Connected game server",
    "Anzeigen, mit welchem Server DBD verbunden ist": "Show which server DBD is connected to",
    "Serverregionen": "Server regions",
    "DBD sucht Matches nur in den angehakten Regionen (über die Windows-hosts-Datei, das Spiel wird nicht "
    "verändert). Nach „Auswahl anwenden“ DBD neu starten.":
        "DBD only searches for matches in the ticked regions (through the Windows hosts file, the game is not "
        "changed). Restart DBD after “Apply selection”.",
    "Region": "Region",
    "hosts-Datei": "hosts file",
    "Ping messen": "Measure ping",
    "Auswahl anwenden": "Apply selection",
    "Alles freigeben": "Allow all",
    "Mit VPN unzuverlässig. Region-Tools sind von BHVR weder erlaubt noch verboten – auf eigene Verantwortung.":
        "Unreliable with a VPN. Region tools are neither allowed nor forbidden by BHVR – at your own risk.",
    "Warte auf Windows (Administratorrechte) …": "Waiting for Windows (administrator rights) …",
    "Aus": "Off",
    "Zeigt Region und Ping des Spielservers, auch im Overlay (braucht Administratorrechte).":
        "Shows region and ping of the game server, also in the overlay (needs administrator rights).",
    "Automatisch: im schwarzen Rand neben dem Spielbild. Regler bewegen = eigene Position.":
        "Automatic: in the black border next to the game picture. Moving a slider = own position.",
    "Regler bewegen = eigene Position.": "Moving a slider = own position.",
    "Mehr (Map-Zuordnungen, Sicherung, Ordner)": "More (map assignments, backup, folders)",
    "Selten gebrauchte Einstellungen ein- oder ausklappen.": "Show or hide rarely used settings.",
    "Verbunden mit: {server}": "Connected to: {server}",
    "pausiert, bis DBD läuft": "paused until DBD runs",
    "Anzeige des Spielservers beendet.": "Game server display stopped.",
    "Spielserver-Anzeige: {error}": "Game server display: {error}",
    "Spielserver-Anzeige läuft (liest nur Paketköpfe, keine Inhalte).":
        "Game server display running (reads packet headers only, no contents).",
    "Spielserver-Anzeige pausiert – DBD läuft nicht (startet automatisch mit DBD).":
        "Game server display paused – DBD is not running (starts again with DBD).",
    "Spielserver-Anzeige beendet: {error}": "Game server display stopped: {error}",
    " – nicht in deiner Regionsauswahl": " – not in your region selection",
    "Verbunden mit Spielserver: {region}{note}.": "Connected to game server: {region}{note}.",
    "hosts-Datei nicht lesbar: {error}": "hosts file not readable: {error}",
    "Aktiv: nur {regions} erlaubt.": "Active: only {regions} allowed.",
    "(keine)": "(none)",
    "Keine eigene Auswahl aktiv, aber andere Einträge sperren Regionen.":
        "No own selection active, but other entries block regions.",
    "Keine Region gesperrt – DBD wählt selbst.": "No region blocked – DBD chooses by itself.",
    "anderen Programmen": "other programs",
    " Es gibt {n} Einträge von {who} für DBD-Server (werden beim Anwenden ersetzt).":
        " There are {n} entries from {who} for DBD servers (replaced when applying).",
    "Serverregionen: {text}": "Server regions: {text}",
    "Messe Ping zu den Serverregionen …": "Measuring ping to the server regions …",
    "Ping fehlgeschlagen: {error}": "Ping failed: {error}",
    "Am schnellsten: {list}.": "Fastest: {list}.",
    "Keine Region hat geantwortet (Internet/Firewall/VPN?).": "No region answered (internet/firewall/VPN?).",
    "Bitte mindestens eine Region anhaken.": "Please tick at least one region.",
    "Erlaubt bleiben: {names}.\n\nAlle anderen DBD-Serverregionen werden in der Windows-hosts-Datei gesperrt. "
    "Windows fragt gleich nach Administratorrechten.":
        "Allowed: {names}.\n\nAll other DBD server regions are blocked in the Windows hosts file. "
        "Windows will ask for administrator rights.",
    "{n} vorhandene Einträge anderer Programme (z. B. Make Your Choice) für DBD-Server werden dabei entfernt.":
        "{n} existing entries of other programs (e.g. Make Your Choice) for DBD servers will be removed.",
    "Danach DBD neu starten, damit es wirkt.": "Then restart DBD for it to take effect.",
    "Serverregionen anwenden": "Apply server regions",
    "Nur noch {names} erlaubt": "Only {names} allowed",
    "Es ist nichts gesperrt.": "Nothing is blocked.",
    "Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen (auch die von Make Your Choice)?":
        "Remove all blocks of DBD server regions from the hosts file (including those of Make Your Choice)?",
    "Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen?":
        "Remove all blocks of DBD server regions from the hosts file?",
    "Windows fragt gleich nach Administratorrechten. Danach DBD neu starten.":
        "Windows will ask for administrator rights. Then restart DBD.",
    "Serverregionen freigeben": "Allow server regions",
    "Alle Regionen freigegeben": "All regions allowed",
    "Serverregionen: {text}. DBD neu starten, damit es wirkt.": "Server regions: {text}. Restart DBD for it to take effect.",
    "{text}. DBD jetzt neu starten.": "{text}. Restart DBD now.",
    "Keine Änderung nötig.": "No change needed.",
    "unbekannter Fehler": "unknown error",
    "Firewall-Regeln von Make Your Choice („Enforced“) gefunden – sie sperren Regionen unabhängig von der "
    "hosts-Datei. In Make Your Choice „Revert to Default“ drücken.":
        "Firewall rules of Make Your Choice (“Enforced”) found – they block regions regardless of the hosts file. "
        "Press “Revert to Default” in Make Your Choice.",
    "Achtung: Firewall-Regeln von Make Your Choice aktiv (siehe Log).":
        "Attention: firewall rules of Make Your Choice are active (see log).",
    # regions (names, groups, hosts state)
    "Europa": "Europe",
    "Amerika": "Americas",
    "Asien": "Asia",
    "Ozeanien": "Oceania",
    "frei": "allowed",
    "gesperrt": "blocked",
    "gesperrt (fremd)": "blocked (other program)",
    "umgeleitet (fremd)": "redirected (other program)",
    "Frankfurt": "Frankfurt",
    "Irland": "Ireland",
    "London": "London",
    "USA Ost (N. Virginia)": "US East (N. Virginia)",
    "USA Ost (Ohio)": "US East (Ohio)",
    "USA West (N. Kalifornien)": "US West (N. California)",
    "USA West (Oregon)": "US West (Oregon)",
    "Kanada (Zentral)": "Canada (Central)",
    "Südamerika (São Paulo)": "South America (São Paulo)",
    "Tokio": "Tokyo",
    "Seoul": "Seoul",
    "Mumbai": "Mumbai",
    "Singapur": "Singapore",
    "Hongkong": "Hong Kong",
    "Sydney": "Sydney",
    "Name nicht auflösbar": "name cannot be resolved",
    "Start mit Administratorrechten fehlgeschlagen (Fehler {code}).": "Start with administrator rights failed (error {code}).",
    "Hilfsprogramm nicht gestartet.": "Helper program not started.",
    "Das Hilfsprogramm hat kein Ergebnis geliefert (Code {code}).": "The helper program returned no result (code {code}).",
    "Zeitüberschreitung beim Schreiben der hosts-Datei.": "Timeout while writing the hosts file.",
    "Abgebrochen (keine Administratorrechte erteilt).": "Cancelled (no administrator rights granted).",
    # connection watch
    "Warte auf Match …": "Waiting for a match …",
    "keine Daten vom Mitschnitt": "no data from the capture",
    "Nur unter Windows verfügbar.": "Only available on Windows.",
    "Mitschnitt beendet (Code {code}).": "Capture ended (code {code}).",
    "Fehler: {error}": "Error: {error}",

    # ------------------------------------------------------------------ tab statistics
    "Statistik": "Statistics",
    "Gezählt werden Runden mit automatisch erkannter Map, vom Map-Banner bis zum erkannten Rundenende (mindestens "
    "1 Minute). Gespeichert nur lokal in rounds.jsonl.":
        "Counted are rounds with an automatically detected map, from the map banner to the detected end of the "
        "round (at least 1 minute). Stored only locally in rounds.jsonl.",
    "Maps": "Maps",
    "Map": "Map",
    "Runden": "Rounds",
    "Ø Dauer": "Avg. length",
    "Längste": "Longest",
    "Letzte Runden": "Last rounds",
    "Gesamter Zeitraum": "All time",
    "Heute": "Today",
    "Diese Woche": "This week",
    "Dieser Monat": "This month",
    "Dieses Jahr": "This year",
    "Alle Regionen": "All regions",
    "Alle Killer": "All killers",
    "Häufigste Map": "Most frequent map",
    "Name unter dem Lobby-Knopf, nur wenn du Killer spielst. Manche Skins zeigen dort ihren eigenen Namen – dann Zeile "
    "markieren und dem Killer zuordnen (gilt auch rückwirkend). Killer auswählen (oben) zeigt Maps und Dauer nur für "
    "ihn.":
        "Name below the lobby button, only when you play killer. Some skins show their own name there – then select "
        "the row and assign it to the killer (also applies to past rounds). Picking a killer (above) shows maps and "
        "durations for that killer only.",
    "Der markierte Name (Skin oder neuer Killer) zählt ab jetzt als der gewählte Killer – auch in allen bisherigen "
    "Runden.": "The selected name (skin or new killer) counts as the chosen killer from now on – in all past rounds "
               "too.",
    "Entfernt alle eigenen Killer-Zuordnungen; die Namen erscheinen wieder so, wie sie gelesen wurden.":
        "Removes all own killer assignments; the names show up again as they were read.",
    "Zuordnen": "Assign",
    "Verstanden": "Got it",
    "Hinweis schliessen – er erscheint nicht wieder.": "Close the hint – it will not come back.",
    "So geht's: DBD starten und spielen – die Karte erscheint beim Match-Start von selbst und verschwindet nach der "
    "Runde. Hotkeys: {toggle} ein/aus, {rotate} drehen, {edit} verschieben (ändern unter Einstellungen).":
        "How it works: start DBD and play – the map appears by itself when the match starts and disappears after "
        "the round. Hotkeys: {toggle} on/off, {rotate} rotate, {edit} move (change them under Settings).",
    "Killer der markierten Runde:": "Killer of the selected round:",
    "Killer setzen": "Set killer",
    "Killer konnte nicht gespeichert werden: {error}": "Could not save the killer: {error}",
    "Killer für {map} ({when}) auf {killer} gesetzt.": "Killer for {map} ({when}) set to {killer}.",
    "Setzt den Killer nur für die markierte Runde und zählt sie als Killer-Runde – z. B. wenn sie fälschlich als "
    "Survivor gezählt wurde oder der Name falsch gelesen wurde.":
        "Sets the killer for the selected round only and counts it as a killer round – e.g. if it was wrongly counted "
        "as survivor or the name was misread.",
    "Zuordnungen löschen": "Delete assignments",
    "„{name}“ zählt jetzt als {killer}.": "\"{name}\" now counts as {killer}.",
    "Alle eigenen Killer-Zuordnungen löschen?": "Delete all own killer assignments?",
    "Killer-Zuordnungen gelöscht.": "Killer assignments deleted.",
    "ohne Region": "no region",
    "Anteil": "Share",
    "Region nur bekannt, wenn im Tab Server „Verbundener Spielserver“ an war.":
        "Region only known if “Connected game server” was on in the Server tab.",
    "Keine Runden in dieser Auswahl.": "No rounds in this selection.",
    "Wann": "When",
    "Dauer": "Length",
    "Verlauf löschen": "Delete history",
    "Noch keine Runden gespeichert.": "No rounds saved yet.",
    "{n} Runden · Ø {avg} · gesamt {total}": "{n} rounds · avg. {avg} · total {total}",
    "Alle gespeicherten Runden löschen?": "Delete all saved rounds?",
    "Rundenverlauf gelöscht.": "Round history deleted.",
    "Löscht alle gespeicherten Runden (Datei rounds.jsonl).": "Deletes all saved rounds (file rounds.jsonl).",

    # ------------------------------------------------------------------ tab log
    "Anzeigen:": "Show:",
    "Leeren": "Clear",
    "Log-Datei öffnen": "Open log file",

    # ------------------------------------------------------------------ tab settings
    "Sprache und Darstellung": "Language and appearance",
    "Wirkt nach dem nächsten Start des Programms.": "Takes effect the next time the program starts.",
    "Sprache geändert – wirkt nach dem nächsten Start des Programms.":
        "Language changed – takes effect the next time the program starts.",
    "Dark Mode": "Dark mode",
    "Hotkeys": "Hotkeys",
    "Standard": "Defaults",
    "Zum Ändern anklicken und die neue Tastenkombination drücken.": "Click to change, then press the new key combination.",
    "Start und Infobereich": "Start and notification area",
    "Beim Minimieren in den Infobereich (neben der Uhr)": "Minimise to the notification area (next to the clock)",
    "Mit Windows starten (im Infobereich, ohne Windows-Abfrage)":
        "Start with Windows (in the notification area, without a Windows prompt)",
    "Updates": "Updates",
    "Beim Start nach Updates suchen und installieren (GitHub)": "Check for updates at start and install them (GitHub)",
    "nur über start.bat bzw. die Desktop-Verknüpfung; eigene Änderungen werden nie überschrieben":
        "only via start.bat or the desktop shortcut; your own changes are never overwritten",
    "Eigene Map-Zuordnungen": "Own map assignments",
    "Jetzt nach Updates suchen": "Check for updates now",
    "Aktualisieren und neu starten": "Update and restart",
    "Suche nach Updates …": "Checking for updates …",
    "Neustart nicht möglich: {error}": "Restart not possible: {error}",
    "Nur unter Windows: bitte das Programm über start.bat neu starten.": "Windows only: please restart the program via start.bat.",
    "Programm startet neu und installiert das Update …": "The program restarts and installs the update …",
    "Fragt GitHub, ob es eine neue Version gibt (nur bei diesem Klick). Installiert wird erst mit „Aktualisieren "
    "und neu starten“.":
        "Asks GitHub whether there is a new version (only on this click). It is installed only with “Update and "
        "restart”.",
    "Beendet das Programm und startet es über start.bat neu – dabei wird das Update installiert.":
        "Closes the program and starts it again via start.bat – the update is installed on the way.",
    "Alle löschen": "Delete all",
    "Ordner": "Folders",
    "Programmordner öffnen": "Open program folder",
    "Karten-Ordner öffnen": "Open maps folder",
    "liest nur Bildschirmpixel, sendet keine Eingaben ans Spiel.": "reads screen pixels only, sends no input to the game.",
    "Keine. Unbekannte Map-Namen lassen sich nach dem Match im Hauptfenster zuordnen.":
        "None. Unknown map names can be assigned in the main window after the match.",
    "Eigene Zuordnungen": "Own assignments",
    "Alle eigenen Map-Zuordnungen löschen?": "Delete all own map assignments?",
    "Eigene Map-Zuordnungen gelöscht.": "Own map assignments deleted.",
    "Spielsprachen: {langs}": "Game languages: {langs}",
    "Änderbar, wenn das Programm über die Desktop-Verknüpfung gestartet wurde (verknuepfung_erstellen.bat "
    "einmal ausführen).":
        "Can be changed when the program was started through the desktop shortcut (run "
        "verknuepfung_erstellen.bat once).",
    "Wird eingerichtet …": "Setting up …",
    "Startet ab jetzt mit Windows im Infobereich.": "From now on starts with Windows in the notification area.",
    "Startet nicht mehr mit Windows.": "No longer starts with Windows.",
    "Fehlgeschlagen: {error}": "Failed: {error}",
    "Nur unter Windows.": "Windows only.",
    "Tipp: Einmal als Administrator starten (Rechtsklick auf start.bat → „Als Administrator ausführen“) – dann "
    "richtet das Programm die Desktop-Verknüpfung ein, die künftig ohne Windows-Abfrage startet.":
        "Tip: start once as administrator (right-click start.bat → “Run as administrator”) – the program then sets "
        "up the desktop shortcut, which starts it without a Windows prompt from then on.",
    "Desktop-Verknüpfung eingerichtet/aktualisiert: startet ab jetzt ohne Windows-Abfrage.":
        "Desktop shortcut set up/updated: starts without a Windows prompt from now on.",
    "Einrichtung der Verknüpfung fehlgeschlagen: {error}": "Setting up the shortcut failed: {error}",
    "Verknüpfung erstellt: {path}": "Shortcut created: {path}",
    "Aufgabe konnte nicht angelegt werden: {error}": "The scheduled task could not be created: {error}",
    "Verknüpfung konnte nicht angelegt werden: {error}": "The shortcut could not be created: {error}",
    "(Autostart nicht erneuert: {error})": "(autostart not renewed: {error})",
    "Symbol im Infobereich nicht verfügbar ({error}) – Minimieren wie gewohnt.":
        "Notification area icon not available ({error}) – minimising works as usual.",
    "Öffnen nur unter Windows: {path}": "Opening only works on Windows: {path}",
    "Kann {path} nicht öffnen: {error}": "Cannot open {path}: {error}",
    "Fenster öffnen": "Open window",
    "Beenden": "Quit",

    # ------------------------------------------------------------------ hotkeys
    "Hotkey: {keys}": "Hotkey: {keys}",
    "Hotkey {keys} ({action}) nicht verfügbar: {why}.": "Hotkey {keys} ({action}) not available: {why}.",
    "{n} Hotkey(s) nicht verfügbar – siehe Log.": "{n} hotkey(s) not available – see log.",
    "– aus –": "– off –",
    "Tasten drücken …": "Press keys …",
    "Neue Kombination drücken – Esc bricht ab, Entf schaltet den Hotkey aus.":
        "Press the new combination – Esc cancels, Delete switches the hotkey off.",
    "{keys} ist schon „{action}“ – andere wählen.": "{keys} is already “{action}” – choose another one.",
    "aus": "off",
    "Hotkey {action}: {keys}.": "Hotkey {action}: {keys}.",
    "Standard-Hotkeys wiederhergestellt.": "Default hotkeys restored.",
    "Strg": "Ctrl",
    "Taste „{key}“ geht nicht als Hotkey": "Key “{key}” cannot be used as a hotkey",
    "Bitte mit Strg und/oder Alt kombinieren": "Please combine with Ctrl and/or Alt",
    "schon von einem anderen Programm belegt": "already used by another program",

    # ------------------------------------------------------------------ overlay / map actions
    "Für „{map}“ gibt es kein Bild.": "There is no picture for “{map}”.",
    "Bild konnte nicht geladen werden: {path} ({error})": "Picture could not be loaded: {path} ({error})",
    "Map gewählt: {map}": "Map chosen: {map}",
    "Noch keine Map gewählt.": "No map chosen yet.",
    "Overlay eingeblendet.": "Overlay shown.",
    "Overlay ausgeblendet.": "Overlay hidden.",
    "„{map}“ hat nur ein Layout.": "“{map}” has only one layout.",
    "Layout manuell gewechselt": "layout changed by hand",
    "Scanne den Bildschirm nach Map- oder Realm-Namen …": "Scanning the screen for map or realm names …",
    "Testanzeige": "test display",
    "Test: Overlay 10 s lang an seiner normalen Position – jetzt zu DBD wechseln (nochmal drücken beendet den "
    "Test).":
        "Test: overlay for 10 s at its normal position – switch to DBD now (press again to end the test).",
    "Test beendet.": "Test ended.",
    "Diagnose in die Zwischenablage kopiert (auch als diagnose.txt gespeichert).":
        "Diagnostics copied to the clipboard (also saved as diagnose.txt).",
    "Erst eine Map wählen, dann lässt sich das Overlay verschieben.": "Choose a map first, then the overlay can be moved.",
    "Overlay mit der Maus ziehen, Mausrad = Grösse. Danach „Fertig“ oder Hotkey.":
        "Drag the overlay with the mouse, mouse wheel = size. Then “Done” or the hotkey.",
    "Position zurückgesetzt (automatisch).": "Position reset (automatic).",
    "keine Map": "no map",
    "ausgeblendet": "hidden",
    "Menü offen": "menu open",
    "aktives Fenster ist {window}": "active window is {window}",
    "DBD-Fenster {w}×{h}": "DBD window {w}×{h}",
    "Bildschirm": "screen",
    "Overlay sichtbar bei {pos} über {src}.": "Overlay visible at {pos} over {src}.",
    "Overlay pausiert: {reason}.": "Overlay paused: {reason}.",
    "{text} – Details in dbdmapscout.log": "{text} – details in dbdmapscout.log",

    # ------------------------------------------------------------------ detection events
    "Map-Banner gefunden, lese …": "Map banner found, reading …",
    "automatisch erkannt ({p})": "detected automatically ({p})",
    "Layout {n} ({p})": "Layout {n} ({p})",
    "Rundentimer gestartet.": "Round timer started.",
    "Rundentimer gestoppt: {time}.": "Round timer stopped: {time}.",
    "Erkannt: {map} – gelesen „{name}“ / „{realm}“": "Detected: {map} – read “{name}” / “{realm}”",
    "Layout unsicher – falls falsch: Layout-Knopf oder {keys}.": "Layout unsure – if wrong: layout button or {keys}.",
    "Banner gesehen, aber keine bekannte Map: „{text}“. Map manuell wählen oder mit „Zuordnen …“ dauerhaft "
    "zuordnen.":
        "Banner seen, but no known map: “{text}”. Choose the map by hand or assign it for good with “Assign …”.",
    "Runde vorbei ({reason}) – Overlay ausgeblendet.": "Round over ({reason}) – overlay hidden.",
    "Runde vorbei ({reason}).": "Round over ({reason}).",
    "Menü offen (Mauszeiger sichtbar) – Overlay pausiert.": "Menu open (mouse pointer visible) – overlay paused.",
    "Zurück im Spiel – Overlay wieder sichtbar.": "Back in the game – overlay visible again.",
    "Die Erkennung ist abgestürzt – Details in dbdmapscout.log": "The detection crashed – details in dbdmapscout.log",
    "Die Erkennung ist abgestürzt:": "The detection crashed:",
    "Scan fehlgeschlagen: {error}": "Scan failed: {error}",
    "per Scan gefunden: „{text}“": "found by scan: “{text}”",
    "Scan ({s} s): {map}": "Scan ({s} s): {map}",
    "Realm „{realm}“ hat nur diese Map": "Realm “{realm}” has only this map",
    "Scan: Realm „{realm}“ gefunden – bitte Map in der Liste wählen.": "Scan: realm “{realm}” found – please choose the map in the list.",
    "Scan ({s} s): kein Map- oder Realm-Name auf dem Bildschirm.": "Scan ({s} s): no map or realm name on the screen.",
    # end-of-round reasons and state (matchend / detector / worker)
    "Ergebnisbildschirm": "results screen",
    "Lobby/Menü": "lobby/menu",
    "Ladebildschirm": "loading screen",
    "DBD wurde geschlossen": "DBD was closed",
    "Menü/Lobby (Mauszeiger lange sichtbar)": "menu/lobby (mouse pointer visible for a long time)",
    "keine Map angezeigt": "no map shown",
    "Runde vorbei ({reason})": "round over ({reason})",
    "wartet, bis du im Match bist (Map manuell gewählt)": "waiting until you are in a match (map chosen by hand)",
    "Menü offen – Overlay pausiert": "menu open – overlay paused",
    "im Match": "in match",
    "Ausblenden nach der Runde aus": "hiding after the round off",
    "Mauszeiger-Hinweis aus": "mouse pointer cue off",
    "Mauszeiger-Hinweis ab dem nächsten Map-Banner": "mouse pointer cue from the next map banner",
    "Mauszeiger: –": "mouse pointer: –",
    "Mauszeiger sichtbar": "mouse pointer visible",
    "Mauszeiger verborgen": "mouse pointer hidden",
    "aus (Einstellung)": "off (setting)",
    "Runde vorbei – wartet auf die nächste Map": "round over – waiting for the next map",
    "Automatische Erkennung ist aus": "Automatic detection is off",
    "DBD ist minimiert": "DBD is minimised",
    "DBD gefunden ({w}×{h}) – warte auf Map-Banner": "DBD found ({w}×{h}) – waiting for the map banner",
    "DBD-Fenster nicht gefunden – beobachte Hauptbildschirm": "DBD window not found – watching the main screen",
    "Bildschirmaufnahme fehlgeschlagen: {error}": "Screen capture failed: {error}",
    "Aufnahme ist schwarz – DBD im Modus „Fenster-Vollbild“ betreiben":
        "Capture is black – run DBD in “Windowed Fullscreen” mode",
    "Fensteraufnahme nicht möglich, nutze Bildschirmaufnahme ({error})":
        "Window capture not possible, using screen capture ({error})",
    "DBD im Hintergrund – Fensteraufnahme aktiv: die Map wird auch erkannt, wenn andere Fenster darüber liegen.":
        "DBD in the background – window capture active: the map is detected even when other windows cover it.",
    "Rundenende-Erkennung für die gewählte Map ist jetzt aktiv.": "End-of-round detection for the chosen map is now active.",
    "Mauszeiger war beim Map-Banner sichtbar – Menü-Erkennung per Mauszeiger ist für diese Runde aus.":
        "The mouse pointer was visible at the map banner – menu detection by mouse pointer is off for this round.",

    # ------------------------------------------------------------------ assign dialog
    "Map zuordnen": "Assign map",
    "Gelesen: „{text}“": "Read: “{text}”",
    "Welche Map war das? Der Name wird künftig automatisch erkannt.":
        "Which map was it? The name will be recognised automatically from now on.",
    "Bitte eine Map auswählen.": "Please choose a map.",
    "Abbrechen": "Cancel",
    "„{text}“ wird jetzt als {map} erkannt (eigene Zuordnung).": "“{text}” is now recognised as {map} (own assignment).",
    "zugeordnet: „{text}“": "assigned: “{text}”",
    "Der gelesene Text ist zu kurz.": "The text read is too short.",
    "Unbekannte Map.": "Unknown map.",
    "„{text}“ ist schon der Name von {map}.": "“{text}” is already the name of {map}.",

    # ------------------------------------------------------------------ picture dialog
    "Kartenbild hinzufügen": "Add map picture",
    "eigenes Bild": "own picture",
    "Kartenbild gespeichert: {path}": "Map picture saved: {path}",
    "Eigenes Kartenbild für {map} gespeichert: {path}": "Own map picture for {map} saved: {path}",
    "wird ab jetzt automatisch erkannt.": "is detected automatically from now on.",
    "Eigenes Kartenbild für {map} gelöscht – das mitgelieferte gilt wieder.":
        "Own map picture for {map} deleted – the supplied one is used again.",
    "Bitte den Namen der Map eingeben.": "Please enter the name of the map.",
    "„{name}“ gibt es schon ({map}) – dann „Bild einer vorhandenen Map ersetzen“ wählen.":
        "“{name}” already exists ({map}) – choose “Replace the picture of an existing map” instead.",
    "Noch kein Bild gewählt (PNG, JPG, WebP, GIF)": "No picture chosen yet (PNG, JPG, WebP, GIF)",
    "Für welche Map?": "For which map?",
    "Original": "Original",
    "Ergebnis": "Result",
    "Eigenes Bild löschen": "Delete own picture",
    "Speichern": "Save",
    "Bilder": "Pictures",
    "Alle Dateien": "All files",
    "Kartenbild wählen": "Choose map picture",
    "Für diese Map lässt sich kein Bild speichern.": "No picture can be saved for this map.",
    "Erst ein Bild wählen.": "Choose a picture first.",
    "Das ist kein lesbares Bild: {error}": "This is not a readable picture: {error}",
    "Bild konnte nicht verarbeitet werden: {error}": "The picture could not be processed: {error}",
    "Speichern fehlgeschlagen: {error}": "Saving failed: {error}",
    "Eigenes Bild für „{map}“ löschen?": "Delete your own picture for “{map}”?",
    "Löschen fehlgeschlagen: {error}": "Deleting failed: {error}",
    "Bild wählen …": "Choose picture …",
    "Bild einer vorhandenen Map ersetzen": "Replace the picture of an existing map",
    "Neue Map (fehlt im Programm)": "New map (missing in the program)",
    "Name": "Name",
    "Name so, wie er im Map-Banner steht – dann wird die Map automatisch erkannt.":
        "Name as shown in the map banner – then the map is detected automatically.",
    "Hintergrund entfernen (Dunkelblau und Graulila der Community-Karten) und Rand abschneiden":
        "Remove the background (dark blue and grey violet of the community maps) and cut off the border",
    "Ordner öffnen": "Open folder",
    "Animiertes GIF: wird unverändert übernommen.": "Animated GIF: used unchanged.",

    # ------------------------------------------------------------------ tooltips
    "Technische Optionen für die Fehlersuche ein- oder ausklappen.": "Show or hide technical options for troubleshooting.",
    "Klicken und die neue Tastenkombination drücken (Strg/Alt + Taste oder F-Taste). Esc bricht ab, Entf "
    "schaltet den Hotkey aus.":
        "Click and press the new key combination (Ctrl/Alt + key or an F key). Esc cancels, Delete switches the "
        "hotkey off.",
    "Map-Namen in dieser Spielsprache erkennen. Nur die Sprachen anhaken, in denen du spielst – weniger "
    "Sprachen, weniger Verwechslungen.":
        "Recognise map names in this game language. Only tick the languages you play in – fewer languages, fewer "
        "mix-ups.",
    "Meldungen der Art „{category}“ im Log anzeigen.": "Show “{category}” messages in the log.",
    "Karte ausblenden (die automatische Erkennung läuft weiter).": "Hide the map (automatic detection keeps running).",
    "Karte wieder einblenden.": "Show the map again.",
    "Die Erkennung war beim Layout nicht sicher – stimmt es nicht, hier weiterschalten.":
        "The detection was not sure about the layout – if it is wrong, switch here.",
    "Wechselt zum nächsten Layout dieser Map (z. B. Coal Tower ↔ Coal Tower II). Die Layouts ab II gibt es seit "
    "Patch 8.6.0 nur noch in Custom Games.":
        "Switches to the next layout of this map (e.g. Coal Tower ↔ Coal Tower II). Since patch 8.6.0 the layouts "
        "from II on only exist in custom games.",
    "Test sofort beenden.": "End the test now.",
    "Zeigt die Karte 10 s an ihrer normalen Position – auch wenn sie gerade ausgeblendet wäre. Nochmal drücken "
    "beendet den Test.":
        "Shows the map for 10 s at its normal position – even if it would be hidden right now. Press again to end "
        "the test.",
    "Verschieben beenden.": "Stop moving.",
    "Karte direkt mit der Maus ziehen, Mausrad ändert die Grösse.": "Drag the map with the mouse, the mouse wheel changes the size.",
    "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen – falls die automatische Erkennung "
    "das Banner verpasst hat.":
        "Searches the whole screen for a map or realm name right away – in case automatic detection missed the "
        "banner.",
    "Eigenes Kartenbild für diese unbekannte Map anlegen – Name und Realm sind schon eingetragen, der "
    "Hintergrund wird automatisch entfernt.":
        "Create your own map picture for this unknown map – name and realm are filled in already, the background "
        "is removed automatically.",
    "Der gelesene Name gehört zu einer vorhandenen Map (z. B. anders geschrieben)? Einmal zuordnen – danach wird "
    "er automatisch erkannt.":
        "The name read belongs to an existing map (e.g. spelled differently)? Assign it once – after that it is "
        "recognised automatically.",
    "✕": "✕",
    "Hinweis ausblenden.": "Hide this notice.",
    "Eigenes Bild für eine Map wählen: vorhandenes Bild ersetzen oder neue Map anlegen. Rand und Hintergrund "
    "werden automatisch entfernt.":
        "Choose your own picture for a map: replace an existing picture or create a new map. Border and "
        "background are removed automatically.",
    "Position wieder auf „automatisch“ stellen (auf Ultrawide im linken schwarzen Rand).":
        "Set the position back to “automatic” (on ultrawide in the left black bar).",
    "Auf breiten Monitoren bleibt die Karte im schwarzen Balken, in dem sie liegt, und wird bei Bedarf "
    "verkleinert. Mitten über dem Spiel platziert gilt keine Begrenzung.":
        "On wide monitors the map stays inside the black bar it is in and is made smaller if needed. Placed over "
        "the middle of the game there is no limit.",
    "Karte ausblenden, solange ein anderes Fenster (Browser, Discord …) im Vordergrund ist.":
        "Hide the map while another window (browser, Discord …) is in the foreground.",
    "Zusätzliche Namenszeile über der Karte – die meisten Kartenbilder tragen den Namen schon selbst.":
        "Extra name line above the map – most map pictures already show the name themselves.",
    "Zeit seit dem Einblenden der Karte, gross unter der Karte.": "Time since the map appeared, large below the map.",
    "Region und Ping des Spielservers unter der Karte. Braucht „Verbundener Spielserver“ im Tab Server.":
        "Region and ping of the game server below the map. Needs “Connected game server” in the Server tab.",
    "Aus: Karte liegt auf einem dunklen Rechteck – besser lesbar über hellen Spielszenen.":
        "Off: the map sits on a dark rectangle – easier to read over bright game scenes.",
    "Liest das Map-Banner am Match-Anfang und blendet die passende Karte ein. Aus: Map nur von Hand wählen.":
        "Reads the map banner at the start of a match and shows the matching map. Off: choose the map by hand only.",
    "Blendet die Karte nach der Runde aus (Ergebnisbildschirm, Lobby, Ladebildschirm, DBD beendet).":
        "Hides the map after the round (results screen, lobby, loading screen, DBD closed).",
    "Karte verschwindet, solange der Mauszeiger im Spiel sichtbar ist (ESC-Menü), und kommt danach wieder.":
        "The map disappears while the mouse pointer is visible in the game (ESC menu) and comes back afterwards.",
    "Fensteraufnahme wie bei OBS: erkennt das Banner auch, wenn DBD verdeckt ist. Nur solange DBD im Hintergrund "
    "ist.":
        "Window capture like OBS: detects the banner even when DBD is covered. Only while DBD is in the background.",
    "Speichert gelesene Banner und verkleinerte Bilder der Runde – nur zur Fehlersuche, kostet Speicherplatz.":
        "Saves the banners read and small pictures of the round – for troubleshooting only, uses disk space.",
    "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen.":
        "Searches the whole screen for a map or realm name right away.",
    "Kopiert technische Infos (Fenster, Overlay, letzte Rundenende-Prüfungen) in die Zwischenablage – zum "
    "Weitergeben bei Problemen.":
        "Copies technical info (window, overlay, last end-of-round checks) to the clipboard – to pass on when "
        "something goes wrong.",
    "Zeigt Region und Ping des Spielservers (liest nur Paketköpfe, nie Inhalte). Braucht Administratorrechte.":
        "Shows region and ping of the game server (reads packet headers only, never contents). Needs "
        "administrator rights.",
    "Misst den Ping zu allen AWS-Regionen (UDP-Beacon von Amazon GameLift).":
        "Measures the ping to all AWS regions (UDP beacon of Amazon GameLift).",
    "Nur die angehakten Regionen erlauben – trägt die übrigen in die Windows-hosts-Datei ein (fragt nach "
    "Administratorrechten).":
        "Allow only the ticked regions – adds the others to the Windows hosts file (asks for administrator "
        "rights).",
    "Entfernt die Einträge des Programms aus der hosts-Datei – alle Regionen wieder erlaubt.":
        "Removes the program's entries from the hosts file – all regions allowed again.",
    "Log-Anzeige leeren (die Log-Datei bleibt).": "Clear the log view (the log file stays).",
    "Öffnet dbdmapscout.log mit allen Details.": "Opens dbdmapscout.log with all details.",
    "Dunkle oder helle Darstellung des Steuerfensters.": "Dark or light look of the control window.",
    "Alle Hotkeys auf die Voreinstellung zurücksetzen.": "Reset all hotkeys to the defaults.",
    "Minimieren versteckt das Fenster im Infobereich; Doppelklick auf das Symbol holt es zurück.":
        "Minimising hides the window in the notification area; double-click the icon to bring it back.",
    "Startet das Programm bei der Anmeldung im Infobereich. Nur als Administrator änderbar.":
        "Starts the program in the notification area when you sign in. Can only be changed as administrator.",
    "Holt beim Start über die Verknüpfung den neuen Stand von GitHub. Eigene Änderungen werden nie überschrieben.":
        "Fetches the newest version from GitHub when started through the shortcut. Your own changes are never "
        "overwritten.",
    "Alle eigenen Map-Zuordnungen löschen (die Namen werden dann wieder als unbekannt gemeldet).":
        "Delete all own map assignments (the names are reported as unknown again).",
    "Öffnet den Ordner des Programms im Explorer.": "Opens the program folder in Explorer.",
    "Öffnet den Ordner mit den mitgelieferten Kartenbildern.": "Opens the folder with the supplied map pictures.",
    "PNG, JPG, WebP oder GIF auswählen – zum Beispiel ein Original mit Hintergrund.":
        "Choose a PNG, JPG, WebP or GIF – for example an original with background.",
    "Dein Bild ersetzt das mitgelieferte Bild dieser Map (bzw. dieses Layouts). Löschen stellt das Original "
    "wieder her.":
        "Your picture replaces the supplied picture of this map (or this layout). Deleting restores the original.",
    "Legt eine neue Map an. Sie wird erkannt, wenn der Name so geschrieben ist wie im Map-Banner.":
        "Creates a new map. It is detected if the name is written as in the map banner.",
    "Öffnet den Ordner user_maps mit deinen eigenen Kartenbildern.": "Opens the user_maps folder with your own map pictures.",
    "Löscht dein Bild für die gewählte Map – danach gilt wieder das mitgelieferte.":
        "Deletes your picture for the chosen map – the supplied one is used again.",
    "Bild umwandeln und speichern; die Karte wird sofort angezeigt.": "Convert and save the picture; the map is shown right away.",
    "Schliessen, ohne etwas zu ändern.": "Close without changing anything.",
    "Macht Dunkelblau (#282a42) und Graulila (#535781) der Community-Karten transparent, schneidet den "
    "gleichfarbigen Rand ab und bringt das Bild auf 1280 px Höhe.":
        "Makes the dark blue (#282a42) and grey violet (#535781) of the community maps transparent, cuts off the "
        "border of the same colour and scales the picture to 1280 px height.",
}
