"""Core tests (python -m pytest tests)."""
import itertools
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dbdmapscout.catalog import Catalog
from dbdmapscout.detector import Accumulator, FrameResult
from dbdmapscout.hotkeys import parse
from dbdmapscout.ocr import N_GROUPS, LexiconScorer, _GROUP_OF
from dbdmapscout.textnorm import fmt_duration, fold, name_forms


def test_fold():
    assert fold("Azarov’s Resting Place") == "AZAROVSRESTINGPLACE"
    assert fold("Gestörtenabteilung") == "GESTORTENABTEILUNG"
    assert fold("Posiadłość Macmillanów") == "POSIADLOSCMACMILLANOW"
    assert fold("Krähenhorst") == "KRAHENHORST"
    assert name_forms("The Game", "en") == ["The Game", "Game"]
    assert name_forms("Das Spiel", "de") == ["Das Spiel", "Spiel"]


def _brute_ctc(groups, label):
    """Sum over all frame labellings that collapse to `label` (tiny inputs only)."""
    T = groups.shape[0]
    symbols = sorted({0} | set(label))
    total = 0.0
    for path in itertools.product(symbols, repeat=T):
        out, prev = [], None
        for s in path:
            if s != prev and s != 0:
                out.append(s)
            prev = s
        if out == list(label):
            total += float(np.prod([groups[t, s] for t, s in enumerate(path)]))
    return total


@pytest.mark.parametrize("word", ["AB", "ABA", "AAB", "A", "BB"])
def test_ctc_matches_brute_force(word):
    rng = np.random.default_rng(1)
    T = 6
    g = rng.random((T, N_GROUPS)) + 1e-3
    g /= g.sum(1, keepdims=True)
    scorer = LexiconScorer([word])
    got = scorer.score(g)[0]
    want = np.log(_brute_ctc(g, [_GROUP_OF[c] for c in word]))
    assert got == pytest.approx(want, rel=1e-6)


def test_hotkey_parse():
    assert parse("ctrl+alt+m") == (0x0003, ord("M"))
    assert parse("Strg+Shift+F8") == (0x0006, 0x77)
    with pytest.raises(ValueError):
        parse("ctrl+alt")


def test_catalog_variants_and_images():
    cat = Catalog(ROOT, ["en", "de"])
    keys = {(h.map_id, h.variant, h.name_key) for h in cat.hypotheses}
    assert ("coal-tower", 2, "COALTOWERII") in keys
    assert ("coal-tower", 1, "COALTOWER") in keys
    assert ("coal-tower", 2, "KOHLELAGERII") in keys
    assert ("badham-preschool", 4, "BADHAMPRESCHOOLIV") in keys
    # every image in maps/ belongs to a catalogue entry (no orphaned custom maps)
    assert not [m for m in cat.maps.values() if m.custom]
    path, shown = cat.image_path("family-residence", 2)      # variant without picture -> falls back to I
    assert shown == 1 and path.endswith("Family Residence.webp")


def test_both_spellings_of_treatment_theatre():
    """The game shows "TREATMENT THEATER" (US spelling), the catalogue name is British – both must match."""
    cat = Catalog(ROOT, ["en"])
    keys = {(h.map_id, h.name_key) for h in cat.hypotheses}
    assert ("treatment-theatre", "TREATMENTTHEATRE") in keys
    assert ("treatment-theatre", "TREATMENTTHEATER") in keys
    alias = next(h for h in cat.hypotheses if h.name_key == "TREATMENTTHEATER")
    assert fold("Léry's Memorial Institute") in alias.realm_keys


def test_accumulator_prefers_consistent_evidence():
    acc = Accumulator()
    good = FrameResult(scores={("a", 1): -1.0, ("a", 2): -4.0, ("b", 1): -60.0}, best=("a", 1), name_fit=-0.5)
    d = acc.add(good)
    assert d is not None and (d.map_id, d.variant) == ("a", 1)
    bad = FrameResult(scores={("b", 1): -1.0}, best=("b", 1), name_fit=-30.0)   # unreadable -> ignored
    assert acc.add(bad) is None


def test_custom_images(tmp_path):
    import shutil
    (tmp_path / "maps" / "Coldwind Farm").mkdir(parents=True)
    (tmp_path / "maps" / "Meine Karten").mkdir(parents=True)
    src = os.path.join(ROOT, "maps", "Coldwind", "Rotten Fields.webp")
    shutil.copy(src, tmp_path / "maps" / "Coldwind Farm" / "Blood Hollow.webp")
    shutil.copy(src, tmp_path / "maps" / "Meine Karten" / "Night Harbor.webp")
    shutil.copy(os.path.join(ROOT, "maps.json"), tmp_path / "maps.json")
    cat = Catalog(str(tmp_path), ["en", "de"])
    hyp = {h.map_id: h for h in cat.hypotheses if h.map_id.startswith("custom:")}
    blood = hyp["custom:Coldwind Farm/Blood Hollow.webp"]
    night = hyp["custom:Meine Karten/Night Harbor.webp"]
    assert blood.name_key == "BLOODHOLLOW" and "COLDWINDFARM" in blood.realm_keys
    assert night.name_key == "NIGHTHARBOR" and night.realm_keys == ()      # unknown folder: no realm constraint


