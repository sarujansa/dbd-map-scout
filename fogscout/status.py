"""What the player should read in the status line at the top (pure logic, testable).

The worker reports technical texts ("DBD gefunden (3440×1440) – warte auf Map-Banner"); the
player wants to know where things stand. Errors of the worker always win, since they need action.
"""
from __future__ import annotations

from dataclasses import dataclass

from .i18n import _


@dataclass
class State:
    kind: str      # dot colour: err | idle | wait | ok | menu | done
    text: str


DOT_STYLE = {"err": "err", "idle": "idle", "wait": "warn", "ok": "ok", "menu": "warn", "done": "info"}


# 1.3.6: the dot on the tray icon (theme.DOT colours) – None = plain icon (DBD not running)
TRAY_DOT = {"err": "err", "ok": "ok", "menu": "ok", "wait": "idle", "done": "idle", "idle": "idle"}


def tray_dot(state: State, unsure: bool = False, game_found: bool = True) -> str | None:
    """Green = map on display, yellow = shown but doubtful, red = a problem, grey = DBD runs and it waits."""
    if state.kind == "err":
        return "err"
    if unsure and state.kind in ("ok", "menu"):
        return "warn"
    if state.kind == "idle" and not game_found:
        return None
    return TRAY_DOT.get(state.kind, "idle")


def is_problem(worker_status: str) -> bool:
    low = (worker_status or "").lower()
    return any(w in low for w in ("fehl", "schwarz", "minimiert", "abgestürzt",       # German texts
                                   "fail", "black", "minimi", "crash"))                # English texts


def user_state(worker_status: str = "", *, auto_detect: bool = True, game_found: bool = False,
               simulate: bool = False, has_map: bool = False, map_label: str = "",
               visible_wanted: bool = True, hidden_after_match: bool = False, menu_paused: bool = False) -> State:
    if is_problem(worker_status):
        return State("err", worker_status)
    shown = has_map and visible_wanted and not hidden_after_match
    if shown and menu_paused:
        return State("menu", _("Im Menü – Karte pausiert ({map})", map=map_label))
    if shown:
        return State("ok", _("Im Match: {map}", map=map_label) if map_label else _("Karte eingeblendet"))
    if has_map and hidden_after_match:
        return State("done", _("Runde vorbei – wartet auf das nächste Match"))
    if has_map and not visible_wanted:
        return State("idle", _("Karte ausgeblendet ({map})", map=map_label))
    if not game_found and not simulate:
        return State("idle", _("Wartet auf DBD"))
    if not auto_detect:
        return State("wait", _("DBD läuft – automatische Erkennung ist aus (Map von Hand wählen)"))
    return State("wait", _("Wartet auf das nächste Match") if not simulate else _("Simulation – wartet auf das Map-Banner"))
