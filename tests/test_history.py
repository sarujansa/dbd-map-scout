"""Round history (fogscout/history.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import history as h  # noqa: E402


def rnd(m, s, t=0.0, region=""):
    return h.Round(t=t, seconds=s, map_id=m.lower(), map=m, region=region, source="auto")


def test_short_rounds_do_not_count():
    assert not h.should_record(12) and not h.should_record(59.9) and h.should_record(60)


def test_file_round_trip(tmp_path):
    p = str(tmp_path / h.FILE)
    assert h.load(p) == []                                           # no file yet
    h.append(p, rnd("Coal Tower", 600, 1.0, "eu-central-1"))
    h.append(p, rnd("Léry's Memorial Institute", 420, 2.0))
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("kaputt\n{}\n")                                     # broken lines are skipped
    got = h.load(p)
    assert [r.map for r in got] == ["Coal Tower", "Léry's Memorial Institute"]
    assert got[0].region == "eu-central-1" and got[0].seconds == 600
    h.clear(p)
    assert h.load(p) == [] and not os.path.exists(p)


def test_statistics():
    rs = [rnd("Coal Tower", 600), rnd("Coal Tower", 300), rnd("Badham Preschool II", 900)]
    assert h.summary(rs) == {"count": 3, "total": 1800, "avg": 600}
    assert h.summary([]) == {"count": 0, "total": 0, "avg": 0.0}
    assert h.per_map(rs) == [("Coal Tower", 2, 450, 600), ("Badham Preschool II", 1, 900, 900)]


def test_file_is_tidied(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "KEEP", 10)
    p = str(tmp_path / h.FILE)
    for i in range(30):
        h.append(p, rnd("Coal Tower", 100 + i, float(i)))
    got = h.load(p)
    assert len(got) <= 30 and got[-1].seconds == 129                # newest kept
    assert len(got) >= 10


def test_periods_are_calendar_based():
    import datetime
    now = datetime.datetime(2026, 9, 30, 15, 30).timestamp()            # a Wednesday
    ts = lambda *a: datetime.datetime(*a).timestamp()                   # noqa: E731
    assert h.period_start("all", now) is None
    assert h.period_start("day", now) == ts(2026, 9, 30)
    assert h.period_start("week", now) == ts(2026, 9, 28)              # Monday
    assert h.period_start("month", now) == ts(2026, 9, 1)
    assert h.period_start("year", now) == ts(2026, 1, 1)


def test_select_and_per_region():
    rs = [rnd("A", 100, 10, "eu-central-1"), rnd("B", 300, 20, "eu-central-1"), rnd("C", 200, 30, "eu-west-2"),
          rnd("D", 400, 40)]
    assert [r.map for r in h.select(rs, since=25)] == ["C", "D"]
    assert [r.map for r in h.select(rs, region="eu-central-1")] == ["A", "B"]
    assert [r.map for r in h.select(rs, region=h.NO_REGION)] == ["D"]
    assert h.regions_used(rs) == ["eu-central-1", "eu-west-2"]
    assert h.per_region(rs) == [("eu-central-1", 2, 200, 0.5), ("eu-west-2", 1, 200, 0.25),
                                (h.NO_REGION, 1, 400, 0.25)]
    assert h.per_region([]) == []


def test_wait_and_role_round_trip(tmp_path):
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=1.0, seconds=600, map_id="a", map="A", wait=125.0, role="killer"))
    h.append(p, h.Round(t=2.0, seconds=600, map_id="b", map="B", custom=True))
    with open(p, "a", encoding="utf-8") as fh:
        fh.write('{"t": 3, "seconds": 70, "map_id": "c", "role": "hacker", "wait": -5}\n')   # nonsense is dropped
    a, b, c = h.load(p)
    assert (a.wait, a.role, a.custom) == (125.0, "killer", False)
    assert (b.wait, b.role, b.custom) == (None, "", True)
    assert (c.wait, c.role) == (None, "")


def test_role_filter_and_waiting_times():
    import datetime
    ts = lambda *a: datetime.datetime(*a).timestamp()                   # noqa: E731
    rs = [h.Round(ts(2026, 9, 28, 20, 5), 600, "a", "A", "eu-central-1", wait=60, role="killer"),      # Monday
          h.Round(ts(2026, 9, 28, 21, 0), 600, "a", "A", "eu-west-2", wait=180, role="killer"),
          h.Round(ts(2026, 9, 29, 9, 0), 600, "a", "A", "eu-central-1", wait=30, role="survivor"),        # Tuesday
          h.Round(ts(2026, 9, 29, 10, 0), 600, "a", "A", custom=True, role="killer"),
          h.Round(ts(2026, 9, 29, 11, 0), 600, "a", "A", role="survivor")]                              # search not seen
    assert len(h.select(rs, role="killer")) == 2 and len(h.select(rs, role="custom")) == 1
    assert len(h.select(rs, role="survivor")) == 2 and len(h.select(rs)) == 5
    assert h.wait_summary(rs) == {"count": 3, "avg": 90.0, "median": 60, "min": 30, "max": 180}
    assert h.wait_summary([])["count"] == 0
    assert h.wait_by(rs, "weekday") == [(0, 2, 120.0, 60), (1, 1, 30.0, 30)]
    assert h.wait_by(rs, "hour") == [(9, 1, 30.0, 30), (18, 1, 60.0, 60), (21, 1, 180.0, 180)]
    assert h.wait_by(rs, "region") == [("eu-central-1", 2, 45.0, 30), ("eu-west-2", 1, 180.0, 180)]


def test_role_can_be_corrected(tmp_path):
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=100.5, seconds=600, map_id="a", map="A", wait=90.0, role="survivor"))
    h.append(p, h.Round(t=200.25, seconds=600, map_id="b", map="B", role="killer"))
    assert h.set_role(p, 100.5, "killer").map == "A"
    assert [r.role for r in h.load(p)] == ["killer", "killer"]
    h.set_role(p, 100.5, "custom")
    a = h.load(p)[0]
    assert (a.custom, a.role, a.wait) == (True, "", 90.0)             # wait kept: undo-able, ignored while custom
    assert h.wait_summary(h.load(p))["count"] == 0
    h.set_role(p, 100.5, "survivor")
    assert (h.load(p)[0].custom, h.load(p)[0].role) == (False, "survivor")
    assert h.set_role(p, 999.0, "killer") is None
    import pytest
    with pytest.raises(ValueError):
        h.set_role(p, 100.5, "hacker")



def test_a_round_can_be_deleted(tmp_path):
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=100.5, seconds=600, map_id="a", map="A"))
    h.append(p, h.Round(t=200.25, seconds=300, map_id="b", map="B"))
    h.append_lost(p, 150.0, "C", "banner")
    assert h.delete(p, 200.25).map == "B"
    assert [r.map for r in h.load(p)] == ["A"] and len(h.load_lost(p)) == 1     # lost lines stay
    assert h.delete(p, 999.0) is None
def test_ping_per_round_and_region(tmp_path):
    assert h.median([30, None, 10, 20]) == 20 and h.median([10, 20]) == 15 and h.median([]) is None
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=1.0, seconds=600, map_id="a", map="A", region="eu-central-1", ping=20.0))
    h.append(p, h.Round(t=2.0, seconds=600, map_id="a", map="A", region="eu-central-1", ping=30.0))
    h.append(p, h.Round(t=3.0, seconds=600, map_id="a", map="A", region="eu-west-2"))               # no ping
    rs = h.load(p)
    assert [r.ping for r in rs] == [20.0, 30.0, None]
    assert h.ping_by_region(rs) == {"eu-central-1": 25.0}


def test_lost_rounds_are_kept_apart(tmp_path, monkeypatch):
    p = str(tmp_path / h.FILE)
    h.append(p, rnd("Coal Tower", 600, 1.0))
    h.append_lost(p, 2.0, "Badham Preschool I", "banner")
    h.append(p, rnd("Hawkins", 700, 3.0))
    h.append_lost(p, 4.0, "Ormond", "quit")
    assert [r.map for r in h.load(p)] == ["Coal Tower", "Hawkins"]            # not counted as rounds
    assert h.load_lost(p) == [(2.0, "Badham Preschool I", "banner"), (4.0, "Ormond", "quit")]
    h.set_role(p, 1.0, "killer")                                               # rewriting keeps them
    assert len(h.load_lost(p)) == 2 and h.load(p)[0].role == "killer"
    monkeypatch.setattr(h, "KEEP", 1)                                          # tidy: old lost lines go too
    import os
    monkeypatch.setattr(os.path, "getsize", lambda _p: 10 ** 9)
    h._tidy(p)
    assert [r.map for r in h.load(p)] == ["Hawkins"] and h.load_lost(p) == [(4.0, "Ormond", "quit")]


def test_killer_per_round(tmp_path):
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=1.0, seconds=600, map_id="a", map="A", role="killer", killer="The Nurse"))
    h.append(p, h.Round(t=2.0, seconds=300, map_id="b", map="B", role="killer", killer="The Nurse"))
    h.append(p, h.Round(t=3.0, seconds=900, map_id="b", map="B", role="killer", killer="The Hillbilly"))
    h.append(p, h.Round(t=4.0, seconds=500, map_id="b", map="B", role="killer", killer="The Hillbilly"))
    h.append(p, h.Round(t=5.0, seconds=700, map_id="c", map="C", role="survivor"))
    rs = h.load(p)
    assert [r.killer for r in rs] == ["The Nurse", "The Nurse", "The Hillbilly", "The Hillbilly", ""]
    assert [r.map for r in h.select(rs, killer="The Nurse")] == ["A", "B"]
    assert h.killers_used(rs) == ["The Hillbilly", "The Nurse"]                    # tie: by name
    assert h.per_killer(rs) == [("The Hillbilly", 2, 700.0, "B"), ("The Nurse", 2, 450.0, "A")]
    h.set_role(p, 1.0, "survivor")                                             # corrected: no killer round any more
    rs = h.load(p)
    assert [r.map for r in h.select(rs, killer="The Nurse")] == ["B"] and rs[0].killer == "The Nurse"   # undo-able
    assert h.select(rs, role="survivor", killer="The Nurse") == []


def test_killer_of_one_round_can_be_set(tmp_path):
    """A round counted as survivor has no killer name – setting one makes it a killer round with that killer."""
    p = str(tmp_path / h.FILE)
    h.append(p, h.Round(t=1.0, seconds=600, map_id="a", map="A", wait=90.0, role="survivor"))
    h.append(p, h.Round(t=2.0, seconds=300, map_id="b", map="B", custom=True))
    assert h.set_killer(p, 1.0, "The Nurse").map == "A"
    a = h.load(p)[0]
    assert (a.role, a.killer, a.custom, a.wait) == ("killer", "The Nurse", False, 90.0)
    assert h.per_killer(h.load(p)) == [("The Nurse", 1, 600.0, "A")]
    h.set_killer(p, 2.0, "The Oni")                                            # custom game -> killer round
    assert [r.map for r in h.select(h.load(p), killer="The Oni")] == ["B"]
    assert h.set_killer(p, 9.0, "The Oni") is None
    import pytest
    with pytest.raises(ValueError):
        h.set_killer(p, 1.0, "")


def test_roles_per_map():
    rs = [h.Round(1, 600, "a", "Coal Tower", role="killer"), h.Round(2, 600, "a", "Coal Tower", role="survivor"),
          h.Round(3, 600, "a", "Coal Tower", role="killer"), h.Round(4, 600, "a", "Coal Tower", custom=True),
          h.Round(5, 600, "b", "Ormond")]                                      # role unknown
    assert h.roles_per_map(rs) == {"Coal Tower": (2, 1), "Ormond": (0, 0)}


def test_today_at_a_glance():
    import datetime
    now = datetime.datetime(2026, 10, 2, 20, 0).timestamp()
    yesterday = now - 86400
    rounds = [h.Round(t=now - 3600, seconds=600, map_id="a", map="A", role="killer", killer="The Nurse", wait=120,
                      ping=30),
              h.Round(t=now - 1800, seconds=900, map_id="b", map="B", role="survivor", wait=60, ping=40),
              h.Round(t=now - 900, seconds=300, map_id="b", map="B", custom=True),
              h.Round(t=yesterday, seconds=999, map_id="c", map="C", role="killer", killer="The Hag", wait=999)]
    d = h.today(rounds, now)
    assert d["count"] == 3 and d["total"] == 1800 and (d["killer"], d["survivor"]) == (1, 1)
    assert d["wait"] == 90 and d["top_killer"] == "The Nurse" and d["ping"] == 35
    empty = h.today(rounds[3:], now)
    assert empty["count"] == 0 and empty["wait"] is None and empty["ping"] is None and not empty["top_killer"]


def test_lost_rounds_keep_what_was_known(tmp_path):
    p = str(tmp_path / h.FILE)
    h.append(p, rnd("Coal Tower", 600, 1.0))
    h.append_lost(p, 2.0, "Coal Tower II", "banner", map_id="coal-tower", region="eu-central-1", wait=95.0,
                  role="killer", killer="The Nurse", ping=None, pings=[1, 2])      # unknown keys are dropped
    with open(p, "a", encoding="utf-8") as fh:
        fh.write('{"lost": true, "t": 3.0, "map": "Old Line", "reason": "banner"}\n')   # written before 1.35
    assert h.load_lost(p) == [(2.0, "Coal Tower II", "banner"), (3.0, "Old Line", "banner")]
    a, b = h.load_lost_rounds(p)
    assert (a.t, a.seconds, a.map_id, a.map, a.region, a.wait, a.role, a.killer, a.ping) == \
        (2.0, 0.0, "coal-tower", "Coal Tower II", "eu-central-1", 95.0, "killer", "The Nurse", None)
    assert (b.map_id, b.map, b.role, b.wait) == ("", "Old Line", "", None)
    h.set_role(p, 1.0, "survivor")                         # rewriting the file keeps the lost lines whole
    assert [r.wait for r in h.load_lost_rounds(p)] == [95.0, None]
    assert [r.role for r in h.load(p)] == ["survivor"]


def test_last_days_periods_map_filter_and_csv_export(tmp_path):
    """1.2.16: "Letzte 7/30 Tage" start at midnight 6 / 29 days back; select() takes a map label; export_csv
    writes one row per round with the official result columns."""
    import datetime
    now = datetime.datetime(2026, 10, 16, 15, 30).timestamp()
    assert h.period_start("7d", now) == datetime.datetime(2026, 10, 10).timestamp()
    assert h.period_start("30d", now) == datetime.datetime(2026, 9, 17).timestamp()
    rounds = [h.Round(t=now - i * 3600, seconds=600, map_id="coal", map="Coal Tower" if i % 2 else "Gas Heaven")
              for i in range(4)]
    assert [r.map for r in h.select(rounds, map_label="Coal Tower")] == ["Coal Tower", "Coal Tower"]
    assert len(h.select(rounds, map_label=None)) == 4
    path = tmp_path / "runden.csv"
    n = h.export_csv(str(path), [{"start": "2026-10-16 15:30:00", "map": "Coal Tower", "seconds": 600, "kills": 3,
                                  "escaped": None, "bloodpoints": 25000, "extra": "ignored"}])
    text = path.read_text(encoding="utf-8-sig")
    assert n == 1 and text.splitlines()[0] == ";".join(h.CSV_COLUMNS)
    assert text.splitlines()[1] == "2026-10-16 15:30:00;Coal Tower;600;;;;;;;;3;;25000"


def test_farming_rounds_count_only_in_their_own_filter(tmp_path):
    """1.2.20 (user: rounds without cross-play / on the farming region are farming rounds, not normal ones)."""
    rs = [h.Round(100, 600, "a", "A", "eu-central-1", wait=60, role="killer"),
          h.Round(200, 600, "a", "A", "ap-southeast-1", wait=30, role="killer", farming=True),
          h.Round(300, 600, "a", "A", role="survivor", farming=True),
          h.Round(400, 600, "a", "A", custom=True, farming=True)]
    assert [r.t for r in h.select(rs)] == [100, 400]                       # "all" leaves farming out
    assert [r.t for r in h.select(rs, role="killer")] == [100]
    assert [r.t for r in h.select(rs, role="farming")] == [200, 300]       # custom stays custom
    assert [r.t for r in h.select(rs, role="custom")] == [400]
    assert h.wait_summary(rs)["count"] == 1 and h.roles_per_map(rs) == {"A": (1, 0)}
    assert [h.normal(r) for r in rs] == [True, False, False, False]
    assert "farming" in h.LOST_KEYS and "farming" in h.CSV_COLUMNS
    path = str(tmp_path / "rounds.jsonl")
    for r in rs[:2]:
        h.append(path, r)
    assert [r.farming for r in h.load(path)] == [False, True]
    assert h.set_farming(path, 100, True).farming is True
    assert [r.farming for r in h.load(path)] == [True, True]
    assert h.set_farming(path, 200, False).role == "killer"                # the role stays
    h.append(path, h.Round(t=300, map_id="x", map="X", seconds=400, role="", custom=True))
    r = h.set_farming(path, 300, True)                                     # 1.5.5: farming drops "custom game"
    assert r.farming and not r.custom and [x.t for x in h.select(h.load(path), role="farming")] == [100, 300]
    assert h.set_farming(path, 999, True) is None


def test_bloodpoints_per_round_and_per_hour_with_and_without_waiting():
    """1.6.3 (user: farming evaluation): BP per round, per hour in the match (the page's length, else banner to
    end) and per hour with the search time; rounds without a known wait count with the average of the others."""
    from fogscout import dashboard
    from fogscout.official import Match
    rs = [h.Round(t=1, seconds=500, map_id="a", map="A", role="survivor", wait=60.0),
          h.Round(t=2, seconds=500, map_id="a", map="A", role="killer", killer="The Nurse", wait=None),
          h.Round(t=3, seconds=500, map_id="a", map="A", role="killer", killer="The Nurse", wait=120.0),
          h.Round(t=4, seconds=500, map_id="a", map="A", role="survivor", wait=30.0)]
    ms = [Match(t=0, map="A", seconds=600, bp=30000), Match(t=0, map="A", seconds=0, bp=40000),
          Match(t=0, map="A", seconds=900, bp=50000), Match(t=0, map="A", seconds=600, bp=0)]   # no BP: left out
    b = dashboard.bp_rate(list(zip(rs, ms)))
    assert (b.rounds, b.bp, b.play_s) == (3, 120000, 600 + 500 + 900) and b.per_round == 40000
    assert b.wait_s == 60 + 90 + 120                                    # the unknown wait = mean of 60 and 120
    assert b.per_hour == 120000 * 3600 / 2000 and b.per_hour_waiting == 120000 * 3600 / 2270
    rows = dashboard.bp_rows(list(zip(rs, ms)), lambda k: k[4:])
    assert [g for g, _b in rows] == ["Alle", "Survivor", "Killer", "   Nurse"]
    assert rows[2][1].bp == 90000 and dashboard.bp_rate([]).per_hour is None
    tile = dashboard.tiles(rs, list(zip(rs, ms)))[-1]
    assert tile.title == "Bloodpoints pro Stunde" and tile.value == "216k" and tile.sub.startswith("mit Wartezeit")


def test_the_bloodpoints_dashboard_tiles_and_trend():
    """1.7.1 (user: a small dashboard for the bloodpoints): tiles above the table – total, per round, per hour,
    best round, Ø per role with bars relative to the higher one – and Ø BP per bucket with empty buckets kept."""
    from fogscout import dashboard
    from fogscout.official import Match, bucket_start
    day = 86400
    t0 = bucket_start(1_760_000_000, "day")
    rs = [h.Round(t=t0 + 60, seconds=600, map_id="a", map="Coal Tower", role="killer", wait=60.0),
          h.Round(t=t0 + 2 * day, seconds=600, map_id="b", map="Badham", role="survivor", wait=30.0),
          h.Round(t=t0 + 2 * day + 900, seconds=600, map_id="b", map="Badham", role="survivor", wait=30.0)]
    ms = [Match(t=0, map="Coal Tower", seconds=600, bp=30000), Match(t=0, map="Badham", seconds=600, bp=50000),
          Match(t=0, map="Badham", seconds=600, bp=0)]
    tiles = {t.title: t for t in dashboard.bp_tiles(list(zip(rs, ms)), lambda r: r.upper())}
    assert tiles["Bloodpoints"].value == "80k" and tiles["Bloodpoints"].sub.startswith("2 Runden")
    assert tiles["Ø pro Runde"].value == "40k" and tiles["BP/h im Match"].value == "240k"
    assert tiles["Beste Runde"].value == "50k" and tiles["Beste Runde"].sub.startswith("Badham · ")
    assert tiles["Beste Runde"].sub.endswith("SURVIVOR")
    assert tiles["Ø BP als Killer"].frac == 30000 / 50000 and tiles["Ø BP als Survivor"].frac == 1.0
    assert dashboard.bp_tiles([]) == []
    trend = dashboard.bp_trend(list(zip(rs, ms)), "day")
    assert [(round((b - t0) / day), bps) for b, bps in trend] == [(0, [30000]), (1, []), (2, [50000])]
    assert dashboard.bp_trend([], "day") == []


def test_a_round_after_a_line_cut_off_by_a_crash_is_kept(tmp_path):
    """1.8.38 (QA audit): a crash while writing left the last line without its line break – the next round was
    glued to it and both were lost (and dropped for good by the next rewrite)."""
    path = str(tmp_path / "rounds.jsonl")
    h.append(path, h.Round(t=1.0, seconds=60.0, map_id="a", map="A"))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"t": 2.0, "seconds": 60.0, "map_id": "b", "ma')                # cut off
    h.append(path, h.Round(t=3.0, seconds=60.0, map_id="c", map="C"))
    h.append_lost(path, 4.0, "D", "neues Banner")
    assert [r.t for r in h.load(path)] == [1.0, 3.0]
    assert [d["t"] for d in h._lost_lines(path)] == [4.0]
