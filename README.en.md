# DbD Map Scout

*[Deutsche Fassung: README.md](README.md)*

Map overlay for Dead by Daylight. When a match starts, the map name is detected automatically and the matching callout map from the `maps/` folder is shown. The map is a separate click-through window on top of the game.

**Language:** the program shows German or English. By default it follows the Windows language (English unless Windows runs in German). Change it under **Settings → Language and appearance → Sprache / Language**; it takes effect the next time the program starts.

## Installation (once)

1. **Install Python** (if you do not have it yet): <https://www.python.org/downloads/>, version 3.12 or newer. Tick **"Add python.exe to PATH"** in the installer.
2. Unpack the folder, e.g. to `C:\Tools\dbd-map-scout`.
3. Double-click **`start.bat`**. The first start creates a Python environment of its own (`.venv`) and installs the packages (about 1–2 minutes, around 250 MB). The program then starts right away.
4. **Desktop shortcut:** once the program runs as administrator (e.g. right-click `start.bat` → "Run as administrator"), it sets the shortcut up **by itself** and renews it after updates or when you move the folder. By hand: **`verknuepfung_erstellen.bat`** (Windows asks once for administrator rights). Both create the task "DbD Map Scout" in the Windows Task Scheduler and put "DbD Map Scout" with its own icon on the desktop: the shortcut starts the program as administrator (needed for "Connected to") **without a Windows prompt** and without a console window. The same shortcut goes into the **Start menu**. Pin it via the shortcut (right-click → "Pin to taskbar") or directly on the running program in the taskbar – either way it is one button with the program icon. (Pinned before 1.30.3 and it shows the Python icon? "Unpin from taskbar" once, start the program once through the desktop shortcut, pin again.)

**Notification area and autostart.** When minimised, the control window goes to the notification area next to the clock (double-click opens it, right-click: overlay on/off, quit). The program **starts with Windows** (on by default since 1.30.3, set up on the first start as administrator or through the desktop shortcut) – quietly in the notification area, as administrator, without a prompt. Without DBD it only looks for the game window once a second; as soon as DBD runs, it works. Starting exactly "when DBD starts" is not possible within the rules (something would have to watch processes or launch the game). If it is already running (also hidden in the notification area), starting it again only says "already running". Switch it off under **Settings → Start and notification area** – it then stays off. Switching works when the program runs through the desktop shortcut.

*Security note:* a task "with highest privileges" deliberately skips the Windows prompt – whatever is in the program folder (including code fetched by an update) then runs as administrator without asking. If you want this stricter, put the folder somewhere only administrators can write to (e.g. under `C:\Program Files`).

**Updates** come automatically: when started through `start.bat` or the desktop shortcut, the program fetches the new version from GitHub (only if the folder is a git clone on `main` and you did not change program files yourself) and installs changed packages. Offline or with your own changes it simply starts the version that is there. The log shows what is new. Can be switched off under **Settings → Updates**. There is also **"Check for updates now"**: it asks GitHub (only on this click) and shows "No update" or the new version with its changes; **"Update and restart"** closes the program, installs the update via `start.bat` and starts again – even if the check at start is switched off.

In DBD, use the display mode **"Windowed Fullscreen"** under **Settings → Graphics**. In exclusive fullscreen Windows cannot show a window on top of the game.

**Window mode** works too: the map then appears next to the DBD window if at least 200 px of the monitor are free there, and the background window capture leaves out the title bar. Below 1920×1080 detection is less reliable (above all the lobby button and killer name). Windows narrower than 16:9 (e.g. 1718×1360) are untested. The log mentions both once.

## Usage

Start the program and play DBD. When the map name appears at the bottom left at the start of a match (e.g. "COAL TOWER / THE MACMILLAN ESTATE"), the map is shown automatically.

**After the round** the map disappears again. This is detected by:

- the results screen (button "CONTINUE"),
- lobby, main menu, bloodweb and store (currencies at the top right),
- the loading screen of the next round (almost black, still picture with a loading bar – lying on the ground with the recovery bar does not count),
- DBD being closed.

