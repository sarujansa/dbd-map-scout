"""Round recordings with OBS (1.4, user's wish: "die Runden mit OBS aufnehmen … auf die externe Festplatte").

OBS records; this program only tells it when – through obs-websocket (built into OBS 28+), and only on this
PC: the address is fixed to 127.0.0.1, never configurable (rule: no connection off the computer). Nothing here
touches DBD. Per round: start at the map banner (plus, if OBS's replay buffer runs, the seconds before it as a
"pre-roll" file), stop at the detected end, name the file after date/map/killer and note it in an index in the
recording folder (``dbdmapscout-recordings.jsonl``). The folder keeps at most ``limit`` bytes: the oldest
recordings *of this index* go first (never any other file on the drive), kept ones stay.

The external drive (Samsung T7) may get another letter after re-plugging: the folder is remembered by its volume
(``\\\\?\\Volume{…}\\``) plus the path on it; a missing drive means no recording and a note, never C: instead.

Only the standard library (a minimal WebSocket client: RFC 6455 handshake, masked text frames, ping/pong) –
plus, since 1.4.2, the ffmpeg binary that imageio-ffmpeg ships, run as a child process on the two files of a
round only (pre-roll + round → one file, stream copy, nothing re-encoded, no network).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import queue
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from .i18n import _

log = logging.getLogger("dbdmapscout")

HOST = "127.0.0.1"               # fixed: OBS on this PC only (never a setting)
DEFAULT_PORT = 4455
TIMEOUT = 3.0                    # s for connecting and for each answer
INDEX = "dbdmapscout-recordings.jsonl"
LIMITS_GB = (0, 100, 200, 500, 1000)         # 0 = the whole drive (user: "man kann die ganze Platte verwenden")
DEFAULT_LIMIT_GB = 0
RESERVE = 10 * 1024 ** 3        # free space kept on the drive: older recordings go before it is used up
MIN_FREE = 5 * 1024 ** 3        # below this much free space on the drive: no new recording
RENAME_TRIES = 40               # OBS may still hold the file a moment after StopRecord
RENAME_WAIT = 0.5
REPLAY_WAIT = 4.0               # 1.5.4: s to wait for OBS to finish writing the replay buffer (it saves asynchronously)
REPLAY_POLL = 0.2
MAX_ROUND_S = 45 * 60           # a recording longer than this is stopped (an end that was never detected)
EARLY_WAIT_S = 180              # 1.6: started at the end of the loading screen – no banner within this: filed as it is
CLIP_SECONDS = (15, 30, 45, 60, 90, 120)   # 1.6: F8 instant clip – the last n seconds of the replay buffer
DEFAULT_CLIP_S = 30
# 1.6 (user: "only DBD and Discord audio, each switchable"): OBS's own "Application Audio Capture" sources,
# created once in the current scene. OBS picks the window by its executable (priority 2) – the title is only a
# hint. OBS does the capture (Windows process loopback); this program only sends the requests.
AUDIO_KIND = "wasapi_process_output_capture"
AUDIO_APPS = {
    "dbd": ("DbD Map Scout – DBD", "DeadByDaylight:UnrealWindow:DeadByDaylight-Win64-Shipping.exe"),
    "discord": ("DbD Map Scout – Discord", "Discord:Chrome_WidgetWin_1:Discord.exe"),
}
AUDIO_PRIORITY_EXE = 2
TAILS_S = (0, 3, 5, 8, 10)      # 1.4.1: seconds recorded after the detected end (the result screen)
DEFAULT_TAIL_S = 5
MIN_FILE_BYTES = 1024 * 1024    # 1.4.1: a recording smaller than this is reported as broken/empty
MAGIC = {b"\x1a\x45\xdf\xa3": "mkv", b"ftyp": "mp4"}   # file signatures (mp4: at offset 4)
SHORT_ROUND_S = 300             # 1.4.2: rounds shorter than this go first when room is needed
FFMPEG_TIMEOUT = 600            # s for joining the two files (stream copy: seconds, not minutes)
SPACE_EVERY = 10.0              # s between two looks at the drive (Recorder.space)
DURATION_RE = re.compile(rb"Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)")
AUDIO_STREAM_RE = re.compile(rb"Stream #\d+:\d+[^\n]*?: Audio:")   # 1.8.5: one per audio track in ffmpeg -i
# 1.8.6 (1.8.5 had only "with/without Discord"): every sound source on its own OBS audio track, like Medal –
# track 1 = everything (plays anywhere), 2 = the game (+ other desktop sound), 3 = Discord, 4 = the microphone.
# The clip editor mixes them (audio_graph), F8 takes Config.clip_sources. OBS writes several tracks only in the
# advanced output mode with the recording tracks ticked ([Output] Mode=Advanced, [AdvOut] RecTracks bit mask) –
# we only read those values, never set them.
SOURCES = ("dbd", "discord", "mic")                       # the mixable sources, in the order of tracks 2, 3, 4
SOURCE_TRACKS = {"dbd": (1, 2), "desktop": (1, 2), "discord": (1, 3), "mic": (1, 4)}
REC_TRACKS_NEEDED = 0b1111
DEFAULT_CLIP_SOURCES = ("dbd", "mic")                      # F8: the game and the own voice, no Discord
LEGACY = -1                                                # 1.8.5 recordings: track 2 = everything but Discord
NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
CLIPS_DIR = "Clips"              # 1.5.3: clips (editor, F8 instant clips) beside the recordings
FARMING_DIR = "Farming"         # 1.5.3 (user's wish): recordings of farming rounds go into this subfolder


class ObsError(Exception):
    pass


# ------------------------------------------------------------------ obs-websocket (v5) client
def auth_string(password: str, salt: str, challenge: str) -> str:
    """obs-websocket 5 authentication: base64(sha256(base64(sha256(password + salt)) + challenge))."""
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def _frame(payload: bytes, opcode: int = 1) -> bytes:
    """A client frame (always masked, RFC 6455 5.3)."""
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 1 << 16:
        head += bytes([0x80 | 126]) + struct.pack("!H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack("!Q", n)
    mask = os.urandom(4)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class ObsClient:
    """One connection to obs-websocket on this PC."""

    def __init__(self, port: int = DEFAULT_PORT, password: str = "", timeout: float = TIMEOUT):
        self.port, self.password, self.timeout = int(port), password or "", timeout
        self._sock = None
        self._buf = b""
        self.events = []                       # events that came while waiting for an answer (op 5)
        self.version = ""

    # ---- transport
    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ObsError(_("OBS hat die Verbindung geschlossen"))
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def _recv_message(self) -> str:
        parts = []
        while True:
            b0, b1 = self._recv_exact(2)
            opcode, fin = b0 & 0x0F, b0 & 0x80
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b1 & 0x80 else None
            data = self._recv_exact(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 8:
                raise ObsError(_("OBS hat die Verbindung geschlossen"))
            if opcode == 9:                    # ping -> pong
                self._sock.sendall(_frame(data, 10))
                continue
            if opcode == 10:
                continue
            parts.append(data)
            if fin:
                return b"".join(parts).decode("utf-8")

    def _send(self, obj):
        self._sock.sendall(_frame(json.dumps(obj).encode("utf-8")))

    def _read(self):
        return json.loads(self._recv_message())

    # ---- protocol
    def connect(self):
        try:
            self._sock = socket.create_connection((HOST, self.port), timeout=self.timeout)
        except OSError as e:
            raise ObsError(_("OBS nicht erreichbar – läuft OBS, ist der WebSocket-Server an? ({error})", error=e.__class__.__name__)) from None
        self._sock.settimeout(self.timeout)
        try:
            return self._handshake()
        except BaseException:
            self.close()                          # a refused login must not leave the socket open
            raise

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall((f"GET / HTTP/1.1\r\nHost: {HOST}:{self.port}\r\nUpgrade: websocket\r\n"
                            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                            f"Sec-WebSocket-Protocol: obswebsocket.json\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ObsError(_("Keine Antwort von obs-websocket"))
            head += chunk
        head, self._buf = head.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise ObsError(_("Kein obs-websocket auf diesem Port"))
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        accept = next((ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sec-websocket-accept")), "")
        if accept.encode() != want:
            raise ObsError(_("Falsche WebSocket-Antwort"))
        hello = self._read()
        if hello.get("op") != 0:
            raise ObsError(_("Unerwartete Begrüssung von OBS"))
        d = hello.get("d", {})
        self.version = str(d.get("obsWebSocketVersion", ""))
        ident = {"rpcVersion": 1, "eventSubscriptions": 64}        # 64 = Outputs (RecordStateChanged)
        auth = d.get("authentication")
        if auth:
            if not self.password:
                raise ObsError(_("OBS verlangt ein Passwort (OBS: Werkzeuge → WebSocket-Servereinstellungen)"))
            ident["authentication"] = auth_string(self.password, auth["salt"], auth["challenge"])
        self._send({"op": 1, "d": ident})
        try:
            msg = self._read()
        except ObsError:
            raise ObsError(_("OBS hat die Anmeldung abgelehnt – Passwort falsch?")) from None
        if msg.get("op") != 2:
            raise ObsError(_("OBS hat die Anmeldung abgelehnt – Passwort falsch?"))
        return self

    def request(self, kind: str, data: dict | None = None) -> dict:
        rid = uuid.uuid4().hex
        self._send({"op": 6, "d": {"requestType": kind, "requestId": rid, "requestData": data or {}}})
        while True:
            msg = self._read()
            if msg.get("op") == 5:
                self.events.append(msg.get("d", {}))
                continue
            d = msg.get("d", {})
            if msg.get("op") == 7 and d.get("requestId") == rid:
                st = d.get("requestStatus", {})
                if not st.get("result"):
                    raise ObsError(f"{kind}: {st.get('comment') or st.get('code')}")
                return d.get("responseData") or {}

    def close(self):
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.sendall(_frame(b"", 8))
            except OSError:
                pass
            sock.close()


# ------------------------------------------------------------------ drive and folder
def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetVolumePathNameW.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    k.GetVolumeNameForVolumeMountPointW.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    return k


def volume_of(path: str) -> tuple[str, str]:
    """(volume name, path on that volume) of a folder – the volume name stays when the drive letter changes.
    ("", path) outside Windows or when it cannot be read."""
    if sys.platform != "win32":
        return "", path
    import ctypes
    try:
        k = _kernel32()
        mount = ctypes.create_unicode_buffer(512)
        if not k.GetVolumePathNameW(os.path.abspath(path), mount, 512):
            return "", path
        name = ctypes.create_unicode_buffer(512)
        if not k.GetVolumeNameForVolumeMountPointW(mount.value, name, 512):
            return "", path
        return name.value, os.path.relpath(os.path.abspath(path), mount.value)
    except Exception:
        return "", path


def find_folder(volume: str, rel: str, last: str) -> str | None:
    """The folder now: on the volume's current drive letter (the T7 after re-plugging), else the last path if
    no volume is known. None = the drive is not connected."""
    if not volume or sys.platform != "win32":
        return last if last and os.path.isdir(last) else None
    import ctypes
    import string
    k = _kernel32()
    name = ctypes.create_unicode_buffer(512)
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if k.GetVolumeNameForVolumeMountPointW(root, name, 512) and name.value.lower() == volume.lower():
            path = os.path.normpath(os.path.join(root, rel)) if rel and rel != "." else root
            return path if os.path.isdir(path) else None
    return None


def file_name(t: float, label: str, who: str, ext: str, suffix: str = "") -> str:
    """'2026-10-17 21-40 Coal Tower – Nurse.mkv' – no characters Windows forbids."""
    stamp = time.strftime("%Y-%m-%d %H-%M", time.localtime(t))
    parts = [stamp, NAME_CHARS.sub("", label or "Map").strip() or "Map"]
    name = " ".join(parts) + (f" – {NAME_CHARS.sub('', who).strip()}" if who else "") + suffix
    return name[:150] + ext


# ------------------------------------------------------------------ index
@dataclass
class Recording:
    t: float                     # banner time = the round's key (rounds.jsonl)
    file: str                    # file name in the folder
    pre: str = ""                # pre-roll from the replay buffer ("" = none)
    map_id: str = ""
    label: str = ""
    role: str = ""
    killer: str = ""
    end: float = 0.0
    size: int = 0
    keep: bool = False           # never deleted by the limit
    extra: dict = field(default_factory=dict)
    marks: list = field(default_factory=list)   # 1.4.2: F8 moments, seconds from the start of the file
    farming: bool = False        # 1.4.2: a farming round (cross-play off) – goes first when room is needed
    pre_s: float = 0.0           # 1.4.2: seconds of pre-roll at the start of the file (0 = none or separate)


def rel_path(folder: str, name: str) -> str | None:
    """Absolute path of an index entry's file: a plain name or one inside a subfolder (``Farming/…``), never
    outside ``folder`` (no absolute path, no ``..``) – None for anything else. Entries use "/" on every system."""
    if not name or os.path.isabs(name) or name.startswith(("/", "\\")) or ":" in name:   # ":" = a drive letter
        return None
    parts = [p for p in re.split(r"[\\/]", name) if p]
    if not parts or any(p in ("..", ".") for p in parts) or len(parts) > 2:
        return None
    return os.path.join(folder, *parts)


def load_index(folder: str) -> list[Recording]:
    out = []
    try:
        with open(os.path.join(folder, INDEX), encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    out.append(Recording(**{k: v for k, v in d.items() if k in Recording.__dataclass_fields__}))
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass
    return out


def save_index(folder: str, recs: list[Recording]):
    path = os.path.join(folder, INDEX)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in sorted(recs, key=lambda r: r.t):
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def prune_rank(r: Recording) -> int:
    """1.4.2: what goes first when room is needed – 0 farming rounds and rounds shorter than SHORT_ROUND_S,
    1 ordinary rounds, 2 rounds with a mark (F8); within a rank the oldest first. Kept ones never."""
    if r.marks:
        return 2
    if r.farming or (r.end and 0 < r.end - r.t < SHORT_ROUND_S):
        return 0
    return 1


def prune(folder: str, recs: list[Recording], limit: int, reserve: int = RESERVE,
          free=None) -> tuple[list[Recording], list[str]]:
    """Keep the folder's recordings under ``limit`` bytes (0 = the whole drive) and ``reserve`` bytes free on
    the drive: delete not-kept ones of the index in ``prune_rank`` order (farming/short first, marked last,
    oldest first) – only files named in it, only inside ``folder``.
    Entries whose files are gone drop out. ``free`` = bytes free now (measured when None).
    Returns (entries left, files deleted)."""
    left, deleted = [], []
    for r in recs:
        main = rel_path(folder, r.file)
        if main and os.path.exists(main):
            paths = [p for p in (rel_path(folder, n) for n in (r.file, r.pre) if n) if p and os.path.exists(p)]
            r.size = sum(os.path.getsize(p) for p in paths)
            left.append(r)
    if free is None:
        try:
            free = shutil.disk_usage(folder).free
        except OSError:
            free = reserve
    total = sum(r.size for r in left)
    for r in sorted([r for r in left if not r.keep], key=lambda r: (prune_rank(r), r.t)):
        if (limit <= 0 or total <= limit) and free >= reserve:
            break
        for n in (r.file, r.pre):
            p = rel_path(folder, n) if n else None                        # only inside the folder
            if p:
                try:
                    os.remove(p)
                    deleted.append(n)
                except OSError:
                    pass
        total -= r.size
        free += r.size
        left.remove(r)
    return left, deleted


def select_recordings(recs: list[Recording], since: float | None = None, map_label: str | None = None,
                      role: str | None = None, only: str | None = None) -> list[Recording]:
    """1.5, tab "Aufnahmen": the index filtered – ``since`` (banner time ≥), map label, role ("killer" /
    "survivor" / "farming"), ``only`` "marked" / "kept" / "bad". Newest first."""
    out = []
    for r in recs:
        if since is not None and r.t < since:
            continue
        if map_label and r.label != map_label:
            continue
        if role == "farming":
            if not r.farming:
                continue
        elif role and (r.role != role or r.farming):
            continue
        if only == "marked" and not r.marks:
            continue
        if only == "kept" and not r.keep:
            continue
        if only == "bad" and not (r.extra or {}).get("bad"):
            continue
        out.append(r)
    return sorted(out, key=lambda r: r.t, reverse=True)


@dataclass
class Space:
    """1.4.2: what the overview's tile "Aufnahmen" shows – measured by the recorder thread, never on the UI thread."""
    free: int = 0                # bytes free on the drive
    total: int = 0               # bytes the drive holds
    used: int = 0                # bytes the recordings of the index take
    count: int = 0
    oldest: float = 0.0          # banner time of the oldest recording (0 = none)
    marked: int = 0              # recordings with an F8 mark
    folder: str = ""             # "" = drive not connected
    t: float = 0.0               # when measured


