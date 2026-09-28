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
                    out.append(Round(t=float(d["t"]), seconds=float(d["seconds"]), map_id=str(d["map_id"]),
                                     map=str(d.get("map") or d["map_id"]), region=str(d.get("region") or ""),
                                     source=str(d.get("source") or "")))
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


def select(rounds, since=None, region=None) -> list:
    """Rounds from ``since`` on; ``region``: None = all, NO_REGION = rounds without a known server."""
    out = [r for r in rounds if since is None or r.t >= since]
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
