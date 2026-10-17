"""Streaks and records (dbdmapscout/records.py, 1.7) – pure logic."""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import records  # noqa: E402
from dbdmapscout.history import Round  # noqa: E402
from dbdmapscout.official import Match, Player  # noqa: E402


def _t(day, hour=20, minute=0):
    return datetime.datetime(2026, 3, day, hour, minute).timestamp()


def _killer_match(t, kills):
    stats = ["SACRIFICED"] * kills + ["ESCAPED"] * (4 - kills)
    return Match(t=t - 38, map="Coal Tower", role="killer", seconds=600,
                 opp=[Player(role="survivor", status=s) for s in stats])


def _survivor_match(t, escaped):
    return Match(t=t - 38, map="Coal Tower", role="survivor", seconds=600,
                 status="ESCAPED" if escaped else "SACRIFICED")


def test_streaks_run_in_time_order_and_unknown_results_are_skipped():
    s = records.streak([(3, True), (1, True), (2, True), (4, False), (5, True), (6, None), (7, True)])
    assert (s.best, s.best_end, s.current, s.rounds) == (3, 3, 2, 6)
    assert records.streak([]) == records.Streak()
    assert records.streak([(1, False)]).current == 0


def test_the_best_week_needs_enough_rounds_and_ties_go_to_the_newer_week():
    week1 = [(_t(2) + i, 4) for i in range(5)]                 # Mon 2.3.: five 4Ks
    week2 = [(_t(9) + i, 4) for i in range(5)]                 # Mon 9.3.: five 4Ks too -> newer wins
    week3 = [(_t(16) + i, 4) for i in range(3)]                # too few rounds, even if perfect
    week4 = [(_t(23) + i, 1) for i in range(6)]
    start, mean, n = records.best_week(week1 + week2 + week3 + week4)
    assert (start, mean, n) == (records.week_start(_t(9)), 4.0, 5)
    assert records.best_week(week3) is None and records.best_week([]) is None
    assert records.week_start(_t(4)) == _t(2, 0)               # Wednesday -> Monday midnight


def test_busiest_day_sessions_and_longest_round():
    rs = [Round(t=_t(1, 20), seconds=600, map_id="a", map="A"),
          Round(t=_t(1, 20, 15), seconds=900, map_id="a", map="A"),          # 5 min after the first ended
          Round(t=_t(1, 21, 30), seconds=300, map_id="b", map="B"),          # 60 min gap: a second session
          Round(t=_t(2, 20), seconds=1200, map_id="c", map="C II")]
    assert records.busiest_day(rs) == (_t(1, 0), 3, 1800)
    ses = records.sessions(rs)
    assert [(s[2], round((s[1] - s[0]) / 60)) for s in ses] == [(2, 30), (1, 5), (1, 20)]
    assert records.longest_session(rs) == ses[0]
    assert records.longest_round(rs).map == "C II"
    assert records.busiest_day([]) is None and records.longest_session([]) is None


def test_the_tiles_of_the_records_tab(monkeypatch):
    monkeypatch.setattr(time, "localtime", lambda t=None: time.gmtime(t))
    rs = [Round(t=_t(2, 10) + i * 1800, seconds=600, map_id="a", map="Coal Tower", role="killer") for i in range(6)]
    rs += [Round(t=_t(3, 10) + i * 3600, seconds=700, map_id="a", map="Coal Tower", role="survivor") for i in range(3)]
    ms = [_killer_match(r.t, k) for r, k in zip(rs[:6], (4, 4, 4, 2, 4, 4))]
    ms += [_survivor_match(r.t, e) for r, e in zip(rs[6:], (True, False, True))]
    tiles = {t.title: t for t in records.tiles(rs, list(zip(rs, ms)))}
    assert tiles["4K-Serie"].value == "3" and tiles["4K-Serie"].sub.startswith("aktuell 2 ·")
    assert tiles["Entkommen-Serie"].value == "1" and "3 Runden" in tiles["Entkommen-Serie"].sub
    assert tiles["Beste Woche als Killer"].value == "Ø 3.67 Kills" and "6 Runden" in tiles["Beste Woche als Killer"].sub
    assert tiles["Beste Woche als Survivor"].value == "–"           # three survivor rounds: fewer than WEEK_MIN
    assert tiles["Meiste Runden an einem Tag"].value == "6"
    assert tiles["Längste Sitzung"].sub.endswith("6 Runden")
    assert tiles["Längste Runde"].value == "11:40" and tiles["Längste Runde"].sub.startswith("Coal Tower")
    empty = {t.title: t for t in records.tiles([], [])}
    assert set(empty) == {"4K-Serie", "Entkommen-Serie", "Beste Woche als Killer", "Beste Woche als Survivor"}
    assert empty["4K-Serie"].value == "–"