def space(folder: str | None, recs: list[Recording] | None = None) -> Space:
    if not folder:
        return Space(t=time.time())
    recs = load_index(folder) if recs is None else recs
    try:
        du = shutil.disk_usage(folder)
        free, total = du.free, du.total
    except OSError:
        free = total = 0
    return Space(free=free, total=total, used=sum(r.size for r in recs), count=len(recs),
                 oldest=min((r.t for r in recs), default=0.0), marked=sum(1 for r in recs if r.marks),
                 folder=folder, t=time.time())


# ------------------------------------------------------------------ ffmpeg (1.4.2): pre-roll + round → one file
def ffmpeg_exe() -> str | None:
    """The ffmpeg binary imageio-ffmpeg ships (BSD-2; no PATH lookup – only the one pip installed into .venv),
    None when the package is missing."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _run(args: list[str], timeout: float = FFMPEG_TIMEOUT) -> tuple[int, bytes]:
    """ffmpeg as a child process without a console window; (exit code, stderr)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=timeout, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e).encode()
    return p.returncode, p.stderr or b""


def media_duration(path: str, ffmpeg: str | None = None, run=None) -> float | None:
    """Length of a video in seconds from ffmpeg's own file summary (``ffmpeg -i``; imageio-ffmpeg has no ffprobe)."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg:
        return None
    _rc, err = (run or _run)([ffmpeg, "-hide_banner", "-i", path], timeout=30)
    m = DURATION_RE.search(err)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def track_flags(tracks) -> dict:
    """The ``inputAudioTracks`` value for SetInputAudioTracks: tracks 1–4 on or off (5 and 6 are left alone)."""
    return {str(n): n in tracks for n in range(1, 5)}


def track_sources(n_tracks: int) -> dict:
    """Which sources a recording with ``n_tracks`` audio tracks carries on their own track, as 0-based stream
    indexes: 3 or more tracks = the 1.8.6 layout (dbd 1, discord 2, mic 3 when there), exactly 2 = the 1.8.5
    layout (track 2 = everything but Discord, marked LEGACY), otherwise nothing to pick."""
    if n_tracks >= 3:
        d = {"dbd": 1, "discord": 2}
        if n_tracks >= 4:
            d["mic"] = 3
        return d
    if n_tracks == 2:
        return {"dbd": 1, "discord": LEGACY}
    return {}


def audio_graph(n_tracks: int, mix) -> tuple[str, str | None]:
    """(filter_complex part, ``-map`` value) for the wanted ``mix`` {source: volume, 1.0 = as recorded} of a file
    with ``n_tracks`` audio tracks: ("", "0:a?") = ffmpeg's default, nothing to mix; ("", None) = no sound at
    all; ("", "0:a:N") = one track as it is (stream copy possible); else a volume/amix graph ending in [aout]
    with map "[aout]" – the sound is then re-encoded. Pure."""
    if mix is None or n_tracks < 2:
        return "", "0:a?"
    srcs = track_sources(n_tracks)
    vol = {k: max(0.0, float(mix.get(k, 0) or 0)) for k in SOURCES}
    if srcs.get("discord") == LEGACY:                      # 1.8.5 file: all or all-but-Discord, one volume
        if vol["discord"] > 0:
            parts = [(0, max(vol["dbd"], vol["discord"]))]
        else:
            parts = [(1, vol["dbd"])] if vol["dbd"] > 0 else []
    else:
        parts = [(idx, vol[name]) for name, idx in srcs.items() if vol[name] > 0]
    if not parts:
        return "", None
    if len(parts) == 1 and abs(parts[0][1] - 1.0) < 1e-3:
        return "", f"0:a:{parts[0][0]}"
    chain = ";".join(f"[0:a:{i}]volume={v:.3f}[a{k}]" for k, (i, v) in enumerate(parts))
    if len(parts) == 1:
        return chain.replace("[a0]", "[aout]"), "[aout]"
    chain += ";" + "".join(f"[a{k}]" for k in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0[aout]"
    return chain, "[aout]"


def audio_tracks(path: str, ffmpeg: str | None = None, run=None) -> int:
    """1.8.5: how many audio streams a video has (``ffmpeg -i``); 0 without ffmpeg or on failure."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg:
        return 0
    _rc, err = (run or _run)([ffmpeg, "-hide_banner", "-i", path], timeout=30)
    return len(AUDIO_STREAM_RE.findall(err))


