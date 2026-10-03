"""Round history (dbdmapscout/history.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import history as h  # noqa: E402


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
