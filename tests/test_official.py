"""Official match data (dbdmapscout/official.py) and the userscript that saves it (matchexport.user.js)."""
import json
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import history  # noqa: E402
from dbdmapscout import official as o  # noqa: E402
from dbdmapscout.textnorm import fold  # noqa: E402

T0 = 1791030420.0           # 3 Oct 2026, 12:27 UTC
SCRIPT = os.path.join(os.path.dirname(o.__file__), o.SCRIPT)


def survivor(status, img="", character="Meg Thomas"):
    return {"role": "VE_Camper", "character": character, "status": {"name": status, "image": img} if status or img
            else None}


def entry(t, map_name="Mother's Dwelling", role="VE_Slasher", statuses=("Sacrificed",) * 4, own=None, custom=False):
    return {"start": t, "map": map_name, "custom": custom,
            "player": {"role": role, "character": "The Nurse" if role == "VE_Slasher" else "Dwight Fairfield",
                       "status": own, "seconds": 440, "bp": 241377},
            "opponents": [survivor(s) for s in statuses] if role == "VE_Slasher" else
            [survivor("Escaped"), {"role": "VE_Slasher", "character": "The Hag", "status": None}]}


def export(*entries, script=1):
    return {"format": o.FORMAT, "version": 1, "script": script, "exported": T0 + 3600, "matches": list(entries)}


def write(folder, name, data):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))
    return path


# ------------------------------------------------------------------ reading
def test_parse_keeps_only_the_needed_fields():
    ms, script = o.parse(export(entry(T0), entry(T0 - 600, role="VE_Camper", own={"name": "Escaped"})), now=T0)
    assert script == 1 and len(ms) == 2
    k, s = ms
    assert (k.t, k.map, k.role, k.character, k.seconds, k.bp, k.custom) == (T0, "Mother's Dwelling", "killer",
                                                                            "The Nurse", 440, 241377, False)
    assert [(p.role, p.status) for p in k.opp] == [("survivor", "Sacrificed")] * 4
    assert (s.role, s.status) == ("survivor", "Escaped")
    assert [p.role for p in s.opp] == ["survivor", "killer"]


def test_status_from_the_picture_when_there_is_no_name():
    m, _s = o.parse(export(entry(T0, statuses=())), now=T0)
    m = m[0]
    m2 = o._player({"role": "VE_Camper", "status": {"image": "display/status/StatusIcon_escaped.png"}})
    assert (m2.status, m2.img) == ("", "StatusIcon_escaped") and o.classify(m2.status, m2.img) == "escaped"
    assert o._player({"role": "VE_Camper", "status": {"id": 3}}).status == "3"
    assert m.opp == []


def test_not_our_file_or_broken_entries():
    for bad in ([], {"matches": []}, {"format": "other", "matches": []}, {"format": o.FORMAT, "matches": "x"}):
        with pytest.raises(ValueError):
            o.parse(bad)
    ms, script = o.parse({"format": o.FORMAT, "script": True, "matches": [
        None, {"start": "x"}, {"start": 1000.0}, {"start": T0 + 10 * 86400}, {"start": float("nan")},
        {"start": T0, "map": 5, "player": "x", "opponents": "x"}]}, now=T0)
    assert script == 0 and len(ms) == 1                     # only the last one, with defaults
    assert (ms[0].map, ms[0].role, ms[0].bp, ms[0].opp) == ("", "", 0, [])


def test_bundled_userscript_version():
    assert o.script_version(SCRIPT) >= 1
    with open(SCRIPT, encoding="utf-8") as fh:
        js = fh.read()
    assert f"SCRIPT_VERSION = {o.script_version(SCRIPT)};" in js        # header and code agree
    assert f"'{o.FORMAT}'" in js and f"'{o.PREFIX}.json'" in js
    assert o.script_version("/does/not/exist") == 0


# ------------------------------------------------------------------ status -> result
def test_classify_the_statuses_seen_on_the_page():
    # name / picture as in the user's diagnostics (Oct 2026)
    assert o.classify("ESCAPED", "VE_Escaped") == "escaped"
    assert o.classify("SACRIFICED", "VE_Sacrificed") == o.classify("DEAD", "VE_Killed") == "dead"
    assert o.classify("VE_SurrenderLoss", "VE_SurrenderDraw") == "abandoned"
    assert o.classify("ESCAPED", "VE_SurrenderDraw") == "abandoned"   # the page calls some abandons "escaped"
    assert o.classify("VE_ManuallyLeftMatch", "VE_ManuallyLeftMatch") == "gone"


def test_classify_other_names():
    assert o.classify("BledOut") == o.classify("", "status_mori") == "dead"
    assert o.classify("Abandoned") == "abandoned" and o.classify("Disconnected") == "gone"
    assert o.classify("Escaped", "killed") == "escaped"           # the name decides, the picture only without one
    assert o.classify("EscapedButKilled") is None                 # contradicting: rather unknown than wrong
    assert o.classify("") is None and o.classify("Killer") is None and o.classify("VE_Unknown") is None


