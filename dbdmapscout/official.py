"""Official match data from stats.deadbydaylight.com: kills, escapes and bloodpoints of the rounds (tab Statistik).

The program itself never goes online for this. The user's browser does: the own userscript
``matchexport.user.js`` (installed once in Tampermonkey & co.) saves the page's recent match
history – only the match fields below, no account or login data – as ``dbdmapscout-matches.json``
into the download folder. ``take_downloads()`` reads such files (only with our format marker),
merges them into ``official.jsonl`` (one line per match, keyed by its start time) and deletes
them. Files without the marker are never touched.

The page lists the newest 30 matches only; a new batch that does not reach back to the newest
stored match leaves a gap (stored as its own line, shown in the statistics).

Matches are tied to the rounds of rounds.jsonl by map and start time (``link``). The status
names of the page are not documented: ``classify()`` sorts them by keywords, unknown ones are
shown in the statistics instead of guessed. Pure logic apart from the file handling.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import re
from dataclasses import asdict, dataclass, field

from .textnorm import fold

FILE = "official.jsonl"
PREFIX = "dbdmapscout-matches"          # file name the userscript downloads (browsers may add " (1)")
FORMAT = "dbdmapscout-matches"          # marker inside the file
URL = "https://stats.deadbydaylight.com/match-history"
SCRIPT = "matchexport.user.js"          # next to this module
MAX_FILE = 5_000_000                    # bytes; the page's 30 matches are ~20 kB
MAX_MATCHES = 500                       # per file
KEEP = 5000                             # newest matches kept in official.jsonl
PAGE_LIMIT = 30                         # the page gives the newest 30 matches only
EARLIEST = 1598918400.0                 # 2020-09-01: the page's stats begin here
# banner (rounds.jsonl) minus the page's start: measured +31 … +51 s, median +38 (user's data, Oct 2026)
LINK_TYPICAL = 38.0
LINK_BEFORE = 60.0                      # same map: banner at most this long before the start (clocks) …
LINK_AFTER = 180.0                      # … and this long after it
OTHER_MAP = (0.0, 90.0)                 # other map (detection wrong?): only this close
ROLES = {"VE_Slasher": "killer", "VE_Camper": "survivor"}
MIN_ROUND = 60.0                        # shorter rounds are not stored (history.MIN_SECONDS)

# Status of a survivor as the page names it / its picture (seen Oct 2026): ESCAPED / VE_Escaped,
# SACRIFICED / VE_Sacrificed, DEAD / VE_Killed, VE_SurrenderLoss / VE_SurrenderDraw (abandoned),
# ESCAPED / VE_SurrenderDraw (also abandoned: the page calls some abandons "escaped", a known bug of the
# page – the picture is right), VE_ManuallyLeftMatch (left the match). Lower case substrings; abandoning
# and leaving win when found in the name or the picture, otherwise the name decides (the picture only
# without a name); a name matching two kinds is unknown.
STATUS_KINDS = (("abandoned", ("surrender", "abandon")),
                ("gone", ("leftmatch", "disconnect", "quit")),
                ("escaped", ("escap",)),
                ("dead", ("sacrific", "killed", "dead", "died", "death", "bled", "mori")))


@dataclass
class Player:
    role: str = ""          # killer | survivor | ""
    character: str = ""
    status: str = ""        # status as the page names it (name / id), "" = none
    img: str = ""           # file name of the status picture (without folder and extension)


@dataclass
class Match:
    t: float                # start (unix seconds)
    map: str                # map name as the page shows it
    custom: bool = False
    role: str = ""          # own role: killer | survivor | ""
    character: str = ""     # own character ("The Nurse", "Meg Thomas" – as the page names it)
    seconds: float = 0.0    # own time in the match
    bp: int = 0
    status: str = ""        # own status (survivor)
    img: str = ""
    opp: list = field(default_factory=list)     # [Player]


# ------------------------------------------------------------------ reading the userscript's file
def _text(v, limit=80) -> str:
    return v.strip()[:limit] if isinstance(v, str) else ""


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _status(d) -> tuple:
    """(status, picture name) of a status object as the userscript passes it on."""
    if not isinstance(d, dict):
        return "", ""
    key = ""
    for k in ("name", "status", "id", "key", "type", "label"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            key = v.strip()[:60]
            break
        if isinstance(v, int) and not isinstance(v, bool):
            key = str(v)
            break
    img = d.get("image")
    stem = os.path.splitext(img.replace("\\", "/").rsplit("/", 1)[-1])[0][:60] if isinstance(img, str) else ""
    return key, stem


def _player(d) -> Player:
    if not isinstance(d, dict):
        return Player()
    status, img = _status(d.get("status"))
    return Player(role=ROLES.get(d.get("role"), ""), character=_text(d.get("character"), 60), status=status, img=img)


def _match(d, now):
    if not isinstance(d, dict):
        return None
    t = _num(d.get("start"))
    if t is None or t < EARLIEST or (now is not None and t > now + 86400):
        return None
    me = d.get("player") if isinstance(d.get("player"), dict) else {}
    p = _player(me)
    seconds = _num(me.get("seconds"))
    bp = _num(me.get("bp"))
    opps = d.get("opponents") if isinstance(d.get("opponents"), list) else []
    return Match(t=t, map=_text(d.get("map")), custom=d.get("custom") is True, role=p.role, character=p.character,
                 seconds=max(0.0, seconds) if seconds is not None else 0.0,
                 bp=int(bp) if bp is not None and 0 <= bp < 1e9 else 0,
                 status=p.status, img=p.img, opp=[_player(o) for o in opps[:8]])


def parse(data, now=None):
    """Matches of a file the userscript saved -> ([Match], script version). ValueError: not such a file."""
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("matches"), list):
        raise ValueError("not a DbD Map Scout match file")
    out = [m for m in (_match(d, now) for d in data["matches"][:MAX_MATCHES]) if m is not None]
    script = data.get("script")
    return out, script if isinstance(script, int) and not isinstance(script, bool) else 0


def script_version(path: str) -> int:
    """``@version`` of the bundled userscript (0 = unreadable)."""
    try:
        with open(path, encoding="utf-8") as fh:
            m = re.search(r"^//\s*@version\s+(\d+)", fh.read(4000), re.M)
    except OSError:
        return 0
    return int(m.group(1)) if m else 0


# ------------------------------------------------------------------ official.jsonl
def load(path: str) -> list:
    """All stored matches, oldest first; broken lines and gap lines are skipped."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    if not isinstance(d, dict) or d.get("gap"):
                        continue
                    opp = [Player(**{k: str(o.get(k) or "") for k in ("role", "character", "status", "img")})
                           for o in d.get("opp") or [] if isinstance(o, dict)]
                    out.append(Match(t=float(d["t"]), map=str(d.get("map") or ""), custom=bool(d.get("custom")),
                                     role=str(d.get("role") or ""), character=str(d.get("character") or ""),
                                     seconds=float(d.get("seconds") or 0), bp=int(d.get("bp") or 0),
                                     status=str(d.get("status") or ""), img=str(d.get("img") or ""), opp=opp))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return []
    return sorted(out, key=lambda m: m.t)


