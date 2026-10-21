"""English texts: German original (the key in the code) -> English.

Placeholders ({map}, {error}, …) must stay the same – tests/test_i18n.py checks that every
text in the code is here and that the placeholders match.
"""

EN = {
    # ------------------------------------------------------------------ start
    "DbD Map Scout läuft bereits, reagiert aber nicht (oder ist gerade beim Beenden).\n\nKurz warten und nochmal starten. Hilft das nicht: im Task-Manager unter „Details“ „pythonw.exe“ (DbD Map Scout) beenden.":
        "DbD Map Scout is already running but does not answer (or is just closing).\n\nWait a moment and start it again. If that does not help: end “pythonw.exe” (DbD Map Scout) in Task Manager under “Details”.",
    "DbD Map Scout konnte nicht neu gestartet werden: Die alte Kopie läuft noch im Hintergrund.\n\nIm Task-Manager unter „Details“ „pythonw.exe“ (DbD Map Scout) beenden und das Programm neu starten.":
        "DbD Map Scout could not restart: the old copy is still running in the background.\n\nEnd “pythonw.exe” (DbD Map Scout) in Task Manager under “Details” and start the program again.",
    "Start fehlgeschlagen:": "Start failed:",
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
    "eigene Grösse {n} % (Hotkeys/Strg+Mausrad)": "own size {n} % (hotkeys/Ctrl+wheel)",
    "gedreht um {deg}°": "turned by {deg}°",
    # lobby: search, waiting time, role
    "Killer": "Killer",
    "Survivor": "Survivor",
    "Rolle": "Role",
    "Rolle: {role}": "Role: {role}",
    "Alle Rollen": "All roles",
    "Custom Game": "Custom game",
    "Custom Games": "Custom games",
    "Farming": "Farming",
    "Stil": "Style",
    "Original": "Original",
    "Dunkel": "Dark",
    "Die Karten mit lila Boden, wie sie mitgeliefert werden – gilt auch im Spiel.":
        "The maps with the purple floor, as they come – applies in the game too.",
    "Klassisch": "Classic",
    "Glas-Karten": "Glass cards",
    "Chips & Icons": "Chips & icons",
    "Minimal Line": "Minimal line",
    "SYSTEM": "SYSTEM",
    "Farming an/aus": "Farming on/off",
    "Farming-Runden": "Farming rounds",
    "Runden ohne Crossplay als Farming zählen": "Count rounds without cross-play as farming",
    "Alle Runden auf": "All rounds on",
    "Farming-Runden zählen nicht zu den normalen Runden (Rollen-Filter, Wartezeiten, Bilanz, Ergebnisse) – "
    "die Statistik hat dafür den Filter „Farming“. Crossplay aus erkennt das Programm an der Weltkugel mit "
    "rotem Kreuz neben dem Lobby-Knopf; Runden auf der gewählten Region zählen immer als Farming, auch "
    "ältere. Einzelne Runden: „Farming an/aus“ unter „Letzte Runden“.":
        "Farming rounds do not count as normal rounds (role filters, waiting times, record, results) – the "
        "statistics have their own filter \"Farming\". Cross-play off is read from the globe with the red cross next "
        "to the lobby button; rounds on the chosen region always count as farming, older ones too. Single rounds: "
        "\"Farming on/off\" under \"Last rounds\".",
    "{map} ({when}) zählt jetzt als Farming-Runde.": "{map} ({when}) now counts as a farming round.",
    "{map} ({when}) zählt wieder als normale Runde.": "{map} ({when}) counts as a normal round again.",
    "Hinweis: Runden auf {region} zählen laut Einstellung weiter als Farming.":
        "Note: rounds on {region} still count as farming by the setting.",
    "Crossplay war aus – die Runde zählt als Farming-Runde.": "Cross-play was off – the round counts as a farming round.",
    "Crossplay war aus, die Lobby sah aus wie ein Custom Game – die Runde zählt als Farming-Runde, sobald die Stats-Seite sie als öffentliches Match zeigt.": "Cross-play was off, the lobby looked like a custom game – the round counts as a farming round once the stats page shows it as a public match.",
    "{off} von {n} Blicken mit Kreuz": "{off} of {n} looks with the cross",
    "letzter Blick": "last look",
    "Crossplay ist aus ({looks}) – die nächste Runde zählt als Farming-Runde.":
        "Cross-play is off ({looks}) – the next round counts as a farming round.",
    "Crossplay ist an ({looks}) – keine Farming-Runde.": "Cross-play is on ({looks}) – no farming round.",
    "Als Custom Game erkannt – die Runde zählt nicht als Farming (unter „Letzte Runden“ mit „Farming an/aus“ "
    "korrigierbar).": "Recognised as a custom game – the round does not count as farming (correct it under "
                      "\"Last rounds\" with \"Farming on/off\").",
    "Keine Lobby zur Runde ({why}) – sie zählt nicht als Farming.":
        "No lobby for this round ({why}) – it does not count as farming.",
    "Lobby zu alt": "lobby too old",
    "Lobby nicht gesehen": "lobby not seen",
    "Diese Runde als Farming-Runde zählen bzw. wieder als normale Runde – Farming-Runden erscheinen nur unter dem "
    "Filter „Farming“. Runden auf der Farming-Region (Einstellungen → Mehr) bleiben Farming.":
        "Count this round as a farming round, or as a normal round again – farming rounds show only under the "
        "filter \"Farming\". Rounds on the farming region (Settings → More) stay farming.",
    "Zeigt die Lobby die Weltkugel mit rotem Kreuz (Crossplay aus), zählt die nächste Runde als Farming-Runde.":
        "If the lobby shows the globe with the red cross (cross-play off), the next round counts as a farming round.",
    "Custom Game – keine Wartezeit.": "Custom game – no waiting time.",
    "Suche läuft: {time}": "Searching: {time}",
    "Suche nach einem Match gestartet.": "Started searching for a match.",
    "Lobby verlassen – sie zählt für keine Runde.": "Lobby left – it does not count for any round.",
    "Suche abgebrochen.": "Search cancelled.",
    "Lobby gefunden nach {time}{role}.": "Lobby found after {time}{role}.",
    "Lobby gefunden{role}.": "Lobby found{role}.",
    "Wartezeit {time}": "waited {time}",
    "Ergebnisbildschirm: gespielt als {role}.": "Results screen: played as {role}.",
    "Wartezeit": "Waiting time",
    "Regionen": "Regions",
    "Markierte Runde:": "Selected round:",
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
    "Ø Ping": "Avg. ping",
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
    "Noch keine Wartezeiten in dieser Auswahl.": "No waiting times in this selection yet.",
    "nach Wochentag": "by weekday",
    "nach Uhrzeit": "by time of day",
    "nach Region": "by region",
    "Wann/Wo": "When/where",
    "Ø Wartezeit": "Avg. wait",
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
    "Etage wechseln": "Change floor",
    "Beide Etagen": "Both floors",
    "Etage {n} von {total}": "Floor {n} of {total}",
    "Diese Map hat nur eine Etage.": "This map has only one floor.",
    "Wechselt die Anzeige bei Karten mit Etagen (Midwich): beide untereinander → unten → oben → beide. Gilt "
    "bis zur nächsten Map.":
        "Switches what maps with floors (Midwich) show: both one below the other → bottom → top → both. Lasts "
        "until the next map.",
    "Etagen (Midwich) untereinander zeigen (aus: nur die untere)":
        "Show the floors (Midwich) one below the other (off: only the bottom one)",
    "An: Karten mit Etagen (Midwich) zeigen alle Etagen untereinander, oben über unten – jede so groß wie "
    "eine normale Karte, soweit der Platz reicht. Aus: Sie starten mit der unteren Etage. Der Knopf „Etage“ "
    "oder der Hotkey schaltet jederzeit um.":
        "On: maps with floors (Midwich) show all floors one below the other, top above bottom – each as big as "
        "a normal map, as far as the space allows. Off: they start with the bottom floor. The “Floor” button or "
        "the hotkey switches at any time.",
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
    "DBD läuft mit {w}×{h}, kleiner als 1920×1080: die Erkennung ist unsicherer (vor allem "
    "Lobby-Knopf und Killername). Fenster größer ziehen oder „Fenster-Vollbild“ nutzen.":
        "DBD runs at {w}×{h}, smaller than 1920×1080: detection is less reliable (above all the lobby "
        "button and killer name). Make the window bigger or use “Windowed Fullscreen”.",
    "DBD-Fenster ist schmaler als 16:9 ({w}×{h}): diese Form ist ungetestet, Map- und "
    "Rundenende-Erkennung können danebenliegen. Am sichersten: 16:9 oder breiter.":
        "DBD window is narrower than 16:9 ({w}×{h}): this shape is untested, map and round-end "
        "detection may be off. Safest: 16:9 or wider.",
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
    "Global": "Global",
    "keine Daten vom Mitschnitt": "no data from the capture",
    "Nur unter Windows verfügbar.": "Only available on Windows.",
    "Mitschnitt beendet (Code {code}).": "Capture ended (code {code}).",
    "Fehler: {error}": "Error: {error}",

    # ------------------------------------------------------------------ tab statistics
    "Statistik": "Statistics",
    "Maps": "Maps",
    "Map": "Map",
    "Runden": "Rounds",
    "Ø Dauer": "Avg. length",
    "Letzte Runden": "Last rounds",
    "Gesamter Zeitraum": "All time",
    "Heute": "Today",
    "Diese Woche": "This week",
    "Dieser Monat": "This month",
    "Dieses Jahr": "This year",
    "Alle Regionen": "All regions",
    "Alle Killer": "All killers",
    "Häufigste Map": "Most frequent map",
    "Der markierte Name (Skin oder neuer Killer) zählt ab jetzt als der gewählte Killer – auch in allen bisherigen "
    "Runden.": "The selected name (skin or new killer) counts as the chosen killer from now on – in all past rounds "
               "too.",
    "Entfernt alle eigenen Killer-Zuordnungen; die Namen erscheinen wieder so, wie sie gelesen wurden.":
        "Removes all own killer assignments; the names show up again as they were read.",
    "Zuordnen": "Assign",
    "Warte auf Map": "Waiting for map",
    "Solange DBD läuft und keine Karte eingeblendet ist, zeigt das Overlay eine kleine Karte: „Warte auf Map“, "
    "darunter Suche/Lobby (z. B. „Suche läuft: 02:13 · Nurse“) oder die letzte Runde. Gilt nicht, wenn du die "
    "Karte selbst ausgeblendet hast.":
        "While DBD runs and no map is shown, the overlay shows a small card: \"Waiting for map\", below it the "
        "search/lobby (e.g. \"Searching: 02:13 · Nurse\") or the last round. Not when you hid the map yourself.",
    "Ohne Karte: „Warte auf Map“ und Lobby-Status anzeigen": "Without a map: show \"Waiting for map\" and the lobby state",
    "Killer der Runde:": "Killer of the round:",
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
    "Runde löschen": "Delete round",
    "Ø {kills} Kills · {n} Runden": "Avg. {kills} kills · {n} rounds",
    "Killer: Ø {kills} Kills, {four}× 4K ({n})": "Killer: avg. {kills} kills, {four}× 4K ({n})",
    "Survivor: {share} entkommen ({n})": "Survivor: {share} escaped ({n})",
    "{share} entkommen · {n} Runden": "{share} escaped · {n} rounds",
    "Eigene Bilanz auf der Map unter dem Timer (Stats-Seite)": "Own record on the map below the timer (stats page)",
    "Eigene Notiz zur Map unter dem Timer (Seite Maps)": "Own note on the map below the timer (Maps page)",
    "Zeigt deine eigene Notiz zur Map unter dem Rundentimer – geschrieben auf der Seite Maps (Map anklicken "
    "oder Rechtsklick → „Notiz bearbeiten …“), höchstens vier Zeilen.":
        "Shows your own note on the map below the round timer – written on the Maps page (click a map or right "
        "click → \"Edit note …\"), at most four lines.",
    "Deine Notiz zu dieser Map – wird beim Tippen gespeichert und im Spiel unter dem Timer gezeigt (höchstens vier "
    "Zeilen). Leer = keine Notiz.":
        "Your note on this map – saved while you type and shown in the game below the timer (at most four lines). "
        "Empty = no note.",
    "Eigene Notiz (im Spiel unter dem Timer)": "Own note (in the game below the timer)",
    "z. B. Shack links vom Main, Gen im Keller …": "e.g. shack left of main, gen in the basement …",
    "Notiz bearbeiten …": "Edit note …",
    "Eigene Notiz": "Own note",
    "Eigene Notiz: {note}": "Own note: {note}",
    "Zeigt unter dem Rundentimer, wie es dir auf dieser Map bisher ging: als Killer Ø Kills, als Survivor den "
    "Anteil Escapes – aus den Runden mit Daten der Stats-Seite, ab 3 Runden.":
        "Shows below the round timer how you have done on this map so far: average kills as killer, share of "
        "escapes as survivor – from the rounds with stats-page data, from 3 rounds on.",
    "Entfernt die markierte Runde aus der Statistik – z. B. eine Map, die mitten im Match falsch erkannt wurde. "
    "Fragt vorher nach.":
        "Removes the marked round from the statistics – e.g. a map read wrongly in the middle of a match. Asks "
        "first.",
    "Runde {what} aus der Statistik löschen?": "Delete round {what} from the statistics?",
    "Runde konnte nicht gelöscht werden: {error}": "Could not delete the round: {error}",
    "Runde gelöscht: {map} ({when}).": "Round deleted: {map} ({when}).",
    "✓ {n} × Map mitten im Match falsch erkannt (laut Stats-Seite lief da schon ein Match) – nicht gezählt. "
    "Zuletzt: {map}, {when}.":
        "✓ {n} × map read wrongly in the middle of a match (the stats page already had a match running) – not "
        "counted. Last: {map}, {when}.",
    "Noch keine Runden gespeichert.": "No rounds saved yet.",
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
    "Startet ab jetzt mit Windows im Infobereich (abschaltbar unter Einstellungen → Start und Infobereich).":
        "From now on starts with Windows in the notification area (can be switched off under Settings → "
        "Start and notification area).",
    "Autostart mit Windows fehlgeschlagen: {error}": "Starting with Windows could not be set up: {error}",
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
    "Test: Overlay 10 s lang an seiner normalen Position, mit Systemwerten, „Heute“ und Musik (Beispielwerte, wenn "
    "nichts anliegt) – nochmal drücken beendet den Test.":
        "Test: overlay for 10 s at its normal position, with system values, \"Today\" and music (sample values when "
        "nothing is there) – press again to end the test.",
    "Links": "Left",
    "Mittig": "Centred",
    "Rechts": "Right",
    "Im Balken": "In the bar",
    "Abstand": "Gap",
    "Zeile CPU (Temperatur, Last)": "Row CPU (temperature, load)",
    "Zeile GPU (Temperatur, Last)": "Row GPU (temperature, load)",
    "Zeile Hotspot / GPU-Speicher (HWiNFO)": "Row hot spot / GPU memory (HWiNFO)",
    "Zeile VRAM": "Row VRAM",
    "Zeile RAM": "Row RAM",
    "Zeile in den Systemwerten an/aus. Die Warnungen „CPU/GPU DROSSELT“ erscheinen immer.":
        "Row of the system values on/off. The warnings \"CPU/GPU THROTTLED\" always show.",
    "Zeile in den Systemwerten an/aus – Hotspot und Memory Junction kommen nur mit HWiNFO.":
        "Row of the system values on/off – hot spot and memory junction only come with HWiNFO.",
    "Zeile in den Systemwerten an/aus.": "Row of the system values on/off.",
    "Test beendet.": "Test ended.",
    "Diagnose in die Zwischenablage kopiert (auch als diagnose.txt gespeichert).":
        "Diagnostics copied to the clipboard (also saved as diagnose.txt).",
    "Karte, Systemwerte und Musik mit der Maus ziehen (im Spiel oder in der Vorschau), Strg+Mausrad = Grösse. Danach „Fertig“ oder Hotkey.":
        "Drag the map, the system values and the music with the mouse (in the game or in the preview), Ctrl+mouse wheel = size. Then “Done” or the hotkey.",
    "Verschieben aktiv – ziehen (rastet ein, Alt = frei), Pfeiltasten = fein, Ecke/Strg+Mausrad = Grösse":
        "Moving is on – drag (snaps, Alt = free), arrow keys = fine, corner/Ctrl+wheel = size",
    "Rückgängig": "Undo",
    "Karte darf grösser als der Balken werden (ragt dann ins Spielbild)": "The map may grow bigger than the bar (it then reaches into the game picture)",
    "Erlaubt jede Kartengrösse: Ist die Karte breiter als der schwarze Balken, bleibt sie an dessen Aussenrand und ragt ins Spielbild. Aus: Die Karte wird nie breiter als der Balken (auf 3440×1440 etwa 31 % der Bildhöhe).":
        "Allows any map size: when the map is wider than the black bar it stays at the bar's outer edge and reaches into the game picture. Off: the map is never wider than the bar (about 31 % of the height on 3440×1440).",
    "Nimmt die letzte Änderung an Position oder Grösse zurück (Karte, Systemwerte, Musik) – auch mit Strg+Z auf dieser Seite. Ein ganzes Ziehen zählt als ein Schritt.":
        "Takes back the last change of place or size (map, system values, music) – also with Ctrl+Z on this page. A whole drag counts as one step.",
    "Merkt Position und Grösse aller Elemente getrennt für jede Grösse des DBD-Fensters (z. B. Vollbild 3440×1440 und ein kleineres Fenster) und lädt sie automatisch, sobald DBD in dieser Grösse läuft.":
        "Remembers place and size of every element separately for each size of the DBD window (e.g. full screen 3440×1440 and a smaller window) and loads them by itself as soon as DBD runs at that size.",
    "Nichts rückgängig zu machen.": "Nothing to undo.",
    "Position/Grösse rückgängig gemacht.": "Place/size undone.",
    "Position und Grösse je DBD-Fenstergrösse merken": "Remember place and size per DBD window size",
    "DBD-Fenster {size}: Layout für diese Grösse geladen.": "DBD window {size}: layout of this size loaded.",
    "DBD-Fenster {size}: neue Grösse – Layout wird ab jetzt dafür gemerkt.":
        "DBD window {size}: new size – the layout is remembered for it from now on.",
    "Aktuell: Layout für {size} · {n} Grössen gemerkt": "Now: layout for {size} · {n} sizes remembered",
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
    "Mitten in der Runde „{name}“ / „{realm}“ gelesen (am ehesten {map}) – ignoriert: Map-Banner gibt es nur am "
    "Rundenstart, und die Lesung war nicht eindeutig.":
        "Read “{name}” / “{realm}” in the middle of the round (closest: {map}) – ignored: map banners only appear "
        "at the start of a round, and the read was not clear.",
    "Banner gesehen, aber keine bekannte Map: „{text}“. Map manuell wählen oder mit „Zuordnen …“ dauerhaft "
    "zuordnen.":
        "Banner seen, but no known map: “{text}”. Choose the map by hand or assign it for good with “Assign …”.",
    "Runde vorbei ({reason}) – Overlay ausgeblendet.": "Round over ({reason}) – overlay hidden.",
    "Runde vorbei ({reason}).": "Round over ({reason}).",
    "Menü offen (Mauszeiger sichtbar) – Overlay pausiert.": "Menu open (mouse pointer visible) – overlay paused.",
    "Zurück im Spiel – Overlay wieder sichtbar.": "Back in the game – overlay visible again.",
    "Die Erkennung ist abgestürzt – Details in dbdmapscout.log": "The detection crashed – details in dbdmapscout.log",
    "Die Erkennung ist abgestürzt:": "The detection crashed:",
    "Die Erkennung ist abgestürzt – bitte DbD Map Scout neu starten.": "The detection crashed – please restart DbD Map Scout.",
    "Nichts gefunden": "Nothing found",
    "Runde gilt jetzt für {map} (vorher {old}).": "The round now counts for {map} (before: {old}).",
    "settings.json war nicht lesbar ({error}) – Standardwerte geladen. Bis zum Neustart wird nichts gespeichert.":
        "settings.json could not be read ({error}) – defaults loaded. Nothing is saved until the restart.",
    "settings.json war nicht lesbar ({error}) – Standardwerte geladen, die alte Datei liegt als settings.json.broken daneben.":
        "settings.json could not be read ({error}) – defaults loaded, the old file was kept as settings.json.broken.",
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
    "Clip wird geladen …": "Loading clip …",
    "Vorschaubild und Zeitleiste kommen aus der Aufnahme.": "Preview picture and timeline are read from the recording.",
    "{n} von {total} Bildern": "{n} of {total} pictures",
    "Lädt länger als erwartet – das Fenster ist trotzdem bedienbar.": "Taking longer than expected – the window works anyway.",
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
    "DBD nicht gefunden – Erkennung startet, sobald DBD läuft": "DBD not found – detection starts once DBD runs",
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
    "Klicken und die neue Tastenkombination drücken: Strg/Alt + Taste, oder eine Taste allein (F1–F12, Numpad, "
    "Pause, Rollen, Einfg, Pos1, Ende, Bild↑/↓ – die gilt nur, solange DBD vorne ist). Esc bricht ab, Entf schaltet "
    "den Hotkey aus.":
        "Click and press the new key combination: Ctrl/Alt + key, or a single key (F1–F12, numpad, Pause, Scroll "
        "Lock, Insert, Home, End, Page Up/Down – it only works while DBD is in front). Esc cancels, Delete "
        "switches the hotkey off.",
    "Bild↑": "PgUp",
    "Bild↓": "PgDn",
    "Einfg": "Insert",
    "Pos1": "Home",
    "Ende": "End",
    "Rollen": "Scroll Lock",
    "Gilt nur, solange DBD im Vordergrund ist – DBD selbst bekommt {keys} dann nicht mehr (in DBD nicht belegt?).":
        "Only works while DBD is in front – DBD itself no longer gets {keys} (not bound in DBD?).",
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
    "Zeigt 10 s lang alles, was das Overlay im Match zeigt – Karte, Systemwerte, „Heute“ und Musik (Beispielwerte, "
    "wenn nichts anliegt) – an den eingestellten Stellen, auch ohne DBD. Nochmal drücken beendet den Test.":
        "Shows for 10 s everything the overlay shows in a match – map, system values, \"Today\" and music (sample "
        "values when nothing is there) – at their places, also without DBD. Press again to end the test.",
    "Verschieben beenden.": "Stop moving.",
    "Karte direkt mit der Maus ziehen, Strg+Mausrad ändert die Grösse.": "Drag the map with the mouse, Ctrl+mouse wheel changes the size.",
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
    # doubtful detection, today line (1.33)
    "? unsicher – {keys} = falsch": "? unsure – {keys} = wrong",
    "Falsch erkannt": "Wrong map",
    "Stimmt": "Correct",
    "Unsicher erkannt: {map} (gelesen „{name}“)": "Unsure detection: {map} (read “{name}”)",
    "Unsicher erkannt: {map} – gelesen „{name}“, Passung {fit}. Falls falsch: {keys} oder „Falsch erkannt“.":
        "Unsure detection: {map} – read “{name}”, fit {fit}. If wrong: {keys} or “Wrong map”.",
    "{map} bestätigt.": "{map} confirmed.",
    "Nichts zu verwerfen: keine automatisch erkannte Map eingeblendet.":
        "Nothing to throw away: no automatically detected map on display.",
    "Verworfen: {map} – die Runde wird nicht gezählt.": "Thrown away: {map} – the round is not counted.",
    "Die erkannte Map stimmt nicht: Karte ausblenden, Timer zurücksetzen, die Runde wird nicht "
    "gezählt. Geht auch im Spiel mit dem Hotkey (Standard Strg+Alt+X).":
        "The detected map is wrong: hide the map, reset the timer, the round is not counted. Also works in "
        "game with the hotkey (default Ctrl+Alt+X).",
    "Die Map stimmt – Hinweis „unsicher“ ausblenden.": "The map is right – hide the “unsure” note.",
    "als falsch verworfen": "thrown away as wrong",
    "{k} Killer / {s} Survivor": "{k} killer / {s} survivor",
    "Ping {ms} ms": "ping {ms} ms",
    # official match data (stats.deadbydaylight.com)
    "Ø Kills": "Avg. kills",
    "4K": "4K",
    "Entkommen": "Escaped",
    "Ergebnis": "Result",
    "entkommen": "escaped",
    "tot": "died",
    "aufgegeben": "abandoned",
    "verlassen": "left",
    "Stats-Seite öffnen, wenn DBD beendet wird": "Open the stats page when DBD is closed",
    "Userscript kopieren": "Copy userscript",
    "Stats-Seite öffnen": "Open stats page",
    "⚠ Unbekannter Status auf der Stats-Seite: {list} – zählt nicht. Bitte melden („Diagnose kopieren“).":
        "⚠ Unknown status on the stats page: {list} – not counted. Please report (\"Copy diagnostics\").",
    "⚠ Lücke: zwischen {start} und {end} fehlen vielleicht Matches – die Seite zeigt nur die letzten 30. Seite öfter "
    "öffnen.":
        "⚠ Gap: matches between {start} and {end} may be missing – the page shows only the last 30. Open the page "
        "more often.",
    "⚠ {n}× andere Map als erkannt, zuletzt {when}: erkannt {ours}, laut Seite {theirs}.":
        "⚠ {n}× a different map than detected, last {when}: detected {ours}, the page says {theirs}.",
    "⚠ Das Userscript ist veraltet (Version {old}, aktuell {new}) – „Userscript kopieren“ und in Tampermonkey "
    "ersetzen.":
        "⚠ The userscript is outdated (version {old}, current {new}) – \"Copy userscript\" and replace it in "
        "Tampermonkey.",
    "Stats-Seite konnte nicht geöffnet werden: {error}": "Could not open the stats page: {error}",
    "DBD beendet – Stats-Seite geöffnet; das Userscript speichert die Matches.":
        "DBD closed – stats page opened; the userscript saves the matches.",
    "Userscript nicht gefunden: {error}": "Userscript not found: {error}",
    "Userscript in die Zwischenablage kopiert. In Tampermonkey: „Neues Skript erstellen“ → alles ersetzen (Strg+A, "
    "Strg+V) → Speichern. Danach stats.deadbydaylight.com öffnen und anmelden.":
        "Userscript copied to the clipboard. In Tampermonkey: \"Create a new script\" → replace everything (Ctrl+A, "
        "Ctrl+V) → Save. Then open stats.deadbydaylight.com and sign in.",
    "Offizielle Match-Daten: {n} Matches gelesen, {new} neu – Datei gelöscht.":
        "Official match data: {n} matches read, {new} new – file deleted.",
    "Offizielle Match-Daten: zwischen {start} und {end} fehlen vielleicht Matches (die Seite zeigt nur die letzten 30).":
        "Official match data: matches between {start} and {end} may be missing (the page shows only the last 30).",
    "{name} gelesen, aber nicht gelöscht: {error}": "{name} read, but not deleted: {error}",
    "{name} ist keine Match-Datei von DbD Map Scout – bleibt liegen.":
        "{name} is not a DbD Map Scout match file – left alone.",
    "Unbekannter Status auf der Stats-Seite: „{status}“ – zählt nicht für Kills/Escapes. Bitte melden.":
        "Unknown status on the stats page: \"{status}\" – not counted for kills/escapes. Please report.",
    "Schliesst du DBD nach mindestens einer Runde, öffnet das Programm stats.deadbydaylight.com im Browser. Das "
    "Userscript speichert dann die letzten 30 Matches, das Programm liest sie ein und löscht die Datei. Nie während "
    "DBD läuft.":
        "When you close DBD after at least one round, the program opens stats.deadbydaylight.com in the browser. The "
        "userscript then saves the last 30 matches; the program reads them and deletes the file. Never while DBD is "
        "running.",
    "Kopiert das Userscript in die Zwischenablage. In Tampermonkey „Neues Skript erstellen“, alles ersetzen und "
    "speichern. Es liest nur die Match-Liste, die die Seite selbst lädt – keine Konto- oder Login-Daten – und schickt "
    "nichts irgendwohin.":
        "Copies the userscript to the clipboard. In Tampermonkey \"Create a new script\", replace everything and save. "
        "It only reads the match list the page loads itself – no account or login data – and sends nothing anywhere.",
    "Öffnet stats.deadbydaylight.com jetzt. Mit installiertem Userscript kommen die Matches gleich danach an.":
        "Opens stats.deadbydaylight.com now. With the userscript installed, the matches arrive right after.",
    "Vom Programm erkannt: {seen} von {n} ({share})": "Detected by the program: {seen} of {n} ({share})",
    "Nicht erkannt (oder das Programm lief nicht): {list}": "Not detected (or the program was not running): {list}",
    "Rundenende erkannt: Median {off} gegenüber dem Ende laut Seite ({n} Runden; + = später)":
        "End of round detected: median {off} against the end on the page ({n} rounds; + = later)",
    "{n} Mio.": "{n}M",
    "Ø BP": "Avg. BP",
    "✓ {n} × Rundenende nicht erkannt, aber mit der Dauer laut Stats-Seite gezählt.":
        "✓ {n} × end of round not detected, but counted with the length from the stats page.",
    # statistics: official data in the tables, check in tab Erkennung (1.36)
    "Runden vom Map-Banner bis zum Rundenende (ab 1 min), nur lokal gespeichert. Kills, Escapes und Bloodpoints laut "
    "stats.deadbydaylight.com, sobald eine Runde dort zugeordnet ist.":
        "Rounds from the map banner to the end of the round (from 1 min), stored only locally. Kills, escapes and "
        "bloodpoints from stats.deadbydaylight.com as soon as a round is tied to a match there.",
    "{n}× Abandon": "{n}× abandon",
    "Ein Skin oder neuer Killer steht unter seinem eigenen Namen? Zeile markieren, Killer wählen, „Zuordnen“ – gilt "
    "auch rückwirkend.":
        "An outfit or new killer shows under its own name? Select the row, pick the killer, \"Assign\" – also applies "
        "to past rounds.",
    "Abgleich mit der Stats-Seite": "Check against the stats page",
    "Noch keine offiziellen Daten. Einrichten: Einstellungen → Mehr → Offizielle Match-Daten.":
        "No official data yet. Set up: Settings → More → Official match data.",
    "Offizielle Match-Daten": "Official match data",
    "Einmal einrichten: Tampermonkey im Browser installieren, „Userscript kopieren“ und dort als neues Skript einfügen "
    "und speichern, auf stats.deadbydaylight.com anmelden. Chrome/Edge: in den Details der Erweiterung „Allow User "
    "Scripts“ einschalten, sonst läuft kein Skript. Beim Öffnen der Seite speichert das Skript neue Matches (die "
    "letzten 30) im Download-Ordner; das Programm liest die Datei und löscht sie. Es geht dafür selbst nicht ins "
    "Internet.":
        "Set up once: install Tampermonkey in the browser, \"Copy userscript\", paste it there as a new script and "
        "save it, sign in on stats.deadbydaylight.com. Chrome/Edge: switch on \"Allow User Scripts\" in the "
        "extension's details, otherwise no script runs. When the page opens, the script saves new matches (the last "
        "30) into the download folder; the program reads the file and deletes it. It does not go online for this "
        "itself.",
    "Alle Matches neu speichern": "Save all matches again",
    "Öffnet die Stats-Seite so, dass das Userscript ihre letzten 30 Matches noch einmal speichert, auch wenn keines "
    "neu ist – nach einer Neuinstallation oder wenn die Datei verloren ging.":
        "Opens the stats page so that the userscript saves its last 30 matches once more although none is new – "
        "after a new install or when the file got lost.",
    "Die Stats-Seite öffnet sich im Browser. Das Userscript (ab Version {n}) speichert ihre letzten 30 Matches noch "
    "einmal, auch wenn keines neu ist; das Programm übernimmt sie gleich – bekannte zählen nur einmal. Kommt keine "
    "Datei: in der Console des Browsers (F12) steht, ob das Skript läuft. Ältere Userscripts: vorher „Userscript "
    "kopieren“ und in Tampermonkey ersetzen.":
        "The stats page opens in the browser. The userscript (version {n} or newer) saves its last 30 matches once "
        "more although none is new; the program takes them right away – known ones count once. If no file comes: the "
        "browser's console (F12) says whether the script runs. Older userscripts: \"Copy userscript\" first and "
        "replace it in Tampermonkey.",
    # statistics: trend page, today line (1.37)
    "Verlauf": "Trend",
    "Nur Runden, die einem Match auf der Stats-Seite zugeordnet sind. Die Maus über einer Säule zeigt Wert und Anzahl "
    "der Runden.":
        "Only rounds tied to a match on the stats page. Hover over a column for its value and number of rounds.",
    "Killer – Ø Kills {per}": "Killer – avg. kills {per}",
    "Survivor – entkommen {per}": "Survivor – escaped {per}",
    "pro Stunde": "per hour",
    "pro Tag": "per day",
    "pro Woche": "per week",
    "KW {n}": "W{n}",
    "{when}: Ø {kills} Kills · {n} Runden": "{when}: avg. {kills} kills · {n} rounds",
    "{when}: {share} entkommen · {n} Runden": "{when}: {share} escaped · {n} rounds",
    "Keine Killer-Runden mit offiziellen Daten in dieser Auswahl.": "No killer rounds with official data in this selection.",
    "Keine Survivor-Runden mit offiziellen Daten in dieser Auswahl.":
        "No survivor rounds with official data in this selection.",
    "Ø {kills} Kills": "avg. {kills} kills",
    "{share} entkommen": "{share} escaped",
    "{bp} BP": "{bp} BP",
    # notification after an import (1.37.1)
    "Meldung, wenn Match-Daten eingelesen und gelöscht wurden": "Notify when match data was read and deleted",
    "Zeigt unten rechts kurz, wie viele Matches gelesen wurden und dass die Datei gelöscht ist – nicht, solange DBD "
    "im Vordergrund ist. Im Log steht es immer.":
        "Briefly shows bottom right how many matches were read and that the file was deleted – not while DBD is in "
        "front. The log always has it.",
    "{n} Matches gelesen, davon {new} neu. Die Datei wurde gelöscht.":
        "{n} matches read, {new} of them new. The file was deleted.",
    "{name} wurde gelesen, konnte aber nicht gelöscht werden – Details im Log.":
        "{name} was read but could not be deleted – details in the log.",
    # system values (app_sysinfo)
    "Links oben (über der Karte)": "Top left (above the map)",
    "Rechts oben": "Top right",
    "GPU: {name}": "GPU: {name}",
    "GPU: keine NVIDIA-Karte gefunden": "GPU: no NVIDIA card found",
    "CPU-Temperatur: aus HWiNFO": "CPU temperature: from HWiNFO",
    "Systemwerte (CPU/GPU-Temperatur, Auslastung, VRAM, RAM)": "System values (CPU/GPU temperature, load, VRAM, RAM)",
    # statistics: system values (app_stats)
    "System": "System",
    "nach Map": "by map",
    "nach Killer": "by killer",
    "GPU Ø °C": "GPU avg. °C",
    "GPU max": "GPU max",
    "CPU Ø °C": "CPU avg. °C",
    "CPU max": "CPU max",
    "GPU Ø Last": "GPU avg. load",
    "Ø Watt": "Avg. watts",
    "Noch keine Systemwerte in dieser Auswahl (Tab Overlay → Systemwerte einschalten).":
        "No system values in this selection yet (Overlay tab → switch on system values).",
    # system values: throttling, hot spot, temperature trend
    "GPU DROSSELT (TEMP.)": "GPU THROTTLED (TEMP.)",
    "GPU DROSSELT (HW)": "GPU THROTTLED (HW)",
    "Hotspot max {v} °C": "hot spot max {v} °C",
    "Hotspot max": "Hot spot max",
    "GPU-Temperatur – Ø {per}": "GPU temperature – average {per}",
    "Noch keine GPU-Temperaturen in dieser Auswahl.": "No GPU temperatures in this selection yet.",
    "{when}: Ø {avg} °C · max {max} °C · {n} Runden": "{when}: avg. {avg} °C · max {max} °C · {n} rounds",
    "Werte der Systemwerte-Anzeige (Tab Overlay) während der Runden – nur Runden, in denen sie eingeschaltet war. "
    "CPU-Temperatur nur mit HWiNFO. „Wann/Wo“ zeigt, auf welchen Maps oder zu welcher Tageszeit der PC am heißesten "
    "läuft. „Gedrosselt“: Sekunden, in denen die GPU wegen Temperatur oder Hardware langsamer lief (nur NVIDIA).":
        "Values of the system values display (Overlay tab) during the rounds – only rounds in which it was on. CPU "
        "temperature only with HWiNFO. \"When/Where\" shows on which maps or at what time of day the PC runs hottest. "
        "\"Throttled\": seconds in which the GPU ran slower because of temperature or hardware (NVIDIA only).",
    # system values: own position
    "Eigene Position (mit der Maus verschieben)": "Own position (drag with the mouse)",
    "SYSTEMWERTE": "SYSTEM VALUES",
    "Direkt über der Karte (wandert mit)": "Right above the map (moves with it)",
    "Schriftgrösse": "Font size",
    "Übersicht": "Overview",
    "Aktuelle Map": "Current map",
    "Rundenzeit": "Round time",
    "Ping": "Ping",
    "läuft": "running",
    "letzte Runde": "last round",
    "startet": "starting",
    "4K: {n} von {total}": "4K: {n} of {total}",
    "noch keine Stats-Daten": "no stats page data yet",
    "{n} Survivor-Runden": "{n} survivor rounds",
    "{n} normal": "{n} normal",
    "{n} Farming-Runden · Ø BP": "{n} farming rounds · avg. BP",
    "Spielzeit heute: {time}": "Played today: {time}",
    "Systemwerte sind aus (Tab Overlay → Systemwerte).": "System values are off (Overlay tab → System values).",
    "Systemwerte gibt es nur unter Windows.": "System values are only available on Windows.",
    "Erscheinen, sobald DBD läuft.": "Appear as soon as DBD is running.",
    "OK": "OK",
    '4 Kills · leer = weniger als {n} Runden': '4 kills · empty = fewer than {n} rounds',
    'Killer × Map – Ø Kills laut Stats-Seite': 'Killer × map – avg. kills from the stats page',
    'Maps – am häufigsten gespielt': 'Maps – most played',
    'Median {time}': 'median {time}',
    'Noch keine Killer-Runden mit Ergebnis von der Stats-Seite (Einstellungen → Mehr → Offizielle Match-Daten).': 'No killer rounds with a result from the stats page yet (Settings → More → Official match data).',
    'keine Killer-Runden mit Stats-Daten': 'no killer rounds with stats data',
    'keine Survivor-Runden mit Stats-Daten': 'no survivor rounds with stats data',
    '{map} · {killer}: Ø {kills} Kills ({n} Runden)': '{map} · {killer}: avg. {kills} kills ({n} rounds)',
    '{n} Matches': '{n} matches',
    '{time} gespielt': '{time} played',
    'Ø Bloodpoints': 'Avg. bloodpoints',
    'Ø Rundendauer': 'Avg. round length',
    # 1.58.1: maps page with preview
    'Anzeigen': 'Show',
    'Kartenbild nicht lesbar: {error}': 'Map picture not readable: {error}',
    'Keine Map gewählt': 'No map selected',
    'Blendet die gewählte Map jetzt als Overlay ein – die Erkennung übernimmt beim nächsten Match wieder.':
        'Shows the selected map in the overlay now – detection takes over again at the next match.',
    # 1.59: own order of the cards
    'Ziehen, um den Kasten zu verschieben': 'Drag to move this box',
    'Anordnung zurücksetzen': 'Reset arrangement',
    'Die Kästen der Seiten lassen sich am Griff rechts im Titel verschieben.':
        'The boxes of the pages can be moved by the handle at the right of their title.',
    'Stellt die Kästen auf allen Seiten, die Reiter-Reihen (Statistik, Overlay) und die Navigation links wieder in die ursprüngliche Reihenfolge.':
        'Puts the boxes of all pages, the tab rows (Statistics, Overlay) and the navigation on the left back in their original order.',
    # 1.60: setup assistant, search over the settings
    'Das Programm liest beim Match-Start den Map-Namen aus dem Bild. Hake die Sprache an, in der du Dead by Daylight spielst (mehrere gehen).':
        'The program reads the map name from the picture when a match starts. Tick the language you play Dead by Daylight in (several are fine).',
    'Die Karte erscheint beim Match-Start von selbst und verschwindet nach der Runde. „automatisch“ legt sie in den schwarzen Rand neben dem Spielbild (Ultrawide) bzw. neben das DBD-Fenster.':
        'The map appears by itself when a match starts and goes away after the round. "automatic" puts it into the black border next to the game picture (ultrawide) or next to the DBD window.',
    'Die wichtigsten Tasten – zum Ändern draufklicken und die neue Kombination drücken. Alle Tasten findest du später unter Einstellungen.':
        'The most important keys – click one to change it, then press the new combination. All keys are under Settings later.',
    '„Overlay testen“ zeigt die Karte sofort, „Mit der Maus verschieben“ lässt sie dich hinziehen.':
        '"Test overlay" shows the map right away, "Move with the mouse" lets you drag it into place.',
    'Einrichtung starten': 'Start setup',
    'Öffnet noch einmal die Einrichtung vom ersten Start: Spielsprache, Overlay-Position und die wichtigsten Tasten.':
        'Opens the setup of the first start again: game language, overlay position and the most important keys.',
    'Einstellung suchen (Strg+F)': 'Search settings (Ctrl+F)',
    'Einstellung suchen …': 'Search settings …',
    'Schritt {n} von {total}': 'Step {n} of {total}',
    'Sprache': 'Language',
    'Sprache dieses Programms:': 'Language of this program:',
    'Tasten und Start': 'Keys and start',
    'Weiter': 'Next',
    'Zurück': 'Back',
    'Überspringen': 'Skip',
    # 1.60: setup title, System sub-tab
    'Einrichtung: {step}': 'Setup: {step}',
    'Aufgeteilt': 'Broken down',
    'CPU-Temperatur': 'CPU temperature',
    'GPU gedrosselt': 'GPU throttled',
    'GPU-Leistung': 'GPU power',
    'GPU-Speicher': 'GPU memory',
    'GPU-Temperatur': 'GPU temperature',
    'Hotspot': 'Hot spot',
    'Höchstwert': 'Highest',
    'Höchstwerte': 'Highest values',
    'RAM': 'RAM',
    'Runden, zusammen {time}': 'rounds, {time} in all',
    'VRAM': 'VRAM',
    'Wert': 'Value',
    '{n} von {total}': '{n} of {total}',
    'Ø CPU-Temperatur': 'Avg. CPU temperature',
    'Ø GPU-Last': 'Avg. GPU load',
    'Ø GPU-Leistung': 'Avg. GPU power',
    'Ø GPU-Temperatur': 'Avg. GPU temperature',
    'über {n} Runden': 'over {n} rounds',
    # 1.61: overlay preview
    'Bilanz: Ø 2,8 Kills · 12 Runden': 'Record: avg. 2.8 kills · 12 rounds',
    'Klick auf Karte, Systemwerte oder Musik wählt das Element für den Regler „Grösse“. Mit „Mit der Maus verschieben“: Element ziehen = verschieben, an der Ecke ziehen oder Strg+Mausrad = Grösse, Klick auf eine freie Stelle setzt die Karte dorthin. Ende mit „Fertig“.':
        'A click on the map, the system values or the music picks the element for the “Size” slider. With “Move with the mouse”: drag an element = move it, drag its corner or Ctrl+mouse wheel = size, a click on an empty spot puts the map there. End with “Done”.',
    "Element": "Element",
    "Infos und Schrift (Name, Timer, Bilanz, Server)": "Info and text (name, timer, record, server)",
    # 1.8.24: the map's lines as an element of their own, the size slider marks where the bar stops it
    "Eigenes Element unter der Karte": "Own element below the map",
    "Eigenes Element über der Karte": "Own element above the map",
    "Eigenes Element, eigene Position": "Own element, own position",
    "Mit der Karte verbunden, unten": "Joined to the map, below",
    "Mit der Karte verbunden, oben": "Joined to the map, on top",
    "Infos": "Info",
    "INFOS": "INFO",
    "Infos (Timer, Bilanz, Server)": "Info (timer, record, server)",
    "In OBS ist der Wiederholungspuffer nicht aktiviert – OBS: Einstellungen → Ausgabe → "
    "Wiederholungspuffer → „Wiederholungspuffer aktivieren“ und übernehmen. Ohne ihn gibt es keine "
    "Sofort-Clips (F8) und keinen Vorlauf.":
        "OBS's replay buffer is not enabled – OBS: Settings → Output → Replay Buffer → \"Enable Replay Buffer\" "
        "and apply. Without it there are no instant clips (F8) and no pre-roll.",
    "Wiederholungspuffer in OBS nicht aktiviert (Einstellungen → Ausgabe → Wiederholungspuffer)":
        "Replay buffer not enabled in OBS (Settings → Output → Replay Buffer)",
    "Karten im selben Balken gleich breit (Systemwerte, Heute, Musik)":
        "Cards in the same bar at one width (system values, today, music)",
    "Zu einer Spalte zusammenführen": "Merge into one column",
    "Die Karten, die im selben schwarzen Balken stehen, werden so breit gezeichnet wie die breiteste von ihnen – "
    "untereinander ergeben sie eine Spalte mit bündigen Rändern.":
        "The cards standing in the same black bar are drawn as wide as the widest of them – one below the other "
        "they make a column with flush edges.",
    "Heute unter die Systemwerte, die Musik unter Heute, alle gleich breit – eine Spalte im Balken der "
    "Systemwerte. Rückgängig mit Strg+Z.":
        "Today below the system values, the music below today, all at one width – one column in the bar of the "
        "system values. Undo with Ctrl+Z.",
    "Cover": "Cover",
    "Discord-Overlay freihalten (Sprach-Widget unten links, Benachrichtigungen oben rechts, Text-Chat rechts)":
        "Keep Discord's overlay free (voice widget bottom left, notifications top right, text chat right)",
    "Karte, Infos, Systemwerte, Heute und Musik weichen den Stellen aus, an denen Discords Overlay seine Widgets "
    "zeigt (in der Vorschau schraffiert). Das Programm liest nichts aus Discord – die Flächen sind fest.":
        "Map, info, system values, today and music stay clear of the places where Discord's overlay shows its widgets "
        "(hatched in the preview). The program reads nothing from Discord – the areas are fixed.",
    "Wie der Stil": "Like the style",
    "Rund": "Round",
    "Eckig": "Square",
    "{what} ist hier schon so gross wie möglich – ab {cap} % ändert der Regler nichts mehr "
    "(der schwarze Balken ist voll).": "{what} is as big as it gets here – from {cap} % on the slider changes nothing "
                                       "(the black bar is full).",
    "Grösser mit „Karte darf grösser als der Balken werden“ (ragt dann ins Spielbild).":
        "Bigger with “The map may grow bigger than the bar” (it then reaches into the game picture).",
    'Spielbild': 'Game picture',
    'Map-Name': 'Map name',
    # 1.62: colour themes
    'Farbthema': 'Colour theme',
    'Gold (Standard)': 'Gold (default)',
    'Blutrot': 'Blood red',
    'Eisblau': 'Ice blue',
    'Giftgrün': 'Toxic green',
    'Lila': 'Purple',
    # 1.62: block "today" in the black bar; 1.2.6: a card of its own
    '„Heute“: Runden, Spielzeit, Ø Kills/Entkommen, Uhrzeit': '"Today": rounds, play time, avg. kills/escaped, clock',
    'Eine eigene Karte, solange eine Map im Match zu sehen ist: wie viele Runden du heute gespielt hast, wie '
    'lange, Ø Kills bzw. Entkommen laut Stats-Seite und die Uhrzeit. Position darunter, Grösse über den '
    'Grössenregler („Heute“ wählen).':
        'A card of its own while a map is on screen in a match: how many rounds you played today, for how long, '
        'avg. kills or escaped from the stats page and the time of day. Position below, size through the size '
        'slider (pick "Today").',
    'Dunkle Fläche hinter „Heute“': 'Dark area behind "Today"',
    'Vorlage': 'Preset',
    'Vorlage anwenden': 'Apply preset',
    'Alles links': 'Everything left',
    'Alles rechts': 'Everything right',
    'Verteilt: Karte links, Werte rechts': 'Spread: map left, values right',
    'Vorlage „{name}“ angewendet.': 'Preset "{name}" applied.',
    'Setzt Karte, Systemwerte, „Heute“ und Musik auf einmal auf die gewählte Anordnung. „Rückgängig“ holt '
    'die vorherige zurück.':
        'Puts map, system values, "Today" and music into the chosen arrangement at once. "Undo" brings the '
        'previous one back.',
    'Weich ein- und ausblenden (Karte, Systemwerte, Heute)': 'Fade in and out smoothly (map, system values, Today)',
    'Overlay in kleinen DBD-Fenstern ausblenden (Runden werden weiter gezählt und aufgenommen)': 'Hide the overlay in small DBD windows (rounds are still counted and recorded)',
    'Läuft DBD in einem kleinen Fenster (Bild kleiner als 1920×1080 oder schmaler als 16:9), zeigt das Programm im Spiel nichts – wie der Hauptschalter. Map-Erkennung, Statistik und OBS-Aufnahmen laufen weiter. Wird das Fenster wieder gross, erscheint das Overlay von selbst.': 'If DBD runs in a small window (picture smaller than 1920×1080 or narrower than 16:9), the program shows nothing in the game – like the master switch. Map detection, statistics and OBS recordings go on. When the window is big again, the overlay comes back by itself.',
    'Kleines DBD-Fenster ({w}×{h}) – Overlay ausgeblendet, Runden werden weiter gezählt und aufgenommen.': 'Small DBD window ({w}×{h}) – overlay hidden, rounds are still counted and recorded.',
    'Update gesperrt: eine Runde läuft. Nach dem Rundenende noch einmal auf „Aktualisieren und neu starten“ klicken.': 'Update locked: a round is running. Click “Update and restart” again after the round ends.',
    'DBD-Fenster wieder gross genug – Overlay wieder an.': 'DBD window big enough again – overlay back on.',
    'Overlay anzeigen (aus: nichts im Spiel, Erkennung läuft weiter)': 'Show the overlay (off: nothing in the game, detection goes on)',
    'Hauptschalter: aus = das Programm zeigt im Spiel nichts (Karte, Systemwerte, Heute, Musik). Erkennung, '
    'Statistik und Aufnahmen laufen weiter. Auch als Knopf in der Übersicht.':
        'Master switch: off = the program shows nothing in the game (map, system values, Today, music). Detection, '
        'statistics and recordings go on. Also a button on the overview.',
    'Overlay eingeschaltet.': 'Overlay switched on.',
    'Overlay ausgeschaltet – die Erkennung läuft weiter.': 'Overlay switched off – detection goes on.',
    'Overlay ausschalten': 'Switch overlay off',
    'Overlay einschalten': 'Switch overlay on',
    'Blendet alles aus, was das Programm im Spiel zeigt – Karte, Systemwerte, Heute, Musik. Die '
    'Erkennung, Statistik und Aufnahmen laufen weiter.':
        'Hides everything the program shows in the game – map, system values, Today, music. Detection, '
        'statistics and recordings go on.',
    'Zeigt das Overlay im Spiel wieder an.': 'Shows the overlay in the game again.',
    'Karte, Systemwerte und „Heute“ blenden in einer Drittelsekunde ein und aus, statt hart zu erscheinen. '
    'Die Musik hat ihr eigenes Häkchen.':
        'Map, system values and "Today" fade in and out within a third of a second instead of popping up. '
        'The music has a tick box of its own.',
    'Unter „Heute“': 'Below "Today"',
    'Unter der Musik': 'Below the music',
    'Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter „Heute“.':
        'A half-transparent dark area with rounded corners behind "Today".',
    'HEUTE': 'TODAY',
    'Heute': 'Today',
    'ENTKOMMEN ': 'ESCAPED ',
    'HEUTE ': 'TODAY ',
    'UHR ': 'TIME ',
    '{n} RUNDEN · {time}': '{n} ROUNDS · {time}',
    'Ø KILLS ': 'AVG. KILLS ',
    'NORMAL ': 'NORMAL ',
    'FARMING ': 'FARMING ',
    'Ø BP ': 'AVG. BP ',
    # 1.62.1: OLED black with every accent
    'OLED-Schwarz (echtes Schwarz statt Grau im Dark Mode)': 'OLED black (true black instead of grey in dark mode)',
    'Hintergründe in echtem Schwarz statt Dunkelgrau – passt zu OLED-Bildschirmen und geht mit jeder Akzentfarbe. Im hellen Modus ohne Wirkung.':
        'Backgrounds in true black instead of dark grey – suits OLED screens and goes with every accent colour. No effect in light mode.',
    # 1.63: colour palette + own colour
    'Eigene Farbe': 'Own colour',
    'Eigene Farbe …': 'Own colour …',
    'Beliebige Farbe wählen – das Programm passt die Helligkeit an, bis alles lesbar ist.':
        'Pick any colour – the program adjusts its brightness until everything is readable.',
    # 1.64: music in the black bar
    '„Läuft gerade“: Titel, Interpret und Cover der Musik (Spotify, Browser … – nur während sie spielt)':
        '"Now playing": title, artist and cover of the music (Spotify, browser … – only while it plays)',
    'Liest Titel und Interpret aus der Windows-Mediensteuerung (dieselbe Liste wie beim Lautstärkeregler von Windows) – nur Anzeige, das Programm steuert nichts und speichert nichts.':
        'Reads title and artist from the Windows media controls (the same list as the Windows volume flyout) – display only, the program controls nothing and stores nothing.',
    # 1.64: music card of its own
    'Unter den Systemwerten': 'Below the system values',
    'Rechts unten im Balken': 'Bottom right in the bar',
    'Links unten im Balken': 'Bottom left in the bar',
    'Musik': 'Music',
    'MUSIK': 'MUSIC',
    'läuft gerade': 'now playing',
    'Grösse Musik': 'Music size',
    'Albumcover zeigen': 'Show the album cover',
    "Auch Videos zeigen (YouTube, Twitch …) – aus: nur Musik": "Show videos too (YouTube, Twitch …) – off: music only",
    "Die Mediensteuerung meldet auch Videos aus dem Browser. An: ein Video erscheint als „▶ Titel“ mit dem Kanal darunter. Aus: die Karte zeigt nur Musik. Unterschieden wird am Album: Musikdienste melden eins, ein Video nicht.":
        "The media controls report browser videos too. On: a video appears as \"▶ Title\" with the channel below. Off: the card shows music only. Told apart by the album: music services report one, a video does not.",
    'Balken in der Farbe des Covers': "Bar in the cover's colour",
    'Dunkle Fläche hinter Karte und Infos': 'Dark area behind the map and its lines',
    'Dunkle Fläche hinter den Systemwerten': 'Dark area behind the system values',
    'Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Karte, Timer und Infozeilen (auch hinter '
    '„Warte auf Map“) – gut lesbar über hellen Stellen im Spiel.':
        'A half-transparent dark area with rounded corners behind map, timer and info lines (also behind '
        '"Waiting for map") – easy to read over bright parts of the game.',
    'Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Systemwerten und „Heute“.':
        'A half-transparent dark area with rounded corners behind the system values and "Today".',
    'Restzeit statt Länge (−1:46)': 'Time left instead of length (−1:46)',
    'Dunkle Fläche hinter der Musikkarte': 'Dark area behind the music card',
    'Weich ein- und ausblenden (auch beim nächsten Lied)': 'Fade in and out smoothly (also on the next song)',
    'Der Fortschrittsbalken nimmt die Hauptfarbe des Albumcovers an, wie bei Spotify. Graue Cover: weiss.':
        "The progress bar takes the album cover's main colour, like in Spotify. Grey covers: white.",
    'Rechts neben dem Balken steht, wie lange das Lied noch läuft, statt seiner Gesamtlänge.':
        'Right of the bar: how long the song still runs instead of its total length.',
    'Eine halb durchsichtige dunkle Fläche mit runden Ecken hinter Cover und Text – gut lesbar, wenn die '
    'Karte über hellen Stellen im Spiel liegt.':
        'A half-transparent dark area with rounded corners behind cover and text – easy to read when the card '
        'lies over bright parts of the game.',
    'Die Musikkarte blendet in einer Drittelsekunde ein und aus, statt hart zu erscheinen – auch wenn ein '
    'neues Lied beginnt.':
        'The music card fades in and out within a third of a second instead of popping up – also when a new '
        'song starts.',
    'Das Bild zum Lied links neben Titel und Interpret – Windows liefert es mit; es bleibt nur im Speicher.':
        'The picture of the song left of title and artist – Windows supplies it; it stays in memory only.',
    # 1.64.7: music card styles
    'Stil': 'Style',
    'Gross – Cover oben, Titel darunter': 'Large – cover on top, title below',
    'Kompakt – Cover links': 'Compact – cover left',
    'Fortschritt des Lieds zeigen (Zeit und Balken)': "Show the song's progress (time and bar)",
    'Unter Titel und Künstler: wie weit das Lied ist, mit Balken und Länge – wie in Spotify.':
        'Below title and artist: how far the song is, with a bar and its length – like in Spotify.',
    # 1.64.7: names while moving
    'KARTE · Strg+Mausrad = Grösse': 'MAP · Ctrl+wheel = size',
    'SYSTEMWERTE · HEUTE': 'SYSTEM VALUES · TODAY',
    'Karte': 'Map',
    'Systemwerte': 'System values',
    'Ziehst: {name}': 'Dragging: {name}',
    'Unter der Maus: {name}': 'Under the mouse: {name}',
    'Kartenstil': 'Map style',
    'Kartenstil: {style}.': 'Map style: {style}.',
    'Map wählen …': 'Choose map …',
    "Zur Seite Maps: eine Map von Hand anzeigen (Doppelklick oder „Anzeigen“). Beim nächsten Match übernimmt die automatische Erkennung wieder.":
        'To the Maps page: show a map by hand (double-click or "Show"). At the next match the automatic detection takes over again.',
    "Erscheint automatisch, sobald im Match das Map-Banner kommt – oder von Hand über „Map wählen“.":
        'Appears by itself as soon as the map banner comes in the match – or by hand with "Choose map".',
    'Wann zeigen': 'When to show',
    'Alle Maps': 'All maps',
    'Zuletzt gespielt': 'Played last',
    'Suchen: Name, Realm, Abkürzung …': 'Search: name, realm, abbreviation …',
    'Klick = groß ansehen · Doppelklick = jetzt anzeigen. Die Erkennung übernimmt beim nächsten Match wieder.':
        'Click = view big · double click = show now. Detection takes over again at the next match.',
    'Zurück zu den Karten des Realms (Esc).': "Back to the realm's maps (Esc).",
    'Allgemein': 'General',
    'Alle Einstellungen zurücksetzen': 'Reset all settings',
    'Alle Einstellungen auf die Auslieferung zurücksetzen? Runden, Match-Daten und eigene Bilder bleiben. Das '
    'Programm startet danach neu.': 'Reset every setting to the delivered state? Rounds, match data and own pictures '
                                     'stay. The program restarts afterwards.',
    'Alle Einstellungen zurückgesetzt.': 'All settings reset.',
    'Standard wiederherstellen': 'Restore default',
    'Ausschalten': 'Switch off',
    '{free} von {total} Regionen freigegeben': '{free} of {total} regions allowed',
    'DBD läuft gerade – die Änderung gilt erst nach einem Neustart von DBD.':
        'DBD is running – the change takes effect only after DBD restarts.',
    'Suchen …': 'Search …',
    'Setzt jede Einstellung auf die Auslieferung zurück (Overlay, Hotkeys, Erkennung, Server-Auswahl im Programm …). '
    'Runden, Match-Daten und eigene Bilder bleiben; das Programm startet danach neu. Vorher sichern: „Einstellungen '
    'exportieren“.': 'Resets every setting to the delivered state (overlay, hotkeys, detection, the region choice in '
                     'the program …). Rounds, match data and own pictures stay; the program restarts afterwards. '
                     'Back up first: "Export settings".',
    'Grösse {pct} %': 'size {pct} %',
    'eigenes Bild': 'own picture',
    'Eigene Einstellungen dieser Map: {what}': 'Own settings of this map: {what}',
    'Eigene Grösse und Drehung zurücksetzen': 'Reset own size and rotation',
    'Kartenbild ersetzen …': 'Replace map picture …',
    'Automatisch: im schwarzen Rand neben dem Spielbild bzw. neben dem DBD-Fenster. Frei platzieren: „Mit der Maus '
    'verschieben“.': 'Automatic: in the black bar next to the game picture or next to the DBD window. Place freely: '
                     '"Move with the mouse".',
    'Frei platzieren: „Mit der Maus verschieben“ oder Vorgabe „eigene Position“.':
        'Place freely: "Move with the mouse" or preset "own position".',
    'Im schwarzen Rand, solange die Karte im Match zu sehen ist. GPU-Werte von NVIDIA (Treiber), CPU-Temperatur nur '
    'mit HWiNFO („Shared Memory Support“ an) – kein eigener Treiber.':
        'In the black bar while the map is on screen in the match. GPU values from NVIDIA (driver), CPU temperature '
        'only with HWiNFO ("Shared Memory Support" on) – no driver of its own.',
    'Standard (wie ausgeliefert)': 'Standard (as delivered)',
    'Fenster {size}': 'window {size}',
    'alle Fenstergrössen': 'all window sizes',
    'Gilt für: {window}': 'Applies to: {window}',
    'Gilt für: {maps} · {window}': 'Applies to: {maps} · {window}',
    'nur {map}': 'only {map}',
    'alle Maps (keine Map eingeblendet)': 'all maps (no map on screen)',
    'Letzte 7 Tage': 'Last 7 days',
    'Letzte 30 Tage': 'Last 30 days',
    'Alle Maps': 'All maps',
    'Rolle/Killer': 'Role/killer',
    'Weitere 100 Runden anzeigen': 'Show 100 more rounds',
    'Als CSV exportieren …': 'Export as CSV …',
    'Runden exportieren': 'Export rounds',
    '{n} Runden exportiert: {path}': '{n} rounds exported: {path}',
    'Median': 'Median',
    '{n} Runden': '{n} rounds',
    'Längste': 'Longest',
    'Die Liste zeigt die neuesten 100 Runden der Auswahl; jeder Klick hängt 100 ältere an.':
        'The list shows the newest 100 rounds of the selection; every click appends 100 older ones.',
    'Speichert die Runden der aktuellen Filter als CSV (Semikolon, UTF-8) – mit Kills, Entkommen und Bloodpoints, '
    'soweit ein Match der Stats-Seite zugeordnet ist.': 'Saves the rounds of the current filters as CSV (semicolon, '
                                                        'UTF-8) – with kills, escapes and bloodpoints where a match '
                                                        'of the stats page is tied.',
    'Server-Tab öffnen': 'Open the server tab',
    'Match-Daten einrichten …': 'Set up match data …',
    'Kills und Entkommen kommen von der Stats-Seite': 'Kills and escapes come from the stats page',
    'Match-Daten': 'Match data',
    'Kills, Entkommen und Bloodpoints deiner Runden kommen von stats.deadbydaylight.com – geladen von deinem '
    'Browser, nicht vom Programm. Lässt sich auch später einrichten (Einstellungen → Mehr → Offizielle Match-Daten).':
        'Kills, escapes and bloodpoints of your rounds come from stats.deadbydaylight.com – loaded by your browser, '
        'not by the program. Can be set up later too (Settings → More → Official match data).',
    'Zum Tab Server: dort „Anzeigen, mit welchem Server DBD verbunden ist“ anhaken – Region und Ping stehen dann '
    'hier und im Overlay.': 'To the server tab: tick "Show which server DBD is connected to" there – region and '
                            'ping then show here and in the overlay.',
    'Zu Einstellungen → Mehr → Offizielle Match-Daten: einmal das Userscript in den Browser, danach zählen Kills, '
    'Entkommen und Bloodpoints in der Statistik.': 'To Settings → More → Official match data: the userscript into '
                                                   'the browser once, then kills, escapes and bloodpoints count in '
                                                   'the statistics.',
    'CPU DROSSELT (TEMP.)': 'CPU THROTTLED (TEMP.)',
    'CPU gedr.': 'CPU thr.',
    'GPU gedr.': 'GPU thr.',
    'CPU gedrosselt': 'CPU throttled',
    'CPU Ø W': 'CPU avg W',
    'CPU-Leistung': 'CPU power',
    'Kern Ø %': 'Core avg %',
    'Ø CPU-Leistung': 'Avg. CPU power',
    'Ø stärkster CPU-Kern': 'Avg. busiest CPU core',
    'Niedrigstes FPS-Tief': 'Lowest FPS low',
    'Ø FPS': 'Avg. FPS',
    'Ø FPS-Tief': 'Avg. FPS low',
    'FPS Ø': 'FPS avg',
    'FPS Tief': 'FPS low',
    'Klick: sortieren · Rechtsklick: Spalten ein-/ausblenden': 'Click: sort · right-click: show/hide columns',
    'Alle Spalten zeigen': 'Show all columns',
    # 1.4: recordings with OBS
    'Mehr (Match-Daten, Farming, OBS-Aufnahmen, Discord, Spotify, Sicherung, Ordner)': 'More (match data, farming, OBS recordings, Discord, Spotify, backup, folders)',
    'Aufnahmen mit OBS': 'Recordings with OBS',
    'Jede Runde mit OBS aufnehmen': 'Record every round with OBS',
    'Port': 'Port',
    'Passwort': 'Password',
    'Verbindung testen': 'Test connection',
    'Aufnahmeordner wählen …': 'Choose recording folder …',
    '(kein Ordner gewählt)': '(no folder chosen)',
    'Platz für Aufnahmen': 'Room for recordings',
    'Ganze Platte (Älteste weg, wenn sie voll wird)': 'Whole drive (oldest go when it fills up)',
    'Vorlauf: Wiederholungspuffer von OBS beim Map-Banner sichern (Sekunden davor)': 'Pre-roll: save OBS\'s replay buffer at the map banner (the seconds before it)',
    'OBS nimmt auf, das Programm sagt nur wann: Start beim Map-Banner, Stopp beim erkannten Rundenende, Datei nach Datum, Map und Killer benannt. Dafür in OBS unter Werkzeuge → WebSocket-Servereinstellungen den Server einschalten und das Passwort hier eintragen; Verbindung nur auf diesem PC (127.0.0.1). Empfohlen: Aufnahmeformat MKV oder Hybrid-MP4 (bleibt bei Abbruch lesbar), Fenster- oder Bildschirmaufnahme statt Spielaufnahme. Der Ordner wird über sein Laufwerk gemerkt – ist die Platte nicht angeschlossen, wird nicht aufgenommen.':
        'OBS records, the program only says when: start at the map banner, stop at the detected end of the round, file named after date, map and killer. In OBS enable the server under Tools → WebSocket Server Settings and enter its password here; the connection stays on this PC (127.0.0.1). Recommended: recording format MKV or hybrid MP4 (stays readable after a crash), window or display capture rather than game capture. The folder is remembered by its drive – with the drive unplugged nothing is recorded.',
    'Ordner für die Aufnahmen (z. B. auf der externen Platte)': 'Folder for the recordings (e.g. on the external drive)',
    'Aufnahmeordner: {path}': 'Recording folder: {path}',
    'Verbinde mit OBS …': 'Connecting to OBS …',
    'Aufnahme: {text}': 'Recording: {text}',
    'Aufnahme gespeichert: {file}': 'Recording saved: {file}',
    'Aufnahmen gelöscht (Platz): {n}': 'Recordings deleted (room): {n}',
    'OBS hat die Verbindung geschlossen': 'OBS closed the connection',
    'OBS nicht erreichbar – läuft OBS, ist der WebSocket-Server an? ({error})': 'OBS not reachable – is OBS running with its WebSocket server on? ({error})',
    'Keine Antwort von obs-websocket': 'No answer from obs-websocket',
    'Kein obs-websocket auf diesem Port': 'No obs-websocket on this port',
    'Falsche WebSocket-Antwort': 'Wrong WebSocket answer',
    'Unerwartete Begrüssung von OBS': 'Unexpected greeting from OBS',
    'OBS verlangt ein Passwort (OBS: Werkzeuge → WebSocket-Servereinstellungen)': 'OBS wants a password (OBS: Tools → WebSocket Server Settings)',
    'OBS hat die Anmeldung abgelehnt – Passwort falsch?': 'OBS refused the login – wrong password?',
    'Fehler: {error}': 'Error: {error}',
    'OBS {version} verbunden': 'OBS {version} connected',
    'nimmt gerade auf': 'recording now',
    'bereit': 'ready',
    'Wiederholungspuffer läuft': 'replay buffer running',
    'Wiederholungspuffer aus (kein Vorlauf)': 'replay buffer off (no pre-roll)',
    'Ordner: {folder}': 'Folder: {folder}',
    'Ordner/Laufwerk nicht gefunden': 'folder/drive not found',
    'Aufnahme-Laufwerk nicht angeschlossen – Runde wird nicht aufgenommen': 'Recording drive not connected – the round is not recorded',
    'Aufnahme-Laufwerk fast voll – Runde wird nicht aufgenommen': 'Recording drive almost full – the round is not recorded',
    'OBS nimmt schon auf (von Hand?) – nichts gestartet': 'OBS is already recording (by hand?) – nothing started',
    'Nimmt die Runde auf': 'Recording the round',
    'OBS hat keinen Dateinamen genannt – Aufnahme nicht zugeordnet': 'OBS gave no file name – recording not assigned',
    "Aufnahme liegt in OBS' eigenem Ordner: {path}": "Recording is in OBS's own folder: {path}",
    'Gespeichert: {file}': 'Saved: {file}',
    'Das Programm startet die OBS-Aufnahme beim Map-Banner und stoppt sie beim erkannten Rundenende (obs-websocket, nur auf diesem PC). OBS muss laufen.': 'The program starts the OBS recording at the map banner and stops it at the detected end of the round (obs-websocket, on this PC only). OBS must be running.',
    'Verbindet sich einmal mit OBS und zeigt Version, Aufnahmezustand, Wiederholungspuffer und ob der Aufnahmeordner erreichbar ist.': 'Connects to OBS once and shows its version, whether it records, the replay buffer and whether the recording folder is reachable.',
    'Ordner, in den OBS die Runden legt – z. B. auf der externen Platte. Gemerkt wird das Laufwerk, nicht der Buchstabe: bekommt die Platte einen anderen, findet das Programm den Ordner trotzdem.': 'Folder OBS puts the rounds in – e.g. on the external drive. The drive is remembered, not its letter: if the drive gets another one, the program still finds the folder.',
    'Läuft in OBS der Wiederholungspuffer, wird er beim Map-Banner gespeichert – der Anfang (Spawn) fehlt dann nicht, aber die Datei enthält auch Lobby und Ladebildschirm. Seit 1.5.5 standardmässig aus (Wunsch des Nutzers: nur die Runde). Die Datei liegt als „(Vorlauf)“ neben der Runde.': 'If OBS\'s replay buffer is running, it is saved at the map banner – the start (spawn) is not missing then, but the file also holds the lobby and the loading screen. Off by default since 1.5.5 (user\'s wish: the round only). The file lies next to the round as "(Vorlauf)".',
    # 1.4.1
    'Wiederholungspuffer mit DBD starten und stoppen': "Start and stop the replay buffer with DBD",
    "Nur das DBD-Fenster aufnehmen (Fensteraufnahme in OBS selbst einrichten)":
        "Record only the DBD window (set up a window capture in OBS)",
    "Bildquelle angelegt: {name} (Szene „{scene}“)": "Picture source created: {name} (scene \"{scene}\")",
    "Bildquelle in der Szene „{scene}“ ausgeblendet: {name}": "Picture source hidden in the scene \"{scene}\": {name}",
    "Bildquelle zur Szene „{scene}“ hinzugefügt: {name}": "Picture source added to the scene \"{scene}\": {name}",
    "Bildquelle in der Szene „{scene}“ wieder eingeblendet: {name}":
        "Picture source shown again in the scene \"{scene}\": {name}",
    "Bildquelle {name} zeigt jetzt {exe}": "Picture source {name} now shows {exe}",
    "DBD-Fenster in OBS nicht eingerichtet: {error}": "DBD window not set up in OBS: {error}",
    "OBS konnte den Wiederholungspuffer nicht starten (OBS meldet einen Fehler der Ausgabe, meist des Kodierers – Details im OBS-Log). Das Programm versucht es erst beim nächsten DBD-Start wieder; bis dahin keine Sofort-Clips (F8) und kein Vorlauf.":
        "OBS could not start the replay buffer (OBS reports an output error, mostly the encoder – details in the OBS log). The program tries again only at the next DBD start; until then no instant clips (F8) and no pre-roll.",
    "Das Programm legt in OBS eine Fensteraufnahme „DbD Map Scout – DBD-Fenster“ an (oben in der laufenden Szene, auf die Leinwand eingepasst) und stellt sie auf Steam, Epic oder Store um. Aufgenommen wird dann nur das Spiel – ohne Discord, Benachrichtigungen und ohne das Overlay dieses Programms. OBS nimmt über Windows auf (wie die Fensteraufnahme), nicht über die Spielaufnahme, die sich ins Spiel hängt. Aus: die Quelle wird nur ausgeblendet, deine eigene Bildschirmaufnahme bleibt unangetastet.":
        "The program creates a window capture \"DbD Map Scout – DBD-Fenster\" in OBS (on top of the scene on air, fitted to the canvas) and switches it to Steam, Epic or the Store. Only the game is recorded then – without Discord, notifications and without this program's overlay. OBS captures through Windows (like the window capture), not through game capture, which hooks into the game. Off: the source is only hidden, your own display capture stays untouched.",
    'Das Programm startet den Wiederholungspuffer in OBS, sobald DBD läuft, und stoppt ihn, wenn DBD zu ist – so kostet er ausserhalb des Spiels nichts und du musst nicht daran denken.': "The program starts OBS's replay buffer as soon as DBD runs and stops it when DBD is closed – so it costs nothing outside the game and you need not think of it.",
    'Nachlauf nach dem Rundenende': 'Tail after the end of the round',
    '{n} s': '{n} s',
    'keiner': 'none',
    'Aufnahme-Laufwerk nicht angeschlossen – die Runden werden nicht aufgenommen.': 'Recording drive not connected – the rounds are not recorded.',
    'OBS läuft nicht – die Runden werden nicht aufgenommen. ({error})': 'OBS is not running – the rounds are not recorded. ({error})',
    'OBS bereit – Runden werden aufgenommen': 'OBS ready – rounds are recorded',
    'Aufnahme sieht beschädigt aus ({why}): {file} – OBS-Einstellungen prüfen (Encoder, Platte).': 'Recording looks broken ({why}): {file} – check the OBS settings (encoder, drive).',
    'Aufnahme': 'Recording',
    # 1.4.2
    'Vorlauf und Runde zu einer Datei zusammenfügen': 'Join pre-roll and round into one file',
    'Nach der Runde hängt ffmpeg den Vorlauf vorne an die Aufnahme – ohne Neukodierung, in Sekunden. Seit 1.5.5 standardmässig aus: Am PC des Nutzers lief der Rundenteil der zusammengefügten Datei zu schnell. Klappt es nicht, bleiben beide Dateien liegen.': 'After the round ffmpeg puts the pre-roll in front of the recording – no re-encoding, seconds of work. Off by default since 1.5.5: on the user\'s PC the round part of the joined file played too fast. If it fails, both files stay.',
    'ffmpeg fehlt (Paket imageio-ffmpeg) – start.bat installiert es beim nächsten Start; bis dahin bleibt der Vorlauf eine eigene Datei.': 'ffmpeg is missing (package imageio-ffmpeg) – start.bat installs it on the next start; until then the pre-roll stays a file of its own.',
    'Gespeichert: {file} – Vorlauf nicht angefügt, liegt als eigene Datei daneben': 'Saved: {file} – pre-roll not joined, lies next to it as its own file',
    'Clip-Marke setzen': 'Set clip mark',
    'Clip-Marke {n} bei {pos} gesetzt.': 'Clip mark {n} set at {pos}.',
    'Keine Aufnahme läuft – keine Clip-Marke gesetzt.': 'No recording is running – no clip mark set.',
    'Aufnahmen': 'Recordings',
    'Aufnahmen einrichten …': 'Set up recordings …',
    'Öffnet die Einstellungen für die Aufnahmen mit OBS (Ordner, Verbindung).': 'Opens the settings for the recordings with OBS (folder, connection).',
    'Platte nicht angeschlossen': 'drive not connected',
    'kein Ordner gewählt': 'no folder chosen',
    'Platz wird gemessen …': 'measuring room …',
    '1 Runde': '1 round',
    '{n} mit Marke': '{n} with a mark',
    'älteste {date}': 'oldest {date}',
    '{size} frei': '{size} free',
    # 1.5 – tab "Aufnahmen"
    '1 Aufnahme': '1 recording',
    '{n} Aufnahmen': '{n} recordings',
    'Abspielen': 'Play',
    'Alle Aufnahmen': 'All recordings',
    'Aufnahme fehlt: {file}': 'Recording missing: {file}',
    'Aufnahme gelöscht: {file}': 'Recording deleted: {file}',
    'Aufnahme ist aus.': 'Recording is off.',
    'Aufnahme löschen': 'Delete recording',
    'Aufnahme nicht gelöscht ({error}): {file}': 'Recording not deleted ({error}): {file}',
    'Aufnahme wird behalten: {file}': 'Recording is kept: {file}',
    'Aufnahme wird nicht mehr behalten: {file}': 'Recording is no longer kept: {file}',
    'Aufnahme-Laufwerk nicht angeschlossen.': 'Recording drive not connected.',
    'Aufnahmeordner öffnen': 'Open recording folder',
    'Behalten': 'Keep',
    'Beschädigt': 'Broken',
    'Datei': 'File',
    'Einschalten unter Einstellungen → Mehr → Aufnahmen mit OBS.': 'Turn it on under Settings → More → Recordings with OBS.',
    'Im Explorer zeigen': 'Show in Explorer',
    'Keine Marken – F8 während der Runde setzt eine.': 'No marks – F8 during the round sets one.',
    'Marken': 'Marks',
    'Marken: {list}': 'Marks: {list}',
    'Mit Marke': 'With a mark',
    'Nicht mehr behalten': 'Stop keeping',
    'Noch kein Aufnahmeordner gewählt.': 'No recording folder chosen yet.',
    'OBS nimmt jede Runde auf (Einstellungen → Mehr → Aufnahmen mit OBS). F8 setzt während der Runde eine Marke; „Behalten“ schützt eine Aufnahme vor dem Aufräumen, wenn die Platte Platz braucht.': 'OBS records every round (Settings → More → Recordings with OBS). F8 sets a mark during the round; "Keep" protects a recording from the clean-up when the drive needs room.',
    'fehlt': 'missing',
    '{file} von der Platte löschen?': 'Delete {file} from the drive?',
    'Spielt die markierte Aufnahme im Standard-Videoplayer ab.': 'Plays the marked recording in the default video player.',
    'Öffnet den Explorer mit der markierten Datei.': 'Opens Explorer with the marked file selected.',
    'Eine behaltene Aufnahme wird nie fürs Aufräumen gelöscht, wenn die Platte Platz braucht. Nochmal drücken hebt es auf.': 'A kept recording is never deleted by the clean-up when the drive needs room. Press again to undo.',
    'Löscht die markierte Aufnahme (und ihren Vorlauf) von der Platte – nach Rückfrage.': 'Deletes the marked recording (and its pre-roll) from the drive – after a confirmation.',
    'Öffnet den Aufnahmeordner im Explorer.': 'Opens the recording folder in Explorer.',
    # 1.5.3 – farming subfolder
    'Farming-Runden im Unterordner „Farming“ ablegen': 'Put farming rounds into the subfolder "Farming"',
    'Runden, die das Programm als Farming erkennt (Crossplay aus oder die Farming-Region), landen im Unterordner „Farming“ des Aufnahmeordners statt zwischen den normalen Runden. Clips gehen immer in den Ordner „Clips“.': 'Rounds the program recognises as farming (cross-play off or the farming region) land in the subfolder "Farming" of the recording folder instead of among the normal rounds. Clips always go into the folder "Clips".',
    # 1.5.4 – several rows, cross-play diagnosis
    'Crossplay-Anzeige nicht lesbar – die Runde zählt nicht als Farming (Ausschnitt in debug/lobby).': 'Cross-play indicator not readable – the round does not count as farming (crop in debug/lobby).',
    'Rolle für {n} Runden auf {role} geändert.': 'Role of {n} rounds changed to {role}.',
    '{n} Runden aus der Statistik löschen?': 'Delete {n} rounds from the statistics?',
    '{n} Runden gelöscht.': '{n} rounds deleted.',
    '{n} Runden zählen jetzt als Farming-Runden.': '{n} rounds now count as farming rounds.',
    '{n} Runden zählen wieder als normale Runden.': '{n} rounds count as normal rounds again.',
    # 1.5.1 – clip editor
    'Clip bearbeiten …': 'Edit clip …',
    'Öffnet den Clip-Editor für die markierte Aufnahme: Vorschau, Zeitleiste mit Marken, Start/Ende setzen, Ausschnitt als MP4 in den Ordner „Clips“ speichern.': 'Opens the clip editor for the marked recording: preview, timeline with marks, set start/end, save the cut as MP4 into the folder "Clips".',
    'Clip bearbeiten – {name}': 'Edit clip – {name}',
    'Schnell (an Schlüsselbildern, Anfang bis zu ein paar Sekunden früher)': 'Fast (at key frames, the start may be a few seconds early)',
    'Genau (Bild neu kodiert, dauert etwas)': 'Exact (picture re-encoded, takes a moment)',
    '1 Sekunde vor (→)': '1 second forward (→)',
    '1 Sekunde zurück (←)': '1 second back (←)',
    '5 Sekunden vor (Shift+→)': '5 seconds forward (Shift+→)',
    '5 Sekunden zurück (Shift+←)': '5 seconds back (Shift+←)',
    '▶ Abspielen': '▶ Play',
    '⏸ Pause': '⏸ Pause',
    'Abspielen / Pause (Leertaste)': 'Play / pause (space bar)',
    'Start setzen': 'Set start',
    'Ende setzen': 'Set end',
    'Der Clip beginnt am Abspielkopf (Taste I).': 'The clip starts at the playhead (key I).',
    'Der Clip endet am Abspielkopf (Taste O).': 'The clip ends at the playhead (key O).',
    'Zur Marke ▸': 'To mark ▸',
    'Springt zur nächsten F8-Marke (Taste M).': 'Jumps to the next F8 mark (key M).',
    'Clip: {start} – {end} ({length} s)': 'Clip: {start} – {end} ({length} s)',
    'Ton': 'Sound',
    'Beim Abspielen den Ton der Aufnahme mitlaufen lassen (Windows).': 'Play the sound of the recording along with the preview (Windows).',
    'Ton im Clip': 'Sound in the clip',
    'Abspielkopf hierher': 'Playhead here',
    'Als Custom Game': 'As custom game',
    'Als Killer-Runde': 'As killer round',
    'Als Survivor-Runde': 'As survivor round',
    'Ausblenden': 'Hide',
    'Bild': 'Picture',
    'Clip beginnt hier': 'Clip starts here',
    'Clip endet hier': 'Clip ends here',
    'Dunkle Fläche dahinter': 'Dark area behind it',
    'Grösse zurücksetzen': 'Reset size',
    'Standbild gespeichert: {file}': 'Still picture saved: {file}',
    'Standbild hier speichern': 'Save a still picture here',
    'Standbild nicht gespeichert.': 'Still picture not saved.',
    '{n} Runden löschen': 'Delete {n} rounds',
    'Grosser Editor …': 'Large editor …',
    'Öffnet den Clip im eigenen Fenster – mit Zensieren, Lautstärke je Tonquelle und allen Tasten.': 'Opens the clip in its own window – with censoring, a level per sound source and all keys.',
    'Discord-Sprachchat – OBS-Spur 3. Aus = der Clip hat keinen Discord-Ton.': 'Discord voice chat – OBS track 3. Off = the clip has no Discord sound.',
    'Dein Mikrofon – OBS-Spur 4 (nur, wenn es in OBS aufgenommen wird).': 'Your microphone – OBS track 4 (only when OBS records it).',
    'Lautstärke dieser Quelle im Clip (100 % = wie aufgenommen).': 'Level of this source in the clip (100 % = as recorded).',
    'Eine Tonspur – zum Mischen nimmt OBS mit Spur 1–4 auf (Einstellungen → Mehr → Aufnahmen mit OBS).': 'One audio track – for mixing, OBS records with tracks 1–4 (Settings → More → Recordings with OBS).',
    'ohne Ton': 'without sound',
    'Ton neu gemischt': 'sound remixed',
    'Clip speichern': 'Save clip',
    'Schreibt den Ausschnitt als MP4 in den Ordner „Clips“ neben den Aufnahmen.': 'Writes the cut as MP4 into the folder "Clips" next to the recordings.',
    'Clips-Ordner öffnen': 'Open clips folder',
    'Öffnet den Ordner „Clips“ im Explorer.': 'Opens the folder "Clips" in Explorer.',
    'Datei nicht lesbar oder ffmpeg fehlt – keine Vorschau.': 'File not readable or ffmpeg missing – no preview.',
    'Clips-Ordner nicht anlegbar: {error}': 'Clips folder cannot be created: {error}',
    'Schreibe {file} …': 'Writing {file} …',
    'Clip gespeichert: {file}': 'Clip saved: {file}',
    'Clip nicht gespeichert: {why}': 'Clip not saved: {why}',
    '(Sofort-Clip)': '(instant clip)',
    'Aufnahme schon am Ende des Ladebildschirms starten (mit Spawn)': 'Start recording at the end of the loading screen (with the spawn)',
    'Aufnahme-Laufwerk nicht angeschlossen': 'Recording drive not connected',
    'Clip': 'Clip',
    'DBD': 'DBD',
    'Discord': 'Discord',
    'F8 speichert die letzten Sekunden als Sofort-Clip': 'F8 saves the last seconds as an instant clip',
    'Kein Sofort-Clip: {why}': 'No instant clip: {why}',
    'Ladebildschirm vorbei – das Match beginnt.': 'Loading screen over – the match begins.',
    'Mikrofon': 'Microphone',
    'Spiel': 'Game',
    'Nimmt auf – seit dem Ende des Ladebildschirms, wartet auf das Map-Banner': 'Recording – since the end of the loading screen, waiting for the map banner',
    'Nimmt die Runde auf (seit dem Ladebildschirm)': 'Recording the round (since the loading screen)',
    'OBS hat den Puffer nicht gespeichert': 'OBS did not save the buffer',
    'Sofort-Clip gespeichert ({n} s): {file}': 'Instant clip saved ({n} s): {file}',
    'Ton in OBS einstellen, sobald DBD startet:': 'Set the sound in OBS as soon as DBD starts:',
    'Ton in OBS nicht eingestellt: {error}': 'Sound in OBS not set: {error}',
    'OBS bereit – Runden werden aufgenommen. {problem}': 'OBS ready – rounds are recorded. {problem}',
    'Für die Tonmischung im Clip-Editor in OBS: Einstellungen → Ausgabe → Ausgabemodus „Erweitert“ → Reiter Aufnahme → Audiospur 1 bis 5 anhaken (1 alles, 2 Spiel, 3 Discord, 4 Mikrofon, 5 Hintergrund)': 'For the sound mix in the clip editor, in OBS: Settings → Output → Output mode "Advanced" → tab Recording → tick audio tracks 1 to 5 (1 everything, 2 game, 3 Discord, 4 microphone, 5 background)',
    'Jede Tonquelle auf eine eigene OBS-Tonspur legen (1 alles, 2 nur DBD, 3 Discord, 4 Mikrofon, 5 Hintergrund) – zum Mischen im Clip-Editor': 'Put every sound source on its own OBS audio track (1 everything, 2 DBD only, 3 Discord, 4 microphone, 5 background) – for mixing in the clip editor',
    'Dafür in OBS: Einstellungen → Ausgabe → Ausgabemodus „Erweitert“ → Reiter Aufnahme → Audiospur 1 bis 5 anhaken. Das Programm prüft das beim DBD-Start und meldet es im Status unten; es ändert nichts am OBS-Profil.': 'For this, in OBS: Settings → Output → Output mode "Advanced" → tab Recording → tick audio tracks 1 to 5. The program checks this when DBD starts and reports it in the status below; it changes nothing in the OBS profile.',
    'Sofort-Clip (F8) mit Ton von:': 'Instant clip (F8) with sound from:',
    'Wie bei Medal: Das Programm weist in OBS jede Tonquelle der Spur 1 (alles – spielt in jedem Player) und ihrer eigenen Spur zu: nur DBD 2, Discord 3, Mikrofon 4, alle anderen Tonquellen in OBS (z. B. Spotify, Browser) 5 = Hintergrund. Der Desktop-Ton von Windows enthält auch DBD und Discord und liegt deshalb nur auf Spur 1. Im Clip-Editor schaltest du jede Quelle an oder aus und regelst ihre Lautstärke; beim Speichern mischt ffmpeg sie zusammen. OBS schreibt die Spuren nur im Ausgabemodus „Erweitert“ mit Audiospur 1 bis 5 angehakt (MKV oder MP4, nicht FLV); das Programm prüft das beim DBD-Start und meldet es, ändert aber nichts am OBS-Profil. Aus = Spuren bleiben, wie sie in OBS stehen.': 'Like Medal: the program assigns every sound source in OBS to track 1 (everything – plays in any player) and to its own track: DBD only 2, Discord 3, microphone 4, every other sound source in OBS (e.g. Spotify, browser) 5 = background. Windows\' desktop sound holds DBD and Discord too and therefore sits on track 1 only. In the clip editor you switch each source on or off and set its level; ffmpeg mixes them when saving. OBS writes the tracks only in the output mode "Advanced" with audio tracks 1 to 5 ticked (MKV or MP4, not FLV); the program checks this when DBD starts and reports it, but changes nothing in the OBS profile. Off = the tracks stay as set in OBS.',
    'Nur der Ton von DBD im Sofort-Clip.': 'Only the sound of DBD in the instant clip.',
    'Ton von Discord (Sprachchat) in der Aufnahme bzw. im Sofort-Clip.': 'Sound from Discord (voice chat) in the recording or the instant clip.',
    'Dein Mikrofon – die Quelle „Mikrofon/AUX“ in OBS bzw. seine Spur im Sofort-Clip.': 'Your microphone – the source "Mic/Aux" in OBS, or its track in the instant clip.',
    'Hintergrund': 'Background',
    'Andere Programme mit eigener Tonquelle in OBS (z. B. Spotify, Browser) – OBS-Spur 5. Der Desktop-Ton von Windows enthält auch DBD und Discord und liegt nur auf Spur 1.': "Other programs with a sound source of their own in OBS (e.g. Spotify, browser) – OBS track 5. Windows' desktop sound holds DBD and Discord too and sits on track 1 only.",
    'Andere Programme mit eigener Tonquelle in OBS (z. B. Spotify, Browser) im Sofort-Clip – OBS-Spur 5.': 'Other programs with a sound source of their own in OBS (e.g. Spotify, browser) in the instant clip – OBS track 5.',
    'Tonquelle angelegt: {name}': 'Sound source created: {name}',
    'Farming-Aufnahmen löschen nach': 'Delete farming recordings after',
    'nie': 'never',
    '{n} Tagen': '{n} days',
    'Alte Farming-Aufnahmen gelöscht (älter als {days} Tage): {n}': 'Old farming recordings deleted (older than {days} days): {n}',
    '{name} – keine Quelle': '{name} – no source',
    '{name} – in OBS aus': '{name} – off in OBS',
    'In OBS gab es bei dieser Aufnahme keine Hintergrund-Quelle. Für Spotify, Browser & Co. in OBS je Programm eine Anwendungs-Audioaufnahme anlegen – das Programm legt sie auf Spur 5.': 'OBS had no background source for this recording. For Spotify, the browser & co. add an application audio capture per program in OBS – the program puts it on track 5.',
    'Diese Tonquelle war bei der Aufnahme unter Einstellungen → Mehr → Aufnahmen mit OBS ausgeschaltet.': 'This sound source was switched off under Settings → More → Recordings with OBS when this was recorded.',
    'Tonquelle {name} hört jetzt auf {exe}': 'Sound source {name} now listens to {exe}',
    'Auf Spur 5 (Hintergrund) statt bei Spiel/Discord/Mikrofon: {names}': 'On track 5 (background) instead of with game/Discord/microphone: {names}',
    'Auf Spur {n} ist in der ganzen Aufnahme nichts zu hören.': 'Nothing can be heard on track {n} in the whole recording.',
    'Tonquelle zur Szene „{scene}“ hinzugefügt: {name}': 'Sound source added to the scene "{scene}": {name}',
    'Tonquelle in der Szene „{scene}“ wieder eingeblendet: {name}': 'Sound source shown again in the scene "{scene}": {name}',
    '{name} (Spur {n})': '{name} (track {n})',
    'Still in dieser Aufnahme: {names} – OBS hat dort nichts aufgenommen. In OBS prüfen: Quelle in der Szene der Aufnahme, nicht stumm, Spur angehakt.': 'Silent in this recording: {names} – OBS recorded nothing there. Check in OBS: source in the scene being recorded, not muted, track ticked.',
    '{name} – still': '{name} – silent',
    'Nur der Ton von Dead by Daylight – OBS-Spur 2.': 'Only the sound of Dead by Daylight – OBS track 2.',
    'Unbekannte Map': 'Unknown map',
    'Wiederholungspuffer in OBS läuft nicht': "OBS's replay buffer is not running",
    'Übriger Desktop-Ton': 'Other desktop sound',
    'Das Map-Banner kommt erst einige Sekunden nach dem Spawn. Mit diesem Häkchen startet OBS schon, wenn der Ladebildschirm nach der Lobby endet – ohne Lobby, mit Spawn. Das Banner benennt die Aufnahme danach. Kommt 3 Minuten lang kein Banner, endet die Aufnahme und heisst „Unbekannte Map“.': 'The map banner comes a few seconds after the spawn. With this box OBS starts as soon as the loading screen after the lobby ends – no lobby, with the spawn. The banner names the recording afterwards. Without a banner for 3 minutes the recording ends and is called "Unknown map".',
    'F8 sichert den Wiederholungspuffer von OBS und legt die letzten Sekunden als MP4 in den Ordner „Clips“ – ohne Neukodierung, in Sekunden. Der Wiederholungspuffer muss in OBS eingerichtet sein. Die Marke in der Rundenaufnahme setzt F8 weiterhin.': 'F8 saves OBS\'s replay buffer and puts its last seconds as an MP4 into the folder "Clips" – no re-encoding, seconds of work. The replay buffer has to be set up in OBS. F8 still sets the mark in the round recording.',
    'Das Programm legt in der aktuellen OBS-Szene je eine Anwendungs-Audioaufnahme für DBD und Discord an (einmalig) und schaltet die Tonquellen wie gewählt stumm oder laut – beim Start von DBD und bei jeder Änderung hier, auch mitten in der Runde. Aufnehmen tut OBS, das Programm fasst DBD nicht an. Braucht OBS 28 oder neuer.': 'The program creates one application audio capture each for DBD and Discord in the current OBS scene (once) and mutes or unmutes the sound sources as chosen – when DBD starts and on every change here, also mid-round. OBS does the capture, the program does not touch DBD. Needs OBS 28 or newer.',
    'Ton des Spiels in der Aufnahme.': "The game's sound in the recording.",
    'Alles andere, was am PC zu hören ist (Musik, Browser, Systemtöne) – die Quelle „Desktop-Audio“ in OBS.': 'Everything else you hear on the PC (music, browser, system sounds) – OBS\'s source "Desktop Audio".',
    'Als Farming markieren': 'Mark as farming',
    'Discord: ohne Nitro 10 MB, Nitro Basic 50 MB, Nitro 500 MB.': 'Discord: 10 MB without Nitro, Nitro Basic 50 MB, Nitro 500 MB.',
    'Format': 'Format',
    'Für Discord (passt unter die Zielgrösse)': 'For Discord (fits under the target size)',
    'Gespeichert: {file} ({mb} MB)': 'Saved: {file} ({mb} MB)',
    'Ignorieren': 'Ignore',
    'Kodiere {file} … (dauert etwas)': 'Encoding {file} … (takes a while)',
    'Runden nicht geändert: {error}': 'Rounds not changed: {error}',
    'Spielt genau den Ausschnitt ab und springt danach an seinen Anfang zurück.': 'Plays exactly the clip and then jumps back to its start.',
    'Zeigt den zuletzt gespeicherten Clip im Explorer.': 'Shows the clip saved last in Explorer.',
    '{n} Runden als Farming markiert.': '{n} rounds marked as farming.',
    '{n} Runden als Farming-Runden markieren?': 'Mark {n} rounds as farming rounds?',
    '{n} Runden sind als Custom Game gespeichert, laut Stats-Seite waren es aber öffentliche Matches – vermutlich Farming mit Crossplay aus (vor 1.5.5 als Custom Game erkannt). Zuletzt: {map}, {when}.': '{n} rounds are saved as custom games, but the stats page lists them as public matches – probably farming with cross-play off (recognised as custom games before 1.5.5). Last: {map}, {when}.',
    'etwa {mb} MB': 'about {mb} MB',
    'wird {h}p {fps} fps, ≈ {kbps} kbit/s, unter {mb} MB': 'becomes {h}p {fps} fps, ≈ {kbps} kbit/s, under {mb} MB',
    '≤ {n} MB': '≤ {n} MB',
    '▶ Clip ansehen': '▶ Watch clip',
    'Markiert alle genannten Runden als Farming-Runden (und nicht mehr als Custom Game); ihre Aufnahmen wandern in den Ordner „Farming“. Einzeln zurück: „Farming an/aus“ unter „Letzte Runden“.': 'Marks all these rounds as farming rounds (no longer custom games); their recordings move into the folder "Farming". One by one back: "Farming on/off" under "Last rounds".',
    'Diese Runden nicht mehr vorschlagen – sie bleiben, wie sie sind.': 'Do not suggest these rounds again – they stay as they are.',
    'Alle': 'All',
    'BP/h': 'BP/h',
    'BP/h mit Wartezeit': 'BP/h with waiting',
    'Bloodpoints': 'Bloodpoints',
    'Bloodpoints laut Stats-Seite. BP/h = je Stunde im Match; mit Wartezeit = je Stunde aus Match und Suche zusammen. Mit dem Rollen-Filter „Farming“ steht hier, was das Farmen bringt.': 'Bloodpoints from the stats page. BP/h = per hour in the match; with waiting = per hour of match and search together. With the role filter "Farming" this shows what farming earns.',
    'Bloodpoints pro Stunde': 'Bloodpoints per hour',
    'Summe': 'Total',
    'mit Wartezeit {bp}': 'with waiting {bp}',
    # ------------------------------------------------------------------ 1.7: records, Discord
    'Rekorde': 'Records',
    'Serien zählen Runden mit Ergebnis laut Stats-Seite in zeitlicher Reihenfolge – „aktuell“ ist die Serie der neuesten Runden der Auswahl. Beste Woche ab {n} Runden mit Ergebnis. Eine Sitzung endet nach 45 Minuten ohne Runde.': 'Streaks count rounds with a result from the stats page in order of time – "current" is the streak of the newest rounds of the selection. Best week from {n} rounds with a result. A session ends after 45 minutes without a round.',
    'Noch keine Runden in dieser Auswahl.': 'No rounds in this selection yet.',
    'aktuell {n}': 'current {n}',
    'zuletzt {date}': 'last {date}',
    '4K-Serie': '4K streak',
    'Entkommen-Serie': 'Escape streak',
    'Beste Woche als Killer': 'Best week as killer',
    'ab {date} · {n} Runden': 'from {date} · {n} rounds',
    'ab {n} Killer-Runden in einer Woche': 'from {n} killer rounds in one week',
    'Beste Woche als Survivor': 'Best week as survivor',
    'ab {n} Survivor-Runden in einer Woche': 'from {n} survivor rounds in one week',
    'Meiste Runden an einem Tag': 'Most rounds in a day',
    'Längste Sitzung': 'Longest session',
    'Längste Runde': 'Longest round',
    'Spielstatus in Discord anzeigen (Rich Presence)': 'Show the game status in Discord (Rich Presence)',
    'Application-ID': 'Application ID',
    'Discord testen': 'Test Discord',
    'Developer-Portal öffnen': 'Open developer portal',
    'Killer in Discord anzeigen': 'Show the killer in Discord',
    'Auch Lobby, Suche und Menü anzeigen': 'Also show lobby, search and menu',
    'Zeigt in deinem Discord-Status, was gerade läuft: „Nurse auf Coal Tower“ mit Rundenzeit, in der Lobby „Sucht ein Match“. Discord braucht dafür eine Application-ID: im Developer-Portal „New Application“ anlegen (als Name z. B. „Dead by Daylight“ – so steht es im Status), die Application-ID kopieren und hier eintragen. Das Programm spricht nur mit dem Discord-Client auf diesem PC (lokale Pipe), ohne ID wird nichts gesendet; Discord erfährt nur Map, Rolle, Killer und die Startzeit.': 'Shows in your Discord status what is going on: "Nurse on Coal Tower" with the round time, in the lobby "Searching for a match". Discord needs an Application ID for that: create a "New Application" in the developer portal (name it e.g. "Dead by Daylight" – that is what the status shows), copy its Application ID and enter it here. The program talks only to the Discord client on this PC (local pipe); without an ID nothing is sent; Discord learns only map, role, killer and the start time.',
    'Verbinde mit Discord …': 'Connecting to Discord …',
    'Discord nicht gefunden – läuft es?': 'Discord not found – is it running?',
    'Killer · {killer}': 'Killer · {killer}',
    'Im Match': 'In a match',
    'Sucht ein Match': 'Searching for a match',
    'In der Lobby': 'In the lobby',
    'Bereit machen': 'Getting ready',
    'Im Menü': 'In the menu',
    'Discord: aus': 'Discord: off',
    'Discord: Fehler – {error}': 'Discord: error – {error}',
    'Application-ID fehlt – im Developer-Portal anlegen und hier eintragen.': 'Application ID missing – create one in the developer portal and enter it here.',
    'Ungültige Application-ID ({error})': 'Invalid Application ID ({error})',
    'Discord: verbunden': 'Discord: connected',
    'Als Killer steht dein Killer im Status („Killer · The Nurse“); aus = nur „Killer“.': 'As killer your killer is in the status ("Killer · The Nurse"); off = just "Killer".',
    'Aus = der Status erscheint nur während einer Runde; sonst auch „Sucht ein Match“, „In der Lobby“ und „Im Menü“, solange DBD läuft.': 'Off = the status appears only during a round; else also "Searching for a match", "In the lobby" and "In the menu" while DBD runs.',
    'Dein Discord-Status zeigt Map, Rolle, Killer und die Rundenzeit (in der Lobby: Suche/Lobby). Braucht eine Application-ID aus dem Discord-Developer-Portal; das Programm spricht nur mit dem Discord-Client auf diesem PC.': "Your Discord status shows map, role, killer and the round time (in the lobby: search/lobby). Needs an Application ID from Discord's developer portal; the program talks only to the Discord client on this PC.",
    'Verbindet sich einmal mit dem laufenden Discord und zeigt, ob die Application-ID angenommen wird.': 'Connects once to the running Discord and shows whether the Application ID is accepted.',
    'Öffnet discord.com/developers im Browser: „New Application“ anlegen (Name z. B. „Dead by Daylight“), die Application-ID kopieren und links eintragen.': 'Opens discord.com/developers in the browser: create a "New Application" (name e.g. "Dead by Daylight"), copy its Application ID and enter it on the left.',
    'Ø pro Runde': 'avg per round',
    'BP/h im Match': 'BP/h in the match',
    'Spielzeit laut Stats-Seite': 'play time from the stats page',
    'Match und Suche zusammen': 'match and search together',
    'Beste Runde': 'Best round',
    'Ø BP als Killer': 'avg BP as killer',
    'Ø BP als Survivor': 'avg BP as survivor',
    '{when}: Ø {bp} BP · {n} Runden · Summe {sum}': '{when}: avg {bp} BP · {n} rounds · total {sum}',
    'Ø Bloodpoints pro Runde {per}': 'Avg. bloodpoints per round {per}',
    'Keine Runden mit Bloodpoints in dieser Auswahl.': 'No rounds with bloodpoints in this selection.',
    'Verpixelt': 'Pixelated',
    'Verwischt': 'Blurred',
    'Schwarz': 'Black',
    'Leertaste Abspielen · ←/→ 1 s · Shift 5 s · Strg 1 Bild · I/O Start/Ende · M Marke · Pos1/Ende Anfang/Schluss · Entf Kasten weg · Esc schliessen': 'Space play · ←/→ 1 s · Shift 5 s · Ctrl 1 frame · I/O start/end · M mark · Home/End first/last · Del removes a box · Esc closes',
    'Zensieren': 'Censor',
    'Beim Speichern anwenden': 'Apply when saving',
    'Die Kästen werden im gespeicherten Clip unkenntlich gemacht (dafür wird das Bild neu kodiert, auch im Format „Schnell“).': 'The boxes are hidden in the saved clip (the picture is re-encoded for that, also in the "Fast" format).',
    'Kasten zeichnen': 'Draw box',
    'Im Bild einen Bereich aufziehen; Kästen lassen sich verschieben und an der Ecke rechts unten vergrössern. Nochmal drücken beendet das Werkzeug.': 'Drag out an area on the picture; boxes can be moved and resized at their bottom-right corner. Press again to end the tool.',
    'Namen links unten': 'Names bottom left',
    'Setzt einen Kasten dorthin, wo DBD die Namen der Survivor zeigt (links unten im Spielbild) – bei Bedarf verschieben.': 'Puts a box where DBD shows the survivor names (bottom left of the game picture) – move it if needed.',
    'Kasten entfernen': 'Remove box',
    'Entfernt den markierten Kasten (Taste Entf).': 'Removes the marked box (Del key).',
    'Alle entfernen': 'Remove all',
    'Noch kein Kasten. „Namen links unten“ setzt einen auf die Survivor-Namen, „Kasten zeichnen“ lässt dich einen aufziehen.': 'No box yet. "Names bottom left" puts one on the survivor names, "Draw box" lets you drag one out.',
    '{n} Kasten/Kästen – ziehen = verschieben, Ecke rechts unten = Grösse, Klick = markieren.': '{n} box(es) – drag = move, bottom-right corner = size, click = mark.',
    '{n} Kasten/Kästen gemerkt – sie gelten auch für den nächsten Clip.': '{n} box(es) remembered – they apply to the next clip too.',
    'mit Zensur neu kodiert (wie „Genau“)': 're-encoded for the censoring (like "Exact")',
    'Retusche (aus der Umgebung übermalt)': 'Retouch (painted over from the surroundings)',
    # ------------------------------------------------------------------ 1.8: "Als nächstes" from Spotify
    'Spotify': 'Spotify',
    '„Als nächstes“ aus Spotify in der Musikkarte zeigen': 'Show "Up next" from Spotify on the music card',
    'Client-ID': 'Client ID',
    'Developer-Dashboard öffnen': 'Open developer dashboard',
    'Mit Spotify verbinden': 'Connect to Spotify',
    'Spotify-Verbindung trennen': 'Disconnect Spotify',
    'Zeigt in der Musikkarte, was in Spotify als Nächstes kommt (Position und Anzahl unter Overlay → Musik). Die Windows-Mediensteuerung kennt nur den laufenden Titel, die Liste holt das Programm deshalb von Spotify selbst: Dafür im Developer-Dashboard „Create app“ anlegen (Name frei, API „Web API“), als Redirect URI genau {uri} eintragen, die Client-ID kopieren und hier einfügen, dann „Mit Spotify verbinden“ – der Browser fragt einmal nach der Freigabe. Gelesen wird nur die Warteschlange, nichts gesteuert; die Freigabe liegt verschlüsselt auf diesem PC und lässt sich hier trennen. Titel kommen nie ins Log.':
        'Shows on the music card what comes next in Spotify (place and count under Overlay → Music). The Windows media controls know only the current track, so the program gets the list from Spotify itself: in the developer dashboard "Create app" (any name, API "Web API"), enter exactly {uri} as the redirect URI, copy the Client ID and paste it here, then "Connect to Spotify" – the browser asks once for your consent. Only the queue is read, nothing is controlled; the consent is kept encrypted on this PC and can be removed here. Titles never go to the log.',
    'Spotify: öffne die Anmeldung im Browser …': 'Spotify: opening the login in the browser …',
    'Spotify: Client-ID sieht falsch aus – erwartet werden 32 Zeichen aus 0–9 und a–f (Dashboard → deine App → Settings → Basic Information → Client ID).':
        'Spotify: the Client ID looks wrong – expected are 32 characters of 0–9 and a–f (dashboard → your app → Settings → Basic Information → Client ID).',
    'ALS NÄCHSTES': 'UP NEXT',
    'Unter dem Lied': 'Below the song',
    'Rechts neben dem Lied': 'Right of the song',
    'Als nächstes': 'Up next',
    'Anzahl Titel': 'Tracks shown',
    'Die Liste kommt aus Spotify – einrichten unter Einstellungen → Mehr → Spotify.':
        'The list comes from Spotify – set it up under Settings → More → Spotify.',
    'Spotify: aus': 'Spotify: off',
    'Spotify: Client-ID fehlt – im Developer-Dashboard anlegen und hier eintragen.':
        'Spotify: Client ID missing – create it in the developer dashboard and enter it here.',
    'Spotify: nicht verbunden – „Mit Spotify verbinden“ klicken.': 'Spotify: not connected – click "Connect to Spotify".',
    'Spotify: Anmeldung im Browser offen – dort bei Spotify anmelden und zustimmen …':
        'Spotify: login open in the browser – sign in to Spotify there and agree …',
    'Spotify: Port {port} ist belegt – Anmeldung nicht möglich.': 'Spotify: port {port} is in use – login not possible.',
    'Spotify: Browser konnte nicht geöffnet werden ({error})': 'Spotify: the browser could not be opened ({error})',
    'Spotify: Anmeldung fehlgeschlagen ({error})': 'Spotify: login failed ({error})',
    'Spotify: Anmeldung abgelehnt ({error})': 'Spotify: login refused ({error})',
    'Spotify: keine Antwort vom Browser – Anmeldung abgebrochen.': 'Spotify: no answer from the browser – login cancelled.',
    'Spotify: verbunden': 'Spotify: connected',
    'Spotify: Anmeldung abgelaufen – bitte neu verbinden.': 'Spotify: login expired – please connect again.',
    'Spotify: kein Zugriff ({error}) – ist dein Spotify-Konto in der Developer-App unter „User Management“ eingetragen?':
        'Spotify: no access ({error}) – is your Spotify account listed in the developer app under "User Management"?',
    'Spotify: Fehler – {error}': 'Spotify: error – {error}',
    'Spotify: Kontingent der Developer-App aufgebraucht – „Als nächstes“ pausiert bis {time}.': 'Spotify: the developer app\'s quota is used up – "Up next" paused until {time}.',
    'keine Antwort mit Token': 'no answer with a token',
    'Mit Spotify verbunden – du kannst dieses Fenster schliessen.': 'Connected to Spotify – you can close this window.',
    'Spotify hat die Anmeldung abgelehnt – du kannst dieses Fenster schliessen.':
        'Spotify refused the login – you can close this window.',
    'Die nächsten Titel deiner Spotify-Warteschlange unter oder neben dem laufenden Lied. Braucht eine eigene App im Spotify-Developer-Dashboard (Client-ID) und einmal die Anmeldung im Browser; nur solange Spotify spielt.':
        'The next tracks of your Spotify queue below or beside the current song. Needs an app of your own in the Spotify developer dashboard (Client ID) and one login in the browser; only while Spotify plays.',
    'Öffnet developer.spotify.com/dashboard im Browser: „Create app“, Redirect URI wie unten angegeben eintragen, die Client-ID kopieren und links einfügen.':
        'Opens developer.spotify.com/dashboard in the browser: "Create app", enter the redirect URI given below, copy the Client ID and paste it on the left.',
    'Öffnet die Spotify-Anmeldung im Browser. Nach dem Zustimmen kommt der Browser auf 127.0.0.1 zurück und das Programm merkt sich die Freigabe (verschlüsselt, nur auf diesem PC). Dafür hört es nur während der Anmeldung einmal auf diesem Port.':
        'Opens the Spotify login in the browser. After you agree, the browser returns to 127.0.0.1 and the program keeps the consent (encrypted, on this PC only). For that it listens on this port once, only during the login.',
    'Vergisst die Spotify-Freigabe auf diesem PC; die Liste verschwindet. In Spotify selbst lässt sich die App unter Konto → Apps ebenfalls entfernen.':
        'Forgets the Spotify consent on this PC; the list goes away. In Spotify itself the app can be removed under Account → Apps as well.',
    'Alle Arten': 'All kinds',
    'Art': 'Kind',
    'Clip abspielen': 'Play clip',
    'Clip im Editor öffnen …': 'Open clip in editor …',
    'Im Editor öffnen …': 'Open in editor …',
    'Datei kopieren (zum Einfügen)': 'Copy file (to paste)',
    'Zur Runde springen': 'Go to the round',
    'Farming-Runde': 'Farming round',
    'Datei fehlt: {file}': 'File missing: {file}',
    '{file} kopiert – mit Strg+V z. B. in Discord einfügen.': '{file} copied – paste it with Ctrl+V, e.g. in Discord.',
    'Die Aufnahme dieser Runde gibt es nicht mehr.': 'The recording of this round is gone.',
    'ffmpeg fehlt (Paket imageio-ffmpeg) – start.bat installiert es beim nächsten Start.':
        'ffmpeg missing (package imageio-ffmpeg) – start.bat installs it on the next start.',
    'Öffnet den markierten Clip (auch Sofort-Clips von F8) im Clip-Editor: kürzen, zensieren, Ton mischen. '
    'Gespeichert wird ein neuer Clip, der alte bleibt.':
        'Opens the marked clip (F8 instant clips too) in the clip editor: trim, censor, mix the sound. '
        'It saves a new clip, the old one stays.',
    'Clip fehlt: {file}': 'Clip missing: {file}',
    'Clip gelöscht: {file}': 'Clip deleted: {file}',
    'Clip im Explorer zeigen': 'Show clip in Explorer',
    'Clip löschen': 'Delete clip',
    'Clip nicht gelöscht ({error}): {file}': 'Clip not deleted ({error}): {file}',
    'Hier stehen die Clips aus dem Editor, die Sofort-Clips (F8) und die Standbilder – mit der Runde, aus der sie stammen. Gelöscht werden nur Dateien, die das Programm selbst angelegt hat.':
        'Here are the clips from the editor, the instant clips (F8) and the stills – with the round each came from. Only files the program made itself are deleted.',
    'Kein Aufnahmeordner – die Clips liegen in seinem Ordner „Clips“.':
        'No recording folder – the clips are kept in its folder "Clips".',
    'Länge': 'Length',
    'Noch keine Clips – „Clip bearbeiten …“ bei einer Runde oder F8 im Spiel.':
        'No clips yet – "Edit clip …" on a round, or F8 in the game.',
    'Sofort-Clip': 'Instant clip',
    'Sofort-Clips (F8)': 'Instant clips (F8)',
    'Standbild': 'Still',
    'Standbilder': 'Stills',
    '{n} von {total} Clips': '{n} of {total} clips',
    'Spielt den markierten Clip im Standard-Player von Windows ab.':
        "Plays the marked clip in Windows' default player.",
    'Öffnet den Explorer mit dem markierten Clip.': 'Opens Explorer with the marked clip.',
    'Löscht den markierten Clip von der Platte – nach Rückfrage. Nur Dateien, die das Programm selbst angelegt hat.':
        'Deletes the marked clip from the drive – after asking. Only files the program made itself.',
    'Öffnet den Ordner „Clips“ neben den Aufnahmen im Explorer.': 'Opens the folder "Clips" beside the recordings in Explorer.',
    'Clips': 'Clips',
    'Graue Linien in den Balken = Grenzen (aus) – eine ziehen schaltet sie ein': 'Grey lines in the bars = limits (off) – drag one to switch them on',
    'mit kurzer Meldung': 'with a short notification',
    'Clip wird gespeichert …': 'Saving clip …',
    'Die letzten {n} s aus dem Puffer von OBS': "The last {n} s from OBS's buffer",
    'Clip gespeichert ✓': 'Clip saved ✓',
    '{n} s · im Tab Aufnahmen → Clips': '{n} s · in the tab Recordings → Clips',
    'Kein Clip': 'No clip',
    'Zeigt beim Sofort-Clip (F8) unten rechts ein kleines Hinweisfenster – „Clip wird gespeichert …“ und danach „Clip gespeichert“ bzw. warum nicht. Auch im Spiel, ohne Ton; nimmt nie den Fokus.':
        'Shows a small notification window bottom right for the instant clip (F8) – "Saving clip …" and then "Clip saved" or why not. Also in the game, without sound; never takes the focus.',
    'Die Linien in der Vorschau mit „Mit der Maus verschieben“ ziehen – Karte, Systemwerte, Heute und Musik bleiben im Balken dazwischen.':
        'Drag the lines in the preview with "Move with the mouse" – map, system values, today and music stay in the bar between them.',
    'Grenzen oben und unten in den schwarzen Balken': 'Limits at the top and bottom of the black bars',
    'Grenzen zurücksetzen': 'Reset limits',
    'Links und rechts gleich': 'Left and right alike',
    'In jedem schwarzen Balken (links und rechts) eine Linie oben und eine unten: Karte, Systemwerte, Heute und Musik bleiben dazwischen – z. B. frei für eine FPS-Anzeige oder Benachrichtigungen. Die Karte wird bei Bedarf kleiner.':
        'A line at the top and one at the bottom of each black bar (left and right): map, system values, today and music stay between them – e.g. to keep room for an FPS counter or notifications. The map gets smaller when needed.',
    'Eine Linie ziehen bewegt die gleiche Linie im anderen Balken mit.':
        'Dragging a line moves the same line in the other bar along.',
    'Setzt alle vier Linien auf 8 % vom Rand zurück.': 'Puts all four lines back at 8 % from the edge.',
    'Dunkelgrauer Boden mit hellem Rand – gilt auch im Spiel.': 'Dark grey floor with a light edge – in the game too.',
    'Dunkelgrauer Boden – die Form der Map bleibt auf dem schwarzen Balken sichtbar. Gilt auch im Spiel.':
        "Dark grey floor – the map's shape stays visible on the black bar. In the game too.",
    'Dunkles Lila mit lila Rand, erinnert an die Originalfarbe – gilt auch im Spiel.':
        'Dark lilac with a lilac edge, close to the original colour – in the game too.',
    'Durchsichtiger Boden mit dunklem Rand – gilt auch im Spiel.': 'See-through floor with a dark edge – in the game too.',
    'Grau': 'Grey',
    'Grau mit Rand': 'Grey with edge',
    'Lila dunkel': 'Dark lilac',
    'Lila transparent': 'Lilac see-through',
    'Lila Boden, halb durchsichtig – gilt auch im Spiel.': 'Lilac floor, half see-through – in the game too.',
    # 1.8.45
    'Wichtig: In DBD unter Einstellungen → Grafik den Anzeigemodus „Fenster-Vollbild“ wählen. Im exklusiven Vollbild kann Windows kein Fenster über dem Spiel zeigen – die Karte bliebe unsichtbar.':
        'Important: in DBD under Settings → Graphics choose the display mode "Windowed Fullscreen". In exclusive fullscreen Windows cannot show a window above the game – the map would stay invisible.',
    'Ungültiger Servername im Auftrag: {name}': 'Invalid server name in the job: {name}',
    'Die hosts-Datei wurde direkt nach dem Schreiben wieder verändert (Virenschutz oder ein anderes Programm?).':
        'The hosts file was changed again right after writing (antivirus or another program?).',
    'Keine Schreibrechte auf die hosts-Datei (Administratorrechte?).': 'No permission to write the hosts file (administrator rights?).',
    # 1.8.46
    'Aufbau der Match-Daten speichern': 'Save the structure of the match data',
    'Öffnet die Stats-Seite so, dass das Userscript einmal den Aufbau ihrer Match-Daten im Download-Ordner speichert: nur Feldnamen und Arten, keine Werte. Damit lässt sich entscheiden, welche Daten das Programm zusätzlich auswerten könnte.':
        'Opens the stats page so that the userscript saves the structure of its match data once in the download folder: field names and types only, no values. That shows which further data the program could use.',
    'Die Stats-Seite öffnet sich im Browser. Das Userscript (ab Version {n}) legt danach „{file}“ in den Download-Ordner: nur die Namen und Arten der Felder, die die Seite liefert – keine Werte, keine Namen, keine IDs. Das Programm liest diese Datei nicht; du kannst sie weitergeben, um zu entscheiden, welche Felder zusätzlich übernommen werden sollen. Ältere Userscripts: vorher „Userscript kopieren“ und in Tampermonkey ersetzen.':
        'The stats page opens in the browser. The userscript (version {n} or newer) then puts "{file}" into the download folder: only the names and kinds of the fields the page sends – no values, no names, no IDs. The program does not read this file; you can pass it on to decide which further fields should be taken. Older userscripts: first "Copy userscript" and replace it in Tampermonkey.',
    'Gegner': 'Opponents',
    'Charakter': 'Character',
    'Begegnungen': 'Encounters',
    'Geopfert': 'Sacrificed',
    'Getötet': 'Killed',
    'Aufgegeben': 'Abandoned',
    'Laut Stats-Seite: als Killer die Survivor gegen dich und wie ihr Match endete, als Survivor der Killer und wie dein Match endete. „Getötet“ = vom Killer direkt getötet (z. B. Mori), „Aufgegeben“ schließt verlassene Matches ein. „Ø Kills ohne Aufgaben“ zählt nur Matches, in denen kein Survivor aufgab oder ging.':
        'From the stats page: as killer the survivors against you and how their match ended, as survivor the killer and how your match ended. "Killed" = killed by the killer directly (e.g. a mori), "Abandoned" includes matches left. "Clean Ø kills" counts only matches in which no survivor abandoned or left.',
    'Noch keine Runden mit Daten der Stats-Seite in dieser Auswahl.': 'No rounds with stats-page data in this selection yet.',
    'Schnellste 4K': 'Fastest 4K',
    '{n} von {total} Runden': '{n} of {total} rounds',
    '{n} Survivor': '{n} survivors',
    'Ø Kills ohne Aufgaben': 'Clean Ø kills',
    # 1.8.47
    'OBS mit DBD starten, falls es noch nicht läuft': 'Start OBS with DBD if it is not running yet',
    'Startet DBD und ist OBS nicht erreichbar, startet das Programm OBS einmal minimiert im Infobereich – nur, wenn kein OBS-Fenster offen ist. OBS bleibt offen, wenn DBD beendet wird. OBS läuft dann mit denselben Rechten wie das Programm (Administrator).':
        'When DBD starts and OBS cannot be reached, the program starts OBS once, minimised to the notification area – only if no OBS window is open. OBS stays open when DBD is closed. OBS then runs with the same rights as the program (administrator).',
    'OBS wurde gestartet, ist aber nicht erreichbar – in OBS unter Werkzeuge → WebSocket-Servereinstellungen den Server aktivieren und Port/Passwort prüfen. ({error})':
        'OBS was started but cannot be reached – in OBS under Tools → WebSocket Server Settings enable the server and check port/password. ({error})',
    'OBS nicht gefunden – bitte OBS selbst starten (gesucht unter Programme\\obs-studio).':
        'OBS not found – please start OBS yourself (looked in Program Files\\obs-studio).',
    'OBS konnte nicht gestartet werden: {error}': 'OBS could not be started: {error}',
    'OBS wird gestartet …': 'Starting OBS …',
    'OBS ist offen, aber nicht erreichbar – in OBS unter Werkzeuge → WebSocket-Servereinstellungen den Server aktivieren und Port/Passwort prüfen. ({error})':
        'OBS is open but cannot be reached – in OBS under Tools → WebSocket Server Settings enable the server and check port/password. ({error})',
    # 1.8.48
    'Builds': 'Builds',
    'Build (4 Perks)': 'Build (4 perks)',
    'Perk': 'Perk',
    'Add-on': 'Add-on',
    'Opfergabe': 'Offering',
    'Kraft/Item': 'Power/item',
    'ohne': 'without',
    'Dein Loadout laut Stats-Seite (ab Userscript Version 3). „Ergebnis“ = als Killer Ø Kills, als Survivor Anteil entkommen; „ohne“ = dasselbe in deinen Runden derselben Rolle ohne diesen Eintrag. Builds ab {n} Runden. Embleme: Ø Stufe von keins (0) bis Iri (4); „voll“ = Kategorie mit {max} Punkten.':
        'Your loadout from the stats page (userscript version 3 or newer). "Result" = as killer Ø kills, as survivor the share escaped; "without" = the same in your rounds of that role without this entry. Builds from {n} rounds. Emblems: Ø tier from none (0) to iri (4); "full" = category at {max} points.',
    'Öffentlich': 'Public',
    'Event-Modus': 'Event mode',
    'keins': 'none',
    'Bronze': 'Bronze',
    'Silber': 'Silver',
    'Gold': 'Gold',
    'Iri': 'Iri',
    'Emblem': 'Emblem',
    'Ø Stufe': 'Ø tier',
    'Punktekategorie': 'Score category',
    'Ø Punkte': 'Ø points',
    'voll': 'full',
    'Killer-Wertung: {list}': 'Killer rating: {list}',
    'Noch keine Matches mit Loadout in dieser Auswahl – die Stats-Seite liefert es ab Userscript Version 3 (Einstellungen → Mehr → Offizielle Match-Daten → „Userscript kopieren“).':
        'No matches with a loadout in this selection yet – the stats page sends it from userscript version 3 (Settings → More → Official match data → "Copy userscript").',
    # 1.8.49
    'Alle Modi': 'All modes',
}
