"""Small helpers shared by the Qt pages and views (labels, cards, tooltips, pixmaps, scroll pages).
"""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from .i18n import _


SLIDER_MAX = 420                  # px (logical): longest slider (overlay position, size, opacity)


def pixmap_from_pil(img: Image.Image, height: int, ratio: float = 1.0) -> QPixmap:
    """Map picture (PIL, RGBA) -> QPixmap ``height`` logical px tall, sharp on scaled screens."""
    img = img.convert("RGBA")
    h = max(1, round(height * ratio))
    w = max(1, round(img.width * h / img.height))
    # 1.3.3: reducing_gap shrinks in big integer steps first (a 1440-px card to a 120-px preview: ~5× faster,
    # the same picture to the eye)
    img = img.resize((w, h), Image.LANCZOS, reducing_gap=2.0 if h < img.height else None)
    data = img.tobytes("raw", "RGBA")
    pm = QPixmap.fromImage(QImage(data, w, h, 4 * w, QImage.Format_RGBA8888).copy())
    pm.setDevicePixelRatio(ratio)
    return pm


def _label(text="", cls=None, wrap=False):
    w = QLabel(text)
    if cls:
        w.setProperty("class", cls)
    if wrap:
        w.setWordWrap(True)
    return w


def _tip(label: str) -> str:
    """Hover text of a button of the window itself (tooltip.TIPS, by German label)."""
    from .tooltip import tip_for_label
    return tip_for_label(_(label)) or ""


def _card():
    f = QFrame()
    f.setProperty("class", "card")
    return f


def _set(widget, text):
    if widget.text() != text:
        widget.setText(text)


def steady_scroll(sa):
    """1.8.24 (user: "das GUI springt ab und zu kurz nach links und wieder zurück"): a page close to the window's
    height got its scroll bar for a moment whenever a line came and went – everything moved left by its width and
    back. The bar is always there; without anything to scroll its handle is invisible (``idle``)."""
    sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    bar = sa.verticalScrollBar()

    def idle(_lo=0, hi=None):
        on = (bar.maximum() if hi is None else hi) <= 0
        if bar.property("idle") != on:
            bar.setProperty("idle", on)
            bar.style().unpolish(bar)
            bar.style().polish(bar)
    bar.rangeChanged.connect(idle)
    idle()
    return sa


def _scroll_page(title, scroll=True):
    """(page, body layout): a page that scrolls as a whole, with its title on top (``scroll`` False: a page that
    fits the window, its parts scroll on their own)."""
    page = QWidget()
    page.setObjectName("page")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    body = QWidget()
    body.setObjectName("page")
    if scroll:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        steady_scroll(sa)
        outer.addWidget(sa)
        sa.setWidget(body)
    else:
        outer.addWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(22, 18, 22, 18)
    lay.setSpacing(12)
    lay.addWidget(_label(title, "h1"))
    return page, lay
