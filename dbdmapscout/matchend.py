"""When is the player no longer in the trial?  (pure logic, fed by the worker)

Evidence, from strong to weak:

* hard cues from the screen (detector.OutOfMatchWatcher): CONTINUE button of
  the result screens, currency bar of lobby/menus, loading-screen bar.
  One very clear CONTINUE or two looks in a row end the match.
* the mouse pointer: DBD shows the Windows pointer in every menu and hides it
  while you play. Pointer visible inside the DBD window for a few seconds ->
  a menu is open -> the overlay pauses; pointer gone again -> it comes back.
  A menu that stays open very long counts as "left the match".
  The pointer is only trusted once it was seen hidden while a map banner was
  up (= in the trial). If it was visible during a banner, the cue is switched
  off for that match.
* DBD window gone for a few seconds.

Automatically detected maps are watched right away. A map picked by hand (or
by scan) is only watched once the screen looked like a trial for a while, so
choosing a map in the lobby does not make it vanish again at once.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signals:
    t: float
    game: bool = True              # DBD window exists
    foreground: bool = True        # DBD is the active window
    cursor: bool | None = None     # mouse pointer visible inside DBD (None = unknown)
    banner: bool = False           # map banner visible now (= certainly in the trial)
    obs: object | None = None      # EndObservation of a screen check in this tick, else None


class MatchEndTracker:
    SOFT_DELAY = 2.5       # pointer visible this long -> menu open, pause overlay
    SOFT_RELEASE = 1.0     # pointer hidden this long -> back in the game
    SOFT_LATCH = 60.0      # pointer visible in DBD this long (summed) while paused -> match over
    ARM_QUIET = 20.0       # hand-picked map: this long in DBD without any cue -> watch for the end
    LOOKS_NEEDED = {"Ladebildschirm": 3}   # screen cues that need more looks in a row (default 2)
    GAME_GONE = 3.0

    def __init__(self):
        self.generation = None
        self.use_cursor = True         # pause the overlay while a menu is open (pointer visible)
        self.use_end = True            # hide the overlay for good once the match is over
        self.cursor_proven = False     # pointer seen hidden during a map banner (kept across matches)
        self.reset(None, None, 0.0)

    # ------------------------------------------------------------------
    def reset(self, generation, source, t: float):
        self.generation = generation
        self.source = source
        self.active = source is not None
        self.armed = source == "auto"
        self.ended = False
        self.end_reason = None
        self.end_t = None              # best guess when the match really ended (for the round timer)
        self.quiet_since = t
        self.cursor_ok = True
        self.banner_samples = 0
        self.banner_cursor = 0
        self.vis_since = None
        self.hid_since = None
        self.menu = False
        self.menu_since = None
        self.menu_start = None         # pointer visible since (start of the current menu)
        self.menu_visible = 0.0
        self.last_t = t
        self.streak = 0
        self.candidate = None
        self.candidate_since = None    # first look of the current screen-cue streak
        self.missing_since = None
        self.game_seen = False
        self.cursor_now = None

    def _end(self, reason, events, t):
        if not self.use_end:
            return events
        self.ended = True
        self.end_reason = reason
        self.end_t = t
        if self.menu:
            self.menu = False
        events.append(("match_end", reason))
        return events

    # ------------------------------------------------------------------
    def update(self, s: Signals) -> list:
        """Feed one worker tick; returns events:
        ("menu", True/False), ("match_end", reason), ("armed",), ("cursor_unreliable",)."""
        events = []
        if not self.active or self.ended:
            return events
        dt = max(0.0, min(2.0, s.t - self.last_t))
        self.last_t = s.t
        self.cursor_now = s.cursor if s.foreground else None

        # ---- DBD closed?
        if s.game:
            self.game_seen = True
            self.missing_since = None
        elif self.game_seen:
            self.missing_since = self.missing_since if self.missing_since is not None else s.t
            if self.armed and s.t - self.missing_since > self.GAME_GONE:
                return self._end("DBD wurde geschlossen", events, self.missing_since)

        # ---- pointer while the banner is up tells whether the pointer cue works here
        if s.banner and s.foreground and s.cursor is not None:
            self.banner_samples += 1
            self.banner_cursor += bool(s.cursor)
            hidden = self.banner_samples - self.banner_cursor
            if self.banner_samples >= 3 and self.banner_cursor > 0.5 * self.banner_samples:
                if self.cursor_ok:
                    self.cursor_ok = False
                    self.cursor_proven = False
                    events.append(("cursor_unreliable",))
            elif hidden >= 3 and self.cursor_ok:
                self.cursor_proven = True
        cursor_vis = (bool(s.cursor) and s.foreground and self.use_cursor and self.cursor_ok
                      and self.cursor_proven)
        menu_now = cursor_vis and s.game and not s.banner
        if menu_now:
            self.vis_since = self.vis_since if self.vis_since is not None else s.t
            self.hid_since = None
        else:
            self.vis_since = None
            if s.foreground and (s.cursor is not None or s.banner):
                self.hid_since = self.hid_since if self.hid_since is not None else s.t
            elif not s.foreground:
                self.hid_since = None

        # ---- screen cues (need two looks in a row unless very clear)
        hard = None
        if s.banner:                                  # in the trial: forget older screen cues
            self.streak = 0
            self.candidate = None
        if s.obs is not None:
            reason = getattr(s.obs, "reason", None)
            if reason:
                if reason != self.candidate:
                    self.candidate_since = s.t
                self.streak = self.streak + 1 if reason == self.candidate else 1
                self.candidate = reason
                if getattr(s.obs, "sure", False) or self.streak >= self.LOOKS_NEEDED.get(reason, 2):
                    hard = reason
            else:
                self.streak = 0
                self.candidate = None

        # ---- hand-picked map: wait until we are (probably) in a trial
        if not self.armed:
            if s.banner:                              # a map banner: certainly in a trial
                self.armed = True
            elif cursor_vis or self.streak > 0 or not s.foreground or not s.game:
                self.quiet_since = s.t
            elif s.t - self.quiet_since >= self.ARM_QUIET:
                self.armed = True
            if self.armed:
                events.append(("armed",))
            return events

        if hard and self.use_end:
            # the pointer usually shows up with the result screen, before its CONTINUE button
            since = self.candidate_since if self.candidate_since is not None else s.t
            if self.menu and self.menu_start is not None:
                since = min(since, self.menu_start)
            return self._end(hard, events, since)

        # ---- menus (pointer visible)
        if not self.menu:
            if self.vis_since is not None and s.t - self.vis_since >= self.SOFT_DELAY:
                self.menu = True
                self.menu_since = s.t
                self.menu_start = self.vis_since
                self.menu_visible = s.t - self.vis_since
                events.append(("menu", True))
        else:
            if menu_now:
                self.menu_visible += dt
            if self.menu_visible >= self.SOFT_LATCH and menu_now and self.use_end:
                return self._end("Menü/Lobby (Mauszeiger lange sichtbar)", events, self.menu_start)
            if self.hid_since is not None and s.t - self.hid_since >= self.SOFT_RELEASE:
                self.menu = False
                self.menu_since = None
                self.menu_start = None
                events.append(("menu", False))
        return events

    # ------------------------------------------------------------------
    def describe(self) -> str:
        """Short state text for the UI."""
        if not self.active:
            return "keine Map angezeigt"
        if self.ended:
            return f"Runde vorbei ({self.end_reason})"
        if not self.armed:
            return "wartet, bis du im Match bist (Map manuell gewählt)"
        parts = []
        if self.menu:
            parts.append("Menü offen – Overlay pausiert")
        elif self.candidate:
            parts.append(f"{self.candidate}? ({self.streak}/2)")
        else:
            parts.append("im Match")
        if not self.use_end:
            parts.append("Ausblenden nach der Runde aus")
        if not self.use_cursor:
            pass
        elif not self.cursor_ok:
            parts.append("Mauszeiger-Hinweis aus")
        elif not self.cursor_proven:
            parts.append("Mauszeiger-Hinweis ab dem nächsten Map-Banner")
        elif self.cursor_now is None:
            parts.append("Mauszeiger: –")
        else:
            parts.append("Mauszeiger sichtbar" if self.cursor_now else "Mauszeiger verborgen")
        return " · ".join(parts)
