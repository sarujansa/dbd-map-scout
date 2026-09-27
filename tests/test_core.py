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
