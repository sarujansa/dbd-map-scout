"""Qt views of the UI model's larger widgets: tables, the log, hotkey buttons, charts, the dashboard, tiles and colour
swatches (drawn from the model's data, clicks go back through ``post``).
"""
from __future__ import annotations

import html
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import qt_theme
from .qt_layouts import FlowRow, TileGrid
from .i18n import _
from .qt_common import _label, _card, _set, _tip


class FactBox(QWidget):
    """Title, big value, optional bar and a small line (map card values and today's tiles)."""

    def __init__(self, bar=False, post=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.title = _label(cls="dim")
        self.value = _label(cls="kpi")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        self.bar = None
        if bar:
            self.bar = QProgressBar()
            self.bar.setTextVisible(False)
            self.bar.setRange(0, 1000)
            lay.addWidget(self.bar)
        self.sub = _label(cls="dim")
        lay.addWidget(self.sub)
        # 1.2.15: a fact can carry a small button (overview: "Server aus" → server tab, no stats data → setup)
        self._post, self._action = post, ""
        self.link = QPushButton()
        self.link.setFocusPolicy(Qt.TabFocus)
        self.link.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.link.clicked.connect(lambda _c=False: self._post and self._action and self._post(self._action))
        self.link.hide()
        lay.addWidget(self.link, 0, Qt.AlignLeft)
        self._colour = None

    def show_fact(self, f):
        _set(self.title, f.title)
        _set(self.value, f.value)
        _set(self.sub, f.sub)
        action = getattr(f, "action", "") if self._post else ""
        if action != self._action or (action and self.link.text() != f.action_label):
            self._action = action
            _set(self.link, f.action_label if action else "")
            self.link.setToolTip(_tip(f.action_label) if action else "")
            self.link.setVisible(bool(action))
        colour = qt_theme.hex_colour(f.colour) if f.colour is not None else None
        if colour != self._colour:
            self._colour = colour
            self.value.setStyleSheet(f"color: {colour};" if colour else "")
        if self.bar is not None:
            self.bar.setVisible(f.frac is not None)
            self.bar.setValue(round(1000 * min(1.0, max(0.0, f.frac or 0.0))))


CHECKS = {"check:on": Qt.Checked, "check:off": Qt.Unchecked, "check:part": Qt.PartiallyChecked}   # uimodel.CHECK_*


def _check(item, tags):
    """A row tagged uimodel.CHECK_*: a tick box in the first column. Not user-checkable – the click goes to the
    model like any click on the row, the model toggles and sends the new tag."""
    state = next((CHECKS[t] for t in tags if t in CHECKS), None)
    if state is not None and item.data(0, Qt.CheckStateRole) != state:
        item.setCheckState(0, state)


class Table(QTreeWidget):
    """A table of the UI model (uimodel.Treeview): columns, rows (with groups), colours by tag, selection. A click
    on a row or a heading goes to the model (sorting, selecting, the server tab's tick boxes)."""

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._shape = None
        self._fit = False
        self.setMinimumHeight(200)
        self.header().setStretchLastSection(False)
        self.header().setMinimumSectionSize(48)
        self.setAlternatingRowColors(False)
        self.setUniformRowHeights(True)
        self.header().setSectionsClickable(True)
        self.header().sectionClicked.connect(self._sort)
        self.itemClicked.connect(lambda item, _c: self._post("act", (self._key, ("click", item.data(0, Qt.UserRole)))))
        self._cols = []
        self._titles = []
        self._stretch = 0
        self.hidden = set()               # 1.3.6: column ids the user hid (right-click on the heading)
        self._hidden_map = {}             # setting hidden_columns: {column ids joined by "|": [hidden ids]}
        self.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.header().customContextMenuRequested.connect(self._column_menu)
        self.header().setToolTip(_("Klick: sortieren · Rechtsklick: Spalten ein-/ausblenden"))

    def col_key(self) -> str:
        """The table's name in the setting: its columns – unlike the model path it stays the same when a later
        version adds widgets elsewhere on the page."""
        return "|".join(self._cols)

    def set_hidden_map(self, hidden: dict):
        """The setting hidden_columns; this table takes the entry of its columns (now or once it has them)."""
        self._hidden_map = dict(hidden or {})
        self.set_hidden(self._hidden_map.get(self.col_key(), ()))

    def set_hidden(self, cols):
        self.hidden = set(cols or ())
        self._apply_hidden()

    def _apply_hidden(self):
        if not self._cols:
            return
        hide = [c in self.hidden for c in self._cols]
        if all(hide):                     # never an empty table (an old setting, other columns now)
            hide = [False] * len(hide)
        for i, h in enumerate(hide):
            self.setColumnHidden(i, h)
        mode = self.header().ResizeMode
        stretch = self._stretch if not hide[self._stretch] else next(i for i, h in enumerate(hide) if not h)
        for i in range(len(hide)):          # the stretching column must be a shown one, or a gap stays
            if i == stretch:
                self.header().setSectionResizeMode(i, mode.Stretch)
            elif self.header().sectionResizeMode(i) == mode.Stretch:
                self.header().setSectionResizeMode(i, mode.Interactive)

    def _column_menu(self, pos):
        """Right-click on the heading: tick the columns to show (one stays), or show all again. popup, not exec."""
        if not self._cols:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        shown = [c for c in self._cols if c not in self.hidden]
        for cid, title in zip(self._cols, self._titles):
            act = menu.addAction(title or cid)
            act.setCheckable(True)
            act.setChecked(cid not in self.hidden)
            act.setEnabled(not (cid not in self.hidden and len(shown) == 1))
            act.toggled.connect(lambda on, c=cid: self._toggle_column(c, on))
        menu.addSeparator()
        menu.addAction(_("Alle Spalten zeigen")).triggered.connect(lambda: self._show_all_columns())
        menu.setAttribute(Qt.WA_DeleteOnClose)
        menu.popup(self.header().mapToGlobal(pos))

    def _toggle_column(self, cid, on):
        (self.hidden.discard if on else self.hidden.add)(cid)
        self._remember_hidden()

    def _show_all_columns(self):
        self.hidden.clear()
        self._remember_hidden()

    def _remember_hidden(self):
        self._apply_hidden()
        self._hidden_map[self.col_key()] = sorted(self.hidden)
        self._post("table_cols", (self.col_key(), sorted(self.hidden)))

    def _sort(self, index):
        if 0 <= index < len(self._cols):
            self._post("act", (self._key, ("sort", self._cols[index])))

    def show_state(self, st):
        cols = st.get("columns", [])
        rows = st.get("rows", [])
        shape = (tuple(tuple(c) for c in cols), tuple((r[0], r[1], r[2], tuple(r[3]), tuple(r[4])) for r in rows),
                 tuple(sorted(st.get("colours", {}).items())))
        if shape != self._shape and self._shape is not None and shape[0] == self._shape[0] and shape[2] == \
                self._shape[2] and [r[:2] for r in shape[1]] == [r[:2] for r in self._shape[1]]:
            self._shape = shape                       # same rows, other values (pings, counts): update in place
            self._update_cells(cols, rows, st.get("colours", {}))
        elif shape != self._shape:
            self._shape = shape
            self._cols = [c[0] for c in cols]
            self._titles = [c[1] for c in cols]
            self.hidden = set(self._hidden_map.get(self.col_key(), ()))
            tree = bool(cols) and cols[0][0] == "#0"
            self.setRootIsDecorated(tree and any(r[1] > 0 for r in rows))
            self.setHeaderLabels([c[1] for c in cols])
            for i, c in enumerate(cols):                  # numbers right-aligned: their heading too
                self.headerItem().setTextAlignment(i, (Qt.AlignRight if c[2] == "e" else Qt.AlignLeft) | Qt.AlignVCenter)
            self.clear()
            parents = {}
            colours = st.get("colours", {})
            for iid, depth, text, values, tags, opened in rows:
                cells = ([text] if tree else []) + list(values)
                item = QTreeWidgetItem(cells[:len(cols)] + [""] * max(0, len(cols) - len(cells)))
                item.setData(0, Qt.UserRole, iid)
                for i, (_cid, _t, anchor) in enumerate(cols):
                    if anchor == "e":
                        item.setTextAlignment(i, Qt.AlignRight | Qt.AlignVCenter)
                fg = next((colours[t] for t in tags if t in colours), None)
                if fg:
                    for i in range(len(cols)):
                        item.setForeground(i, QColor(fg))
                _check(item, tags)
                parent = parents.get(depth - 1)
                if parent is not None:
                    parent.addChild(item)
                else:
                    self.addTopLevelItem(item)
                parents[depth] = item
                item.setExpanded(True)
            fm = self.header().fontMetrics()
            widths = st.get("widths") or []
            stretch = st.get("stretch", 0) if 0 <= st.get("stretch", 0) < len(cols) else 0
            for i, c in enumerate(cols):
                self.header().setSectionResizeMode(i, self.header().ResizeMode.Interactive)
                self.resizeColumnToContents(i)
                least = widths[i] if i < len(widths) and i != stretch else 0    # the model's width: room for "…"
                self.setColumnWidth(i, max(self.columnWidth(i), fm.horizontalAdvance(c[1]) + 24, least))
            if cols:                  # the name column takes the rest (not always the first: "Wann" stays readable)
                self.header().setSectionResizeMode(stretch, self.header().ResizeMode.Stretch)
            self._stretch = stretch
            self._apply_hidden()
            self._fit_height()
        self._select(st)

    def fit_rows(self):
        """As tall as its rows (a table packed without expand – the server regions): no empty box below the last
        row, the page scrolls instead."""
        self._fit = True
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _fit_height(self):
        if not self._fit:
            return
        n = sum(1 for _i in self._items())
        row = self.sizeHintForRow(0) if n else 0
        self.setFixedHeight(self.header().sizeHint().height() + n * max(row, 1) + 2 * self.frameWidth() + 10)

    def _items(self):
        it = self.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount() - 1, -1, -1)]
        while stack:
            item = stack.pop()
            yield item
            stack += [item.child(i) for i in range(item.childCount() - 1, -1, -1)]

    def _update_cells(self, cols, rows, colours):
        """Texts and colours of the rows already there (same rows in the same order) – no rebuild, no resizing,
        the scroll position stays."""
        tree = bool(cols) and cols[0][0] == "#0"
        for item, (_iid, _depth, text, values, tags, _o) in zip(self._items(), rows):
            cells = ([text] if tree else []) + list(values)
            fg = next((colours[t] for t in tags if t in colours), None)
            for i in range(len(cols)):
                value = cells[i] if i < len(cells) else ""
                if item.text(i) != value:
                    item.setText(i, value)
                item.setData(i, Qt.ForegroundRole, QColor(fg) if fg else None)
            _check(item, tags)

    def _select(self, st):
        sel = set(st.get("selection", []))
        mode = QTreeWidget.SingleSelection if st.get("selectable") else QTreeWidget.NoSelection
        if self.selectionMode() != mode:
            self.setSelectionMode(mode)
        if sel == getattr(self, "_sel", None) and sel == {i.data(0, Qt.UserRole) for i in self.selectedItems()}:
            return                                # nothing changed: no walk over all rows 4×/s
        self._sel = sel
        it = self.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount())]
        self.blockSignals(True)
        while stack:
            item = stack.pop()
            on = item.data(0, Qt.UserRole) in sel
            if item.isSelected() != on:
                item.setSelected(on)
            stack += [item.child(i) for i in range(item.childCount())]
        self.blockSignals(False)


