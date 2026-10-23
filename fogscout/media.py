"""What music plays (since 1.64, user's wish: "Läuft gerade" in the black bar).

Read from the Windows media controls (GlobalSystemMediaTransportControlsSessionManager – the same list the volume
flyout of Windows shows: Spotify, a browser tab, …) through the pywinrt packages (MIT, pinned in
requirements.txt; checked like windows-capture: they import no OpenProcess, hooks or input functions). Only the
title, artist, whether it plays, (1.64, user's wish) the cover picture and (1.64.7) the song's position are read – nothing is controlled,
nothing is saved or logged, DBD is not touched. The cover is read once per title and kept small in memory.
"""
from __future__ import annotations

import logging
import sys
import threading
import io
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

IS_WIN = sys.platform == "win32"
POLL_EVERY = 2.0            # seconds between two looks
STALE_AFTER = 6.0           # a reading older than this is not shown (thread stuck / stopped)
MAX_CHARS = 22              # a line this long fits the card at full size; longer ones get smaller text (1.65.2,
                            # user: "lieber die Schrift kleiner statt Zeilenumbruch") and wrap only below that
TITLE_LINES, ARTIST_LINES = 4, 2    # at most this many lines when even the smaller text does not fit
LONGEST = 90                # characters kept of a title (beyond that "…")
PLAYING = 4                 # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
COVER_PX = 160              # cover kept at most this big (the card shows it at ~70 px on 1440p)
MAX_COVER_BYTES = 4_000_000     # a bigger "thumbnail" is not read
ACCENT_SAT, ACCENT_VAL = 0.3, 0.25  # accent(): pixels at least this colourful / bright count
ACCENT_SHARE = 0.03         # … and the main colour weighs at least this much (else the bar stays white)
ACCENT_LIGHT = 0.62         # HLS lightness the accent is lifted to: readable on black
VIDEO, MUSIC = 2, 1         # MediaPlaybackType.VIDEO / .MUSIC (0 = unknown)
BROWSERS = ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "chromium", "zen", "librewolf")
VIDEO_MARK = "▶ "           # 1.8.4: a video's title starts with this on the card


@dataclass(frozen=True)
class NowPlaying:
    title: str = ""
    artist: str = ""
    playing: bool = False
    t: float = 0.0          # time.time() of the reading
    cover: object = field(default=None, compare=False)      # PIL RGBA ≤ COVER_PX or None
    position: float | None = None   # seconds into the song when Windows last reported it (1.64.7)
    duration: float | None = None   # length of the song in seconds
    at: float = 0.0                 # time.time() of that report – the position runs on from there while it plays
    kind: str = ""                  # 1.8.4: "music" | "video" | "" (see classify) – a video shows as "▶ Titel / Kanal"
    app: str = ""                   # the player's app id (chrome, Spotify.exe …) – diagnosis only, never a title


def classify(playback_type: int, album: str, app: str) -> str:
    """"video" or "music" (pure, 1.8.4 – user: YouTube Music and YouTube videos in the same browser). Windows'
    PlaybackType is reliable from players (Movies & TV, VLC: VIDEO), but every browser reports MUSIC for all it
    plays – there the album decides: YouTube Music, Spotify Web … fill it, a YouTube or Twitch video has none."""
    if int(playback_type or 0) == VIDEO:
        return "video"
    low = (app or "").lower()
    if any(b in low for b in BROWSERS):
        return "music" if (album or "").strip() else "video"
    return "music"


def progress(now: NowPlaying, wall: float):
    """(elapsed, total) in seconds for the progress bar, or None (pure). Players report the position only now and
    then (Spotify: on play, pause, seek), so it runs on from the report while the song plays."""
    if now.position is None or not now.duration or now.duration <= 0:
        return None
    el = now.position + (max(0.0, wall - now.at) if now.playing else 0.0)
    return min(max(0.0, el), now.duration), now.duration


def clock(seconds: float) -> str:
    s = int(max(0, seconds))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def decode_cover(data: bytes):
    """The cover as a small PIL RGBA picture, None for no / broken / too big data (pure)."""
    if not data or len(data) > MAX_COVER_BYTES:
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.draft("RGB", (COVER_PX, COVER_PX))          # JPEG: decode at a fraction of the size
        img = img.convert("RGBA")
        img.thumbnail((COVER_PX, COVER_PX))
        return img
    except Exception:
        return None


