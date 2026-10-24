"""1.8.38 (QA audit): failures in one part must not leave the user with a dead detection, a map that stays up after
the round or OBS recording on after quitting – the detection loop, the round end in the app, quitting."""
import json
import os
import queue
import sys
import time

import cv2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fogscout import config, worker  # noqa: E402
from fogscout.catalog import Catalog  # noqa: E402


def _events(q, timeout, until):
    """Events of the worker until ``until(kinds)`` holds or the time is up."""
    seen, end = [], time.time() + timeout
    while time.time() < end and not until([e.kind for e in seen]):
        try:
            seen.append(q.get(timeout=0.1))
        except queue.Empty:
            pass
    return seen


def _worker(tmp_path, monkeypatch, fails):
    """A worker in simulation whose picture source raises for the first ``fails`` frames (None = always)."""
    frame = cv2.imread(os.path.join(ROOT, "tests", "data", "end", "spectate.jpg"))
    calls = {"n": 0}

    class Source:
        def __init__(self, *_a, **_k):
            pass

        def current(self):
            calls["n"] += 1
            if fails is None or calls["n"] <= fails:
                raise RuntimeError("bad frame")
            return frame

    monkeypatch.setattr(worker, "ImageSource", Source)
    monkeypatch.setattr(worker, "TICK_FAIL_WAIT_S", 0.01)
    events = queue.Queue()
    w = worker.DetectionWorker(ROOT, config.Settings(str(tmp_path / "settings.json")), Catalog(ROOT, ["en"]),
                               events, simulate=str(tmp_path))
    return w, events, calls


def test_a_frame_that_raises_does_not_end_the_detection(tmp_path, monkeypatch):
    """Before, any exception in the loop (OCR, capture, a tracker) ended the thread for good: no end of the round,
    no next map until a restart – and only a bar in the hidden main window said so."""
    w, events, calls = _worker(tmp_path, monkeypatch, fails=3)
    w.start()
    try:
        seen = _events(events, 20, lambda kinds: "status" in kinds)
        kinds = [e.kind for e in seen]
        assert "status" in kinds and "error" not in kinds              # it went on with the next frame
        warns = [e.data["text"] for e in seen if e.kind == "warn"]
        assert len(warns) == 1 and warns[0].startswith("Erkennung:") and "bad frame" in warns[0]   # told once
        assert calls["n"] > 3 and w.is_alive()
    finally:
        w.stop()
        w.join(timeout=10)
    assert not w.is_alive()


def test_a_detection_that_fails_every_frame_is_reported_as_crashed(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "TICK_FAIL_LIMIT", 4)
    w, events, calls = _worker(tmp_path, monkeypatch, fails=None)
    w.start()
    seen = _events(events, 20, lambda kinds: "error" in kinds)
    w.join(timeout=10)
    assert [e.kind for e in seen].count("error") == 1 and "bad frame" in seen[-1].data["text"]
    assert calls["n"] == 4 and not w.is_alive()


