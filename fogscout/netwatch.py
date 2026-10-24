"""Which game server is DBD connected to? (idea: "Connected to" in Make Your Choice, own implementation)

Started by the program with administrator rights (Windows asks via UAC):
    pythonw.exe -I -S netwatch.py <control.json> <result.json>

How: a Windows raw socket with SIO_RCVALL in IP-level mode on the network
interface of the default route: only this computer's own traffic arrives,
the network card is not switched to promiscuous mode (and there is no
fallback to it). Only the IPv4/UDP headers are looked at (addresses,
ports); packet contents are never read or stored. Nothing is sent, nothing is
changed, and the game process is not touched. Once a second the busiest
UDP partners on public addresses are written to the result file, each with the
local ports it talked to (1.11.6: the program matches them against the ports
Windows lists for DBD's process); the program decides which one is the game
server.

The helper stops by itself when the control file is gone, asks it to stop,
or has not been refreshed for STALE seconds (program closed or crashed).

Only the standard library is used (the elevated helper runs isolated).
"""
from __future__ import annotations

import collections
import ipaddress
import json
import os
import socket
import struct
import sys
import time

STALE = 20.0             # control file not refreshed for this long -> the program is gone, stop
WINDOW = 5.0             # packet rates are averaged over this many seconds
WRITE_EVERY = 1.0
REBIND_EVERY = 10.0      # the default-route interface may change (VPN on/off)
RCVALL_IPLEVEL = getattr(socket, "RCVALL_IPLEVEL", 3)   # own traffic only; RCVALL_ON (1) = promiscuous, never used
# not a game server: DNS, NTP, QUIC/HTTP3, GameLift ping beacons, mDNS, SSDP, NetBIOS
IGNORE_PORTS = frozenset({53, 123, 137, 138, 443, 1900, 5353, 7770})


def parse(pkt: bytes):
    """(src, dst, src port, dst port) of an IPv4 UDP packet, else None. Only header fields are read."""
    if len(pkt) < 20 or pkt[0] >> 4 != 4 or pkt[9] != 17:
        return None
    ihl = (pkt[0] & 0x0F) * 4
    if ihl < 20 or len(pkt) < ihl + 4:
        return None
    if struct.unpack_from("!H", pkt, 6)[0] & 0x1FFF:          # later fragment: carries no UDP header
        return None
    sport, dport = struct.unpack_from("!HH", pkt, ihl)
    return socket.inet_ntoa(pkt[12:16]), socket.inet_ntoa(pkt[16:20]), sport, dport


_PUBLIC = {}                 # ip -> is_global; the same few partners come again thousands of times per second


def is_public(ip: str) -> bool:
    r = _PUBLIC.get(ip)
    if r is None:
        try:
            r = ipaddress.ip_address(ip).is_global
        except ValueError:
            r = False
        if len(_PUBLIC) > 4096:          # bounded (port scans, torrents …)
            _PUBLIC.clear()
        _PUBLIC[ip] = r
    return r


LPORTS_KEPT = 4             # 1.11.6: local ports listed per partner (a game server talks to one)
STALL_S = 0.25              # 1.11.9: nothing received from a partner for this long, then a packet = one gap
SNAPSHOT_LIMIT = 8          # 1.11.6: partners written (5 before) – the game server may not be the busiest one


