"""The pages of the control window: the overview, the hand-made pages (SPECS) with their controls, the pages built from
a tab's structure (AutoPage), dialogs and the setup assistant.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from . import qt_theme
from .qt_layouts import FlowRow, TileGrid, WrapCheck
from .i18n import N_, _
from .qt_common import SLIDER_MAX, pixmap_from_pil, _label, _tip, _card, _set, _scroll_page
from .qt_views import FactBox, Table, LogView, HotkeyButton, Chart, SwatchView, TilesView, DashboardView
from .qt_preview import PreviewView


THUMB_H = 170                     # px (logical) of the map picture on the overview


SETUP_W = 820                     # px (logical): widest step of the setup assistant


# The setup assistant on the first start (1.60, user's wish): three steps of controls that are also on the pages
# (same keys – the same widgets of the UI model). ("note", text) = an explaining line of the step itself.
GAME_LANGS = ("en", "de", "fr", "es", "es-MX", "it", "pl", "pt-BR", "tr")   # app.LANGS (test: the same)


SETUP_HOTKEYS = ("toggle_overlay", "rotate_map", "edit_position", "scan_now", "reject_map")


SETUP = (
    (N_("Sprache"), (
        ("note", N_("Das Programm liest beim Match-Start den Map-Namen aus dem Bild. Hake die Sprache an, in der "
                    "du Dead by Daylight spielst (mehrere gehen).")),
        ("grid", 5, tuple(("check", f"det.lang.{code}") for code in GAME_LANGS)),
        ("note", N_("Sprache dieses Programms:")),
        ("row", (("combo", "st.lang"), ("stretch",))), ("hint", "st.lang_note"))),
    (N_("Overlay"), (
        ("note", N_("Die Karte erscheint beim Match-Start von selbst und verschwindet nach der Runde. „automatisch“ "
                    "legt sie in den schwarzen Rand neben dem Spielbild (Ultrawide) bzw. neben das DBD-Fenster.")),
        ("row", (("label", "ov.anchor.label"), ("combo", "ov.anchor"), ("stretch",))),
        ("slider", "ov.size"),
        ("row", (("button", "ov.test"), ("button", "ov.edit"), ("stretch",))),
        ("note", N_("„Overlay testen“ zeigt die Karte sofort, „Mit der Maus verschieben“ lässt sie dich hinziehen.")))),
    (N_("Tasten und Start"), (
        ("note", N_("Die wichtigsten Tasten – zum Ändern draufklicken und die neue Kombination drücken. Alle "
                    "Tasten findest du später unter Einstellungen.")),
        ("grid", 1, tuple(("row", (("label", f"st.hk.{k}.label"), ("stretch",), ("hotkey", f"st.hk.{k}")))
                          for k in SETUP_HOTKEYS)),
        ("check", "st.autostart"), ("check", "st.lobby_notify"))),
)


class OverviewPage(QWidget):
    def __init__(self, post):
        super().__init__()
        self.setObjectName("page")
        self._post = post
        self._thumb_rev = None
        self._pill_style = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("page")
        scroll.setWidget(body)
        page = QVBoxLayout(body)
        page.setContentsMargins(22, 18, 22, 18)
        page.setSpacing(14)

        top = FlowRow(spacing=12)                 # narrow window: the status goes below the title
        top.right = 1
        top.addWidget(_label(_("Übersicht"), "h1"))
        self.pill = QLabel()
        self.pill.setObjectName("pill")
        self.pill.setMaximumWidth(520)
        top.addWidget(self.pill)
        page.addLayout(top)

        # the map on display: picture, name, values, actions
        card = _card()
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(18)
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(THUMB_H + 12, THUMB_H + 12)
        self.thumb.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.thumb, alignment=Qt.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(_label(_("Aktuelle Map").upper(), "h2"))
        self.map_name = _label(cls="map", wrap=True)
        info.addWidget(self.map_name)
        self.map_line = _label(cls="dim", wrap=True)
        info.addWidget(self.map_line)
        self.queue = _label(cls="dim", wrap=True)
        info.addWidget(self.queue)
        info.addSpacing(8)
        grid = TileGrid(min_width=110, columns=4, spacing=20)    # four values side by side, or two by two
        self.facts = [FactBox() for _i in range(4)]
        for box in self.facts:
            grid.addWidget(box)
        info.addLayout(grid)
        self.note = _label(cls="note", wrap=True)
        info.addWidget(self.note)
        self.unknown = QWidget()
        ul = QHBoxLayout(self.unknown)
        ul.setContentsMargins(0, 0, 0, 0)
        self.unknown_text = _label(cls="note", wrap=True)
        ul.addWidget(self.unknown_text, 1)
        for text, action in ((N_("Zuordnen …"), "assign"), (N_("Bild hinzufügen …"), "picture"),
                             ("✕", "dismiss_unknown")):
            ub = QPushButton(_(text))
            ub.setToolTip(_tip(text))
            ub.clicked.connect(lambda _c=False, a=action: self._post(a))
            ul.addWidget(ub)
        info.addWidget(self.unknown)
        info.addStretch()
        btns = FlowRow(spacing=6)                 # the buttons wrap instead of running out of the card
        self.buttons = {}
        for key in ("scan", "choose", "rotate", "toggle", "reject", "confirm", "layout", "floor"):
            b = QPushButton()
            if key == "scan":
                b.setObjectName("primary")
            b.clicked.connect(lambda _c=False, k=key: self._post(k))
            btns.addWidget(b)
            self.buttons[key] = b
        info.addLayout(btns)
        cl.addLayout(info, 1)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)    # without a picture: only as tall as its text
        page.addWidget(card)

        # today
        head = QHBoxLayout()
        head.addWidget(_label(_("Heute").upper(), "h2"))
        head.addStretch()
        self.today_note = _label(cls="dim")
        head.addWidget(self.today_note)
        page.addLayout(head)
        tiles = TileGrid(min_width=170, columns=4)
        self.tiles = []
        for _i in range(4):
            t = _card()
            tl = QVBoxLayout(t)
            tl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)
            tl.addWidget(box)
            tiles.addWidget(t)
            self.tiles.append(box)
        page.addLayout(tiles)

        # system values and the last rounds
        row = TileGrid(min_width=300, columns=2)  # side by side, below each other in a narrow window
        sysc = _card()
        self.sys_lay = QVBoxLayout(sysc)
        self.sys_lay.setContentsMargins(14, 12, 14, 12)
        self.sys_lay.addWidget(_label(_("System").upper(), "h2"))
        self.sys_rows = []
        self.sys_note = _label(cls="dim", wrap=True)
        self.sys_lay.addWidget(self.sys_note)
        self.sys_lay.addStretch()
        row.addWidget(sysc)
        last = _card()
        self.last_lay = QVBoxLayout(last)
        self.last_lay.setContentsMargins(14, 12, 14, 12)
        self.last_lay.addWidget(_label(_("Letzte Runden").upper(), "h2"))
        self.last_rows = []
        self.last_empty = _label(_("Noch keine Runden gespeichert."), "dim")
        self.last_lay.addWidget(self.last_empty)
        self.last_lay.addStretch()
        row.addWidget(last)
        page.addLayout(row)
        page.addStretch()

    # ------------------------------------------------------------- update
    def update_page(self, o, thumb=None, tips=None):
        _set(self.pill, "●  " + o.status_text)
        pill = qt_theme.pill_style(o.status_kind)
        if pill != self._pill_style:                  # re-styling repaints: only on a change
            self._pill_style = pill
            self.pill.setStyleSheet(pill)
        _set(self.map_name, o.map_label or _("Noch keine Map"))
        _set(self.map_line, o.map_line)
        _set(self.queue, o.queue)
        self.queue.setVisible(bool(o.queue))
        # 1.66.3: without a map no empty picture box and no row of dashes – only the line how one comes
        self.thumb.setVisible(bool(o.map_label))
        empty = not o.map_label and all(f.value == "–" for f in o.facts)
        for box in self.facts:
            box.setVisible(not empty)
        if o.thumb_rev != self._thumb_rev:
            self._thumb_rev = o.thumb_rev
            if thumb is None:
                self.thumb.clear()
            else:
                h = THUMB_H if thumb.height >= thumb.width else round(THUMB_H * thumb.height / thumb.width)
                self.thumb.setPixmap(pixmap_from_pil(thumb, max(1, h), self.devicePixelRatioF()))   # fits both ways
        for box, f in zip(self.facts, o.facts):
            box.show_fact(f)
        _set(self.note, o.note)
        self.note.setVisible(bool(o.note))
        _set(self.unknown_text, o.unknown)
        self.unknown.setVisible(bool(o.unknown))
        for key, b in self.buttons.items():
            a = o.actions.get(key)
            b.setVisible(a is not None)
            if a is not None:
                _set(b, a[1])
                b.setEnabled(a[0])
                if tips:
                    tip = tips(key, a[1]) or ""
                    if b.toolTip() != tip:
                        b.setToolTip(tip)
        _set(self.today_note, o.today_note)
        for box, f in zip(self.tiles, o.today):
            box.show_fact(f)
        self._show_system(o)
        self._show_rounds(o.rounds)

    def _show_system(self, o):
        while len(self.sys_rows) < len(o.system):
            r = QHBoxLayout()
            name, value = _label(cls="dim"), _label()
            r.addWidget(name)
            r.addStretch()
            r.addWidget(value)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setRange(0, 1000)
            pos = 1 + 2 * len(self.sys_rows)
            self.sys_lay.insertLayout(pos, r)
            self.sys_lay.insertWidget(pos + 1, bar)
            self.sys_rows.append((name, value, bar, [None]))
        for i, (name, value, bar, colour) in enumerate(self.sys_rows):
            shown = i < len(o.system)
            for w in (name, value):
                w.setVisible(shown)
            if not shown:
                bar.setVisible(False)
                continue
            label, text, frac, col = o.system[i]
            _set(name, label)
            _set(value, text)
            bar.setVisible(frac is not None)
            bar.setValue(round(1000 * min(1.0, max(0.0, frac or 0.0))))
            want = qt_theme.bar_style(col) if col is not None else ""
            if want != colour[0]:
                colour[0] = want
                bar.setStyleSheet(want)
        _set(self.sys_note, o.system_note)
        self.sys_note.setVisible(bool(o.system_note))

    def _show_rounds(self, rounds):
        while len(self.last_rows) < len(rounds):
            r = QHBoxLayout()
            left, right = _label(), _label(cls="dim")
            left.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)      # long names must not widen it
            r.addWidget(left, 1)
            r.addWidget(right)
            self.last_lay.insertLayout(1 + len(self.last_rows), r)
            self.last_rows.append((left, right))
        for i, (left, right) in enumerate(self.last_rows):
            shown = i < len(rounds)
            left.setVisible(shown)
            right.setVisible(shown)
            if shown:
                _set(left, rounds[i][0])
                _set(right, rounds[i][1])
        self.last_empty.setVisible(not rounds)


def make_control(kind, key, post):
    """(widget, extra) of one control of the UI model; clicks go out as post("act", (key, value))."""
    extra = None
    if kind == "check":
        w = WrapCheck()                           # its text wraps in a narrow window (QCheckBox's does not)
        w.clicked.connect(lambda checked: post("act", (key, checked)))
    elif kind == "button":
        w = QPushButton()
        # Tab only, no focus by click (1.62.2): a button that disables itself on click passed its focus on and
        # the page scrolled to whatever came next in the tab order
        w.setFocusPolicy(Qt.TabFocus)
        w.clicked.connect(lambda _c=False: post("act", (key, None)))
    elif kind == "combo":
        w = QComboBox()
        w.setMinimumWidth(140)
        w.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        w.activated.connect(lambda i: post("act", (key, w.itemText(i))))
        w.editTextChanged.connect(lambda text: w.isEditable() and w.hasFocus() and post("act", (key, text)))
    elif kind == "slider":
        w = QWidget()
        r = QHBoxLayout(w)
        r.setContentsMargins(0, 0, 0, 0)
        name, value = _label(), _label()
        name.setMinimumWidth(110)
        value.setMinimumWidth(56)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        s = QSlider(Qt.Horizontal)
        s.setMaximumWidth(SLIDER_MAX)              # a wide window: no slider across the whole page
        s.valueChanged.connect(lambda v: post("act", (key, v)))
        r.addWidget(name)
        r.addWidget(s, 1)
        r.addWidget(value)
        r.addStretch()
        extra = (name, s, value)
    elif kind == "table":
        w = Table(key, post)
    elif kind == "chart":
        w = Chart()
    elif kind == "dashboard":
        w = DashboardView()
    elif kind == "tiles":
        w = TilesView()
    elif kind == "preview":
        w = PreviewView(key, post)
    elif kind == "swatches":
        w = SwatchView(key, post)
    elif kind == "log":
        w = LogView()
    elif kind == "radio":
        w = QRadioButton()
        w.setAutoExclusive(False)                 # the model decides which one is on
        w.clicked.connect(lambda _c=False: post("act", (key, None)))
    elif kind == "entry":
        w = QLineEdit()
        w.setMinimumWidth(220)
        w.textEdited.connect(lambda text: post("act", (key, text)))
    elif kind == "image":
        w = QLabel()
        w.setAlignment(Qt.AlignCenter)
        w.setMinimumSize(200, 120)
    elif kind == "hotkey":
        w = HotkeyButton(key, post)
    elif kind in ("hint", "plain"):
        w = _label(cls="dim", wrap=True)
    elif kind == "big":
        w = _label(cls="big", wrap=True)
    elif kind == "value":
        w = _label()
        w.setStyleSheet("font-weight: 600;")
    else:                                                     # label, entry (shown, not edited)
        w = _label(wrap=True)
    return w, extra


def show_control(kind, w, extra, st):
    """Put a model widget's state (app_qt.ui_state) into its Qt control – never sends anything back."""
    if kind == "tab":                    # a tab of a hand-made page: hidden with its frame
        if w.isTabVisible(extra) != bool(st.get("visible", True)):
            w.setTabVisible(extra, bool(st.get("visible", True)))
        return
    if kind == "title":                  # 1.66.3: a card whose frame is folded away ("Mehr" closed) is not shown
        card, shown = w.parentWidget(), bool(st.get("visible", True))
        if card is not None and card.isHidden() == shown:
            card.setVisible(shown)
    else:
        shown = bool(st.get("visible", True))
        if kind in ("hint", "plain", "big", "label"):
            shown = shown and bool(st.get("text"))            # empty lines take no room
        w.setVisible(shown)
    if "enabled" in st:
        w.setEnabled(st["enabled"])
    if st.get("tip") is not None and w.toolTip() != st["tip"]:
        w.setToolTip(st["tip"])
    if kind in ("check", "radio"):
        _set(w, st.get("text", ""))
        if w.isChecked() != bool(st.get("value")):
            w.setChecked(bool(st.get("value")))                 # setChecked does not emit clicked
    elif kind == "entry":
        if not w.hasFocus() and w.text() != st.get("value", ""):     # never overwrite while typing
            w.setText(st.get("value", ""))
    elif kind == "image":
        pil = st.get("pil")
        if pil is not getattr(w, "_pil", None):
            w._pil = pil
            if pil is None:
                w.setText(st.get("text", ""))
            else:
                w.setPixmap(pixmap_from_pil(pil, pil.height, w.devicePixelRatioF()))
    elif kind == "combo":
        if w.isEditable() != bool(st.get("editable")):
            w.setEditable(bool(st.get("editable")))
        values = st.get("values", [])
        if [w.itemText(i) for i in range(w.count())] != values:
            w.blockSignals(True)
            w.clear()
            w.addItems(values)
            w.blockSignals(False)
        if w.currentText() != st.get("value") and not (w.isEditable() and w.hasFocus()):
            w.blockSignals(True)
            i = w.findText(st.get("value", ""))
            if i >= 0:
                w.setCurrentIndex(i)
            elif w.isEditable():
                w.setEditText(st.get("value", ""))
            else:
                w.setCurrentIndex(-1)
            w.blockSignals(False)
    elif kind == "slider":
        name, s, value = extra
        _set(name, st.get("label", ""))
        _set(value, st.get("text", ""))
        if not s.isSliderDown():                                  # the user is dragging: no pull back
            s.blockSignals(True)
            s.setRange(round(st.get("lo", 0)), round(st.get("hi", 100)))
            s.setValue(round(st.get("value", 0)))
            s.blockSignals(False)
    elif kind in ("table", "chart", "log", "dashboard", "tiles", "preview", "swatches"):
        w.show_state(st)
    elif kind == "hotkey":
        w.show_text(st.get("text", ""))
        w.show_recording(bool(st.get("recording")))
    elif kind in ("box", "card"):
        pass
    else:                                                         # button, label, hint, value, title, big
        text = st.get("text", "")
        _set(w, text.upper() if kind == "title" else text)


