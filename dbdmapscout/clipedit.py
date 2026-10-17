"""Clip editor, the ffmpeg side (1.5.1, user's wish: "direkt im Programm bearbeiten wie in Medal"). Pure
functions and small threads around the ffmpeg binary of imageio-ffmpeg (``obsrec.ffmpeg_exe``) – no Qt here,
so it is testable without a window. Nothing touches the game; only the recording files the user chose.

Qt Multimedia was tried and works, but lives in PySide6-Addons (175 MB, with Qt WebEngine/Chromium inside) –
not worth it for a preview: ffmpeg decodes single frames in ~40 ms (scrubbing) and streams scaled frames for
playback; the sound of the clip is played by Windows (winsound) from a temporary WAV of the same stretch.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

from .obsrec import CLIPS_DIR as _CLIPS_DIR, NAME_CHARS, ffmpeg_exe

PREVIEW_H = 540                  # px: frames for the preview picture
THUMB_H = 54                     # px: pictures of the timeline strip
THUMBS = 24                      # pictures along the strip
FPS_CAP = 30.0                   # playback: at most this many frames a second (preview, not the file)
SIZE_RE = re.compile(rb"Video: .*?, (\d{2,5})x(\d{2,5})")
FPS_RE = re.compile(rb"(\d+(?:\.\d+)?) fps")
DURATION_RE = re.compile(rb"Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)")
CLIPS_DIR = _CLIPS_DIR         # one place for the folder name (obsrec)
CENSOR_STYLES = ("pixel", "blur", "black", "retouch")   # 1.7.2: how a censored area looks; 1.7.3 retouch = delogo
EDGE_PX = 2                                # delogo refuses a box that touches the frame edge: keep this far away
NAMES_BOX = (0.004, 0.50, 0.26, 0.32)      # DBD's survivor list bottom left (portraits + names + status text), as
                                           # fractions of the 16:9 game picture – 1.7.4 after the user's screenshot:
                                           # the list sits higher (≈ 50–82 % of the height) and long names reach further
MODES = ("copy", "exact", "discord")   # key frames, no re-encoding / frame exact / 1.6.1: fits a size (Discord)
TARGETS_MB = (10, 25, 50, 500)  # 1.6.1: Discord's upload limits (free 10 MB, Nitro Basic 50, Nitro 500)
DEFAULT_TARGET_MB = 10
AUDIO_KBPS = 96                 # sound of a size-fitted clip
SIZE_MARGIN = 0.90              # aim this far below the limit (container overhead, rate control)


@dataclass
class Info:
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 30.0

    @property
    def ok(self) -> bool:
        return self.duration > 0 and self.width > 0 and self.height > 0


def _flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def probe(path: str, ffmpeg: str | None = None) -> Info:
    """Length, picture size and frame rate from ``ffmpeg -i`` (imageio-ffmpeg ships no ffprobe)."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg:
        return Info()
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-i", path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=30, creationflags=_flags())
    except (OSError, subprocess.TimeoutExpired):
        return Info()
    err = p.stderr or b""
    info = Info()
    m = DURATION_RE.search(err)
    if m:
        info.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = SIZE_RE.search(err)
    if m:
        info.width, info.height = int(m.group(1)), int(m.group(2))
    m = FPS_RE.search(err)
    if m:
        info.fps = float(m.group(1)) or 30.0
    return info


def scaled(info: Info, height: int) -> tuple[int, int]:
    """Preview size: ``height`` tall, width even (ffmpeg's scale=-2)."""
    if not info.ok:
        return 16 * height // 9 // 2 * 2, height
    h = min(height, info.height)
    return max(2, round(info.width * h / info.height / 2) * 2), h


def frame_at(path: str, t: float, height: int = PREVIEW_H, info: Info | None = None, ffmpeg: str | None = None):
    """One picture at second ``t`` as PIL image (RGB), or None. Seeks to the key frame before ``t`` and decodes
    up to it – about 40 ms for 1080p, more for 1440p."""
    from PIL import Image
    ffmpeg = ffmpeg or ffmpeg_exe()
    info = info or probe(path, ffmpeg)
    if not ffmpeg or not info.ok:
        return None
    w, h = scaled(info, height)
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path,
                            "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
                           creationflags=_flags())
    except (OSError, subprocess.TimeoutExpired):
        return None
    need = w * h * 3
    if len(p.stdout) < need:
        return None
    return Image.frombytes("RGB", (w, h), p.stdout[:need])


