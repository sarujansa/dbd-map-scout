"""Layouts of the control window that follow its width (since 1.59.1, user's wish: a narrow window cut things
off): a row that wraps when it does not fit (FlowRow), tiles that take fewer columns (TileGrid) and a tick box
whose text wraps (WrapCheck – Qt's QCheckBox keeps its text on one line and makes the page wider)."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLayout, QSizePolicy, QWidget


def _height(item, width: int) -> int:
    return item.heightForWidth(width) if item.hasHeightForWidth() else item.sizeHint().height()


def _one_line(label) -> int:
    """Width of a label's text on one line (a word-wrapping QLabel reports a narrower size hint and wraps)."""
    m = label.contentsMargins()
    fm = label.fontMetrics()
    lines = (label.text() or "").split("\n")
    return max(fm.horizontalAdvance(t) for t in lines) + m.left() + m.right() + 2 * label.margin() + 2


def _natural(item) -> int:
    """1.8.7: the width an item wants in a row – a wrapping label or tick box only wraps when the row is too
    narrow for its text on one line (before, "übriger Desktop-Ton" wrapped in a wide window and its tick sat
    above the others)."""
    w = item.widget()
    if w is not None:
        if isinstance(w, QLabel) and w.wordWrap():
            return max(w.minimumWidth(), _one_line(w))
        if hasattr(w, "natural_width"):
            return max(w.minimumWidth(), w.natural_width())
    return item.sizeHint().width()


class _Layout(QLayout):
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def _shown(self):
        return [it for it in self._items if not (it.widget() is not None and it.widget().isHidden())]

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()


class FlowRow(_Layout):
    """Controls side by side; ``right`` of them (the last ones) sit at the right end – like a row with a stretch.
    When they do not fit in one line, all of them flow on, line by line, left-aligned."""

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent, spacing)
        self.right = 0                       # how many of the last items go to the right end

    def minimumSize(self):
        # the height of one line: the real height comes from heightForWidth (a minimum for the narrowest width
        # would leave a gap below in a wide window)
        items = self._shown()
        w = max((it.minimumSize().width() for it in items), default=0)
        return QSize(w, max((it.minimumSize().height() for it in items), default=0))

    def sizeHint(self):
        items = self._shown()
        w = sum(_natural(it) for it in items) + self._gap * max(0, len(items) - 1)
        return QSize(w, max((it.sizeHint().height() for it in items), default=0))

    def _place(self, rect, apply):
        items = self._shown()
        if not items:
            return 0
        widths = [min(_natural(it), rect.width()) for it in items]
        total = sum(widths) + self._gap * (len(items) - 1)
        lines, line, x = [], [], 0
        for it, w in zip(items, widths):
            if line and x + w > rect.width():
                lines.append(line)
                line, x = [], 0
            line.append((it, w))
            x += w + self._gap
        lines.append(line)
        one_line = total <= rect.width()
        n_right = min(self.right, len(items)) if one_line else 0
        y = rect.y()
        for line in ([[(it, w) for it, w in zip(items, widths)]] if one_line else lines):
            h = max(_height(it, w) for it, w in line)
            x = rect.x()
            for i, (it, w) in enumerate(line):
                if n_right and i == len(line) - n_right:          # the right group: to the right end
                    rest = sum(ww for _it, ww in line[i:]) + self._gap * (n_right - 1)
                    x = rect.right() + 1 - rest
                if apply:
                    ih = _height(it, w)
                    it.setGeometry(QRect(QPoint(x, y + (h - ih) // 2), QSize(w, ih)))
                x += w + self._gap
            y += h + self._gap
        return y - self._gap - rect.y()


class TileGrid(_Layout):
    """Tiles of equal width: as many columns as fit with ``min_width`` each (at most ``columns``), the rest on
    the next lines – six tiles side by side in a wide window, two or three below each other in a narrow one."""

    def __init__(self, parent=None, min_width=150, columns=6, spacing=12):
        super().__init__(parent, spacing)
        self.min_width = min_width
        self.columns = columns

    def minimumSize(self):
        items = self._shown()           # one row high, like FlowRow: heightForWidth gives the real height
        w = min(self.min_width, max((it.minimumSize().width() for it in items), default=0)) if items else 0
        return QSize(w, max((it.minimumSize().height() for it in items), default=0))

    def sizeHint(self):
        n = min(len(self._shown()), self.columns)
        w = n * self.min_width + self._gap * max(0, n - 1)
        return QSize(w, self.heightForWidth(w))

    def cols_for(self, width: int) -> int:
        """Columns for this width, evened out: four tiles 2 × 2 rather than 3 + 1, six 3 + 3 rather than 4 + 2."""
        n = len(self._shown())
        fit = max(1, (width + self._gap) // (self.min_width + self._gap))
        cols = max(1, min(n or 1, self.columns, fit))
        rows = -(-max(n, 1) // cols)
        return -(-max(n, 1) // rows)

    def _place(self, rect, apply):
        items = self._shown()
        if not items:
            return 0
        cols = self.cols_for(rect.width())
        w = (rect.width() - self._gap * (cols - 1)) // cols
        y = rect.y()
        for start in range(0, len(items), cols):
            row = items[start:start + cols]
            h = max(_height(it, w) for it in row)
            for i, it in enumerate(row):
                if apply:
                    it.setGeometry(QRect(rect.x() + i * (w + self._gap), y, w, h))
            y += h + self._gap
        return y - self._gap - rect.y()


class _ClickLabel(QLabel):
    def __init__(self, box):
        super().__init__()
        self._box = box

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._box.isEnabled():
            self._box.click()


class WrapCheck(QWidget):
    """A tick box whose text wraps in a narrow window; otherwise like QCheckBox (text, checked, clicked)."""

    clicked = Signal(bool)

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.box = QCheckBox()
        self.label = _ClickLabel(self.box)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.box, 0, Qt.AlignTop)
        lay.addWidget(self.label, 1)
        self.box.clicked.connect(lambda _c=False: self.clicked.emit(self.box.isChecked()))

    def natural_width(self) -> int:
        """Box + text on one line (FlowRow): wraps only when the row is narrower."""
        return self.box.sizeHint().width() + self.layout().spacing() + _one_line(self.label)

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str):
        self.label.setText(text)

    def isChecked(self) -> bool:
        return self.box.isChecked()

    def setChecked(self, on: bool):
        self.box.setChecked(on)

    def click(self):
        self.box.click()
