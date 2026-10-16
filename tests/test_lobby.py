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


def test_lobby_before_its_countdown_is_no_custom_game():
    """1.64.4 (user diagnosis: "Zustand custom" in a normal match): READY with nothing below right after a search
    is the found lobby before its countdown starts – with the wait; in a lobby (someone left, countdown stopped)
    it stays a lobby. Only without a search before is it a custom game."""
    q = QueueTracker()
    ev = run(q, [(0, V("search", "survivor", 0)), (1, V("search", "survivor", 1)),
                 (90, V("custom")), (91, V("custom")),                         # READY, no countdown yet
                 (100, V("lobby", "survivor")), (130, V("custom")), (131, V("custom"))])
    found = [e[1] for e in ev if e[0] == "found"]
    assert len(found) == 1 and not found[0].custom and found[0].wait == pytest.approx(90, abs=1)
    assert found[0].role == "survivor" and q.state == "lobby"


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


# ------------------------------------------------------------------ own killer
@pytest.mark.parametrize("name, killer", [("k_search_hb", "The Hillbilly"), ("k_search_nurse", "The Nurse"),
                                          ("k_search_loadout", "The Hillbilly"), ("k_ready", "The Hillbilly"),
                                          ("k_search_grizzly", "The Oni"), ("s_search", ""),
                                          ("s_ready", ""), ("custom_ready", ""), ("k_play", "")])
def test_killer_name(reader, name, killer):
    assert view(reader, name).killer == killer


def test_killer_missing_from_the_list_is_kept_as_read(reader, monkeypatch):
    """A new killer must never be taken for a listed one (like unknown maps)."""
    monkeypatch.setattr(lobby, "KILLERS", tuple(k for k in lobby.KILLERS if k != "The Nurse"))
    r = lobby.LobbyReader(reader.rec)
    assert view(r, "k_search_nurse").killer == "The Nurse"                  # read text, not the lexicon
    assert r.killers.strings and "THENURSE" not in r.killers.strings
    assert lobby.plain_name("THE  NEW-ONE!") == "The New One"
    assert lobby.killer_label("The Nurse") == "Nurse" and lobby.killer_label("Frank Stone") == "Frank Stone"


def K(kind, name, elapsed=None):
    """A killer's LobbyView with the name as the reader matched it."""
    v = V(kind, "killer", elapsed)
    v.name, v.killer = name.upper(), name
    return v


def test_unlisted_skin_is_kept_and_can_be_assigned(reader, monkeypatch):
    monkeypatch.setattr(lobby, "SKINS", {})
    r = lobby.LobbyReader(reader.rec)
    name = view(r, "k_search_grizzly").killer
    assert name.replace(" ", "").lower() == "murderousgrizzly"             # as read, not a wrong killer
    assert lobby.resolve_killer(name, {"MURDEROUSGRIZZLY": "The Oni"}) == "The Oni"
    assert lobby.resolve_killer(name, {}) == name and lobby.resolve_killer("", {"X": "Y"}) == ""
    assert all(k in lobby.KILLERS for k in lobby.SKINS.values())


def test_found_lobby_carries_the_killer():
    q = QueueTracker()
    ev = run(q, [(0, K("search", "The Nurse", 0)), (1, K("search", "The Nurse", 1)),
                 (2, K("search", "The Nurce", 2)),                                  # one misread: majority wins
                 (60, K("lobby", "The Nurse")), (61, K("lobby", "The Nurse"))])
    assert [e[1] for e in ev if e[0] == "found"][0].killer == "The Nurse"
    run(q, [(100, V("play")), (101, V("play"))])
    assert q.killer == ""                                                    # next search starts fresh
    q2 = QueueTracker()                                                      # survivor: never a killer
    ev2 = run(q2, [(0, V("search", "survivor", 0)), (1, V("search", "survivor", 1)), (9, V("lobby")), (10, V("lobby"))])
    assert [e[1] for e in ev2 if e[0] == "found"][0].killer == ""


def test_leaving_a_lobby_drops_it():
    """Lobby found, then back on PLAY (left / dodged): the old lobby must not stick to the next round."""
    q = QueueTracker()
    ev = run(q, [(0, V("search", "killer", 0)), (1, V("search", "killer", 1)), (60, V("lobby", "killer")),
                 (61, V("lobby", "killer")), (90, V("play")), (91, V("play"))])
    assert ("left",) in ev and ("cancel",) not in ev
    assert q.state == "idle" and q.found is None and q.take(100) is None
    q2 = QueueTracker()                                                      # custom game left: same
    assert ("left",) in run(q2, [(0, V("custom")), (1, V("custom")), (5, V("play")), (6, V("play"))])
    q3 = QueueTracker()                                                      # plain PLAY screen: nothing to leave
    assert run(q3, [(0, V("play")), (1, V("play"))]) == []


