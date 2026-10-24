"""Server tab: which game server DBD is connected to (like "Connected to" in Make Your Choice).

Program started as administrator: ``netwatch`` runs in a thread of this
process (no prompt). Otherwise the helper ``netwatch.py`` is started with
administrator rights (UAC). Either way it writes its result file, read here.
The game server is the busiest UDP partner on a public address whose
reverse DNS name is an AWS EC2 machine (GameLift runs on EC2); the region
is part of that name, e.g. ``ec2-3-120-1-2.eu-central-1.compute.amazonaws.com``.

1.11.6 (user's decision): only partners on DBD's own UDP ports count. Windows
lists which process owns each local UDP port (``GetExtendedUdpTable``); the
process id comes from the DBD window (``GetWindowThreadProcessId``, window
information like the title). Neither opens the game process – no
``OpenProcess``, no handle, nothing read from it. Without the window or the
table the busiest partner is taken as before.

Ping: while connected, the region is measured every few seconds like in the
Server tab (``regions.ping_once``: ICMP to ``gamelift.<region>.amazonaws.com``,
else the UDP ping beacon). The game server is never sent anything.
"""
from __future__ import annotations

import collections
import ctypes
import ipaddress
import json
import os
import re
import socket
import statistics
import sys
import tempfile
import threading
import time

from . import netwatch, regions
from .i18n import _

IS_WIN = sys.platform == "win32"
MIN_PPS = 10.0         # a running match exchanges dozens of packets per second with its server
LOST_AFTER = 8.0       # no server traffic for this long -> not connected any more
TOUCH_EVERY = 5.0      # refresh the control file (the helper stops when it gets older than 20 s)
NO_DATA_AFTER = 8.0    # result file not updated for this long -> the helper is not working
RDNS_RETRY = 60.0      # look up an address again after this long if it gave no AWS region
PING_EVERY = 5.0       # one ping to the region's beacon this often while connected (GameLift allows 3/s)
PING_KEEP = 3          # shown value = median of the last pings (one slow packet does not jump the display)
PEAK_KEEP = 1800.0     # diagnostics: busiest partners of the last 30 min (the match is over when it is copied)
PEAK_MAX = 8
PORTS_EVERY = 2.0      # 1.11.6: DBD's UDP ports looked up again this often (a new match may open a new socket)
UNKNOWN = "?"          # region of a game server that AWS does not tell (see AWS_GLOBAL_EC2)
# EC2 address ranges AWS publishes with region "GLOBAL" (ip-ranges.json, service EC2, as of 2026-10-09): machines
# there have no reverse DNS name, so the region cannot be read from the address. GameLift runs DBD servers in
# 54.115.0.0/16 (seen 2026-10). Bundled instead of downloaded: the server display opens no new connection.
AWS_GLOBAL_EC2 = tuple(ipaddress.ip_network(n) for n in (
    "3.4.8.0/24", "15.177.0.0/18", "15.193.32.0/19", "23.228.196.0/24", "23.228.197.0/24", "23.228.198.0/24",
    "31.220.247.0/24", "35.54.16.0/20", "40.168.224.0/24", "40.168.225.0/24", "40.168.226.0/24",
    "40.168.227.0/24", "40.168.228.0/24", "40.168.229.0/24", "40.168.230.0/24", "40.168.231.0/24",
    "54.25.32.0/19", "54.25.192.0/18", "54.115.0.0/16", "63.249.128.0/18", "63.249.192.0/19", "64.73.192.0/19",
    "159.248.232.0/21", "159.248.240.0/21", "216.39.168.0/21"))
_REGION_RE = re.compile(r"\.([a-z]{2}(?:-[a-z]+)+-\d)\.compute\.amazonaws\.com$")


def region_from_ptr(name: str) -> str | None:
    """AWS region code from an EC2 reverse DNS name, else None."""
    name = (name or "").lower().rstrip(".")
    if name.endswith(".compute-1.amazonaws.com"):          # us-east-1 has its own naming
        return "us-east-1"
    m = _REGION_RE.search(name)
    return m.group(1) if m else None


def pick_server(flows, region_of, ports=None) -> dict | None:
    """Busiest partner with enough traffic whose region is known. ``flows`` is sorted busiest first;
    ``region_of(ip)`` returns a region code, or None when not an AWS server / not resolved yet. ``ports``
    (1.11.6): DBD's own local UDP ports – then only partners that talked to one of them count (no ports = DBD has
    no UDP socket = not in a match); None = unknown, the busiest partner as before. Flows without local ports (a
    result file of an older helper) are judged the old way."""
    for f in flows:
        if f.get("pps", 0) < MIN_PPS:
            break
        if ports is not None and "lports" in f and not set(f["lports"]) & ports:
            continue
        code = region_of(f["ip"])
        if code:
            return {**f, "region": code}
    return None