def test_kills_and_escapes():
    ms, _s = o.parse(export(entry(T0, statuses=("Sacrificed", "Killed", "Escaped", "Disconnected")),
                            entry(T0 + 1, statuses=("Sacrificed", "VE_SurrenderLoss", "VE_SurrenderLoss", "Dead")),
                            entry(T0 + 2, statuses=("Sacrificed", "VE_Mystery", "Escaped", "Escaped")),
                            entry(T0 + 3, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 4, role="VE_Camper", own={"name": "Sacrificed"}),
                            entry(T0 + 5, role="VE_Camper", own={"name": "ESCAPED", "image": "x/VE_SurrenderDraw.png"}),
                            entry(T0 + 6, role="VE_Camper", own=None)), now=T0)
    assert [o.kills(m) for m in ms] == [2, 4, None, None, None, None, None]
    assert [o.abandons(m) for m in ms] == [0, 2, 0, 0, 0, 0, 0]
    assert [o.escaped(m) for m in ms] == [None, None, None, True, False, False, None]
    assert o.unknown_statuses(ms) == {"VE_Mystery": 1, "–": 1}
    s = o.summary(ms)
    assert (s["killer"], s["kills"], s["four"], s["abandons"], s["survivor"], s["escaped"]) == \
        (2, 3.0, 1, 2, 3, 1 / 3)


def test_results_grouped_by_round():
    ms, _s = o.parse(export(entry(T0), entry(T0 + 1, statuses=("Escaped",) * 4), entry(T0 + 2, map_name="Coal Tower"),
                            entry(T0 + 3, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 4, statuses=("VE_Mystery",) * 4, map_name="Dead Dawg Saloon")), now=T0)
    rounds = [rnd(m.t, "x") for m in ms]
    for r, m in zip(rounds, ms):
        r.map = m.map                                          # the label the program stored
    got = o.results(list(zip(rounds, ms)), lambda r: r.map)
    assert got["Mother's Dwelling"] == {"kills": [4, 0], "escaped": [True], "bp": [241377] * 3}
    assert got["Coal Tower"]["kills"] == [4]
    assert got["Dead Dawg Saloon"] == {"kills": [], "escaped": [], "bp": [241377]}   # result unknown, BP count
    assert o.mean([1, 2, 6]) == 3 and o.mean([]) is None and o.mean(None) is None


# ------------------------------------------------------------------ official.jsonl
def test_merge_replaces_and_finds_gaps(tmp_path):
    p = str(tmp_path / o.FILE)
    first, _s = o.parse(export(*[entry(T0 + i * 600) for i in range(5)]), now=T0 + 10 ** 6)
    assert o.merge(p, first) == (5, None)                     # first import: no gap
    again, _s = o.parse(export(*[entry(T0 + i * 600, map_name="Coal Tower") for i in range(3, 8)]), now=T0 + 10 ** 6)
    assert o.merge(p, again) == (3, None)                     # overlaps: no gap, 3 new
    got = o.load(p)
    assert [m.t for m in got] == [T0 + i * 600 for i in range(8)]
    assert got[3].map == "Coal Tower"                         # the newer copy wins
    full, _s = o.parse(export(*[entry(T0 + 10 ** 5 + i * 600) for i in range(o.PAGE_LIMIT)]), now=T0 + 10 ** 6)
    new, gap = o.merge(p, full)
    assert new == o.PAGE_LIMIT and gap == (T0 + 7 * 600, T0 + 10 ** 5)
    assert o.load_gaps(p) == [gap] and len(o.load(p)) == 8 + o.PAGE_LIMIT
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("kaputt\n{}\n")
    assert len(o.load(p)) == 8 + o.PAGE_LIMIT
    o.clear(p)
    assert o.load(p) == [] and o.load_gaps(p) == []


def test_merge_keeps_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "KEEP", 3)
    p = str(tmp_path / o.FILE)
    ms, _s = o.parse(export(*[entry(T0 + i * 600) for i in range(5)]), now=T0 + 10 ** 6)
    o.merge(p, ms)
    assert [m.t for m in o.load(p)] == [T0 + i * 600 for i in (2, 3, 4)]


# ------------------------------------------------------------------ download folder
def test_take_downloads_reads_ours_and_deletes_only_ours(tmp_path):
    dl, store = tmp_path / "Downloads", str(tmp_path / o.FILE)
    dl.mkdir()
    a = write(dl, "dbdmapscout-matches.json", export(entry(T0), entry(T0 + 600)))
    b = write(dl, "dbdmapscout-matches (1).json", export(entry(T0 + 600), entry(T0 + 1200), script=2))
    foreign = write(dl, "dbdmapscout-matches (2).json", {"something": "else"})
    half = write(dl, "DBDMAPSCOUT-MATCHES (3).json", '{"format": "dbdmapscout-matches", "matc')
    other = write(dl, "other.json", export(entry(T0 + 5000)))
    res = o.take_downloads(str(dl), store, now=T0 + 3600)
    assert (res.files, res.matches, res.new, res.script) == (2, 4, 3, 1)
    assert not os.path.exists(a) and not os.path.exists(b)
    assert os.path.exists(foreign) and os.path.exists(half) and os.path.exists(other)
    assert res.foreign == [foreign] and res.unreadable == [half] and res.undeleted == []
    assert [m.t for m in o.load(store)] == [T0, T0 + 600, T0 + 1200]
    assert o.take_downloads(str(tmp_path / "missing"), store).files == 0


