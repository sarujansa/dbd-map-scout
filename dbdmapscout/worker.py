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

from .capture import IS_WIN, ImageSource, ScreenGrabber, cursor_state, find_game_window, foreground_root
from .i18n import _
from .detector import ROI, Accumulator, BannerReader, OutOfMatchWatcher
from .lobby import LobbyReader, QueueTracker, corner_box, result_box
from .matchend import MatchEndTracker, Signals
from .ocr import Recognizer

log = logging.getLogger("dbdmapscout")
END_CHECK_INTERVAL = 0.5          # seconds between two looks for result screen / lobby / loading screen …
END_IDLE_INTERVAL = 1.0           # … and while nothing points to the end yet (whole-screen grab: ~14 MB each)
IN_MATCH_RATE = 1.0               # scans per second while a detected map is being played (banner only at the start)
LOBBY_INTERVAL = 1.0              # seconds between two looks at the lobby button (never during a match)
LOBBY_RATE = 1.0                  # banner scans per second while the lobby button is on screen: the banner
LOBBY_HOLD = 3.0                  # only comes after the loading screen; full rate again 3 s after the button went


@dataclass
class Event:
    kind: str          # status | detected | unknown | banner | menu | match_end | watch_info | warn | scan_result | error
    data: dict


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
        self.watch_status = _("keine Map angezeigt")
        self.capture_info = "Bildschirm"                     # where the pictures come from (diagnosis)
        self.end_history = collections.deque(maxlen=80)     # for the diagnosis
        self.queue = QueueTracker()                          # lobby: search / waiting time / role
        self.lobby_info = "–"                                # last look at the lobby button (diagnosis)
        self._scanner = None
        self._reported = set()
        self._last_frame_save = 0.0

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

    def _report(self, key, text):
        """An unexpected error: full text to the log file, one line to the UI (once per kind)."""
        log.error(text)
        if key not in self._reported:
            self._reported.add(key)
            last = text.strip().splitlines()[-1] if text.strip() else key
            self.post("warn", text=f"{key}: {last}")

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
        source = ImageSource(self.simulate) if self.simulate else None
        grabber = None if source else ScreenGrabber()
        from .wincapture import CapturePolicy, WindowCapture, describe
        policy = CapturePolicy()          # window capture (WGC) while DBD is in the background
        wcap = None
        wcap_failed = None                # hwnd the window capture could not be started for
        wcap_told = False
        via = {"screen": True}            # last picture came from the screen (-> our overlay is in it)

        window, window_checked = None, 0.0
        session, last_seen, session_frames = False, 0.0, []
        tracker = MatchEndTracker()
        tracker_gen = None
        last_end_check = 0.0
        last_hist = 0.0
        last_status = None
        black_since = None

        while self.running:
            tick = time.time()
            # --------------------------------------------------- commands
            try:
                while True:
                    cmd = self.commands.get_nowait()
                    if cmd[0] == "stop":
                        return
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

                def grab(box, _o=origin, _size=(fw, fh), _cap=wcap):
                    if _cap is not None:
                        img = _cap.grab(box[0], box[1], box[2], box[3], expect_size=_size)
                        if img is not None:
                            via["screen"] = False
                            return img
                    via["screen"] = True
                    return grabber.grab(_o[0] + box[0], _o[1] + box[1], box[2], box[3])

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
                if img.size and float(img.mean()) < 1.0 and window is not None:
                    black_since = black_since or tick
                    if tick - black_since > 8:
                        warn = _("Aufnahme ist schwarz – DBD im Modus „Fenster-Vollbild“ betreiben")
                        self._status(warn, last_status)
                        last_status = warn
                else:
                    black_since = None

                if source is None and via["screen"] and self.overlay_rect:
                    self._mask_overlay(img, origin[0] + box[0], origin[1] + box[1])
                sep, res = reader.read(img, fw, fh)
                if sep is not None:
                    if not session:
                        session, session_frames = True, []
                        acc.reset()
                        self.post("banner", t=tick)
                    last_seen = tick
                    if res is not None:
                        session_frames.append((res.name_text, res.realm_text, res.name_fit))
                        d = acc.add(res)
                        if d is not None:
                            self.post("detected", map_id=d.map_id, variant=d.variant, probability=d.probability,
                                      variant_probability=d.variant_probability, name_text=d.name_text,
                                      realm_text=d.realm_text, frames=d.frames)
                        if self.settings.get("save_debug_images"):
                            self._save_debug(img, res, sep)
                elif session and tick - last_seen > 1.5:
                    session = False
                    if acc.decided is None and session_frames:
                        best = max(session_frames, key=lambda f: f[2])
                        self.post("unknown", name_text=best[0], realm_text=best[1])

            # ------------------------------------- lobby: searching / found / role (never in a match)
            if (self.settings.get("auto_detect", True) and sep is None and not session
                    and tick - last_lobby >= LOBBY_INTERVAL and (source is not None or window is not None)
                    and not (self.map_on_screen and tracker.in_trial)):
                last_lobby = tick
                try:
                    cb = corner_box(fw, fh)
                    corner = grab(cb)
                    if source is None and via["screen"] and self.overlay_rect:
                        self._mask_overlay(corner, origin[0] + cb[0], origin[1] + cb[1])
                    view = lobby_reader.read(corner, fw, fh)
                    if view.button is not None:
                        lobby_button_t = tick
                    self.lobby_info = (f"{view.button or '–'} ({'–' if view.fit is None else f'{view.fit:.1f}'}) "
                                       f"„{view.name}“ „{view.time_text}“ → {view.kind or '–'}")
                    for ev in self.queue.update(view, tick):
                        self._queue_event(ev, tick)
                except Exception:
                    self._report("Lobby-Erkennung", traceback.format_exc())

            # ------------------------------------- left the trial? -> hide map
            gen = self.watch_gen
            if gen != tracker_gen:
                tracker.reset(gen[0] if gen else None, gen[1] if gen else None, tick)
                tracker_gen = gen
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
                        ignore = None
                        if source is None and via["screen"] and self.overlay_rect:
                            ignore = self._mask_overlay(look, origin[0], origin[1])   # in place: no 14 MB copy
                        obs = out_of_match.observe(look, ignore)
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
                                role = lobby_reader.result_role(look[ry:ry + rh, rx:rx + rw])
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

            rate = max(1.0, float(self.settings.get("scans_per_second", 5)))
            if self.map_on_screen and tracker.in_trial and not session:
                rate = min(rate, IN_MATCH_RATE)          # in the match: save CPU for the game
                if watching and "Scan/s" not in self.watch_status:
                    self.watch_status += f" · {IN_MATCH_RATE:.0f} Scan/s"
            elif not session and tick - lobby_button_t < LOBBY_HOLD:
                rate = min(rate, LOBBY_RATE)             # in the lobby / queue: no banner possible yet
            elif source is None and window is None:
                rate = 1.0                               # no DBD: only looking for its window
            try:
                cmd = self.commands.get(timeout=max(0.02, 1.0 / rate - (time.time() - tick)))
                self.commands.put(cmd)          # handled at the top of the next loop
            except queue.Empty:
                pass
        if grabber:
            grabber.close()
        if wcap is not None:
            wcap.stop()

    def _queue_event(self, ev, tick):
        """QueueTracker events -> UI: what=search | cancel | role | found."""
        if ev[0] == "search":
            self.post("queue", what="search", since=self.queue.search_start, role=self.queue.role,
                      killer=self.queue.killer)
        elif ev[0] == "cancel":
            self.post("queue", what="cancel")
        elif ev[0] == "left":
            self.post("queue", what="left")
        elif ev[0] == "role":
            self.post("queue", what="role", role=ev[1], killer=self.queue.killer)
        elif ev[0] == "found":
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
                    frame = wcap.grab(0, 0, window.width, window.height, expect_size=(window.width, window.height))
                if frame is None:
                    frame = grabber.grab(window.left, window.top, window.width, window.height)
            else:
                frame = grabber.grab(*grabber.primary_monitor())
            hits = self._scanner.scan(frame)
            self.post("scan_result", hits=hits, seconds=time.time() - t0)
        except Exception as e:
            self.post("scan_result", hits=[], seconds=time.time() - t0, error=str(e))

    # ------------------------------------------------------------- helpers
    def _mask_overlay(self, img, left, top):
        """Black out our own overlay in a screenshot (it is always on top and would
        otherwise be read as part of the game picture)."""
        r = self.overlay_rect
        if not r:
            return
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