def test_killer_name_read_with_a_slip_is_still_found():
    """1.61 (user, small window): "HILLILLY" – "THE" and one letter lost, the lexicon fit below KILLER_OK. A name
    very close to one listed name counts for it; a different (new) name stays as read."""
    r = lobby.LobbyReader.__new__(lobby.LobbyReader)
    r._names = list(lobby.KILLERS) + list(lobby.SKINS)
    assert r.fuzzy_killer("HILLILLY") == "The Hillbilly"
    assert r.fuzzy_killer("THE HILLBILY") == "The Hillbilly"
    assert r.fuzzy_killer("TRAPPER") == "The Trapper"
    assert r.fuzzy_killer("THE HUNTER") is None             # a new killer is not taken for the Huntress
    assert r.fuzzy_killer("THE NEW ONE") is None and r.fuzzy_killer("NURS") is None


def test_old_rounds_read_with_a_slip_count_for_the_killer():
    """rounds.jsonl keeps the name as read: "Hillilly" (before 1.61) shows as the Hillbilly; an own assignment
    still wins, a new killer stays as it is."""
    assert lobby.resolve_killer("Hillilly", {}) == "The Hillbilly"
    assert lobby.resolve_killer("Hillilly", {"HILLILLY": "The Nurse"}) == "The Nurse"
    assert lobby.resolve_killer("The Hunter", {}) == "The Hunter"
    assert lobby.resolve_killer("", {}) == ""


# ------------------------------------------------------------------ cross-play (farming rounds, 1.2.20)
@pytest.mark.parametrize("name, expected", [
    ("crossplay_off", True),             # the user's lobby screenshot (2000×837 copy): globe with the red cross
    ("crossplay_on_synthetic", False),   # the same globe with the cross painted over (no screenshot with it on yet)
    ("crossplay_none", None),            # ground and fire only
])
def test_crossplay_globe(name, expected):
    img = cv2.imread(os.path.join(DATA, name + ".png"))
    assert lobby.crossplay_off(img, 2000, 837) is expected


def test_crossplay_box_sits_above_the_button_and_scales():
    x, y, w, h = lobby.crossplay_box(W, H)
    bx, by, bw, bh = lobby.corner_box(W, H)
    assert x + w <= W and y + h <= by + 2 and x >= bx                 # above the button, inside its columns
    assert lobby.crossplay_box(1920, 1080)[2] == pytest.approx(w * 0.75, abs=2)
    assert lobby.crossplay_off(np.zeros((h, w, 3), np.uint8), W, H) is None
    red = np.zeros((h, w, 3), np.uint8)
    red[:] = (20, 20, 220)                                             # a red-tinted zone without a globe
    assert lobby.crossplay_off(red, W, H) is None


def test_found_lobby_carries_crossplay_off():
    """The looks while searching decide; the PLAY screen before counts only when none of them could tell."""
    q = QueueTracker()
    play = LobbyView(button="play", crossplay_off=True)
    search = LobbyView(button="cancel", time_text="0:05 EST. 2:00", crossplay_off=True)
    blind = LobbyView(button="cancel", time_text="0:06 EST. 2:00")           # globe hidden (overlay, notification)
    ready = LobbyView(button="ready", time_text="00:50", crossplay_off=True)
    t = 0.0
    for v in (play, play, search, search, blind, ready, ready):
        ev = q.update(v, t)
        t += 1
    found = [e for e in ev if e[0] == "found"][0][1]
    assert found.crossplay_off is True
    # a new search with cross-play on: the old looks do not stick
    q.update(LobbyView(button="play", crossplay_off=False), t)
    q.update(LobbyView(button="play", crossplay_off=False), t + 1)
    on = LobbyView(button="cancel", time_text="0:05 EST. 2:00", crossplay_off=False)
    for i in range(2):
        q.update(on, t + 2 + i)
    assert q.crossplay_off is False
    for i in range(2):
        ev = q.update(LobbyView(button="ready", time_text="00:50"), t + 4 + i)
    assert [e for e in ev if e[0] == "found"][0][1].crossplay_off is False
    # never seen: unknown
    q2 = QueueTracker()
    for i in range(2):
        ev = q2.update(LobbyView(button="ready", time_text="00:50"), float(i))
    assert [e for e in ev if e[0] == "found"][0][1].crossplay_off is None
