"""Status line wording and recording a hotkey by pressing it."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.hotkeys import combo_from_keys, modifier_name, parse  # noqa: E402
from dbdmapscout.status import DOT_STYLE, user_state  # noqa: E402


# ------------------------------------------------------------------ status line
def test_waiting_for_dbd_then_match():
    assert user_state("DBD-Fenster nicht gefunden – beobachte Hauptbildschirm").text == "Wartet auf DBD"
    s = user_state("DBD gefunden (3440×1440) – warte auf Map-Banner", game_found=True)
    assert (s.kind, s.text) == ("wait", "Wartet auf das nächste Match")


def test_in_match_menu_and_round_over():
    common = dict(game_found=True, has_map=True, map_label="Treatment Theatre")
    assert user_state(**common).text == "Im Match: Treatment Theatre"
    assert user_state(**common, menu_paused=True).kind == "menu"
    s = user_state(**common, hidden_after_match=True)
    assert s.kind == "done" and "Runde vorbei" in s.text
    assert user_state(**common, visible_wanted=False).text == "Karte ausgeblendet (Treatment Theatre)"


def test_problems_always_win():
    s = user_state("Aufnahme ist schwarz – DBD im Modus „Fenster-Vollbild“ betreiben", game_found=True,
                   has_map=True, map_label="X")
    assert s.kind == "err" and "Fenster-Vollbild" in s.text
    assert user_state("DBD ist minimiert", game_found=True).kind == "err"


def test_auto_detect_off_and_simulation():
    assert "Erkennung ist aus" in user_state(game_found=True, auto_detect=False).text
    assert "Simulation" in user_state("Simulation: x.png", simulate=True).text


def test_every_kind_has_a_dot_style():
    assert set(DOT_STYLE) == {"err", "idle", "wait", "ok", "menu", "done"}


# ------------------------------------------------------------------ hotkey recording
def test_modifiers_are_recognised():
    assert modifier_name("Control_L") == "ctrl" and modifier_name("Alt_R") == "alt"
    assert modifier_name("Shift_L") == "shift" and modifier_name("m") is None


def test_combo_from_keys():
    assert combo_from_keys({"alt", "ctrl"}, "m") == ("ctrl+alt+m", None)          # fixed order
    assert combo_from_keys({"ctrl", "shift"}, "M") == ("ctrl+shift+m", None)       # Shift gives capitals
    assert combo_from_keys({"ctrl", "alt"}, "Right") == ("ctrl+alt+right", None)
    assert combo_from_keys({"shift"}, "F8") == ("shift+f8", None)
    assert combo_from_keys(set(), "F13") == ("f13", None)                          # no normal key uses it
    assert combo_from_keys({"ctrl"}, "KP_Add") == ("ctrl+numpadplus", None)
    for combo, _ in (combo_from_keys({"ctrl", "alt"}, "m"), combo_from_keys({"shift"}, "F8")):
        parse(combo)                                                               # registrable


def test_keys_that_would_steal_normal_typing_are_refused():
    assert combo_from_keys(set(), "m")[0] is None                  # plain letter: gone in every program
    assert combo_from_keys({"shift"}, "M")[0] is None              # capital letters in the chat
    assert combo_from_keys(set(), "F8")[0] is None
    assert "Strg" in combo_from_keys({"shift"}, "a")[1]


def test_still_holding_modifiers_and_unknown_keys():
    assert combo_from_keys({"ctrl"}, "Control_L") == (None, None)
    combo, why = combo_from_keys({"ctrl"}, "dead_circumflex")
    assert combo is None and "geht nicht" in why


def test_shift_digit_uses_the_windows_key_code():
    assert combo_from_keys({"ctrl", "shift"}, "exclam", keycode=0x31) == ("ctrl+shift+1", None)
    assert combo_from_keys({"ctrl", "alt"}, "adiaeresis", keycode=0x41 + 25)[0] == "ctrl+alt+z"
