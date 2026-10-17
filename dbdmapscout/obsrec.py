"""Round recordings with OBS (1.4, user's wish: "die Runden mit OBS aufnehmen … auf die externe Festplatte").

OBS records; this program only tells it when – through obs-websocket (built into OBS 28+), and only on this
PC: the address is fixed to 127.0.0.1, never configurable (rule: no connection off the computer). Nothing here
touches DBD. Per round: start at the map banner (plus, if OBS's replay buffer runs, the seconds before it as a
"pre-roll" file), stop at the detected end, name the file after date/map/killer and note it in an index in the
recording folder (``dbdmapscout-recordings.jsonl``). The folder keeps at most ``limit`` bytes: the oldest
recordings *of this index* go first (never any other file on the drive), kept ones stay.

The external drive (Samsung T7) may get another letter after re-plugging: the folder is remembered by its volume
(``\\\\?\\Volume{…}\\``) plus the path on it; a missing drive means no recording and a note, never C: instead.

Only the standard library (a minimal WebSocket client: RFC 6455 handshake, masked text frames, ping/pong).
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
MAX_ROUND_S = 45 * 60           # a recording longer than this is stopped (an end that was never detected)
TAILS_S = (0, 3, 5, 8, 10)      # 1.4.1: seconds recorded after the detected end (the result screen)
DEFAULT_TAIL_S = 5
MIN_FILE_BYTES = 1024 * 1024    # 1.4.1: a recording smaller than this is reported as broken/empty
MAGIC = {b"\x1a\x45\xdf\xa3": "mkv", b"ftyp": "mp4"}   # file signatures (mp4: at offset 4)
NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


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


def prune(folder: str, recs: list[Recording], limit: int, reserve: int = RESERVE,
          free=None) -> tuple[list[Recording], list[str]]:
    """Keep the folder's recordings under ``limit`` bytes (0 = the whole drive) and ``reserve`` bytes free on
    the drive: delete the oldest not-kept ones of the index – only files named in it, only inside ``folder``.
    Entries whose files are gone drop out. ``free`` = bytes free now (measured when None).
    Returns (entries left, files deleted)."""
    left, deleted = [], []
    for r in recs:
        if os.path.exists(os.path.join(folder, r.file)):
            r.size = sum(os.path.getsize(os.path.join(folder, n)) for n in (r.file, r.pre)
                         if n and os.path.exists(os.path.join(folder, n)))
            left.append(r)
    if free is None:
        try:
            free = shutil.disk_usage(folder).free
        except OSError:
            free = reserve
    total = sum(r.size for r in left)
    for r in sorted([r for r in left if not r.keep], key=lambda r: r.t):
        if (limit <= 0 or total <= limit) and free >= reserve:
            break
        for n in (r.file, r.pre):
            if n and os.path.dirname(os.path.normpath(n)) == "":          # a plain name: inside the folder
                try:
                    os.remove(os.path.join(folder, n))
                    deleted.append(n)
                except OSError:
                    pass
        total -= r.size
        free += r.size
        left.remove(r)
    return left, deleted


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

    @property
    def recording(self) -> bool:
        return self.active is not None

    # ---- called from the UI thread
    def configure(self, cfg: Config):
        self.cmds.put(("config", cfg))

    def start_round(self, **meta):
        self.cmds.put(("start", meta))

    def stop_round(self, **meta):
        self.cmds.put(("stop", meta))

    def test(self):
        self.cmds.put(("test", None))

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
                except ObsError as e:
                    self._say(str(e), False)
                continue
            try:
                if cmd == "quit":
                    return
                if cmd == "config":
                    self.cfg = arg
                elif cmd == "test":
                    self._test()
                elif cmd == "start":
                    self._begin(arg)
                elif cmd == "stop":
                    self._stop_later(arg)
                elif cmd == "game":
                    self._game_changed(arg)
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
            if self.cfg.pre and self.cfg.buffer_auto:
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

    def _begin(self, meta):
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
            if self.cfg.pre:
                try:
                    if c.request("GetReplayBufferStatus").get("outputActive"):
                        c.request("SaveReplayBuffer")
                        time.sleep(0.3)
                        pre = c.request("GetLastReplayBufferReplay").get("savedReplayPath", "")
                except ObsError as e:
                    log.info("OBS: kein Vorlauf (%s)", e)
            c.request("StartRecord")
        finally:
            c.close()
        self.active = dict(meta, pre=pre, since=time.time())
        self._say(_("Nimmt die Runde auf"), True)
        self._post("started", t=meta.get("t"))

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
        ext = os.path.splitext(path)[1] or ".mkv"
        who = rec.get("killer") or {"killer": "Killer", "survivor": "Survivor"}.get(rec.get("role") or "", "")
        name = self._unique(folder, file_name(rec.get("t") or time.time(), rec.get("label", ""), who, ext))
        target = os.path.join(folder, name)
        final = self._move(path, target)
        pre = rec.get("pre") or ""
        pre_name = ""
        if pre and os.path.exists(pre):
            pname = self._unique(folder, file_name(rec.get("t") or time.time(), rec.get("label", ""), who,
                                                   os.path.splitext(pre)[1] or ext, " (Vorlauf)"))
            moved = self._move(pre, os.path.join(folder, pname))
            pre_name = os.path.basename(moved) if os.path.dirname(moved) == folder else ""
        if os.path.dirname(final) != folder:          # another drive than the folder: leave it, still noted
            self._say(_("Aufnahme liegt in OBS' eigenem Ordner: {path}", path=final), False)
            return
        bad = check_file(final)                        # 1.4.1: OBS may have failed silently
        recs = load_index(folder)
        recs.append(Recording(t=float(rec.get("t") or time.time()), file=os.path.basename(final), pre=pre_name,
                              map_id=rec.get("map_id", ""), label=rec.get("label", ""), role=rec.get("role", ""),
                              killer=rec.get("killer", ""), end=time.time(), extra={"bad": bad} if bad else {}))
        limit = int(self.cfg.limit_gb) * 1024 ** 3
        recs, deleted = prune(folder, recs, limit)
        save_index(folder, recs)
        if bad:
            self._warn(_("Aufnahme sieht beschädigt aus ({why}): {file} – OBS-Einstellungen prüfen (Encoder, Platte).",
                         why=bad, file=os.path.basename(final)))
        else:
            self._say(_("Gespeichert: {file}", file=os.path.basename(final)), True)
        self._post("saved", file=os.path.basename(final), t=rec.get("t"))
        if deleted:
            self._post("deleted", files=deleted)

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
        """An end that never came (DBD crashed, detection missed it): stop after MAX_ROUND_S."""
        if (self.active is not None and self._pending is None
                and time.time() - self.active.get("since", time.time()) > MAX_ROUND_S):
            self._finish({})
