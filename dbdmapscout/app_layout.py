"""Overlay layout, part of App (1.65): undo of place/size changes, one layout per DBD window size, arrow keys in
the preview. Pure logic in layoutmem.py."""
from __future__ import annotations

import time

from . import layoutmem
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
        from .app_sysinfo import HUD_SIDES, MEDIA_SPOTS
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

    # ---------------------------------------------------------------- arrow keys in the preview
    def _nudge(self, dx, dy):
        """Arrow keys on the preview (moving mode): the picked element by (dx, dy) screen pixels."""
        lay = {n: (x, y) for n, x, y, _w, _h in self._preview_data()["layers"]}.get(getattr(self, "_sel", "map"))
        if lay is None:
            return
        self._preview_pick_now(("place", self._sel, lay[0] + dx, lay[1] + dy))
