"""Small pictures of the maps for the tiles of the maps page (1.8.72), pure – no Qt.

Decoding a 1280-px map picture and shrinking it took 30–45 ms per tile in the window thread (measured: 55 tiles
≈ 2.1 s, in slices of one picture per 10 ms – the page stuttered until all were in, on every first visit and every
style click). Now a thumbnail is made once per picture (``thumbnail``: the file's path, mtime and size are its
key, so a replaced own picture or a new style cache file gets a new one) and kept as a PNG below ``cache/thumbs``;
``Loader`` decodes in a thread of its own and hands the finished RGBA bytes to the window thread, which only
turns them into pixmaps (``_pending`` → the page's timer). The thread never touches Qt (qt_clip 1.8.66).
"""
from __future__ import annotations

import hashlib
import os
import queue
import threading
import time

from PIL import Image

VERSION = 1                       # raise when the thumbnails change: the cache is made anew
PRUNE_AFTER_S = 90 * 24 * 3600    # a cache file not used for this long goes (prune, once per session)


def cache_name(path: str, box: tuple) -> str:
    """File name of the thumbnail of ``path`` in a cache folder: path, mtime, size and box, so that a changed
    picture never shows its old thumbnail."""
    try:
        st = os.stat(path)
        stamp = f"{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        stamp = "missing"
    key = f"{os.path.abspath(path)}|{stamp}|{box[0]}x{box[1]}|v{VERSION}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:24] + ".png"


def thumbnail(path: str, box: tuple, cache_dir: str | None = None) -> Image.Image:
    """The picture at ``path`` shrunk to fit ``box`` (RGBA, first frame). From ``cache_dir`` when it is there
    (the file's mtime is refreshed – ``prune`` keeps what is used), else decoded and, with a cache folder, saved
    for the next time. OSError/ValueError of a broken picture are the caller's."""
    target = os.path.join(cache_dir, cache_name(path, box)) if cache_dir else None
    if target and os.path.isfile(target):
        try:
            with Image.open(target) as im:
                pic = im.convert("RGBA")
            try:
                os.utime(target)
            except OSError:
                pass
            return pic
        except (OSError, ValueError):
            pass                                      # unreadable cache file: made anew below
    with Image.open(path) as im:
        im.seek(0)
        pic = im.convert("RGBA")
    pic.thumbnail((max(1, box[0]), max(1, box[1])), Image.LANCZOS)      # as the tiles were drawn before
    if target:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            tmp = target + f".{os.getpid()}.tmp"
            pic.save(tmp, "PNG", optimize=False)
            os.replace(tmp, target)                   # never a half-written file under the final name
        except OSError:
            pass
    return pic


def prune(cache_dir: str, now: float | None = None, max_age_s: float = PRUNE_AFTER_S) -> int:
    """Delete thumbnails nobody used for ``max_age_s`` (their mtime is refreshed on every use); the number
    removed. Only our own PNG files in the folder."""
    if not cache_dir or not os.path.isdir(cache_dir):
        return 0
    now = time.time() if now is None else now
    gone = 0
    for name in os.listdir(cache_dir):
        if not name.endswith(".png"):
            continue
        full = os.path.join(cache_dir, name)
        try:
            if now - os.stat(full).st_mtime > max_age_s:
                os.remove(full)
                gone += 1
        except OSError:
            pass
    return gone


class Loader:
    """Thumbnails in a thread: ``request(paths)`` replaces the list to do (the newest request wins, a picture
    already in hand is finished first); ``take()`` in the window thread gives the finished ones as
    (path, width, height, RGBA bytes) – a broken picture comes as (path, 0, 0, b"")."""

    def __init__(self, box: tuple, cache_dir: str | None = None):
        self.box = tuple(box)
        self.cache_dir = cache_dir
        self._done: queue.Queue = queue.Queue()
        self._lock = threading.Condition()
        self._todo: list = []
        self._gen = 0
        self._thread = None
        self._pruned = False

    def request(self, paths):
        """Make these (in this order); what an earlier request still had to do is dropped."""
        with self._lock:
            self._todo = list(paths)
            self._gen += 1
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True, name="map-thumbs")
                self._thread.start()
            self._lock.notify()

    def take(self, limit: int = 8) -> list:
        """Up to ``limit`` finished thumbnails (window thread)."""
        out = []
        while len(out) < limit:
            try:
                out.append(self._done.get_nowait())
            except queue.Empty:
                break
        return out

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._todo) or not self._done.empty()

    def _next(self, wait_s: float):
        with self._lock:
            if not self._todo:
                self._lock.wait(wait_s)
            if self._todo:
                return self._todo.pop(0)
            return None

    def _run(self):
        idle_since = time.time()
        while True:
            path = self._next(1.0)
            if path is None:
                if time.time() - idle_since > 30:            # nothing to do for a while: the thread ends
                    with self._lock:
                        if not self._todo:
                            self._thread = None
                            return
                continue
            idle_since = time.time()
            self._done.put(self.make(path))
            if not self._pruned and self.cache_dir:
                self._pruned = True
                try:
                    prune(self.cache_dir)
                except OSError:
                    pass

    def make(self, path: str) -> tuple:
        """One thumbnail as (path, width, height, RGBA bytes) – also usable without the thread (tests)."""
        try:
            pic = thumbnail(path, self.box, self.cache_dir)
        except (OSError, ValueError):
            return (path, 0, 0, b"")
        return (path, pic.width, pic.height, pic.tobytes("raw", "RGBA"))
