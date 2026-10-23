"""Discord Rich Presence (fogscout/discordrpc.py, 1.7): the activity (pure), the IPC client against a fake
Discord on a local socket, the presence thread (connect, update, clear, bad ID, no Discord). Nothing leaves the PC."""
import json
import os
import socket
import struct
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import discordrpc as dc  # noqa: E402

GOOD_ID = "123456789012345678"


class FakeDiscord(threading.Thread):
    """The Discord client's IPC: handshake (READY or CLOSE for a bad client id), SET_ACTIVITY answered,
    an occasional PING. Linux only (unix socket in XDG_RUNTIME_DIR)."""

    def __init__(self, folder, ping=False):
        super().__init__(daemon=True)
        self.path = os.path.join(folder, "discord-ipc-0")
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.path)
        self.srv.listen(2)
        self.srv.settimeout(0.2)
        self.ping = ping
        self.activities = []            # every activity set (None = cleared)
        self.handshakes = []
        self.stop_flag = False
        self.conns = []                 # served connections, closed by stop() like a quitting Discord

    @staticmethod
    def _recv(conn):
        head = b""
        while len(head) < 8:
            part = conn.recv(8 - len(head))
            if not part:
                return None, None
            head += part
        op, n = struct.unpack("<ii", head)
        body = b""
        while len(body) < n:
            body += conn.recv(n - len(body))
        return op, json.loads(body or b"{}")

    @staticmethod
    def _send(conn, op, d):
        body = json.dumps(d).encode()
        conn.sendall(struct.pack("<ii", op, len(body)) + body)

    def run(self):
        while not self.stop_flag:
            try:
                conn, _a = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.conns.append(conn)
            try:
                self.serve(conn)
            except (OSError, ValueError):
                pass
            finally:
                conn.close()

    def serve(self, conn):
        op, d = self._recv(conn)
        if op != dc.OP_HANDSHAKE:
            return
        self.handshakes.append(d)
        if d.get("client_id") != GOOD_ID:
            self._send(conn, dc.OP_CLOSE, {"code": 4000, "message": "Invalid Client ID"})
            return
        self._send(conn, dc.OP_FRAME, {"cmd": "DISPATCH", "evt": "READY", "data": {"v": 1}})
        while True:
            op, d = self._recv(conn)
            if op is None or op == dc.OP_CLOSE:
                return
            if op == dc.OP_PONG:
                continue
            if op == dc.OP_FRAME and d.get("cmd") == "SET_ACTIVITY":
                self.activities.append(d["args"].get("activity"))
                assert d["args"]["pid"] == os.getpid()
                if self.ping:
                    self._send(conn, dc.OP_PING, {})
                self._send(conn, dc.OP_FRAME, {"cmd": "SET_ACTIVITY", "nonce": d["nonce"],
                                               "data": d["args"].get("activity")})

    def stop(self):
        self.stop_flag = True
        self.srv.close()
        for c in self.conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


