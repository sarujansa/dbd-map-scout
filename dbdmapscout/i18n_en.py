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
    "Die Karten im Stil von Fallen Refuge (durchsichtiger Boden, dunkler Rand) – gilt auch im Spiel.":
        "The maps in the style of Fallen Refuge (see-through floor, dark edge) – applies in the game too.",
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
    "Crossplay ist aus – die nächste Runde zählt als Farming-Runde.":
        "Cross-play is off – the next round counts as a farming round.",
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
    "Runde löschen": "Delete round",
    "Ø {kills} Kills · {n} Runden": "Avg. {kills} kills · {n} rounds",
    "Killer: Ø {kills} Kills, {four}× 4K ({n})": "Killer: avg. {kills} kills, {four}× 4K ({n})",
    "Survivor: {share} entkommen ({n})": "Survivor: {share} escaped ({n})",
    "{share} entkommen · {n} Runden": "{share} escaped · {n} rounds",
    "Eigene Bilanz auf der Map unter dem Timer (Stats-Seite)": "Own record on the map below the timer (stats page)",
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
    "Die Karte ist so breit wie der schwarze Balken – grösser geht so nicht. Grösser mit „Karte darf grösser als der Balken werden“ (ragt dann ins Spielbild).":
        "The map is as wide as the black bar – it cannot get bigger like this. Bigger with “The map may grow bigger than the bar” (it then reaches into the game picture).",
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
    "Einmal einrichten: Tampermonkey im Browser installieren, „Userscript kopieren“ und dort als neues Skript einfügen, "
    "auf stats.deadbydaylight.com anmelden. Beim Öffnen der Seite speichert das Skript die letzten 30 Matches im "
    "Download-Ordner; das Programm liest die Datei und löscht sie. Es geht dafür selbst nicht ins Internet.":
        "Set up once: install Tampermonkey in the browser, \"Copy userscript\" and paste it there as a new script, sign "
        "in on stats.deadbydaylight.com. When the page opens, the script saves the last 30 matches into the download "
        "folder; the program reads the file and deletes it. It does not go online for this itself.",
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
    'Stellt die Kästen auf allen Seiten wieder in die ursprüngliche Reihenfolge.':
        'Puts the boxes of all pages back in their original order.',
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
    "Schrift der Karte (Name, Timer, Infos)": "Map text (name, timer, info)",
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
    'Groß – Cover oben, Titel darunter': 'Large – cover on top, title below',
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
    'Original (lila Boden)': 'Original (lilac floor)',
    'Dunkel – wie Fallen Refuge (durchsichtiger Boden)': 'Dark – like Fallen Refuge (see-through floor)',
    'Kartenstil': 'Map style',
    'Kartenstil: {style}.': 'Map style: {style}.',
    'Map wählen …': 'Choose map …',
    "Zur Seite Maps: eine Map von Hand anzeigen (Doppelklick oder „Anzeigen“). Beim nächsten Match übernimmt die automatische Erkennung wieder.":
        'To the Maps page: show a map by hand (double-click or "Show"). At the next match the automatic detection takes over again.',
    "Erscheint automatisch, sobald im Match das Map-Banner kommt – oder von Hand über „Map wählen“.":
        'Appears by itself as soon as the map banner comes in the match – or by hand with "Choose map".',
    'Unter der Karte': 'Below the map',
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
    'Mehr (Map-Zuordnungen, Match-Daten, Aufnahmen, Sicherung, Ordner)': 'More (map assignments, match data, recordings, backup, folders)',
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
    'Das Banner kommt erst ~40 s nach Matchbeginn. Läuft in OBS der Wiederholungspuffer, wird er beim Banner gespeichert – so fehlt der Anfang (Spawn) nicht. Die Datei liegt als „(Vorlauf)“ neben der Runde.': 'The banner comes ~40 s after the match starts. If OBS\'s replay buffer is running, it is saved at the banner – so the start (spawn) is not missing. The file lies next to the round as "(Vorlauf)".',
    # 1.4.1
    'Wiederholungspuffer mit DBD starten und stoppen': "Start and stop the replay buffer with DBD",
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
    'Nach der Runde hängt ffmpeg den Vorlauf vorne an die Aufnahme – ohne Neukodierung, in Sekunden, Bild und Ton bleiben wie von OBS. Klappt es nicht, bleiben beide Dateien liegen.': 'After the round ffmpeg puts the pre-roll in front of the recording – no re-encoding, seconds of work, picture and sound stay as OBS made them. If it fails, both files stay.',
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
    'Clip schneiden …': 'Cut a clip …',
    'Öffnet den Clip-Editor für die markierte Aufnahme: Vorschau, Zeitleiste mit Marken, Start/Ende setzen, Ausschnitt als MP4 in den Ordner „Clips“ speichern.': 'Opens the clip editor for the marked recording: preview, timeline with marks, set start/end, save the cut as MP4 into the folder "Clips".',
    'Clip schneiden – {name}': 'Cut a clip – {name}',
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
    'Clip speichern': 'Save clip',
    'Schreibt den Ausschnitt als MP4 in den Ordner „Clips“ neben den Aufnahmen.': 'Writes the cut as MP4 into the folder "Clips" next to the recordings.',
    'Clips-Ordner öffnen': 'Open clips folder',
    'Öffnet den Ordner „Clips“ im Explorer.': 'Opens the folder "Clips" in Explorer.',
    'Datei nicht lesbar oder ffmpeg fehlt – keine Vorschau.': 'File not readable or ffmpeg missing – no preview.',
    'Clips-Ordner nicht anlegbar: {error}': 'Clips folder cannot be created: {error}',
    'Schreibe {file} …': 'Writing {file} …',
    'Clip gespeichert: {file}': 'Clip saved: {file}',
    'Clip nicht gespeichert: {why}': 'Clip not saved: {why}',
}