def test_fmt_duration():
    assert fmt_duration(0) == "00:00"
    assert fmt_duration(452.9) == "07:32"
    assert fmt_duration(3723) == "1:02:03"
    assert fmt_duration(-5) == "00:00"


def test_user_aliases_become_hypotheses():
    cat = Catalog(ROOT, ["en"], {"coal-tower": ["Macmillan Tower"], "no-such-map": ["Whatever Place"]})
    alias = [h for h in cat.hypotheses if h.name_key == "MACMILLANTOWER"]
    assert [(h.map_id, h.lang) for h in alias] == [("coal-tower", "alias")]
    assert fold("The MacMillan Estate") in alias[0].realm_keys            # realm check stays on
    assert not [h for h in cat.hypotheses if h.name_key == "WHATEVERPLACE"]
    assert not [h for h in Catalog(ROOT, ["en"]).hypotheses if h.name_key == "MACMILLANTOWER"]


def test_alias_problems():
    cat = Catalog(ROOT, ["en"])
    assert cat.alias_problem("Macmillan Tower", "coal-tower") is None
    assert "zu kurz" in cat.alias_problem("A.B", "coal-tower")
    assert "Shelter Woods" in cat.alias_problem("SHELTER WOODS", "coal-tower")   # name of another map
    assert cat.alias_problem("COAL TOWER", "coal-tower") is None                  # own name: harmless
    assert cat.alias_problem("Macmillan Tower", "no-such-map") == "Unbekannte Map."


def test_suggestion_for_unknown_banner():
    cat = Catalog(ROOT, ["en", "de"])
    assert cat.suggest("GRIM PANTRI", "BACKWATER SWAMP") == "grim-pantry"
    assert cat.suggest("COAL TOWR", "THE MACMILLAN ESTATE") == "coal-tower"
    assert cat.suggest("TREATMENT THEATER", "LERY'S MEMORIAL INSTITUTE") == "treatment-theatre"


def test_settings_backup_round_trip(tmp_path):
    import json
    from dbdmapscout import config
    s = config.Settings(str(tmp_path / "settings.json"))
    s.data["hotkeys"]["rotate_map"] = "ctrl+alt+x"
    s.data["overlay"]["map_rotations"] = {"coal-tower": 90}
    s.data["user_aliases"] = {"coal-tower": ["KOHLETURM"]}
    s.data["setup_root"] = "C:/old/place"
    backup = str(tmp_path / "backup.json")
    config.export_settings(s.data, backup)
    raw = json.load(open(backup, encoding="utf-8"))
    del raw["overlay"]["show_map"]                                   # older backup without a newer key
    json.dump(raw, open(backup, "w", encoding="utf-8"))
    got = config.read_backup(backup, {"setup_root": "D:/new/place", "window_geometry": "800x600"})
    assert got["hotkeys"]["rotate_map"] == "ctrl+alt+x" and got["overlay"]["map_rotations"] == {"coal-tower": 90}
    assert got["user_aliases"] == {"coal-tower": ["KOHLETURM"]}
    assert got["overlay"]["show_map"] is True                        # default filled in
    assert got["setup_root"] == "D:/new/place" and got["window_geometry"] == "800x600"   # this PC's values
    bad = tmp_path / "bad.json"
    bad.write_text('{"foo": 1}', encoding="utf-8")
    import pytest
    for path in (str(bad), str(tmp_path / "missing.json")):
        with pytest.raises(ValueError):
            config.read_backup(path, {})
    s.frozen = True                                                  # after an import: no writes until restart
    s.save()
    assert not (tmp_path / "settings.json").exists()


def test_doubtful_read_is_marked_and_cleared_by_a_clean_frame():
    acc = Accumulator()
    meh = FrameResult(scores={("a", 1): -5.0, ("b", 1): -60.0}, best=("a", 1), name_fit=-5.0)
    assert acc.add(meh) is None                                   # one mediocre frame: not decided yet
    d = acc.add(meh)
    assert d is not None and d.map_id == "a" and d.unsure and d.name_fit == -5.0
    assert acc.add(meh) is None                                   # still doubtful: nothing new
    clean = FrameResult(scores={("a", 1): -0.5, ("b", 1): -60.0}, best=("a", 1), name_fit=-0.2)
    d = acc.add(clean)
    assert d is not None and not d.unsure and d.name_fit == -0.2  # the banner read cleanly later on
    assert acc.add(clean) is None
    acc.reset()
    d = acc.add(clean)
    assert d is not None and not d.unsure                         # a clean banner is never doubtful
