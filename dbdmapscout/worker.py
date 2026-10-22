"""Background thread: capture -> detect -> events for the UI thread."""
from __future__ import annotations

import collections
import logging
import os
import queue
import threading
import time
import traceback
from dataclasses import dataclass

import cv2

from .capture import (IS_WIN, ImageSource, ScreenGrabber, cursor_state, find_game_window, foreground_root,
                      overlaps, windows_above)
from .i18n import _
from .detector import ROI, Accumulator, BannerReader, OutOfMatchWatcher, has_loading_bar, is_dark, letterbox_rows
from .layout import MIN_VBAR
from .lobby import LobbyReader, QueueTracker, corner_box, crossplay_box, crossplay_off, result_box
from .matchstart import MatchStart
from .matchend import MatchEndTracker, Signals
from .ocr import Recognizer

log = logging.getLogger("dbdmapscout")
END_CHECK_INTERVAL = 0.5          # seconds between two looks for result screen / lobby / loading screen …
END_IDLE_INTERVAL = 1.0           # … and while nothing points to the end yet (whole-screen grab: ~14 MB each)
IN_MATCH_RATE = 1.0               # scans per second while a detected map is being played (banner only at the start)
VBAR_STRIP_S = 1.0                # 1.8.65: without a map, a look at the bars above/below at most this often
VBAR_LOOKS = 5                    # looks (1/s) whose smallest black bar above/below counts (dark scenes at the edge)
MID_MATCH_AFTER = 30.0            # s after the map appeared: a "banner" now is in the game world -> strict reading
MID_MATCH_SPAN = 2.0              # … and it must stay on screen this long (a real banner stands still for ~5 s,
                                  # light strips in the world move with the camera)
RESULT_MISSES_KEPT = 10           # 1.8.72: result screens without a role kept in debug/result
SIGHTINGS_KEPT = 20               # mid-match sightings kept in debug/midmatch (picture + text each), newest first
GLOBE_KEPT = 10                   # 1.5.4: unreadable cross-play globe crops kept in debug/lobby
GLOBE_SAVE_EVERY = 120.0          # s between two saved crops (one per lobby is enough)
MENU_RATE = 1.0                   # 1.6.4: banner scans per second in menus, store, bloodweb … (no banner there)
FAST_AFTER_LOBBY = 120.0          # … full rate for this long after the lobby button was last on screen (READY → match)
FAST_AFTER_LOADING = 90.0         # … and after a loading screen was seen (the banner follows it)
START_LOOK_INTERVAL = 1.0         # 1.6: seconds between two looks for the end of the loading screen (armed only)
LOBBY_INTERVAL = 1.0              # seconds between two looks at the lobby button (never during a match)
LOBBY_RATE = 1.0                  # banner scans per second while the lobby button is on screen: the banner
TICK_FAIL_LIMIT = 30               # 1.8.38: ticks in a row that raise before the detection counts as crashed
TICK_FAIL_WAIT_S = 1.0            # … pause after one (no busy loop on a lasting fault)
TICK_FAIL_LOG_S = 60.0            # … the same traceback goes to the log at most this often
LOBBY_HOLD = 3.0                  # only comes after the loading screen; full rate again 3 s after the button went


def _wgc_grab(cap, window, box):
    """``box`` (game-picture coordinates) from the window capture, or None. In window mode its pictures
    include title bar and frame: the game picture sits at an offset that depends on the picture size."""
    size = cap.size
    off = window.capture_offset(size) if size is not None else (0, 0)
    if off is None:
        return None
    return cap.grab(box[0] + off[0], box[1] + off[1], box[2], box[3],
                    expect_size=size or (window.width, window.height))


@dataclass
class Event:
    kind: str          # status | detected | unknown | banner | menu | match_end | watch_info | warn | scan_result | error
    data: dict


def scan_rate(base: float, *, in_match: bool, session: bool, since_button: float, since_loading: float,
              live: bool, lobby_visible: bool) -> float:
    """Banner scans per second (pure, 1.6.4). Full rate while a banner is being read, after a loading screen and in
    the two minutes after the lobby button (READY, loading, spawn); 1/s in the match (banner only at its start), in
    the lobby (no banner possible) and everywhere else in the menus – there a banner is read at most a second late,
    after its first frame the session runs at full rate. Simulation (not live): full rate outside the match."""
    base = max(1.0, base)
    if session:
        return base
    if in_match:
        return min(base, IN_MATCH_RATE)
    if lobby_visible:
        return min(base, LOBBY_RATE)
    if not live or since_loading <= FAST_AFTER_LOADING or since_button <= FAST_AFTER_LOBBY:
        return base
    return min(base, MENU_RATE)