def thumb_strip(path: str, times: list, height: int = THUMB_H, info: Info | None = None, ffmpeg: str | None = None,
                stop=lambda: False):
    """1.7.1 (user: the strip loaded slowly): the pictures for evenly spaced ``times`` from ONE ffmpeg run that
    decodes key frames only (``-skip_frame nokey``; the fps filter repeats the key frame before each moment) –
    yields (index, image) as they arrive instead of one seek + decode per picture. A picture may show the key
    frame up to one key-frame interval earlier (OBS: ~2–4 s), which is fine for a strip. ``stop()`` True ends it."""
    from PIL import Image
    ffmpeg = ffmpeg or ffmpeg_exe()
    info = info or probe(path, ffmpeg)
    if not ffmpeg or not info.ok or len(times) < 2:
        return
    step = times[1] - times[0]
    if step <= 0:
        return
    w, h = scaled(info, height)
    need = w * h * 3
    try:
        proc = subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-skip_frame", "nokey",
                                 "-ss", f"{max(0.0, times[0]):.3f}", "-i", path, "-an", "-sn",
                                 # the fps filter emits a moment only once a later frame arrived: clone the last
                                 # key frame long enough (tpad) so the strip's tail is not missing
                                 "-vf", f"scale={w}:{h},tpad=stop_mode=clone:stop_duration={6 * step:.3f},"
                                        f"fps=1/{step:.6f}", "-frames:v", str(len(times)),
                                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                creationflags=_flags())
    except OSError:
        return
    try:
        for i in range(len(times)):
            buf = b""
            while len(buf) < need and not stop():
                part = proc.stdout.read(need - len(buf))
                if not part:
                    break
                buf += part
            if len(buf) < need:
                return
            yield i, Image.frombytes("RGB", (w, h), buf)
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait(timeout=5)


def thumb_times(duration: float, n: int = THUMBS) -> list[float]:
    """Moments for the strip: the middle of n equal stretches."""
    n = max(1, n)
    return [duration * (i + 0.5) / n for i in range(n)]


