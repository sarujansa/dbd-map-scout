"""Dashboard of the statistics page (since 1.58, user's wish): what the filters selected, as tiles and two charts.

Pure logic (no Qt): ``build()`` turns the selected rounds and their official matches into the data the window draws
(qt_window.DashboardView): key figures, maps by rounds with their results, and killer × map (average kills).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import history, official
from .i18n import _
from .textnorm import fmt_duration

MAPS_SHOWN = 10            # map bars: the most played
MATRIX_KILLERS = 8         # heatmap columns: the most played killers (with official data)
MATRIX_MAPS = 10           # heatmap rows: the maps most played as killer
MATRIX_MIN = 2             # a cell needs this many rounds with a result, else it stays empty (one round says little)


@dataclass
class Tile:
    title: str
    value: str = "–"
    sub: str = ""
    frac: float | None = None          # bar below the value (0..1), None = no bar
    colour: object = None              # value in this colour (None = text colour)


@dataclass
class Dashboard:
    tiles: list = field(default_factory=list)
    maps: list = field(default_factory=list)          # [(map, rounds, result text)] most played first
    maps_max: int = 1
    rows: list = field(default_factory=list)          # heatmap rows (maps)
    columns: list = field(default_factory=list)       # heatmap columns (killers, display names)
    cells: dict = field(default_factory=dict)         # (map, killer) -> (average kills, rounds)
    empty: str = ""                                   # text instead of everything (no rounds)


def _bp(n) -> str:
    """Bloodpoints short: 215k, 3.45 Mio."""
    if n >= 1e6:
        return _("{n} Mio.", n=f"{n / 1e6:.2f}")
    return f"{n / 1000:.0f}k" if n >= 1000 else f"{n:.0f}"


def play_time(seconds: float) -> str:
    """Play time of many rounds: "29.5 h" from an hour on (h:mm:ss reads like a clock time there)."""
    if seconds < 3600:
        return fmt_duration(seconds)
    return f"{seconds / 3600:.1f} h"


@dataclass
class BpRate:
    """1.6.3 (user: farming evaluation): bloodpoints of the rounds tied to a match with BP."""
    rounds: int = 0
    bp: int = 0
    play_s: float = 0.0          # match length (the stats page's, else banner to end)
    wait_s: float = 0.0          # search time in the lobby (rounds without a known wait: the average of the others)

    @property
    def per_round(self):
        return self.bp / self.rounds if self.rounds else None

    @property
    def per_hour(self):
        return self.bp * 3600 / self.play_s if self.play_s > 0 else None

    @property
    def per_hour_waiting(self):
        """Per hour of playing and searching together – what an evening of farming really earns."""
        total = self.play_s + self.wait_s
        return self.bp * 3600 / total if total > 0 else None


def bp_rate(pairs) -> BpRate:
    """``pairs``: [(round, official match)]; only matches with bloodpoints count."""
    got = [(r, m) for r, m in pairs if m.bp > 0]
    out = BpRate(rounds=len(got), bp=sum(m.bp for _r, m in got))
    out.play_s = sum(m.seconds if m.seconds > 0 else r.seconds for r, m in got)
    waits = [r.wait for r, _m in got if r.wait is not None]
    avg_wait = sum(waits) / len(waits) if waits else 0.0
    out.wait_s = sum(r.wait if r.wait is not None else avg_wait for r, _m in got)
    return out


def bp_rows(pairs, killer_label=lambda k: k) -> list:
    """[(group, BpRate)]: all, survivor, killer, then each killer by rounds – the table "Bloodpoints"."""
    rows = [(_("Alle"), bp_rate(pairs))]
    for role, label in (("survivor", _("Survivor")), ("killer", _("Killer"))):
        sub = [(r, m) for r, m in pairs if r.role == role]
        if sub:
            rows.append((label, bp_rate(sub)))
    killers = {}
    for r, m in pairs:
        if r.role == "killer" and r.killer:
            killers.setdefault(r.killer, []).append((r, m))
    for k, sub in sorted(killers.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows.append(("   " + killer_label(k), bp_rate(sub)))
    return [(g, b) for g, b in rows if b.rounds]


def tiles(rounds, pairs) -> list:
    s = history.summary(rounds)
    o = official.summary([m for _r, m in pairs])
    ws = history.wait_summary(rounds)
    out = [Tile(_("Runden"), str(s["count"]), _("{time} gespielt", time=play_time(s["total"])))]
    if o["killer"]:
        sub = _("4K: {n} von {total}", n=o["four"], total=o["killer"])
        if o["abandons"]:
            sub += " · " + _("{n}× Abandon", n=o["abandons"])
        out.append(Tile(_("Ø Kills"), f"{o['kills']:.2f}", sub, frac=o["kills"] / 4))
    else:
        out.append(Tile(_("Ø Kills"), sub=_("keine Killer-Runden mit Stats-Daten")))
    if o["survivor"]:
        out.append(Tile(_("Entkommen"), f"{o['escaped']:.0%}", _("{n} Survivor-Runden", n=o["survivor"]),
                        frac=o["escaped"]))
    else:
        out.append(Tile(_("Entkommen"), sub=_("keine Survivor-Runden mit Stats-Daten")))
    out.append(Tile(_("Ø Rundendauer"), fmt_duration(s["avg"]) if s["count"] else "–"))
    out.append(Tile(_("Ø Wartezeit"), fmt_duration(ws["avg"]) if ws["count"] else "–",
                    _("Median {time}", time=fmt_duration(ws["median"])) if ws["count"] else ""))
    out.append(Tile(_("Ø Bloodpoints"), _bp(o["bp"] / o["bp_matches"]) if o["bp_matches"] else "–",
                    _("{n} Matches", n=o["bp_matches"]) if o["bp_matches"] else ""))
    rate = bp_rate(pairs)                                       # 1.6.3: what farming earns
    out.append(Tile(_("Bloodpoints pro Stunde"), _bp(rate.per_hour) if rate.per_hour else "–",
                    _("mit Wartezeit {bp}", bp=_bp(rate.per_hour_waiting)) if rate.per_hour_waiting else ""))
    return out


def map_rows(rounds, pairs, limit: int = MAPS_SHOWN) -> list:
    """[(map, rounds, results)] of the most played maps; results: Ø kills as killer · escaped as survivor."""
    res = official.results(pairs, lambda r: (r.map, r.role))
    rows = []
    for name, n, _avg, _longest in history.per_map(rounds)[:limit]:
        parts = []
        k = official.mean(res.get((name, "killer"), {}).get("kills"))
        e = official.mean(res.get((name, "survivor"), {}).get("escaped"))
        if k is not None:
            parts.append(_("Ø {kills} Kills", kills=f"{k:.1f}"))
        if e is not None:
            parts.append(_("{share} entkommen", share=f"{e:.0%}"))
        rows.append((name, n, " · ".join(parts)))
    return rows


def short_killer(name: str) -> str:
    """Column heading of the heatmap: "The Nurse" -> "Nurse" (the columns are narrow)."""
    return name[4:] if name.startswith("The ") else name


def matrix(pairs, label=lambda k: k):
    """Map × killer, average kills from the stats page: (maps, killers, {(map, killer): (avg, n)}). Only killer
    rounds with a known result; rows/columns = the most played, cells with fewer than MATRIX_MIN rounds left out."""
    res = official.results([(r, m) for r, m in pairs if r.role == "killer" and r.killer], lambda r: (r.map, r.killer))
    per_killer, per_map = {}, {}
    for (m, k), g in res.items():
        n = len(g["kills"])
        per_killer[k] = per_killer.get(k, 0) + n
        per_map[m] = per_map.get(m, 0) + n
    killers = [k for k, n in sorted(per_killer.items(), key=lambda kv: (-kv[1], kv[0]))[:MATRIX_KILLERS] if n]
    maps = [m for m, n in sorted(per_map.items(), key=lambda kv: (-kv[1], kv[0]))[:MATRIX_MAPS] if n]
    cells = {}
    for (m, k), g in res.items():
        if k in killers and m in maps and len(g["kills"]) >= MATRIX_MIN:
            cells[(m, label(k))] = (sum(g["kills"]) / len(g["kills"]), len(g["kills"]))
    rows = [m for m in maps if any((m, label(k)) in cells for k in killers)]          # no empty rows/columns
    cols = [label(k) for k in killers if any((m, label(k)) in cells for m in maps)]
    return rows, cols, cells


def build(rounds, pairs, killer_label=lambda k: k) -> Dashboard:
    """``rounds``: the rounds the filters selected; ``pairs``: [(round, official match)] of those."""
    if not rounds:
        return Dashboard(empty=_("Keine Runden in dieser Auswahl."))
    d = Dashboard(tiles=tiles(rounds, pairs), maps=map_rows(rounds, pairs))
    d.maps_max = max((n for _m, n, _r in d.maps), default=1)
    d.rows, d.columns, d.cells = matrix(pairs, killer_label)
    return d
