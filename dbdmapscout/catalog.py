"""Map catalog: which image belongs to which in-game map name.

maps.json lists every map with its realm, localized names and the image file
per layout variant. Images that are in the maps folder but not listed in
maps.json are added automatically (file name = map name, folder = realm), so
new maps can be added by just dropping a picture into the folder.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

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
    def __init__(self, root: str, languages=("en", "de")):
        self.root = root
        self.maps_dir = os.path.join(root, "maps")
        self.languages = [l for l in languages] or ["en"]
        self.maps: dict[str, MapEntry] = {}
        self.realms: dict[str, dict] = {}
        self._load()
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
        for m in data.get("maps", []):
            variants = {}
            for k, v in (m.get("variants") or {"1": None}).items():
                if v and not os.path.exists(os.path.join(self.maps_dir, v)):
                    v = None
                variants[int(k)] = v
                if v:
                    used.add(os.path.normcase(os.path.normpath(v)))
            realm = m.get("realm", "")
            entry = MapEntry(
                id=m["id"], realm=realm, names=dict(m.get("names", {})), variants=variants,
                realm_names=dict(self.realms.get(realm, {"en": realm})),
                aliases=list(m.get("aliases", [])),
            )
            self.maps[entry.id] = entry
        # images nobody listed -> custom maps (file name = map name)
        if os.path.isdir(self.maps_dir):
            for dirpath, _, files in os.walk(self.maps_dir):
                for f in sorted(files):
                    if not f.lower().endswith(IMAGE_EXT):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, f), self.maps_dir)
                    if os.path.normcase(os.path.normpath(rel)) in used:
                        continue
                    stem = os.path.splitext(f)[0]
                    folder = os.path.basename(dirpath) if os.path.normpath(dirpath) != os.path.normpath(self.maps_dir) else ""
                    realm_key = self._known_realm(folder)
                    mid = "custom:" + rel.replace("\\", "/")
                    self.maps[mid] = MapEntry(
                        id=mid, realm=realm_key or folder, names={"en": stem}, variants={1: rel.replace("\\", "/")},
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