def fmt_pos(seconds: float) -> str:
    """m:ss.t for the editor (tenths matter when cutting)."""
    s = max(0.0, float(seconds))
    m, s = int(s // 60), s % 60
    return f"{m}:{s:04.1f}"


def clip_name(round_name: str, start: float, end: float) -> str:
    """'2026-10-17 21-40 Coal Tower – Nurse – Clip 3m12s-3m40s' (file name without extension)."""
    base = os.path.splitext(re.split(r"[\\/]", round_name)[-1])[0]        # a Windows path on any system

    def tag(t):
        return f"{int(t // 60)}m{int(t % 60):02d}s"
    return NAME_CHARS.sub("", f"{base} – Clip {tag(start)}-{tag(end)}")[:150]


def unique_path(folder: str, name: str, ext: str) -> str:
    out = os.path.join(folder, name + ext)
    n = 2
    while os.path.exists(out):
        out = os.path.join(folder, f"{name} ({n}){ext}")
        n += 1
    return out


def cut(path: str, start: float, end: float, out: str, mode: str = "copy", ffmpeg: str | None = None,
        run=None, target_mb: float = DEFAULT_TARGET_MB, info: Info | None = None,
        retry: bool = True, censor=None, censor_style: str = "pixel") -> tuple[bool, str]:
    """Write the stretch ``start``..``end`` of ``path`` to ``out``. "copy" = stream copy (seconds of work; the
    cut lands on the key frame before ``start``, so the clip may begin up to a few seconds early), "exact" =
    frame exact, picture re-encoded (x264 veryfast, CRF 18; a 30-s clip takes some seconds), sound as AAC;
    "discord" (1.6.1) = re-encoded to stay under ``target_mb`` (discord_plan picks rate, size, frame rate).
    ``censor`` (1.7.2): boxes to hide (fractions of the picture, see censor_graph) – needs the picture re-encoded,
    so "copy" becomes "exact". Returns (ok, ffmpeg's last words on failure)."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg:
        return False, "ffmpeg fehlt"
    censor = list(censor or ())
    if censor and mode == "copy":
        mode = "exact"
    start, end = max(0.0, float(start)), float(end)
    if end <= start:
        return False, "Ende vor Anfang"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", path]
    vf = ""
    if mode == "discord":
        kbps, h, fps = discord_plan(end - start, target_mb, info)
        vf = f"scale=-2:{h},fps={fps:g}"
        args += ["-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k",
                 "-maxrate", f"{int(kbps * 1.1)}k", "-bufsize", f"{kbps * 2}k", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k"]
    elif mode == "exact":
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac",
                 "-b:a", "160k"]
    else:
        args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    if censor:
        if info is None or not info.ok:
            info = probe(path, ffmpeg)
        args += ["-filter_complex", censor_graph(censor, censor_style, info.width, info.height, vf),
                 "-map", "[vout]", "-map", "0:a?"]
    elif vf:
        args += ["-vf", vf]
    args += ["-movflags", "+faststart", out] if out.lower().endswith(".mp4") else [out]
    if run is None:
        def run(a):
            p = subprocess.run(a, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               timeout=1800, creationflags=_flags())
            return p.returncode, p.stderr or b""
    try:
        rc, err = run(args)
    except (OSError, subprocess.TimeoutExpired) as e:
        rc, err = 1, str(e).encode()
    ok = rc == 0 and os.path.exists(out) and os.path.getsize(out) > 0
    if not ok:
        try:
            os.remove(out)
        except OSError:
            pass
        return False, err[-300:].decode("utf-8", "replace").strip()
    if mode == "discord" and retry and os.path.getsize(out) > target_mb * 1024 * 1024:
        # the rate control overshot (very busy pictures): once more with less, never a file over the limit
        return cut(path, start, end, out, mode, ffmpeg, run, target_mb * 0.8, info, retry=False, censor=censor,
                   censor_style=censor_style)
    return True, ""


def names_box(width: int, height: int) -> tuple:
    """1.7.2: where DBD draws the survivor names (bottom left of the game picture) as a box (x, y, w, h) in
    fractions of a frame ``width`` × ``height`` – the game picture is 16:9 centred in a wider frame (ultrawide
    recordings of the whole screen carry the black bars)."""
    if width <= 0 or height <= 0:
        return NAMES_BOX
    gw = min(width, height * 16 / 9)
    off = (width - gw) / 2 / width
    x, y, w, h = NAMES_BOX
    return (off + x * gw / width, y, w * gw / width, h)


def box_px(box, width: int, height: int) -> tuple:
    """A fraction box -> whole, even pixel values (x, y, w, h) inside the frame (ffmpeg wants even sizes)."""
    x, y, w, h = box
    x0 = min(max(0, int(x * width)), width - 2) // 2 * 2
    y0 = min(max(0, int(y * height)), height - 2) // 2 * 2
    x1 = min(width, int((x + w) * width + 1)) // 2 * 2
    y1 = min(height, int((y + h) * height + 1)) // 2 * 2
    return x0, y0, max(2, x1 - x0), max(2, y1 - y0)


def censor_graph(boxes, style: str, width: int, height: int, tail: str = "") -> str:
    """1.7.2 (user: censor the names on the left): the ffmpeg filter graph that hides ``boxes`` (fraction
    boxes) in a ``width`` × ``height`` picture – "pixel" = coarse blocks, "blur" = blurred, "black" = a black
    box, "retouch" = ffmpeg's delogo (the area is interpolated from its surroundings, no visible box); ``tail`` = filters to run after it (scale/fps of the Discord mode). Ends in [vout]."""
    parts, cur = [], "[0:v]"
    for i, box in enumerate(boxes):
        x, y, w, h = box_px(box, width, height)
        nxt = f"[c{i}]"
        if style == "black":
            parts.append(f"{cur}drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill{nxt}")
        elif style == "retouch":            # 1.7.3 (user: "retouchieren"): painted over from the surroundings
            x, y = max(EDGE_PX, x), max(EDGE_PX, y)
            w, h = max(2, min(w, width - EDGE_PX - x)), max(2, min(h, height - EDGE_PX - y))
            parts.append(f"{cur}delogo=x={x}:y={y}:w={w}:h={h}{nxt}")
        else:
            if style == "blur":
                r = max(2, min(w, h) // 6)
                inner = f"boxblur=luma_radius={r}:luma_power=3:chroma_radius={max(1, r // 2)}:chroma_power=3"
            else:
                p = max(4, min(w, h) // 8)
                inner = f"scale={max(1, w // p)}:{max(1, h // p)}:flags=area,scale={w}:{h}:flags=neighbor"
            parts.append(f"{cur}split[a{i}][b{i}];[b{i}]crop={w}:{h}:{x}:{y},{inner}[p{i}];"
                         f"[a{i}][p{i}]overlay={x}:{y}{nxt}")
        cur = nxt
    parts.append(f"{cur}{tail or 'null'}[vout]")
    return ";".join(parts)


def discord_plan(seconds: float, target_mb: float, info: Info | None = None) -> tuple[int, int, float]:
    """1.6.1: (video kbit/s, picture height, frame rate) so a clip of ``seconds`` stays under ``target_mb`` MB.
    Less room → smaller picture and 30 fps instead of a blurred 1440p (rules of thumb for x264: 1080p60 needs
    ~6000 kbit/s, 1080p30 ~4000, 720p30 ~2000, 480p30 ~900)."""
    seconds = max(1.0, float(seconds))
    total = target_mb * 8 * 1024 * SIZE_MARGIN / seconds          # kbit/s for picture + sound
    video = max(150, int(total - AUDIO_KBPS))
    src_h = info.height if info and info.height else 1080
    src_fps = info.fps if info and info.fps else 30.0
    if video >= 6000:
        h, fps = 1080, 60.0
    elif video >= 4000:
        h, fps = 1080, 30.0
    elif video >= 2000:
        h, fps = 720, 30.0
    elif video >= 900:
        h, fps = 480, 30.0
    else:
        h, fps = 360, 30.0
    return video, min(h, src_h), min(fps, src_fps)


def sound_wav(path: str, start: float, end: float, ffmpeg: str | None = None) -> str | None:
    """The sound of ``start``..``end`` as a temporary WAV (for winsound while the preview plays); None on failure."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg or end <= start:
        return None
    fd, tmp = tempfile.mkstemp(prefix="dbdms-clip-", suffix=".wav")
    os.close(fd)
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-to",
                            f"{end:.3f}", "-i", path, "-vn", "-ac", "2", "-ar", "44100", "-acodec", "pcm_s16le", tmp],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
                           creationflags=_flags())
        if p.returncode == 0 and os.path.getsize(tmp) > 44:
            return tmp
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        os.remove(tmp)
    except OSError:
        pass
    return None


class FramePlayer(threading.Thread):
    """Streams scaled frames from ``start`` on through ffmpeg (rawvideo on stdout) and hands each one to
    ``on_frame(t, image)`` at the file's pace (frames that come late are dropped, at most FPS_CAP shown);
    ``on_end()`` when the file or the stretch is over. ``stop()`` ends it at once."""

    def __init__(self, path: str, start: float, info: Info, on_frame, on_end, end: float | None = None,
                 height: int = PREVIEW_H, ffmpeg: str | None = None):
        super().__init__(name="clip-player", daemon=True)
        self.path, self.start_t, self.info = path, max(0.0, start), info
        self.end_t = end
        self.on_frame, self.on_end = on_frame, on_end
        self.height = height
        self.ffmpeg = ffmpeg or ffmpeg_exe()
        self._stop = threading.Event()
        self._proc = None
        self.position = self.start_t

    def stop(self):
        self._stop.set()
        p = self._proc
        if p is not None:
            try:
                p.kill()
            except OSError:
                pass

    def _read(self, n: int) -> bytes:
        out = bytearray()
        stream = self._proc.stdout
        while len(out) < n and not self._stop.is_set():
            chunk = stream.read(n - len(out))
            if not chunk:
                break
            out += chunk
        return bytes(out)

    def run(self):
        from PIL import Image
        if not self.ffmpeg or not self.info.ok:
            self.on_end()
            return
        w, h = scaled(self.info, self.height)
        fps = min(FPS_CAP, self.info.fps or 30.0)
        args = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{self.start_t:.3f}"]
        if self.end_t is not None:
            args += ["-to", f"{self.end_t:.3f}"]
        args += ["-i", self.path, "-an", "-vf", f"fps={fps:g},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        try:
            self._proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, creationflags=_flags(), bufsize=0)
        except OSError:
            self.on_end()
            return
        need = w * h * 3
        t0 = None                                         # the clock starts with the first frame (ffmpeg's start-up
        i = 0                                             # and seek take 0.1–0.5 s and must not count as "late")
        try:
            while not self._stop.is_set():
                buf = self._read(need)                    # a pipe gives short reads: collect a whole frame
                if len(buf) < need:
                    break
                t = self.start_t + i / fps
                i += 1
                if t0 is None:
                    t0 = time.monotonic()
                due = t0 + (t - self.start_t)
                late = time.monotonic() - due
                if late > 2.0 / fps:                      # behind: drop this frame, catch up
                    continue
                if late < 0:
                    self._stop.wait(-late)
                    if self._stop.is_set():
                        break
                self.position = t
                self.on_frame(t, Image.frombytes("RGB", (w, h), buf))
        finally:
            self.stop()
            self.on_end()                                 # the window ignores it when it stopped the player itself