@pytest.fixture
def discord(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("the fake Discord is a unix socket; Windows talks over the named pipe")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    fake = FakeDiscord(str(tmp_path))
    fake.start()
    yield fake
    fake.stop()


def _wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


# ------------------------------------------------------------------ the activity (pure)
def test_the_activity_names_map_role_killer_and_start():
    st = dc.GameState(True, "match", "Coal Tower II", "The MacMillan Estate", "killer", "The Nurse", 1700000000.5)
    a = dc.activity(st)
    assert a == {"details": "The MacMillan Estate – Coal Tower II", "state": "Killer · The Nurse",
                 "timestamps": {"start": 1700000000}}
    assert dc.activity(st, show_killer=False)["state"] == "Killer"
    assert dc.activity(dc.GameState(True, "match", "Fallen Refuge", "Fallen Refuge", "survivor"))["details"] == \
        "Fallen Refuge"                                               # realm = map: not twice
    assert dc.activity(dc.GameState(True, "match", "X", "", "", "", None)) == {"details": "X", "state": "Im Match"}


def test_lobby_search_and_menu_can_be_switched_off_and_a_closed_game_shows_nothing():
    assert dc.activity(dc.GameState(False, "match", "Coal Tower")) is None
    search = dc.GameState(True, "search", role="survivor", since=100.0)
    assert dc.activity(search) == {"details": "Sucht ein Match", "state": "Survivor", "timestamps": {"start": 100}}
    assert dc.activity(search, show_lobby=False) is None
    assert dc.activity(dc.GameState(True, "lobby", role="killer", killer="The Trapper", since=5.0))["details"] == \
        "In der Lobby"
    assert dc.activity(dc.GameState(True, "custom"))["details"] == "Custom Game"
    assert dc.activity(dc.GameState(True, "menu")) == {"details": "Im Menü"}
    assert dc.activity(dc.GameState(True, "menu"), show_lobby=False) is None
    long = dc.activity(dc.GameState(True, "match", "A" * 300))
    assert len(long["details"]) == dc.MAX_CHARS and long["details"].endswith("…")


# ------------------------------------------------------------------ client and thread
def test_the_client_shakes_hands_sets_and_clears_the_activity(discord):
    ipc = dc.connect(GOOD_ID)
    dc.set_activity(ipc, {"details": "x", "state": "y"})
    dc.set_activity(ipc, None)
    ipc.close()
    assert _wait(lambda: discord.activities == [{"details": "x", "state": "y"}, None])
    assert discord.handshakes[0] == {"v": 1, "client_id": GOOD_ID}


def test_a_bad_application_id_and_a_missing_discord_are_clear_errors(discord):
    with pytest.raises(dc.IpcError) as e:
        dc.connect("1")
    assert e.value.args == ("Invalid Client ID", "client_id")
    discord.stop()
    os.unlink(discord.path)
    with pytest.raises(dc.IpcError) as e:
        dc.connect(GOOD_ID)
    assert e.value.args[1] == "absent" and "Discord" in e.value.args[0]


def test_the_presence_thread_sends_changes_only_and_clears_when_switched_off(discord, monkeypatch):
    monkeypatch.setattr(dc, "MIN_GAP_S", 0.0)
    said = []
    p = dc.Presence(lambda text, ok: said.append((text, ok)))
    p.start()
    try:
        p.configure(True, GOOD_ID)
        p.update(dc.GameState(True, "match", "Coal Tower", "The MacMillan Estate", "killer", "The Nurse", 50.0))
        assert _wait(lambda: len(discord.activities) == 1)
        assert discord.activities[0]["details"] == "The MacMillan Estate – Coal Tower"
        assert ("Discord: verbunden", True) in said and p.connected
        p.update(dc.GameState(True, "match", "Coal Tower", "The MacMillan Estate", "killer", "The Nurse", 50.0))
        time.sleep(0.3)
        assert len(discord.activities) == 1                     # the same state again: nothing sent
        p.update(dc.GameState(True, "menu"))
        assert _wait(lambda: len(discord.activities) == 2) and discord.activities[1] == {"details": "Im Menü"}
        p.configure(True, GOOD_ID, show_lobby=False)             # menu switched off: cleared
        assert _wait(lambda: len(discord.activities) == 3) and discord.activities[2] is None
        p.update(dc.GameState(False))
        time.sleep(0.3)
        assert len(discord.activities) == 3                     # already cleared: nothing sent
        p.update(dc.GameState(True, "match", "Badham Preschool", role="survivor", since=7.0))
        assert _wait(lambda: len(discord.activities) == 4)
        p.configure(False, GOOD_ID)                              # switched off: cleared and disconnected
        assert _wait(lambda: len(discord.activities) == 5 and not p.connected)
        assert discord.activities[4] is None and said[-1] == ("Discord: aus", True)
    finally:
        p.quit()
        p.join(timeout=3)


def test_the_presence_thread_reports_a_bad_id_once_and_a_missing_discord_without_dying(discord, monkeypatch):
    monkeypatch.setattr(dc, "RETRY_S", 0.2)
    said = []
    p = dc.Presence(lambda text, ok: said.append((text, ok)))
    p.start()
    try:
        p.configure(True, "1")
        p.update(dc.GameState(True, "menu"))
        assert _wait(lambda: any("Ungültige Application-ID" in t for t, _ok in said))
        time.sleep(0.6)
        assert len(discord.handshakes) == 1                      # not tried again with the same id
        p.configure(True, GOOD_ID)
        assert _wait(lambda: len(discord.activities) == 1)
        discord.stop()
        os.unlink(discord.path)
        p.update(dc.GameState(True, "match", "Coal Tower"))      # Discord gone: the send fails, it reconnects later
        assert _wait(lambda: not p.connected and "Discord" in p.status)
        p.test()
        assert _wait(lambda: p.status == "Discord nicht gefunden – läuft es?")
        assert p.is_alive()
    finally:
        p.quit()
        p.join(timeout=3)


def test_without_an_id_nothing_is_sent_and_the_test_button_says_so(discord):
    said = []
    p = dc.Presence(lambda text, ok: said.append((text, ok)))
    p.start()
    try:
        p.configure(True, "")
        p.update(dc.GameState(True, "match", "Coal Tower"))
        p.test()
        assert _wait(lambda: any("Application-ID fehlt" in t for t, _ok in said))
        time.sleep(0.3)
        assert discord.handshakes == []
    finally:
        p.quit()
        p.join(timeout=3)
