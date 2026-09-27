"""Round timer: runs while a map is on display, pure logic (testable)."""


class RoundTimer:
    RESTART = 90.0      # an auto detection restarts a running timer only after this long (same banner read twice)

    def __init__(self):
        self.start_t = None      # map shown (time.time())
        self.end_t = None        # map gone (None = still running)

    @property
    def running(self) -> bool:
        return self.start_t is not None and self.end_t is None

    def start(self, t: float):
        """Map appeared: count from zero."""
        self.start_t, self.end_t = t, None

    def detected(self, t: float) -> bool:
        """A map banner was read. Starts a new round unless the timer only just started. True = restarted."""
        if self.running and t - self.start_t < self.RESTART:
            return False
        self.start(t)
        return True

    def stop(self, t: float) -> bool:
        """Map gone: freeze the time. True if it was running."""
        if not self.running:
            return False
        self.end_t = max(self.start_t, t)
        return True

    def elapsed(self, now: float) -> float:
        if self.start_t is None:
            return 0.0
        return max(0.0, (self.end_t if self.end_t is not None else now) - self.start_t)