def merge_files(parts: list[str], out: str, ffmpeg: str | None = None, run=None) -> bool:
    """Join video files of the same format into ``out`` without re-encoding (concat demuxer, stream copy):
    seconds of work, the picture stays as OBS wrote it. False when ffmpeg is missing or fails – the parts stay."""
    ffmpeg = ffmpeg or ffmpeg_exe()
    if not ffmpeg or len(parts) < 2:
        return False
    lst = out + ".txt"
    try:
        with open(lst, "w", encoding="utf-8") as f:
            for p in parts:
                f.write("file '" + os.path.abspath(p).replace("'", "'\\''") + "'\n")
        rc, err = (run or _run)([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                                "-i", lst, "-map", "0", "-c", "copy", out])
    finally:
        try:
            os.remove(lst)
        except OSError:
            pass
    ok = rc == 0 and os.path.exists(out) and os.path.getsize(out) > 0
    if not ok:
        log.info("ffmpeg: Zusammenfügen fehlgeschlagen (%s): %s", rc, err[-400:].decode("utf-8", "replace").strip())
        try:
            os.remove(out)
        except OSError:
            pass
    return ok


# ------------------------------------------------------------------ the recorder thread
@dataclass
class Config:
    on: bool = False
    port: int = DEFAULT_PORT
    password: str = ""
    volume: str = ""
    rel: str = ""
    folder: str = ""             # last known absolute path
    limit_gb: int = DEFAULT_LIMIT_GB
    pre: bool = True
    tail_s: float = DEFAULT_TAIL_S   # 1.4.1: keep recording this long after the end (result screen)
    buffer_auto: bool = True         # 1.4.1: start OBS's replay buffer with DBD, stop it when DBD is gone
    merge: bool = True               # 1.4.2: pre-roll + round → one file (ffmpeg, stream copy)
    farming_sub: bool = True         # 1.5.3: farming rounds into the subfolder FARMING_DIR
    early: bool = True               # 1.6: start at the end of the loading screen (spawn), the banner names it
    instant: bool = True             # 1.6: F8 saves the last clip_s seconds of the replay buffer as a clip
    clip_s: int = DEFAULT_CLIP_S
    audio: bool = True               # 1.6: set OBS's audio sources (below) when DBD starts
    audio_dbd: bool = True
    audio_discord: bool = True
    audio_desktop: bool = False      # the rest of the desktop sound (OBS "Desktop Audio")
    audio_mic: bool = False          # OBS "Mic/Aux"
    tracks: bool = True              # 1.8.6: every source on its own OBS track (SOURCE_TRACKS), 1 = everything
    clip_sources: tuple = DEFAULT_CLIP_SOURCES   # 1.8.6: what the F8 clip keeps when the buffer file has the tracks

    @property
    def wants_buffer(self) -> bool:
        return self.pre or self.instant