class LogView(QPlainTextEdit):
    """The log (App._log_entries, filtered by the categories ticked) – coloured by category, follows new lines.
    New entries are appended (the entries are the App's own tuples, so the last one shown is found by identity);
    only another colour scheme or ``rev`` (filter changed, log cleared) rebuilds the whole text."""

    MAX_LINES = 400

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMinimumHeight(360)
        self.setMaximumBlockCount(self.MAX_LINES)        # old lines drop off by themselves
        self._last = None                                # last entry shown
        self._look = None

    def _row(self, entry, col):
        ts, cat, text = entry
        msg = col["Fehler"] if cat == "Fehler" else col["text"]
        return (f'<span style="color:{col["ts"]}">{html.escape(ts)}</span>&nbsp;&nbsp;'
                f'<span style="color:{col.get(cat, col["text"])}">{html.escape(_(cat))}</span>&nbsp;&nbsp;'
                f'<span style="color:{msg}">{html.escape(text)}</span>')

    def show_state(self, st):
        from .theme import LOG_COLORS
        lines = list(st.get("lines", ()))
        look = (st.get("dark"), st.get("rev"))           # colours / filter or cleared log
        last = lines[-1] if lines else None
        if last is self._last and look == self._look:
            return
        col = LOG_COLORS[bool(look[0])]
        bar = self.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        start = None
        if look == self._look and self._last is not None:
            start = next((i + 1 for i in range(len(lines) - 1, -1, -1) if lines[i] is self._last), None)
        if start is None:                                # filter/colours changed, log cleared: everything again
            # one paragraph (block) per line, like appendHtml: the block limit then drops single old lines
            self.document().setHtml("".join(f'<p style="margin:0">{self._row(e, col)}</p>'
                                            for e in lines[-self.MAX_LINES:]))
        else:
            for e in lines[start:]:
                self.appendHtml(self._row(e, col))
        self._last, self._look = last, look
        if at_end:
            bar.setValue(bar.maximum())


