"""Streaks and records (1.7, user's pick 6): longest and current 4K streak, longest and current escape streak,
best week as killer / survivor, most rounds in a day, longest session, longest round.

Pure logic on the rounds the statistics selected and their official matches; the sub-tab "Rekorde" shows the
result as tiles (dashboard.Tile).
"""
from __future__ import annotations

import datetime
import time
from dataclasses import dataclass

from . import official
from .dashboard import Tile, play_time
from .i18n import _
from .textnorm import fmt_duration

WEEK_MIN = 5              # a week needs this many rounds with a result to be "the best week"
SESSION_GAP = 45 * 60     # rounds further apart than this (end -> next start) are two sessions


@dataclass
class Streak:
    best: int = 0
    best_end: float = 0.0     # start of the last round of the best streak
    current: int = 0          # the run the newest rounds are on
    rounds: int = 0           # rounds with a known result


def streak(items) -> Streak:
    """``items``: [(start, hit)] in any order; ``hit`` None = result unknown, neither extends nor breaks a run."""
    s = Streak()
    run = 0
    for t, hit in sorted((i for i in items if i[1] is not None), key=lambda i: i[0]):
        s.rounds += 1
        run = run + 1 if hit else 0
        if run > s.best:
            s.best, s.best_end = run, t
    s.current = run
    return s


def _day(t: float) -> float:
    return datetime.datetime.fromtimestamp(t).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def week_start(t: float) -> float:
    """Midnight of the Monday of the week ``t`` lies in (local time)."""
    d = datetime.datetime.fromtimestamp(t).replace(hour=0, minute=0, second=0, microsecond=0)
    return (d - datetime.timedelta(days=d.weekday())).timestamp()


def best_week(items, minimum=WEEK_MIN):
    """``items``: [(start, value)] -> (week start, mean, n) of the week with the highest mean among the weeks with
    at least ``minimum`` values; None without such a week. Ties go to the newer week."""
    weeks = {}
    for t, v in items:
        if v is not None:
            weeks.setdefault(week_start(t), []).append(float(v))
    best = None
    for start, vals in weeks.items():
        if len(vals) < minimum:
            continue
        mean = sum(vals) / len(vals)
        if best is None or mean > best[1] or (mean == best[1] and start > best[0]):
            best = (start, mean, len(vals))
    return best


def busiest_day(rounds):
    """(day start, rounds, play seconds) of the day with the most rounds; None without rounds."""
    days = {}
    for r in rounds:
        d = days.setdefault(_day(r.t), [0, 0.0])
        d[0] += 1
        d[1] += r.seconds
    if not days:
        return None
    start = max(days, key=lambda k: (days[k][0], k))
    return start, days[start][0], days[start][1]


def sessions(rounds, gap=SESSION_GAP) -> list:
    """[(first start, last end, rounds)]: rounds that follow each other within ``gap`` form a session."""
    out = []
    for r in sorted(rounds, key=lambda r: r.t):
        end = r.t + r.seconds
        if out and r.t - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], end), out[-1][2] + 1)
        else:
            out.append((r.t, end, 1))
    return out


def longest_session(rounds, gap=SESSION_GAP):
    """The session that lasted longest (first banner to last end): (start, end, rounds) or None."""
    ss = sessions(rounds, gap)
    return max(ss, key=lambda s: (s[1] - s[0], s[0])) if ss else None


def longest_round(rounds):
    return max(rounds, key=lambda r: (r.seconds, r.t)) if rounds else None


def _date(t: float) -> str:
    return time.strftime("%d.%m.%y", time.localtime(t))


def _streak_tile(title: str, s: Streak, empty: str) -> Tile:
    if not s.rounds:
        return Tile(title, sub=empty)
    sub = _("aktuell {n}", n=s.current)
    if s.best:
        sub += " · " + _("zuletzt {date}", date=_date(s.best_end))
    sub += " · " + _("{n} Runden", n=s.rounds)
    return Tile(title, str(s.best), sub)


def tiles(rounds, pairs) -> list:
    """The tiles of the sub-tab "Rekorde" for the selected ``rounds`` and their official ``pairs``."""
    kills = [(r.t, official.kills(m)) for r, m in pairs]
    esc = [(r.t, official.escaped(m)) for r, m in pairs]
    out = [_streak_tile(_("4K-Serie"), streak([(t, None if k is None else k == 4) for t, k in kills]),
                        _("keine Killer-Runden mit Stats-Daten")),
           _streak_tile(_("Entkommen-Serie"), streak(esc), _("keine Survivor-Runden mit Stats-Daten"))]
    bw = best_week(kills)
    out.append(Tile(_("Beste Woche als Killer"), _("Ø {kills} Kills", kills=f"{bw[1]:.2f}"),
                    _("ab {date} · {n} Runden", date=_date(bw[0]), n=bw[2]), frac=bw[1] / 4) if bw
               else Tile(_("Beste Woche als Killer"), sub=_("ab {n} Killer-Runden in einer Woche", n=WEEK_MIN)))
    bw = best_week([(t, None if e is None else int(e)) for t, e in esc])
    out.append(Tile(_("Beste Woche als Survivor"), _("{share} entkommen", share=f"{bw[1]:.0%}"),
                    _("ab {date} · {n} Runden", date=_date(bw[0]), n=bw[2]), frac=bw[1]) if bw
               else Tile(_("Beste Woche als Survivor"), sub=_("ab {n} Survivor-Runden in einer Woche", n=WEEK_MIN)))
    day = busiest_day(rounds)
    if day:
        out.append(Tile(_("Meiste Runden an einem Tag"), str(day[1]),
                        _date(day[0]) + " · " + _("{time} gespielt", time=play_time(day[2]))))
    ses = longest_session(rounds)
    if ses:
        out.append(Tile(_("Längste Sitzung"), play_time(ses[1] - ses[0]),
                        _date(ses[0]) + " · " + _("{n} Runden", n=ses[2])))
    r = longest_round(rounds)
    if r is not None:
        out.append(Tile(_("Längste Runde"), fmt_duration(r.seconds), f"{r.map} · {_date(r.t)}"))
    return out
