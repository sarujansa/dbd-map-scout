# Datenschutzerklärung – Fog Scout

*English version below.*

Fog Scout ist ein Open-Source-Programm für Windows, das lokal auf deinem PC läuft. Es gibt keinen Server, kein Konto, keine Telemetrie und keine Werbung. Alles, was das Programm speichert (Einstellungen, Rundenverlauf, Statistik), liegt in seinem eigenen Ordner auf deinem PC. Dieses Dokument nennt alles, was das Programm nach aussen sendet – jeder Punkt ist einzeln abschaltbar oder nur auf deinen Klick aktiv.

| Funktion | Wohin | Was | Wann |
|---|---|---|---|
| Updates | GitHub (`github.com`) | `git fetch` dieses Repositorys | Beim Start (abschaltbar) und auf Klick „Jetzt nach Updates suchen“ |
| Tab „Server“ | AWS GameLift (`amazonaws.com`, `api.aws`) | Ping (ICMP oder UDP-Beacon), DNS-Auflösung | Nur im Tab „Server“ bzw. solange „Verbunden mit“ läuft |
| Offizielle Match-Daten | Keine eigene Verbindung | Dein Browser lädt mit einem Userscript die Match-Daten, die stats.deadbydaylight.com dir selbst anzeigt, als Datei in den Download-Ordner; das Programm liest nur diese Datei | Nur mit dem Userscript, das du selbst installierst |
| OBS | Nur `127.0.0.1` (dein eigener PC) | Befehle an OBS Studio über obs-websocket | Nur mit eingeschalteter Aufnahme |
| Discord Rich Presence | Nur der lokale Discord-Client (IPC-Pipe) | Map, Rolle, Lobby-Zustand | Nur eingeschaltet und mit eigener Application-ID |
| Spotify „Als nächstes“ | Spotify Web API (`api.spotify.com`, `accounts.spotify.com`) | Anmeldung (OAuth 2 PKCE), Lesen der Warteschlange – nie steuern | Nur eingeschaltet und nach deiner Anmeldung |
| YouTube-Upload | Google (`accounts.google.com`, `oauth2.googleapis.com`, `www.googleapis.com`) | Siehe unten | Nur eingeschaltet bzw. je Datei auf Klick |

Das Programm fasst Dead by Daylight nie an: keine Eingaben, kein Zugriff auf den Spielprozess oder Spieldateien. Es liest Bildschirmpixel, Fensterinformationen und – auf Wunsch – Systemwerte (CPU/GPU-Auslastung und -Temperatur).

## YouTube-Upload (Google-Nutzerdaten)

Der YouTube-Upload ist standardmässig aus. Schaltest du ihn ein, gilt:

- **Angeforderter Bereich (Scope):** `https://www.googleapis.com/auth/youtube.upload` – das Programm kann Videos auf deinen Kanal hochladen, sonst nichts. Nur wenn du „Uploads in Playlists einsortieren“ einschaltest, fragt die Anmeldung zusätzlich `https://www.googleapis.com/auth/youtube` an; davon nutzt das Programm ausschliesslich das Auflisten deiner eigenen Playlists (Titel und ID, für die Auswahl) und das Einsortieren des gerade hochgeladenen Videos in die gewählte Playlist. Es liest sonst keine Daten aus deinem Google-Konto oder Kanal; die Antworten, die es auswertet, sind die Zugangstoken, die Video-ID des hochgeladenen Videos und diese Playlist-Liste.
- **Gesendet werden** die Videodatei aus deinem Aufnahmeordner sowie Titel und Beschreibung, die das Programm aus Map, Rolle/Killer, Datum und Dauer bildet. Keine Spielernamen, keine anderen Daten.
- **Gespeichert wird** das Refresh-Token von Google zusammen mit Client-ID und Client-Secret deines eigenen OAuth-Clients – verschlüsselt mit der Windows-Datenschutz-API (DPAPI) in der Datei `settings.json` auf deinem PC. Diese Werte kommen in keine Sicherung und keinen Export. „YouTube-Verbindung trennen“ löscht sie; zusätzlich kannst du den Zugriff jederzeit unter <https://myaccount.google.com/permissions> entziehen.
- **Weitergabe:** keine. Die Daten gehen nur an Google und bleiben sonst auf deinem PC. Es gibt keinen Server des Programms, keine Analyse, keine Werbung.
- **Kontrolle:** Jeder Upload lässt sich in der Warteschlange entfernen, die lokale Datei bleibt immer erhalten. Die Sichtbarkeit (privat, nicht gelistet, öffentlich) wählst du selbst; Standard ist privat.