def test_an_odd_file_never_blocks_the_import_of_the_others(tmp_path):
    """1.8.38 (QA audit): a list as role raised TypeError and a deeply nested file RecursionError – neither was
    caught, the file stayed and every later export behind it was stuck (re-read every 20 s)."""
    dl, store = tmp_path / "Downloads", str(tmp_path / o.FILE)
    dl.mkdir()
    odd = dict(entry(T0), player={"role": [], "character": {}, "status": 5, "seconds": "x"})
    mixed = write(dl, "dbdmapscout-matches.json", export(odd, entry(T0 + 600)))
    deep = write(dl, "dbdmapscout-matches (1).json", "[" * 100000 + "]" * 100000)
    later = write(dl, "dbdmapscout-matches (2).json", export(entry(T0 + 1200)))
    os.utime(mixed, (T0, T0)), os.utime(deep, (T0 + 1, T0 + 1)), os.utime(later, (T0 + 2, T0 + 2))
    res = o.take_downloads(str(dl), store, now=T0 + 3600)
    assert res.foreign == [deep] and os.path.exists(deep)                     # not ours: left alone
    assert not os.path.exists(mixed) and not os.path.exists(later)            # read and deleted
    stored = {m.t: m for m in o.load(store)}
    assert set(stored) == {T0, T0 + 600, T0 + 1200} and stored[T0].role == "" and stored[T0].character == ""   # odd fields left empty


def test_take_downloads_skips_huge_files(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "MAX_FILE", 10)
    big = write(tmp_path, "dbdmapscout-matches.json", export(entry(T0)))
    res = o.take_downloads(str(tmp_path), str(tmp_path / o.FILE), now=T0)
    assert res.files == 0 and res.foreign == [big] and os.path.exists(big)


def test_downloads_dir_is_a_path():
    assert os.path.isabs(o.downloads_dir())


# ------------------------------------------------------------------ tying matches to rounds
def rnd(t, map_id):
    return history.Round(t=t, seconds=600, map_id=map_id, map=map_id, source="auto")


def match(t, name):
    return o.Match(t=t, map=name)


def test_bloodpoints():
    ms, _s = o.parse(export(entry(T0), entry(T0 + 1, role="VE_Camper", own={"name": "Escaped"})), now=T0)
    ms[1].bp, ms[1].seconds = 100000, 360
    s = o.summary(ms)
    assert (s["bp"], s["bp_matches"]) == (341377, 2)
    assert (o.summary([])["bp"], o.summary([])["kills"]) == (0, None)


def test_end_offset_and_rescued_length():
    m = o.Match(t=T0, map="Coal Tower", seconds=600)
    r = rnd(T0 + 38, "coal")                                  # banner 38 s after the start, 600 s counted
    assert o.end_offset(r, m) == 38                           # end detected 38 s after the end on the page
    assert o.rescued_seconds(r, m) == 562                     # from the banner to the page's end
    assert o.rescued_seconds(rnd(T0 + 550, "coal"), m) is None   # under a minute: not a round


def test_detection_rate():
    ms = [o.Match(t=T0 + i * 600, map="Coal Tower", seconds=500) for i in range(5)]
    ms[4].seconds = 30                                        # too short to be stored as a round
    seen, missed = o.detection(ms, {id(ms[1]), id(ms[2])}, since=T0 + 300)
    assert seen == [ms[1], ms[2]] and missed == [ms[3]]       # ms[0] is older than the program's first round
    assert o.detection(ms, set())[1] == ms[:4]


def test_map_index_over_all_names_and_aliases():
    maps = {"coal-tower": SimpleNamespace(id="coal-tower", names={"en": "Coal Tower", "de": "Kohlelager"},
                                          aliases=["Kohleturm"]),
            "x": SimpleNamespace(id="x", names={"en": "Mother’s Dwelling"}, aliases=None),
            "gs": SimpleNamespace(id="gs", names={"en": "Groaning Storehouse"}, aliases=[], variants={1: "a", 2: "b"},
                                  label=lambda v: "Groaning Storehouse" + (" II" if v == 2 else ""))}
    idx = o.map_index(maps)
    assert idx[fold("Groaning Storehouse II")] == "gs"          # labels as rounds.jsonl stores them
    assert idx[fold("Kohlelager")] == idx[fold("kohleturm")] == "coal-tower"
    assert idx[fold("Mother's Dwelling")] == "x"                # typographic apostrophe


def test_link_prefers_the_same_map():
    # banner minus start: the user's data says +31 … +51 s
    ids = {"Coal Tower": "coal", "Treatment Theater": "tt"}
    rounds = [rnd(T0 + 20, "coal"), rnd(T0 + 900, "coal"), rnd(T0 + 2000, "coal"), rnd(T0 + 4000, "tt")]
    matches = [match(T0 + 900 - 60, "Treatment Theater"),   # other map, close to round 1 …
               match(T0 + 900 - 150, "Coal Tower"),         # … but the same map 150 s off wins
               match(T0, "Coal Tower"),
               match(T0 + 2000 - 60, "Groaning Storehouse"),  # other map, only one there -> tied, flagged
               match(T0 + 4000 - 400, "Treatment Theater")]   # too far
    ids["Groaning Storehouse"] = "gs"
    tied, other = o.link(rounds, matches, ids.get)
    assert tied == {0: matches[2], 1: matches[1], 2: matches[3]}
    assert other == [(rounds[2], matches[3])]