def load_gaps(path: str) -> list:
    """[(newest stored match before, oldest match of the next file)]: matches in between may be missing."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    if isinstance(d, dict) and d.get("gap"):
                        out.append((float(d["from"]), float(d["to"])))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        return []
    return out


def _write(path: str, matches, gaps) -> None:
    lines = [(m.t, json.dumps(asdict(m), ensure_ascii=False)) for m in matches] + \
        [(b, json.dumps({"gap": True, "from": a, "to": b})) for a, b in gaps]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for _t, line in sorted(lines, key=lambda x: x[0]):
            fh.write(line + "\n")
    os.replace(tmp, path)


def merge(path: str, matches) -> tuple:
    """Add matches (a match already stored is replaced by the newer copy). -> (new matches, gap or None)."""
    stored = {round(m.t): m for m in load(path)}
    gaps = load_gaps(path)
    newest = max(stored) if stored else None
    new = sum(1 for m in matches if round(m.t) not in stored)
    gap = None
    if newest is not None and len(matches) >= PAGE_LIMIT and min(m.t for m in matches) > newest:
        gap = (float(newest), min(m.t for m in matches))
        gaps.append(gap)
    for m in matches:
        stored[round(m.t)] = m
    kept = sorted(stored.values(), key=lambda m: m.t)[-KEEP:]
    _write(path, kept, [g for g in gaps if kept and g[1] >= kept[0].t])
    return new, gap


def clear(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ------------------------------------------------------------------ download folder
def downloads_dir() -> str:
    """The user's download folder (Windows: known folder "Downloads", wherever it was moved to)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]
            folder = GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(buf)) == 0:
                path = buf.value
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if path:
                    return path
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