def accent(cover):
    """Main colour of the cover for the progress bar (1.2.4, user's pick from a list: "Farbe aus dem Cover"),
    as (r, g, b, 255) light enough to read on the dark game edge, or None for a grey cover (pure)."""
    if cover is None:
        return None
    memo = getattr(cover, "info", None)
    if isinstance(memo, dict) and "_dbdms_accent" in memo:    # 1.6.1: once per cover, not twice a second
        return memo["_dbdms_accent"]
    out = _accent(cover)
    if isinstance(memo, dict):
        memo["_dbdms_accent"] = out
    return out


def _accent(cover):
    import colorsys
    raw = cover.convert("RGB").resize((24, 24)).tobytes()
    px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    bins = {}
    for r, g, b in px:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < ACCENT_SAT or v < ACCENT_VAL:              # grey, black, white: no colour
            continue
        k = int(h * 18) % 18
        w = s * v
        acc = bins.setdefault(k, [0.0, 0.0, 0.0, 0.0])
        acc[0] += w
        acc[1] += r * w
        acc[2] += g * w
        acc[3] += b * w
    if not bins:
        return None
    total, r, g, b = max(bins.values(), key=lambda a: a[0])
    if total < ACCENT_SHARE * len(px):                   # a few coloured pixels are no main colour
        return None
    h, light, s = colorsys.rgb_to_hls(r / total / 255, g / total / 255, b / total / 255)
    r, g, b = colorsys.hls_to_rgb(h, min(0.8, max(ACCENT_LIGHT, light)), min(0.9, max(0.5, s)))
    return int(r * 255), int(g * 255), int(b * 255), 255


def look(o: dict) -> tuple:
    """Options of the music card's look from the overlay settings (1.2.4, pure)."""
    shape = o.get("media_cover_shape", "style")          # 1.8.24: round / square / the style's own
    return tuple(k for k, key in (("accent", "media_accent"), ("remaining", "media_remaining"),
                                  ("backdrop", "media_backdrop")) if o.get(key, True)) + \
        ((f"cover_{shape}",) if shape in ("round", "square") else ())


class Fader:
    """Fading the music card in and out (1.2.4, user's pick: "sanft ein- und ausblenden"), pure: ``value`` = share
    of the opacity, moved towards ``target`` by step(now) – eased, IN_S / OUT_S long."""
    IN_S, OUT_S = 0.35, 0.25
    STEP_MS = 30

    def __init__(self):
        self.value = self.start = self.target = 1.0
        self.t = 0.0

    def go(self, target: float, now: float, start=None):
        if start is not None:
            self.value = start
        self.start, self.target, self.t = self.value, target, now

    def step(self, now: float) -> bool:
        """Advance; True when the target is reached."""
        span = self.IN_S if self.target > self.start else self.OUT_S
        f = 1.0 if span <= 0 else min(1.0, max(0.0, (now - self.t) / span))
        f = f * f * (3 - 2 * f)                              # smooth start and end
        self.value = self.start + (self.target - self.start) * f
        return f >= 1.0


class Transition:
    """A song change on the music card (1.8.1, user: "smoother … die Liste bleibt bestehen und rutscht hoch"):
    for SWAP_S the old song's card cross-fades into the new one while the queue rows slide up a row – pure.
    ``old`` = the render arguments of the card as it was, ``leaving`` = the queue row that became the song
    (slides out at the top) or None (plain cross-fade)."""
    SWAP_S = 0.35
    STEP_MS = 40

    def __init__(self, old: dict, leaving, now: float):
        self.old, self.leaving, self.t0 = old, leaving, now

    def progress(self, now: float) -> float:
        f = min(1.0, max(0.0, (now - self.t0) / self.SWAP_S))
        return f * f * (3 - 2 * f)

    def done(self, now: float) -> bool:
        return now - self.t0 >= self.SWAP_S


def playing(now: NowPlaying, wall: float) -> bool:
    """Something plays and the reading is fresh (pure)."""
    return bool(now.playing and now.title and wall - now.t <= STALE_AFTER)


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


def wrap(text: str, limit: int = MAX_CHARS, lines: int = TITLE_LINES) -> list:
    """The whole text on lines of at most ``limit`` characters, broken between words (a longer word is cut);
    only what does not fit on ``lines`` lines ends with "…" (pure, 1.65)."""
    words, out, cur = " ".join(str(text or "").split()).split(" "), [], ""
    for word in words:
        while len(word) > limit:                   # one word longer than a line
            if cur:
                out.append(cur)
                cur = ""
            out.append(word[:limit])
            word = word[limit:]
        cur = f"{cur} {word}" if cur and word else (cur or word)
        if len(cur) > limit:
            out.append(cur[:len(cur) - len(word) - 1])
            cur = word
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines - 1] + [clip(" ".join(out[lines - 1:]), limit)]
    return out