def test_link_other_map_only_when_close_and_unknown_maps_are_not_flagged():
    rounds = [rnd(T0, "coal"), rnd(T0 + 5000, "coal"), rnd(T0 + 9000, "coal")]
    matches = [match(T0 - 120, "Groaning Storehouse"),        # other map 120 s before the banner: too far
               match(T0 + 5000 - 100, "Brand New Map"),       # unknown map: counts as the same one
               match(T0 + 9000 + 90, "Coal Tower")]           # starts 90 s after the banner: not this round
    tied, other = o.link(rounds, matches, {"Groaning Storehouse": "gs", "Coal Tower": "coal"}.get)
    assert tied == {1: matches[1]} and other == []
    assert o.link([], matches, {}.get) == ({}, []) and o.link(rounds, [], {}.get) == ({}, [])


def test_each_match_and_round_used_once():
    rounds = [rnd(T0, "coal"), rnd(T0 + 30, "coal")]
    matches = [match(T0 - 30, "Coal Tower")]                 # +30 s / +60 s: the first is closer to the usual +38
    tied, _other = o.link(rounds, matches, {"Coal Tower": "coal"}.get)
    assert tied == {0: matches[0]}


# ------------------------------------------------------------------ opening the page after DBD
def test_open_after_game():
    g = o.OpenAfterGame()
    assert not g.update(0, False) and not g.update(100, False)         # DBD never seen
    g.update(200, True)
    g.round_recorded()
    assert not g.update(205, False) and not g.update(205 + g.GONE - 1, False)
    g.update(215, True)                                                  # back (restart, loading): starts over
    assert not g.update(220, False)
    assert g.update(220 + g.GONE, False)                                 # gone long enough: open once
    assert not g.update(400, False)
    g.update(500, True)
    assert not g.update(600, False) and not g.update(700, False)         # no round this time: nothing to fetch


# ------------------------------------------------------------------ the userscript itself (needs node)
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync(process.argv[2], 'utf8');
const answer = fs.readFileSync(process.argv[3], 'utf8');
const api = 'https://account-backend.bhvr.com/player-stats/match-history/games/dbd/providers/bhvr?lang=en&limit=30';
const saved = { xhr: [], fetch: [], cache: [] };
function context(out, store, cache, fetchAnswer) {
  class XHR { open() {} send() {} addEventListener(ev, fn) { this.onload = fn; } }
  const ctx = {
    console: { log() {} }, setTimeout: fn => setTimeout(fn, 0), clearTimeout,
    XMLHttpRequest: XHR,
    sessionStorage: { getItem: () => cache },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } },
    URL: { createObjectURL: b => { out.push(b.text); return 'blob:x'; }, revokeObjectURL() {} },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    document: { body: { appendChild() {} }, addEventListener() {},
                createElement: () => ({ click() {}, remove() {}, style: {} }) },
  };
  if (fetchAnswer) ctx.fetch = async () => ({ clone: () => ({ json: async () => JSON.parse(fetchAnswer) }) });
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  return ctx;
}
function load(ctx, url) {
  const x = new ctx.XMLHttpRequest();
  x.open('GET', url);
  x.send();
  x.responseType = '';
  x.responseText = answer;
  if (x.onload) x.onload();
}
const store = {};
load(context(saved.xhr, store), 'https://stats.deadbydaylight.com/_next/data/x/faq.json');   // other requests: ignored
load(context(saved.xhr, store), api);
const f = context(saved.fetch, {}, null, answer);
f.window.fetch(api);
const cached = JSON.stringify({ clientState: { queries: [{ queryKey: ['stats.match-history'],
                                                           state: { data: JSON.parse(answer) } }] } });
