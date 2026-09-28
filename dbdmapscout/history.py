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
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rounds[-KEEP:]:
                fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except OSError:
        pass


def load(path: str) -> list:
    """All rounds, oldest first; broken lines are skipped."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    wait = d.get("wait")
                    out.append(Round(t=float(d["t"]), seconds=float(d["seconds"]), map_id=str(d["map_id"]),
                                     map=str(d.get("map") or d["map_id"]), region=str(d.get("region") or ""),
                                     source=str(d.get("source") or ""),
                                     wait=float(wait) if isinstance(wait, (int, float)) and wait >= 0 else None,
                                     role=str(d.get("role") or "") if d.get("role") in ROLES else "",
                                     custom=bool(d.get("custom")),
                                     ping=float(d["ping"]) if isinstance(d.get("ping"), (int, float))
                                     and d["ping"] >= 0 else None))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return []
    return out


def clear(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def summary(rounds) -> dict:
    total = sum(r.seconds for r in rounds)
    return {"count": len(rounds), "total": total, "avg": total / len(rounds) if rounds else 0.0}


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


def select(rounds, since=None, region=None, role="all") -> list:
    """Rounds from ``since`` on; ``region``: None = all, NO_REGION = rounds without a known server;
    ``role``: all | killer | survivor | custom (custom games only)."""
    out = [r for r in rounds if since is None or r.t >= since]
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
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rounds:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    os.replace(tmp, path)
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