# ---------------------------------------------------------------- 1.11.6: DBD's own UDP ports
AF_INET6 = 23                  # Windows' value (socket.AF_INET6 differs between platforms)
UDP_TABLE_OWNER_PID = 1
ERROR_INSUFFICIENT_BUFFER = 122
ROW_SIZE = {socket.AF_INET: 12, AF_INET6: 28}   # MIB_UDPROW_OWNER_PID / MIB_UDP6ROW_OWNER_PID
PORT_AT = {socket.AF_INET: 4, AF_INET6: 20}     # offset of dwLocalPort in a row (dwOwningPid follows it)


def parse_udp_table(buf: bytes, family: int, pid: int) -> set:
    """Local ports owned by ``pid`` in a MIB_UDP(6)TABLE_OWNER_PID as GetExtendedUdpTable fills it: a DWORD count,
    then the rows; the port is the low word of dwLocalPort in network byte order. Pure, bounded by the buffer."""
    if len(buf) < 4:
        return set()
    size, at = ROW_SIZE[family], PORT_AT[family]
    n = min(int.from_bytes(buf[:4], "little"), (len(buf) - 4) // size)
    out = set()
    for i in range(n):
        row = 4 + i * size
        if int.from_bytes(buf[row + at + 4:row + at + 8], "little") == pid:
            out.add(int.from_bytes(buf[row + at:row + at + 2], "big"))
    return out


def window_pid(hwnd) -> int | None:
    """Process id of the window ``hwnd`` – window information (user32), the process is not opened."""
    if not IS_WIN or not hwnd:
        return None
    try:
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.c_void_p(int(hwnd)), ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def udp_ports(pid: int) -> set | None:
    """Local UDP ports (IPv4 and IPv6) Windows lists for process ``pid`` (GetExtendedUdpTable, the same table as
    netstat -abno), None when the table cannot be read. Reads the system's table only, never the process."""
    if not IS_WIN or not pid:
        return None
    try:
        api = ctypes.windll.iphlpapi.GetExtendedUdpTable
        api.restype = ctypes.c_ulong
        api.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int, ctypes.c_ulong,
                        ctypes.c_int, ctypes.c_ulong)
    except (AttributeError, OSError):
        return None
    out, read = set(), False
    for family in (socket.AF_INET, AF_INET6):
        size = ctypes.c_ulong(0)
        for _attempt in range(3):                  # the table may grow between the two calls
            buf = ctypes.create_string_buffer(max(size.value, 4))
            err = api(buf, ctypes.byref(size), 0, family, UDP_TABLE_OWNER_PID, 0)
            if err == 0:
                out |= parse_udp_table(buf.raw[:size.value or len(buf)], family, pid)
                read = True
                break
            if err != ERROR_INSUFFICIENT_BUFFER:
                break
    return out if read else None


