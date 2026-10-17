"""State machine that decides when the overlay pauses (menus) or ends (match over)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout.detector import EndObservation  # noqa: E402
from dbdmapscout.matchend import MatchEndTracker, Signals  # noqa: E402


def run(tr, seconds, t0=0.0, step=0.2, **kw):
    """Feed identical signals for `seconds`; returns (events, end time)."""
    events, t = [], t0
    while t < t0 + seconds - 1e-9:
        t = round(t + step, 3)
        obs = kw.get("obs")
        events += tr.update(Signals(t=t, game=kw.get("game", True), foreground=kw.get("fg", True),
                                    cursor=kw.get("cursor", False), banner=kw.get("banner", False),
                                    obs=obs() if callable(obs) else obs))
    return events, t


def fresh(source="auto", proven=True):
    tr = MatchEndTracker()
    tr.cursor_proven = proven          # normally learned from the first map banner
    tr.reset(1, source, 0.0)
    return tr


CONTINUE = EndObservation(continue_fit=0.0, reason="Ergebnisbildschirm", sure=True)
LOBBY = EndObservation(currency_groups=3, currency_digits=14, reason="Lobby/Menü")
NOTHING = EndObservation()


def test_in_game_nothing_happens():
    tr = fresh()
    ev, _ = run(tr, 120, cursor=False, obs=NOTHING)
    assert ev == []
    assert not tr.ended and not tr.menu


def test_result_screen_pauses_then_ends():
    tr = fresh()
    ev, t = run(tr, 30, cursor=False)
    ev, t = run(tr, 3, t0=t, cursor=True)                     # result screen appears, pointer visible
    assert ev == [("menu", True)]
    ev, t = run(tr, 0.2, t0=t, cursor=True, obs=CONTINUE)       # one clear CONTINUE is enough
    assert ev == [("match_end", "Ergebnisbildschirm")]
    assert tr.ended


def test_escape_menu_in_trial_comes_back():
    tr = fresh()
    ev, t = run(tr, 20, cursor=False)
    ev, t = run(tr, 6, t0=t, cursor=True, obs=NOTHING)          # ESC menu: no hard cue
    assert ev == [("menu", True)]
    ev, t = run(tr, 2, t0=t, cursor=False)
    assert ev == [("menu", False)]
    assert not tr.ended


def test_short_pointer_flash_is_ignored():
    tr = fresh()
    ev, t = run(tr, 1.6, cursor=True)
    ev2, _ = run(tr, 5, t0=t, cursor=False)
    assert ev + ev2 == []


def test_menu_open_very_long_ends_match():
    tr = fresh()
    ev, t = run(tr, 70, cursor=True, obs=NOTHING)              # lobby whose screen cues are not recognised
    assert ("menu", True) in ev
    assert ev[-1][0] == "match_end" and "Mauszeiger" in ev[-1][1]


def test_lobby_needs_two_looks():
    tr = fresh()
    ev = tr.update(Signals(t=1.0, obs=LOBBY))
    assert ev == []
    ev = tr.update(Signals(t=1.5, obs=NOTHING))                 # streak broken
    ev += tr.update(Signals(t=2.0, obs=LOBBY))
    assert ev == []
    ev = tr.update(Signals(t=2.5, obs=LOBBY))
    assert ev == [("match_end", "Lobby/Menü")]


def test_pointer_visible_during_banner_disables_pointer_cue():
    tr = fresh()
    ev, t = run(tr, 3, cursor=True, banner=True)
    assert ("cursor_unreliable",) in ev
    ev, t = run(tr, 60, t0=t, cursor=True)
    assert ev == []                                            # no menu pause, no end from the pointer
    ev, t = run(tr, 0.2, t0=t, cursor=True, obs=CONTINUE)
    assert ev == [("match_end", "Ergebnisbildschirm")]      # screen cues still work


def test_alt_tab_does_not_count_as_menu():
    tr = fresh()
    ev, _ = run(tr, 60, cursor=True, fg=False)
    assert ev == []


def test_manual_map_in_lobby_is_not_hidden():
    tr = fresh("manual")
    ev, t = run(tr, 30, cursor=True, obs=LOBBY)                 # picked in the lobby
    assert ev == [] and not tr.armed
    ev, t = run(tr, 21, t0=t, cursor=False, obs=NOTHING)         # match started, quiet for a while
    assert ev == [("armed",)] and tr.armed
    ev, t = run(tr, 0.2, t0=t, obs=CONTINUE)
    assert ev == [("match_end", "Ergebnisbildschirm")]


def test_manual_map_armed_by_banner():
    tr = fresh("manual")
    ev, _ = run(tr, 0.4, banner=True)
    assert ("armed",) in ev


def test_game_closed():
    tr = fresh()
    ev, t = run(tr, 5)
    ev, t = run(tr, 4, t0=t, game=False, fg=False, cursor=None)
    assert ev == [("match_end", "DBD wurde geschlossen")]


def test_keep_overlay_after_match_but_pause_in_menus():
    tr = fresh()
    tr.use_end = False
    ev, t = run(tr, 5, cursor=True, obs=CONTINUE)
    assert ev == [("menu", True)]
    ev, t = run(tr, 60, t0=t, cursor=True, obs=LOBBY)
    assert ev == [] and not tr.ended
    ev, t = run(tr, 2, t0=t, cursor=False)
    assert ev == [("menu", False)]


def test_pointer_cue_off():
    tr = fresh()
    tr.use_cursor = False
    ev, t = run(tr, 60, cursor=True)
    assert ev == []
    ev, t = run(tr, 0.4, t0=t, obs=LOBBY)
    assert ev == [("match_end", "Lobby/Menü")]


def test_nothing_after_end():
    tr = fresh()
    run(tr, 0.2, obs=CONTINUE)
    assert tr.ended
    ev, _ = run(tr, 60, cursor=True, obs=LOBBY)
    assert ev == []


def test_pointer_only_trusted_after_banner_proof():
    tr = fresh(proven=False)
    ev, t = run(tr, 30, cursor=True)                           # pointer visible, but never proven hidden
    assert ev == [] and not tr.menu
    tr.reset(2, "auto", t)                                     # next match: banner with hidden pointer
    ev, t = run(tr, 2, t0=t, cursor=False, banner=True)
    assert tr.cursor_proven
    ev, t = run(tr, 3, t0=t, cursor=True)
    assert ev == [("menu", True)]


def test_proof_survives_next_match_without_banner_samples():
    tr = fresh(proven=False)
    run(tr, 2, cursor=False, banner=True)
    tr.reset(2, "manual", 10.0)
    assert tr.cursor_proven


def test_stale_streak_does_not_skip_two_looks():
    tr = fresh("manual", proven=False)
    run(tr, 10, obs=LOBBY)                                        # lobby looks while unarmed
    ev, t = run(tr, 0.4, t0=10, banner=True)                      # banner arms it
    assert ("armed",) in ev
    ev = tr.update(Signals(t=t + 1, obs=LOBBY))
    assert ev == []                                               # one look is not enough


def test_loading_screen_needs_three_looks():
    tr = fresh()
    load = EndObservation(loading=True, static=True, reason="Ladebildschirm")
    assert tr.update(Signals(t=1, obs=load)) == []
    assert tr.update(Signals(t=1.5, obs=load)) == []
    assert tr.update(Signals(t=2, obs=load)) == [("match_end", "Ladebildschirm")]


def test_latch_counts_only_time_with_visible_pointer_in_dbd():
    tr = fresh()
    ev, t = run(tr, 10, cursor=True)                              # ESC menu -> pause
    assert ev == [("menu", True)]
    ev, t = run(tr, 120, t0=t, cursor=True, fg=False)             # alt-tabbed away for 2 min
    ev, t = run(tr, 5, t0=t, cursor=True)                         # back, menu still open
    assert not any(e[0] == "match_end" for e in ev)


def test_end_time_result_screen_uses_pointer_start():
    tr = fresh()
    ev, t = run(tr, 30, cursor=False)
    ev, t2 = run(tr, 5, t0=t, cursor=True)                      # result screen, CONTINUE not yet readable
    ev, _ = run(tr, 0.2, t0=t2, cursor=True, obs=CONTINUE)
    assert tr.ended and abs(tr.end_t - (t + 0.2)) < 1e-6        # when the pointer showed up


def test_end_time_two_looks_uses_first_look():
    tr = fresh()
    tr.update(Signals(t=1.0, obs=LOBBY))
    tr.update(Signals(t=2.5, obs=LOBBY))
    assert tr.ended and tr.end_t == 1.0


def test_end_time_latch_is_start_of_menu_not_after_60s():
    tr = fresh()
    ev, t = run(tr, 10, cursor=False)
    ev, _ = run(tr, 70, t0=t, cursor=True, obs=NOTHING)
    assert tr.ended and abs(tr.end_t - (t + 0.2)) < 1e-6


def test_end_time_game_closed():
    tr = fresh()
    ev, t = run(tr, 5)
    run(tr, 4, t0=t, game=False, fg=False, cursor=None)
    assert tr.ended and abs(tr.end_t - (t + 0.2)) < 1e-6


def test_in_trial_for_scan_throttling():
    tr = fresh()                                  # detected map: watched right away
    assert tr.in_trial
    run(tr, 3, obs=CONTINUE)
    assert tr.ended and not tr.in_trial           # match over: full scan rate for the next banner
    manual = fresh(source="manual")               # picked in the lobby: not yet in a trial
    assert not manual.in_trial
    assert not MatchEndTracker().in_trial         # nothing on display


def test_banner_scans_slow_down_in_the_menus_only():
    """1.6.4 (user: optimise): full rate while reading a banner, after a loading screen and for two minutes after the
    lobby button; 1/s in the match, in the lobby and in the other menus; simulation keeps its full rate."""
    from dbdmapscout.worker import scan_rate
    far = 1e9

    def rate(**kw):
        args = dict(in_match=False, session=False, since_button=far, since_loading=far, live=True, lobby_visible=False)
        args.update(kw)
        return scan_rate(5, **args)
    assert rate() == 1                                       # menus, store, bloodweb
    assert rate(session=True) == 5 and rate(session=True, in_match=True) == 5
    assert rate(in_match=True) == 1 and rate(lobby_visible=True, since_button=0) == 1
    assert rate(since_button=30) == 5 and rate(since_button=121) == 1        # READY pressed → loading → banner
    assert rate(since_loading=10) == 5 and rate(since_loading=91) == 1
    assert rate(live=False) == 5 and scan_rate(0.2, in_match=False, session=False, since_button=far,
                                                since_loading=far, live=True, lobby_visible=False) == 1