Die Nutzung von Informationen aus Google-APIs durch Fog Scout richtet sich nach der [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy) einschliesslich der Limited-Use-Anforderungen.

## Kontakt

Fragen und Hinweise: über die Issues dieses Repositorys (<https://github.com/sarujansa/fog-scout/issues>).

---

# Privacy Policy – Fog Scout

Fog Scout is an open-source program for Windows that runs locally on your PC. There is no server, no account, no telemetry and no advertising. Everything the program stores (settings, round history, statistics) lives in its own folder on your PC. This document lists everything the program sends anywhere – each item can be switched off on its own or is active only when you click.

| Feature | Where to | What | When |
|---|---|---|---|
| Updates | GitHub (`github.com`) | `git fetch` of this repository | At start (can be disabled) and on "Check for updates now" |
| "Server" tab | AWS GameLift (`amazonaws.com`, `api.aws`) | Ping (ICMP or UDP beacon), DNS lookups | Only in the "Server" tab or while "Connected to" runs |
| Official match data | No connection of its own | Your browser, with a userscript, saves the match data that stats.deadbydaylight.com shows you as a file in your download folder; the program only reads that file | Only with the userscript you install yourself |
| OBS | Only `127.0.0.1` (your own PC) | Commands to OBS Studio over obs-websocket | Only with recording enabled |
| Discord Rich Presence | Only the local Discord client (IPC pipe) | Map, role, lobby state | Only when enabled, with your own application ID |
| Spotify "Up next" | Spotify Web API (`api.spotify.com`, `accounts.spotify.com`) | Login (OAuth 2 PKCE), reading the queue – never controlling | Only when enabled and after your login |
| YouTube upload | Google (`accounts.google.com`, `oauth2.googleapis.com`, `www.googleapis.com`) | See below | Only when enabled, or per file on click |

The program never touches Dead by Daylight: no input, no access to the game process or game files. It reads screen pixels, window information and – if you want – system values (CPU/GPU load and temperature).

## YouTube upload (Google user data)

The YouTube upload is off by default. If you switch it on:

- **Requested scope:** `https://www.googleapis.com/auth/youtube.upload` – the program can upload videos to your channel and nothing else. Only if you enable "Sort uploads into playlists" does the login also ask for `https://www.googleapis.com/auth/youtube`; of that the program uses exclusively listing your own playlists (title and ID, for the choice) and sorting the video just uploaded into the chosen playlist. It reads no other data from your Google account or channel; the answers it evaluates are the access tokens, the video ID of the uploaded video and that playlist list.
- **Sent** are the video file from your recordings folder and a title and description the program builds from map, role/killer, date and length. No player names, no other data.
- **Stored** are Google's refresh token together with the client ID and client secret of your own OAuth client – encrypted with the Windows Data Protection API (DPAPI) in the file `settings.json` on your PC. These values never go into a backup or an export. "Disconnect YouTube" deletes them; you can also revoke the access at any time at <https://myaccount.google.com/permissions>.
- **Sharing:** none. The data goes only to Google and otherwise stays on your PC. There is no server of the program, no analytics, no advertising.
- **Control:** every upload can be removed from the queue; the local file is always kept. You choose the visibility (private, unlisted, public); the default is private.

Fog Scout's use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Contact

Questions and remarks: through the issues of this repository (<https://github.com/sarujansa/fog-scout/issues>).
