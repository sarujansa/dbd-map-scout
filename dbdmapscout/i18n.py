"""Language of the user interface and the log (German / English).

The German text in the code is the key: ``_("Overlay testen")`` returns the English text from
``i18n_en.EN`` when English is active, else the German one. Placeholders are named and filled by
``_()``: ``_("Erkannt: {name}", name=label)``. A missing translation falls back to German, and
tests/test_i18n.py makes sure there are none.

The language is chosen once at start (setting ``ui_language``: "auto" | "de" | "en"; "auto" =
German if Windows runs in German, else English). Changing it takes effect after a restart.
"""
from __future__ import annotations

import json
import locale
import os
import sys

LANGUAGES = [("auto", "Automatisch (Windows-Sprache)"), ("de", "Deutsch"), ("en", "English")]   # "auto": translated

_lang = "de"
_table: dict = {}
_reverse: dict = {}


def system_language() -> str:
    """'de' if Windows (or the locale) is German, else 'en'. DBDMS_LANG overrides (tests)."""
    if os.environ.get("DBDMS_LANG") in ("de", "en"):
        return os.environ["DBDMS_LANG"]
    try:
        if sys.platform == "win32":
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "de" if (langid & 0x3FF) == 0x07 else "en"
        code = (locale.getlocale()[0] or os.environ.get("LANG", "") or "").lower()
        return "de" if code.startswith("de") else "en"
    except Exception:
        return "en"


def resolve(setting: str | None) -> str:
    return setting if setting in ("de", "en") else system_language()


def set_language(code: str) -> str:
    """Activate 'de' or 'en' ('auto'/None: from the system). Returns the active code."""
    global _lang, _table, _reverse
    _lang = resolve(code)
    if _lang == "en":
        from .i18n_en import EN
        _table = EN
    else:
        _table = {}
    _reverse = {v: k for k, v in _table.items()}
    return _lang


def init_from_settings(path: str) -> str:
    """Language from settings.json before the app (and its Settings object) exists."""
    setting = "auto"
    try:
        with open(path, encoding="utf-8") as fh:
            setting = json.load(fh).get("ui_language", "auto")
    except (OSError, ValueError, AttributeError):
        pass
    return set_language(setting)


def current() -> str:
    return _lang


def _(msg: str, /, **kw) -> str:
    out = _table.get(msg, msg)
    if kw:
        try:
            return out.format(**kw)
        except (KeyError, IndexError, ValueError):
            return msg.format(**kw)
    return out


def source(text: str) -> str:
    """German original of a (translated) text – for lookups keyed by the German label."""
    return _reverse.get(text, text)


def N_(text: str) -> str:
    """Marks a text for translation where it is defined (lists, tables); translated later with _()."""
    return text
