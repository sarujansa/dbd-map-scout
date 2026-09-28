"""Map catalog: which image belongs to which in-game map name.

maps.json lists every map with its realm, localized names and the image file
per layout variant. Images that are in the maps folder but not listed in
maps.json are added automatically (file name = map name, folder = realm), so
new maps can be added by just dropping a picture into the folder.

Own pictures live in ``user_maps/`` (gitignored, written by "Kartenbild hinzufügen …"):
a picture with the same relative path as a listed one (any extension) replaces it,
every other picture becomes a map of its own, just like unlisted files in ``maps/``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .i18n import _
from .mapimage import USER_DIR
from .textnorm import fold, name_forms, roman

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


@dataclass
class MapEntry:
    id: str
    realm: str
    names: dict                      # lang -> display name
    variants: dict                   # int -> relative image path or None
    realm_names: dict = field(default_factory=dict)
    aliases: list = field(default_factory=list)
    custom: bool = False

    @property
    def name(self) -> str:
        return self.names.get("en") or next(iter(self.names.values()))

    def label(self, variant: int = 1) -> str:
        n = self.name
        if len(self.variants) > 1:
            n = f"{n} {roman(variant)}"
        return n

    def image_for(self, variant: int):
        """(relative path, variant actually shown). Falls back to variant 1."""
        p = self.variants.get(variant)
        if p:
            return p, variant
        for v in sorted(self.variants):
            if self.variants[v]:
                return self.variants[v], v
        return None, variant


@dataclass
class Hypothesis:
    map_id: str
    variant: int
    lang: str
    name_key: str          # folded map-name string
    realm_keys: tuple      # folded realm strings allowed together with this name


class Catalog:
    def __init__(self, root: str, languages=("en", "de"), aliases=None):
        """``aliases``: the user's own assignments {map_id: [banner text, ...]} (settings.json),
        added to the aliases from maps.json."""
        self.root = root
        self.maps_dir = os.path.join(root, "maps")
        self.user_dir = os.path.join(root, USER_DIR)
        self.languages = [l for l in languages] or ["en"]
        self.maps: dict[str, MapEntry] = {}
        self.realms: dict[str, dict] = {}
        self._load()
        for mid, texts in (aliases or {}).items():
            m = self.maps.get(mid)
            if m:
                m.aliases.extend(t for t in texts if fold(t) and t not in m.aliases)
        self._build_hypotheses()

    # ------------------------------------------------------------------ load
    def _load(self):
        path = os.path.join(self.root, "maps.json")
        data = {"realms": {}, "maps": []}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        self.realms = data.get("realms", {})
        used = set()
        own = {_stem_key(rel): os.path.join(self.user_dir, rel) for rel in _pictures(self.user_dir)}
        for m in data.get("maps", []):
            variants = {}
            for k, v in (m.get("variants") or {"1": None}).items():
                if v:
                    stem = _stem_key(v)
                    if stem in own:                   # own picture replaces the supplied one
                        used.add(stem)
                        v = own[stem]
                    elif not os.path.exists(os.path.join(self.maps_dir, v)):
                        v = None
                    else:
                        used.add(stem)
                variants[int(k)] = v
            realm = m.get("realm", "")
            entry = MapEntry(
                id=m["id"], realm=realm, names=dict(m.get("names", {})), variants=variants,
                realm_names=dict(self.realms.get(realm, {"en": realm})),
                aliases=list(m.get("aliases", [])),
            )
            self.maps[entry.id] = entry
        # images nobody listed -> custom maps (file name = map name); an own picture with the
        # same path (any extension) replaces a supplied one
        custom_ids = {}                               # stem -> id of a supplied unlisted picture
        for base in (self.maps_dir, self.user_dir):
            for rel in _pictures(base):
                stem = _stem_key(rel)
                if stem in used:
                    continue
                path = rel.replace("\\", "/") if base == self.maps_dir else os.path.join(base, rel)
                if base == self.user_dir and stem in custom_ids:
                    self.maps[custom_ids[stem]].variants[1] = path     # own picture replaces it, same id
                    continue
                folder = os.path.dirname(rel).replace("\\", "/").split("/")[-1]
                realm_key = self._known_realm(folder)
                mid = "custom:" + rel.replace("\\", "/")
                if base == self.maps_dir:
                    custom_ids[stem] = mid
                elif mid in self.maps:
                    mid = "custom:user/" + rel.replace("\\", "/")
                self.maps[mid] = MapEntry(
                    id=mid, realm=realm_key or folder, names={"en": os.path.splitext(os.path.basename(rel))[0]},
                    variants={1: path},
                    # only a folder named like a real realm constrains the realm line
                    realm_names=dict(self.realms[realm_key]) if realm_key else {}, custom=True,
                )

    def _known_realm(self, folder: str):
        f = fold(folder)
        if not f:
            return None
        for key, names in self.realms.items():
            if f == fold(key) or any(f == fold(n) for n in names.values()):
                return key
        return None

    def is_own(self, map_id: str, variant: int = 1) -> bool:
        """Is the picture shown for this map one of the user's own (user_maps/)?"""
        path, _ = self.image_path(map_id, variant)
        return bool(path) and os.path.normcase(os.path.abspath(path)).startswith(
            os.path.normcase(os.path.abspath(self.user_dir)) + os.sep)

    def own_stem(self, map_id: str, variant: int = 1):
        """Relative path (no extension) an own picture for this map must have to replace it."""
        m = self.maps.get(map_id)
        if not m:
            return None
        v = m.variants.get(variant) or ""
        if not v:
            return None
        if os.path.isabs(v):
            return os.path.splitext(os.path.relpath(v, self.user_dir))[0].replace("\\", "/")
        return os.path.splitext(v)[0].replace("\\", "/")

    # ----------------------------------------------------------- hypotheses
    def _build_hypotheses(self):
        hyps = []
        for m in self.maps.values():
            langs = [l for l in self.languages if l in m.names]
            if m.custom or not langs:
                langs = list(m.names)[:1]
            multi = len(m.variants) > 1
            for lang in langs:
                if m.custom:
                    # file name is language-neutral: accept the realm in any enabled language
                    realm_keys = tuple(dict.fromkeys(
                        fold(r) for l in self.languages for r in name_forms(m.realm_names.get(l, ""), l) if fold(r)))
                else:
                    realm = m.realm_names.get(lang) or m.realm_names.get("en") or m.realm
                    realm_keys = tuple(dict.fromkeys(fold(r) for r in name_forms(realm, lang) if fold(r)))
                for form in name_forms(m.names[lang], lang):
                    for v in sorted(m.variants):
                        texts = []
                        if not multi:
                            texts = [form]
                        elif v == 1:
                            texts = [form, f"{form} {roman(1)}"]
                        else:
                            texts = [f"{form} {roman(v)}"]
                        for t in texts:
                            k = fold(t)
                            if k:
                                hyps.append(Hypothesis(m.id, v, lang, k, realm_keys))
            for alias in m.aliases:
                all_realms = tuple(dict.fromkeys(
                    fold(r) for l in self.languages for r in name_forms(m.realm_names.get(l, ""), l) if fold(r)))
                k = fold(alias)
                if k:
                    hyps.append(Hypothesis(m.id, 1, "alias", k, all_realms))
        self.hypotheses = hyps
        self.name_strings = sorted({h.name_key for h in hyps})
        self.realm_strings = sorted({r for h in hyps for r in h.realm_keys})

    # --------------------------------------------------------------- helpers
    def image_path(self, map_id: str, variant: int = 1):
        m = self.maps.get(map_id)
        if not m:
            return None, variant
        rel, shown = m.image_for(variant)
        return (os.path.join(self.maps_dir, rel) if rel else None), shown

    # ----------------------------------------------------- user assignments
    MIN_ALIAS = 4                    # letters/digits a banner text needs to be assigned to a map

    def alias_problem(self, text: str, map_id: str) -> str | None:
        """Why ``text`` cannot become an alias of ``map_id`` (None = fine)."""
        k = fold(text)
        if len(k) < self.MIN_ALIAS:
            return _("Der gelesene Text ist zu kurz.")
        if map_id not in self.maps:
            return _("Unbekannte Map.")
        other = {h.map_id for h in self.hypotheses if h.name_key == k} - {map_id}
        if other:
            return _("„{text}“ ist schon der Name von {map}.", text=text, map=self.maps[sorted(other)[0]].name)
        return None

    def suggest(self, name_text: str, realm_text: str = "") -> str | None:
        """Best guess for a banner that matched no map: similar name, realm read as well.
        Only a preselection for the user – never used for detection."""
        import difflib
        n, r = fold(name_text), fold(realm_text)
        best, best_score = None, 0.0
        for m in self.maps.values():
            if m.custom:
                continue
            ns = max((difflib.SequenceMatcher(None, n, fold(x)).ratio() for x in list(m.names.values()) + m.aliases),
                     default=0.0)
            rs = max((difflib.SequenceMatcher(None, r, fold(x)).ratio() for x in m.realm_names.values()),
                     default=0.0) if r else 0.0
            score = ns + 0.5 * rs
            if score > best_score:
                best, best_score = m.id, score
        return best

    def sorted_entries(self):
        return sorted(self.maps.values(), key=lambda m: (m.realm.lower(), m.name.lower()))

    def realm_display(self, m: MapEntry) -> str:
        return m.realm_names.get("en") or m.realm

    def search(self, query: str):
        """Maps whose (any language) name or realm contains the query."""
        q = fold(query)
        res = []
        for m in self.sorted_entries():
            keys = [fold(n) for n in m.names.values()] + [fold(r) for r in m.realm_names.values()] + [fold(a) for a in m.aliases]
            if not q or any(q in k for k in keys):
                res.append(m)
        return res


def _stem_key(rel: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.splitext(rel)[0]))


def _pictures(base: str):
    """Relative paths of all pictures below ``base`` (sorted, stable)."""
    out = []
    if os.path.isdir(base):
        for dirpath, dirs, files in os.walk(base):
            dirs.sort()
            for f in sorted(files):
                if f.lower().endswith(IMAGE_EXT):
                    out.append(os.path.relpath(os.path.join(dirpath, f), base))
    return out
