"""1.6: the end of the loading screen into a match – the moment OBS should start recording (the spawn), long
before the map banner. Pure logic, fed by the worker with one look per second while it is armed.

Armed only by a lobby the queue tracker found (search -> lobby, or a custom game): the loading screen back to the
menus after a match must never start a recording, so one lobby arms one start. A loading screen is the filled
progress bar on an almost black picture (detector.has_loading_bar + is_dark, the same signs the round end
uses), seen LOADING_LOOKS times; the match has begun when the picture is no longer dark BRIGHT_LOOKS times in a
row and no lobby button is on screen."""
from __future__ import annotations

from dataclasses import dataclass

LOADING_LOOKS = 2
BRIGHT_LOOKS = 2
ARM_MAX_S = 15 * 60         # a lobby older than this arms nothing any more (left without the PLAY screen seen)


@dataclass
class MatchStart:
    armed_t: float | None = None
    loading: int = 0           # looks at the loading screen since it was armed
    bright: int = 0            # bright looks in a row after the loading screen
    started_t: float | None = None

    @property
    def armed(self) -> bool:
        return self.armed_t is not None

    def arm(self, t: float):
        self.armed_t, self.loading, self.bright, self.started_t = t, 0, 0, None

    def disarm(self):
        self.armed_t, self.loading, self.bright = None, 0, 0

    def update(self, t: float, loading_bar: bool, dark: bool, lobby_button: bool) -> bool:
        """One look. True once: the match has just begun (the loading screen is over)."""
        if self.armed_t is None:
            return False
        if t - self.armed_t > ARM_MAX_S and self.loading < LOADING_LOOKS:
            self.disarm()
            return False
        if loading_bar and dark:
            self.loading += 1
            self.bright = 0
            return False
        if lobby_button:                            # still (or again) in the lobby: no match yet
            self.bright = 0
            if self.loading >= LOADING_LOOKS:       # back from a loading screen into a lobby (someone left)
                self.loading = 0
            return False
        if self.loading < LOADING_LOOKS:
            return False
        if dark:                                    # black between loading screen and match: wait
            self.bright = 0
            return False
        self.bright += 1
        if self.bright >= BRIGHT_LOOKS:
            self.started_t = t
            self.disarm()
            return True
        return False

    def describe(self) -> str:
        if self.armed_t is None:
            return "aus" if self.started_t is None else "Match begonnen"
        return f"wartet (Ladebildschirm {self.loading}×, hell {self.bright}×)"