On ultrawide monitors DBD shows the results screen and menus in full width, but the match in 16:9 with black bars. The program recognises this and then looks for CONTINUE and the currencies up to the real screen edge; during the match the bars are left out.

**The overlay pauses in menus.** DBD only shows the mouse pointer in menus (ESC menu, results screen, lobby). If it is visible over the DBD window for a few seconds, the map is hidden. When it disappears, the map comes back. If the mouse pointer is visible in a menu for a minute in total, the round counts as over.

**Round timer.** The timer runs while a map is shown. When a map appears (detected automatically, chosen by hand or shown by hotkey), it starts at 00:00. When it disappears (end of round detected or hidden by hand), it stops. It is shown in the control window below the map name ("Round running: 07:32", then "Last round: 12:04") and large and centred right below the map in the overlay, styled like the map title: white digits with a shadow, no box (can be switched off in the Overlay tab). At the end of the round, the first sign of it counts as the end time, e.g. the mouse pointer appearing on the results screen, not the moment detection is sure. Briefly hiding in the ESC menu or while another window is active does not stop the timer, because the match goes on. Switching the layout or map while the map is shown does not reset it. A new map banner always starts a new round, even if the end of the previous one was not detected.

**Waiting card.** While DBD runs and no map is shown (before the match, in the lobby, after the round), the overlay shows a small card in the same place: "WAITING FOR MAP", below it the search or lobby ("SEARCHING: 02:13 · NURSE") or after the round "LAST ROUND: 12:04". With "Connected game server" (Server tab) on, region and ping follow below as soon as DBD is connected to a game server – usually from the lobby on. As soon as the map banner is detected, the map replaces it. If it is still there in the middle of a match, the map was not detected – use "Scan". Not when you hid the map yourself; can be switched off in the Overlay tab.

**Only while DBD runs.** As long as the DBD window is not found, nothing is detected automatically, even if a DBD video or screenshot is on screen. So no map pops up while you work. "Scan" still checks the main screen when clicked.

In the **Detection** tab, the line "End-of-round detection: …" always shows what the program currently sees, e.g. "in match · mouse pointer hidden". `Ctrl+Alt+M` brings back a hidden map right away.

The top of the control window always says where things stand: **Waiting for DBD**, **Waiting for the next match**, **In match: …**, **In a menu – map paused** or **Round over** (problems such as a black picture are shown in red). Technical details are in the Log tab.

**Info texts:** rest the mouse briefly on a button or checkbox and a small text explains what it does (with its hotkey).

**Layout button:** only appears for maps with several layouts (Coal Tower, Groaning Storehouse, Ironworks of Misery, Shelter Woods, Suffocation Pit, Mount Ormond Resort, Badham Preschool) and shows the layout on display, e.g. "Layout II of V ▸". A click switches to the next one. If detection was unsure about the layout, "(unsure)" is added.

The control window has these tabs. If a tab does not fit into the window, a scrollbar appears on the right (mouse wheel works too), so the window can be made as small or large as you like:

