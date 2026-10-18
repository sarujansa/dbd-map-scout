"""Overlay layout, part of App (1.65): undo of place/size changes, one layout per DBD window size, arrow keys in
the preview. Pure logic in layoutmem.py."""
from __future__ import annotations

import time

from . import layout, layoutmem
from .i18n import _

SIZE_SETTLE = 2.0          # s a new window size must stay before its layout is loaded (no switch while resizing)


class LayoutMemory:
    def _layout_init(self):
        self._undo = layoutmem.UndoStack()
        self._layout_seen = (None, 0.0)          # (window size, since) – a new size must settle first

    # ---------------------------------------------------------------- undo
    def _layout_mark(self):
        """Before a change of place or size: remember the layout (one step per gesture)."""
        if getattr(self, "_layout_applying", False):
            return
        self._undo.mark(layoutmem.snapshot(self.settings.data), time.monotonic())
        self._undo_btn_state()

    def undo_layout(self):
        """Button "Rückgängig" / Ctrl+Z on the overlay page: the layout before the last change."""
        snap = self._undo.undo(layoutmem.snapshot(self.settings.data))
        if snap is None:
            self._log(_("Nichts rückgängig zu machen."), "Overlay")
        else:
            self._layout_apply(snap)
            self._log(_("Position/Grösse rückgängig gemacht."), "Overlay")
        self._undo_btn_state()

    def _undo_btn_state(self):
        btn = getattr(self, "undo_btn", None)
        if btn is not None:
            btn.state(["!disabled"] if len(self._undo) else ["disabled"])

    def _layout_apply(self, snap):
        """A stored layout into the settings and every control that shows it."""
        from .app_sysinfo import BAR_ALIGNS, HUD_SIDES, MEDIA_SPOTS, TODAY_SPOTS
        self._layout_applying = True
        try:
            layoutmem.apply(self.settings.data, snap)
            o = self.settings["overlay"]
            self.anchor_var.set(self._anchor_text(o.get("anchor", "auto")))
            self._set_pos_sliders(o.get("pos_x", 0.0), o.get("pos_y", 0.0))
            self.size_var.set(o["height"] * 100)
            self.size_label.configure(text=f"{o['height'] * 100:.0f} %")
            self.media_size_var.set(round(o.get("media_scale", 1.0) * 100))
            self.media_pos_var.set(_(dict(MEDIA_SPOTS).get(o.get("media_pos", "bottom_right"), "")))
            self.today_pos_var.set(_(dict(TODAY_SPOTS).get(o.get("today_pos", "below"), "")))
            self.bar_align_var.set(_(dict(BAR_ALIGNS).get(o.get("bar_align", "centre"), "")))
            self.gap_var.set(float(o.get("stack_gap", 8)))
            self.limits_var.set(bool(o.get("bar_limits_on", False)))         # 1.8.14
            self.limits_same_var.set(bool(o.get("bar_limits_same", False)))
            self.sysinfo_var.set(_(dict(HUD_SIDES).get(self.settings.get("sysinfo", "off"), "")))
            self._pos_hint()
            self._show_map_size()
            self._sel_sync()
        finally:
            self._layout_applying = False
        self._save_soon()
        self._tick_overlay(reschedule=False)

    # ---------------------------------------------------------------- per window size
    def _layout_size_key(self):
        g = self.game
        if g is None or g.minimized or g.width <= 100:
            return None
        return layoutmem.size_key(g.width, g.height)

    def _layout_size_tick(self):
        """4×/s: the layout of the DBD window size in use is kept in settings.layouts; a new size (settled for
        SIZE_SETTLE) loads its own layout, a size seen for the first time starts with the one in use."""
        if not hasattr(self, "anchor_var"):
            return
        self._size_cap_tick()
        scope = self._size_scope_text()
        if scope != self.size_scope_var.get():
            self.size_scope_var.set(scope)
            self._sel_sync()                      # another map on display: its own size on the slider
        text = self._layout_size_text()
        if text != self.per_size_text.get():
            self.per_size_text.set(text)
        if not self.settings.get("layout_per_size", True):
            return
        store = self.settings.data.setdefault("layouts", {})
        cur = self.settings.get("layout_key")
        key = self._layout_size_key()
        now = time.monotonic()
        if key != self._layout_seen[0]:
            self._layout_seen = (key, now)
        if key and key != cur and now - self._layout_seen[1] >= SIZE_SETTLE:
            if cur:
                store[cur] = layoutmem.snapshot(self.settings.data)
            self.settings.set("layout_key", key)
            if key in store and cur:
                self._layout_apply(store[key])
                self._undo.clear()
                self._undo_btn_state()
                self._log(_("DBD-Fenster {size}: Layout für diese Grösse geladen.", size=key.replace("x", "×")),
                          "Overlay")
            elif cur:
                self._log(_("DBD-Fenster {size}: neue Grösse – Layout wird ab jetzt dafür gemerkt.",
                            size=key.replace("x", "×")), "Overlay")
            store[key] = layoutmem.snapshot(self.settings.data)
            self._save_soon()
            return
        if cur:                                  # changes (also with DBD closed) belong to the size last used
            snap = layoutmem.snapshot(self.settings.data)
            if store.get(cur) != snap:
                store[cur] = snap

    def _per_size_changed(self):
        self.settings.set("layout_per_size", bool(self.per_size_var.get()))
        self._save_soon()

    def _layout_size_text(self):
        key = self.settings.get("layout_key")
        if not self.settings.get("layout_per_size", True) or not key:
            return ""
        n = len(self.settings.get("layouts") or {})
        return _("Aktuell: Layout für {size} · {n} Grössen gemerkt", size=key.replace("x", "×"), n=n)

    # ---------------------------------------------------------------- the bar limits the map
    def _size_cap_tick(self):
        """1.65.2 (user: "die Map wird nicht grösser"): in a black bar the map can only be as wide as the bar – on
        3440×1440 about 31 % of the height. Say so under the size slider when that is what holds it back."""
        if not hasattr(self, "size_cap_var"):
            return
        text = ""
        if getattr(self, "_sel", "map") == "map":
            data = self._preview_data()
            gw, gh = data["screen"]
            bar = data.get("bar", 0)
            lay = next((lay for lay in data["layers"] if lay[0] == "map"), None)
            o = self.settings["overlay"]
            in_bar = (o["anchor"] == "auto" or o.get("keep_in_bar", True)) and not o.get("grow_past_bar", False)
            iw, ih = self.overlay.map_size() if self.overlay.has_map() else (0, 0)
            if not ih:
                pic = self._preview_sample()
                iw, ih = pic.size if pic is not None else (4, 5)
            if lay and in_bar and bar >= layout.MIN_BAR and (lay[1] < bar or lay[1] + lay[3] > gw - bar):
                avail = layout.max_width(bar, int(gh * o["margin"]))
                if self._map_height() * gh * iw / ih > avail + 2:     # the map itself wider than the bar
                    text = _("Die Karte ist so breit wie der schwarze Balken – grösser geht so nicht. Grösser mit "
                             "„Karte darf grösser als der Balken werden“ (ragt dann ins Spielbild).")
        if text != self.size_cap_var.get():
            self.size_cap_var.set(text)

    # ---------------------------------------------------------------- arrow keys in the preview
    def _nudge(self, dx, dy):
        """Arrow keys on the preview (moving mode): the picked element by (dx, dy) screen pixels."""
        lay = {n: (x, y) for n, x, y, _w, _h in self._preview_data()["layers"]}.get(getattr(self, "_sel", "map"))
        if lay is None:
            return
        self._preview_pick_now(("place", self._sel, lay[0] + dx, lay[1] + dy))
