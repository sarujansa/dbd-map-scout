"""Lobby button, waiting time and role (lobby.py) – on crops of the user's screenshots (3440×1440)."""
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import lobby  # noqa: E402
from dbdmapscout.lobby import Found, LobbyView, QueueTracker  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tests", "data", "lobby")
W, H = 3440, 1440


@pytest.fixture(scope="module")
def reader():
    from dbdmapscout.ocr import Recognizer
    return lobby.LobbyReader(Recognizer(os.path.join(ROOT, "models", "ch_PP-OCRv4_rec_infer.onnx")))


def view(reader, name):
    return reader.read(cv2.imread(os.path.join(DATA, name + ".jpg")), W, H)


@pytest.mark.parametrize("name, button, kind, role, elapsed", [
    ("k_play", "play", "play", None, None),
    ("k_play_nurse", "play", "play", None, None),
    ("s_play", "play", "play", None, None),
    ("k_search_grizzly", "cancel", "search", "killer", 6),
    ("k_search_hb", "cancel", "search", "killer", 0),
    ("k_search_loadout", "cancel", "search", "killer", 7 * 60 + 29),   # search goes on in the loadout menu
    ("k_search_nurse", "cancel", "search", "killer", 2),
    ("s_search", "cancel", "search", "survivor", 0),
    ("k_ready", "ready", "lobby", "killer", None),
    ("s_ready", "ready", "lobby", "survivor", None),
    ("s_readied", "cancel", "lobby", "survivor", None),                 # CANCEL again, but no EST.
    ("s_readied_red", "cancel", "lobby", "survivor", None),
    ("custom_ready", "ready", "custom", None, None),                    # nothing below the button
    ("k_match", None, None, None, None),
    ("s_match", None, None, None, None),
    ("loading", None, None, None, None),
    ("k_result", None, None, None, None),
    ("s_result", None, None, None, None),
])
def test_lobby_button(reader, name, button, kind, role, elapsed):
    v = view(reader, name)
    assert (v.button, v.kind, v.role, v.elapsed) == (button, kind, role, elapsed), (v.fit, v.name, v.time_text)


@pytest.mark.parametrize("name, role", [("k_result", "killer"), ("s_result", "survivor"), ("k_match", None),
                                        ("s_match", None), ("loading", None), ("k_play", None)])
def test_result_screen_role(reader, name, role):
    assert reader.result_role(cv2.imread(os.path.join(DATA, name + ".result.jpg"))) == role


def test_zones_are_inside_the_window_and_scale():
    x, y, w, h = lobby.corner_box(W, H)
    assert x > 2400 and x + w <= W and y + h <= H                         # at the real right window edge
    x2, y2, w2, h2 = lobby.corner_box(2560, 1440)                          # 16:9 monitor: same size
    assert (w2, h2) == (w, h) and x2 == x - 880
    assert lobby.corner_box(1920, 1080)[2] == pytest.approx(w * 0.75, abs=2)
    assert reader_free_empty()


def reader_free_empty():
    r = lobby.LobbyReader.__new__(lobby.LobbyReader)
    return r.read(np.zeros((0, 0, 3), np.uint8), W, H).button is None


# ------------------------------------------------------------------ queue logic
def V(kind, role=None, elapsed=None):
    """A LobbyView that the reader would produce for this state."""
    name = "THE NURSE" if role == "killer" else ""
    if kind == "play":
        return LobbyView("play", 0.0)
    if kind == "search":
        t = f"{elapsed // 60}:{elapsed % 60:02d} EST. 4:16" if elapsed is not None else "EST. 4:16"
        return LobbyView("cancel", 0.0, name, t)
    if kind == "lobby":
        return LobbyView("ready", 0.0, name, "00:59")
    if kind == "readied":
        return LobbyView("cancel", 0.0, name, "00:34")
    if kind == "custom":
        return LobbyView("ready", 0.0, "", "")
    return None


def run(q, looks):
    out = []
    for t, v in looks:
        out += q.update(v, t)
    return out


def test_search_to_lobby_measures_the_wait():
    q = QueueTracker()
    ev = run(q, [(0, V("play")), (1, V("play")), (10, V("search", "killer", 0)), (11, V("search", "killer", 1)),
                 (50, None), (80, None),                                         # loadout/store: no button
                 (130, V("search", "killer", 120)), (200, V("lobby", "killer")), (201, V("lobby", "killer"))])
    assert ("search",) in ev and ("role", "killer") in ev
    found = [e[1] for e in ev if e[0] == "found"][0]
    assert found.role == "killer" and found.wait == pytest.approx(190, abs=1)
    assert q.take(400) == found and q.take(401) is None                        # handed out once


