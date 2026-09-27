"""Server tab: which game server DBD is connected to (like "Connected to" in Make Your Choice).

Program started as administrator: ``netwatch`` runs in a thread of this
process (no prompt). Otherwise the helper ``netwatch.py`` is started with
administrator rights (UAC). Either way it writes its result file, read here.
The game server is the busiest UDP partner on a public address whose
reverse DNS name is an AWS EC2 machine (GameLift runs on EC2); the region
is part of that name, e.g. ``ec2-3-120-1-2.eu-central-1.compute.amazonaws.com``.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import tempfile
import threading
import time

from . import netwatch, regions

IS_WIN = sys.platform == "win32"
MIN_PPS = 10.0         # a running match exchanges dozens of packets per second with its server
LOST_AFTER = 8.0       # no server traffic for this long -> not connected any more
TOUCH_EVERY = 5.0      # refresh the control file (the helper stops when it gets older than 20 s)
NO_DATA_AFTER = 8.0    # result file not updated for this long -> the helper is not working
RDNS_RETRY = 60.0      # look up an address again after this long if it gave no AWS region
_REGION_RE = re.compile(r"\.([a-z]{2}(?:-[a-z]+)+-\d)\.compute\.amazonaws\.com$")


def region_from_ptr(name: str) -> str | None:
    """AWS region code from an EC2 reverse DNS name, else None."""
    name = (name or "").lower().rstrip(".")
    if name.endswith(".compute-1.amazonaws.com"):          # us-east-1 has its own naming
        return "us-east-1"
    m = _REGION_RE.search(name)
    return m.group(1) if m else None


def pick_server(flows, region_of) -> dict | None:
    """Busiest partner with enough traffic whose region is known. ``flows`` is sorted busiest first;
    ``region_of(ip)`` returns a region code, or None when not an AWS server / not resolved yet."""
    for f in flows:
        if f.get("pps", 0) < MIN_PPS:
            break
        code = region_of(f["ip"])
        if code:
            return {**f, "region": code}
    return None


def region_name(code: str) -> str:
    return regions.NAMES.get(code, code)


def is_admin() -> bool:
    """This program runs with administrator rights (e.g. started via "Als Administrator ausführen")."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class ConnectionWatch:
    def __init__(self):
        self.proc = None               # helper process handle, or the capture thread when already admin
        self.control = self.result = None
        self.error = ""
        self.server = None             # {"ip", "port", "pps", "region", ...} while connected
        self.no_data = False
        self._seen = 0.0
        self._touched = 0.0
        self._started = 0.0
        self._rdns = {}                # ip -> (region code or "" = none/pending, time of the lookup)
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.proc is not None

    # --------------------------------------------------------------- start/stop
    def start(self, hwnd=None) -> dict | None:
        """Start capturing. Returns an error dict or None. Without administrator rights Windows asks
        (UAC) and this blocks until the prompt is answered – call from a thread."""
        if self.running:
            return None
        if not IS_WIN:
            return {"error": "Nur unter Windows verfügbar."}
        fd, control = tempfile.mkstemp(prefix="dbdmapscout-net-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"stop": False}, fh)
        fd, result = tempfile.mkstemp(prefix="dbdmapscout-netres-", suffix=".json")
        os.close(fd)
        if is_admin():
            proc = threading.Thread(target=netwatch.main, args=(["netwatch.py", control, result],),
                                    daemon=True, name="netwatch")
            proc.start()
        else:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netwatch.py")
            proc, err = regions.start_elevated(script, [control, result], hwnd)
            if err:
                _remove(control, result)
                return err
        self.error, self.server, self.no_data = "", None, False
        self._started = self._touched = time.time()
        self.control, self.result = control, result
        self.proc = proc                         # last: poll() (UI thread) starts working from here on
        return None

    def stop(self) -> None:
        """Ask the capture to stop (it checks every 2 s) and forget it."""
        if self.control:
            try:
                with open(self.control, "w", encoding="utf-8") as fh:
                    json.dump({"stop": True}, fh)
            except OSError:
                pass
        if self.proc and not isinstance(self.proc, threading.Thread):
            regions.close_handle(self.proc)
        _remove(self.control, self.result)      # gone control file stops the helper as well
        self.proc = self.control = self.result = None
        self.server = None

    # --------------------------------------------------------------- polling
    def poll(self, now: float | None = None) -> None:
        """Call about once a second from the UI thread."""
        if not self.running:
            return
        now = now or time.time()
        if now - self._touched >= TOUCH_EVERY:
            try:
                os.utime(self.control)
            except OSError:
                pass
            self._touched = now
        data = self._read()
        if isinstance(self.proc, threading.Thread):
            code = None if self.proc.is_alive() else 0
        else:
            code = regions.exit_code(self.proc)
        if code is not None:                     # capture ended by itself
            self.error = (data or {}).get("error") or f"Mitschnitt beendet (Code {code})."
            self.stop()
            return
        if not data or not data.get("ok"):
            self.no_data = now - self._started > NO_DATA_AFTER
            return
        self.no_data = now - float(data.get("t", 0)) > NO_DATA_AFTER
        found = pick_server(data.get("flows") or [], self._region)
        if found:
            self.server, self._seen = found, now
        elif self.server and now - self._seen > LOST_AFTER:
            self.server = None

    def _read(self):
        try:
            with open(self.result, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError, TypeError):
            return None                          # not written yet / being written right now

    def _region(self, ip: str) -> str | None:
        now = time.time()
        with self._lock:
            code, t = self._rdns.get(ip, (None, 0.0))
            if code or (code == "" and now - t < RDNS_RETRY):
                return code or None              # known, or looked up (or pending) only recently
            self._rdns[ip] = ("", now)           # pending
        threading.Thread(target=self._lookup, args=(ip,), daemon=True, name="rdns").start()
        return None

    def _lookup(self, ip):
        try:
            code = region_from_ptr(socket.gethostbyaddr(ip)[0]) or ""
        except OSError:
            code = ""
        with self._lock:
            self._rdns[ip] = (code, time.time())

    # --------------------------------------------------------------- text
    def text(self) -> str:
        if not self.running:
            return f"Fehler: {self.error}" if self.error else ""
        if self.no_data:
            return "keine Daten vom Mitschnitt"
        if self.server:
            return f"{region_name(self.server['region'])} ({self.server['ip']})"
        return "Warte auf Match …"


def _remove(*paths):
    for p in paths:
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