def profile_hint(mode: str, rec_tracks: str) -> str:
    """1.8.5 (pure): what the user has to tick in OBS for a second audio track, "" when the profile is fine.
    ``mode`` = [Output] Mode ("Simple"/"Advanced"), ``rec_tracks`` = [AdvOut] RecTracks (bit mask, track 1 = 1)."""
    try:
        mask = int(str(rec_tracks).strip() or "1")
    except ValueError:
        mask = 1
    if str(mode).strip().lower() == "advanced" and mask & REC_TRACKS_NEEDED == REC_TRACKS_NEEDED:
        return ""
    return _("Für die Tonmischung im Clip-Editor in OBS: Einstellungen → Ausgabe → Ausgabemodus „Erweitert“ → Reiter "
             "Aufnahme → Audiospur 1 bis 4 anhaken (1 alles, 2 Spiel, 3 Discord, 4 Mikrofon)")


def check_file(path: str) -> str | None:
    """1.4.1: None if the recording looks fine, else why not ("leer"/"zu klein"/"kein Video") – OBS may have
    failed silently (drive gone, encoder error)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError:
        return "fehlt"
    if size == 0:
        return "leer"
    if size < MIN_FILE_BYTES:
        return "zu klein"
    if not (head[:4] in MAGIC or head[4:8] in MAGIC):
        return "kein Video"
    return None


class Recorder(threading.Thread):
    """Talks to OBS off the UI thread. ``post(kind, **data)`` reports back: status (text, ok), started, saved,
    deleted, error."""

    def __init__(self, post):
        super().__init__(name="obs-recorder", daemon=True)
        self._post = post
        self.cmds = queue.Queue()
        self.cfg = Config()
        self.active = None           # the round being recorded: dict(t, map_id, label, role, killer, pre, since)
        self.status = ""
        self._pending = None         # (meta, deadline): the end came, the tail is still being recorded (1.4.1)
        self._game = None            # last known: DBD running? (set_game)
        self._buffer_ours = False    # we started OBS's replay buffer: we stop it with DBD
        self.space = Space()         # 1.4.2: the drive and the index, for the overview's tile
        self._space_t = 0.0

    @property
    def recording(self) -> bool:
        return self.active is not None

    # ---- called from the UI thread
    def configure(self, cfg: Config):
        self.cmds.put(("config", cfg))

    def start_round(self, **meta):
        self.cmds.put(("start", meta))

    def start_early(self, **meta):
        """1.6: the loading screen ended – record from the spawn on; the banner (start_round) names the round."""
        self.cmds.put(("early", meta))

    def instant_clip(self, **meta):
        """1.6: F8 – the last clip_s seconds of OBS's replay buffer as a clip in Clips/."""
        self.cmds.put(("clip", meta))

    def apply_audio(self):
        """1.6: set OBS's audio sources now (settings changed)."""
        self.cmds.put(("audio", None))

    def stop_round(self, **meta):
        self.cmds.put(("stop", meta))

    def test(self):
        self.cmds.put(("test", None))

    def mark(self):
        """1.4.2: F8 – note this moment in the running recording (the clip editor jumps to it later)."""
        self.cmds.put(("mark", None))

    def set_keep(self, t: float, on: bool):
        """1.5: "behalten" – never deleted for room. Index writes stay on this thread."""
        self.cmds.put(("keep", (float(t), bool(on))))

    def delete(self, t: float):
        """1.5: remove one recording (its files from the index only) and its index entry."""
        self.cmds.put(("delete", float(t)))

    def set_farming(self, t: float, on: bool):
        """1.5.4: the statistics marked the round as farming (or not): the recording follows – flag in the index,
        file into / out of the subfolder FARMING_DIR. Unknown rounds are ignored."""
        self.cmds.put(("farming", (float(t), bool(on))))

    def set_game(self, on: bool):
        """DBD running or not (1.4.1): starts/stops OBS's replay buffer, checks OBS and the drive once."""
        if bool(on) != self._game:
            self.cmds.put(("game", bool(on)))

    def quit(self):
        self.cmds.put(("quit", None))

    # ---- thread
    def run(self):
        while True:
            wait = 5.0 if self._pending is None else max(0.05, min(5.0, self._pending[1] - time.time()))
            try:
                cmd, arg = self.cmds.get(timeout=wait)
            except queue.Empty:
                try:
                    self._due()
                    self._watchdog()
                    self._look_at_space()
                except ObsError as e:
                    self._say(str(e), False)
                continue
            try:
                if cmd == "quit":
                    return
                if cmd == "config":
                    self.cfg = arg
                    self._look_at_space(force=True)    # the tile follows a new folder/switch at once
                elif cmd == "test":
                    self._test()
                elif cmd == "start":
                    self._begin(arg)
                elif cmd == "early":
                    self._begin_early(arg)
                elif cmd == "clip":
                    self._instant_clip(arg)
                elif cmd == "audio":
                    self._audio_now()
                elif cmd == "stop":
                    self._stop_later(arg)
                elif cmd == "game":
                    self._game_changed(arg)
                elif cmd == "mark":
                    self._mark()
                elif cmd == "keep":
                    self._set_keep(*arg)
                elif cmd == "delete":
                    self._delete_one(arg)
                elif cmd == "farming":
                    self._set_farming(*arg)
            except ObsError as e:
                self._say(str(e), False)
            except Exception as e:                     # never let the thread die
                log.exception("OBS-Aufnahme")
                self._say(_("Fehler: {error}", error=e), False)

    def _say(self, text, ok):
        self.status = text
        self._post("status", text=text, ok=ok)

    def _client(self) -> ObsClient:
        return ObsClient(self.cfg.port, self.cfg.password).connect()

    def _mark(self):
        if self.active is None:
            self._post("marked", pos=None)
            return
        pos = round(time.time() - self.active["since"], 1)
        self.active.setdefault("marks", []).append(pos)
        self._post("marked", pos=pos, n=len(self.active["marks"]))

    def _set_keep(self, t, on):
        folder = self.folder()
        if folder is None:
            self._warn(_("Aufnahme-Laufwerk nicht angeschlossen."))
            return
        recs = load_index(folder)
        hit = next((r for r in recs if r.t == t), None)
        if hit is None:
            return
        hit.keep = on
        save_index(folder, recs)
        self._post("changed", what="keep", t=t, on=on, file=hit.file)
        self._look_at_space(force=True)

    def _set_farming(self, t, on):
        folder = self.folder()
        if folder is None:
            return
        recs = load_index(folder)
        hit = next((r for r in recs if abs(r.t - t) < 1e-6), None)
        if hit is None:
            return
        hit.farming = on
        if self.cfg.farming_sub:                            # the file follows the flag (both parts)
            dest = os.path.join(folder, FARMING_DIR) if on else folder
            prefix = FARMING_DIR + "/" if on else ""
            try:
                os.makedirs(dest, exist_ok=True)
            except OSError:
                dest = None
            for attr in ("file", "pre"):
                name = getattr(hit, attr)
                src = rel_path(folder, name) if name else None
                if dest is None or not src or not os.path.exists(src):
                    continue
                base = os.path.basename(src)
                if os.path.dirname(src) == os.path.normpath(dest):
                    continue                                # already where it belongs
                target = os.path.join(dest, self._unique(dest, base))
                moved = self._move(src, target)
                if moved == target:
                    setattr(hit, attr, prefix + os.path.basename(target))
        save_index(folder, recs)
        self._post("changed", what="farming", t=t, on=on, file=hit.file)
        self._look_at_space(force=True)

    def _delete_one(self, t):
        folder = self.folder()
        if folder is None:
            self._warn(_("Aufnahme-Laufwerk nicht angeschlossen."))
            return
        recs = load_index(folder)
        hit = next((r for r in recs if r.t == t), None)
        if hit is None:
            return
        gone = []
        for n in (hit.file, hit.pre):
            p = rel_path(folder, n) if n else None                        # only inside the folder
            if p:
                try:
                    os.remove(p)
                    gone.append(n)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    self._warn(_("Aufnahme nicht gelöscht ({error}): {file}", error=e.__class__.__name__, file=n))
                    return
        recs.remove(hit)
        save_index(folder, recs)
        self._post("changed", what="delete", t=t, file=hit.file)
        if gone:
            self._post("deleted", files=gone, manual=True)
        self._look_at_space(force=True)

    def _look_at_space(self, force=False):
        """Drive and index for the overview – every SPACE_EVERY s while recording is on."""
        if not force and time.time() - self._space_t < SPACE_EVERY:
            return
        self._space_t = time.time()
        self.space = space(self.folder()) if self.cfg.on else Space(t=self._space_t)

    def folder(self) -> str | None:
        return find_folder(self.cfg.volume, self.cfg.rel, self.cfg.folder)

    def _test(self):
        c = self._client()
        try:
            ver = c.request("GetVersion")
            rec = c.request("GetRecordStatus")
            try:
                buf = c.request("GetReplayBufferStatus").get("outputActive")
            except ObsError:
                buf = None
        finally:
            c.close()
        folder = self.folder()
        bits = [_("OBS {version} verbunden", version=ver.get("obsVersion", "?"))]
        bits.append(_("nimmt gerade auf") if rec.get("outputActive") else _("bereit"))
        if self.cfg.pre:
            bits.append(_("Wiederholungspuffer läuft") if buf else _("Wiederholungspuffer aus (kein Vorlauf)"))
        bits.append(_("Ordner: {folder}", folder=folder) if folder else _("Ordner/Laufwerk nicht gefunden"))
        self._say(" · ".join(bits), bool(folder))

    # (named _begin/_finish: threading.Thread has its own _stop(), which join() calls on Python 3.12 – a method
    # of ours with that name broke join with "missing argument meta")
    def _stop_later(self, meta):
        """The round ended: keep recording for the tail (result screen), then stop."""
        if self.active is None:
            return
        if self.cfg.tail_s <= 0:
            self._finish(meta)
        else:
            self._pending = (meta, time.time() + float(self.cfg.tail_s))

    def _due(self):
        if self._pending is not None and time.time() >= self._pending[1]:
            meta, self._pending = self._pending[0], None
            self._finish(meta)

    def _flush(self):
        """A recording still running (or in its tail) ends now."""
        if self._pending is not None:
            meta, self._pending = self._pending[0], None
            self._finish(meta)
        elif self.active is not None:
            self._finish({})

    def _game_changed(self, on: bool):
        self._game = on
        if not on:
            self._flush()                               # DBD closed: the round is over
            if self._buffer_ours:
                self._buffer_ours = False
                try:
                    c = self._client()
                    try:
                        c.request("StopReplayBuffer")
                    finally:
                        c.close()
                except ObsError as e:
                    log.info("OBS: Wiederholungspuffer nicht gestoppt (%s)", e)
            return
        if not self.cfg.on:
            return
        folder = self.folder()
        if folder is None:
            self._warn(_("Aufnahme-Laufwerk nicht angeschlossen – die Runden werden nicht aufgenommen."))
            return
        try:
            c = self._client()
        except ObsError as e:
            self._warn(_("OBS läuft nicht – die Runden werden nicht aufgenommen. ({error})", error=e))
            return
        try:
            if self.cfg.audio:
                self._audio(c)
            if self.cfg.wants_buffer and self.cfg.buffer_auto:
                try:
                    if not c.request("GetReplayBufferStatus").get("outputActive"):
                        c.request("StartReplayBuffer")
                        self._buffer_ours = True
                except ObsError as e:
                    log.info("OBS: Wiederholungspuffer nicht gestartet (%s)", e)
            self._say(_("OBS bereit – Runden werden aufgenommen"), True)
        finally:
            c.close()

    def _warn(self, text):
        self._say(text, False)
        self._post("warn", text=text)

    def _begin_early(self, meta):
        """1.6: recording from the end of the loading screen on, before any banner: provisional until _begin."""
        if self.active is not None or not self.cfg.on or not self.cfg.early:
            return
        self._begin(dict(meta, early=True), pre_roll=False)

    def _begin(self, meta, pre_roll=True):
        a = self.active
        if (a is not None and a.get("early") and not meta.get("early") and self._pending is None
                and time.time() - a.get("since", 0) <= EARLY_WAIT_S):
            # 1.6: the banner of the round recorded since the loading screen: it names it, nothing restarts
            marks = a.get("marks", [])
            merged = dict(a)
            merged.update({k: v for k, v in meta.items() if v is not None})
            merged.update(early=False, marks=marks, farming=bool(a.get("farming") or meta.get("farming")))
            self.active = merged
            self._say(_("Nimmt die Runde auf (seit dem Ladebildschirm)"), True)
            self._post("started", t=meta.get("t"))
            return
        self._flush()                                   # a new banner while recording: close the old one first
        if not self.cfg.on:
            return
        folder = self.folder()
        if folder is None:
            self._say(_("Aufnahme-Laufwerk nicht angeschlossen – Runde wird nicht aufgenommen"), False)
            return
        if shutil.disk_usage(folder).free < MIN_FREE:
            self._say(_("Aufnahme-Laufwerk fast voll – Runde wird nicht aufgenommen"), False)
            return
        c = self._client()
        try:
            if c.request("GetRecordStatus").get("outputActive"):
                self._say(_("OBS nimmt schon auf (von Hand?) – nichts gestartet"), False)
                return
            try:
                c.request("SetRecordDirectory", {"recordDirectory": folder})     # obs-websocket 5.3+ (OBS 30)
            except ObsError:
                log.info("OBS: Aufnahmeordner nicht setzbar – OBS nimmt in seinen eigenen Ordner auf")
            pre = ""
            if self.cfg.pre and pre_roll:
                try:
                    if c.request("GetReplayBufferStatus").get("outputActive"):
                        pre = self._save_replay(c)
                except ObsError as e:
                    log.info("OBS: kein Vorlauf (%s)", e)
            c.request("StartRecord")
        finally:
            c.close()
        self.active = dict(meta, pre=pre, since=time.time(), marks=[])
        if meta.get("early"):
            self._say(_("Nimmt auf – seit dem Ende des Ladebildschirms, wartet auf das Map-Banner"), True)
            self._post("started", t=meta.get("t"), early=True)
            return
        self._say(_("Nimmt die Runde auf"), True)
        self._post("started", t=meta.get("t"))

    @staticmethod
    def _save_replay(c: ObsClient) -> str:
        """SaveReplayBuffer and the path of *this* replay. OBS writes the buffer asynchronously: a fixed 0.3-s wait
        (1.4–1.5.3) often still got the previous replay's path or none – the new file then stayed behind under
        OBS's own name "Replay_…" (user's report). Now: the path before, save, then poll until the path changes
        and the file exists (or the ReplayBufferSaved event names it), at most REPLAY_WAIT s."""
        try:
            before = c.request("GetLastReplayBufferReplay").get("savedReplayPath", "") or ""
        except ObsError:
            before = ""
        c.request("SaveReplayBuffer")
        deadline = time.time() + REPLAY_WAIT
        path = ""
        while time.time() < deadline:
            time.sleep(REPLAY_POLL)
            saved = [e for e in c.events if e.get("eventType") == "ReplayBufferSaved"]
            if saved:
                path = (saved[-1].get("eventData") or {}).get("savedReplayPath", "") or path
            cur = c.request("GetLastReplayBufferReplay").get("savedReplayPath", "") or ""
            if cur and cur != before:
                path = cur
            if path and os.path.exists(path):
                return path
        if path:
            log.info("OBS: Vorlauf %s noch nicht geschrieben – wird am Rundenende gesucht", path)
        else:
            log.info("OBS: Vorlauf nicht gefunden (Pfad unverändert: %s)", before or "–")
        return path

    def _finish(self, meta):
        rec, self.active = self.active, None
        if rec is None:
            return
        rec.update({k: v for k, v in meta.items() if v})
        c = self._client()
        try:
            path = c.request("StopRecord").get("outputPath", "")
        finally:
            c.close()
        if not path:
            self._say(_("OBS hat keinen Dateinamen genannt – Aufnahme nicht zugeordnet"), False)
            return
        self._file_away(rec, path)

    def _file_away(self, rec, path):
        folder = self.folder() or os.path.dirname(path)
        sub = FARMING_DIR if rec.get("farming") and self.cfg.farming_sub else ""     # 1.5.3: farming rounds apart
        dest = os.path.join(folder, sub) if sub else folder
        try:
            os.makedirs(dest, exist_ok=True)
        except OSError:
            sub, dest = "", folder
        ext = os.path.splitext(path)[1] or ".mkv"
        who = rec.get("killer") or {"killer": "Killer", "survivor": "Survivor"}.get(rec.get("role") or "", "")
        name = self._unique(dest, file_name(rec.get("t") or time.time(), rec.get("label", ""), who, ext))
        target = os.path.join(dest, name)
        final = self._move(path, target)
        pre = rec.get("pre") or ""
        pre_name = ""
        if pre and os.path.exists(pre):
            pname = self._unique(dest, file_name(rec.get("t") or time.time(), rec.get("label", ""), who,
                                                 os.path.splitext(pre)[1] or ext, " (Vorlauf)"))
            moved = self._move(pre, os.path.join(dest, pname))
            pre_name = os.path.basename(moved) if os.path.dirname(moved) == dest else ""
        if os.path.dirname(final) != dest:            # another drive than the folder: leave it, still noted
            self._say(_("Aufnahme liegt in OBS' eigenem Ordner: {path}", path=final), False)
            return
        bad = check_file(final)                        # 1.4.1: OBS may have failed silently
        marks = list(rec.get("marks") or [])
        pre_s, extra = 0.0, {}
        if pre_name and not bad and self.cfg.merge:    # 1.4.2: pre-roll + round → one file
            final, pre_name, pre_s, joined = self._join(dest, os.path.join(dest, pre_name), final)
            if joined:
                marks = [round(m + pre_s, 1) for m in marks]
            else:
                extra["merge_failed"] = True
        if bad:
            extra["bad"] = bad
        prefix = sub + "/" if sub else ""              # index names: "Farming/…" with "/" on every system
        if pre_name:
            pre_name = prefix + pre_name
        recs = load_index(folder)
        recs.append(Recording(t=float(rec.get("t") or time.time()), file=prefix + os.path.basename(final), pre=pre_name,
                              map_id=rec.get("map_id", ""), label=rec.get("label", ""), role=rec.get("role", ""),
                              killer=rec.get("killer", ""), end=time.time(), extra=extra, marks=marks,
                              farming=bool(rec.get("farming")), pre_s=pre_s))
        limit = int(self.cfg.limit_gb) * 1024 ** 3
        recs, deleted = prune(folder, recs, limit)
        save_index(folder, recs)
        if bad:
            self._warn(_("Aufnahme sieht beschädigt aus ({why}): {file} – OBS-Einstellungen prüfen (Encoder, Platte).",
                         why=bad, file=os.path.basename(final)))
        elif extra.get("merge_failed"):
            self._say(_("Gespeichert: {file} – Vorlauf nicht angefügt, liegt als eigene Datei daneben",
                        file=os.path.basename(final)), True)
        else:
            self._say(_("Gespeichert: {file}", file=os.path.basename(final)), True)
        self._post("saved", file=os.path.basename(final), t=rec.get("t"), marks=len(marks))
        if deleted:
            self._post("deleted", files=deleted)
        self._look_at_space(force=True)

    @staticmethod
    def _join(folder, pre_path, round_path):
        """Pre-roll and round into one file named like the round (ffmpeg, stream copy). Returns
        (file, pre name left, seconds of pre-roll, joined?) – on failure both files stay as they were."""
        ffmpeg = ffmpeg_exe()
        if not ffmpeg or os.path.splitext(pre_path)[1].lower() != os.path.splitext(round_path)[1].lower():
            return round_path, os.path.basename(pre_path), 0.0, False
        pre_s = media_duration(pre_path, ffmpeg)
        tmp = os.path.splitext(round_path)[0] + " (zusammen)" + os.path.splitext(round_path)[1]
        if not merge_files([pre_path, round_path], tmp, ffmpeg):
            return round_path, os.path.basename(pre_path), 0.0, False
        try:
            os.remove(pre_path)
            os.replace(tmp, round_path)
        except OSError as e:
            log.info("ffmpeg: zusammengefügte Datei nicht abgelegt (%s)", e)
            try:
                os.remove(tmp)
            except OSError:
                pass
            return round_path, os.path.basename(pre_path) if os.path.exists(pre_path) else "", 0.0, False
        return round_path, "", float(pre_s or 0.0), True

    @staticmethod
    def _unique(folder, name):
        base, ext = os.path.splitext(name)
        n, out = 2, name
        while os.path.exists(os.path.join(folder, out)):
            out = f"{base} ({n}){ext}"
            n += 1
        return out

    @staticmethod
    def _move(src, dst) -> str:
        """Rename (same drive: instant); OBS may still hold the file a moment. Another drive: left where it is."""
        if os.path.splitdrive(os.path.abspath(src))[0].lower() != os.path.splitdrive(os.path.abspath(dst))[0].lower():
            return src
        for _i in range(RENAME_TRIES):
            try:
                os.replace(src, dst)
                return dst
            except PermissionError:
                time.sleep(RENAME_WAIT)
            except OSError:
                break
        return src

    def _watchdog(self):
        """An end that never came (DBD crashed, detection missed it): stop after MAX_ROUND_S. 1.6: a recording
        started at the loading screen whose banner never came within EARLY_WAIT_S is stopped and filed as it is
        (an unknown map is still a round – nothing is deleted)."""
        a = self.active
        if a is None or self._pending is not None:
            return
        age = time.time() - a.get("since", time.time())
        if a.get("early") and age > EARLY_WAIT_S:
            log.info("OBS: kein Map-Banner %d s nach dem Ladebildschirm – Aufnahme beendet", EARLY_WAIT_S)
            self._finish({"label": a.get("label") or _("Unbekannte Map")})
        elif age > MAX_ROUND_S:
            self._finish({})

    # ---- 1.6: audio sources in OBS
    def _audio_now(self):
        if not (self.cfg.on and self.cfg.audio and self._game):
            return
        try:
            c = self._client()
        except ObsError as e:
            log.info("OBS: Ton nicht eingestellt (%s)", e)
            return
        try:
            self._audio(c)
        finally:
            c.close()

    def _audio(self, c: ObsClient):
        """DBD and Discord as OBS application audio sources (created in the current scene the first time),
        each muted or not as set; OBS's desktop audio and microphone muted or not as set. Errors only in the log
        and the status: older OBS (< 28) has no application audio capture."""
        notes = []
        try:
            names = {i.get("inputName") for i in c.request("GetInputList").get("inputs", [])}
            scene = None
            for key, on in (("dbd", self.cfg.audio_dbd), ("discord", self.cfg.audio_discord)):
                name, window = AUDIO_APPS[key]
                if name not in names:
                    if not on:
                        continue                          # never created, not wanted: nothing to do
                    if scene is None:
                        cur = c.request("GetCurrentProgramScene")
                        scene = cur.get("currentProgramSceneName") or cur.get("sceneName") or ""
                    c.request("CreateInput", {"sceneName": scene, "inputName": name, "inputKind": AUDIO_KIND,
                                              "inputSettings": {"window": window, "priority": AUDIO_PRIORITY_EXE},
                                              "sceneItemEnabled": True})
                    notes.append(_("Tonquelle angelegt: {name}", name=name))
                c.request("SetInputMute", {"inputName": name, "inputMuted": not on})
            special = c.request("GetSpecialInputs")
            others = []
            for key, on in (("desktop1", self.cfg.audio_desktop), ("desktop2", self.cfg.audio_desktop),
                            ("mic1", self.cfg.audio_mic), ("mic2", self.cfg.audio_mic),
                            ("mic3", self.cfg.audio_mic), ("mic4", self.cfg.audio_mic)):
                name = special.get(key)
                if name:
                    c.request("SetInputMute", {"inputName": name, "inputMuted": not on})
                    others.append(("mic" if key.startswith("mic") else "desktop", name))
            if self.cfg.tracks:
                self._tracks(c, names, others)
        except ObsError as e:
            log.info("OBS: Ton nicht eingestellt (%s)", e)
            self._say(_("Ton in OBS nicht eingestellt: {error}", error=e), False)
            return
        for n in notes:
            log.info("OBS: %s", n)

    def _tracks(self, c: ObsClient, names: set, others: list):
        """1.8.6: every source on track 1 (everything) and its own track (SOURCE_TRACKS: game + desktop 2, Discord
        3, microphone 4) – the clip editor mixes them like Medal. Only sources that exist are touched (nothing is
        created here). Then a look at the profile: OBS writes several tracks only in the advanced output mode with
        the recording tracks ticked; we never change the profile, the status line says what to tick."""
        wanted = list(others)
        for key in ("dbd", "discord"):
            name = AUDIO_APPS[key][0]
            if name in names or getattr(self.cfg, "audio_" + key):
                wanted.append((key, name))
        for key, name in wanted:
            c.request("SetInputAudioTracks", {"inputName": name, "inputAudioTracks": track_flags(SOURCE_TRACKS[key])})
        hint = profile_hint(self._profile(c, "Output", "Mode"), self._profile(c, "AdvOut", "RecTracks"))
        if hint:
            log.info("OBS: %s", hint)
            self._say(hint, False)

    @staticmethod
    def _profile(c: ObsClient, category: str, name: str) -> str:
        d = c.request("GetProfileParameter", {"parameterCategory": category, "parameterName": name})
        value = d.get("parameterValue")
        if value is None:
            value = d.get("defaultParameterValue")
        return "" if value is None else str(value)

    def _clip_sound(self, src: str, ffmpeg: str) -> tuple[list, list]:
        """1.8.6: ffmpeg's map and codec arguments for the instant clip – the sources of Config.clip_sources mixed
        from the buffer file's own tracks (audio_graph); a file without them (one track) is taken as it is."""
        n = audio_tracks(src, ffmpeg)
        if n < 2:
            return ["-map", "0"], ["-c", "copy"]
        flt, amap = audio_graph(n, {s: 1.0 for s in self.cfg.clip_sources})
        if amap is None:
            return ["-map", "0:v", "-an"], ["-c", "copy"]
        if flt:
            return ["-filter_complex", flt, "-map", "0:v", "-map", amap], ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k"]
        return ["-map", "0:v", "-map", amap], ["-c", "copy"]

    # ---- 1.6: F8 instant clip
    def _instant_clip(self, meta):
        """Save OBS's replay buffer, keep its last clip_s seconds as Clips/<name>.mp4 (ffmpeg, stream copy). The
        saved replay is our own file (made by our request, path from OBS): it is removed once the clip exists;
        without ffmpeg it is moved into Clips as it is."""
        if not (self.cfg.on and self.cfg.instant):
            return
        folder = self.folder()
        if folder is None:
            self._post("clip", ok=False, why=_("Aufnahme-Laufwerk nicht angeschlossen"))
            return
        c = self._client()
        try:
            if not c.request("GetReplayBufferStatus").get("outputActive"):
                self._post("clip", ok=False, why=_("Wiederholungspuffer in OBS läuft nicht"))
                return
            src = self._save_replay(c)
        finally:
            c.close()
        if not src or not os.path.exists(src):
            self._post("clip", ok=False, why=_("OBS hat den Puffer nicht gespeichert"))
            return
        clips = os.path.join(folder, CLIPS_DIR)
        os.makedirs(clips, exist_ok=True)
        who = meta.get("killer") or {"killer": "Killer", "survivor": "Survivor"}.get(meta.get("role") or "", "")
        name = file_name(time.time(), meta.get("label") or _("Clip"), who, "", " " + _("(Sofort-Clip)"))
        ffmpeg = ffmpeg_exe()
        out = None
        if ffmpeg:
            out = os.path.join(clips, self._unique(clips, name + ".mp4"))
            maps, codec = self._clip_sound(src, ffmpeg)
            rc, err = _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-sseof", f"-{int(self.cfg.clip_s)}",
                            "-i", src, *maps, *codec, "-avoid_negative_ts", "make_zero",
                            "-movflags", "+faststart", out])
            if rc != 0 or not os.path.exists(out) or os.path.getsize(out) == 0:
                log.info("ffmpeg: Sofort-Clip nicht geschnitten (%s): %s", rc,
                         err[-300:].decode("utf-8", "replace").strip())
                try:
                    os.remove(out)
                except OSError:
                    pass
                out = None
        if out is not None:
            try:
                os.remove(src)
            except OSError:
                pass
        else:                                            # no ffmpeg / cut failed: the whole buffer is the clip
            target = os.path.join(clips, self._unique(clips, name + (os.path.splitext(src)[1] or ".mkv")))
            out = self._move(src, target)
        self._post("clip", ok=True, file=os.path.basename(out), seconds=int(self.cfg.clip_s))
        self._look_at_space(force=True)