context(saved.cache, {}, cached);
setTimeout(() => {
  load(context(saved.xhr, store), api);       // same matches on the next visit: no second file
  setTimeout(() => process.stdout.write(JSON.stringify(saved)), 20);
}, 20);
"""


def test_userscript_saves_a_file_the_program_reads(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    page_answer = [{
        "matchStat": {"matchStartTime": T0, "map": {"name": "Mother's Dwelling", "image": {"path": "m.png"}},
                      "isCustomMatch": False, "matchId": "secret-match-id"},
        "playerStat": {"playerRole": "VE_Slasher", "characterName": {"name": "The Nurse"}, "playerTimeInMatch": 440,
                       "bloodpointsEarned": 241377, "playerName": "MyOwnName", "postGameStat": {"x": 1}},
        "opponentStat": [{"playerRole": "VE_Camper", "characterName": {"name": "Meg Thomas"},
                          "playerName": "SomeoneElse", "platformId": "765611",
                          "playerStatus": {"name": "Sacrificed", "image": {"path": "display/status/sacrificed.png"},
                                           "details": {"nested": "dropped"}}}] * 4}]
    script_path = tmp_path / "harness.js"
    answer_path = tmp_path / "answer.json"
    script_path.write_text(HARNESS, encoding="utf-8")
    answer_path.write_text(json.dumps(page_answer), encoding="utf-8")
    out = subprocess.run([node, str(script_path), SCRIPT, str(answer_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    saved = json.loads(out.stdout)
    assert len(saved["xhr"]) == 1                            # once; not again for the same matches
    assert len(saved["fetch"]) == 1 and len(saved["cache"]) == 1   # fetch() and the page's cached copy work too
    for secret in ("MyOwnName", "SomeoneElse", "765611", "secret-match-id", "dropped"):
        assert secret not in saved["xhr"][0]                 # only the whitelisted fields leave the page
    ms, script = o.parse(json.loads(saved["xhr"][0]), now=T0)
    assert script == o.script_version(SCRIPT)
    assert len(ms) == 1 and o.kills(ms[0]) == 4 and ms[0].opp[0].img == "sacrificed"


STRUCTURE_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync(process.argv[2], 'utf8');
const answer = fs.readFileSync(process.argv[3], 'utf8');
const api = 'https://account-backend.bhvr.com/player-stats/match-history/games/dbd/providers/bhvr?lang=en&limit=30';
function run(hash, store) {
  const files = [];
  let pending = null;
  class XHR { open() {} send() {} addEventListener(ev, fn) { this.onload = fn; } }
  const ctx = {
    console: { log() {} }, setTimeout: fn => setTimeout(fn, 0), clearTimeout, Date,
    XMLHttpRequest: XHR, location: { hash },
    sessionStorage: { getItem: () => null },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; },
                    removeItem: k => { delete store[k]; } },
    URL: { createObjectURL: b => { pending = b.text; return 'blob:x'; }, revokeObjectURL() {} },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    document: { body: { appendChild() {} }, addEventListener() {},
                createElement: () => { const a = { click() { files.push([a.download, pending]); }, remove() {},
                                                   style: {} }; return a; } },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  const x = new ctx.XMLHttpRequest();
  x.open('GET', api);
  x.send();
  x.responseType = '';
  x.responseText = answer;
  x.onload();
  return files;
}
const store = {};
const asked = run('#dbdmapscout-structure', store);
setTimeout(() => {
  const again = run('', store);              // the request is used up: matches only
  const plain = run('', {});
  setTimeout(() => process.stdout.write(JSON.stringify({ asked, again, plain })), 20);
}, 20);
"""


def _without_clock(body: str) -> str:
    """The saved file without its "exported" time – the clock's digits are no leaked value (1.8.51: CI failed when
    the time 1792410993 held the secret "99")."""
    return json.dumps({k: v for k, v in json.loads(body).items() if k != "exported"})


