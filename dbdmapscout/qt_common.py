"""Small helpers shared by the Qt pages and views (labels, cards, tooltips, pixmaps, scroll pages).
"""
from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from .i18n import _


SLIDER_MAX = 420                  # px (logical): longest slider (overlay position, size, opacity)


def pixmap_from_pil(img: Image.Image, height: int, ratio: float = 1.0) -> QPixmap:
    """Map picture (PIL, RGBA) -> QPixmap ``height`` logical px tall, sharp on scaled screens."""
    img = img.convert("RGBA")
    h = max(1, round(height * ratio))
    w = max(1, round(img.width * h / img.height))
    img = img.resize((w, h), Image.LANCZOS)
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
        outer.addWidget(sa)
        sa.setWidget(body)
    else:
        outer.addWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(22, 18, 22, 18)
    lay.setSpacing(12)
    lay.addWidget(_label(title, "h1"))
    return page, lay