def rows(now: NowPlaying, wall: float, label: str, dim, white) -> list:
    """HUD rows (pure): nothing unless something plays and the reading is fresh. Title and artist whole, one row
    each – the card sets them smaller when they are long (overlay_win32.fit_lines)."""
    if not playing(now, wall):
        return []
    title = clip(now.title, LONGEST)                # one row each: the card makes long ones smaller (fit_lines)
    if now.kind == "video":                          # 1.8.4: a video is marked, its "artist" is the channel
        title = VIDEO_MARK + title
    out = [[(label, dim), (title, white)] if label else [(title, white)]]
    if now.artist:
        out.append([(clip(now.artist, LONGEST), dim)])
    return out


class _Reader:
    """The WinRT calls (Windows only). ``read()`` -> NowPlaying; raises when the media controls fail."""

    def __init__(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        self._manager = Manager.request_async().get()
        self._cover_key, self._cover = None, None

    def read(self, want_cover: bool = True) -> NowPlaying:
        session = self._manager.get_current_session()
        if session is None:
            return NowPlaying(t=time.time())
        status = session.get_playback_info().playback_status
        props = session.try_get_media_properties_async().get()
        if props is None:
            return NowPlaying(t=time.time())
        title, artist = str(props.title or ""), str(props.artist or "")
        try:                                      # 1.8.4: music or video (kind), the player for the diagnosis
            app = str(session.source_app_user_model_id or "")
        except Exception:
            app = ""
        try:
            kind = classify(int(props.playback_type or 0), str(props.album_title or ""), app)
        except Exception:
            kind = classify(0, "", app)
        cover = None
        if want_cover and title:
            key = (title, artist)
            if key != self._cover_key:            # once per title: the picture does not change while it plays
                try:
                    data = self._cover_bytes(props.thumbnail)
                except Exception:                 # no picture is fine: title and artist still show
                    data = b""
                self._cover_key, self._cover = key, decode_cover(data)
            cover = self._cover
        pos = dur = None
        at = time.time()
        try:                                      # the song's progress (read only, like the rest)
            tl = session.get_timeline_properties()
            start = tl.start_time.total_seconds()
            end = tl.end_time.total_seconds()
            if end > start:
                dur, pos = end - start, tl.position.total_seconds() - start
                updated = tl.last_updated_time.timestamp()
                if 0 < at - updated < 24 * 3600:
                    at = updated                  # the position belongs to this moment, not to now
        except Exception:
            pos = dur = None
        return NowPlaying(title=title, artist=artist, playing=int(status) == PLAYING, t=time.time(), cover=cover,
                          position=pos, duration=dur, at=at, kind=kind, app=app)

    @staticmethod
    def _cover_bytes(ref) -> bytes:
        """The bytes of the media's thumbnail (in memory only); b"" when there is none."""
        if ref is None:
            return b""
        from winrt.windows.storage.streams import Buffer, InputStreamOptions
        stream = ref.open_read_async().get()
        try:
            n = int(stream.size)
            if not 0 < n <= MAX_COVER_BYTES:
                return b""
            buf = stream.read_async(Buffer(n), n, InputStreamOptions.READ_AHEAD).get()
            return bytes(memoryview(buf))
        finally:
            stream.close()


class MediaWatcher:
    """Looks every POLL_EVERY seconds in its own thread while ``active`` (set by the app: shown in the bar and
    DBD running). ``now`` is replaced as a whole – safe to read from the UI thread. ``error`` for the diagnosis."""

    def __init__(self, reader=None):
        self.active = False
        self.want_cover = False                   # set by the app (cover card: not wired up yet)
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
        what = f", Art={n.kind or '?'}, App={n.app or '?'}" if n.title else ""      # 1.8.4: never the title
        return f"Musik: aktiv={self.active}, {seen}{what}" + (f", Fehler: {self.error}" if self.error else "")

    def look(self):
        """One reading (the thread's step; tests call it directly)."""
        if not self.active:
            self.now = NowPlaying()
            return
        try:
            if self._reader is None:
                self._reader = _Reader()
            self.now = self._reader.read(self.want_cover)
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