class DetectionWorker(threading.Thread):
    def __init__(self, root_dir: str, settings, catalog, events: queue.Queue, simulate: str | None = None):
        super().__init__(daemon=True, name="detector")
        self.root_dir = root_dir
        self.settings = settings
        self.catalog = catalog
        self.events = events
        self.simulate = simulate
        self.commands: queue.Queue = queue.Queue()
        self.running = True
        self.map_on_screen = False       # set by the UI: a map is displayed (not hidden after a match)
        self.watch_gen = None            # set by the UI: (number, source) of the map on display
        self.overlay_rect = None         # set by the UI: overlay position on screen (x, y, w, h) or None
        self.hud_rect = None             # … and of the system values at the top of a bar
        self.media_rect = None           # … and of the music card ("Läuft gerade", 1.64)
        self.today_rect = None           # … and of "today" (its own card since 1.2.6)
        self.info_rect = None            # … and of the map's lines when they are their own element (1.8.24)
        self.guide_rects = ()            # … and of the centre guide lines while moving (1.64.5)
        self.toast_rect = None           # … and of the notification window (1.8.13: F8 clip, lobby found)
        self.vbars = None                # (top, bottom, time, (w, h)): black bars above/below the picture
        self._vbar_looks = collections.deque(maxlen=VBAR_LOOKS)
        self._vbar_strip_t = 0.0
        self.watch_status = _("keine Map angezeigt")
        self.capture_info = "Bildschirm"                     # where the pictures come from (diagnosis)
        self.end_history = collections.deque(maxlen=80)     # for the diagnosis
        self.queue = QueueTracker()                          # lobby: search / waiting time / role
        self.match_start = MatchStart()                      # 1.6: end of the loading screen (recording start)
        self.lobby_info = "–"                                # last look at the lobby button (diagnosis)
        self.banner_history = collections.deque(maxlen=20)  # every banner-like sighting and its outcome (diagnosis)
        self.role_misses = collections.deque(maxlen=5)      # 1.8.72: result screens without a role read (diagnosis)
        self._scanner = None
        self._reported = set()
        self._fail_text, self._fail_logged = "", 0.0     # 1.8.38: last tick error logged, when
        self._last_frame_save = 0.0
        self._last_sighting_save = 0.0

    # ------------------------------------------------------------- helpers
    def post(self, kind, **data):
        self.events.put(Event(kind, data))

    def stop(self):
        self.running = False
        self.commands.put(("stop",))

    def request_scan(self):
        self.commands.put(("scan",))

    def set_catalog(self, catalog):
        self.commands.put(("catalog", catalog))

    def _banner_seen(self, t, strict, frames, acc, picture=None):
        """One line per banner-like sighting for the diagnosis: what was read and what came of it."""
        best = max(frames, key=lambda f: f[2]) if frames else ("", "", None)
        lead = acc.best()
        outcome = ("erkannt " + acc.decided[0] + (" (unsicher)" if acc.decided_unsure else "") if acc.decided
                   else "ignoriert" if strict and frames else "unbekannt" if frames else "kein Text")
        fit = "–" if best[2] is None else f"{best[2]:.1f}"
        like = f" · am ehesten {lead[0]} p={lead[1]:.2f}" if lead else ""
        self.banner_history.append(
            f"{time.strftime('%H:%M:%S', time.localtime(t))} {'mitten in der Runde' if strict else 'Rundenstart'} · "
            f"{len(frames)} Bilder, {acc.good_frames} lesbar · „{best[0]}“ / „{best[1]}“ Passung {fit}{like} "
            f"→ {outcome}" + (f" · Bild debug/midmatch/{picture}" if picture else ""))

    def _report(self, key, text):
        """An unexpected error: full text to the log file, one line to the UI (once per kind)."""
        log.error(text)
        if key not in self._reported:
            self._reported.add(key)
            last = text.strip().splitlines()[-1] if text.strip() else key
            self.post("warn", text=f"{key}: {last}")

    def _tick_failed(self, text: str, fails: int) -> bool:
        """1.8.38: a tick raised (OCR, capture, a tracker …). The full text goes to the log (a repeated one at most
        every TICK_FAIL_LOG_S), the UI hears it once; the loop goes on with the next frame. False after
        TICK_FAIL_LIMIT ticks in a row: the detection is broken for good – reported as a crash."""
        now = time.time()
        if text != self._fail_text or now - self._fail_logged >= TICK_FAIL_LOG_S:
            self._fail_text, self._fail_logged = text, now
            self._report("Erkennung", text)
        if fails >= TICK_FAIL_LIMIT:
            self.post("error", text=text)
            return False
        return True

    # ---------------------------------------------------------------- loop
    def run(self):
        try:
            self._run()
        except Exception:
            self.post("error", text=traceback.format_exc())

    def _run(self):
        models = os.path.join(self.root_dir, "models")
        rec = Recognizer(os.path.join(models, "ch_PP-OCRv4_rec_infer.onnx"),
                         threads=self.settings.get("ocr_threads", 2))
        reader = BannerReader(rec, self.catalog)
        acc = Accumulator()
        out_of_match = OutOfMatchWatcher(rec)
        lobby_reader = LobbyReader(rec)
        last_lobby = 0.0
        lobby_button_t = -1e9             # last look that saw PLAY / CANCEL / READY
        last_start_look = -1e9            # 1.6: last look for the end of the loading screen
        last_loading = -1e9               # 1.6.4: last look that showed a loading screen (scan rate)
        source = ImageSource(self.simulate) if self.simulate else None
        grabber = None if source else ScreenGrabber()
        from .wincapture import CapturePolicy, WindowCapture, describe
        policy = CapturePolicy()          # window capture (WGC) while DBD is in the background
        wcap = None
        wcap_failed = None                # hwnd the window capture could not be started for
        wcap_told = False
        via = {"screen": True}            # last picture came from the screen (-> our overlay is in it)
        self.hidden_looks = 0
        self.scan_rate = 0.0                                 # 1.6.4: banner scans per second right now (diagnosis)
        self._globe_saved = 0.0           # 1.5.4: last saved cross-play crop             # looks skipped: DBD in the background, another window over it

        window, window_checked = None, 0.0
        session, last_seen, session_frames = False, 0.0, []
        session_strict, session_t, session_saved = False, 0.0, None
        tracker = MatchEndTracker()
        tracker_gen = None
        trial_since = 0.0                 # when the map on display appeared (tracker reset)
        last_end_check = 0.0
        last_hist = 0.0
        last_status = None
        black_since = None
        fails, failed = 0, False          # 1.8.38: ticks in a row that raised, did the last one

        while self.running:
            try:
                fails, failed = (fails if failed else 0), False   # a tick that ends in "continue" counts as fine
                tick = time.time()
                # --------------------------------------------------- commands
                try:
                    while True:
                        cmd = self.commands.get_nowait()
                        if cmd[0] == "stop":
                            self.running = False
                            break
                        if cmd[0] == "catalog":
                            self.catalog = cmd[1]
                            reader = BannerReader(rec, self.catalog)
                            acc.reset()
                            if self._scanner:
                                self._scanner = None
                        if cmd[0] == "scan":
                            self._manual_scan(rec, grabber, source, window, wcap)
                except queue.Empty:
                    pass
                if not self.running:
                    break                        # 1.8.38: not return – the capture below is closed

                # --------------------------------------------- where is DBD?
                if source is None and tick - window_checked > 1.5:
                    window = find_game_window()
                    window_checked = tick
                if source is not None:
                    frame = source.current()
                    if frame is None:
                        time.sleep(0.5)
                        continue
                    fh, fw = frame.shape[:2]
                    status = f"Simulation: {os.path.basename(self.simulate)}"
                    grab = lambda box: frame[box[1]:box[1] + box[3], box[0]:box[0] + box[2]]
                    origin = (0, 0)
                else:
                    if window is not None and window.minimized:
                        self._status(_("DBD ist minimiert"), last_status)
                        last_status = _("DBD ist minimiert")
                        time.sleep(0.5)
                        continue
                    if window is not None and window.width > 100 and window.height > 100:
                        origin = (window.left, window.top)
                        fw, fh = window.width, window.height
                        status = _("DBD gefunden ({w}×{h}) – warte auf Map-Banner", w=fw, h=fh)
                    else:
                        # no DBD: no automatic detection – a DBD video or screenshot on the desktop must not open
                        # the overlay over other work ("Scannen" still looks at the main screen)
                        ml, mt, mw, mh = grabber.primary_monitor()
                        origin, fw, fh = (ml, mt), mw, mh
                        status = _("DBD nicht gefunden – Erkennung startet, sobald DBD läuft")
                    # ---- DBD in the background: take its picture from Windows instead of the screen
                    win_ok = source is None and window is not None and not window.minimized and window.width > 100
                    fg_now = win_ok and foreground_root() == window.hwnd
                    if policy.update(tick, IS_WIN and bool(self.settings.get("window_capture", True)), win_ok, fg_now):
                        if wcap is not None and (wcap.hwnd != window.hwnd or wcap.closed):
                            if wcap.closed and wcap.hwnd == window.hwnd:
                                wcap_failed = window.hwnd           # ended by itself: do not restart every tick
                            wcap.stop()
                            wcap = None
                        if wcap is None and wcap_failed != window.hwnd:
                            wcap = WindowCapture(window.hwnd)
                            if wcap.start():
                                if not wcap_told:
                                    wcap_told = True
                                    self.post("watch_info", text=_("DBD im Hintergrund – Fensteraufnahme aktiv: die Map "
                                                                   "wird auch erkannt, wenn andere Fenster darüber "
                                                                   "liegen."))
                            else:
                                self.post("warn", text=_("Fensteraufnahme nicht möglich, nutze Bildschirmaufnahme "
                                                         "({error})", error=wcap.error))
                                wcap_failed, wcap = window.hwnd, None
                    elif wcap is not None:
                        wcap.stop()
                        wcap = None
                    self.capture_info = describe(wcap, policy.active)
                    if wcap is not None and via["screen"]:
                        self.capture_info += " · letztes Bild vom Bildschirm (Fensteraufnahme ohne Bild)"
                    if self.hidden_looks:
                        self.capture_info += f" · {self.hidden_looks}× verdeckt, ausgelassen"
                    covers = []                       # windows over DBD (looked up once per tick, when needed)

                    def grab(box, _o=origin, _cap=wcap, _win=window, _fg=fg_now, _covers=covers):
                        """Part of the game picture, or None: DBD is in the background, the window capture had
                        no picture and another window lies over that part of the screen (e.g. our own
                        statistics) – then nothing is read rather than someone else's pixels."""
                        if _cap is not None and _win is not None:
                            img = _wgc_grab(_cap, _win, box)
                            if img is not None:
                                via["screen"] = False
                                return img
                        via["screen"] = True
                        rect = (_o[0] + box[0], _o[1] + box[1], box[2], box[3])
                        if _win is not None and not _fg:
                            if not _covers:
                                _covers.append(windows_above(_win.hwnd))
                            if overlaps(rect, _covers[0]):
                                self.hidden_looks += 1
                                return None
                        return grabber.grab(*rect)

                if not self.settings.get("auto_detect", True):
                    status = _("Automatische Erkennung ist aus")
                if status != last_status:
                    self._status(status, last_status)
                    last_status = status
                sep = None
                if self.settings.get("auto_detect", True) and (source is not None or window is not None):
                    # ------------------------------------------------ banner search
                    box = (int(ROI[0] * fw), int(ROI[1] * fh), int((ROI[2] - ROI[0]) * fw), int((ROI[3] - ROI[1]) * fh))
                    try:
                        img = grab(box)
                    except Exception as e:           # e.g. window moved off-screen
                        warn = _("Bildschirmaufnahme fehlgeschlagen: {error}", error=e)
                        self._status(warn, last_status)
                        last_status = warn
                        time.sleep(1.0)
                        continue
                    if img is not None and img.size and float(img.mean()) < 1.0 and window is not None:
                        black_since = black_since or tick
                        if tick - black_since > 8:
                            warn = _("Aufnahme ist schwarz – DBD im Modus „Fenster-Vollbild“ betreiben")
                            self._status(warn, last_status)
                            last_status = warn
                    else:
                        black_since = None

                    if img is None:
                        sep = res = None                # covered by another window: nothing of DBD to read
                    else:
                        if source is None and via["screen"] and (self.overlay_rect or self.hud_rect or self.media_rect or self.today_rect or self.info_rect or self.guide_rects or self.toast_rect):
                            self._mask_overlay(img, origin[0] + box[0], origin[1] + box[1])
                        if not self.map_on_screen:
                            self._vbar_strip(grab, fw, fh, tick, origin, lambda: source is None and via["screen"])
                        boxed = self._letterboxed(fw, fh)
                        # 1.8.62: without a line, read at the banner's spot – not well into a round (game world)
                        mid = self.map_on_screen and tracker.in_trial and tick - trial_since >= MID_MATCH_AFTER
                        bars = self._vbar_looks[-1][:2] if boxed and not mid else None
                        sep, res = reader.read(img, fw, fh, letterboxed=boxed, bars=bars)
                    if sep is not None:
                        if not session:
                            session, session_frames, session_t, session_saved = True, [], tick, None
                            # DBD shows the banner only at the start of a trial: well into a running round it is
                            # something in the game world (neon strips, signs) – only a clean read may switch
                            session_strict = (self.map_on_screen and tracker.in_trial
                                              and tick - trial_since >= MID_MATCH_AFTER)
                            acc.reset()
                            if not session_strict:
                                self.post("banner", t=tick)
                        last_seen = tick
                        if res is not None:
                            session_frames.append((res.name_text, res.realm_text, res.name_fit))
                            d = acc.add(res, strict=session_strict,
                                        hold=session_strict and tick - session_t < MID_MATCH_SPAN)
                            if session_strict and (d is not None or (session_saved is None
                                                                     and tick - self._last_sighting_save >= 10)):
                                # always kept (no debug switch needed): the only way to see what fooled the reader
                                self._last_sighting_save = tick
                                session_saved = self._save_sighting(img, res, sep, "umgeschaltet" if d else "gesehen")
                            if d is not None:
                                lobby = self.queue.lobby_for_round(tick)   # 1.8.71: also a lobby seen only briefly
                                self.queue.round_started(tick)  # 1.8.43: the lobby is used up (same custom lobby next)
                                self.post("detected", lobby=lobby, map_id=d.map_id, variant=d.variant, probability=d.probability,
                                          variant_probability=d.variant_probability, name_text=d.name_text,
                                          realm_text=d.realm_text, frames=d.frames, name_fit=d.name_fit,
                                          unsure=d.unsure)
                            if self.settings.get("save_debug_images"):
                                self._save_debug(img, res, sep)
                    elif session and tick - last_seen > 1.5:
                        session = False
                        self._banner_seen(session_t, session_strict, session_frames, acc, session_saved)
                        if acc.decided is None and session_frames:
                            best = max(session_frames, key=lambda f: f[2])
                            if session_strict:            # mid-match: only a note in the log, no "unknown map" bar
                                lead = acc.best()
                                self.post("ignored", name_text=best[0], realm_text=best[1],
                                          map_id=lead[0] if lead else None, name_fit=best[2], frames=acc.good_frames)
                            else:
                                self.post("unknown", name_text=best[0], realm_text=best[1])

                # ------------------------------------- lobby: searching / found / role (never in a match)
                if (self.settings.get("auto_detect", True) and sep is None and not session
                        and tick - last_lobby >= LOBBY_INTERVAL and (source is not None or window is not None)
                        and not (self.map_on_screen and tracker.in_trial)):
                    last_lobby = tick
                    try:
                        cb = corner_box(fw, fh)
                        corner = grab(cb)
                        if corner is not None:
                            if source is None and via["screen"] and (self.overlay_rect or self.hud_rect or self.media_rect or self.today_rect or self.info_rect or self.guide_rects or self.toast_rect):
                                self._mask_overlay(corner, origin[0] + cb[0], origin[1] + cb[1])
                            view = lobby_reader.read(corner, fw, fh)
                            if view.button is not None:
                                lobby_button_t = tick
                                # 1.2.20: the cross-play globe above the button (farming rounds) – a second small grab
                                xb = crossplay_box(fw, fh)
                                globe = grab(xb)
                                if globe is not None:
                                    if source is None and via["screen"] and (self.overlay_rect or self.hud_rect or self.media_rect or self.today_rect or self.info_rect or self.guide_rects or self.toast_rect):
                                        self._mask_overlay(globe, origin[0] + xb[0], origin[1] + xb[1])
                                    view.crossplay_off = crossplay_off(globe, fw, fh)
                                    if view.crossplay_off is None and tick - self._globe_saved > GLOBE_SAVE_EVERY:
                                        self._globe_saved = tick    # 1.5.4 (user: farming not recognised): keep the
                                        self._save_globe(globe, view.button)   # unreadable crop for a look
                            fit = "–" if view.fit is None else f"{view.fit:.1f}"
                            cross = {True: " · Crossplay aus", False: " · Crossplay an"}.get(view.crossplay_off, "")
                            self.lobby_info = (f"{view.button or '–'} ({fit}) "
                                               f"„{view.name}“ „{view.time_text}“ → {view.kind or '–'}{cross}")
                            for ev in self.queue.update(view, tick):
                                self._queue_event(ev, tick)
                    except Exception:
                        self._report("Lobby-Erkennung", traceback.format_exc())

                # ------------------------------------- 1.6: loading screen over -> the match begins (recording)
                # 1.6.4: also unarmed – a loading screen tells the scan rate that a banner is coming
                ms = self.match_start
                if self.map_on_screen and ms.armed:
                    ms.disarm()                          # a banner came first: the recording starts there
                elif (not self.map_on_screen and sep is None and not session
                        and tick - last_start_look >= START_LOOK_INTERVAL
                        and (source is not None or window is not None)):
                    last_start_look = tick
                    try:
                        look = grab((0, 0, fw, fh))
                        if look is not None:             # None: covered -> no look, nothing changes
                            if source is None and via["screen"] and (self.overlay_rect or self.hud_rect or self.media_rect or self.today_rect or self.info_rect or self.guide_rects or self.toast_rect):
                                self._mask_overlay(look, origin[0], origin[1])
                            bar, dark = has_loading_bar(look), is_dark(look)
                            if bar and dark:
                                last_loading = tick
                            if ms.armed and ms.update(tick, bar, dark, tick - lobby_button_t < START_LOOK_INTERVAL * 1.5):
                                log.info("Ladebildschirm vorbei – das Match beginnt")
                                self.post("match_start", t=tick)
                    except Exception:
                        self._report("Matchbeginn", traceback.format_exc())

                # ------------------------------------- left the trial? -> hide map
                gen = self.watch_gen
                if gen != tracker_gen:
                    tracker.reset(gen[0] if gen else None, gen[1] if gen else None, tick)
                    tracker_gen = gen
                    trial_since = tick
                use_end = bool(self.settings.get("hide_after_match", True))
                use_menu = bool(self.settings.get("pause_in_menus", True))
                watching = (self.map_on_screen and gen is not None and (use_end or use_menu)
                            and tracker.active and not tracker.ended)
                if watching:
                    tracker.use_end, tracker.use_cursor = use_end, use_menu
                    if source is not None:                       # simulation: no window, no pointer
                        game, foreground, pointer = True, True, None
                    else:
                        game = window is not None
                        foreground = game and foreground_root() == window.hwnd
                        pointer = None
                        if foreground:
                            cur = cursor_state()
                            if cur is not None:
                                vis, cx, cy = cur
                                pointer = vis and (window.left <= cx < window.left + window.width
                                                   and window.top <= cy < window.top + window.height)
                    obs = full = look = None
                    interval = END_CHECK_INTERVAL if tracker.candidate else END_IDLE_INTERVAL
                    if sep is None and tick - last_end_check >= interval and (game or source is not None):
                        last_end_check = tick
                        try:
                            full = look = grab((0, 0, fw, fh))
                            if look is not None:                 # None: covered -> no observation, nothing changes
                                ignore = None
                                if source is None and via["screen"] and (self.overlay_rect or self.hud_rect or self.media_rect or self.today_rect or self.info_rect or self.guide_rects or self.toast_rect):
                                    ignore = self._mask_overlay(look, origin[0], origin[1])   # in place: no 14 MB copy
                                obs = out_of_match.observe(look, ignore)
                                self._note_vbars(look, fw, fh)
                        except Exception:
                            self._report("Rundenende-Prüfung", traceback.format_exc())
                    events = tracker.update(Signals(t=tick, game=game, foreground=foreground, cursor=pointer,
                                                    banner=sep is not None, obs=obs))
                    self.watch_status = tracker.describe()
                    interesting = obs is not None and (obs.reason or obs.continue_fit is not None
                                                       or obs.currency_groups or obs.loading)
                    if interesting or events or (obs is not None and tick - last_hist > 30):
                        last_hist = tick
                        ptr = "–" if pointer is None else ("sichtbar" if pointer else "verborgen")
                        line = (f"{time.strftime('%H:%M:%S')} {obs.describe() if obs else '(kein Bild)'} · "
                                f"Maus {ptr} · DBD aktiv {'ja' if foreground else 'nein'} · {tracker.describe()}")
                        if events:
                            line += " · " + ", ".join(e[0] + (f"={e[1]}" if len(e) > 1 else "") for e in events)
                        self.end_history.append(line)
                        if interesting or events:
                            log.info("Rundenende: %s", line)
                    if full is not None and self.settings.get("save_debug_images"):
                        tag = ("ende" if any(e[0] == "match_end" for e in events) else
                               "menue" if events else "hinweis" if interesting else None)
                        if tag or tick - self._last_frame_save > 5:
                            self._save_frame(full, tag or "runde")
                    for ev in events:
                        if ev[0] == "menu":
                            self.post("menu", on=ev[1], gen=tracker.generation)
                        elif ev[0] == "match_end":
                            role = None
                            if look is not None and ev[1] == "Ergebnisbildschirm":
                                try:     # categories BRUTALITY … / OBJECTIVES … (our overlay blacked out: 2 of 4 words do)
                                    rx, ry, rw, rh = result_box(fw, fh)
                                    crop = look[ry:ry + rh, rx:rx + rw]
                                    role = lobby_reader.result_role(crop)
                                    if role is None:     # 1.8.72: keep what was seen (user: farming rounds no role)
                                        self._result_miss(crop, getattr(lobby_reader, "last_result_text", ""))
                                except Exception:
                                    self._report("Rolle", traceback.format_exc())
                            self.post("match_end", reason=ev[1], gen=tracker.generation, t=tracker.end_t, role=role)
                        elif ev[0] == "armed" and tracker.source != "auto":
                            self.post("watch_info", text=_("Rundenende-Erkennung für die gewählte Map ist jetzt aktiv."))
                        elif ev[0] == "cursor_unreliable":
                            self.post("watch_info", text=_("Mauszeiger war beim Map-Banner sichtbar – Menü-Erkennung "
                                                           "per Mauszeiger ist für diese Runde aus."))
                elif not (use_end or use_menu):
                    self.watch_status = _("aus (Einstellung)")
                elif tracker.ended and self.map_on_screen:
                    self.watch_status = tracker.describe()
                elif not self.map_on_screen:
                    self.watch_status = (_("Runde vorbei – wartet auf die nächste Map") if tracker.ended
                                         else _("keine Map angezeigt"))

                in_match = self.map_on_screen and tracker.in_trial
                rate = scan_rate(float(self.settings.get("scans_per_second", 5)), in_match=in_match, session=session,
                                 since_button=tick - lobby_button_t, since_loading=tick - last_loading,
                                 live=source is None, lobby_visible=tick - lobby_button_t < LOBBY_HOLD)
                if in_match and not session and watching and "Scan/s" not in self.watch_status:
                    self.watch_status += f" · {IN_MATCH_RATE:.0f} Scan/s"
                if source is None and window is None:
                    rate = 1.0                               # no DBD: only looking for its window
                self.scan_rate = rate                        # diagnosis
                try:
                    cmd = self.commands.get(timeout=max(0.02, 1.0 / rate - (time.time() - tick)))
                    self.commands.put(cmd)          # handled at the top of the next loop
                except queue.Empty:
                    pass
            except Exception:                    # 1.8.38: one bad frame must not end the detection for good
                fails, failed = fails + 1, True
                if not self._tick_failed(traceback.format_exc(), fails):
                    break
                time.sleep(TICK_FAIL_WAIT_S)
        if grabber:
            grabber.close()
        if wcap is not None:
            wcap.stop()

    def _queue_event(self, ev, tick):
        """QueueTracker events -> UI: what=search | cancel | role | found."""
        if ev[0] == "search":
            self.post("queue", what="search", since=self.queue.search_start, role=self.queue.role,
                      killer=self.queue.killer, crossplay_off=self.queue.crossplay_off)
        elif ev[0] == "cancel":
            self.match_start.disarm()
            self.post("queue", what="cancel")
        elif ev[0] == "left":
            self.match_start.disarm()
            self.post("queue", what="left")
        elif ev[0] == "role":
            self.post("queue", what="role", role=ev[1], killer=self.queue.killer,
                      crossplay_off=self.queue.crossplay_off)
        elif ev[0] == "found":
            self.match_start.arm(tick)                # 1.6: one lobby arms one match start
            self.post("queue", what="found", found=ev[1], role=ev[1].role)
        elif ev[0] == "remind":
            self.post("queue", what="remind", seconds=ev[1])

    def _status(self, text, last):
        if text != last:
            self.post("status", text=text)

    # ---------------------------------------------------------- full scan
    def _manual_scan(self, rec, grabber, source, window, wcap=None):
        from .fullscan import FullScanner, TextDetector
        t0 = time.time()
        try:
            if self._scanner is None:
                det = TextDetector(os.path.join(self.root_dir, "models", "ch_PP-OCRv4_det_infer.onnx"),
                                   threads=max(2, int(self.settings.get("ocr_threads", 2))))
                self._scanner = FullScanner(det, rec, self.catalog)
            if source is not None:
                frame = source.current()
            elif window is not None and not window.minimized:
                frame = None
                if wcap is not None:
                    frame = _wgc_grab(wcap, window, (0, 0, window.width, window.height))
                if frame is None:
                    frame = grabber.grab(window.left, window.top, window.width, window.height)
            else:
                frame = grabber.grab(*grabber.primary_monitor())
            hits = self._scanner.scan(frame)
            self.post("scan_result", hits=hits, seconds=time.time() - t0)
        except Exception as e:
            self.post("scan_result", hits=[], seconds=time.time() - t0, error=str(e))

    # ------------------------------------------------------------- helpers
    def _note_vbars(self, look, fw, fh):
        """Black bars above/below the picture (window narrower than 16:9): the smallest of the last looks, so a
        dark scene at the picture edge does not count as bar; smaller bars apply at once (intro → gameplay)."""
        if self._vbar_looks and self._vbar_looks[-1][2] != (fw, fh):
            self._vbar_looks.clear()                 # window resized: old looks are void
        top, bottom = letterbox_rows(look)
        self._vbar_looks.append((top, bottom, (fw, fh)))
        self.vbars = (min(t for t, _b, _s in self._vbar_looks), min(b for _t, b, _s in self._vbar_looks),
                      time.time(), (fw, fh))

    def _vbar_strip(self, grab, fw, fh, tick, origin=(0, 0), from_screen=lambda: False):
        """1.8.65 (user's diagnosis 1718×1360: "Letzte Banner: keine"): the bars were measured only in the round-end
        looks, i.e. while a map is on display – before a round's banner there is none, so the picture never counted
        as letterboxed and neither the tolerant line pass nor the banner's fixed spot (1.8.62) ran. Now, in a window
        narrower than 16:9 and without a map, a quarter-wide strip from the middle at most every VBAR_STRIP_S.
        ``from_screen()``: the strip came from the screen (at ``origin``) – our own windows are blacked out first."""
        if fw * 9 >= fh * 16 - 32 or tick - self._vbar_strip_t < VBAR_STRIP_S:
            return
        self._vbar_strip_t = tick
        box = (fw * 3 // 8, 0, max(1, fw // 4), fh)
        strip = grab(box)
        if strip is None:
            return
        if from_screen():
            self._mask_overlay(strip, origin[0] + box[0], origin[1] + box[1])
        self._note_vbars(strip, fw, fh)

    def _letterboxed(self, fw, fh) -> bool:
        """The last whole-screen look (≤ ~1 s old) showed black bars above and below: a trial in a narrow window."""
        last = self._vbar_looks[-1] if self._vbar_looks else None
        return bool(last and last[2] == (fw, fh) and min(last[0], last[1]) >= MIN_VBAR)

    def _mask_overlay(self, img, left, top):
        """Black out our own overlay in a screenshot (it is always on top and would
        otherwise be read as part of the game picture)."""
        for r in (self.hud_rect, self.media_rect, self.today_rect, self.toast_rect, *self.guide_rects):
            if r:
                self._black_out(img, r, left, top)
        lines = self._black_out(img, self.info_rect, left, top)      # 1.8.24: the map's lines apart – they
        done = self._black_out(img, self.overlay_rect, left, top)     # count as the map (fills_bars' ignore)
        if lines and done:
            return (min(lines[0], done[0]), min(lines[1], done[1]), max(lines[2], done[2]), max(lines[3], done[3]))
        return done or lines

    @staticmethod
    def _black_out(img, r, left, top):
        if not r:
            return None
        x0, y0 = int(r[0] - left), int(r[1] - top)
        x1, y1 = x0 + int(r[2]), y0 + int(r[3])
        h, w = img.shape[:2]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 > x0 and y1 > y0:
            img[y0:y1, x0:x1] = 0
            return x0, y0, x1, y1                    # the blacked-out part, in picture coordinates
        return None

    def _save_frame(self, frame, tag):
        """Debug: downscaled screenshots while a map is shown (folder debug/frames)."""
        try:
            self._last_frame_save = time.time()
            d = os.path.join(self.root_dir, "debug", "frames")
            os.makedirs(d, exist_ok=True)
            h, w = frame.shape[:2]
            s = min(1.0, 1280.0 / max(1, w))
            small = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else frame
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
            cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tofile(os.path.join(d, f"{stamp}-{tag}.jpg"))
            files = sorted(os.listdir(d))
            for old in files[:-150]:
                os.remove(os.path.join(d, old))
        except Exception:
            pass

    # --------------------------------------------------------------- debug
    def _save_globe(self, img, button):
        """1.5.4: the cross-play zone when the globe could not be read (farming rounds not recognised) – PNG in
        debug/lobby, newest GLOBE_KEPT. The user sends these; the detector is tuned on them."""
        try:
            d = os.path.join(self.root_dir, "debug", "lobby")
            os.makedirs(d, exist_ok=True)
            name = time.strftime("%Y%m%d-%H%M%S") + f"-crossplay-{button or 'x'}.png"
            cv2.imencode(".png", img)[1].tofile(os.path.join(d, name))
            for old in sorted(f for f in os.listdir(d) if "-crossplay-" in f)[:-GLOBE_KEPT]:
                os.remove(os.path.join(d, old))
        except Exception:
            pass

    def _result_miss(self, crop, text):
        """1.8.72: the result screen gave no role – what was read goes to the diagnosis, the picture of the category
        zone to debug/result (only the newest RESULT_MISSES_KEPT)."""
        self.role_misses.append(f"{time.strftime('%H:%M:%S')} Bild {crop.shape[1]}×{crop.shape[0]} · "
                                f"gelesen „{text[:60]}“")
        try:
            d = os.path.join(self.root_dir, "debug", "result")
            os.makedirs(d, exist_ok=True)
            cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(
                os.path.join(d, time.strftime("%Y%m%d-%H%M%S") + ".jpg"))
            for old in sorted(os.listdir(d))[:-RESULT_MISSES_KEPT]:
                os.remove(os.path.join(d, old))
        except Exception:
            pass

    def _save_sighting(self, img, res, sep, tag):
        """Mid-match banner-like sighting: the captured region (separator marked) + what was read, in
        debug/midmatch – only the newest SIGHTINGS_KEPT. Returns the file name (None on failure)."""
        try:
            d = os.path.join(self.root_dir, "debug", "midmatch")
            os.makedirs(d, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
            name = f"{stamp}-{tag}.jpg"
            vis = img.copy()
            cv2.line(vis, (sep.x0, sep.y), (sep.x1, sep.y), (0, 0, 255), 1)
            cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(os.path.join(d, name))
            with open(os.path.join(d, f"{stamp}-{tag}.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"name: {res.name_text}\nrealm: {res.realm_text}\nbest: {res.best}\nfit: {res.name_fit:.2f}\n"
                         f"separator: x {sep.x0}-{sep.x1}, y {sep.y}, frac {sep.frac:.2f}\n")
            stamps = sorted({f.rsplit("-", 1)[0] for f in os.listdir(d)})
            for old in stamps[:-SIGHTINGS_KEPT]:
                for f in os.listdir(d):
                    if f.startswith(old + "-"):
                        os.remove(os.path.join(d, f))
            return name
        except Exception:
            return None

    def _save_debug(self, img, res, sep):
        try:
            d = os.path.join(self.root_dir, "debug")
            os.makedirs(d, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
            vis = img.copy()
            cv2.line(vis, (sep.x0, sep.y), (sep.x1, sep.y), (0, 0, 255), 1)
            cv2.imencode(".png", vis)[1].tofile(os.path.join(d, f"{stamp}.png"))
            with open(os.path.join(d, f"{stamp}.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"name: {res.name_text}\nrealm: {res.realm_text}\nbest: {res.best}\nfit: {res.name_fit:.2f}\n")
            files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
            for old in files[:-400]:                   # keep the folder small
                os.remove(os.path.join(d, old))
        except Exception:
            pass
