"""Lobby: matchmaking state, waiting time and role – read from the button bottom right.

Measured on the user's screenshots (3440×1440, English game). The lobby fills the whole window, the
button sits at the real right window edge; positions are therefore measured from the right (x) and
the top (y) of the window in units of the 16:9 picture width.

    PLAY                                   not searching
    CANCEL, below "0:06   EST. 4:39"       searching (DBD shows the time already waited)
    READY,  below "00:59"                  lobby found (countdown)
    CANCEL, below "00:34" (no EST.)        lobby, ready pressed
    READY,  nothing below                  custom game (no queue, no countdown) – unless it comes right after a
                                           search or in a lobby: a public lobby before its countdown starts

Killers see their killer's name left below the button (searching and lobby), survivors never do. The
name is matched against KILLERS (lexicon fit, like the button word); a name not on the list (a new
killer, or a skin: some skins show their own name there, e.g. "MURDEROUS GRIZZLY") is kept as read
instead of being forced onto a wrong one – the user assigns it once (settings "killer_aliases").
After the match the result screen names the four categories – BRUTALITY … for killers,
OBJECTIVES … for survivors – which confirms the role (also in custom games).

Only screen pixels, like the rest of the detection. ``QueueTracker`` is pure logic (testable).
"""
from __future__ import annotations

import difflib
import functools
import re
from dataclasses import dataclass, field

from .ocr import LexiconScorer, best_path_logp
from .textnorm import fold

BUTTON_WORDS = ("PLAY", "CANCEL", "READY")
BUTTON_OK = -2.0          # fit of the button word (0 = perfect); other screens score -7 and worse
# as the English game shows them below the button (new killers: add here; unknown ones are kept as read)
KILLERS = ("The Trapper", "The Wraith", "The Hillbilly", "The Nurse", "The Shape", "The Hag", "The Doctor",
           "The Huntress", "The Cannibal", "The Nightmare", "The Pig", "The Clown", "The Spirit", "The Legion",
           "The Plague", "The Ghost Face", "The Demogorgon", "The Oni", "The Deathslinger", "The Executioner",
           "The Blight", "The Twins", "The Trickster", "The Nemesis", "The Cenobite", "The Artist", "The Onryō",
           "The Dredge", "The Mastermind", "The Knight", "The Skull Merchant", "The Singularity", "The Xenomorph",
           "The Good Guy", "The Unknown", "The Lich", "The Dark Lord", "The Houndmaster", "The Ghoul",
           "The Animatronic", "The Krasue", "The First")
# Legendary outfits show their own name below the button instead of the killer's. Only outfits whose
# killer is confirmed (official news / wiki); anything else the user assigns once in the statistics.
SKINS = {"Murderous Grizzly": "The Oni", "The Minotaur": "The Oni", "Ferryman of the Underworld": "The Blight",
         "Naughty Bear": "The Trapper", "Frank Stone": "The Trapper", "Were-Elk": "The Huntress",
         "Hunk": "The Legion", "William Afton": "The Animatronic"}
KILLER_OK = -3.0          # listed killers fit about +1, a killer missing from the list -22 and worse
FUZZY_OK, FUZZY_GAP = 0.88, 0.12   # text as read vs a listed name (without "The"): this alike, and clearly the best
KILLER_CATEGORIES = ("BRUTALITY", "DEVIOUSNESS", "HUNTER", "SACRIFICE")
SURVIVOR_CATEGORIES = ("OBJECTIVES", "SURVIVAL", "ALTRUISM", "BOLDNESS")

# (from the right edge, to the right edge) in 16:9 widths, (top, bottom) in heights
BUTTON_ZONE = (0.275, 0.10, 0.878, 0.942)
NAME_ZONE = (0.275, 0.13, 0.950, 0.985)
TIME_ZONE = (0.13, 0.02, 0.950, 0.985)
# result screen: category headers, (from the left edge, to) in 16:9 widths
RESULT_ZONE = (0.05, 0.42, 0.198, 0.232)