def pending(folder: str) -> list:
    """Files of the userscript in ``folder``: dbdmapscout-matches.json, … (1).json, oldest first."""
    try:
        with os.scandir(folder) as it:
            found = [e for e in it if e.name.lower().startswith(PREFIX) and e.name.lower().endswith(".json")
                     and e.is_file()]
    except OSError:
        return []
    return [e.path for e in sorted(found, key=lambda e: (e.stat().st_mtime, e.name))]


@dataclass
class Taken:
    files: int = 0                  # files read and deleted
    matches: int = 0                # matches in them
    new: int = 0                    # … not stored before
    gaps: list = field(default_factory=list)
    script: int = 0                 # lowest userscript version seen
    unreadable: list = field(default_factory=list)   # not (yet) readable: still being written, locked, broken
    foreign: list = field(default_factory=list)      # the name fits, the content is not ours: left alone
    undeleted: list = field(default_factory=list)    # [(path, error)] read, but could not be deleted


def take_downloads(folder: str, store: str, now=None) -> Taken:
    """Read the userscript's files from ``folder`` into ``store`` and delete them."""
    res = Taken()
    for path in pending(folder):
        try:
            if os.path.getsize(path) > MAX_FILE:
                res.foreign.append(path)
                continue
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            res.unreadable.append(path)
            continue
        try:
            matches, script = parse(data, now)
        except ValueError:
            res.foreign.append(path)
            continue
        if matches:
            new, gap = merge(store, matches)
            res.new += new
            if gap:
                res.gaps.append(gap)
        res.files += 1
        res.matches += len(matches)
        res.script = script if not res.script else min(res.script, script)
        try:
            os.remove(path)
        except OSError as e:
            res.undeleted.append((path, str(e)))
    return res


# ------------------------------------------------------------------ evaluation
def classify(status: str, img: str = "") -> str | None:
    """"escaped" | "dead" | "abandoned" | "gone" (left the match) | None (unknown) for a status
    name and the name of its picture."""
    texts = [t.lower() for t in (status, img) if t]
    for kind, words in STATUS_KINDS[:2]:
        if any(w in t for t in texts for w in words):
            return kind
    for t in texts:
        kinds = {kind for kind, words in STATUS_KINDS[2:] if any(w in t for w in words)}
        if kinds:
            return kinds.pop() if len(kinds) == 1 else None
    return None


def survivors(m: Match) -> list:
    return [p for p in m.opp if p.role == "survivor"]


def kills(m: Match):
    """Survivors that died or abandoned in a killer match (an abandon counts as a kill, like the killer's
    result in the game); None: no killer match or a status is unknown."""
    if m.role != "killer" or not survivors(m):
        return None
    kinds = [classify(p.status, p.img) for p in survivors(m)]
    return None if None in kinds else kinds.count("dead") + kinds.count("abandoned")


