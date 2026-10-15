"""What music plays (since 1.64, user's wish: "Läuft gerade" in the black bar).

Read from the Windows media controls (GlobalSystemMediaTransportControlsSessionManager – the same list the volume
flyout of Windows shows: Spotify, a browser tab, …) through the pywinrt packages (MIT, pinned in
requirements.txt; checked like windows-capture: they import no OpenProcess, hooks or input functions). Only the
title, artist and whether it plays are read – nothing is controlled, nothing is logged, DBD is not touched.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

IS_WIN = sys.platform == "win32"
POLL_EVERY = 2.0            # seconds between two looks
STALE_AFTER = 6.0           # a reading older than this is not shown (thread stuck / stopped)
MAX_CHARS = 22              # longer titles are cut with "…" (no wider than the system value rows)
PLAYING = 4                 # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING


@dataclass(frozen=True)
class NowPlaying:
    title: str = ""
    artist: str = ""
    playing: bool = False
    t: float = 0.0          # time.time() of the reading


def clip(text: str, limit: int = MAX_CHARS) -> str:
    """One line of at most ``limit`` characters; cut at a word where possible."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" -–·,") + "…"


def rows(now: NowPlaying, wall: float, label: str, dim, white) -> list:
    """HUD rows (pure): nothing unless something plays and the reading is fresh."""
    if not now.playing or not now.title or wall - now.t > STALE_AFTER:
        return []
    out = [[(label, dim), (clip(now.title), white)]]
    if now.artist:
        out.append([(clip(now.artist), dim)])
    return out


class _Reader:
    """The WinRT calls (Windows only). ``read()`` -> NowPlaying; raises when the media controls fail."""

    def __init__(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        self._manager = Manager.request_async().get()

    def read(self) -> NowPlaying:
        session = self._manager.get_current_session()
        if session is None:
            return NowPlaying(t=time.time())
        status = session.get_playback_info().playback_status
        props = session.try_get_media_properties_async().get()
        if props is None:
            return NowPlaying(t=time.time())
        return NowPlaying(title=str(props.title or ""), artist=str(props.artist or ""),
                          playing=int(status) == PLAYING, t=time.time())


class MediaWatcher:
    """Looks every POLL_EVERY seconds in its own thread while ``active`` (set by the app: shown in the bar and
    DBD running). ``now`` is replaced as a whole – safe to read from the UI thread. ``error`` for the diagnosis."""

    def __init__(self, reader=None):
        self.active = False
        self.now = NowPlaying()
        self.error = ""
        self._reader = reader
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None and (IS_WIN or self._reader is not None):
            self._thread = threading.Thread(target=self._run, daemon=True, name="media")
            self._thread.start()

    def stop(self):
        self._stop.set()

    def diag_line(self) -> str:
        """For "Diagnose kopieren": state and error only – never the title (what someone listens to is private)."""
        n = self.now
        seen = ("spielt" if n.playing else "pausiert/kein Titel") if n.t else "noch nicht gelesen"
        return f"Musik: aktiv={self.active}, {seen}" + (f", Fehler: {self.error}" if self.error else "")

    def look(self):
        """One reading (the thread's step; tests call it directly)."""
        if not self.active:
            self.now = NowPlaying()
            return
        try:
            if self._reader is None:
                self._reader = _Reader()
            self.now = self._reader.read()
            self.error = ""
        except Exception as e:                    # no media controls, package missing, … – never kill the thread
            if not self.error:
                log.info("Medien: nicht lesbar (%s)", type(e).__name__)
            self.error = f"{type(e).__name__}: {e}"
            self.now = NowPlaying()
            self._reader = None                   # try a fresh manager next time

    def _run(self):
        if IS_WIN:                                # WinRT needs an apartment in this thread: multithreaded,
            import ctypes                         # so the blocking .get() calls are allowed
            ctypes.windll.ole32.CoInitializeEx(None, 0)       # COINIT_MULTITHREADED
        while not self._stop.wait(POLL_EVERY):
            self.look()