def _vw(W, H):
    return min(W, H * 16 / 9)


def _right_box(zone, W, H):
    r0, r1, y0, y1 = zone
    vw = _vw(W, H)
    x0, x1 = int(W - r0 * vw), int(W - r1 * vw)
    return x0, int(y0 * H), max(1, x1 - x0), max(1, int(y1 * H) - int(y0 * H))


def plain_name(text: str) -> str:
    """A name not on the list, as read: letters and spaces only, "THE FOO" -> "The Foo"."""
    words = re.sub(r"[^A-Za-z' ]+", " ", text or "").split()
    return " ".join(w.capitalize() for w in words)


def killer_label(name: str) -> str:
    """Short form for tables: "The Nurse" -> "Nurse"."""
    return name[4:] if name.startswith("The ") else name


def _core(name: str) -> str:
    s = fold(name)
    return s[3:] if s.startswith("THE") and len(s) > 6 else s


@functools.lru_cache(maxsize=512)
def fuzzy_killer(text: str, names: tuple | None = None) -> str | None:
    """A listed name the text as read is very close to (user 1.61: "HILLILLY" in a small window – "THE" and a
    letter lost, the lexicon fit too low). Only when one name is clearly the best: a new killer stays as read."""
    names = names or tuple(KILLERS) + tuple(SKINS)
    key = _core(text or "")
    if len(key) < 5:
        return None
    scored = sorted(((difflib.SequenceMatcher(None, key, _core(n)).ratio(), n) for n in names), reverse=True)
    best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    return best[1] if best[0] >= FUZZY_OK and best[0] - second >= FUZZY_GAP else None


def resolve_killer(name: str, aliases: dict) -> str:
    """The killer behind a name as read (skin / unknown name) – user assignments keyed by fold(name),
    so "MURDEROUSGRIZZLY" and "Murderous Grizzly" are the same; else a name read with a slip that is very close
    to a listed killer ("Hillilly" from before 1.61) counts for it."""
    if not name:
        return name
    own = (aliases or {}).get(fold(name))
    if own:
        return own
    if name in KILLERS:
        return name
    hit = fuzzy_killer(name)
    return SKINS.get(hit, hit) if hit else name


def corner_box(W: int, H: int):
    """(x, y, w, h) of the part of the window the lobby reader needs (one grab)."""
    boxes = [_right_box(z, W, H) for z in (BUTTON_ZONE, NAME_ZONE, TIME_ZONE)]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    return x0, y0, x1 - x0, y1 - y0


def result_box(W: int, H: int):
    x0, x1, y0, y1 = RESULT_ZONE
    vw = _vw(W, H)
    return int(x0 * vw), int(y0 * H), int((x1 - x0) * vw), int((y1 - y0) * H)


_CLOCK = re.compile(r"(\d{1,2})\s*[:.;：]+\s*(\d{2})")     # OCR sometimes doubles the colon


@dataclass
class LobbyView:
    button: str | None = None       # play | cancel | ready | None (no lobby button)
    fit: float | None = None
    name: str = ""                  # text left below the button (killer name)
    time_text: str = ""             # text right below the button (waited time + EST. / countdown)
    killer: str = ""                # name from KILLERS, or the name as read if it is not on the list

    @property
    def has_name(self) -> bool:
        return sum(ch.isalpha() and ch.isascii() for ch in self.name) >= 4

    @property
    def has_est(self) -> bool:
        return "EST" in self.time_text.upper()

    @property
    def has_clock(self) -> bool:
        return bool(_CLOCK.search(self.time_text))

    @property
    def elapsed(self) -> float | None:
        """Time already waited as shown by DBD ("7:29" before "EST.")."""
        if not self.has_est:
            return None
        m = _CLOCK.search(self.time_text.upper().split("EST")[0])
        if not m or int(m.group(2)) >= 60:
            return None
        return int(m.group(1)) * 60 + int(m.group(2))

    @property
    def countdown(self) -> float | None:
        """Seconds left on the lobby countdown ("00:53"), lobby screens only."""
        if self.kind != "lobby":
            return None
        m = _CLOCK.search(self.time_text)
        return int(m.group(1)) * 60 + int(m.group(2)) if m and int(m.group(2)) < 60 else None

    @property
    def kind(self) -> str | None:
        """play | search | lobby | custom | None"""
        if self.button == "play":
            return "play"
        if self.button == "cancel" and self.has_est:
            return "search"
        if self.button in ("cancel", "ready") and self.has_clock:
            return "lobby"
        if self.button == "ready" and not self.has_name and not self.time_text.strip():
            return "custom"
        return None

    @property
    def role(self) -> str | None:
        if self.kind not in ("search", "lobby"):
            return None
        return "killer" if self.has_name else "survivor"