def test_userscript_saves_the_structure_only_on_request_and_without_values(tmp_path):
    """1.8.46: opened with #dbdmapscout-structure the script saves once the shape of the page's answer – field
    names and types, no value, no id-like or name-like field name."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    page_answer = {"data": [{
        "matchStat": {"matchStartTime": T0, "map": {"name": "Mother's Dwelling"}, "isCustomMatch": False,
                      "matchId": "secret-match-id", "extra": None},
        "playerStat": {"playerName": "MyOwnName", "perks": [{"name": "Pop Goes the Weasel", "tier": 3}],
                       "bloodpointsEarned": 241377},
        "opponentStat": [{"playerName": "SomeoneElse", "platformId": "765611"}],
        "byPlayer": {"0123456789abcdef": {"score": 1}, "Some Name": {"score": 2}}},
        {"matchStat": {"matchStartTime": T0 - 900, "extra": "x"}, "playerStat": {}, "opponentStat": []}]}
    script_path = tmp_path / "harness.js"
    answer_path = tmp_path / "answer.json"
    script_path.write_text(STRUCTURE_HARNESS, encoding="utf-8")
    answer_path.write_text(json.dumps(page_answer), encoding="utf-8")
    out = subprocess.run([node, str(script_path), SCRIPT, str(answer_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    res = json.loads(out.stdout)
    names = [n for n, _body in res["asked"]]
    assert "dbdmapscout-structure.json" in names and "dbdmapscout-matches.json" in names
    body = dict(res["asked"])["dbdmapscout-structure.json"]
    for secret in ("MyOwnName", "SomeoneElse", "765611", "secret-match-id", "Pop Goes", "241377", "Mother",
                   "0123456789abcdef", "Some Name"):
        assert secret not in _without_clock(body)
    shape = json.loads(body)
    assert shape["format"] == "dbdmapscout-structure" and shape["script"] == o.script_version(SCRIPT)
    match = shape["shape"]["data"][0]
    assert match["matchStat"]["matchStartTime"] == "number" and match["matchStat"]["extra"] == "string"
    assert match["playerStat"]["perks"] == [{"name": "string", "tier": "number"}]
    assert match["byPlayer"] == {"<key>": {"score": "number"}}
    assert [n for n, _b in res["again"]] == [] and [n for n, _b in res["plain"]] == ["dbdmapscout-matches.json"]


RESAVE_RUNS = r"""
const store = {};
const first = run('', store);                          // a new match: saved
setTimeout(() => {
  const again = run('', store);                        // nothing new: nothing saved, and the console says why
  const resave = run('#dbdmapscout-resave', store);    // asked: saved once more although nothing is new
  setTimeout(() => {
    const after = run('', store);                      // the request is used up
    setTimeout(() => process.stdout.write(JSON.stringify({ first, again, resave, after, logs })), 20);
  }, 20);
}, 20);
"""


def test_userscript_4_saves_all_matches_again_on_request_and_says_what_it_does(tmp_path):
    """1.8.52: after a new install the user had to reset the script's memory in the browser console to get a file
    without a new match – #dbdmapscout-resave does it once; the console tells that the script runs and why it saved
    nothing (the user saw an empty console and could not tell whether the script ran at all)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    head = STRUCTURE_HARNESS[:STRUCTURE_HARNESS.index("const store = {};")]
    harness = ("const logs = [];\n" + head.replace("console: { log() {} }", "console: { log: m => logs.push(String(m)) }")
               + RESAVE_RUNS)
    page_answer = {"data": [{"matchStat": {"matchStartTime": T0, "map": {"name": "Coal Tower"}},
                             "playerStat": {"playerRole": "VE_Slasher"}, "opponentStat": []}]}
    (tmp_path / "harness.js").write_text(harness, encoding="utf-8")
    (tmp_path / "answer.json").write_text(json.dumps(page_answer), encoding="utf-8")
    out = subprocess.run([node, str(tmp_path / "harness.js"), SCRIPT, str(tmp_path / "answer.json")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    res = json.loads(out.stdout)
    names = {k: [n for n, _b in res[k]] for k in ("first", "again", "resave", "after")}
    assert names == {"first": ["dbdmapscout-matches.json"], "again": [], "resave": ["dbdmapscout-matches.json"],
                     "after": []}
    assert o.parse(json.loads(res["resave"][0][1]), now=T0)[0][0].map == "Coal Tower"
    assert sum("userscript 4 active" in m for m in res["logs"]) == 4                 # once per page load
    assert sum("no new match" in m for m in res["logs"]) == 2                       # "again" and "after"
    assert o.RESAVE_HASH == "#dbdmapscout-resave" and o.RESAVE_SCRIPT == o.script_version(SCRIPT)


# ------------------------------------------------------------------ map correction, trend
def test_correct_maps_takes_the_page_map_as_layout_one():
    ids = {"Coal Tower": "coal", "Groaning Storehouse": "gs"}.get
    a, b, c = rnd(T0, "coal"), rnd(T0 + 600, "coal"), rnd(T0 + 1200, "")
    a.map, b.map, c.map = "Coal Tower II", "Coal Tower II", "Old Label"
    fixed = o.correct_maps([(a, match(T0, "Coal Tower")), (b, match(T0 + 600, "Groaning Storehouse")),
                            (c, match(T0 + 1200, "Brand New Map"))], ids,
                           lambda mid: {"gs": "Groaning Storehouse I"}.get(mid))
    assert (a.map_id, a.map) == ("coal", "Coal Tower II")          # same map: layout stays as detected
    assert (b.map_id, b.map) == ("gs", "Groaning Storehouse I")     # other map: the page wins
    assert (c.map_id, c.map) == ("", "Old Label")                   # unknown map on the page: left alone
    assert fixed == {id(b): "Coal Tower II"}


def test_bucket_start_hour_day_week():
    import time as _time
    t = T0                                                         # Saturday
    for unit, fmt in (("hour", "%a %H:%M"), ("day", "%a %H:%M"), ("week", "%a %H:%M")):
        b = o.bucket_start(t, unit)
        assert b <= t and o.bucket_start(b, unit) == b
        nxt = o._next_bucket(b, unit)
        assert nxt > t and o.bucket_start(nxt, unit) == nxt
    assert _time.localtime(o.bucket_start(t, "week")).tm_wday == 0  # weeks start on Monday
    assert _time.localtime(o.bucket_start(t, "day")).tm_hour == 0


def test_trend_keeps_empty_buckets_and_the_newest_30(monkeypatch):
    week = 7 * 86400
    ms, _s = o.parse(export(entry(T0), entry(T0 + 60, statuses=("Escaped",) * 4),
                            entry(T0 + 2 * week, role="VE_Camper", own={"name": "Escaped"}),
                            entry(T0 + 3 * week, statuses=("VE_Mystery",) * 4)), now=T0 + 4 * week)
    pairs = [(rnd(m.t, "x"), m) for m in ms]
    got = o.trend(pairs, "week")
    assert [(len(k), len(e)) for _b, k, e in got] == [(2, 0), (0, 0), (0, 1)]   # unknown result: no bucket
    assert got[0][1] == [4, 0] and got[2][2] == [True]
    assert [b for b, _k, _e in got] == sorted(b for b, _k, _e in got)
    assert o.trend([], "day") == []
    monkeypatch.setattr(o, "MAX_BUCKETS", 2)
    assert len(o.trend(pairs, "week")) == 2


def test_chart_columns_stay_thin():
    trendchart = pytest.importorskip("dbdmapscout.trendchart")
    cols = trendchart.columns(3, 600)
    assert len(cols) == 3 and all(x1 - x0 <= trendchart.BAR_MAX + 1e-9 for x0, x1 in cols)
    assert all(a[1] < b[0] for a, b in zip(cols, cols[1:]))     # air between columns
    many = trendchart.columns(30, 400)
    assert all(x1 > x0 for x0, x1 in many) and many[-1][1] <= 400 - trendchart.RIGHT
    assert trendchart.columns(0, 600) == []


def test_a_second_round_inside_a_match_is_a_false_detection():
    # Trickster's Delusion: the real round was lost (new "banner" mid-match), the false one ran to the end
    m = o.Match(t=T0, map="Trickster's Delusion", seconds=900)
    real = rnd(T0 + 38, "trickster")                          # lost round, rescued with the page's length
    ghost = rnd(T0 + 400, "ormond")                           # read from a neon strip 6 min into the match
    later = rnd(T0 + 1000, "coal")                            # the next match (not on the page yet)
    rounds = [ghost, later, real]
    tied, _other = o.link(rounds, [m], {"Trickster's Delusion": "trickster"}.get)
    assert tied == {2: m}
    assert o.phantoms(rounds, tied) == {0}
    assert o.phantoms(rounds, {}) == set()                    # without the page nothing is thrown out
    m.seconds = 0                                             # page without a length: no guess
    assert o.phantoms(rounds, tied) == set()


def test_take_downloads_hands_over_the_new_matches(tmp_path):
    store = str(tmp_path / o.FILE)
    write(str(tmp_path), "dbdmapscout-matches.json", export(entry(T0), entry(T0 + 900)))
    assert [m.t for m in o.take_downloads(str(tmp_path), store, now=T0 + 3600).fresh] == [T0, T0 + 900]
    write(str(tmp_path), "dbdmapscout-matches.json", export(entry(T0 + 900), entry(T0 + 1800)))
    write(str(tmp_path), "dbdmapscout-matches (1).json", export(entry(T0 + 1800)))      # the same match twice
    res = o.take_downloads(str(tmp_path), store, now=T0 + 3600)
    assert [m.t for m in res.fresh] == [T0 + 1800] and res.new == 1                      # only the unknown one


# ------------------------------------------------------------------ 1.8.46: fates and opponents
def _kmatch(*statuses, chars=None):
    chars = chars or ["Meg Thomas", "Feng Min", "Dwight Fairfield", "Claudette Morel"]
    return o.Match(t=T0, map="Coal Tower", role="killer",
                   opp=[o.Player(role="survivor", character=c, status=s, img=i)
                        for c, (s, i) in zip(chars, statuses)])


def test_fates_split_hook_kills_from_other_kills_and_spot_the_abandon_bug():
    assert o.fate("SACRIFICED", "VE_Sacrificed") == "sacrificed"
    assert o.fate("DEAD", "VE_Killed") == "killed" and o.fate("", "VE_Killed") == "killed"
    assert o.fate("ESCAPED", "VE_Escaped") == "escaped"
    assert o.fate("ESCAPED", "VE_SurrenderDraw") == "abandoned"         # the page's bug: the picture is right
    assert o.fate("", "VE_ManuallyLeftMatch") == "gone" and o.fate("", "") is None


def test_fates_clean_kills_and_opponents():
    s, k, e, a = ("SACRIFICED", "VE_Sacrificed"), ("DEAD", "VE_Killed"), ("ESCAPED", "VE_Escaped"), \
        ("ESCAPED", "VE_SurrenderDraw")
    m1 = _kmatch(s, s, k, e)                       # 3 kills, played out
    m2 = _kmatch(a, s, s, s)                       # 4 kills with an abandon: not "clean"
    surv = o.Match(t=T0, map="Badham", role="survivor", status="SACRIFICED", img="VE_Sacrificed",
                   opp=[o.Player(role="killer", character="The Nurse"), o.Player(role="survivor", character="Ace")])
    pairs = [(None, m1), (None, m2), (None, surv)]
    assert o.fates(pairs) == {"sacrificed": 5, "killed": 1, "escaped": 1, "abandoned": 1}
    assert o.share(o.fates(pairs), "abandoned", "gone") == 1 / 8 and o.share({}, "escaped") is None
    assert o.clean_kills(pairs) == [3]
    opp = {(x.name, x.role): x for x in o.opponents(pairs)}
    assert opp[("Meg Thomas", "survivor")].n == 2 and opp[("Meg Thomas", "survivor")].fates == {"sacrificed": 1,
                                                                                                  "abandoned": 1}
    assert opp[("The Nurse", "killer")].fates == {"sacrificed": 1}      # as survivor: how your own match ended
    assert ("Ace", "survivor") not in opp                               # a fellow survivor is no opponent
    assert o.opponents(pairs)[0].n == 2                                  # most met first


# ------------------------------------------------------------------ 1.8.48: userscript 3 – own loadout, match infos
LOADOUT_ANSWER = [{
    "matchStat": {"matchStartTime": T0, "map": {"id": "Ind_Coal_Tower", "name": "Coal Tower", "image": {"path": "x"}},
                  "isCustomMatch": False, "matchDuration": 612, "specialEventId": "",
                  "gameType": {"id": "Online", "name": "Public Match"}, "matchId": "secret-match-id"},
    "playerStat": {"playerRole": "VE_Slasher", "characterName": {"name": "The Nurse"}, "playerTimeInMatch": 600,
                   "bloodpointsEarned": 30000, "prestigeLevel": 12, "characterLevel": 50, "platform": "steam",
                   "killerMatchStatus": "Merciless", "leaderboardScore": 999,
                   "postGameStat": {"DBD_SlasherScoreCat_Hunter": 8000, "Other_Secret": 1},
                   "emblems": [{"emblem_id": "Gatekeeper", "emblem_name": "Gatekeeper", "emblem_quality": "Iridescent"}],
                   "characterLoadout": {
                       "perks": [{"id": f"P{i}", "name": n, "image": {"path": "p.png"}}
                                 for i, n in enumerate(["Lethal Pursuer", "Pop Goes the Weasel", "Grim Embrace",
                                                        "Deadlock"])],
                       "addOns": [{"id": "A1", "name": "Bad Man's Last Breath"}, {"id": "A2", "name": "Kavanagh's"}],
                       "offering": {"id": "O1", "name": "Ebony Memento Mori", "image": {"background": "b"}},
                       "power": {"id": "W1", "name": "Spencer's Last Breath"}}},
    "opponentStat": [{"playerRole": "VE_Camper", "characterName": {"name": "Meg Thomas"}, "prestigeLevel": 99,
                      "platform": "xbox", "bloodpointsEarned": 1234,
                      "characterLoadout": {"perks": [{"id": "DH", "name": "Dead Hard"}]},
                      "emblems": [{"emblem_name": "Benevolent"}],
                      "playerStatus": {"name": "SACRIFICED", "image": {"path": "VE_Sacrificed.png"}}}] * 4}]


def test_userscript_3_takes_the_own_loadout_and_match_infos_but_nothing_more_of_the_others(tmp_path):
    """1.8.48: the user's pick from the structure – own data and match infos; the other players stay at character,
    role and status (no perks, prestige, platform, BP, emblems of them)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    script_path, answer_path = tmp_path / "harness.js", tmp_path / "answer.json"
    script_path.write_text(HARNESS, encoding="utf-8")
    answer_path.write_text(json.dumps(LOADOUT_ANSWER), encoding="utf-8")
    out = subprocess.run([node, str(script_path), SCRIPT, str(answer_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    body = json.loads(out.stdout)["xhr"][0]
    for secret in ("secret-match-id", "Dead Hard", "xbox", "1234", "Benevolent", "99", "Other_Secret", "steam",
                   "999", "p.png"):
        assert secret not in _without_clock(body)
    saved = json.loads(body)["matches"][0]
    assert set(saved["opponents"][0]) == {"role", "character", "status"}
    ms, script = o.parse(json.loads(body), now=T0)
    m = ms[0]
    assert script == o.script_version(SCRIPT) >= 3
    assert m.mode == ["Online", "Public Match"] and m.map_key == "Ind_Coal_Tower" and m.duration == 612
    assert [p[1] for p in m.perks] == ["Lethal Pursuer", "Pop Goes the Weasel", "Grim Embrace", "Deadlock"]
    assert m.addons[0] == ["A1", "Bad Man's Last Breath"] and m.offering == ["O1", "Ebony Memento Mori"]
    assert m.power == ["W1", "Spencer's Last Breath"] and m.emblems == [["Gatekeeper", "Gatekeeper", "Iridescent"]]
    assert m.score == {"DBD_SlasherScoreCat_Hunter": 8000.0} and (m.prestige, m.level) == (12, 50)
    assert m.killer_status == "Merciless" and o.kills(m) == 4
    # stored and read back; an old line without the fields still loads
    store = str(tmp_path / "official.jsonl")
    o.merge(store, ms)
    with open(store, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": T0 - 3600, "map": "Badham", "role": "killer"}) + "\n")
    old, back = o.load(store)
    assert back.perks == m.perks and back.score == m.score and back.prestige == 12 and back.mode == m.mode
    assert old.perks == [] and old.prestige is None and old.mode == []


def test_modes_seen_most_played_first_and_unknown_left_out():
    """1.8.49: the game modes the page named (userscript 3); matches from before have none."""
    ms = [o.Match(t=T0 + i, map="x", mode=mode) for i, mode in
          enumerate((["Online", "Public Match"], ["Online", "Public Match"], ["2v8", "2v8 Mode"], [], ["", "Event"]))]
    assert o.modes_seen(ms) == [("Online", "Public Match"), ("2v8", "2v8 Mode"), ("Event", "Event")]
    assert o.mode_key(ms[3]) == "" and o.mode_key(None) == ""


def test_opponent_names_are_the_other_players_characters():
    """1.8.73: the setting farming_opponents names farming partners by character."""
    m = o.Match(t=T0, map="Coal Tower", role="survivor", opp=[
        o.Player(role="killer", character="Slasher", status="Escaped"),
        o.Player(role="survivor", character="Meg Thomas"), o.Player(role="survivor", character="")])
    assert o.opponent_names(m) == {"Slasher", "Meg Thomas"}
    assert o.opponent_names(o.Match(t=T0, map="Coal Tower")) == set()
