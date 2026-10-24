"""Colours of the control window shared by its parts: the dark palette (qt_theme builds the style sheet from it),
the status dots and the log's category colours."""
from __future__ import annotations

LOG_COLORS = {
    True: {"ts": "#6f757d", "Erkennung": "#7cc47f", "Overlay": "#6fa8dc", "System": "#b3b8bf", "Fehler": "#e06c6c",
           "text": "#dfe2e6"},
    False: {"ts": "#8a8f96", "Erkennung": "#1e7b34", "Overlay": "#1f5fa8", "System": "#555b63", "Fehler": "#b3261e",
            "text": "#1b1b1b"},
}
DOT = {"ok": "#3fb950", "warn": "#d29922", "err": "#e5534b", "info": "#58a6ff", "idle": "#8b8f98"}

DARK = {
    "bg": "#1e1f22", "panel": "#2b2d31", "field": "#232428", "border": "#3a3c42",
    "fg": "#e3e5e8", "dim": "#9ba1a9", "accent": "#c9a227", "select": "#7a1f1f",
    "hover": "#383a40", "press": "#43464d",
}
