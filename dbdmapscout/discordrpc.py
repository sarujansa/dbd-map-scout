"""Discord Rich Presence (1.7, user's pick 12): "Playing … – Nurse on Coal Tower, 4:32" in the Discord status.

Rules: the program talks only to the **local Discord client** over its IPC pipe (``\\\\?\\pipe\\discord-ipc-N``,
the same channel games use for Rich Presence) – no internet, no process access, standard library only. Discord
shows the activity under the name of an *application* the user registers once in Discord's developer portal; its
Application-ID is a setting (``discord_client_id``). Without an ID nothing is ever sent. Only title/state lines
and the start time of the round go out; nothing comes back but Discord's acknowledgements.

``activity()`` is pure logic (tested); ``Presence`` is the thread that keeps the connection and coalesces updates.
"""
from __future__ import annotations

import json
import os
import queue
import socket
import struct
import sys
import threading
import time
import uuid
from dataclasses import dataclass

from .i18n import _

IS_WIN = sys.platform == "win32"
PIPES = 10                 # Discord tries discord-ipc-0 … -9
TIMEOUT = 3.0              # seconds to wait for an answer (Linux socket; the Windows pipe blocks)
RETRY_S = 20.0             # try to reach Discord again this often
MIN_GAP_S = 2.0            # never two updates closer than this (Discord allows ~5 in 20 s)
MAX_CHARS = 128            # Discord's limit for details/state
OP_HANDSHAKE, OP_FRAME, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 3, 4
_NOTHING = object()        # "no activity sent yet" (None = cleared)


class IpcError(Exception):
    pass


