"""Map-banner detection.

When a trial starts, Dead by Daylight shows the map name bottom-left:

        FORGOTTEN RUINS                    <- map name, white, 1-2 lines
        ───────────────────────────        <- thin separator line, ~1/3 screen wide
        THE DECIMATED BORGO                <- realm name, grey

Pipeline per captured frame (only the bottom-left region is captured):

1. ``find_separator``: look for the thin bright horizontal line. That is a very
   specific shape (≈33 % of the screen width, 1-4 px thick) and costs a few
   milliseconds, so it runs at ~5 Hz all the time without OCR.
2. ``locate_text``: the map name sits directly above the line, the realm right
   below it. Their exact rows/extent are measured from the pixels, so UI scale,
   resolution and two-line names do not matter.
3. ``BannerReader``: both text lines go through the recognition network and
   every known (map, realm) pair is scored with the CTC lexicon scorer.
4. ``Accumulator``: scores of consecutive frames of the same banner are summed
   until one map is clearly ahead.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from .i18n import N_
from .ocr import LexiconScorer, Recognizer, best_path_logp

# Part of the game frame that is captured for detection (fractions of w/h).
ROI = (0.0, 0.52, 0.64, 0.99)
# Separator line: (brighter than the rows around it by, at least this bright). The second pass only runs when
# the first finds nothing: a small game picture (window narrower than 16:9 shows the trial letterboxed, user
# screenshot 1718×1360 → picture ~858 px high) draws the hairline below one pixel, it comes out at grey ~55
# on a dark map instead of > 105. Unknown text still never maps to a wrong map (lexicon scoring).
SEPARATOR_PASSES = ((12, 105), (25, 40))
SMALL_PICTURE_H = 1200       # the second pass only for pictures below this height (1440p reads fine with the first)


# --------------------------------------------------------------------------
# 1) separator line
# --------------------------------------------------------------------------
@dataclass
class Separator:
    y: int          # row in the image that was searched
    x0: int
    x1: int
    frac: float     # length relative to the full game width
    thickness: float

    @property
    def length(self) -> int:
        return self.x1 - self.x0


def find_separator(img: np.ndarray, frame_w: int, frame_h: int, letterboxed: bool = False) -> Separator | None:
    """Find the banner's separator line inside ``img`` (the captured ROI).

    ``frame_w``/``frame_h`` are the size of the whole game frame, needed to
    judge the line length independent of the capture region.
    ``letterboxed``: the picture has black bars above and below right now (a trial in a window narrower than
    16:9) – only then the second, tolerant pass may run (in lobby/menus it found lines in the UI, 1.44.1).
    """
    if img is None or img.size == 0:
        return None
    s = min(1.0, 1080.0 / max(1, frame_h))
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1.0 else img
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
    k = 3
    up = np.zeros_like(g)
    up[k:] = g[:-k]
    dn = np.zeros_like(g)
    dn[:-k] = g[k:]
    ridge = g - np.maximum(up, dn)
    tolerant = letterboxed and min(frame_h, frame_w * 9 / 16) < SMALL_PICTURE_H
    for ridge_min, bright_min in SEPARATOR_PASSES[:None if tolerant else 1]:
        sep = _separator_in(((ridge > ridge_min) & (g > bright_min)).astype(np.uint8), frame_w, frame_h, s)
        if sep is not None:
            return sep
    return None


def _separator_in(mask: np.ndarray, frame_w: int, frame_h: int, s: float) -> Separator | None:
    """The banner line in one threshold mask of the (scaled) ROI."""
    # bridge small gaps (texture, compression) along the line
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))) > 0
    h_img, w_img = mask.shape
    # longest horizontal run per row (vectorised): run = i - index of last zero
    cols = np.arange(w_img)[None, :]
    last_zero = np.maximum.accumulate(np.where(mask, -1, cols), axis=1)
    run = cols - last_zero
    run[~mask] = 0
    row_len = run.max(1)
    row_end = run.argmax(1)
    # UI size follows the 16:9 part of the screen (matters for ultrawide)
    wn = min(frame_w, frame_h * 16 / 9) * s
    long_rows = np.where(row_len >= 0.17 * wn)[0]
    if len(long_rows) == 0:
        return None
    # group neighbouring rows -> one line; keep the longest group
    groups, cur = [], [long_rows[0]]
    for r in long_rows[1:]:
        if r - cur[-1] <= 1:
            cur.append(r)
        else:
            groups.append(cur)
            cur = [r]
    groups.append(cur)
    best = None
    for grp in groups:
        if len(grp) > 6:                     # too thick for the separator
            continue
        r = max(grp, key=lambda i: row_len[i])
        length = int(row_len[r])
        x1 = int(row_end[r]) + 1
        x0 = x1 - length
        frac = length / wn
        if frac > 0.60 or x0 > 0.30 * frame_w * s:    # the banner is left-aligned
            continue
        if best is None or length > best[2]:
            best = (x0, float(np.mean(grp)), length, len(grp), frac)
    if best is None:
        return None
    x0, yc, length, thick, frac = best
    return Separator(y=int(round(yc / s)), x0=int(x0 / s), x1=int((x0 + length) / s),
                     frac=float(frac), thickness=float(thick / s))


# --------------------------------------------------------------------------
# 2) text localisation
# --------------------------------------------------------------------------
def _text_mask(bgr: np.ndarray, L: int) -> np.ndarray:
    """Bright, colourless, thin structures (= the banner's letters)."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    k = max(5, int(round(0.016 * L)) | 1)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    ref = float(np.percentile(g, 99.5)) if g.size else 255.0
    thr = max(100.0, 0.70 * ref)
    return ((g >= thr) & (sat < 90) & (th > 18)).astype(np.uint8)


def _components(mask: np.ndarray):
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    comps = [(int(x), int(y), int(w), int(h), int(a)) for x, y, w, h, a in stats[1:] if a >= 3]
    comps.sort()
    return comps


def _is_letter(c, h_lo, h_hi):
    x, y, w, h, a = c
    return h_lo <= h <= h_hi and w <= 2.8 * h and a >= 0.06 * w * h


@dataclass
class _Chain:
    x0: int
    x1: int
    top: int
    bottom: int
    n: int

    @property
    def h(self):
        return self.bottom - self.top


def _chains(comps, h_lo: float, h_hi: float, start_limit: float, min_letters: int = 3):
    """Left-aligned text lines.

    A line starts with a letter-sized component near the left edge and is
    extended to the right by every component that covers most of the line's
    height (letters, but also letters that touch background clutter) as long as
    the horizontal gap stays below ~1.3 letter heights.
    """
    chains = []
    for i, seed in enumerate(comps):
        sx, sy, sw, sh, _ = seed
        if sx > start_limit:
            break
        if not _is_letter(seed, h_lo, h_hi):
            continue
        top, bot, right = sy, sy + sh, sx + sw
        n_letters, tops, bots = 1, [sy], [sy + sh]
        for c in comps[i + 1:]:
            bx, by, bw, bh, _ = c
            overlap = min(bot, by + bh) - max(top, by)
            if overlap < 0.6 * sh:
                continue                     # other row / clutter
            aligned = _is_letter(c, h_lo, h_hi) and abs(by - top) <= 0.3 * sh and abs(by + bh - bot) <= 0.3 * sh
            gap = bx - right
            if gap > 2.4 * sh or (gap > 1.3 * sh and not aligned):
                break                        # end of the text (a lost letter is tolerated)
            right = max(right, bx + bw)
            if aligned:
                n_letters += 1
                tops.append(by)
                bots.append(by + bh)
        if n_letters >= min_letters:
            tops.sort()
            bots.sort()
            chains.append(_Chain(x0=sx, x1=right, top=tops[len(tops) // 2],
                                 bottom=bots[len(bots) // 2], n=n_letters))
    # the same line is found from several seeds -> keep the longest per row
    chains.sort(key=lambda c: (-c.n, c.x0))
    uniq = []
    for c in chains:
        if all(abs(c.top - u.top) > 0.5 * u.h for u in uniq):
            uniq.append(c)
    return uniq


def _crop_chain(region: np.ndarray, c: _Chain) -> np.ndarray:
    pv = int(round(0.28 * c.h))
    ph = int(round(0.40 * c.h))
    return region[max(0, c.top - pv):min(region.shape[0], c.bottom + pv),
                  max(0, c.x0 - ph):min(region.shape[1], c.x1 + ph)]


def _hconcat(imgs):
    h = max(i.shape[0] for i in imgs)
    parts = []
    for i, im in enumerate(imgs):
        if im.shape[0] != h:
            im = cv2.resize(im, (max(1, int(im.shape[1] * h / im.shape[0])), h), interpolation=cv2.INTER_CUBIC)
        if i:
            parts.append(np.zeros((h, max(2, h // 2), 3), np.uint8))
        parts.append(im)
    return np.concatenate(parts, axis=1)


@dataclass
class TextLines:
    name: np.ndarray | None          # map name (two lines already joined)
    realm: np.ndarray | None
    name_lines: int = 0


def locate_text(img: np.ndarray, sep: Separator) -> TextLines:
    H, W = img.shape[:2]
    L = max(1, sep.length)
    # a line shorter than usual was probably only partly visible (bright
    # background on its left end) -> the text may start further left
    left = 0.60 * L if sep.frac < 0.30 else 0.03 * L
    cx0 = max(0, int(sep.x0 - left))
    cx1 = min(W, int(sep.x1 + 0.03 * L))
    start_limit = sep.x0 - cx0 + 0.12 * L

    # ---- map name above the line (one or two lines, left-aligned)
    ay0 = max(0, int(sep.y - 0.30 * L))
    ay1 = max(ay0 + 1, int(sep.y - 0.003 * L))
    above = img[ay0:ay1, cx0:cx1]
    name_img, n_lines = None, 0
    if above.size:
        m = _text_mask(above, L)
        chains = _chains(_components(m), 0.022 * L, 0.095 * L, start_limit)
        bottom = above.shape[0]
        low = [c for c in chains if bottom - c.bottom <= 0.08 * L]
        if low:
            first = max(low, key=lambda c: (c.bottom, c.n))
            picked = [first]
            while len(picked) < 3:           # long names wrap onto 2-3 lines
                cur = picked[0]
                up = [c for c in chains if c.bottom <= cur.top + 0.1 * cur.h
                      and cur.top - c.bottom <= 0.07 * L
                      and 0.7 * first.h <= c.h <= 1.45 * first.h
                      and abs(c.x0 - first.x0) <= 1.0 * first.h]
                if not up:
                    break
                picked.insert(0, max(up, key=lambda c: c.bottom))
            crops = [_crop_chain(above, c) for c in picked]
            crops = [c for c in crops if c.size]
            if crops:
                name_img = crops[0] if len(crops) == 1 else _hconcat(crops)
                n_lines = len(crops)
        if name_img is None:
            # low contrast (fog/snow): fall back to where the name normally sits
            ry0 = int(sep.y - 0.080 * L) - ay0
            ry1 = int(sep.y - 0.008 * L) - ay0
            rx0 = max(0, int(sep.x0 - cx0 - 0.01 * L))
            crop = above[max(0, ry0):max(0, ry1), rx0:min(above.shape[1], rx0 + int(1.0 * L))]
            if crop.size:
                name_img, n_lines = crop, 0

    # ---- realm below the line
    by0 = min(H - 1, int(sep.y + 0.003 * L))
    by1 = min(H, int(sep.y + 0.11 * L))
    below = img[by0:by1, cx0:cx1]
    realm_img = None
    if below.size:
        mb = _text_mask(below, L)
        chains = _chains(_components(mb), 0.013 * L, 0.06 * L, start_limit)
        near = [c for c in chains if c.top <= 0.05 * L]
        if near:
            realm_img = _crop_chain(below, min(near, key=lambda c: c.top))
            if realm_img.size == 0:
                realm_img = None
        if realm_img is None:
            rx0 = max(0, int(sep.x0 - cx0 - 0.01 * L))
            crop = below[0:min(below.shape[0], int(0.058 * L)), rx0:min(below.shape[1], rx0 + int(0.85 * L))]
            realm_img = crop if crop.size else None
    return TextLines(name=name_img, realm=realm_img, name_lines=n_lines)


# --------------------------------------------------------------------------
# 3) scoring one frame
# --------------------------------------------------------------------------
@dataclass
class FrameResult:
    scores: dict                     # (map_id, variant) -> log score
    best: tuple | None
    name_text: str = ""
    realm_text: str = ""
    name_fit: float = -1e9           # best name log-prob minus best-path log-prob (≈0 = perfect fit)
    realm_fit: float | None = None
    ms: float = 0.0


class BannerReader:
    def __init__(self, recognizer: Recognizer, catalog):
        self.rec = recognizer
        self.catalog = catalog
        self.name_scorer = LexiconScorer(catalog.name_strings)
        self.realm_scorer = LexiconScorer(catalog.realm_strings)

    def score_lines(self, lines: TextLines) -> FrameResult | None:
        t0 = time.perf_counter()
        if lines.name is None or lines.name.size == 0:
            return None
        pn = self.rec.probs(lines.name)
        gn = self.rec.groups(pn)
        name_lp = self.name_scorer.score(gn)
        name_bp = best_path_logp(gn)
        realm_lp, realm_bp, realm_text = None, None, ""
        if lines.realm is not None and lines.realm.size:
            pr = self.rec.probs(lines.realm)
            gr = self.rec.groups(pr)
            realm_lp = self.realm_scorer.score(gr)
            realm_bp = best_path_logp(gr)
            realm_text = self.rec.text(pr)
        ni = self.name_scorer.index
        ri = self.realm_scorer.index
        scores = {}
        best_name = {}
        for h in self.catalog.hypotheses:
            s = name_lp[ni[h.name_key]]
            if realm_lp is not None and h.realm_keys:
                s = s + max(realm_lp[ri[r]] for r in h.realm_keys)
            key = (h.map_id, h.variant)
            if s > scores.get(key, -np.inf):
                scores[key] = s
                best_name[key] = h
        best = max(scores, key=scores.get) if scores else None
        res = FrameResult(scores=scores, best=best, name_text=self.rec.text(pn), realm_text=realm_text)
        if best is not None:
            h = best_name[best]
            res.name_fit = float(name_lp[ni[h.name_key]] - name_bp)
            if realm_lp is not None and h.realm_keys:
                res.realm_fit = float(max(realm_lp[ri[r]] for r in h.realm_keys) - realm_bp)
        res.ms = (time.perf_counter() - t0) * 1000
        return res

    def read(self, img: np.ndarray, frame_w: int, frame_h: int, letterboxed: bool = False):
        """Full pipeline on one captured ROI. Returns (Separator|None, FrameResult|None)."""
        sep = find_separator(img, frame_w, frame_h, letterboxed)
        if sep is None:
            return None, None
        lines = locate_text(img, sep)
        return sep, self.score_lines(lines)


# --------------------------------------------------------------------------
# 4) evidence over several frames
# --------------------------------------------------------------------------
@dataclass
class Decision:
    map_id: str
    variant: int
    probability: float           # map certainty
    variant_probability: float   # certainty of the layout variant (II, III ...)
    frames: int
    name_text: str
    realm_text: str
    name_fit: float = 0.0        # best name fit of the frames that read this map (≈0 = a clean banner)
    unsure: bool = False         # no frame fitted well (name_fit < Accumulator.unsure_fit): maybe a false read


def _softmax(d: dict) -> dict:
    if not d:
        return {}
    keys = list(d)
    v = np.array([d[k] for k in keys], dtype=np.float64)
    v = v - v.max()
    p = np.exp(v)
    p /= p.sum()
    return dict(zip(keys, p))


MIN_NAME_CHARS = 3   # a frame whose name reads as (almost) nothing is no evidence: an empty read fitted "The Game"
                     # at -8.1 (> fit_ok) on a line in the lobby (user diagnosis 1.45.0)


@dataclass
class Accumulator:
    """Collects evidence over the frames of one banner appearance.

    Map and layout variant are decided separately: telling maps apart is easy
    (names differ in many letters), telling "COAL TOWER" from "COAL TOWER II"
    hinges on one thin glyph, so the variant uses the full (untempered)
    evidence plus a small prior for the base layout (variants are custom-game
    only since patch 8.6.0).
    """
    temperature: float = 0.35        # damp over-confident single frames (map level)
    min_prob: float = 0.97
    fast_prob: float = 0.9995
    fit_ok: float = -9.0             # name fit needed to trust a frame
    fit_fast: float = -3.0
    base_variant_prior: float = 1.0  # nats in favour of layout I
    variant_decay: float = 0.6
    unsure_fit: float = -3.0         # real banners fit ≈ 0; below this on every frame the read is doubtful
    strict_frames: int = 4           # mid-match (strict): good frames needed – a real banner gives ~20 at 5/s
    maps: dict = field(default_factory=dict)       # map_id -> tempered score sum
    variants: dict = field(default_factory=dict)   # (map_id, v) -> score sum relative to that map's best
    frames: int = 0
    good_frames: int = 0
    last_texts: tuple = ("", "")
    decided: tuple | None = None
    decided_unsure: bool = False
    fits: dict = field(default_factory=dict)       # map_id -> best name fit of the frames that read it

    def reset(self):
        self.maps, self.variants = {}, {}
        self.frames = self.good_frames = 0
        self.last_texts = ("", "")
        self.decided = None
        self.decided_unsure = False
        self.fits = {}

    def map_posterior(self):
        return _softmax(self.maps)

    def variant_posterior(self, map_id):
        vs = {v: s + (self.base_variant_prior if v == 1 else 0.0)
              for (m, v), s in self.variants.items() if m == map_id}
        return _softmax(vs)

    def best(self):
        """(map_id, probability, best name fit) of the leading map so far, or None."""
        post = self.map_posterior()
        if not post:
            return None
        m = max(post, key=post.get)
        return m, float(post[m]), self.fits.get(m, -1e9)

    def add(self, fr: FrameResult, strict: bool = False, hold: bool = False) -> Decision | None:
        """Add one frame; returns a Decision when a (new) map/variant is certain.

        ``strict``: in the middle of a running round, where DBD never shows a banner – something in the game
        world (neon strips, signs) can look like one. Then only a clean read over several frames counts:
        no single-frame decision, ``strict_frames`` good frames, and never a doubtful (unsure) read.
        ``hold``: collect the evidence, but do not decide yet (the caller waits for the banner to stay)."""
        if fr is None or fr.best is None:
            return None
        self.frames += 1
        self.last_texts = (fr.name_text, fr.realm_text)
        if fr.name_fit < self.fit_ok or sum(c.isalnum() for c in fr.name_text) < MIN_NAME_CHARS:
            return None                   # unreadable / unknown text: no evidence (nothing read fits short names)
        self.good_frames += 1
        if fr.best is not None:
            self.fits[fr.best[0]] = max(self.fits.get(fr.best[0], -1e9), fr.name_fit)
        per_map = {}
        for (m, v), sc in fr.scores.items():
            sc = sc if np.isfinite(sc) else -1e6
            per_map[m] = max(per_map.get(m, -np.inf), sc)
        for m, sc in per_map.items():
            self.maps[m] = self.maps.get(m, 0.0) + self.temperature * sc
        # variant evidence fades so the latest (fully faded-in) frames count most
        for (m, v), sc in fr.scores.items():
            sc = sc if np.isfinite(sc) else -1e6
            self.variants[(m, v)] = self.variant_decay * self.variants.get((m, v), 0.0) + max(-60.0, sc - per_map[m])
        post = self.map_posterior()
        best_map = max(post, key=post.get)
        p = float(post[best_map])
        if hold:
            return None
        fast = self.good_frames == 1 and p >= self.fast_prob and fr.name_fit >= self.fit_fast and not strict
        steady = self.good_frames >= (self.strict_frames if strict else 2) and p >= self.min_prob
        if not (fast or steady):
            return None
        vpost = self.variant_posterior(best_map)
        best_v = max(vpost, key=vpost.get)
        choice = (best_map, best_v)
        fit = self.fits.get(best_map, fr.name_fit)
        unsure = fit < self.unsure_fit
        if strict and unsure:
            return None                   # mid-match: a doubtful read never switches the map
        if choice == self.decided and not (self.decided_unsure and not unsure):
            return None                   # nothing new (a doubtful read that became sure is news)
        if self.decided is not None and self.decided[0] != best_map and self.good_frames < 4:
            return None                   # switching to another map needs more evidence
        self.decided, self.decided_unsure = choice, unsure
        return Decision(best_map, best_v, p, float(vpost[best_v]), self.good_frames, fr.name_text, fr.realm_text,
                        name_fit=fit, unsure=unsure)


# --------------------------------------------------------------------------
# 5) leaving the match: result screen, lobby/menus, next loading screen
# --------------------------------------------------------------------------
CONTINUE_WORDS = ["CONTINUE", "FORTFAHREN", "CONTINUER", "CONTINUAR", "CONTINUA", "KONTYNUUJ", "DEVAM ET"]


def viewport(frame_w: int, frame_h: int):
    """(x, width) of the 16:9 picture inside the window (ultrawide shows black bars)."""
    vw = min(frame_w, frame_h * 16 / 9)
    return (frame_w - vw) / 2, vw


def _region(frame, x0, y0, x1, y1):
    """Crop by fractions of the 16:9 viewport (x) and of the height (y)."""
    H, W = frame.shape[:2]
    vx, vw = viewport(W, H)
    return frame[int(y0 * H):int(y1 * H), int(vx + x0 * vw):int(vx + x1 * vw)]


def _right_region(frame, x0, y0, y1, full_width=False):
    """From ``x0`` (fraction of the 16:9 viewport) to the right edge of the 16:9 picture
    (+1 %). The black bars of an ultrawide window are left out: in a trial only other
    programs (FPS counters, notifications) draw there.

    ``full_width``: the screen fills the whole window (result screen, lobby and menus do
    on ultrawide, their buttons sit at the real window edge) – then the region reaches
    the window edge, measured the same way from there."""
    H, W = frame.shape[:2]
    vx, vw = viewport(W, H)
    x_start, x_end = int(vx + x0 * vw), min(W, int(vx + 1.01 * vw))
    if full_width:
        x_start, x_end = min(x_start, int(W - (1.0 - x0) * vw)), W
    return frame[int(y0 * H):int(y1 * H), x_start:x_end]


BAR_FILLED = 0.6        # share of non-black pixels for a side bar to count as "picture"


LETTERBOX_DARK = 0.95        # share of almost black pixels for a row to count as bar (FPS counters stay out)


def letterbox_rows(frame) -> tuple:
    """(top, bottom): rows of black bar above and below the picture. A DBD window narrower than 16:9 shows the
    trial letterboxed (user screenshot 1718×1360: bars of ~250 px, picture ~858 px high). A screen that is dark
    nearly everywhere (loading screen) is no letterbox: (0, 0). One look can mistake a dark scene at the edge for
    bar – the worker keeps the smallest value of several looks."""
    if frame is None or frame.size == 0:
        return 0, 0
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    H = g.shape[0]
    dark = (g < 16).mean(axis=1) >= LETTERBOX_DARK
    if dark.all():
        return 0, 0
    top = int(np.argmin(dark))                       # first row that is not dark
    bottom = int(np.argmin(dark[::-1]))
    if top + bottom > 0.8 * H or min(top, bottom) < 0.6 * max(top, bottom):
        return 0, 0                                  # letterbox bars are even; a loading screen is not
    return top, bottom


def has_bars(frame) -> bool:
    """Is the window wider than 16:9, i.e. does a trial show black bars left and right?"""
    H, W = frame.shape[:2]
    return int(viewport(W, H)[0] * 0.9) >= 40


def fills_bars(frame, ignore=None) -> bool:
    """Does the picture extend into the side bars of an ultrawide window?

    In a trial DBD draws 16:9 with black bars; result screen, lobby and menus use the
    full width. The top and bottom 15 % are ignored (FPS counters, notifications).
    ``ignore``: (x0, y0, x1, y1) of our own overlay, blacked out before the check – those
    pixels do not count (a big map in the left bar would otherwise make it look empty)."""
    H, W = frame.shape[:2]
    vx, _ = viewport(W, H)
    bar = int(vx * 0.9)
    if bar < 40:
        return False                                      # no bars (16:9 or narrower)
    y0, y1 = int(0.15 * H), int(0.85 * H)
    lit = cv2.cvtColor(frame[y0:y1], cv2.COLOR_BGR2GRAY) > 8
    use = np.ones(lit.shape, bool)
    if ignore is not None:
        ix0, iy0, ix1, iy1 = (int(v) for v in ignore)
        use[max(0, iy0 - y0):max(0, iy1 - y0), max(0, ix0):max(0, ix1)] = False

    def share(cols):
        n = int(use[:, cols].sum())
        return float(lit[:, cols][use[:, cols]].mean()) if n >= 0.2 * use[:, cols].size else None

    parts = [s for s in (share(slice(0, bar)), share(slice(W - bar, W))) if s is not None]
    if not parts:
        return False
    if len(parts) == 1:                                   # one bar hidden by our overlay: judge by the other
        return parts[0] >= BAR_FILLED
    return max(parts) >= BAR_FILLED and min(parts) >= BAR_FILLED / 2


def has_loading_bar(frame) -> bool:
    """Filled progress bar of the loading screen (bounded, isolated, plateau-shaped
    bright band in the bottom quarter). Port of dbd-map-overlay's
    hasFilledProgressBar (Apache-2.0)."""
    H = frame.shape[0]
    reg = _region(frame, 0.15, 0.75, 0.85, 1.0)
    if reg.size == 0:
        return False
    fracs = (cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY) > 40).mean(1)
    pi = int(np.argmax(fracs))
    peak = float(fracs[pi])
    if peak < 0.20 or peak > 0.60:
        return False
    off, bw = max(3, round(H * 0.015)), max(2, round(H * 0.004))
    near = np.concatenate([fracs[max(0, pi - off - bw):max(0, pi - off)],
                           fracs[min(len(fracs), pi + off):min(len(fracs), pi + off + bw)]])
    if peak - (float(near.mean()) if len(near) else 0.0) < 0.18:
        return False
    thr, lo, hi = peak * 0.6, pi, pi
    while lo > 0 and fracs[lo - 1] >= thr:
        lo -= 1
    while hi < len(fracs) - 1 and fracs[hi + 1] >= thr:
        hi += 1
    return (hi - lo + 1) >= max(2, round(H * 0.005))


DARK_SHARE = 0.85       # loading screen: share of near-black pixels in the upper picture (measured: 0.95;
                        # darkest gameplay seen: 0.75 – a dark map at match start)


def is_dark(frame) -> bool:
    """Almost black upper picture (loading screen: black with the white logo). A player lying on the
    ground has a progress bar and a nearly still picture too – but the lit game world around them."""
    g = cv2.cvtColor(_region(frame, 0.0, 0.0, 1.0, 0.70), cv2.COLOR_BGR2GRAY)
    return g.size > 0 and float((g < 12).mean()) >= DARK_SHARE


@dataclass
class EndObservation:
    """What one look at the whole screen found (also used for the diagnosis)."""
    continue_fit: float | None = None      # best CONTINUE fit (0 = perfect), None = no text there
    continue_text: str = ""
    currency_groups: int = 0               # number groups top right (bloodpoints, shards, auric cells)
    currency_digits: int = 0
    currency_text: str = ""
    loading: bool = False
    static: bool = False                   # upper picture unchanged since the previous look
    dark: bool = False                     # upper picture almost black (loading screen)
    full_width: bool = False               # picture fills the ultrawide bars (menus, result screen)
    reason: str | None = None
    sure: bool = False
    ms: float = 0.0

    def describe(self) -> str:
        cont = "–" if self.continue_fit is None else f"{self.continue_fit:.1f} „{self.continue_text}“"
        cur = f"{self.currency_groups} Gruppen/{self.currency_digits} Ziffern"
        if self.currency_text:
            cur += f" „{self.currency_text}“"
        bar = (("ja, Bild still" if self.static else "ja, Bild bewegt") + (", dunkel" if self.dark else ", hell")
               if self.loading else "nein")
        out = f"CONTINUE {cont} · Währung {cur} · Ladebalken {bar}" + (" · volle Breite" if self.full_width else "")
        return out + (f" → {self.reason}{' (sicher)' if self.sure else ''}" if self.reason else " → –")


class OutOfMatchWatcher:
    """Looks at a whole screenshot and tells whether it shows a screen outside the trial.

    * result screens: the CONTINUE / FORTFAHREN button bottom right
    * lobby, menus, store, bloodweb: the currency counters top right (never shown in a trial)
    * next loading screen: the filled progress bar on an almost black, still picture
    Confirming (two looks in a row etc.) is the caller's job, see matchend.py.
    """

    CONTINUE_OK = -4.0          # fit needed for a candidate
    CONTINUE_SURE = -1.5        # fit that is trusted on its own

    def __init__(self, recognizer: Recognizer):
        from .textnorm import fold
        self.rec = recognizer
        self.scorer = LexiconScorer([fold(w) for w in CONTINUE_WORDS])
        self._thumb = None

    def _still(self, frame) -> bool:
        """Upper 70 % of the picture unchanged since the last look? A loading screen
        is still; gameplay with a progress bar (repair, heal …) never is."""
        g = cv2.cvtColor(_region(frame, 0.0, 0.0, 1.0, 0.70), cv2.COLOR_BGR2GRAY)
        thumb = cv2.resize(g, (64, 28), interpolation=cv2.INTER_AREA).astype(np.int16)
        prev, self._thumb = self._thumb, thumb
        if prev is None or prev.shape != thumb.shape:
            return False
        return float(np.percentile(np.abs(thumb - prev), 99)) <= 4.0

    def observe(self, frame: np.ndarray, ignore=None) -> EndObservation:
        """``ignore``: rectangle of our own (blacked out) overlay in ``frame``."""
        t0 = time.perf_counter()
        ob = EndObservation()
        if frame is None or frame.size == 0:
            return ob
        H = frame.shape[0]
        ob.full_width = full = fills_bars(frame, ignore)
        ob.continue_fit, ob.continue_text = self._continue_fit(_right_region(frame, 0.78, 0.86, 0.99, full), H)
        if ob.continue_fit is not None and ob.continue_fit >= self.CONTINUE_OK:
            ob.reason, ob.sure = N_("Ergebnisbildschirm"), ob.continue_fit >= self.CONTINUE_SURE
        if full or not has_bars(frame):
            # lobby/menus with the counters fill the bars on ultrawide; black bars = trial, whose
            # score events top right would only cost OCR time (14–28 ms per look)
            ob.currency_groups, ob.currency_digits, ob.currency_text = self._currency(
                _right_region(frame, 0.62, 0.0, 0.12, full), H)
        if ob.reason is None and ob.currency_groups >= 2 and ob.currency_digits >= 6:
            ob.reason = N_("Lobby/Menü")
        ob.static = self._still(frame)
        ob.loading = has_loading_bar(frame)
        ob.dark = ob.loading and is_dark(frame)
        if ob.reason is None and ob.loading and ob.static and ob.dark:   # lying on the ground: bright world
            ob.reason = N_("Ladebildschirm")
        ob.ms = (time.perf_counter() - t0) * 1000
        return ob

    # kept for older callers / tests
    def _reason(self, frame):
        ob = self.observe(frame)
        return ob.reason, ob.sure

    def _chains_in(self, img, frame_h, lo, hi, min_letters):
        L = 0.3338 * frame_h * 16 / 9
        return _chains(_components(_text_mask(img, L)), lo * frame_h, hi * frame_h, img.shape[1],
                       min_letters=min_letters)

    def _continue_fit(self, img, frame_h):
        if img.size == 0:
            return None, ""
        best, text = None, ""
        for c in self._chains_in(img, frame_h, 0.006, 0.035, 4):
            crop = _crop_chain(img, c)
            if crop.size == 0:
                continue
            p = self.rec.probs(crop)
            g = self.rec.groups(p)
            fit = float(self.scorer.score(g).max() - best_path_logp(g))
            if best is None or fit > best:
                best, text = fit, self.rec.text(p)
        return best, text

    def _currency(self, img, frame_h):
        """Number groups in the currency bar top right, e.g. „823“ „4 628“ „1 499 484“.

        The counters sit on one row, separated by coloured icons, so every
        digit group is read on its own. Returns (groups with ≥ 3 digits, digits, text).
        """
        if img.size == 0:
            return 0, 0, ""
        L = 0.3338 * frame_h * 16 / 9
        lo, hi = 0.007 * frame_h, 0.04 * frame_h
        comps = [c for c in _components(_text_mask(img, L))
                 if lo <= c[3] <= hi and c[2] <= 1.3 * c[3] and c[4] >= 0.08 * c[2] * c[3]]
        rows = []                                           # glyphs on the same text row
        for c in sorted(comps, key=lambda c: c[1] + c[3] / 2):
            cy = c[1] + c[3] / 2
            for r in rows:
                if abs(r["cy"] - cy) <= 0.35 * r["h"] and 0.7 * r["h"] <= c[3] <= 1.4 * r["h"]:
                    r["c"].append(c)
                    break
            else:
                rows.append({"cy": cy, "h": c[3], "c": [c]})
        groups, digits, texts = 0, 0, []
        for r in rows:
            if len(r["c"]) < 3:
                continue
            cs = sorted(r["c"])
            words, cur = [], [cs[0]]
            for c in cs[1:]:
                if c[0] - (cur[-1][0] + cur[-1][2]) > 1.0 * r["h"]:
                    words.append(cur)
                    cur = [c]
                else:
                    cur.append(c)
            words.append(cur)
            for w in words:
                if len(w) < 2:
                    continue
                x0, x1 = min(c[0] for c in w), max(c[0] + c[2] for c in w)
                y0, y1 = min(c[1] for c in w), max(c[1] + c[3] for c in w)
                h = y1 - y0
                crop = img[max(0, y0 - int(0.3 * h)):min(img.shape[0], y1 + int(0.3 * h)),
                           max(0, x0 - int(0.4 * h)):min(img.shape[1], x1 + int(0.4 * h))]
                if crop.size == 0:
                    continue
                t = self.rec.text(self.rec.probs(crop)).strip()
                n = sum(ch.isdigit() for ch in t)
                if n >= 3 and all(ch.isdigit() or ch in " .,'’" for ch in t):
                    groups += 1
                    digits += n
                    texts.append(t)
        return groups, digits, " | ".join(texts[:4])