def aws_global(ip: str) -> bool:
    """EC2 address whose region AWS does not publish (no reverse DNS name either)."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a in n for n in AWS_GLOBAL_EC2)


def region_name(code: str) -> str:
    if code == UNKNOWN:
        return _("Global")                # 1.64.6 (user): AWS lists the range as EC2 "GLOBAL"
    return _(regions.NAMES.get(code, code))


def is_admin() -> bool:
    """This program runs with administrator rights (e.g. started via "Als Administrator ausführen")."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class IdlePause:
    """Pause the capture while DBD is not running (pure logic, testable).

    Only used when restarting costs nothing (program runs as administrator: capture thread
    in this process, no UAC prompt). Returns "pause" / "resume" / None per update."""
    AFTER = 30.0            # DBD gone this long -> pause

    def __init__(self):
        self.paused = False
        self._gone_since = None

    def update(self, t: float, game_running: bool, capturing: bool, can_pause: bool):
        if game_running:
            self._gone_since = None
            if self.paused:
                self.paused = False
                return "resume"
            return None
        self._gone_since = self._gone_since if self._gone_since is not None else t
        if capturing and can_pause and not self.paused and t - self._gone_since >= self.AFTER:
            self.paused = True
            return "pause"
        return None

    def reset(self):
        self.paused, self._gone_since = False, None


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
        self.ping_ms = None            # latency to the connected region (median of the last pings)
        self._pings = collections.deque(maxlen=PING_KEEP)
        self._ping_region = None
        self._next_ping = 0.0
        self._pinging = False
        self._beacons = {}             # host name -> address (regions.ping_once cache)
        self._names = {}               # ip -> reverse DNS name or error (diagnostics only)
        self._local = ""               # address of the captured interface (diagnostics only)
        self._result_t = 0.0
        self.peaks = {}                # ip -> busiest moment {"pps", "port", "sent", "recv", "t"} (diagnostics)
        self.ports = None              # 1.11.6: DBD's local UDP ports (None = unknown → busiest partner)
        self.ports_why = "noch nicht gefragt"   # diagnostics: where the ports came from or why there are none
        self._ports_at = 0.0
        self._pid_of = (None, None)    # (hwnd, pid) – one lookup per DBD window

    @property
    def running(self) -> bool:
        return self.proc is not None

    @property
    def in_process(self) -> bool:
        """Capture runs as a thread of this program (started as administrator): restarting is free."""
        return isinstance(self.proc, threading.Thread)

    # --------------------------------------------------------------- start/stop
    def start(self, hwnd=None) -> dict | None:
        """Start capturing. Returns an error dict or None. Without administrator rights Windows asks
        (UAC) and this blocks until the prompt is answered – call from a thread."""
        if self.running:
            return None
        if not IS_WIN:
            return {"error": _("Nur unter Windows verfügbar.")}
        fd, control = tempfile.mkstemp(prefix="fogscout-net-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"stop": False}, fh)
        fd, result = tempfile.mkstemp(prefix="fogscout-netres-", suffix=".json")
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
        self._update_ping(0.0)

    # --------------------------------------------------------------- polling
    def poll(self, now: float | None = None, game_hwnd=None) -> None:
        """Call about once a second from the UI thread. ``game_hwnd`` (1.11.6): the DBD window, for its ports."""
        if not self.running:
            return
        now = now or time.time()
        self._update_ports(now, game_hwnd)
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
            self.error = (data or {}).get("error") or _("Mitschnitt beendet (Code {code}).", code=code)
            self.stop()
            return
        if not data or not data.get("ok"):
            self.no_data = now - self._started > NO_DATA_AFTER
            return
        self.no_data = now - float(data.get("t", 0)) > NO_DATA_AFTER
        self._local, self._result_t = str(data.get("local") or ""), float(data.get("t", 0))
        self._note_peaks(data.get("flows") or [], now)
        found = pick_server(data.get("flows") or [], self._region, self.ports)
        # No guess from the hosts file for UNKNOWN: in a friend's party their matchmaking picks the server
        # (1.41.5, user saw "Singapore" while playing on Frankfurt).
        if found:
            self.server, self._seen = found, now
        elif self.server and now - self._seen > LOST_AFTER:
            self.server = None
        self._update_ping(now)

    def _update_ports(self, now: float, hwnd) -> None:
        """1.11.6: DBD's own UDP ports, looked up every PORTS_EVERY s while its window is there."""
        if not hwnd:
            self.ports, self.ports_why, self._pid_of = None, "kein DBD-Fenster (Schätzung)", (None, None)
            return
        if now - self._ports_at < PORTS_EVERY and self._pid_of[0] == hwnd:
            return
        self._ports_at = now
        if self._pid_of[0] != hwnd:
            self._pid_of = (hwnd, window_pid(hwnd))
        pid = self._pid_of[1]
        ports = udp_ports(pid) if pid else None
        self.ports = ports
        if pid is None:
            self.ports_why = "Prozess des DBD-Fensters unbekannt (Schätzung)"
        elif ports is None:
            self.ports_why = "Verbindungstabelle von Windows nicht lesbar (Schätzung)"
        else:
            self.ports_why = f"{len(ports)} aus der Verbindungstabelle von Windows"

    # --------------------------------------------------------------- ping
    def _update_ping(self, now: float) -> None:
        region = self.server["region"] if self.server else None
        if region == UNKNOWN:
            region = None                            # no beacon to ping; the game server itself never gets a packet
        with self._lock:
            if region != self._ping_region:          # other region / no server: old values are void
                self._ping_region = region
                self._pings.clear()
                self.ping_ms = None
                self._next_ping = 0.0
            if region is None or self._pinging or now < self._next_ping:
                return
            self._pinging = True
            self._next_ping = now + PING_EVERY
        threading.Thread(target=self._ping, args=(region,), daemon=True, name="ping").start()

    def _ping(self, region: str) -> None:
        ms = None
        try:
            ms = regions.ping_once(region, self._beacons)[0]   # DNS server, ignores the hosts file
        except Exception:
            ms = None
        with self._lock:
            if region == self._ping_region and ms is not None:
                self._pings.append(ms)
                self.ping_ms = float(statistics.median(self._pings))
            self._pinging = False

    def _read(self):
        try:
            with open(self.result, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError, TypeError):
            return None                          # not written yet / being written right now

    def _region(self, ip: str) -> str | None:
        if aws_global(ip):
            return UNKNOWN                       # no reverse DNS name to look up
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
            name = socket.gethostbyaddr(ip)[0]
            code = region_from_ptr(name) or ""
        except OSError as e:
            name, code = f"({type(e).__name__}: {e})", ""
        with self._lock:
            self._rdns[ip] = (code, time.time())
            self._names[ip] = name

    # --------------------------------------------------------------- diagnostics
    def _note_peaks(self, flows, now: float) -> None:
        for f in flows:
            p = self.peaks.get(f["ip"])
            if p is None or f.get("pps", 0) >= p["pps"]:
                p = self.peaks[f["ip"]] = {k: f.get(k, 0) for k in ("pps", "port", "sent", "recv")} | {"t": now}
            p["seen"] = now
            if self.ports is not None and "lports" in f:     # 1.11.6: did it talk to one of DBD's ports?
                p["dbd"] = p.get("dbd", False) or bool(set(f["lports"]) & self.ports)
        old = [ip for ip, p in self.peaks.items() if now - p["seen"] > PEAK_KEEP]
        for ip in old:
            del self.peaks[ip]
        if len(self.peaks) > PEAK_MAX:
            for ip in sorted(self.peaks, key=lambda i: self.peaks[i]["pps"])[:len(self.peaks) - PEAK_MAX]:
                del self.peaks[ip]
            for ip in [i for i in self._names if i not in self.peaks]:
                self._names.pop(ip, None)

    def diag_lines(self, now: float | None = None) -> list:
        """Diagnostics text (German, not translated): why no server is chosen. Addresses are masked –
        the text is saved as diagnose.txt, and the server address never goes to a file."""
        now = now or time.time()
        srv = self.server
        lines = [f"Verbunden mit: läuft={self.running} als_thread={self.in_process} keine_daten={self.no_data} "
                 f"fehler={self.error or '—'} server={srv['region'] if srv else '—'} ping={self.ping_ms} "
                 f"schnittstelle={_mask_local(self._local)} ergebnis_vor="
                 f"{f'{now - self._result_t:.0f} s' if self._result_t else '—'} (Server ab {MIN_PPS:.0f}/s + AWS-EC2-Name)",
                 f"  DBD-Ports: {self.ports_why}"]
        if not self.peaks:
            lines.append("  Gegenstellen: keine (kein UDP-Verkehr mit öffentlichen Adressen gesehen)")
            return lines
        lines.append(f"  Gegenstellen (Spitze je Adresse, letzte {PEAK_KEEP / 60:.0f} min):")
        with self._lock:
            names, rdns = dict(self._names), dict(self._rdns)
        for ip, p in sorted(self.peaks.items(), key=lambda kv: -kv[1]["pps"]):
            code = (rdns.get(ip) or (None,))[0]
            name = names.get(ip)
            if aws_global(ip):
                code, name = "AWS EC2 GLOBAL (Region unbekannt)", "nicht gefragt"
            region = code or ("ausstehend" if name is None else "kein AWS-EC2-Name")
            owner = {True: " · DBD", False: " · nicht DBD"}.get(p.get("dbd"), "")
            lines.append(f"  {_mask_ip(ip)} Port {p['port']} · {p['pps']}/s ({p['sent']} gesendet/{p['recv']} "
                         f"empfangen in 5 s) vor {now - p['t']:.0f} s · rDNS {_mask_name(name) if name else '—'} → "
                         f"{region}{owner}")
        return lines

    # --------------------------------------------------------------- text
    def text(self) -> str:
        if not self.running:
            return _("Fehler: {error}", error=self.error) if self.error else ""
        if self.no_data:
            return _("keine Daten vom Mitschnitt")
        if self.server:
            ping = f" · {self.ping_ms:.0f} ms" if self.ping_ms is not None else ""
            return f"{region_name(self.server['region'])} ({self.server['ip']}){ping}"
        return _("Warte auf Match …")


def _mask_ip(ip: str) -> str:
    parts = ip.split(".")
    return ".".join(parts[:2] + ["x", "x"]) if len(parts) == 4 else "?"


def _mask_local(ip: str) -> str:
    """Private addresses as they are (they tell VPN/virtual adapters apart), public ones masked."""
    if not ip:
        return "—"
    try:
        private = ipaddress.ip_address(ip).is_private
    except ValueError:
        private = False
    return ip if private else _mask_ip(ip) + " (öffentlich)"


def _mask_name(name: str) -> str:
    """Reverse DNS name without the address in it (ec2-3-120-1-2.eu-… → ec2-….eu-…)."""
    return re.sub(r"\d{1,3}([-.])\d{1,3}\1\d{1,3}\1\d{1,3}", "…", name)


def _remove(*paths):
    for p in paths:
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
