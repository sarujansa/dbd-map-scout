"""Text folding shared by the catalog (candidate names) and the OCR scorer.

Everything is reduced to the 36 symbols A-Z and 0-9. Spaces, apostrophes,
hyphens and other punctuation disappear, accents are stripped and case is
ignored, so "Azarov’s Resting Place", "AZAROVS RESTING PLACE" and
"Azarov's Resting-Place" all fold to the same key.
"""
import re
import unicodedata

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

_SPECIAL = {
    "ß": "SS", "ẞ": "SS", "ł": "L", "Ł": "L", "ı": "I", "İ": "I",
    "ø": "O", "Ø": "O", "æ": "AE", "Æ": "AE", "œ": "OE", "Œ": "OE",
    "đ": "D", "Đ": "D", "þ": "TH", "Þ": "TH",
}

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}


def fold(text: str) -> str:
    """Uppercase A-Z0-9 only; accents stripped, everything else removed."""
    out = []
    for ch in unicodedata.normalize("NFKC", text or ""):
        if ch in _SPECIAL:
            out.append(_SPECIAL[ch])
            continue
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c))
        out.append(base.upper())
    return re.sub(r"[^A-Z0-9]", "", "".join(out))


def roman(n: int) -> str:
    return _ROMAN.get(int(n), str(n))


# Leading articles that the game might or might not render in front of a name.
_ARTICLES = {
    "en": ("The ",),
    "de": ("Der ", "Die ", "Das "),
    "fr": ("Le ", "La ", "Les ", "L'", "L’"),
    "es": ("El ", "La ", "Los ", "Las "),
    "es-MX": ("El ", "La ", "Los ", "Las "),
    "it": ("Il ", "La ", "Lo ", "I ", "L'", "L’"),
    "pt-BR": ("O ", "A ", "Os ", "As "),
}


def name_forms(name: str, lang: str):
    """The name itself plus, if it starts with an article, the form without it."""
    forms = [name]
    for art in _ARTICLES.get(lang, ()):
        if name.lower().startswith(art.lower()) and len(name) > len(art) + 2:
            forms.append(name[len(art):])
            break
    return forms


def pretty(text: str) -> str:
    """Collapse whitespace for display."""
    return re.sub(r"\s+", " ", text or "").strip()


def fmt_duration(seconds: float) -> str:
    """12:34 or 1:02:03 (round timer)."""
    s = max(0, int(seconds))
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
