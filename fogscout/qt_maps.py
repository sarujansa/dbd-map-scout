"""The maps page (1.66.4): realms on the left, the realm's maps as a picture grid or one map big.

1.8.72: the grid is built once for all maps and filtered by showing/hiding tiles (a search or a realm click no
longer throws 56 widgets away and makes them anew); the pictures come from ``thumbs.Loader`` (a thread, cached on
disk) and the tiles can be walked with the keyboard (arrows, Enter = big, Ctrl+Enter = show in the game).
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPlainTextEdit, QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QScrollArea,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from . import thumbs
from .qt_layouts import FlowRow
from .i18n import N_, _
from .mapnotes import MAX_CHARS as NOTE_CHARS
from .qt_common import pixmap_from_pil, steady_scroll, _label, _tip, _card, _set, _scroll_page


TILE_W, TILE_H = 150, 190          # px (logical) of a map tile on the maps page (1.2.18: + info line)


TILE_PIC = 124                     # the picture in it

PUMP_MS = 20                       # 1.8.72: how often the window thread takes finished thumbnails (≤ 8 each)
PUMP_TAKE = 8


ALL_MAPS, RECENT = "\x00all", "\x00recent"     # the two entries above the realms in the list


class MapTile(QFrame):
    """One map of the grid: its picture and name; a click shows it big, a double click shows it in the game.
    1.8.72: Enter does what the click does, Ctrl+Enter what the double click does, the arrows walk the grid."""

    def __init__(self, page, key, label):
        super().__init__()
        self.setProperty("class", "tile")
        self.setFixedSize(TILE_W, TILE_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._page, self.key = page, key
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        self.pic = QLabel()
        self.pic.setObjectName("tilepic")
        self.pic.setAlignment(Qt.AlignCenter)
        self.pic.setFixedHeight(TILE_PIC)
        lay.addWidget(self.pic)
        self.name = _label(label, "tile")
        self.name.setToolTip(label)
        fm = self.name.fontMetrics()
        self.name.setText(fm.elidedText(label, Qt.ElideRight, TILE_W - 16))
        lay.addWidget(self.name)
        self.info = _label("", "tileinfo")       # 1.2.18: rounds / Ø kills and the map's own settings
        lay.addWidget(self.info)
        self._mark = None

    def set_mark(self, text: str, tip: str = ""):
        if (text, tip) == self._mark:
            return
        self._mark = (text, tip)
        fm = self.info.fontMetrics()
        self.info.setText(fm.elidedText(text, Qt.ElideRight, TILE_W - 16))
        self.info.setToolTip(tip or text)

    def contextMenuEvent(self, e):
        self._page.open_menu(self.key, e.globalPos())

    def set_current(self, on: bool):
        if bool(self.property("current")) != on:
            self.setProperty("current", on)
            self.style().unpolish(self)
            self.style().polish(self)

    def mouseReleaseEvent(self, e):
        # the big view only after the double-click time: it covers the tiles, the second click would miss
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self._page.clicked(self.key)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._page.show_in_game(self.key)

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if e.modifiers() & Qt.ControlModifier:
                self._page.show_in_game(self.key)
            else:
                self._page.open_big(self.key)
        elif key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}[key]
            self._page.focus_step(self, *step)
        else:
            super().keyPressEvent(e)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._page.grid_scroll.ensureWidgetVisible(self, 0, 24)


class RealmDelegate(QStyledItemDelegate):
    """Realm list: the name left, the number of maps right (dim) – text "name\tcount"."""

    def paint(self, p, opt, index):
        name, _tab, count = str(index.data() or "").partition("\t")
        o = QStyleOptionViewItem(opt)
        self.initStyleOption(o, index)
        o.text = ""
        o.widget.style().drawControl(QStyle.CE_ItemViewItem, o, p, o.widget)
        r = o.rect.adjusted(10, 0, -10, 0)
        p.save()
        font = o.font
        font.setBold(bool(o.state & QStyle.State_Selected))
        p.setFont(font)
        p.setPen(o.palette.color(QPalette.Text))
        p.drawText(r, Qt.AlignVCenter | Qt.AlignLeft, p.fontMetrics().elidedText(name, Qt.ElideRight, r.width() - 36))
        p.setPen(o.palette.color(QPalette.PlaceholderText))
        p.drawText(r, Qt.AlignVCenter | Qt.AlignRight, count)
        p.restore()

    def sizeHint(self, opt, index):                 # as wide as the list: the count stays in sight
        return QSize(1, super().sizeHint(opt, index).height())


STYLE_BUTTONS = (("classic", N_("Original"), N_("Die Karten mit lila Boden, wie sie mitgeliefert werden – gilt auch im Spiel.")),
                 ("dark", N_("Dunkel"), N_("Durchsichtiger Boden mit dunklem Rand – gilt auch im Spiel.")),
                 # 1.8.16 (user: "zusätzlich", plain names): the dark conversion with a floor
                 ("grey", N_("Grau"), N_("Dunkelgrauer Boden – die Form der Map bleibt auf dem schwarzen Balken "
                                         "sichtbar. Gilt auch im Spiel.")),
                 ("grey_edge", N_("Grau mit Rand"), N_("Dunkelgrauer Boden mit hellem Rand – gilt auch im Spiel.")),
                 ("lilac", N_("Lila dunkel"), N_("Dunkles Lila mit lila Rand, erinnert an die Originalfarbe – gilt "
                                                 "auch im Spiel.")),
                 ("lilac_glass", N_("Lila transparent"), N_("Lila Boden, halb durchsichtig – gilt auch im Spiel.")))


class MapsPage(QWidget):
    """1.66.4 (user picked variant A): realms on the left (with "Alle Maps" and "Zuletzt gespielt" on top), the
    maps of the chosen one as tiles with their picture; a click shows a map big (with "Anzeigen"), a double click
    shows it in the game. The search filters over all realms. Pictures load bit by bit (``thumbs``: key -> path)."""

    def __init__(self, post, cache_dir=None):
        super().__init__()
        self._post = post
        self._preview_key = None
        self._preview_src = None
        self._shown_current = None
        self._items = None                 # [(realm, label, map_id, variant)] of all maps (1.8.72: unfiltered)
        self._built = None                 # the items the grid was built from
        self._found = None                 # keys the search found, None = no search (everything)
        self._recent = []
        self._thumbs = {}                  # (map_id, variant) -> picture path
        self._pix = {}                     # path -> QPixmap (made once)
        self._awaited = set()              # paths the loader still owes (1.8.72)
        self._tiles = {}                   # (map_id, variant) -> MapTile of the realm grid
        self._groups = []                  # [(realm, heading, FlowRow, [tiles])]
        self._recent_tiles = []            # own tiles of "Zuletzt gespielt" (a map can be in both)
        self._recent_head = self._recent_flow = None
        self._marks = {}                   # (map_id, variant) -> (info text, tooltip) (1.2.18)
        self._menu = None
        self._realm = None                 # chosen entry of the list (None: not yet – the shown map's realm)
        # 1.8.72: the thumbnails in the tile's size in device pixels (sharp on a scaled screen, a pixmap without
        # another resize), made in a thread, kept on disk
        ratio = self.devicePixelRatioF()
        self._loader = thumbs.Loader((round((TILE_W - 24) * ratio), round((TILE_PIC - 8) * ratio)), cache_dir)
        page, lay = _scroll_page("Maps", scroll=False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Suchen: Name, Realm, Abkürzung …"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._searched)
        self.search.returnPressed.connect(self._pick_first)
        row.addWidget(self.search, 1)
        # 1.3.3 (user: "im Maps eine Option, normale Maps anzuzeigen, quasi zu wechseln"): the map style right here –
        # the same setting as Overlay → Karte → Kartenstil, so the tiles and the game switch together
        self._style = None
        self.style_btns = {}
        style_row = QWidget()
        styles = FlowRow(style_row, spacing=6)
        style_label = QLabel(_("Kartenstil"))
        style_label.setProperty("class", "dim")
        styles.addWidget(style_label)
        self._style_group = QButtonGroup(self)          # 1.3.4: exclusive – the click shows at once, not on the
        self._style_group.setExclusive(True)            # next refresh (user: "Farbe wechselt erst nach 1 s")
        for key, label, tip in STYLE_BUTTONS:
            b = QPushButton(_(label))
            b.setCheckable(True)
            b.setProperty("class", "seg")
            b.setFocusPolicy(Qt.TabFocus)
            b.setToolTip(_(tip))
            b.clicked.connect(lambda _c=False, k=key: self._post("map_style", k))
            self._style_group.addButton(b)
            styles.addWidget(b)
            self.style_btns[key] = b
        lay.addLayout(row)
        lay.addWidget(style_row)                        # 1.8.16: six styles – a row of their own, wraps when narrow
        body = QHBoxLayout()
        body.setSpacing(16)
        self.realms = QListWidget()
        self.realms.setObjectName("realms")
        self.realms.setFixedWidth(250)          # 1.8.2: 230 cut "Hawkins National Laboratory"
        self.realms.setItemDelegate(RealmDelegate(self.realms))
        self.realms.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.realms.currentItemChanged.connect(self._realm_picked)
        body.addWidget(self.realms)
        self.stack = QStackedWidget()
        # the grid of tiles
        grid_page = QScrollArea()
        grid_page.setWidgetResizable(True)
        grid_page.setFrameShape(QFrame.NoFrame)
        steady_scroll(grid_page)
        inner = QWidget()
        inner.setObjectName("page")
        self.grid_lay = QVBoxLayout(inner)
        self.grid_lay.setContentsMargins(0, 0, 4, 0)
        self.grid_lay.setSpacing(10)
        self.grid_lay.addStretch()
        grid_page.setWidget(inner)
        self.grid_scroll = grid_page
        self.stack.addWidget(grid_page)
        # one map big
        big = _card()
        cl = QVBoxLayout(big)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(6)
        top = QHBoxLayout()
        self.p_back = QPushButton("← " + _("Zurück"))
        self.p_back.setToolTip(_tip("Zurück"))
        self.p_back.clicked.connect(self.close_big)
        top.addWidget(self.p_back)
        top.addStretch()
        self.p_show = QPushButton(_("Anzeigen"))
        self.p_show.setObjectName("primary")
        self.p_show.setToolTip(_tip("Anzeigen"))
        self.p_show.clicked.connect(self._show_selected)
        top.addWidget(self.p_show)
        cl.addLayout(top)
        self.p_name = _label(cls="map", wrap=True)
        self.p_realm = _label(cls="dim", wrap=True)
        self.p_pic = QLabel()
        self.p_pic.setObjectName("thumb")
        self.p_pic.setAlignment(Qt.AlignCenter)
        self.p_pic.setMinimumSize(160, 160)
        self.p_pic.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)   # scales with the card, not the image
        cl.addWidget(self.p_name)
        cl.addWidget(self.p_realm)
        cl.addWidget(self.p_pic, 1)
        # 1.8.54 (user: "Notizen für die Map"): the own note, saved while typing, shown in the game with the map
        cl.addWidget(_label(_("Eigene Notiz (im Spiel unter dem Timer)"), "dim"))
        self.p_note = QPlainTextEdit()
        self.p_note.setPlaceholderText(_("z. B. Shack links vom Main, Gen im Keller …"))
        self.p_note.setToolTip(_tip("Eigene Notiz"))
        self.p_note.setTabChangesFocus(True)
        self.p_note.setFixedHeight(84)
        self.p_note.setEnabled(False)
        self.p_note.textChanged.connect(self._note_typed)
        cl.addWidget(self.p_note)
        self._note_key = None              # map_id the editor shows the note of
        self._note_saver = QTimer(self)
        self._note_saver.setSingleShot(True)
        self._note_saver.setInterval(600)
        self._note_saver.timeout.connect(self._save_note)
        self.stack.addWidget(big)
        body.addWidget(self.stack, 1)
        lay.addLayout(body, 1)
        self.hint = _label(_("Klick oder Enter = groß ansehen · Doppelklick oder Strg+Enter = jetzt anzeigen. Die "
                             "Erkennung übernimmt beim nächsten Match wieder."), "dim", wrap=True)
        lay.addWidget(self.hint)
        prow = QHBoxLayout()
        b = QPushButton(_("Kartenbild hinzufügen …"))
        b.setToolTip(_tip("Kartenbild hinzufügen …"))
        b.clicked.connect(lambda: self._post("add_picture"))
        prow.addWidget(b)
        prow.addWidget(_label(_("eigenes Bild für eine Map (Hintergrund wird entfernt)"), "dim"))
        prow.addStretch()
        lay.addLayout(prow)
        self._pump = QTimer(self)
        self._pump.setInterval(PUMP_MS)
        self._pump.timeout.connect(self._load_some)
        self._click_key = None
        self._clicker = QTimer(self)
        self._clicker.setSingleShot(True)
        self._clicker.timeout.connect(self._clicked_once)
        self.show_preview(None)

    # ------------------------------------------------------------------ list of realms
    def _searched(self, text):
        self._post("search", text)

    def _fill_realms(self):
        counts = {}
        for realm, _label_, _mid, _v in self._items:
            counts[realm] = counts.get(realm, 0) + 1
        want = [(ALL_MAPS, _("Alle Maps"), sum(counts.values()))]
        if self._recent:
            want.append((RECENT, _("Zuletzt gespielt"), len(self._recent)))
        want += [(r, r, n) for r, n in counts.items()]
        have = [(self.realms.item(i).data(Qt.UserRole), self.realms.item(i).text())
                for i in range(self.realms.count())]
        texts = [(k, f"{t}\t{n}") for k, t, n in want]
        if have == texts:
            return
        self.realms.blockSignals(True)
        self.realms.clear()
        for k, text in texts:
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, k)
            self.realms.addItem(it)
        self.realms.blockSignals(False)

    def _select_realm(self, key):
        for i in range(self.realms.count()):
            if self.realms.item(i).data(Qt.UserRole) == key:
                self.realms.blockSignals(True)
                self.realms.setCurrentRow(i)
                self.realms.blockSignals(False)
                return

    def _realm_picked(self, item, _prev=None):
        if item is None:
            return
        self._realm = item.data(Qt.UserRole)
        self.close_big()
        self._apply_filter()

    # ------------------------------------------------------------------ the tiles
    def _clear_grid(self):
        self._awaited.clear()
        self._pump.stop()
        while self.grid_lay.count() > 1:                    # all but the stretch at the end
            it = self.grid_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            elif it.layout() is not None:
                lay = it.layout()
                while lay.count():
                    sub = lay.takeAt(0).widget()
                    if sub is not None:
                        sub.deleteLater()
        self._tiles, self._groups, self._recent_tiles = {}, [], []
        self._recent_head = self._recent_flow = None

    def _add_group(self, heading, maps) -> tuple:
        """A heading and a FlowRow of tiles for ``maps`` [(label, key)] at the end of the grid."""
        head = _label(heading.upper(), "h2")
        self.grid_lay.insertWidget(self.grid_lay.count() - 1, head)
        flow = FlowRow(spacing=12)
        tiles = []
        for label, key in maps:
            t = MapTile(self, key, label)
            flow.addWidget(t)
            tiles.append(t)
            mark = self._marks.get(key)
            if mark:
                t.set_mark(*mark[:2])
        self.grid_lay.insertLayout(self.grid_lay.count() - 1, flow)
        # 1.8.72: shown now, not by Qt's queued show – the first layout pass counted the tiles as hidden (zero
        # height), the scroll area sized the grid to its viewport and the tiles piled up until a resize
        head.show()
        for t in tiles:
            t.show()
        return head, flow, tiles

    def _grid_batch(self, change):
        """Run ``change`` (showing/hiding/adding tiles) with the grid's widget hidden meanwhile: showing a tile
        under a visible parent costs ~1.2 ms each (measured: 56 tiles 68 ms, under a hidden parent 3 ms); nothing
        is painted in between, the scroll position stays. A tile that had the focus keeps it."""
        inner = self.grid_scroll.widget()
        focus = QApplication.focusWidget()
        inner.setVisible(False)
        try:
            change()
        finally:
            inner.setVisible(True)
        if isinstance(focus, MapTile) and focus._page is self and not focus.isHidden():
            focus.setFocus(Qt.OtherFocusReason)

    def _build_grid(self):
        """All maps as tiles, grouped by realm (once per catalog; the search and the realm list only show and
        hide – 1.8.72), then "Zuletzt gespielt" with tiles of its own."""
        def build():
            self._clear_grid()
            groups = {}
            for realm, label, mid, v in self._items or []:
                groups.setdefault(realm, []).append((label, (mid, v)))
            for realm, maps in groups.items():
                head, flow, tiles = self._add_group(realm, maps)
                self._groups.append((realm, head, flow, tiles))
                for t in tiles:
                    self._tiles[t.key] = t
            self._build_recent()
        self._grid_batch(build)

    def _build_recent(self):
        """The tiles of "Zuletzt gespielt" (newest first, each map once) – made anew when the list changes."""
        if self._recent_flow is not None:
            self.grid_lay.removeWidget(self._recent_head)
            self._recent_head.deleteLater()
            while self._recent_flow.count():
                sub = self._recent_flow.takeAt(0).widget()
                if sub is not None:
                    sub.deleteLater()
            self.grid_lay.removeItem(self._recent_flow)
            self._recent_head = self._recent_flow = None
        self._recent_tiles = []
        by_mid = {}
        for _r, label, mid, v in self._items or []:
            by_mid.setdefault(mid, (label, (mid, v)))
        maps = [by_mid[m] for m in self._recent if m in by_mid]
        if maps:
            self._recent_head, self._recent_flow, self._recent_tiles = self._add_group(_("Zuletzt gespielt"), maps)
        self._apply_filter()

    def _all_tiles(self):
        return list(self._tiles.values()) + self._recent_tiles

    def visible_tiles(self) -> list:
        """The tiles on display, in grid order (the realm chosen, the search's hits or the recent maps)."""
        if self._recent_flow is not None and not self._recent_head.isHidden():
            return list(self._recent_tiles)
        return [t for _r, _h, _f, tiles in self._groups for t in tiles if not t.isHidden()]

    def _apply_filter(self):
        """Show the tiles of the chosen realm (or all), with a search those it found in every realm, for
        "Zuletzt gespielt" its own group – nothing is built here."""
        found = self._found
        recent_mode = self._realm == RECENT and found is None and self._recent_flow is not None

        def wanted(realm, t):
            return (not recent_mode and (found is None or t.key in found)
                    and (found is not None or self._realm in (None, ALL_MAPS, RECENT) or realm == self._realm))

        def apply():
            for realm, head, _flow, tiles in self._groups:
                any_on = False
                for t in tiles:
                    on = wanted(realm, t)
                    t.setVisible(on)
                    any_on = any_on or on
                head.setVisible(any_on)
            if self._recent_flow is not None:
                self._recent_head.setVisible(recent_mode)
                for t in self._recent_tiles:
                    t.setVisible(recent_mode)
        changes = any(t.isHidden() == wanted(realm, t) for realm, _h, _f, tiles in self._groups for t in tiles) \
            or (self._recent_flow is not None and self._recent_head.isHidden() == recent_mode)
        if changes:                                   # a refresh that changes nothing costs nothing
            self._grid_batch(apply)
        self._mark_current()
        self._request_pictures()

    # ------------------------------------------------------------------ the pictures (1.8.72: thumbs.Loader)
    def _request_pictures(self):
        """Ask the loader for every picture a tile still lacks – the tiles on display first, the hidden ones
        after them (a realm click later finds them ready)."""
        shown = self.visible_tiles()
        order = shown + [t for t in self._all_tiles() if t not in shown]
        paths, seen = [], set()
        for t in order:
            path = self._thumbs.get(t.key)
            if path and path not in seen and path not in self._pix:
                seen.add(path)
                paths.append(path)
        self._awaited = set(paths)
        if paths:
            self._loader.request(paths)
            self._pump.start()
        else:
            self._pump.stop()

    def _pixmap(self, w: int, h: int, data: bytes) -> QPixmap:
        """The thumbnail (already the tile's size in device pixels) as a pixmap – ~0.3 ms, no resize."""
        if not w or not h:
            return QPixmap()
        pm = QPixmap.fromImage(QImage(data, w, h, 4 * w, QImage.Format_RGBA8888).copy())
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        return pm

    def _apply_picture(self, result):
        path, w, h, data = result
        self._awaited.discard(path)
        pm = self._pix.get(path)
        if pm is None:
            pm = self._pix[path] = self._pixmap(w, h, data)
        if not pm.isNull():
            for t in self._all_tiles():
                if self._thumbs.get(t.key) == path:
                    t.pic.setPixmap(pm)

    def _load_some(self):
        """Window thread, every PUMP_MS: the thumbnails the thread finished become pixmaps (≤ PUMP_TAKE a tick,
        ≈ 1 ms each – the page stays smooth while the pictures come in)."""
        for result in self._loader.take(PUMP_TAKE):
            self._apply_picture(result)
        if not self._awaited:
            self._pump.stop()

    def load_all(self):
        """Every awaited picture now, in this thread (tests, no waiting for the loader's thread)."""
        for path in list(self._awaited):
            self._apply_picture(self._loader.make(path))
        self._awaited.clear()
        self._pump.stop()

    def _mark_current(self):
        cur = tuple(self._shown_current) if self._shown_current else None
        for t in self._all_tiles():
            t.set_current(t.key == cur)

    # ------------------------------------------------------------------ keyboard (1.8.72)
    def focus_step(self, tile, dx: int, dy: int):
        """Move the focus from ``tile`` to its neighbour in the grid: dx = previous/next in reading order, dy =
        the nearest tile (by x) in the row above/below."""
        shown = self.visible_tiles()
        if tile not in shown:
            return
        inner = self.grid_scroll.widget()
        pos = {t: t.mapTo(inner, QPoint(0, 0)) for t in shown}
        order = sorted(shown, key=lambda t: (pos[t].y(), pos[t].x()))
        target = None
        if dx:
            i = order.index(tile) + dx
            if 0 <= i < len(order):
                target = order[i]
        else:
            y0, x0 = pos[tile].y(), pos[tile].x()
            rows = [t for t in order if (pos[t].y() > y0 if dy > 0 else pos[t].y() < y0)]
            if rows:
                edge = min(pos[t].y() for t in rows) if dy > 0 else max(pos[t].y() for t in rows)
                row = [t for t in rows if pos[t].y() == edge]
                target = min(row, key=lambda t: abs(pos[t].x() - x0))
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------------------ right click (1.2.18)
    MENU = (("show", N_("Anzeigen")), ("rotate", N_("Drehen ↻")),
            ("size_reset", N_("Eigene Grösse und Drehung zurücksetzen")), ("picture", N_("Kartenbild ersetzen …")),
            ("note", N_("Notiz bearbeiten …")))

    def menu_entries(self, key):
        """[(action, label, enabled)] of a tile's context menu – the reset only when the map has own values."""
        mark = self._marks.get(tuple(key))
        own = bool(mark and len(mark) > 2 and mark[2])
        return [(a, _(label), a != "size_reset" or own) for a, label in self.MENU]

    def open_menu(self, key, pos):
        """A popup (no exec: no second event loop); every entry posts ("map_action", (action, key))."""
        menu = QMenu(self)
        for action, label, enabled in self.menu_entries(key):
            act = menu.addAction(label)
            act.setEnabled(enabled)
            if action == "note":                     # 1.8.54: here – the map big, the cursor in its note
                act.triggered.connect(lambda _c=False, k=tuple(key): self.edit_note(k))
            else:
                act.triggered.connect(lambda _c=False, a=action, k=tuple(key): self._post("map_action", (a, k)))
        self._menu = menu
        menu.popup(pos)

    # ------------------------------------------------------------------ one map big
    def clicked(self, key):
        self._click_key = tuple(key)
        self._clicker.start(QApplication.doubleClickInterval())

    def _clicked_once(self):
        key, self._click_key = self._click_key, None
        if key:
            self.open_big(key)

    def open_big(self, key):
        self._post("map_preview", tuple(key))
        self.stack.setCurrentIndex(1)

    def close_big(self):
        self._save_note()
        self.stack.setCurrentIndex(0)

    def edit_note(self, key):
        self.open_big(key)
        self.p_note.setFocus()

    # ------------------------------------------------------------------ own note of the map shown big (1.8.54)
    def _note_typed(self):
        if self._note_key is None:
            return
        text = self.p_note.toPlainText()
        if len(text) > NOTE_CHARS:                     # the game shows four lines – more is cut while typing
            cur = self.p_note.textCursor()
            pos = min(cur.position(), NOTE_CHARS)
            self.p_note.blockSignals(True)
            self.p_note.setPlainText(text[:NOTE_CHARS])
            self.p_note.blockSignals(False)
            cur = self.p_note.textCursor()
            cur.setPosition(pos)
            self.p_note.setTextCursor(cur)
        self._note_saver.start()

    def _save_note(self):
        """The note typed so far to the app (settings, the overlay when that map is on display)."""
        if self._note_saver.isActive() or self._note_dirty():
            self._note_saver.stop()
            self._post("map_note", (self._note_key, self.p_note.toPlainText()))
            self._note_saved = self.p_note.toPlainText()

    def _note_dirty(self) -> bool:
        return self._note_key is not None and self.p_note.toPlainText() != getattr(self, "_note_saved", "")

    def _show_note(self, map_id, text):
        """The editor on another map: what was typed for the last one is saved first."""
        if map_id == self._note_key:
            return
        self._save_note()
        self._note_key = None                          # no save of the text set here
        self.p_note.setPlainText(text or "")
        self._note_saved = text or ""
        self._note_key = map_id
        self.p_note.setEnabled(map_id is not None)

    def show_in_game(self, key):
        self._clicker.stop()
        self._click_key = None
        self._post("show_map", tuple(key))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.stack.currentIndex() == 1:
            self.close_big()
            return
        super().keyPressEvent(e)

    def _show_selected(self):
        if self._preview_key:
            self._post("show_map", tuple(self._preview_key))

    def show_preview(self, p):
        """p = (map_id, variant, name, realm, PIL picture or None, own note) or None (nothing selected)."""
        self._show_note(p[0] if p else None, p[5] if p and len(p) > 5 else "")
        key = tuple(p[:2]) if p else None
        if p is not None and key == self._preview_key and p[4] is self._preview_src:
            return
        self._preview_key, self._preview_src = key, (p[4] if p else None)
        _set(self.p_name, p[2] if p else _("Keine Map gewählt"))
        _set(self.p_realm, p[3] if p else "")
        self.p_show.setEnabled(p is not None)
        self._scale_preview()

    def _scale_preview(self):
        src = self._preview_src
        if src is None:
            self.p_pic.clear()
            return
        w, h = max(1, self.p_pic.width() - 12), max(1, self.p_pic.height() - 12)
        fit_h = max(1, min(h, round(w * src.height / src.width)))
        self.p_pic.setPixmap(pixmap_from_pil(src, fit_h, self.devicePixelRatioF()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._scale_preview()

    def _pick_first(self):
        """Enter in the search field: the first map on display goes to the game."""
        for _r, _l, mid, v in self._items or []:
            if self._found is None or (mid, v) in self._found:
                self._post("show_map", (mid, v))
                return

    # ------------------------------------------------------------------ from the app
    def show_maps(self, items, current, thumbs=None, recent=None, marks=None, style=None, found=None):
        """items [(realm, label, map_id, variant)] of all maps, the map on display, picture paths, the map ids
        played last (newest first), ``marks`` {key: (info text, tooltip, has own values)} (1.2.18), ``style`` = the
        map style for the buttons (1.3.3), ``found`` = the keys the search matched (1.8.72; None: no search)."""
        if style is not None and style != self._style:
            self._style = style
            for key, b in self.style_btns.items():
                b.setChecked(key == style)
        if marks is not None and marks != self._marks:
            self._marks = dict(marks)
            for t in self._all_tiles():
                mark = self._marks.get(t.key)
                t.set_mark(*mark[:2]) if mark else t.set_mark("")
        recent = list(recent or [])
        items = list(items)
        changed = items != self._items
        recent_changed = recent != self._recent
        self._items, self._recent = items, recent
        if changed or recent_changed:
            self._fill_realms()
        if changed:
            if self._realm is None or not any(self.realms.item(i).data(Qt.UserRole) == self._realm
                                              for i in range(self.realms.count())):
                realm = next((r for r, _l, m, v in self._items if current and (m, v) == tuple(current)), None)
                self._realm = realm or ALL_MAPS            # first look: the realm of the map on display
            self._select_realm(self._realm)
        if thumbs is not None and dict(thumbs) != self._thumbs:
            self._thumbs = dict(thumbs)                    # e.g. the dark pictures are made now: asked for below
        found = set(found) if found is not None else None
        self._found = found
        self._shown_current = current
        if changed:
            self._build_grid()                             # ends in _apply_filter → pictures requested
        elif recent_changed:
            self._build_recent()
        else:
            self._apply_filter()
