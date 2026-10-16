"""Round history for the "Statistik" tab – pure logic plus a small JSON-lines file (rounds.jsonl).

One line per round that lasted at least MIN_SECONDS (tests and a map shown briefly by hand do not
count). Stored only locally, nothing leaves the PC. The file is a runtime file (gitignored).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

FILE = "rounds.jsonl"
MIN_SECONDS = 60.0
KEEP = 5000                 # newest rounds kept when the file is tidied


@dataclass
class Round:
    t: float                # start (time.time())
    seconds: float
    map_id: str
    map: str                # label shown, incl. layout ("Coal Tower II")
    region: str = ""        # AWS region code of the game server, if "Verbunden mit" was on
    source: str = ""        # auto | manual | scan
    wait: float | None = None   # seconds searched in the lobby until it was found (None: not seen / custom)
    role: str = ""          # killer | survivor | "" (unknown)
    custom: bool = False    # custom game (no queue)
    ping: float | None = None   # median ping (ms) to the server region during the round
    killer: str = ""        # own killer, read in the lobby ("The Nurse"); counts only while role == killer
    sys: dict | None = None     # system values during the round (sysinfo.SysRecorder: averages and maxima)


def should_record(seconds: float) -> bool:
    return seconds >= MIN_SECONDS


def append(path: str, rnd: Round) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(rnd), ensure_ascii=False) + "\n")
    _tidy(path)


def _tidy(path: str) -> None:
    """Keep the file from growing forever: rewrite it with the newest KEEP rounds now and then."""
    try:
        if os.path.getsize(path) < KEEP * 200:
            return
        rounds = load(path)
        if len(rounds) <= KEEP:
            return
        kept = rounds[-KEEP:]
        _rewrite(path, kept, [d for d in _lost_lines(path) if d["t"] >= kept[0].t])
    except OSError:
        pass


def _rewrite(path: str, rounds, lost) -> None:
    """Write rounds and lost-round lines (as ``_lost_lines()`` returns them) back in time order (atomic)."""
    lines = [(r.t, json.dumps(asdict(r), ensure_ascii=False)) for r in rounds] + \
        [(d["t"], json.dumps(d, ensure_ascii=False)) for d in lost]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for _t, line in sorted(lines, key=lambda x: x[0]):
            fh.write(line + "\n")
    os.replace(tmp, path)


LOST_KEYS = ("map_id", "region", "source", "wait", "role", "custom", "killer", "ping", "sys")   # since 1.35/1.43


def append_lost(path: str, t: float, map_label: str, reason: str, **known) -> None:
    """A round whose end was not detected (not counted): kept as its own line so the statistics can
    say how many rounds are missing – with what was known about it (``LOST_KEYS``), so it can still
    count once the official match data brings its length. load() skips these lines."""
    rec = {"lost": True, "t": t, "map": map_label, "reason": reason}
    rec.update({k: v for k, v in known.items() if k in LOST_KEYS and v not in (None, "")})
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _lost_lines(path: str) -> list:
    """The lost-round lines as stored (dicts with a float ``t``), oldest first."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if '"lost"' not in line:           # quick skip: parsing all 5000 rounds took ~50 ms
                    continue
                try:
                    d = json.loads(line)
                    if isinstance(d, dict) and d.get("lost"):
                        d["t"] = float(d["t"])
                        out.append(d)
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return []
    return out


def load_lost(path: str) -> list:
    """[(t, map label, reason)] of the rounds that were not counted, oldest first."""
    return [(d["t"], str(d.get("map") or ""), str(d.get("reason") or "")) for d in _lost_lines(path)]


def load_lost_rounds(path: str) -> list:
    """The rounds that were not counted as Round objects without a length (``seconds`` = 0);
    lines from before 1.35 only know time and map label (``map_id`` = "")."""
    out = []
    for d in _lost_lines(path):
        wait, ping = d.get("wait"), d.get("ping")
        out.append(Round(t=d["t"], seconds=0.0, map_id=str(d.get("map_id") or ""),
                         map=str(d.get("map") or d.get("map_id") or ""), region=str(d.get("region") or ""),
                         source=str(d.get("source") or ""),
                         wait=float(wait) if isinstance(wait, (int, float)) and wait >= 0 else None,
                         role=str(d.get("role") or "") if d.get("role") in ROLES else "",
                         custom=bool(d.get("custom")),
                         ping=float(ping) if isinstance(ping, (int, float)) and ping >= 0 else None,
                         killer=str(d.get("killer") or ""), sys=_sys(d.get("sys"))))
    return out