class HotkeyButton(QPushButton):
    """A hotkey in the settings: click, then press the new combination (Esc cancels, Del switches it off).
    The key presses go to the App, which checks them (hotkeys.combo_from_keys)."""

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._recording = False
        self.setMinimumWidth(170)
        self.clicked.connect(self._start)

    def _start(self):
        self._recording = True
        self.setFocus()
        self._post("hk_record", self._key)

    def show_text(self, text):
        _set(self, text)

    def keyPressEvent(self, e):
        if not self._recording:
            return super().keyPressEvent(e)
        k = e.key()
        if k in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            return                                            # still holding modifiers
        mods = [name for name, flag in (("ctrl", Qt.ControlModifier), ("alt", Qt.AltModifier),
                                        ("shift", Qt.ShiftModifier)) if e.modifiers() & flag]
        if Qt.Key_A <= k <= Qt.Key_Z:
            sym = chr(k).lower()
        elif Qt.Key_0 <= k <= Qt.Key_9 and not (e.modifiers() & Qt.KeypadModifier):
            sym = chr(k)
        elif Qt.Key_F1 <= k <= Qt.Key_F24:
            sym = f"F{k - Qt.Key_F1 + 1}"
        else:
            sym = {Qt.Key_Escape: "Escape", Qt.Key_Delete: "Delete", Qt.Key_Backspace: "BackSpace"}.get(k, "")
        vk = (e.nativeVirtualKey() or None) if sys.platform == "win32" else None
        self._post("hk_key", (self._key, mods, sym, vk))

    def contextMenuEvent(self, e):
        """1.2.19: right click – this one hotkey back to its default, or off."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        for action, label in (("default", _("Standard wiederherstellen")), ("off", _("Ausschalten"))):
            menu.addAction(label).triggered.connect(lambda _c=False, a=action: self._post("hk_menu", (self._key, a)))
        self._menu = menu
        menu.popup(e.globalPos())

    def focusOutEvent(self, e):
        if self._recording:
            self._recording = False
            self._post("hk_cancel", self._key)
        super().focusOutEvent(e)

    def show_recording(self, on: bool):
        """The App's view: once it has recorded (or cancelled), stop sending keys."""
        if on:
            self._seen = True
        elif getattr(self, "_seen", False):
            self._seen = self._recording = False


