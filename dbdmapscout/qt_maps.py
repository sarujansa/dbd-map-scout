"""The maps page (1.66.4): realms on the left, the realm's maps as a picture grid or one map big.
"""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QScrollArea,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .qt_layouts import FlowRow
from .i18n import N_, _
from .qt_common import pixmap_from_pil, _label, _tip, _card, _set, _scroll_page


TILE_W, TILE_H = 150, 190          # px (logical) of a map tile on the maps page (1.2.18: + info line)


TILE_PIC = 124                     # the picture in it


ALL_MAPS, RECENT = "\x00all", "\x00recent"     # the two entries above the realms in the list


class MapTile(QFrame):
    """One map of the grid: its picture and name; a click shows it big, a double click shows it in the game."""

    def __init__(self, page, key, label):
        super().__init__()
        self.setProperty("class", "tile")
        self.setFixedSize(TILE_W, TILE_H)
        self.setCursor(Qt.PointingHandCursor)
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
                 ("dark", N_("Dunkel"), N_("Die Karten im Stil von Fallen Refuge (durchsichtiger Boden, dunkler Rand) – "
                                           "gilt auch im Spiel.")))


class MapsPage(QWidget):
    """1.66.4 (user picked variant A): realms on the left (with "Alle Maps" and "Zuletzt gespielt" on top), the
    maps of the chosen one as tiles with their picture; a click shows a map big (with "Anzeigen"), a double click
    shows it in the game. The search filters over all realms. Pictures load bit by bit (``thumbs``: key -> path)."""

    def __init__(self, post):
        super().__init__()
        self._post = post
        self._preview_key = None
        self._preview_src = None
        self._shown_current = None
        self._items = None
        self._recent = []
        self._thumbs = {}                  # (map_id, variant) -> picture path
        self._pix = {}                     # path -> QPixmap (made once)
        self._todo = []                    # tiles still waiting for their picture
        self._tiles = {}
        self._marks = {}                   # (map_id, variant) -> (info text, tooltip) (1.2.18)
        self._menu = None
        self._realm = None                 # chosen entry of the list (None: not yet – the shown map's realm)
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
        for key, label, tip in STYLE_BUTTONS:
            b = QPushButton(_(label))
            b.setCheckable(True)
            b.setProperty("class", "seg")
            b.setFocusPolicy(Qt.TabFocus)
            b.setToolTip(_(tip))
            b.clicked.connect(lambda _c=False, k=key: self._post("map_style", k))
            row.addWidget(b)
            self.style_btns[key] = b
        lay.addLayout(row)
        body = QHBoxLayout()
        body.setSpacing(16)
        self.realms = QListWidget()
        self.realms.setObjectName("realms")
        self.realms.setFixedWidth(230)
        self.realms.setItemDelegate(RealmDelegate(self.realms))
        self.realms.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.realms.currentItemChanged.connect(self._realm_picked)
        body.addWidget(self.realms)
        self.stack = QStackedWidget()
        # the grid of tiles
        grid_page = QScrollArea()
        grid_page.setWidgetResizable(True)
        grid_page.setFrameShape(QFrame.NoFrame)
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
        self.stack.addWidget(big)
        body.addWidget(self.stack, 1)
        lay.addLayout(body, 1)
        self.hint = _label(_("Klick = groß ansehen · Doppelklick = jetzt anzeigen. Die Erkennung übernimmt beim "
                             "nächsten Match wieder."), "dim", wrap=True)
        lay.addWidget(self.hint)
        prow = QHBoxLayout()
        b = QPushButton(_("Kartenbild hinzufügen …"))
        b.setToolTip(_tip("Kartenbild hinzufügen …"))
        b.clicked.connect(lambda: self._post("add_picture"))
        prow.addWidget(b)
        prow.addWidget(_label(_("eigenes Bild für eine Map (Hintergrund wird entfernt)"), "dim"))
        prow.addStretch()
        lay.addLayout(prow)
        self._loader = QTimer(self)
        self._loader.setInterval(10)
        self._loader.timeout.connect(self._load_some)
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
        self._build_grid()

    # ------------------------------------------------------------------ the tiles
    def _visible_items(self):
        """[(heading, [(label, key)])] for the chosen entry (a search shows everything it found)."""
        items = self._items or []
        if self._realm == RECENT and not self.search.text():
            by_mid = {}
            for _r, label, mid, v in items:
                by_mid.setdefault(mid, (label, (mid, v)))
            return [(_("Zuletzt gespielt"), [by_mid[m] for m in self._recent if m in by_mid])]
        groups = {}
        for realm, label, mid, v in items:
            if self._realm in (None, ALL_MAPS, RECENT) or self.search.text() or realm == self._realm:
                groups.setdefault(realm, []).append((label, (mid, v)))
        return list(groups.items())

    def _build_grid(self):
        self._loader.stop()
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
        self._tiles = {}
        self._todo = []
        for heading, maps in self._visible_items():
            self.grid_lay.insertWidget(self.grid_lay.count() - 1, _label(heading.upper(), "h2"))
            flow = FlowRow(spacing=12)
            for label, key in maps:
                t = MapTile(self, key, label)
                flow.addWidget(t)
                self._tiles[key] = t
                self._todo.append(t)
                mark = self._marks.get(key)
                if mark:
                    t.set_mark(*mark[:2])
            self.grid_lay.insertLayout(self.grid_lay.count() - 1, flow)
        self._mark_current()
        if self._todo:
            self._loader.start()

    def _load_some(self):
        """A few pictures per tick, so that the page shows at once and fills in (52 maps ≈ 1 s in all)."""
        done = 0
        while self._todo and done < 2:
            t = self._todo.pop(0)
            path = self._thumbs.get(t.key)
            if not path:
                continue
            pm = self._pix.get(path)
            if pm is None:
                try:
                    with Image.open(path) as im:
                        im.seek(0)
                        pic = im.convert("RGBA")
                    bw, bh = TILE_W - 24, TILE_PIC - 8
                    ratio = self.devicePixelRatioF()
                    pic.thumbnail((round(2 * bw * ratio), round(2 * bh * ratio)))      # fast, then sharp
                    pm = pixmap_from_pil(pic, max(1, min(bh, round(bw * pic.height / pic.width))), ratio)
                except (OSError, ValueError):
                    pm = QPixmap()
                self._pix[path] = pm
                done += 1
            if not pm.isNull():
                t.pic.setPixmap(pm)
        if not self._todo:
            self._loader.stop()

    def _mark_current(self):
        cur = tuple(self._shown_current) if self._shown_current else None
        for key, t in self._tiles.items():
            t.set_current(key == cur)

    # ------------------------------------------------------------------ right click (1.2.18)
    MENU = (("show", N_("Anzeigen")), ("rotate", N_("Drehen ↻")),
            ("size_reset", N_("Eigene Grösse und Drehung zurücksetzen")), ("picture", N_("Kartenbild ersetzen …")))

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
        self.stack.setCurrentIndex(0)

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
        """p = (map_id, variant, name, realm, PIL picture or None) or None (nothing selected)."""
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
        if self._items:
            self._post("show_map", (self._items[0][2], self._items[0][3]))

    # ------------------------------------------------------------------ from the app
    def show_maps(self, items, current, thumbs=None, recent=None, marks=None, style=None):
        """items [(realm, label, map_id, variant)] (already searched), the map on display, picture paths, the
        map ids played last (newest first), ``marks`` {key: (info text, tooltip, has own values)} (1.2.18),
        ``style`` = the map style for the two buttons (1.3.3)."""
        if style is not None and style != self._style:
            self._style = style
            for key, b in self.style_btns.items():
                b.setChecked(key == style)
        if marks is not None and marks != self._marks:
            self._marks = dict(marks)
            for key, t in self._tiles.items():
                mark = self._marks.get(key)
                t.set_mark(*mark[:2]) if mark else t.set_mark("")
        if thumbs is not None and dict(thumbs) != self._thumbs:
            old, self._thumbs = self._thumbs, dict(thumbs)
            again = [t for k, t in self._tiles.items() if self._thumbs.get(k) != old.get(k) and t not in self._todo]
            if again:                                  # e.g. the dark pictures are made now: the tiles get them
                self._todo += again
                self._loader.start()
        recent = list(recent or [])
        changed = items != self._items or recent != self._recent
        self._items, self._recent = list(items), recent
        if changed:
            self._fill_realms()
            if self._realm is None or not any(self.realms.item(i).data(Qt.UserRole) == self._realm
                                              for i in range(self.realms.count())):
                realm = next((r for r, _l, m, v in self._items if current and (m, v) == tuple(current)), None)
                self._realm = realm or ALL_MAPS            # first look: the realm of the map on display
            self._select_realm(self._realm)
            self._build_grid()
        if current != self._shown_current:
            self._shown_current = current
            self._mark_current()