def test_start_missed_uses_dbd_counter():
    q = QueueTracker()
    ev = run(q, [(1000, V("search", "survivor", 300)), (1001, V("search", "survivor", 301)),
                 (1100, V("readied", "survivor")), (1101, V("readied", "survivor"))])
    found = [e[1] for e in ev if e[0] == "found"][0]
    assert found.wait == pytest.approx(400, abs=1) and found.role == "survivor"


def test_one_misread_does_not_end_a_search():
    q = QueueTracker()
    run(q, [(0, V("search", "killer", 0)), (1, V("search", "killer", 1)), (2, V("play")), (3, V("search", "killer", 3))])
    assert q.state == "search"


def test_cancelled_search_is_dropped():
    q = QueueTracker()
    ev = run(q, [(0, V("search", "killer", 0)), (1, V("search", "killer", 1)), (60, V("play")), (61, V("play"))])
    assert ("cancel",) in ev and q.state == "idle" and q.found is None


def test_custom_game_has_no_wait_and_no_role():
    q = QueueTracker()
    ev = run(q, [(0, V("custom")), (1, V("custom"))])
    found = [e[1] for e in ev if e[0] == "found"][0]
    assert found == Found(0, None, None, custom=True)


def test_lobby_without_seen_search_has_no_wait():
    q = QueueTracker()
    ev = run(q, [(0, V("lobby", "survivor")), (1, V("lobby", "survivor"))])
    assert [e[1] for e in ev if e[0] == "found"][0].wait is None


def test_old_lobby_is_not_used():
    q = QueueTracker()
    run(q, [(0, V("lobby", "killer")), (1, V("lobby", "killer"))])
    assert q.take(5000) is None


def test_elapsed_parsing():
    assert LobbyView("cancel", 0, "", "7:29 EST. 0:-01").elapsed == 449
    assert LobbyView("cancel", 0, "", "0:00 EST.4:39").elapsed == 0
    assert LobbyView("cancel", 0, "", "00:34").elapsed is None
    assert LobbyView("ready", 0, "", "00:：53").kind == "lobby"
    assert LobbyView("cancel", 0, "专M", "0:00 EST. 0:-01").role == "survivor"   # OCR noise is no name


def test_killer_lobby_after_ready():
    """Killer lobby: READY „THE NURSE 00:56“, after pressing it CANCEL „THE NURSE 00:49“ (no EST.)."""
    assert (LobbyView("ready", 0, "THE NURSE", "00:56").kind, LobbyView("ready", 0, "THE NURSE", "00:56").role) == \
        ("lobby", "killer")
    v = LobbyView("cancel", 0, "THE NURSE", "00:49")
    assert (v.kind, v.role, v.elapsed) == ("lobby", "killer", None)


def test_result_role_with_our_overlay_blacked_out(reader):
    """The map overlay in the left bar covers the first category (BRUTALITY) – three words still do."""
    for name, role in (("k_result", "killer"), ("s_result", "survivor")):
        img = cv2.imread(os.path.join(DATA, name + ".result.jpg"))
        img[:, :423 - lobby.result_box(W, H)[0]] = 0
        assert reader.result_role(img) == role


def test_reminder_when_countdown_runs_out_without_ready():
    q = QueueTracker()
    lob = lambda s: LobbyView("ready", 0, "", f"00:{s:02d}")               # noqa: E731
    ev = run(q, [(0, V("search", "survivor", 0)), (1, V("search", "survivor", 1)), (50, lob(59)), (51, lob(58)),
                 (80, lob(20)), (95, lob(14)), (96, lob(13)), (97, lob(12))])
    assert [e for e in ev if e[0] == "remind"] == [("remind", 14)]           # once per lobby
    q2 = QueueTracker()                                                      # READY pressed: CANCEL, no reminder
    ev2 = run(q2, [(0, lob(59)), (1, lob(58)), (2, LobbyView("cancel", 0, "", "00:10"))])
    assert not [e for e in ev2 if e[0] == "remind"]
    assert LobbyView("ready", 0, "", "00:53").countdown == 53 and LobbyView("play", 0).countdown is None