class LobbyReader:
    def __init__(self, recognizer):
        self.rec = recognizer
        self.scorer = LexiconScorer([fold(w) for w in BUTTON_WORDS])
        self._names = list(KILLERS) + list(SKINS)
        self.killers = LexiconScorer([fold(k) for k in self._names])

    def read(self, corner, W: int, H: int) -> LobbyView:
        """``corner``: the picture of corner_box(W, H)."""
        view = LobbyView()
        if corner is None or corner.size == 0:
            return view
        cx, cy = corner_box(W, H)[:2]

        def crop(zone):
            x, y, w, h = _right_box(zone, W, H)
            return corner[max(0, y - cy):max(0, y - cy) + h, max(0, x - cx):max(0, x - cx) + w]

        b = crop(BUTTON_ZONE)
        if b.size == 0:
            return view
        g = self.rec.groups(self.rec.probs(b))
        s = self.scorer.score(g)
        view.fit = float(s.max() - best_path_logp(g))
        if view.fit < BUTTON_OK:
            return view
        view.button = BUTTON_WORDS[int(s.argmax())].lower()
        if view.button != "play":
            for zone, attr in ((NAME_ZONE, "name"), (TIME_ZONE, "time_text")):
                img = crop(zone)
                if img.size:
                    p = self.rec.probs(img)
                    setattr(view, attr, self.rec.text(p).strip())
                    if attr == "name" and view.has_name:
                        view.killer = self.killer_name(self.rec.groups(p), view.name)
        return view

    def killer_name(self, groups, text: str) -> str:
        s = self.killers.score(groups)
        if len(s) and float(s.max() - best_path_logp(groups)) >= KILLER_OK:
            name = self.killers.strings[int(s.argmax())]
            hit = next(n for n in self._names if fold(n) == name)
            return SKINS.get(hit, hit)                   # an outfit counts for its killer
        hit = self.fuzzy_killer(text)
        return SKINS.get(hit, hit) if hit else plain_name(text)

    def fuzzy_killer(self, text: str) -> str | None:
        return fuzzy_killer(text, tuple(self._names))

    def result_role(self, img) -> str | None:
        """Role from the category headers of the result screen (picture of result_box)."""
        if img is None or img.size == 0:
            return None
        text = fold(self.rec.text(self.rec.probs(img)))
        killer = sum(w in text for w in KILLER_CATEGORIES)
        survivor = sum(w in text for w in SURVIVOR_CATEGORIES)
        if killer >= 2 and survivor == 0:
            return "killer"
        if survivor >= 2 and killer == 0:
            return "survivor"
        return None


# ------------------------------------------------------------------ queue logic (pure)
@dataclass
class Found:
    t: float                         # when the lobby was found
    wait: float | None               # seconds from starting the search to the lobby (None: custom game)
    role: str | None
    custom: bool = False
    killer: str = ""                 # the own killer (role killer only)