class Grip(QWidget):
    """The handle at the right of a card's title: six dots; dragging it moves the card (CardColumn)."""

    def __init__(self, column, card):
        super().__init__()
        self._column, self._card = column, card
        self.setFixedSize(16, 18)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(_("Ziehen, um den Kasten zu verschieben"))

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.palette().color(QPalette.PlaceholderText))
        for x in (5, 11):
            for y in (4, 9, 14):
                p.drawEllipse(x - 1.5, y - 1.5, 3, 3)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self._column.begin(self._card)

    def mouseMoveEvent(self, e):
        self._column.drag_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, _e):
        self.setCursor(Qt.OpenHandCursor)
        self._column.end()


class CardColumn(QWidget):
    """Cards below each other that the user can put in their own order (1.59, user's wish: "Updates nach oben
    schieben"): drag a card at its grip, the others make room as it passes them; the page scrolls at its edges.
    No QDrag – that runs a second event loop. ``on_order(ids)`` gets the new order (saved by the App)."""

    def __init__(self, on_order=None):
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)
        self.cards = []                   # [(id, card)] in the order shown
        self._default = []
        self._drag = None
        self._before = None
        self.on_order = on_order
        self._scroll = None
        self._timer = QTimer(self)        # scrolls the page while the card is held at its top/bottom edge
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._autoscroll)

    def add(self, card_id, card, head_row):
        """``head_row``: the card's title layout – the grip goes to its right end."""
        head_row.addWidget(Grip(self, card), 0, Qt.AlignVCenter)
        self.cards.append((card_id, card))
        self._default.append(card_id)
        self._lay.addWidget(card)

    def ids(self) -> list:
        return [i for i, _c in self.cards]

    def apply(self, ids):
        """Show the cards in this order; ids it does not know, or a missing card (another version), = default."""
        if not ids or sorted(ids) != sorted(self._default):
            ids = self._default
        if ids == self.ids():
            return
        by_id = dict(self.cards)
        for _i, card in self.cards:
            self._lay.removeWidget(card)
        self.cards = [(i, by_id[i]) for i in ids]
        for _i, card in self.cards:
            self._lay.addWidget(card)
        self._tab_order()

    def _tab_order(self):
        """Tab order = the order shown (1.62.2): Qt keeps the order the widgets were made in. A button that
        disables itself on click ("Jetzt nach Updates suchen") hands its focus to the next one in that chain –
        a card that now sits far below – and the page scrolled down to it."""
        def focusable(card):
            return [w for w in card.findChildren(QWidget) if w.focusPolicy() & Qt.TabFocus]
        widgets = [w for _i, card in self.cards for w in focusable(card)]
        if len(widgets) < 2:
            return
        inside = set(map(id, widgets))
        by_id = dict(self.cards)
        first = next((w for i in self._default for w in focusable(by_id[i])), None)
        prev = first.previousInFocusChain() if first is not None else None
        while prev is not None and id(prev) in inside:
            prev = prev.previousInFocusChain()
        chain = ([prev] if prev is not None else []) + widgets
        for a, b in zip(chain, chain[1:]):
            QWidget.setTabOrder(a, b)

    def begin(self, card):
        self._drag = card
        self._before = self.ids()
        card.setProperty("dragging", True)
        card.style().unpolish(card)
        card.style().polish(card)
        w = self.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        self._scroll = w
        self._timer.start()

    def drag_to(self, global_pos):
        card = self._drag
        if card is None:
            return
        y = self.mapFromGlobal(global_pos).y()
        others = [(i, c) for i, c in self.cards if c is not card]
        pos = len(others)
        for n, (_i, c) in enumerate(others):
            if c.isVisible() and y < c.geometry().center().y():
                pos = n
                break
        me = next(e for e in self.cards if e[1] is card)
        if self.cards.index(me) != pos:
            others.insert(pos, me)
            self.cards = others
            self._lay.removeWidget(card)
            self._lay.insertWidget(pos, card)

    def _autoscroll(self):
        from PySide6.QtGui import QCursor
        sa = self._scroll
        if self._drag is None or sa is None:
            return
        y = sa.viewport().mapFromGlobal(QCursor.pos()).y()
        h = sa.viewport().height()
        step = -18 if y < 40 else 18 if y > h - 40 else 0
        if step:
            bar = sa.verticalScrollBar()
            bar.setValue(bar.value() + step)
            self.drag_to(QCursor.pos())

    def end(self):
        card, self._drag = self._drag, None
        self._timer.stop()
        if card is None:
            return
        card.setProperty("dragging", False)
        card.style().unpolish(card)
        card.style().polish(card)
        if self.ids() != self._before:
            self._tab_order()
            if self.on_order is not None:
                self.on_order(self.ids())