class Chart(QWidget):
    """The statistics charts (trendchart.TrendChart's data) drawn with Qt: columns, or a line for temperatures;
    hovering a column/point shows its tooltip text."""

    PANEL_H = 180

    def __init__(self):
        super().__init__()
        self._st = None
        self._hits = []
        self.setMouseTracking(True)
        self.setMinimumHeight(self.PANEL_H)

    def show_state(self, st):
        key = (id(st.get("data")), st.get("dark"), tuple(st.get("panels", ())))
        if self._st is None or key != self._key:
            self._key = key
            self._st = st
            self.setMinimumHeight(len(st.get("panels", ())) * (self.PANEL_H + 10))
            self.update()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter, QPen
        from .trendchart import BOTTOM, COLORS, LEFT, RIGHT, TOP, columns, segments
        st = self._st
        self._hits = []
        if not st or not st.get("data"):
            return
        col = COLORS[bool(st.get("dark", True))]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        width = max(200, self.width())
        for n, role in enumerate(st.get("panels", ())):
            d = st["data"].get(role)
            if not d:
                continue
            top = n * (self.PANEL_H + 10)
            p.setPen(QColor(col["text"]))
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            p.drawText(8, top + 14, d["title"])
            f.setBold(False)
            p.setFont(f)
            y0, y1 = top + TOP, top + self.PANEL_H - BOTTOM
            bars = d["bars"]
            if not any(v is not None for v, _l, _t in bars):
                p.setPen(QColor(col["dim"]))
                p.drawText(LEFT, round((y0 + y1) / 2), d["empty"])
                continue
            lo = d.get("min", 0)
            scale = (y1 - y0) / max(1e-9, d["max"] - lo)
            for value, label in d["ticks"]:
                y = y1 - (value - lo) * scale
                p.setPen(QPen(QColor(col["grid"]), 1))
                p.drawLine(LEFT, round(y), width - RIGHT, round(y))
                p.setPen(QColor(col["dim"]))
                p.drawText(0, round(y) - 8, LEFT - 6, 16, Qt.AlignRight | Qt.AlignVCenter, label)
            xs = columns(len(bars), width)
            every = max(1, -(-len(xs) * 46 // max(1, width - LEFT - RIGHT)))
            newest = max((i for i, (v, _l, _t) in enumerate(bars) if v is not None), default=None)
            slot = (xs[1][0] - xs[0][0]) if len(xs) > 1 else 40
            line = []
            for i, ((value, label, tip), (x0, x1)) in enumerate(zip(bars, xs)):
                mid = (x0 + x1) / 2
                if (len(xs) - 1 - i) % every == 0:
                    p.setPen(QColor(col["dim"]))
                    p.drawText(round(mid) - 30, round(y1) + 4, 60, 16, Qt.AlignHCenter | Qt.AlignTop, label)
                if value is None:
                    line.append(None)
                    continue
                if d.get("kind") == "line":
                    y = y1 - (value - lo) * scale
                    line.append((mid, y))
                else:
                    y = y1 - max(2.0, value * scale)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(col[role]))
                    p.drawRoundedRect(round(x0), round(y), round(x1 - x0), round(y1 - y) + 4, 4, 4)
                    p.fillRect(round(x0), round(y1) - 2, round(x1 - x0), 2, QColor(col[role]))
                if i == newest:
                    p.setPen(QColor(col["text"]))
                    ly = (y1 - (value - lo) * scale) - 6
                    p.drawText(round(mid) - 40, round(ly) - 16, 80, 16, Qt.AlignHCenter | Qt.AlignBottom, d["last"])
                self._hits.append((mid - slot / 2, y0 - 10, mid + slot / 2, y1, tip))
            if d.get("kind") == "line":
                p.setPen(QPen(QColor(col[role]), 2))
                for a, b in segments(line):
                    p.drawLine(round(a[0]), round(a[1]), round(b[0]), round(b[1]))
                p.setBrush(QColor(col[role]))
                for pt in line:
                    if pt is not None:
                        p.drawEllipse(round(pt[0]) - 4, round(pt[1]) - 4, 8, 8)
        p.end()

    def mouseMoveEvent(self, e):
        from PySide6.QtWidgets import QToolTip
        x, y = e.position().x(), e.position().y()
        hit = next((h for h in self._hits if h[0] <= x <= h[2] and h[1] <= y <= h[3]), None)
        if hit:
            QToolTip.showText(e.globalPosition().toPoint(), hit[4], self)
        else:
            QToolTip.hideText()


# Heatmap (average kills 0–4): the sequential blue ramp of the dataviz palette (validated, same blue as "Killer" in
# the trend chart). Light surface: more = darker; dark surface: more = lighter (near zero recedes to the surface).
HEAT_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281")


BAR_NEUTRAL = {True: "#6b7079", False: "#a3a8b0"}     # map bars: a plain count, no identity – neutral grey


def heat_colour(value: float, dark: bool, top: float = 4.0) -> QColor:
    """Colour of a heatmap cell: ``value`` 0..top along the ramp."""
    ramp = HEAT_RAMP[::-1] if dark else HEAT_RAMP
    f = min(1.0, max(0.0, value / top)) * (len(ramp) - 1)
    i = min(len(ramp) - 2, int(f))
    a, b, t = QColor(ramp[i]), QColor(ramp[i + 1]), f - i
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def ink_on(colour: QColor) -> QColor:
    """Text colour on a filled cell: dark ink on light cells, light ink on dark ones."""
    lum = 0.2126 * colour.redF() + 0.7152 * colour.greenF() + 0.0722 * colour.blueF()
    return QColor("#111214") if lum > 0.45 else QColor("#f0efec")


class MapBars(QWidget):
    """Most played maps: one row each – name, a bar for the rounds, the count and the results (stats page)."""
    ROW = 26

    def __init__(self, on_click=None):
        super().__init__()
        self._rows, self._max, self._dark = [], 1, True
        self._on_click = on_click                     # 1.2.16: a click on a row filters the statistics by that map
        if on_click:
            self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(self.ROW)

    def mousePressEvent(self, e):
        i = int(e.position().y() // self.ROW)
        if self._on_click and 0 <= i < len(self._rows):
            self._on_click(("map", self._rows[i][0]))

    def set_rows(self, rows, top, dark):
        self._rows, self._max, self._dark = list(rows), max(1, top), dark
        self.setMinimumHeight(max(self.ROW, len(self._rows) * self.ROW))
        self.update()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPainter
        c = qt_theme.colours(self._dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        name_w = min(190, max(110, w // 4))
        info_w = min(230, max(120, w // 3))
        bar_x, bar_w = name_w + 8, max(40, w - name_w - info_w - 60)
        fm = p.fontMetrics()
        for i, (name, n, info) in enumerate(self._rows):
            y = i * self.ROW
            mid = y + self.ROW / 2
            p.setPen(QColor(c["fg"]))
            p.drawText(0, y, name_w, self.ROW, Qt.AlignLeft | Qt.AlignVCenter, fm.elidedText(name, Qt.ElideRight, name_w))
            length = max(3.0, bar_w * n / self._max)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(BAR_NEUTRAL[self._dark]))
            p.drawRoundedRect(bar_x, round(mid - 5), round(length), 10, 4, 4)
            p.setPen(QColor(c["fg"]))
            p.drawText(round(bar_x + length + 6), y, 40, self.ROW, Qt.AlignLeft | Qt.AlignVCenter, str(n))
            p.setPen(QColor(c["dim"]))
            p.drawText(w - info_w, y, info_w, self.ROW, Qt.AlignRight | Qt.AlignVCenter,
                       fm.elidedText(info, Qt.ElideRight, info_w))
        p.end()


class Heatmap(QWidget):
    """Map × killer, average kills: rows = maps, columns = killers, cell colour = Ø kills (0–4) with the value
    written in it; empty cells = too few rounds. Hover: the cell's text with its number of rounds."""
    HEAD, ROW, LEGEND = 28, 26, 30

    def __init__(self, on_click=None):
        super().__init__()
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.PointingHandCursor)
        self._d, self._dark, self._hits = None, True, []
        self.setMouseTracking(True)

    def set_data(self, d, dark):
        self._d, self._dark = d, dark
        rows = len(d.rows) if d else 0
        self.setMinimumHeight(self.HEAD + rows * self.ROW + self.LEGEND if rows else 0)
        self.update()

    def paintEvent(self, _e):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QLinearGradient, QPainter
        d = self._d
        self._hits = []
        if not d or not d.rows:
            return
        c = qt_theme.colours(self._dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = p.fontMetrics()
        name_w = min(190, max(110, self.width() // 4))
        cols = max(1, len(d.columns))
        cell_w = max(36, min(96, (self.width() - name_w) / cols))
        from .dashboard import MATRIX_MIN, short_killer
        p.setPen(QColor(c["dim"]))
        for j, k in enumerate(d.columns):
            x = name_w + j * cell_w
            p.drawText(QRectF(x, 0, cell_w, self.HEAD), Qt.AlignHCenter | Qt.AlignVCenter,
                       fm.elidedText(short_killer(k), Qt.ElideRight, round(cell_w) - 4))
        for i, m in enumerate(d.rows):
            y = self.HEAD + i * self.ROW
            p.setPen(QColor(c["fg"]))
            p.drawText(QRectF(0, y, name_w - 8, self.ROW), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(m, Qt.ElideRight, name_w - 8))
            for j, k in enumerate(d.columns):
                rect = QRectF(name_w + j * cell_w + 1, y + 1, cell_w - 2, self.ROW - 2)     # 2 px surface gap
                cell = d.cells.get((m, k))
                if cell is None:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(c["hover"]))
                    p.drawRoundedRect(rect.adjusted(cell_w / 2 - 2, self.ROW / 2 - 3, -(cell_w / 2 - 2),
                                                    -(self.ROW / 2 - 3)), 2, 2)
                    continue
                avg, n = cell
                fill = heat_colour(avg, self._dark)
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawRoundedRect(rect, 4, 4)
                p.setPen(ink_on(fill))
                p.drawText(rect, Qt.AlignCenter, f"{avg:.1f}")
                self._hits.append((rect, _("{map} · {killer}: Ø {kills} Kills ({n} Runden)", map=m, killer=k,
                                           kills=f"{avg:.1f}", n=n), m, k))
        # legend: the ramp from 0 to 4 kills
        ly = self.HEAD + len(d.rows) * self.ROW + 10
        grad = QLinearGradient(name_w, 0, name_w + 160, 0)
        for t in range(5):
            grad.setColorAt(t / 4, heat_colour(t, self._dark))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(name_w, ly, 160, 8), 4, 4)
        p.setPen(QColor(c["dim"]))
        p.drawText(QRectF(name_w - 30, ly - 5, 24, 18), Qt.AlignRight | Qt.AlignVCenter, "0")
        p.drawText(QRectF(name_w + 166, ly - 5, 260, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   _("4 Kills · leer = weniger als {n} Runden", n=MATRIX_MIN))
        p.end()

    def mouseMoveEvent(self, e):
        from PySide6.QtWidgets import QToolTip
        pos = e.position()
        hit = next((t for r, t, _m, _k in self._hits if r.contains(pos)), None)
        if hit:
            QToolTip.showText(e.globalPosition().toPoint(), hit, self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, e):
        """1.2.16: a click on a cell filters the statistics by that map and killer."""
        pos = e.position()
        hit = next(((m, k) for r, _t, m, k in self._hits if r.contains(pos)), None)
        if hit and self._on_click:
            self._on_click(("cell",) + hit)


class SwatchView(QWidget):
    """The colour palette below the theme list (1.63, user's wish): one square per colour, the chosen one ringed,
    and "Eigene Farbe …" with Qt's colour dialog (non-modal, no second event loop). post("act", (key, "#rrggbb"))
    – qt_theme.derive_accent makes any colour readable."""

    SIZE = 22

    def __init__(self, key, post):
        super().__init__()
        self._key, self._post = key, post
        self._values, self._current = (), None
        self._buttons = []
        self._dialog = None
        self._row = FlowRow(self, spacing=6)
        self.own = QPushButton(_("Eigene Farbe …"))
        self.own.setFocusPolicy(Qt.TabFocus)
        self.own.setToolTip(_("Beliebige Farbe wählen – das Programm passt die Helligkeit an, bis alles lesbar "
                              "ist."))
        self.own.clicked.connect(self._pick)
        self._row.addWidget(self.own)

    def show_state(self, st):
        values = tuple(st.get("values") or ())
        current = (st.get("current"), bool(st.get("dark", True)))
        if values != self._values:
            for b in self._buttons:
                self._row.removeWidget(b)
                b.deleteLater()
            self._buttons = []
            self._row.removeWidget(self.own)
            for colour, tip in values:
                b = QPushButton()
                b.setFixedSize(self.SIZE, self.SIZE)
                b.setFocusPolicy(Qt.TabFocus)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(tip)
                b.setProperty("swatch", colour)
                b.clicked.connect(lambda _c=False, v=colour: self._post("act", (self._key, v)))
                self._row.addWidget(b)
                self._buttons.append(b)
            self._row.addWidget(self.own)
            self._values, self._current = values, object()
        if current != self._current:
            self._current = current
            chosen, dark = current
            for b in self._buttons:
                colour = b.property("swatch")
                ring = qt_theme.colours(dark)["fg"] if colour == chosen else "transparent"
                b.setStyleSheet(f"QPushButton {{ background: {colour}; border: 2px solid {ring}; "
                                f"border-radius: 4px; padding: 0; min-width: 0; }}")
                b.setAccessibleName(colour)

    def _pick(self):
        from PySide6.QtWidgets import QColorDialog
        chosen = self._current[0] if isinstance(self._current, tuple) else None
        dlg = QColorDialog(QColor(chosen or qt_theme.CUSTOM_DEFAULT), self.window())
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        dlg.setWindowTitle(_("Eigene Farbe"))
        dlg.colorSelected.connect(lambda c: self._post("act", (self._key, c.name())))
        dlg.open()
        self._dialog = dlg                       # keep it alive while it is open


class TilesView(QWidget):
    """Key figure tiles (uimodel.Tiles): as many side by side as fit (TileGrid), each a FactBox on a card."""

    def __init__(self):
        super().__init__()
        self._grid = TileGrid(self, min_width=150, columns=6)
        self._tiles = []
        self._shown = None

    def show_state(self, st):
        data = st.get("data") or []
        if data is self._shown:
            return
        self._shown = data
        while len(self._tiles) < len(data):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)
            cl.addWidget(box)
            self._grid.addWidget(card)
            self._tiles.append((card, box))
        for i, (card, box) in enumerate(self._tiles):
            card.setVisible(i < len(data))
            if i < len(data):
                box.show_fact(data[i])
        self.setVisible(bool(data))


class DashboardView(QWidget):
    """The statistics dashboard (dashboard.Dashboard): key figure tiles, the most played maps, killer × map."""

    def __init__(self, key="", post=None):
        super().__init__()
        self._shown = None
        self._key, self._post = key, post
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.empty = _label(cls="dim")
        lay.addWidget(self.empty)
        self.tiles_box = QWidget()
        self.grid = TileGrid(self.tiles_box, min_width=140, columns=6)   # fewer columns in a narrow window
        self.tiles = []
        for _i in range(6):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            box = FactBox(bar=True)
            box.sub.setWordWrap(True)                 # "no killer rounds with stats data": wraps in a narrow window
            cl.addWidget(box)
            self.grid.addWidget(card)
            self.tiles.append((card, box))
        lay.addWidget(self.tiles_box)
        click = self._click if post else None
        self.maps_card, self.maps = self._chart_card(lay, _("Maps – am häufigsten gespielt"), MapBars(click))
        self.heat_card, self.heat = self._chart_card(lay, _("Killer × Map – Ø Kills laut Stats-Seite"), Heatmap(click))
        self.heat_note = _label(cls="dim", wrap=True)
        self.heat_card.layout().addWidget(self.heat_note)

    def _click(self, value):
        if self._post:
            self._post("act", (self._key, value))

    @staticmethod
    def _chart_card(lay, title, widget):
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)
        cl.addWidget(_label(title.upper(), "h2"))
        cl.addWidget(widget)
        lay.addWidget(card)
        return card, widget

    def show_state(self, st):
        d, dark = st.get("data"), bool(st.get("dark", True))
        key = (id(d), dark)
        if key == self._shown:
            return
        self._shown = key
        has = d is not None and not d.empty
        self.empty.setVisible(d is not None and bool(d.empty))
        _set(self.empty, d.empty if d is not None else "")
        for w in (self.tiles_box, self.maps_card, self.heat_card):
            w.setVisible(has)
        if not has:
            return
        for i, (card, box) in enumerate(self.tiles):
            card.setVisible(i < len(d.tiles))
            if i < len(d.tiles):
                box.show_fact(d.tiles[i])
        self.maps.set_rows(d.maps, d.maps_max, dark)
        self.heat.set_data(d, dark)
        self.heat.setVisible(bool(d.rows))
        _set(self.heat_note, "" if d.rows else _("Noch keine Killer-Runden mit Ergebnis von der Stats-Seite "
                                                 "(Einstellungen → Mehr → Offizielle Match-Daten)."))
        self.heat_note.setVisible(not d.rows)