@dataclass
class QueueTracker:
    """Turns single looks at the lobby button into: search started, cancelled, lobby found.

    A new state needs CONFIRM looks in a row (one misread word must not end a search). Looks without
    a lobby button (other menus, loadout, store …) change nothing: the search keeps running there.
    """
    CONFIRM: int = 2
    REMIND: float = 15                # lobby countdown at/below this and READY not pressed -> remind once
    MAX_SEARCH: float = 3 * 3600      # a "search" older than this is stale (DBD closed meanwhile …)
    state: str = "idle"               # idle | search | lobby | custom
    role: str | None = None
    search_start: float | None = None
    found: Found | None = None
    _pending: tuple | None = None     # (kind, count, first t)
    _reminded: bool = False
    _starts: list = field(default_factory=list)
    _killers: dict = field(default_factory=dict)   # name -> looks (the most read one wins)

    @property
    def killer(self) -> str:
        return max(self._killers, key=self._killers.get) if self.role == "killer" and self._killers else ""

    def update(self, view: LobbyView | None, t: float) -> list:
        """Returns events: ("search",) ("cancel",) ("left",) ("found", Found) ("role", role)
        ("remind", seconds left). ("left",): back on PLAY from a lobby / custom game – the lobby found
        before is gone (left, dodged, or the match is over) and must not stick to anything."""
        events = []
        kind = view.kind if view is not None else None
        if kind == "custom" and self.state in ("search", "lobby"):
            # 1.64.4 (user: "Custom Game" in a normal match): a public lobby shows READY with nothing below until
            # its countdown starts, and again when someone leaves – a custom game never comes from a search
            kind = "lobby"
        if kind is None:
            if self.state == "search" and self.search_start is not None and t - self.search_start > self.MAX_SEARCH:
                self._reset()
            return events
        role = view.role
        if role == "killer" and view.killer:
            self._killers[view.killer] = self._killers.get(view.killer, 0) + 1
        if role and role != self.role and kind in ("search", "lobby"):
            self.role = role
            events.append(("role", role))
        if kind == "search":
            el = view.elapsed
            if el is not None and 0 <= el < self.MAX_SEARCH:
                self._starts.append(t - el)          # DBD's own counter: exact even if the start was missed
        if (kind == "lobby" and self.state == "lobby" and view.button == "ready" and not self._reminded
                and view.countdown is not None and 0 < view.countdown <= self.REMIND):
            self._reminded = True                    # READY still not pressed, the lobby is about to start
            events.append(("remind", view.countdown))
        if self._pending and self._pending[0] == kind:
            self._pending = (kind, self._pending[1] + 1, self._pending[2])
        else:
            self._pending = (kind, 1, t)
        if self._pending[1] < self.CONFIRM or self._state_of(kind) == self.state:
            return events
        first = self._pending[2]
        if kind == "search":
            self.state = "search"
            if not self._starts:
                self._starts.append(first)
            self.search_start = sorted(self._starts)[len(self._starts) // 2]
            events.append(("search",))
        elif kind == "lobby":
            wait = None
            if self.state == "search" and self.search_start is not None:
                start = sorted(self._starts)[len(self._starts) // 2] if self._starts else self.search_start
                wait = max(0.0, first - start)
            self.found = Found(first, wait, self.role, killer=self.killer)
            self.state = "lobby"
            self._reminded = False
            self._starts = []
            events.append(("found", self.found))
        elif kind == "custom":
            self.found = Found(first, None, None, custom=True)
            self.state = "custom"
            self.role = None
            self._starts, self._killers = [], {}
            events.append(("found", self.found))
        elif kind == "play":
            if self.state == "search":
                events.append(("cancel",))
            elif self.state in ("lobby", "custom"):
                events.append(("left",))
                self.found = None
            self._reset()
        return events

    @staticmethod
    def _state_of(kind):
        return {"play": "idle"}.get(kind, kind)

    def _reset(self):
        self.state, self.search_start, self._starts, self.role, self._killers = "idle", None, [], None, {}

    def searching_since(self, t: float) -> float | None:
        return t - self.search_start if self.state == "search" and self.search_start is not None else None

    def take(self, t: float, max_age: float = 900.0) -> Found | None:
        """The lobby that led to the match now starting (once)."""
        f, self.found = self.found, None
        return f if f is not None and 0 <= t - f.t <= max_age else None