class FlowTable:
    """UDP packet counts per remote public address over the last WINDOW seconds."""

    def __init__(self, window: float = WINDOW):
        self.window = window
        # remote ip -> {"sent": deque[t], "recv": deque[t], "ports": {remote port: n}, "lports": {local port: n}}
        self.flows = {}

    def add(self, t: float, local: str, p) -> None:
        src, dst, sport, dport = p
        if src == local:
            remote, port, lport, way = dst, dport, sport, "sent"
        elif dst == local:
            remote, port, lport, way = src, sport, dport, "recv"
        else:
            return
        if port in IGNORE_PORTS or not is_public(remote):
            return
        f = self.flows.get(remote)
        if f is None:
            f = self.flows[remote] = {"sent": collections.deque(), "recv": collections.deque(), "ports": {},
                                      "lports": {}, "last_recv": None, "gaps": collections.deque()}
        if way == "recv":                    # 1.11.9: gaps between two received packets (arrival times only)
            last = f["last_recv"]
            if last is not None and t - last >= STALL_S:
                f["gaps"].append((t, t - last))
            f["last_recv"] = t
        f[way].append(t)
        f["ports"][port] = f["ports"].get(port, 0) + 1
        f["lports"][lport] = f["lports"].get(lport, 0) + 1

    def snapshot(self, now: float, limit: int = SNAPSHOT_LIMIT) -> list:
        """Busiest partners first: [{"ip", "port", "lports", "pps", "sent", "recv", "gaps", "quiet"}] (sent/recv =
        packets in the window, lports = the local ports most used with this partner, busiest first; 1.11.9: gaps =
        [[end time, seconds]] of the receive gaps ≥ STALL_S that ended in the window, quiet = seconds since the last
        packet from it)."""
        cut = now - self.window
        out = []
        for ip in list(self.flows):
            f = self.flows[ip]
            for way in ("sent", "recv"):
                d = f[way]
                while d and d[0] < cut:
                    d.popleft()
            n = len(f["sent"]) + len(f["recv"])
            if not n:
                del self.flows[ip]
                continue
            lports = sorted(f["lports"], key=lambda k: -f["lports"][k])[:LPORTS_KEPT]
            gaps = f["gaps"]
            while gaps and gaps[0][0] < cut:
                gaps.popleft()
            out.append({"ip": ip, "port": max(f["ports"], key=f["ports"].get), "lports": lports,
                        "pps": round(n / self.window, 1), "sent": len(f["sent"]), "recv": len(f["recv"]),
                        "gaps": [[round(te, 3), round(s, 3)] for te, s in gaps],
                        "quiet": None if f["last_recv"] is None else round(max(0.0, now - f["last_recv"]), 3)})
        out.sort(key=lambda x: -x["pps"])
        return out[:limit]


def local_ip() -> str:
    """Address of the interface with the default route (connect() on UDP sends nothing)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]


def keep_running(control: str, now: float) -> bool:
    try:
        if now - os.stat(control).st_mtime > STALE:
            return False
        with open(control, encoding="utf-8") as fh:
            return not json.load(fh).get("stop")
    except (OSError, ValueError, AttributeError):
        return False


def write(result: str, data: dict) -> None:
    """Overwrite the result file in place. It was created by the (non-elevated) program, so it keeps its
    owner and the program can read it; a file the program already removed is not created again."""
    try:
        with open(result, "r+", encoding="utf-8") as fh:
            json.dump(data, fh)
            fh.truncate()
    except OSError:
        pass


def watch(control: str, result: str) -> None:
    table = FlowTable()
    while True:
        local = local_ip()
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        try:
            s.bind((local, 0))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            try:
                s.ioctl(socket.SIO_RCVALL, RCVALL_IPLEVEL)
            except PermissionError:
                raise                                    # no administrator rights: reported as such
            except OSError as e:
                raise OSError(f"Windows unterstützt den Mitschnitt nur des eigenen Verkehrs (RCVALL_IPLEVEL) "
                              f"hier nicht ({e}). Der Promiscuous-Modus wird bewusst nicht verwendet.") from e
            s.settimeout(0.5)
            next_write = next_check = 0.0
            rebind_at = time.time() + REBIND_EVERY
            while True:
                try:
                    pkt = s.recv(65535)
                except socket.timeout:
                    pkt = None
                now = time.time()
                if pkt:
                    p = parse(pkt)
                    if p:
                        table.add(now, local, p)
                if now >= next_check:
                    if not keep_running(control, now):
                        return
                    next_check = now + 2.0
                if now >= next_write:
                    write(result, {"ok": True, "t": now, "local": local, "flows": table.snapshot(now)})
                    next_write = now + WRITE_EVERY
                if now >= rebind_at:
                    rebind_at = now + REBIND_EVERY
                    try:
                        if local_ip() != local:
                            break                        # interface changed -> listen on the new one
                    except OSError:
                        pass
        finally:
            try:
                s.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            except (OSError, AttributeError):
                pass
            s.close()


def main(argv):
    if len(argv) != 3:
        print("usage: netwatch.py <control.json> <result.json>")
        return 2
    try:
        watch(argv[1], argv[2])
        return 0
    except PermissionError:
        err = "Keine Berechtigung für den Netzwerk-Mitschnitt (Administratorrechte?)."
    except OSError as e:
        err = f"Netzwerk-Mitschnitt nicht möglich: {e}"
    except Exception as e:  # report everything to the program
        err = f"{type(e).__name__}: {e}"
    write(argv[2], {"ok": False, "t": time.time(), "error": err})
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
