"""Icon in the notification area (next to the clock) – pystray, own thread.

Menu actions are only posted to the UI thread (``post(action)`` with "open" / "toggle" /
"quit"); the window is never touched from the tray thread.
"""
from __future__ import annotations

import logging

from .i18n import _

log = logging.getLogger("dbdmapscout")


class Tray:
    def __init__(self, post):
        self._post = post
        self._icon = None
        self.error = ""
        self._dot = None                  # status dot on the icon (1.3.6): theme.DOT key or None
        self._images = {}

    @property
    def active(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        try:
            import pystray
            from .icon import draw
        except Exception as e:                          # package missing (older installation)
            self.error = f"{type(e).__name__}: {e}"
            return False
        menu = pystray.Menu(
            pystray.MenuItem(_("Fenster öffnen"), lambda icon, item: self._post("open"), default=True),
            pystray.MenuItem(_("Overlay ein/aus"), lambda icon, item: self._post("toggle")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_("Beenden"), lambda icon, item: self._post("quit")),
        )
        try:
            self._icon = pystray.Icon("dbdmapscout", draw(64), "DbD Map Scout", menu)
            self._icon.run_detached()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self._icon = None
            return False
        return True

    def set_title(self, text: str) -> None:
        if self._icon is not None:
            try:
                self._icon.title = text[:127]                # Windows limit for tooltips
            except Exception:
                log.debug("tray title", exc_info=True)

    def image(self, dot):
        """The icon with the dot of a status (cached per status)."""
        if dot not in self._images:
            from .icon import draw_status
            from .theme import DOT
            self._images[dot] = draw_status(64, DOT.get(dot) if dot else None)
        return self._images[dot]

    def set_status(self, dot) -> None:
        """Colour the dot: "ok" green, "warn" yellow, "err" red, "idle" grey, None = no dot. Only on a change."""
        if self._icon is None or dot == self._dot:
            return
        try:
            self._icon.icon = self.image(dot)
            self._dot = dot
        except Exception:
            log.debug("tray status", exc_info=True)

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()                                  # ends its (non-daemon) thread
            except Exception:
                log.debug("tray stop", exc_info=True)
