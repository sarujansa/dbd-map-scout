"""Icon in the notification area (next to the clock) – pystray, own thread.

Menu actions are only posted to the UI thread (``post(action)`` with "open" / "toggle" /
"quit"); Tk is never touched from the tray thread.
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

    def notify(self, title: str, text: str) -> bool:
        """Windows notification ("balloon") from the tray icon."""
        if self._icon is None:
            return False
        try:
            self._icon.notify(text[:250], title[:60])
            return True
        except Exception:
            log.debug("tray notify", exc_info=True)
            return False

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        if icon is not None:
            try:
                icon.stop()                                  # ends its (non-daemon) thread
            except Exception:
                log.debug("tray stop", exc_info=True)