def load(path: str) -> list:
    """All rounds, oldest first; broken lines and lines of lost rounds are skipped."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    if d.get("lost"):
                        continue
                    wait = d.get("wait")
                    out.append(Round(t=float(d["t"]), seconds=float(d["seconds"]), map_id=str(d["map_id"]),
                                     map=str(d.get("map") or d["map_id"]), region=str(d.get("region") or ""),
                                     source=str(d.get("source") or ""),
                                     wait=float(wait) if isinstance(wait, (int, float)) and wait >= 0 else None,
                                     role=str(d.get("role") or "") if d.get("role") in ROLES else "",
                                     custom=bool(d.get("custom")),
                                     ping=float(d["ping"]) if isinstance(d.get("ping"), (int, float))
                                     and d["ping"] >= 0 else None,
                                     killer=str(d.get("killer") or ""), sys=_sys(d.get("sys"))))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return []
    return out


def _sys(d):
    """System values of a round as stored: only numbers, None without any."""
    if not isinstance(d, dict):
        return None
    out = {str(k): float(v) for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return out or None


def clear(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def summary(rounds) -> dict:
    total = sum(r.seconds for r in rounds)
    return {"count": len(rounds), "total": total, "avg": total / len(rounds) if rounds else 0.0}


def today(rounds, now: float) -> dict:
    """Today at a glance (calendar day, all filters off): rounds, killer/survivor, play time, average wait,
    most played killer, median ping."""
    rs = select(rounds, since=period_start("day", now))
    waits = [r.wait for r in rs if r.wait is not None and not r.custom]
    killers = killers_used(rs)
    return {"count": len(rs), "total": sum(r.seconds for r in rs),
            "killer": sum(1 for r in rs if r.role == "killer" and not r.custom),
            "survivor": sum(1 for r in rs if r.role == "survivor" and not r.custom),
            "wait": sum(waits) / len(waits) if waits else None,
            "top_killer": killers[0] if killers else "",
            "ping": median([r.ping for r in rs if r.ping is not None])}


def roles_per_map(rounds) -> dict:
    """{map label: (killer rounds, survivor rounds)} – custom games and unknown roles count for neither."""
    out = {}
    for r in rounds:
        k, s = out.get(r.map, (0, 0))
        if not r.custom and r.role == "killer":
            k += 1
        elif not r.custom and r.role == "survivor":
            s += 1
        out[r.map] = (k, s)
    return out


def per_map(rounds) -> list:
    """[(map label, rounds, average s, longest s)], most played first."""
    groups = {}
    for r in rounds:
        groups.setdefault(r.map, []).append(r.seconds)
    rows = [(m, len(s), sum(s) / len(s), max(s)) for m, s in groups.items()]
    return sorted(rows, key=lambda row: (-row[1], row[0].lower()))


# ------------------------------------------------------------------ filters (tab Statistik)
PERIODS = ("all", "day", "week", "month", "year")
NO_REGION = "-"


def period_start(period: str, now: float):
    """Start of the current calendar day / week (Monday) / month / year in local time; None = all."""
    import datetime
    if period not in PERIODS or period == "all":
        return None
    d = datetime.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        d -= datetime.timedelta(days=d.weekday())
    elif period == "month":
        d = d.replace(day=1)
    elif period == "year":
        d = d.replace(month=1, day=1)
    return d.timestamp()


ROLES = ("killer", "survivor")
ROLE_FILTERS = ("all", "killer", "survivor", "custom")


def select(rounds, since=None, region=None, role="all", killer=None) -> list:
    """Rounds from ``since`` on; ``region``: None = all, NO_REGION = rounds without a known server;
    ``role``: all | killer | survivor | custom (custom games only); ``killer``: None = all, else only
    killer rounds with this killer."""
    out = [r for r in rounds if since is None or r.t >= since]
    if killer:
        out = [r for r in out if r.killer == killer and r.role == "killer" and not r.custom]
    if role == "custom":
        out = [r for r in out if r.custom]
    elif role in ROLES:
        out = [r for r in out if r.role == role and not r.custom]
    if region == NO_REGION:
        out = [r for r in out if not r.region]
    elif region:
        out = [r for r in out if r.region == region]
    return out


def regions_used(rounds) -> list:
    """Region codes that occur, most rounds first (for the filter list)."""
    counts = {}
    for r in rounds:
        if r.region:
            counts[r.region] = counts.get(r.region, 0) + 1
    return sorted(counts, key=lambda c: (-counts[c], c))


def killers_used(rounds) -> list:
    """Killers of the killer rounds, most rounds first (for the filter list)."""
    counts = {}
    for r in rounds:
        if r.killer and r.role == "killer" and not r.custom:
            counts[r.killer] = counts.get(r.killer, 0) + 1
    return sorted(counts, key=lambda k: (-counts[k], k))


def per_killer(rounds) -> list:
    """[(killer, rounds, average s, most played map)] of the killer rounds, most rounds first."""
    groups = {}
    for r in rounds:
        if r.killer and r.role == "killer" and not r.custom:
            groups.setdefault(r.killer, []).append(r)
    rows = []
    for k, rs in groups.items():
        top = per_map(rs)[0][0]
        rows.append((k, len(rs), sum(r.seconds for r in rs) / len(rs), top))
    return sorted(rows, key=lambda row: (-row[1], row[0]))


def per_region(rounds) -> list:
    """[(region code or NO_REGION, rounds, average s, share 0..1)], most rounds first."""
    groups = {}
    for r in rounds:
        groups.setdefault(r.region or NO_REGION, []).append(r.seconds)
    total = len(rounds) or 1
    rows = [(c, len(s), sum(s) / len(s), len(s) / total) for c, s in groups.items()]
    return sorted(rows, key=lambda row: (-row[1], row[0] == NO_REGION, row[0]))


# ------------------------------------------------------------------ waiting time in the lobby
WAIT_GROUPS = ("weekday", "hour", "region")
HOUR_BLOCK = 3              # time of day in blocks of 3 hours (00–03, 03–06, …)


def wait_summary(rounds) -> dict:
    """Waiting times of rounds that have one (public matches whose search was seen)."""
    w = sorted(r.wait for r in rounds if r.wait is not None and not r.custom)
    if not w:
        return {"count": 0, "avg": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {"count": len(w), "avg": sum(w) / len(w), "median": w[len(w) // 2], "min": w[0], "max": w[-1]}


def _wait_key(r, by):
    import datetime
    d = datetime.datetime.fromtimestamp(r.t)
    if by == "weekday":
        return d.weekday()                                   # 0 = Monday
    if by == "hour":
        return d.hour // HOUR_BLOCK * HOUR_BLOCK             # start hour of the block
    return r.region or NO_REGION


def wait_by(rounds, by: str) -> list:
    """[(key, rounds, average wait s, shortest s)] – weekday 0..6 and hour blocks in calendar order,
    regions by shortest average wait (the answer to "where/when do I find a match fastest?")."""
    groups = {}
    for r in rounds:
        if r.wait is not None and not r.custom:
            groups.setdefault(_wait_key(r, by), []).append(r.wait)
    rows = [(k, len(w), sum(w) / len(w), min(w)) for k, w in groups.items()]
    if by == "region":
        return sorted(rows, key=lambda row: (row[0] == NO_REGION, row[2]))
    return sorted(rows)


def set_role(path: str, t: float, role: str):
    """Correct the role of the round that started at ``t`` (role: killer | survivor | custom).
    Rewrites the file; returns the changed round or None."""
    if role not in ROLES + ("custom",):
        raise ValueError(role)
    rounds = load(path)
    hit = next((r for r in rounds if abs(r.t - t) < 1e-6), None)
    if hit is None:
        return None
    hit.custom = role == "custom"
    hit.role = "" if hit.custom else role       # the waiting time stays (ignored for custom games): undo-able
    _rewrite(path, rounds, _lost_lines(path))
    return hit


def delete(path: str, t: float):
    """Remove the round that started at ``t`` (e.g. a false detection). Returns the removed round or None."""
    rounds = load(path)
    hit = next((r for r in rounds if abs(r.t - t) < 1e-6), None)
    if hit is None:
        return None
    _rewrite(path, [r for r in rounds if r is not hit], _lost_lines(path))
    return hit


def set_killer(path: str, t: float, killer: str):
    """Set the killer of the round that started at ``t`` (also makes it a killer round – e.g. a round
    wrongly counted as survivor has no name from the lobby). Returns the changed round or None."""
    if not killer:
        raise ValueError(killer)
    rounds = load(path)
    hit = next((r for r in rounds if abs(r.t - t) < 1e-6), None)
    if hit is None:
        return None
    hit.killer, hit.role, hit.custom = killer, "killer", False
    _rewrite(path, rounds, _lost_lines(path))
    return hit


# ------------------------------------------------------------------ ping
def median(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def ping_by_region(rounds) -> dict:
    """{region code: average of the rounds' ping}, only rounds with a measured ping."""
    groups = {}
    for r in rounds:
        if r.ping is not None and r.region:
            groups.setdefault(r.region, []).append(r.ping)
    return {c: sum(p) / len(p) for c, p in groups.items()}


# ------------------------------------------------------------------ system values (tab Statistik → System)
SYS_COLUMNS = ("gpu_temp", "gpu_temp_max", "gpu_hot_max", "cpu_temp", "cpu_temp_max", "gpu_load", "gpu_power",
               "vram_used_max", "throttle_s", "core_max", "cpu_power", "cpu_throttle_s", "fps", "fps_low")
SYS_PEAKS = ("gpu_temp_max", "gpu_hot_max", "gpu_mem_max", "cpu_temp_max", "gpu_power_max", "cpu_power_max",
             "vram_used_max", "ram_used_max", "throttle_s", "cpu_throttle_s")
SYS_SUMS = ("throttle_s", "cpu_throttle_s")      # added up over a group, not averaged
SYS_LOWS = ("fps_low",)         # the worst value is the lowest one (highest values: the round with the lowest)


def _sys_key(r, by: str):
    if by == "map":
        return r.map
    if by == "killer":
        return r.killer if r.role == "killer" and r.killer and not r.custom else None
    return _wait_key(r, by)


def sys_by(rounds, by: str) -> list:
    """[(key, rounds, {column: value})] for rounds with system values: averages of the round averages,
    maxima of the round maxima. Maps/killers hottest GPU first, weekday and hour blocks in calendar order."""
    groups = {}
    for r in rounds:
        if r.sys:
            key = _sys_key(r, by)
            if key is not None:
                groups.setdefault(key, []).append(r.sys)
    rows = []
    for key, items in groups.items():
        vals = {}
        for col in SYS_COLUMNS:
            got = [s[col] for s in items if col in s]
            if got:
                vals[col] = max(got) if col.endswith("_max") else sum(got) if col in SYS_SUMS else \
                    sum(got) / len(got)
        rows.append((key, len(items), vals))
    if by in ("map", "killer"):
        return sorted(rows, key=lambda row: (-row[2].get("gpu_temp", -1), -row[2].get("cpu_temp", -1), str(row[0])))
    return sorted(rows, key=lambda row: row[0])


def sys_peaks(rounds) -> list:
    """[(value key, highest value, round)] – the hottest / most loaded round of the selection."""
    out = []
    for key in SYS_PEAKS:
        best = max((r for r in rounds if r.sys and key in r.sys), key=lambda r: r.sys[key], default=None)
        if best is not None and (key not in SYS_SUMS or best.sys[key] > 0):      # "0 s throttled" is no record
            out.append((key, best.sys[key], best))
    for key in SYS_LOWS:
        worst = min((r for r in rounds if r.sys and key in r.sys), key=lambda r: r.sys[key], default=None)
        if worst is not None:
            out.append((key, worst.sys[key], worst))
    return out


def sys_average(rounds) -> dict:
    """Average of the round averages over the selection: {"gpu_temp": …, "cpu_temp": …, "n": rounds}."""
    items = [r.sys for r in rounds if r.sys]
    out = {"n": len(items)}
    for col in ("gpu_temp", "cpu_temp", "gpu_load", "cpu_load", "gpu_power", "core_max", "cpu_power", "fps", "fps_low"):
        got = [s[col] for s in items if col in s]
        if got:
            out[col] = sum(got) / len(got)
    throttled = [s["throttle_s"] for s in items if s.get("throttle_s")]
    out["throttle_rounds"], out["throttle_s"] = len(throttled), sum(throttled)
    known = [s["cpu_throttle_s"] for s in items if "cpu_throttle_s" in s]      # rounds with HWiNFO
    out["cpu_known"] = len(known)
    out["cpu_throttle_rounds"], out["cpu_throttle_s"] = sum(1 for v in known if v), sum(known)
    return out


def sys_trend(rounds, unit: str) -> list:
    """GPU temperature over time: [(bucket start, [round averages], [round maxima], [hot spot maxima])] per
    hour / day / week, empty buckets included (honest time axis), the newest MAX_BUCKETS. A slow rise over
    weeks points at dust, thermal paste or a fan."""
    from .official import MAX_BUCKETS, _next_bucket, bucket_start
    groups = {}
    for r in rounds:
        if r.sys and "gpu_temp" in r.sys:
            g = groups.setdefault(bucket_start(r.t, unit), ([], [], []))
            g[0].append(r.sys["gpu_temp"])
            g[1].append(r.sys.get("gpu_temp_max", r.sys["gpu_temp"]))
            if "gpu_hot_max" in r.sys:
                g[2].append(r.sys["gpu_hot_max"])
    if not groups:
        return []
    out, b, last = [], min(groups), max(groups)
    while b <= last:
        out.append((b, *groups.get(b, ([], [], []))))
        b = _next_bucket(b, unit)
    return out[-MAX_BUCKETS:]