def abandons(m: Match) -> int:
    """Survivors that abandoned in a killer match."""
    return sum(1 for p in survivors(m) if classify(p.status, p.img) == "abandoned") if m.role == "killer" else 0


def escaped(m: Match):
    """Survivor match: True = escaped, False = died / abandoned / left, None = no survivor match or unknown."""
    if m.role != "survivor":
        return None
    kind = classify(m.status, m.img)
    return None if kind is None else kind == "escaped"


def unknown_statuses(matches) -> dict:
    """{status as named on the page: count} of the statuses classify() does not know."""
    out = {}
    for m in matches:
        players = survivors(m) if m.role == "killer" else [Player(status=m.status, img=m.img)] \
            if m.role == "survivor" else []
        for p in players:
            if classify(p.status, p.img) is None:
                key = " / ".join(x for x in (p.status, p.img) if x) or "–"
                out[key] = out.get(key, 0) + 1
    return out


def map_index(maps) -> dict:
    """{fold(name): map id} over all names, languages and aliases of the catalog's maps, and the
    labels with layout ("Coal Tower II") as rounds.jsonl stores them."""
    out = {}
    for m in maps.values():
        labels = [m.label(v) for v in getattr(m, "variants", None) or {}]
        for name in list(m.names.values()) + list(m.aliases or []) + labels:
            if fold(name):
                out.setdefault(fold(name), m.id)
    return out


def link(rounds, matches, map_id_of) -> tuple:
    """Tie rounds (rounds.jsonl) to official matches by start time; same map first, then the offset
    closest to the usual one.

    -> ({index in rounds: Match}, [(round, Match)] tied although the maps differ). A match is used
    once; an official map the catalog does not know never counts as "different"."""
    order = sorted(range(len(matches)), key=lambda i: matches[i].t)
    times = [matches[i].t for i in order]
    mids = {}
    pairs = []
    for ri, r in enumerate(rounds):
        for mi in order[bisect.bisect_left(times, r.t - LINK_AFTER):bisect.bisect_right(times, r.t + LINK_BEFORE)]:
            m = matches[mi]
            off = r.t - m.t                          # banner minus start
            if m.map not in mids:
                mids[m.map] = map_id_of(m.map)
            same = mids[m.map] is None or mids[m.map] == r.map_id
            if same or OTHER_MAP[0] <= off <= OTHER_MAP[1]:
                pairs.append((not same, abs(off - LINK_TYPICAL), ri, mi))
    tied, used, other = {}, set(), []
    for differs, _dt, ri, mi in sorted(pairs):
        if ri in tied or mi in used:
            continue
        tied[ri] = matches[mi]
        used.add(mi)
        if differs:
            other.append((rounds[ri], matches[mi]))
    return tied, other


def correct_maps(pairs, map_id_of, label_of) -> dict:
    """Rounds tied to a match on another map (the detection was wrong) take the page's map – as layout I:
    since patch 8.6.0 the other layouts exist only in custom games. pairs: [(round, match)];
    -> {id(round): the label as detected}."""
    fixed = {}
    for r, m in pairs:
        mid = map_id_of(m.map)
        if mid and mid != r.map_id:
            fixed[id(r)] = r.map
            r.map_id, r.map = mid, label_of(mid) or m.map
    return fixed


TREND_UNITS = ("hour", "day", "week")
MAX_BUCKETS = 30


def bucket_start(t: float, unit: str) -> float:
    """Start of the hour / day / week (Monday) that ``t`` falls in, local time."""
    import datetime
    d = datetime.datetime.fromtimestamp(t).replace(minute=0, second=0, microsecond=0)
    if unit != "hour":
        d = d.replace(hour=0)
    if unit == "week":
        d -= datetime.timedelta(days=d.weekday())
    return d.timestamp()


def _next_bucket(start: float, unit: str) -> float:
    import datetime
    d = datetime.datetime.fromtimestamp(start)
    d += {"hour": datetime.timedelta(hours=1), "day": datetime.timedelta(days=1),
          "week": datetime.timedelta(days=7)}[unit]
    return bucket_start(d.timestamp() + 1, unit)       # a DST change shifts the clock, not the bucket


