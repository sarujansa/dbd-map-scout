"""Keep the overlay inside the black bars of an ultrawide screen (pure logic, testable).

DBD renders 16:9 centred; on 21:9 the bars left/right are empty. A map placed there must not
reach into the game picture. Which bar applies:
  auto, top-left, bottom-left      -> left bar
  top-right, bottom-right          -> right bar
  custom                           -> the bar the overlay starts in (left edge in the left bar,
                                      right edge in the right bar); placed over the game on
                                      purpose (both edges inside the picture) -> no limit
"""
from __future__ import annotations

MIN_BAR = 200          # narrower bars (e.g. 16:10 letterbox) are not used for the map


def bar_width(gw: float, gh: float) -> float:
    """Width of one black bar left/right of the centred 16:9 picture (0 if none)."""
    return max(0.0, (gw - gh * 16 / 9) / 2)


def bar_side(anchor: str, x: float, w: float, gx: float, gw: float, bar: float):
    """'left', 'right' or None (no bar to stay in)."""
    if bar < MIN_BAR:
        return None
    if anchor in ("auto", "top-left", "bottom-left"):
        return "left"
    if anchor in ("top-right", "bottom-right"):
        return "right"
    if x < gx + bar:
        return "left"
    if x + w > gx + gw - bar:
        return "right"
    return None


def max_width(bar: float, margin: float) -> float:
    return bar - 2 * margin


def fit_height(height: int, avail: float, img_w: int, img_h: int, minimum: int = 80) -> int:
    """Largest height <= ``height`` at which the scaled map (compose: round(img_w * h / img_h)) is at
    most ``avail`` wide. Computed from the picture size, so nothing too big is ever put on screen
    (rendering first and shrinking afterwards made the overlay pulse on every tick)."""
    if img_w <= 0 or img_h <= 0 or round(img_w * height / img_h) <= avail:
        return height
    h = int(avail * img_h / img_w) + 1
    while h > minimum and round(img_w * h / img_h) > avail:
        h -= 1
    return max(minimum, min(height, h))


def clamp_x(side: str, x: float, w: float, gx: float, gw: float, bar: float, margin: float) -> float:
    """Move x so that [x, x+w] lies inside the bar (with margin)."""
    if side == "left":
        lo, hi = gx + margin, gx + bar - margin - w
    else:
        lo, hi = gx + gw - bar + margin, gx + gw - margin - w
    return min(max(x, lo), max(lo, hi))


def outside_slot(ox: float, ow: float, mx: float, mw: float, min_w: float = MIN_BAR):
    """Free desktop space beside a DBD window that does not fill the monitor (windowed mode):
    ("left" | "right", x0, width) or None. ``ox``/``ow``: the window's outer edges, ``mx``/``mw``:
    the monitor's work area. Left is preferred, like the left bar on ultrawide."""
    left, right = ox - mx, mx + mw - (ox + ow)
    if left >= min_w:
        return "left", mx, left
    if right >= min_w:
        return "right", ox + ow, right
    return None


def slot_x(slot, w: float, margin: float) -> float:
    """x of an overlay ``w`` wide in ``slot``: right next to the window (short way for the eyes),
    never past the monitor edge."""
    side, x0, width = slot
    if side == "left":
        return max(x0 + margin, x0 + width - margin - w)
    return x0 + margin
