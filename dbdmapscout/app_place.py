"""Placing the overlay in the game (1.8.26, analysis point 3 – moved out of app.py unchanged): the map window with
its lines, the room the system values and cards take in the black bars, the window-mode cases (free desktop beside
the window, bars above/below the picture), the reasons to hide, the waiting card and the visibility log. Mixin of
App; never imports app.py. The cards themselves are placed in app_sysinfo (SysInfo._cards_place), the lines in
app_overlay (OverlayTab._info_place), the geometry is layout.py (pure)."""
from __future__ import annotations

import time

from . import layout
from .capture import IS_WIN, describe_window, foreground_root, is_game_window
from .i18n import _
from .textnorm import fmt_duration

SMALL_PICTURE = 1080      # 16:9 picture lines below which detection gets less reliable (log hint)
MAX_HEIGHT = 0.9          # overlay at most this share of the game height (room for the timer below)


class OverlayPlacement:
    """Where the map (and what hangs on it) goes on screen, every tick (App._tick_overlay → _place_overlay)."""

    def _overlay_off(self) -> bool:
        """The master switch is off – "Overlay testen" and moving show it all the same."""
        return (not self.settings.get("overlay_on", True) and not self.overlay.editing
                and time.time() >= getattr(self, "_force_until", 0))

    def _overlay_all_off(self):
        o = self.settings["overlay"]
        self.worker.map_on_screen = self.overlay.has_map() and not self.hidden_after_match
        gx, gy, gw, gh = self._game_rect()
        self._hud_place(gx, gy, gw, gh, show=False)        # hides the values, still feeds the round's record
        self._fade_hide("map", bool(o.get("fade", True)))
        self._fade_hide("today", bool(o.get("fade", True)))
        self._fade_hide("music", bool(o.get("media_fade", True)))
        self._info_hide(bool(o.get("fade", True)))
        self.worker.overlay_rect = self.worker.today_rect = self.worker.media_rect = None
        self._vis_state = "aus"                     # set_overlay_on logged it already
        self._guides_place()

    TIMED_STEPS = {"hud": "_hud_place", "today": "_today_card", "music": "_media_card", "info": "_info_card",
                   "resolve": "_el_resolve", "guides": "_guides_place"}

    def _tick_times(self):
        """1.8.31: the tick's steps timed for the diagnosis (ticktime.TickTimes) – the methods wrapped once on
        the instance; the map is the rest of the tick."""
        tt = getattr(self, "_ticktimes", None)
        if tt is None:
            from .ticktime import TickTimes
            tt = self._ticktimes = TickTimes()
            for step, name in self.TIMED_STEPS.items():
                setattr(self, name, tt.timed(step, getattr(self, name)))
        return tt

    def _place_overlay(self):
        tt = self._tick_times()
        tt.start()
        t0 = time.perf_counter()
        try:
            self._place_overlay_steps()
        finally:
            tt.end((time.perf_counter() - t0) * 1000)

    def _place_overlay_steps(self):
        if self._overlay_off():
            self._overlay_all_off()
            return
        self._el_orig = {}
        if not hasattr(self, "_el_shift"):
            self._el_shift = {}
        try:
            self._place_overlay_map()
        finally:
            if not getattr(self, "_cards_done", False):
                self._cards_place()                 # "today" and the music card, stacked (1.2.6 / 1.2.7)
            self._cards_done = False
            self._el_resolve()                      # 1.8.25: nothing on top of anything else
            self._guides_place()                    # centre cross while moving (1.64.5)

    def _place_overlay_map(self):
        o = self.settings["overlay"]
        self.overlay.set_skin(self._skin(), self._skin_accent())       # 1.3.1: only re-renders on a change
        self.worker.map_on_screen = self.overlay.has_map() and not self.hidden_after_match
        gx, gy, gw, gh = self._game_rect()               # keeps the game window info fresh
        # test: shown at its normal place, ignoring every reason to hide it
        forced = time.time() < getattr(self, "_force_until", 0) and self.overlay.has_map()
        self._forced = forced                               # the cards show too, with sample values (1.2.8)
        if forced:
            self._pos_forced = True
        elif getattr(self, "_pos_forced", False):
            self._pos_forced = False
            if getattr(self, "_test_map", False):
                self._unload_test_map()
            self._log(_("Test beendet."), "Overlay")
        if (time.time() >= getattr(self, "_force_until", 0) and hasattr(self, "test_btn")
                and self.test_btn.cget("text") != _("Overlay testen")):
            self.test_btn.configure(text=_("Overlay testen"))
        wait = [] if forced else self._waiting_lines()
        self.overlay.set_waiting(wait)
        reason = None
        if forced:
            pass
        elif wait:
            reason = self._focus_reason(o)                  # only the "DBD in front" rule applies
        elif not self.overlay.has_map():
            reason = _("keine Map")
        elif not ((self.user_visible and not self.hidden_after_match) or self.overlay.editing):
            reason = _("ausgeblendet")
        elif self.menu_paused and not self.overlay.editing:
            reason = _("Menü offen")
        elif not o.get("show_map", True) and not self.overlay.has_info() and not self.overlay.editing:
            reason = _("nichts anzuzeigen")          # info only, but no timer/server yet
        else:
            reason = self._focus_reason(o)
        if wait:
            self._vis_state = "wartet"                      # the waiting card is not logged
        elif not forced:
            self._log_visibility(reason, (gx, gy, gw, gh))
        self._hud_place(gx, gy, gw, gh, show=not reason and not wait)
        self._cards_done = False
        if not self._hud_pending:                   # 1.2.11: the cards first (they do not depend on the map) – the
            self._cards_place()                     # map moves below / above what stands at the top / bottom of its
            self._cards_done = True                 # bar; with the values right above the map they follow it later
        else:
            self._cards_place(free_only=True)       # … only the cards in a bar corner / at an own place now
        self._sysinfo_status()
        fade = bool(o.get("fade", True)) and not self.overlay.editing      # 1.2.9
        if reason:
            self._fade_hide("map", fade)
            self._info_hide(fade)
            self.worker.overlay_rect = None
            return
        if self.overlay.editing and self.overlay.dragging:
            return                                           # user is dragging
        self.overlay.opacity = o["opacity"]
        margin = int(gh * o["margin"])
        # floors one below the other (Midwich): each as big as one map, as far as the screen allows
        height = int(gh * min(MAX_HEIGHT, self._map_height() * self.overlay.stacked()))
        a = o["anchor"]
        bar = layout.bar_width(gw, gh)          # black bar left/right of a 16:9 picture (ultrawide)
        # window narrower than 16:9: the trial has bars above/below – the map goes there whatever the position
        # setting says (user: own position at 1440p, the bar in the small window); not while dragging it
        vb = None if self.overlay.editing else layout.vbars(self.worker.vbars, gw, gh, time.time())
        # 1.8.24: timer/record/server as their own element – measured first, the map makes room for them
        apart = layout.info_apart(o) and self.info_win is not None and not vb
        self.overlay.set_info_apart(apart)
        info = self._info_card(gh, margin, bar) if apart else None
        if not apart:
            self._info_hide(fade)
        idrop, ilift = layout.info_reserve(o, info, layout.stack_gap(o, gh))
        extra, shift = layout.own_block(o, info, layout.stack_gap(o, gh))     # own place: map + lines one block
        drop = lift = 0                         # what stands at the top / bottom of the map's bar (1.2.11)
        span = layout.map_bar_range(a, o.get("pos_x", 0.0), gx, gw, bar)
        bands = layout.bar_bands(o, (gx, gy, gw, gh), margin)       # 1.8.14: the limiter lines of the bars
        band = bands["left" if span[0] <= gx else "right"] if bands and span else None
        if span and a != "custom":
            fixed = []
            if not self.overlay.editing:
                fixed = [self.worker.hud_rect if self.hud is not None and self.hud.shown else None]
                if o.get("today_pos", "below") != "custom":
                    fixed.append(self.worker.today_rect)
                if o.get("media_pos", "below") != "custom":
                    fixed.append(self.worker.media_rect)
            drop, lift = layout.bar_room(fixed, span[0], span[1], gy, gh, margin, layout.stack_gap(o, gh), band)
            if band and self._hud_pending == "above" and self.hud is not None:     # values + cards above the map
                drop += layout.follow_reserve(self.hud.size[1], getattr(self, "_card_sizes", None) or {},
                                              {"today": o.get("today_pos", "below"),
                                               "music": o.get("media_pos", "below")}, layout.stack_gap(o, gh))
        drop, lift = drop + idrop, lift + ilift
        height = max(40, min(height, gh - drop - lift - 2 * margin))
        self.overlay.info_beside = bool(vb)
        if vb:
            self._place_in_bottom_bar(gx, gy, gw, gh, vb[1], margin, height, sliders=a != "custom")
            return
        slot = None
        if a == "auto" and bar < layout.MIN_BAR:
            slot = self._outside_slot()          # window mode: free desktop beside the DBD window
            if slot is None:
                a = "top-left"

        def place(w, h):
            if slot is not None:
                return layout.slot_x(slot, w, margin), gy + margin
            if a == "auto":                      # 1.2.8: left / centre / right in the bar
                align = o.get("bar_align", "centre")
                ax = (bar - w) / 2 if align == "centre" else (bar - margin - w if align == "right" else margin)
                return gx + max(margin, ax), gy + margin + drop
            if a == "custom":
                return (gx + o.get("pos_x", 0.0) * max(0, gw - w),
                        gy + o.get("pos_y", 0.0) * max(0, gh - h - extra) + shift)
            return (gx + margin if a.endswith("left") else gx + gw - w - margin,
                    gy + margin + drop if a.startswith("top") else gy + gh - h - margin - lift)

        # Fit before rendering: only the final size may reach the screen (render() shows it at once).
        iw, ih = self.overlay.map_extent()              # 1.8.24: what is drawn, not the transparent strips
        w_est = round(iw * height / ih) if ih else 0
        side = (layout.bar_side(a, place(w_est, 0)[0], w_est, gx, gw, bar)
                if slot is None and (a == "auto" or o.get("keep_in_bar", True)) else None)
        avail = layout.max_width(bar, margin)
        if slot is not None:                     # the free space works like a bar: fit, never cover DBD
            side, avail = "slot", layout.max_width(slot[2], margin)
        # 1.65.4 (user: "die Grösse beliebig ändern"): a map bigger than the bar may reach into the game picture;
        # it stays at the bar's outer edge
        grow = bool(o.get("grow_past_bar", False)) and side in ("left", "right")
        text_h = self._text_height(gh)
        edge = min(self.overlay.backdrop_pad(text_h), max(0, margin - 2))   # the dark area may use the margin
        if side and not grow:
            height = layout.fit_height(height, avail, iw, ih)
            height = self.overlay.fit_width(height, text_h, avail + 2 * edge)   # sets the text height too
        else:
            self.overlay.text_height = text_h
        room = gh - drop - lift - 2 * margin
        if a == "custom":                                # 1.8.22: an own place – between the lines of its bar
            w, h = self.overlay.render(height, push=False)
            room = layout.own_room((place(w, h)[0], 0, w, h), (gx, gy, gw, gh), bands)
            room -= extra                                # the lines right below/above it
        if not self.overlay.dragging:                    # the lines below made it too tall: smaller (1.2.11) –
            height = self.overlay.fit_room(height, room)     # measured off screen (1.8.23), shown once
        w, h = self.overlay.render(height)
        x, y = place(w, h)
        if a != "custom":
            y = max(gy, min(y, gy + gh - h))             # never off the screen
        elif band and not self.overlay.dragging:         # an own place in a bar stays between its lines too
            y = layout.clamp_box((x, y - shift, w, h + extra), (gx, gy, gw, gh), bands)[1] + shift
        if side and side != "slot":
            x = layout.clamp_x(side, x, w, gx, gw, bar, margin - edge)
        self._fade_show("map", fade)
        self.overlay.show_at(int(x), int(y))
        self._last_place = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        block = self._info_place(self._last_place, gx, gy, gw, gh, margin, fade) if apart else None
        # what hangs above/below the map (system values, cards) goes around map and lines together
        self._map_block = layout.union(self._last_place, block) \
            if block and o.get("info_pos", "below") != "custom" else self._last_place
        self._hud_follow_map(self._map_block, gx, gy, gw, gh, margin)       # system values "above the map"
        if a != "custom":                      # sliders follow the preset position
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _place_in_bottom_bar(self, gx, gy, gw, gh, bottom, margin, height, sliders=True):
        """Map (+ timer, server) in the black bar below the picture, left, as big as the bar allows."""
        avail_w, avail_h = gw - 2 * margin, bottom - 2 * margin
        height = min(height, avail_h)
        self.overlay.text_height = min(self._text_height(gh), height)
        w, h = self.overlay.render(height, push=False)      # measured first: only the final size is shown
        for _try in range(3):                    # the info block below the map needs room too (not quite linear)
            f = layout.fit_scale(w, h, avail_w, avail_h)
            if f >= 1 or height <= 40:
                break
            height = max(40, int(height * f))
            self.overlay.text_height = max(40, int(self.overlay.text_height * f))
            w, h = self.overlay.render(height, push=False)
        w, h = self.overlay.render(height)
        x, y = gx + margin, gy + gh - bottom + margin
        self._fade_show("map", bool(self.settings["overlay"].get("fade", True)) and not self.overlay.editing)
        self.overlay.show_at(int(x), int(y))
        self._last_place = self._map_block = (int(x), int(y), w, h)
        self.worker.overlay_rect = self._last_place if self.overlay.shown else None
        self._hud_follow_map(self._last_place, gx, gy, gw, gh, margin)       # "above the map": right of it here
        if sliders:                              # an own position stays as it is (it applies again at 1440p)
            self._set_pos_sliders((x - gx) / max(1, gw - w), (y - gy) / max(1, gh - h))

    def _outside_slot(self):
        """Free desktop space beside a DBD window that does not fill its monitor, or None."""
        g = self.game
        if g is None or g.minimized or not g.monitor:
            return None
        frame = g.outer or g.window or g.client
        if not frame:
            return None
        return layout.outside_slot(frame[0], frame[2], g.monitor[0], g.monitor[2])

    def _note_window(self):
        """Log once when DBD runs in a way that makes detection weaker (small window, narrower than 16:9)."""
        g = self.game
        if g is None or g.minimized or not g.client:
            return
        flags = (min(g.height, g.width * 9 / 16) < SMALL_PICTURE, g.width * 9 < g.height * 16 - 32)
        told = getattr(self, "_window_told", (False, False))
        if flags[0] and not told[0]:
            self._log(_("DBD läuft mit {w}×{h}, kleiner als 1920×1080: die Erkennung ist unsicherer (vor allem "
                        "Lobby-Knopf und Killername). Fenster größer ziehen oder „Fenster-Vollbild“ nutzen.",
                        w=g.width, h=g.height), "Erkennung")
        if flags[1] and not told[1]:
            self._log(_("DBD-Fenster ist schmaler als 16:9 ({w}×{h}): diese Form ist ungetestet, Map- und "
                        "Rundenende-Erkennung können danebenliegen. Am sichersten: 16:9 oder breiter.",
                        w=g.width, h=g.height), "Erkennung")
        self._window_told = flags

    def _focus_reason(self, o):
        """Reason to hide while another window is in front ("Nur zeigen, wenn DBD das aktive Fenster ist")."""
        if (o["only_when_game_focused"] and IS_WIN and not self.overlay.editing and not self.simulate
                and self.game is not None):
            fg = foreground_root()
            own = {self.overlay.hwnd(), self._qt_hwnd()}
            if fg not in own and not is_game_window(fg):
                return _("aktives Fenster ist {window}", window=describe_window(fg))
        return None

    def _waiting_lines(self):
        """The waiting card while DBD runs and no map is on screen: what the program is waiting for, and
        the lobby state below it. Never over a map the user hid on purpose, never while editing."""
        o = self.settings["overlay"]
        if (not o.get("show_waiting", True) or not self.settings.get("auto_detect", True)
                or (self.game is None and not self.simulate) or self.overlay.editing):
            return []
        if self.overlay.has_map() and not self.hidden_after_match:
            return []                                        # map shown, paused in a menu or hidden by hand
        lines = [_("Warte auf Map")]
        q = self._queue
        if q.get("state") == "search" or q.get("found") is not None:      # searching / lobby found (not yet used)
            lines += [t for t in [self._queue_text(time.time())] if t]
        elif self.hidden_after_match and self.round.start_t is not None and not self.round.running:
            lines.append(_("Letzte Runde: {time}", time=fmt_duration(self.round.elapsed(0))))
        return lines

    def _log_visibility(self, reason, game_rect):
        """One log line whenever the overlay goes from visible to hidden or back."""
        if reason == _("keine Map"):
            self._vis_state = reason
            return
        if reason in (_("Menü offen"), _("nichts anzuzeigen")):                     # already logged by the menu event
            self._vis_state = reason
            return
        state = reason or "sichtbar"
        if state == getattr(self, "_vis_state", None):
            return
        self._vis_state = state
        if reason is None:
            src = (_("DBD-Fenster {w}×{h}", w=game_rect[2], h=game_rect[3]) if self.game
                   else _("Bildschirm"))
            self.root.after(300, lambda: self._log(
                _("Overlay sichtbar bei {pos} über {src}.", pos=(self._last_place or ("?", "?"))[:2], src=src),
                "Overlay"))
        elif reason != _("ausgeblendet"):
            self._log(_("Overlay pausiert: {reason}.", reason=reason), "Overlay")