def trend(pairs, unit: str) -> list:
    """Kills and escapes over time: [(bucket start, [kills …], [escaped …])] per hour / day / week from the
    first to the last round with a known result, buckets without one included (empty lists) so the time axis
    stays honest; the newest MAX_BUCKETS. pairs: [(round, match)]."""
    groups = {}
    for r, m in pairs:
        k, e = kills(m), escaped(m)
        if k is None and e is None:
            continue
        g = groups.setdefault(bucket_start(r.t, unit), ([], []))
        if k is not None:
            g[0].append(k)
        if e is not None:
            g[1].append(e)
    if not groups:
        return []
    out, b, last = [], min(groups), max(groups)
    while b <= last:
        out.append((b, *groups.get(b, ([], []))))
        b = _next_bucket(b, unit)
    return out[-MAX_BUCKETS:]


def results(pairs, key) -> dict:
    """Known results of rounds tied to a match, grouped by ``key(round)``: {group: {"kills": [...],
    "escaped": [True/False ...], "bp": [...]}} (pairs: [(round, match)])."""
    out = {}
    for r, m in pairs:
        g = out.setdefault(key(r), {"kills": [], "escaped": [], "bp": []})
        k, e = kills(m), escaped(m)
        if k is not None:
            g["kills"].append(k)
        if e is not None:
            g["escaped"].append(e)
        if m.bp > 0:
            g["bp"].append(m.bp)
    return out


def mean(values):
    return sum(values) / len(values) if values else None


def summary(matches) -> dict:
    """Totals for the line above the table."""
    ks = [k for k in (kills(m) for m in matches) if k is not None]
    es = [e for e in (escaped(m) for m in matches) if e is not None]
    bp = [m.bp for m in matches if m.bp > 0]
    return {"killer": len(ks), "kills": mean(ks), "four": ks.count(4),
            "abandons": sum(abandons(m) for m in matches if kills(m) is not None),
            "survivor": len(es), "escaped": mean(es), "bp": sum(bp), "bp_matches": len(bp)}


def end_offset(r, m: Match) -> float:
    """End of the round as the program saw it (banner + length) minus the end of the match on the page
    (start + own time): how late the end of the round was detected."""
    return (r.t + r.seconds) - (m.t + m.seconds)


def rescued_seconds(r, m: Match):
    """Length of a round whose end was never detected, from its banner to the end of the match on the
    page – None if that is shorter than a counted round."""
    seconds = m.t + m.seconds - r.t
    return seconds if seconds >= MIN_ROUND else None


def detection(matches, linked_ids, since=None) -> tuple:
    """How many official matches the program detected: ([detected], [missed]) of the matches since
    ``since`` (the first round the program stored) that were long enough to be a round."""
    seen, missed = [], []
    for m in matches:
        if (since is not None and m.t < since) or m.seconds < MIN_ROUND:
            continue
        (seen if id(m) in linked_ids else missed).append(m)
    return seen, missed


class OpenAfterGame:
    """Open the stats page once DBD was closed after rounds were played (pure logic, testable).

    ``update()`` -> True exactly once per DBD session with at least one recorded round, after the
    game window has been gone for ``GONE`` seconds (not while playing: the browser would take the focus)."""
    GONE = 15.0

    def __init__(self):
        self.rounds = 0
        self._seen = False
        self._gone_since = None

    def round_recorded(self):
        self.rounds += 1

    def update(self, t: float, game_running: bool) -> bool:
        if game_running:
            self._seen, self._gone_since = True, None
            return False
        if not self._seen:
            return False
        if self._gone_since is None:
            self._gone_since = t
        if t - self._gone_since < self.GONE:
            return False
        self._seen = False
        if not self.rounds:
            return False
        self.rounds = 0
        return True