# ------------------------------------------------------------------ the app
@pytest.fixture
def app(tmp_path):
    if sys.platform == "win32":
        pytest.skip("Linux: the Windows job tests the native parts; the app would touch the system there")
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(ROOT, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    (tmp_path / "settings.json").write_text(json.dumps({"welcome_seen": True}), encoding="utf-8")
    from fogscout.app import App
    a = App(str(tmp_path), simulate=str(tmp_path / "sim"))
    yield a
    a.quit()


def test_the_map_is_hidden_at_the_round_end_even_when_saving_the_round_fails(app):
    """The worker sends match_end once: when saving the round raised before, the map stayed up into the lobby."""
    app.show_map("shattered-square", 1, "auto")
    assert app.overlay.has_map() and not app.hidden_after_match

    def broken(*_a, **_k):
        raise OSError("rounds.jsonl locked")

    app._hist_close = broken
    app._dispatch(worker.Event("match_end", {"t": time.time(), "reason": "Ergebnisbildschirm"}))
    assert app.hidden_after_match and not app.menu_paused
    assert "Rundenverlauf" in app._errors_seen                         # and the user hears of it


def test_a_crashed_detection_shows_in_the_status_line(app):
    from fogscout import status
    app._dispatch(worker.Event("error", {"text": "Traceback …\nRuntimeError: boom"}))
    assert status.is_problem(app._worker_status) and "neu starten" in app._worker_status


def test_quitting_runs_every_step_even_when_one_raises(app):
    calls = []

    def broken():
        raise RuntimeError("tray gone")

    app.tray.stop = broken
    save = app.settings.save
    app.settings.save = lambda: (calls.append("save"), save())
    app.recorder.quit = lambda: calls.append("recorder")
    app.recorder.join = lambda timeout=None: calls.append(("join", timeout))
    app.quit()
    assert calls == ["save", "recorder", ("join", 8)]
    assert not app.worker.is_alive()


def _detected(map_id, variant, p=0.9):
    return worker.Event("detected", {"map_id": map_id, "variant": variant, "probability": p,
                                     "variant_probability": p, "name_text": "COAL TOWER", "realm_text": "MACMILLAN"})


def test_the_round_follows_the_layout_read_later_in_the_same_banner(app):
    """1.8.39 (QA audit): later frames of one banner may decide another layout (Coal Tower I → II) – the overlay
    switched, but the round and its recording kept the first reading; a correction with the layout button too."""
    relabels = []
    app.recorder.relabel = lambda **meta: relabels.append(meta)
    starts = []
    app.recorder.start_round = lambda **meta: starts.append(meta)
    app._dispatch(_detected("coal-tower", 1))
    assert app._hist["map"] == "Coal Tower I" and len(starts) == 1
    t0 = app._hist["t"]
    app._dispatch(_detected("coal-tower", 2))                  # 3 frames later: the other layout
    assert app.current == ("coal-tower", 2)
    assert app._hist["map"] == "Coal Tower II" and app._hist["t"] == t0       # the same round, renamed
    assert relabels == [{"map_id": "coal-tower", "label": "Coal Tower II"}] and len(starts) == 1   # no new recording
    app.next_variant()                                         # the user: no, it was I
    assert app._hist["map"] == "Coal Tower I" and relabels[-1]["label"] == "Coal Tower I"
    app._dispatch(_detected("coal-tower", 1))                  # the same again: nothing to rename
    assert len(relabels) == 2


def test_a_map_shown_after_the_round_ended_does_not_rename_it(app):
    app.recorder.relabel = lambda **meta: pytest.fail("renamed a closed round")
    app.recorder.start_round = app.recorder.stop_round = lambda **meta: None
    app._dispatch(_detected("coal-tower", 1))
    app._dispatch(worker.Event("match_end", {"t": time.time() + 300, "reason": "Ergebnisbildschirm"}))
    assert app._hist is None
    app.next_variant()                                         # looking at the other layout in the lobby


def test_stopping_the_worker_does_not_wait_for_its_nap(tmp_path, monkeypatch):
    """1.8.84 (idea 8 of the UI review): without a picture the simulation slept half a second per loop and
    quitting waited for it – the nap now ends with the stop command."""
    import time
    w, events, calls = _worker(tmp_path, monkeypatch, fails=None)

    class Empty:
        def __init__(self, folder):
            pass

        def current(self):
            return None
    monkeypatch.setattr(worker, "ImageSource", Empty)
    w = worker.DetectionWorker(ROOT, config.Settings(str(tmp_path / "settings.json")), Catalog(ROOT, ["en"]),
                               events, simulate=str(tmp_path))
    w.start()
    time.sleep(0.3)                                       # well inside a nap
    t0 = time.perf_counter()
    w.stop()
    w.join(timeout=4)
    assert not w.is_alive() and time.perf_counter() - t0 < 0.3