| Tab | Content |
|---|---|
| **Maps** | all maps by realm, search, double-click shows a map; "Add map picture …" for your own pictures |
| **Overlay** | position (preset or horizontal/vertical sliders, 0 % = left/top, 100 % = right/bottom; moving a slider switches to "own position"), "Test overlay", size, opacity, display options |
| **Statistics** | on top the line **Today** (independent of the filters): rounds and play time, killer/survivor, avg. wait, most played killer, ping. Below it your rounds (tables as sub-tabs: maps – per map also split into killer/survivor –, killers, server regions, waiting time, last rounds), filtered by period (today, this week, this month, this year) and server region: count, average length, total time; per map rounds, average and longest length (click a column to sort); per server region rounds, average length, share and average ping (median per round, only with "Connected game server"); the last 100 rounds with date, length and server region. Counted from the detected map banner to the detected end of the round (from 1 minute; without a detected end the round is not counted). Also filtered by **role** (killer, survivor, custom games), with the **waiting time in the lobby**: average, median, shortest and longest search, split by weekday, time of day (3-hour blocks) or region. As killer each round also remembers the **killer** (name below the lobby button): its own table with rounds, avg. duration and most frequent map per killer, and a **Killer** filter – e.g. which maps you get how often with the Nurse and how long those rounds last. If the role detection was wrong: select the round under "Last rounds" and correct it with **Killer / Survivor / Custom game**. If the end of a round was not detected, it is not counted – the statistics then say "⚠ Not counted: 2 × …" so you know rounds are missing. Sub-tab **Kills & Escapes**: kills, 4K and escape rate per map from the official stats page (see below). Stored only locally in `rounds.jsonl`, "Delete history" removes everything |
| **Server** | the connected game server at the top, below it server regions with ping, blocked or allowed through the hosts file (see below) |
| **Settings** | hotkeys, notifications, start/notification area, language, dark mode, updates; folded under "More": own map assignments, backup, folders |
| **Detection** | automatic mode, hiding after the round, pause in menus, game language; folded under "Advanced": window capture, scans per second, live status, debug pictures, diagnostics |
| **Log** | messages in the categories *Detection*, *Overlay*, *System*, *Error*, each can be shown or hidden |

**Position "automatic":** if DBD runs with a 16:9 picture on a wider monitor (e.g. 3440×1440 with black bars), the map goes into the left black bar and is scaled to fit. In window mode it appears next to the DBD window (left, otherwise right) if at least 200 px are free there. Otherwise it appears at the top left of the game picture. As soon as you move a position slider or drag the map with the mouse, "custom position" applies. "Reset" sets "automatic" again.

**Waiting time and role:** outside a match the program looks at the button bottom right in the lobby once per second. CANCEL with "EST." below means: searching (DBD shows the time waited so far, which is used). READY, or CANCEL without "EST.", means: lobby found, the waiting time is fixed. If the killer's name is shown below the button you play killer, otherwise survivor; if nothing is shown below it, it is a custom game (no waiting time). On the results screen the categories (BRUTALITY … or OBJECTIVES …) confirm the role. The main window shows "Searching: 02:13 · Nurse" or "Role: Nurse · waited 02:13" (as survivor "Survivor"). The killer name is matched against a list of killers. **Legendary outfits** show their own name there (e.g. "Murderous Grizzly" instead of "The Oni") – known ones count for their killer automatically (Murderous Grizzly, The Minotaur → Oni; Naughty Bear, Frank Stone → Trapper; Ferryman of the Underworld → Blight; Were-Elk → Huntress; Hunk → Legion; William Afton → Animatronic). An outfit or new killer the program does not know is taken as shown – never mapped to a wrong one; in the statistics under "Killer" select the row, pick the killer, **Assign** (also applies to past rounds). A single round wrong (e.g. counted as survivor although you were killer): select it under "Last rounds", pick the killer, **Set killer** – it then counts as a killer round with that killer. A cancelled search does not count. Nothing of this is checked during a match.

**Notification when the lobby is found:** a sound plus a small notification window of its own bottom right ("Lobby found – after 04:12 – Press READY."; above all windows, never takes the focus, also shown with "Do not disturb" – Windows notifications would be swallowed then; "Test notification" shows it), and a reminder when the lobby countdown drops below 15 s while READY is not pressed. By default only while DBD is not the active window – so you can do something else while searching. Can be switched off under Settings → Notifications. Nothing is sent to the game. The game's English texts are recognised.

**Info only, without the map:** switch off "Show the map" in the Overlay tab – the overlay then shows only the round timer, server region and ping when a round starts (same place, same style). Detection, hiding after the round, menu pause and statistics keep working as usual.