def _card_head(card_layout):
    """Title row of a card: (title label, row) – CardColumn puts its grip at the end of the row."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    head = _label(cls="h2")
    row.addWidget(head, 1)
    card_layout.addLayout(row)
    return head, row


class _Arranged:
    """Pages whose cards the user can put in order: one CardColumn per run of cards (a run ends at anything
    else, e.g. Settings' "Mehr" button). ``post("card_order", (page, run, ids))`` saves; ``apply_order``."""

    def _column(self, page_key):
        n = len(self.columns)
        col = CardColumn(lambda ids, n=n: self._post("card_order", (page_key, n, ids)))
        self.columns.append(col)
        return col

    def apply_order(self, saved: dict):
        for n, col in enumerate(self.columns):
            col.apply((saved or {}).get(str(n)))


class FitTabs(QTabWidget):
    """Tabs as tall as the open tab, not the tallest one (QStackedLayout asks every page): no empty room below
    a short tab."""

    def __init__(self):
        super().__init__()
        self.currentChanged.connect(lambda _i: self.updateGeometry())

    def _extra(self):
        return self.tabBar().sizeHint().height() + 2

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        page = self.currentWidget()
        if page is None:
            return super().heightForWidth(w)
        return self._extra() + (page.heightForWidth(w - 2) if page.hasHeightForWidth() else page.sizeHint().height())

    def sizeHint(self):
        hint = super().sizeHint()
        page = self.currentWidget()
        return hint if page is None else QSize(hint.width(), self._extra() + page.sizeHint().height())

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        page = self.currentWidget()
        return hint if page is None else QSize(hint.width(), self._extra() + page.minimumSizeHint().height())


class FormPage(QWidget, _Arranged):
    """A hand-made page (SPECS): one control per widget of the UI model, which does the work."""

    def __init__(self, post, title, spec, page_key=""):
        super().__init__()
        self._post = post
        self.controls = {}                 # key -> (kind, widget, extra)
        self.columns = []
        page, lay = _scroll_page(title)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        col = None
        for item in spec:
            kind = item[0]
            if kind != "card":
                col = None
            if kind == "card":
                if col is None:
                    col = self._column(page_key)
                    lay.addWidget(col)
                card = _card()
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 12, 14, 12)
                cl.setSpacing(6)
                head, hrow = _card_head(cl)
                self.controls[item[1]] = ("title", head, None)
                for row in item[2]:
                    self._add(row, cl)
                col.add(item[1], card, hrow)
            elif kind == "panel":
                card = _card()
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 12, 14, 12)
                for row in item[1]:
                    self._add(row, cl)
                lay.addWidget(card)
            elif kind == "tabs":
                tabs = FitTabs()
                tabs.setObjectName("formtabs")
                for frame, label, rows in item[1]:
                    body = QWidget()
                    body.setObjectName("page")
                    bl = QVBoxLayout(body)
                    bl.setContentsMargins(14, 12, 14, 12)
                    bl.setSpacing(6)
                    for row in rows:
                        self._add(row, bl)
                    bl.addStretch()
                    self.controls[frame] = ("tab", tabs, tabs.addTab(body, _(label).replace("&", "&&")))
                lay.addWidget(tabs)
            elif kind == "links":
                row = QHBoxLayout()
                for c in item[1]:
                    self._add(c, row)
                row.addStretch()
                lay.addLayout(row)
            else:
                self._add(item, lay)
        lay.addStretch()

    def _add(self, item, lay):
        kind = item[0]
        if kind == "row":
            kids = item[1]
            if any(c[0] in ("hint", "slider") for c in kids):    # text that wraps beside controls: a plain row
                row = QHBoxLayout()
                row.setSpacing(8)
                for c in kids:
                    self._add(c, row)
            else:                                     # controls only: they wrap when the window is narrow
                row = FlowRow()
                cut = next((i for i, c in enumerate(kids) if c[0] == "stretch"), len(kids))
                row.right = len([c for c in kids[cut:] if c[0] != "stretch"])
                for c in kids:
                    if c[0] != "stretch":
                        self._add(c, row)
            lay.addLayout(row)
            return
        if kind == "grid":                          # ("grid", columns, rows): the rows side by side (hotkeys)
            g = QGridLayout()
            g.setHorizontalSpacing(28)
            g.setVerticalSpacing(6)
            cols = item[1]
            per = -(-len(item[2]) // cols)            # down the first column, then the next
            for i, c in enumerate(item[2]):
                cell = QVBoxLayout()
                self._add(c, cell)
                g.addLayout(cell, i % per, i // per)
            for c in range(cols):
                g.setColumnStretch(c, 1)
            lay.addLayout(g)
            return
        if kind == "stretch":
            lay.addStretch()
            return
        if kind == "sub":                           # a small heading inside a card (1.66.3: groups of tick boxes)
            lay.addWidget(_label(_(item[1]).upper(), "sub"))
            return
        if kind == "note":                          # a fixed text of the page itself (setup assistant)
            lay.addWidget(_label(_(item[1]), wrap=True))
            return
        w, extra = make_control(kind, item[1], self._post)
        if isinstance(lay, FlowRow):
            lay.addWidget(w)
        else:
            lay.addWidget(w, 1 if kind == "hint" and isinstance(lay, QHBoxLayout) else 0)  # text beside: takes the room
        self.controls[item[1]] = (kind, w, extra)

    def show_states(self, states):
        for key, (kind, w, extra) in self.controls.items():
            st = states.get(key)
            if st is not None:
                show_control(kind, w, extra, st)


FLOW_KINDS = ("button", "combo", "check", "radio", "label", "entry", "value", "big")   # rows of these may wrap


def _grows(node) -> bool:
    """A table, chart or the log below this node: it may take the free height of the page."""
    return (node.get("kind") in ("table", "chart", "log") and not node.get("fit")) or \
        any(_grows(c) for c in node.get("children", ()))


def _fills(node) -> bool:
    """A notebook below this node fills the page (packed with expand): the page does not scroll as a whole."""
    return (node.get("kind") == "tabs" and bool(node.get("fill"))) or any(_fills(c) for c in node.get("children", ()))


class AutoPage(QWidget, _Arranged):
    """A page built from the structure of a tab of the UI model (app_qt.ui_layout): frames → cards/rows,
    notebooks → tabs, tables, charts and controls like FormPage (Statistik, Server, Erkennung, Log, dialogs)."""

    def __init__(self, post, title, node, page_key=""):
        super().__init__()
        self._post = post
        self._page_key = page_key
        self.controls = {}                 # key -> (kind, widget, extra)
        self._tabs = []                    # (QTabWidget, [keys of each page])
        self._all = []
        self.columns = []
        fill = _fills(node) if node else False
        page, lay = _scroll_page(title, scroll=not fill)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        if node:
            self._build(node, lay, self._all, top=True)
        if not fill:
            lay.addStretch()

    def _build(self, n, lay, keys, top=False, column=None):
        kind, key = n["kind"], n["key"]
        keys.append(key)
        if kind in ("box", "card"):
            holder = _card() if kind == "card" else QWidget()
            v = QVBoxLayout(holder)
            v.setContentsMargins(*((14, 12, 14, 12) if kind == "card" else (0, 0, 0, 0)))
            v.setSpacing(6)
            if kind == "card":
                head, hrow = _card_head(v)
                self.controls[key + "#title"] = ("title", head, None)
            kids = n.get("children", [])
            if n.get("grid"):                         # e.g. the game languages
                g = QGridLayout()
                g.setHorizontalSpacing(14)
                for c in kids:
                    cell = QVBoxLayout()
                    self._build(c, cell, keys)
                    g.addLayout(cell, *c.get("cell", (0, 0)))
                g.setColumnStretch(g.columnCount(), 1)
                v.addLayout(g)
                if column is not None:
                    column[0].add(column[1], holder, hrow)
                else:
                    lay.addWidget(holder, 1 if top and _grows(n) else 0)
                self.controls[key] = (kind, holder, None)
                return
            first = [c for c in kids if c.get("side") != "right"]
            last = list(reversed([c for c in kids if c.get("side") == "right"]))
            flow = n.get("row") and all(c["kind"] in FLOW_KINDS for c in kids)   # controls only: they wrap
            inner = (FlowRow() if flow else QHBoxLayout()) if n.get("row") else v
            if inner is not v:
                inner.setSpacing(8)
                v.addLayout(inner)
                if flow:
                    inner.right = len(last)
            arrange = bool(self._page_key) and top and kind == "box" and inner is v and not _grows(n)  # own order
            col, run = None, 0
            for c in first:
                if arrange and c["kind"] == "card":
                    if col is None:
                        col, run = self._column(self._page_key), 0
                        v.addWidget(col)
                    self._build(c, v, keys, column=(col, f"#{run}"))
                    run += 1
                    continue
                col = None
                self._build(c, inner, keys, top=top and inner is v)    # a table further down still gets the height
            if n.get("row") and not flow:
                inner.addStretch()
            for c in last:
                self._build(c, inner, keys, top=top and inner is v)
            if column is not None:
                column[0].add(column[1], holder, hrow)
            else:
                lay.addWidget(holder, 1 if top and _grows(n) else 0)
            self.controls[key] = (kind, holder, None)
            return
        if kind == "tabs":
            tw = QTabWidget()
            fill = bool(n.get("fill"))
            pages = []
            for c in n.get("children", []):
                pw = QWidget()
                pl = QVBoxLayout(pw)
                pl.setContentsMargins(8, 8, 8, 8)
                ks = []
                self._build(c, pl, ks, top=fill)       # filling tabs: a table takes the height of its page
                pl.addStretch()
                if fill:                               # each page scrolls on its own, the filters stay on top
                    pw.setObjectName("page")
                    sa = QScrollArea()
                    sa.setWidgetResizable(True)
                    sa.setFrameShape(QFrame.NoFrame)
                    sa.setWidget(pw)
                    tw.addTab(sa, "")
                else:
                    tw.addTab(pw, "")
                pages.append(ks)
                keys.extend(ks)
            tw.currentChanged.connect(lambda i, k=key: self._post("act", (k, i)))
            lay.addWidget(tw, 1 if fill else 0)
            self._tabs.append((key, tw, pages))
            self.controls[key] = ("tabs", tw, None)
            return
        w, extra = make_control(kind, key, self._post)
        if kind == "table" and n.get("fit"):
            w.fit_rows()
        grow = kind in ("table", "chart", "log") or (kind == "hint" and isinstance(lay, QHBoxLayout))
        if isinstance(lay, FlowRow):
            lay.addWidget(w)
        elif kind in ("button", "combo") and not isinstance(lay, QHBoxLayout):
            lay.addWidget(w, 0, Qt.AlignLeft)             # a button on a line of its own keeps its size
        else:
            lay.addWidget(w, 1 if grow else 0)
        self.controls[key] = (kind, w, extra)

    def visible_keys(self) -> set:
        """Keys to read now: everything except the pages of tabs that are not on display."""
        hidden = set()
        for _key, tw, pages in self._tabs:
            for i, ks in enumerate(pages):
                if i != tw.currentIndex():
                    hidden.update(ks)
        return set(self._all) - hidden

    def show_states(self, states):
        for key, (kind, w, extra) in self.controls.items():
            if kind == "tabs":
                st = states.get(key)
                if st:
                    tw = w
                    for i, text in enumerate(st.get("tabs", [])[:tw.count()]):
                        if tw.tabText(i) != text:
                            tw.setTabText(i, text)
                    if tw.currentIndex() != st.get("index", 0):
                        tw.blockSignals(True)
                        tw.setCurrentIndex(st.get("index", 0))
                        tw.blockSignals(False)
                continue
            if key.endswith("#title"):
                st = states.get(key[:-6])
                if st is not None:
                    show_control("title", w, extra, st)
                continue
            st = states.get(key)
            if st is not None:
                show_control(kind, w, extra, st)


class DialogWindow(QDialog):
    """A dialog of the UI model (Zuordnen, Kartenbild hinzufügen): built like AutoPage, not modal; closing it
    (X, Esc) destroys the model's dialog too."""

    def __init__(self, parent, post, key, title, node):
        super().__init__(parent)
        self._post, self._key = post, key
        self.closing_from_app = False
        self.setWindowTitle(title)
        self.setModal(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.page = AutoPage(post, title, node)
        lay.addWidget(self.page)
        self.resize(640, 560)

    def done(self, r):                            # Esc / X: the model's dialog goes too
        if not self.closing_from_app:
            self._post("dlg_close", self._key)
        super().done(r)


class SetupPage(QWidget):
    """The setup assistant (first start, or "Einrichtung starten" in the settings): SETUP's steps one at a time,
    "Zurück" / "Weiter" / "Fertig" and "Überspringen". Done or skipped: post("setup_done")."""

    def __init__(self, post):
        super().__init__()
        self.setObjectName("page")
        self._post = post
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.steps = QStackedWidget()
        self.pages = [FormPage(post, _("Einrichtung: {step}", step=_(title)), items) for title, items in SETUP]
        for page in self.pages:
            page.setMaximumWidth(SETUP_W)               # a wide window: the keys stay next to their names
            self.steps.addWidget(page)
        lay.addWidget(self.steps, 1)
        foot = QHBoxLayout()
        foot.setContentsMargins(22, 10, 22, 16)
        self.skip = QPushButton(_("Überspringen"))
        self.skip.clicked.connect(lambda: self._post("setup_done"))
        self.where = _label(cls="dim")
        self.back = QPushButton(_("Zurück"))
        self.back.clicked.connect(lambda: self.go(self.steps.currentIndex() - 1))
        self.next = QPushButton()
        self.next.setObjectName("primary")
        self.next.clicked.connect(self._next)
        foot.addWidget(self.skip)
        foot.addStretch()
        foot.addWidget(self.where)
        foot.addSpacing(12)
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        lay.addLayout(foot)
        self.go(0)

    def go(self, i: int):
        i = max(0, min(len(self.pages) - 1, i))
        self.steps.setCurrentIndex(i)
        _set(self.where, _("Schritt {n} von {total}", n=i + 1, total=len(self.pages)))
        self.back.setEnabled(i > 0)
        _set(self.next, _("Fertig") if i == len(self.pages) - 1 else _("Weiter"))

    def _next(self):
        if self.steps.currentIndex() == len(self.pages) - 1:
            self._post("setup_done")
        else:
            self.go(self.steps.currentIndex() + 1)

    def show_states(self, states):
        for page in self.pages:
            page.show_states(states)