def ipc_paths() -> list:
    """Where the Discord client listens; tried in order."""
    if IS_WIN:
        return [rf"\\?\pipe\discord-ipc-{i}" for i in range(PIPES)]
    base = next((os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP") if os.environ.get(k)),
                "/tmp")
    out = []
    for sub in ("", "app/com.discordapp.Discord", "snap.discord"):      # also flatpak / snap Discord
        out += [os.path.join(base, sub, f"discord-ipc-{i}") for i in range(PIPES)]
    return out


class Ipc:
    """One connection to the Discord client: handshake and framed JSON (little-endian op + length)."""

    def __init__(self, path: str):
        self._f = self._s = None
        if IS_WIN:
            self._f = open(path, "r+b", buffering=0)       # the named pipe as a file; blocks until Discord answers
        else:
            self._s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._s.settimeout(TIMEOUT)
            self._s.connect(path)

    def _write(self, data: bytes):
        if self._f is not None:
            self._f.write(data)
        else:
            self._s.sendall(data)

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            part = self._f.read(n - len(buf)) if self._f is not None else self._s.recv(n - len(buf))
            if not part:
                raise IpcError("connection closed")
            buf += part
        return buf

    def send(self, op: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._write(struct.pack("<ii", op, len(body)) + body)

    def recv(self) -> tuple:
        op, length = struct.unpack("<ii", self._read(8))
        if length < 0 or length > 1 << 20:
            raise IpcError("bad frame")
        body = self._read(length) if length else b"{}"
        try:
            return op, json.loads(body.decode("utf-8") or "{}")
        except ValueError as e:
            raise IpcError(f"bad json: {e}") from None

    def close(self):
        for h in (self._f, self._s):
            if h is not None:
                try:
                    h.close()
                except OSError:
                    pass
        self._f = self._s = None


def connect(client_id: str) -> Ipc:
    """Open the first pipe that answers and do the handshake; IpcError names why not (no Discord, bad ID)."""
    seen = None
    for path in ipc_paths():
        try:
            ipc = Ipc(path)
        except OSError:
            continue
        try:
            ipc.send(OP_HANDSHAKE, {"v": 1, "client_id": str(client_id)})
            op, d = ipc.recv()
        except (OSError, IpcError) as e:
            ipc.close()
            seen = e
            continue
        if op == OP_FRAME and d.get("evt") == "READY":
            return ipc
        ipc.close()
        msg = d.get("message") or d.get("data", {}).get("message") if isinstance(d, dict) else ""
        raise IpcError(str(msg or f"op {op}"), "client_id" if op == OP_CLOSE else "")
    raise IpcError(_("Discord nicht gefunden – läuft es?") if seen is None else str(seen), "absent")


def set_activity(ipc: Ipc, activity):
    """SET_ACTIVITY with our own pid (Discord ties the activity to the process that set it); None clears."""
    args = {"pid": os.getpid()}
    if activity is not None:
        args["activity"] = activity
    ipc.send(OP_FRAME, {"cmd": "SET_ACTIVITY", "args": args, "nonce": str(uuid.uuid4())})
    op, d = ipc.recv()
    while op == OP_PING:                                  # Discord may ping in between
        ipc.send(OP_PONG, d)
        op, d = ipc.recv()
    if op == OP_CLOSE:
        raise IpcError(str(d.get("message", "closed")))
    if isinstance(d, dict) and d.get("evt") == "ERROR":
        raise IpcError(str((d.get("data") or {}).get("message", "error")))


# ------------------------------------------------------------------ what to show (pure)
@dataclass(frozen=True)
class GameState:
    running: bool = False        # DBD is running
    phase: str = "menu"          # menu | search | lobby | custom | match
    map: str = ""                # map label incl. layout ("Coal Tower II")
    realm: str = ""              # "The MacMillan Estate"
    role: str = ""               # killer | survivor | ""
    killer: str = ""             # display name ("The Nurse")
    since: float | None = None   # start of the round / the search (unix seconds)


def _clip(s: str) -> str:
    return s if len(s) <= MAX_CHARS else s[:MAX_CHARS - 1] + "…"


def _role_line(st: GameState, show_killer: bool) -> str:
    if st.role == "killer":
        return _("Killer · {killer}", killer=st.killer) if st.killer and show_killer else _("Killer")
    if st.role == "survivor":
        return _("Survivor")
    return ""


def activity(st: GameState, show_killer=True, show_lobby=True):
    """The Discord activity for a game state; None = nothing to show (DBD closed, or a phase switched off)."""
    if not st.running:
        return None
    out = {}
    if st.phase == "match":
        out["details"] = _clip(f"{st.realm} – {st.map}" if st.realm and st.realm not in st.map else st.map
                               or _("Im Match"))
        out["state"] = _clip(_role_line(st, show_killer) or _("Im Match"))
    elif not show_lobby:
        return None
    elif st.phase == "search":
        out["details"] = _("Sucht ein Match")
        out["state"] = _clip(_role_line(st, show_killer) or _("In der Lobby"))
    elif st.phase in ("lobby", "custom"):
        out["details"] = _("Custom Game") if st.phase == "custom" else _("In der Lobby")
        out["state"] = _clip(_role_line(st, show_killer) or _("Bereit machen"))
    else:
        out["details"] = _("Im Menü")
    if st.since and st.phase in ("match", "search", "lobby", "custom"):
        out["timestamps"] = {"start": int(st.since)}
    return out


# ------------------------------------------------------------------ the thread
class Presence(threading.Thread):
    """Keeps the connection to Discord and sends the activity when it changes. ``post(text, ok)`` reports the
    status to the settings page / log (only on change)."""

    def __init__(self, post, pid=None):
        super().__init__(name="discord-presence", daemon=True)
        self._post = post
        self.cmds = queue.Queue()
        self.on, self.client_id = False, ""
        self.show_killer = self.show_lobby = True
        self.state = GameState()
        self.status = _("Discord: aus")
        self.connected = False
        self._ipc = None
        self._sent = _NOTHING         # last activity sent
        self._sent_at = 0.0
        self._retry_at = 0.0
        self._bad_id = None           # an Application-ID Discord refused: not tried again until it changes
        self._wanted_test = False

    # ---- UI thread
    def configure(self, on: bool, client_id: str, show_killer=True, show_lobby=True):
        self.cmds.put(("config", (bool(on), str(client_id or "").strip(), bool(show_killer), bool(show_lobby))))

    def update(self, state: GameState):
        if state != self.state:
            self.cmds.put(("state", state))

    def test(self):
        """Connect now (even if off) and report the result."""
        self.cmds.put(("test", None))

    def quit(self):
        self.cmds.put(("quit", None))

    # ---- thread
    def run(self):
        while True:
            try:
                cmd, arg = self.cmds.get(timeout=1.0)
            except queue.Empty:
                cmd, arg = None, None
            if cmd == "quit":
                self._disconnect(clear=True)
                return
            if cmd == "config":
                self.on, self.client_id, self.show_killer, self.show_lobby = arg
                self._retry_at = 0.0
                if self.client_id != self._bad_id:
                    self._bad_id = None
            elif cmd == "state":
                self.state = arg
            elif cmd == "test":
                self._wanted_test = True
                self._retry_at = 0.0
            try:
                self._tick()
            except Exception as e:                      # never die; the next tick tries again
                self._disconnect()
                self._say(_("Discord: Fehler – {error}", error=str(e)), False)
                self._retry_at = time.time() + RETRY_S

    def _say(self, text: str, ok: bool):
        if text != self.status:
            self.status = text
            try:
                self._post(text, ok)
            except Exception:
                pass

    def _tick(self):
        want = self.on or self._wanted_test
        if not want or not self.client_id:
            self._disconnect(clear=True)
            if self._wanted_test and not self.client_id:
                self._say(_("Application-ID fehlt – im Developer-Portal anlegen und hier eintragen."), False)
            else:
                self._say(_("Discord: aus"), True)
            self._wanted_test = False
            return
        if self.client_id == self._bad_id:
            return
        if self._ipc is None:
            now = time.time()
            if now < self._retry_at and not self._wanted_test:
                return
            self._wanted_test = False
            try:
                self._ipc = connect(self.client_id)
            except IpcError as e:
                kind = e.args[1] if len(e.args) > 1 else ""
                self._retry_at = now + RETRY_S
                if kind == "client_id":
                    self._bad_id = self.client_id
                    self._say(_("Ungültige Application-ID ({error})", error=e.args[0]), False)
                elif kind == "absent":
                    self._say(e.args[0], False)
                else:
                    self._say(_("Discord: Fehler – {error}", error=e.args[0]), False)
                return
            self.connected = True
            self._sent = _NOTHING
            self._say(_("Discord: verbunden"), True)
        self._wanted_test = False
        act = activity(self.state, self.show_killer, self.show_lobby) if self.on else None
        if act == self._sent:
            return
        if act is None and self._sent is _NOTHING:
            self._sent = None                        # nothing shown yet, nothing to show: no clear needed
            return
        if self._sent is not _NOTHING and time.time() - self._sent_at < MIN_GAP_S:
            return                                    # too soon after the last update: the next tick sends it
        set_activity(self._ipc, act)
        self._sent, self._sent_at = act, time.time()

    def _disconnect(self, clear=False):
        if self._ipc is None:
            return
        try:
            if clear and self._sent is not None and self._sent is not _NOTHING:
                set_activity(self._ipc, None)
        except (OSError, IpcError):
            pass
        try:
            self._ipc.send(OP_CLOSE, {})
        except (OSError, IpcError):
            pass
        self._ipc.close()
        self._ipc = None
        self.connected = False
        self._sent = _NOTHING