**Kills & Escapes (official match data):** the official page [stats.deadbydaylight.com](https://stats.deadbydaylight.com/) knows your last 30 matches with map, role, character and the status of every survivor. An own userscript brings this data into the statistics – the program itself does not go online for it and never sees your login. Setup (once):

1. Install **Tampermonkey** (or Violentmonkey) in your browser.
2. Statistics → Kills & Escapes → **Copy userscript**, in Tampermonkey "Create a new script", replace everything (Ctrl+A, Ctrl+V), save.
3. Sign in on stats.deadbydaylight.com with your Behaviour account.
4. Optionally switch on **"Open the stats page when DBD is closed"**: when you close DBD after at least one round, the program opens the page in the browser (never while DBD runs).

When the page opens, the script saves the matches as `dbdmapscout-matches.json` into the download folder – only if a new match is among them, and only start time, map, custom game yes/no, role, character, status, length and BP (no names of other players, no account or login data; the script sends nothing anywhere). The program looks into the download folder every 20 s (every 3 s after opening the page), takes the matches into `official.jsonl` and **deletes the file**. Files with that name but without the program's marker are left alone. Matches are tied to rounds by map and start time (at most 3 min apart). Shown are avg. kills and 4K per map and per killer, the escape rate as survivor, and under "Last rounds" the column **Result** (3K / escaped / died). For tied rounds the killer from the page counts (so outfits are right automatically), and so does custom game. Notes appear for a **gap** (more than 30 matches between two visits of the page), a **different map than detected** (detection was wrong) and an **unknown status** – the page's status names are not documented and not yet checked against real data; such matches do not count, please report them with "Copy diagnostics". If the browser asks where to save each download, a dialog appears every time. If your download folder is elsewhere, set `official_dir` in `settings.json`.

**Unsure detection:** real map banners fit a known name almost perfectly. If none of the frames read fits well (fit below −3), not even 2.5 s later, the overlay shows "? UNSURE – CTRL+ALT+X = WRONG" in amber below the map, and the main window shows a bar with **Wrong map** / **Correct**. "Wrong map" (or `Ctrl+Alt+X`, works for any automatically detected map) hides the map, resets the timer and does not count the round; the same banner does not show it again. If the banner reads cleanly a moment later, the note goes away by itself.

**Rotate the map:** the **Rotate ↻** button in the main window or `Ctrl+Alt+R` turns the map on display by 90° clockwise, so it lies the way you picture the map. The rotation is remembered per map (Overlay tab: "Reset for this map"). The map name above the map stays upright; numbers and labels inside the map turn with it because they are part of the picture. All supplied maps carry their name on top in the same style; only on Midwich (animated GIF with its own background) does the name turn with the map. A map that turns with the camera by itself is not possible: only the game knows the camera angle, and its memory is never read.

**Keep in the black bar** (Overlay tab, on by default): on ultrawide the map stays inside the bar it is in, whatever the position – "top/bottom left" in the left bar, "top/bottom right" in the right one, a custom position in the bar where it starts. If it is too wide, it is made smaller instead of reaching into the game picture. A map placed over the middle of the game on purpose stays as it is. Switch it off if the map may be bigger than the bar.

The overlay is a native Windows window of its own: always on top, click-through, and it never takes the focus away from the game.

**Detection while other windows cover DBD.** Normally the screen is captured – if another window lies over DBD, the program sees that window. So while DBD is not the active window, the program uses **Windows' window capture** (Windows Graphics Capture, the same technique as OBS "Window Capture"): Windows delivers the picture of the DBD window, whatever lies on top. The game is not touched. Once DBD has been active again for 5 seconds, it goes back to the lighter screen capture. Nothing works while minimised. Can be switched off in the Detection tab ("Also detect when other windows cover DBD"). `start.bat` installs the extra package once at the next start; if that fails, everything keeps working through screen capture. The line "Aufnahme" (capture) in the diagnostics shows which source is in use.

| Hotkey | Function |
|---|---|
| `Ctrl+Alt+M` | overlay on/off |
| `Ctrl+Alt+V` | switch layout variant (e.g. Coal Tower ↔ Coal Tower II) |
| `Ctrl+Alt+S` | scan the screen (if automatic detection missed the banner) |
| `Ctrl+Alt+←` / `→` | previous / next map |
| `Ctrl+Alt+↑` / `↓` | overlay bigger / smaller – applies to the map on display and is remembered per map (Overlay tab: "Reset for this map"; the "Size" slider is the default size for all others) |
| `Ctrl+Alt+P` | change position (drag the overlay with the mouse, mouse wheel = size, press again = done) |
| `Ctrl+Alt+R` | turn the map on display by 90° (remembered per map) |
| `Ctrl+Alt+X` | **Wrong map:** hide the detected map, reset the timer, do not count the round |

**Backing up settings:** Settings → Backup → "Export settings …" saves everything (hotkeys, size and rotation per map, own map assignments, overlay, regions) to a file, "Import settings …" loads it again and restarts the program. The statistics are not part of it.

Hotkeys can be changed under **Settings → Hotkeys**: click the field and press the new combination (Esc cancels, Delete switches the hotkey off, "Defaults" resets all). Letters and digits need Ctrl or Alt so the hotkey does not block normal typing; combinations used twice are refused. All settings are stored in `settings.json`.

**Game language:** English and German map names are recognised by default. If DBD runs in French, Spanish, Italian, Polish, Portuguese or Turkish, tick that language in the control window (Detection tab). This is independent of the language of the program itself.

## Choosing the server region (like "Make Your Choice")

The **Server** tab lists all DBD server regions (AWS GameLift) with their current ping. Tick the regions you want to play on and press **Apply selection**. All other regions are blocked in the Windows **hosts file**: their server names then point to 0.0.0.0, DBD cannot reach them and only looks for matches in the allowed regions. **Allow all** removes the blocks again.

- **Administrator rights:** the hosts file is a Windows system file, so Windows asks when applying and when allowing all. Only this write runs with administrator rights, not the program itself (unless you start it as administrator or use the connected server display, see below).
- **Restart DBD afterwards.** The region is fixed when the game starts.
- **What exactly is written:** only a section of its own, marked "DbD Map Scout: server regions". Before the first change the original file is saved next to it as `hosts.dbdmapscout-backup`. Entries of "Make Your Choice" or other tools for the same servers are removed when applying, because they would otherwise override the selection. The program asks first.
- **Ping:** measured like the game does, through GameLift's UDP ping beacons (port 7770), otherwise with a normal ping. The names are resolved directly at the DNS server, so blocked regions get a value too. It only measures while the tab is open or when you press "Measure ping".
- **Limits:** unreliable with a VPN. Unlike the "Enforced" mode of Make Your Choice, the program sets no firewall rules. In rare cases DBD may therefore still fall back to another region, usually N. Virginia. The blocks stay active while the program is closed. At start the log reports when regions are blocked.
- **Not taken over** from Make Your Choice: firewall mode, custom splash screen and skipping trailers (these change game files), queue display through the third-party service Dead by Queue.

### Connected game server ("Connected to")

With the checkbox **Show which server DBD is connected to** in the Server tab, the program shows which server DBD is connected to, e.g. "Connected to: Frankfurt (3.120.45.67)". Between matches it says "Waiting for a match …". The display also appears in the main window below the round timer and in the overlay below the timer as a green dot with the region ("● FRANKFURT", without IP, can be switched off in the Overlay tab), below it the ping ("PING 24 MS", green up to 60 ms, yellow up to 120 ms, red above), and the log reports every new server with its region. If it is outside your region selection, that is noted. The IP address is only shown live in the window and never written to the log file.

- **Administrator rights:** reading the network traffic needs them. If you start the program as administrator, it runs without asking. Otherwise Windows asks once per program start while the checkbox is ticked.
- **What is read:** only the headers of the network packets (IP addresses and ports), never their contents. Only your own PC's traffic arrives: the network card is not put into promiscuous mode, which would also accept other devices' packets. If Windows does not support this, the display stays off instead of falling back to that mode. Nothing is sent, nothing is changed and nothing is stored. The game is not touched, and no extra driver such as Npcap is needed.
- **How the server is found:** a running match constantly exchanges many UDP packets with its server. The region is part of the name AWS gives the server address (reverse DNS, e.g. `…eu-central-1.compute.amazonaws.com`). Other programs with a lot of UDP traffic, such as voice chat, are ignored because they do not run on AWS servers.
- **Ping:** measured like in the Server tab and like DBD itself: every 5 seconds a small UDP packet to the GameLift ping beacon of the connected region; shown is the median of the last three measurements. The game server itself receives no packets. It is in the same data centre, so the value practically equals the game ping.
- **Economical:** if DBD has not been running for 30 seconds (e.g. during a download), the capture pauses and restarts automatically once DBD runs – only when the program runs as administrator, since otherwise every restart would trigger a Windows prompt.
- **Limits:** with a VPN the display may be missing. Without administrator rights, e.g. after a declined Windows prompt, it stays off.
- **Safest:** start the program normally instead of as administrator; then only the small capture helper runs with admin rights (one Windows prompt per start). If you want to be completely on the safe side, leave the checkbox off – map detection and overlay do not need the capture.

## How detection works

1. About 5 times per second, only the bottom-left area of the DBD window is captured, like a screen recording. Once the map is detected and the match is running, this drops to once per second (saving performance for the game); after the end of the round it goes back to the full rate.
2. It looks for the **thin dividing line** between map name and realm. It is a very distinctive feature and costs only a few milliseconds. As long as it is not visible, no OCR runs.
3. If it is there, the line of text above it (map name, also on two lines) and below it (realm) are cut out precisely. This works regardless of resolution, UI scale and monitor format.
4. A text recognition model (PaddleOCR PP-OCRv4, running locally) gives probabilities per letter. Instead of guessing text from them, the program **computes for every known map name how likely exactly that name is**, together with the realm. That is why background, fog and apostrophes hardly matter, and "COAL TOWER" can be told apart from "COAL TOWER II".
5. The results of several pictures are combined. Unknown text (e.g. a new map without a picture) is not mapped to a wrong map but reported in the log.

**Assigning an unknown map.** If the program reads a map name it does not know (e.g. after a DBD update or with a different spelling), the main window shows "Unknown map read: "…"" with the button **Assign …**. Choose the right map there (a suggestion is preselected) – the name read is recognised from then on. The assignments are stored in `settings.json` and survive updates; the realm is still checked. Delete them under **Settings → Own map assignments**.

Note on variants: since patch 8.6.0 the II/III layouts (MacMillan II, Ormond II/III, Badham II–V) can only be played in custom games. With an unsure reading, the standard layout is therefore slightly preferred. `Ctrl+Alt+V` or the layout button switches by hand.

### How good is the detection?

Tested with real DBD screenshots and with rebuilt map banners on real game backgrounds. Rebuilt means: Roboto font, geometry measured from real 4K screenshots, EN/DE, fog, snow, fade-in animation.

| Test | Result |
|---|---|
| real banner screenshots (2 maps × 5 resolutions × 2 backgrounds) | 20/20 correct |
| all 56 pictures × EN/DE, mixed resolutions 720p–4K + ultrawide | 112/112 correct map incl. layout |
| the same with very busy backgrounds | 112/112 correct map, 1× wrong layout (Badham II → I) |
| screens without a banner (lobby, menus, gameplay, end screen) | 0 false alarms in 319 pictures |
| banners with unknown map names | 0 of 120 wrongly assigned to a map |
| comparison with the approach of dbd-map-overlay (rebuilt), 1440p, single picture with fully visible banner | 55/56 instead of 44/56, about 0.1 s instead of 1.5–3 s per picture |

The synthetic tests do not replace a real test. If a map is not detected in real rounds, the debug pictures (see below) help to fine-tune.

## Own / new maps

- **Own map picture (recommended):** Maps tab → "Add map picture …" (or "Add picture …" after an unrecognised banner). Choose a picture, then either replace the picture of an existing map or create a new map (name as shown in the banner, and realm). The program cuts off the border, makes the background of the community maps (dark blue `#282a42`, grey violet `#535781`, 10 % tolerance) transparent, scales the picture to 1280 px height and saves it as WebP in `user_maps/`. With "Put the map name on top" (on by default) it writes the name above the map like on the supplied maps (white with a shadow, font Fira Sans ExtraBold); if the picture already has a name on top, it stays as it is. A preview shows before/after. Animated GIFs are used unchanged. `user_maps/` is ignored by git, so the update at start keeps working. Own pictures take precedence over the supplied ones; "Delete own picture" restores the original.
- **Adding a picture by hand:** put the file into a subfolder of `user_maps/` (or `maps/`), named after the map name as shown in the game, e.g. `user_maps/New Realm/New Map.png`. The program then recognises it automatically (English name or the name from the file). Pictures in `maps/` count as your own changes and stop the automatic update.
- **Replacing a picture:** replace the file in `maps/` or change the path under `variants` in `maps.json`.
- **Additional spelling:** add `"aliases": ["OTHER NAME"]` to the map in `maps.json`.

## When something does not work

- **The map is not visible:** press "Test overlay" in the Overlay tab. The map then appears for 10 seconds at its normal position, even if it would be hidden right now (press again – "End test" – to hide it at once). If no map was shown before, none is shown after the test either. If it stays invisible, press "Copy diagnostics" and pass the text on. It contains window position, window style and Z-order relative to DBD.
- **The map is not detected:** tick "Save debug pictures" in the control window and start a match. The folder `debug/` then receives the pictures the program saw, with the text it read.
- **The map does not disappear after the round:** look at the line "End-of-round detection" in the Detection tab. Right afterwards press "Copy diagnostics": the text contains the latest checks (what was read for "CONTINUE", currencies and loading bar, and whether the mouse pointer was visible). With "Save debug pictures", small screenshots from the round are also saved in `debug/frames/`.
- **Testing your own screenshots:** drag screenshots with a visible map banner (Win+Print) onto `screenshot_testen.bat`. The window then shows what is detected.
- **Seeing error messages:** `start_debug.bat` starts with a console. There is also the log file `dbdmapscout.log`.
- **"Capture is black":** set DBD to "Windowed Fullscreen". Windows HDR can also cause capture problems.
- **A hotkey does not work:** the log reports when another program uses the combination. Choose another one under Settings → Hotkeys.

## Rules / fair play

The program was deliberately built so that it **does not interact with the game**:

- no keyboard or mouse input to the game, no automation of game actions,
- no access to the game process (no memory reading, no injection, not even a process handle), no network connection to the game,
- no game files are read or changed,
- only screen pixels are read (like OBS/Discord) and whether the Windows mouse pointer is currently visible (the same system information OBS uses to draw the pointer in recordings). Only the map name the game shows to everyone is used,
- a static community map is shown, no hidden information (no generators, no positions),
- map detection and overlay open no internet connection (updates: only in the starter and on the "Check for updates now" button, GitHub only), text recognition runs completely locally. Only the **Server** tab measures the ping to AWS GameLift servers on request.
- The statistics page **Kills & Escapes** only reads a file your browser saves from the official stats page (own userscript) and deletes it afterwards. If you want, the program opens that page in the browser once DBD was closed – the program itself makes no connection for it.
- The **Server** tab does not change the game but the Windows hosts file. That is a system setting for the whole PC and can be undone at any time with "Allow all". BHVR has neither officially allowed nor forbidden region tools like "Make Your Choice". Here too: use at your own risk.

BHVR's [Game Rules](https://forums.bhvr.com/dead-by-daylight/kb/articles/139-game-rules) forbid third-party software that gives an "unfair advantage that wasn't intended by the game" unless it is approved. There is no official approval for map overlays. The decision is BHVR's, use at your own risk. Tournaments and leagues have their own rules.

## Structure

```
start.bat               start (sets everything up the first time)
start_debug.bat         start with console
screenshot_testen.bat   test screenshots by drag & drop
maps/                   map pictures
maps.json               picture ↔ in-game names (EN/DE/FR/ES/IT/PL/PT/TR), realm, variants
models/                 OCR models (PP-OCRv4, ONNX)
dbdmapscout/            program code (Python); hostsedit.py writes the hosts file (the only part with admin rights)
tests/                  self tests (optional: pip install pytest, then python -m pytest tests)
```

Licences and sources: see `THIRD_PARTY.md`.
