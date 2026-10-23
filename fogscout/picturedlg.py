"""Dialog "Kartenbild hinzufügen …": pick a picture, remove its background, store it in user_maps/.

Either replaces the picture of a known map (one layout) or adds a new map (name as on the
in-game banner + realm folder). The conversion itself is in mapimage.py.
"""
from __future__ import annotations

import os
import sys
from PIL import Image

from . import mapimage as mi, tooltip
from . import uimodel as ui
from .i18n import _
from .textnorm import fold

PREVIEW_H = 220


def checkerboard(size, cell=10):
    """Light/dark checks behind a transparent preview."""
    w, h = size
    img = Image.new("RGB", size, (58, 60, 66))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if (x // cell + y // cell) % 2:
                px[x, y] = (84, 86, 94)
    return img


def preview(img: Image.Image, height: int = PREVIEW_H) -> Image.Image:
    img = img.convert("RGBA")
    w = max(1, round(img.width * height / img.height))
    img = img.resize((w, height), Image.LANCZOS)
    bg = checkerboard(img.size).convert("RGBA")
    bg.alpha_composite(img)
    return bg.convert("RGB")


def open_folder(path: str) -> bool:
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)                                   # noqa: S606 – opens Explorer
        return True
    return False


class PictureDialog:
    def __init__(self, app, name: str = "", realm: str = "", map_id=None, variant: int = 1):
        """``name``/``realm``: read from a banner that matched no map (new map prefilled).
        ``map_id``: known map to replace (e.g. the one on display)."""
        self.app = app
        cat = app.catalog
        self.choices = [(m.id, v) for m in cat.sorted_entries() for v in sorted(m.variants) if m.variants[v]]
        self.labels = [f"{cat.maps[mid].label(v)} ({cat.realm_display(cat.maps[mid])})" +
                       (" – " + _("eigenes Bild") if cat.is_own(mid, v) else "") for mid, v in self.choices]
        self.realms = sorted(cat.realms)
        self.src = None
        self._base = None                    # picked picture after trim/background removal (preview)

        d = self.dlg = ui.Toplevel(app.ui_root)
        d.title(_("Kartenbild hinzufügen"))
        body = ui.Frame(d, padding=12)
        body.pack(fill="both", expand=True)

        row = ui.Frame(body)
        row.pack(fill="x")
        ui.Button(row, text=_("Bild wählen …"), command=self.choose).pack(side="left")
        self.file_var = ui.StringVar(value=_("Noch kein Bild gewählt (PNG, JPG, WebP, GIF)"))
        ui.Label(row, textvariable=self.file_var, style="Dim.TLabel", wraplength=360).pack(side="left", padx=8)

        self.mode = ui.StringVar(value="new" if name or map_id is None and not app.current else "replace")
        mf = ui.LabelFrame(body, text=_("Für welche Map?"), padding=8)
        mf.pack(fill="x", pady=(10, 0))
        ui.Radiobutton(mf, text=_("Bild einer vorhandenen Map ersetzen"), variable=self.mode, value="replace",
                        command=self._mode_changed).pack(anchor="w")
        pre = map_id or (app.current[0] if app.current else None)
        pre_v = variant if map_id else (app.current[1] if app.current else 1)
        self.map_var = ui.StringVar(value=self.labels[self.choices.index((pre, pre_v))]
                                    if (pre, pre_v) in self.choices else "")
        self.map_cb = ui.Combobox(mf, textvariable=self.map_var, values=self.labels, state="readonly",
                                   width=48, height=18)
        self.map_cb.pack(fill="x", padx=(22, 0), pady=(2, 6))
        self.map_cb.bind("<<ComboboxSelected>>", lambda e: (self._update_buttons(),
                                                              self._render_preview(again=False)))
        ui.Radiobutton(mf, text=_("Neue Map (fehlt im Programm)"), variable=self.mode, value="new",
                        command=self._mode_changed).pack(anchor="w")
        nf = ui.Frame(mf)
        nf.pack(fill="x", padx=(22, 0), pady=(2, 0))
        ui.Label(nf, text=_("Name"), width=7).grid(row=0, column=0, sticky="w")
        self.name_var = ui.StringVar(value=name.title() if name.isupper() else name)
        self.name_var.trace_add("write", lambda *a: self._render_preview(again=False))
        self.name_entry = ui.Entry(nf, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, sticky="we", pady=1)
        ui.Label(nf, text="Realm", width=7).grid(row=1, column=0, sticky="w")
        self.realm_var = ui.StringVar(value=self._realm_guess(realm))
        self.realm_cb = ui.Combobox(nf, textvariable=self.realm_var, values=self.realms, width=38, height=18)
        self.realm_cb.grid(row=1, column=1, sticky="we", pady=1)
        ui.Label(nf, text=_("Name so, wie er im Map-Banner steht – dann wird die Map automatisch erkannt."),
                  style="Dim.TLabel", wraplength=380).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.bg_var = ui.BooleanVar(value=True)
        ui.Checkbutton(body, text=_("Hintergrund entfernen (Dunkelblau und Graulila der Community-Karten) "
                                     "und Rand abschneiden"), variable=self.bg_var,
                        command=self._render_preview).pack(anchor="w", pady=(10, 0))
        self.title_var = ui.BooleanVar(value=True)
        ui.Checkbutton(body, text=_("Map-Namen oben einfügen (wie bei den mitgelieferten Karten)"),
                        variable=self.title_var, command=lambda: self._render_preview(again=False)).pack(anchor="w")

        pv = ui.Frame(body)
        pv.pack(fill="x", pady=(8, 0))
        self.before = ui.Label(pv, text=_("Original"), anchor="center", width=30)
        self.before._dbdms_pil = None            # the previews as PIL images (shown by the window)
        self.before.pack(side="left", padx=(0, 6))
        self.after = ui.Label(pv, text=_("Ergebnis"), anchor="center", width=30)
        self.after._dbdms_pil = None
        self.after.pack(side="left")

        self.msg = ui.StringVar(value="")
        ui.Label(body, textvariable=self.msg, style="Dim.TLabel", wraplength=440).pack(anchor="w", pady=(8, 0))
        br = ui.Frame(body)
        br.pack(fill="x", pady=(8, 0))
        ui.Button(br, text=_("Ordner öffnen"), command=self.open_dir).pack(side="left")
        self.del_btn = ui.Button(br, text=_("Eigenes Bild löschen"), command=self.delete)
        self.del_btn.pack(side="left", padx=6)
        self.save_btn = ui.Button(br, text=_("Speichern"), command=self.save)
        self.save_btn.pack(side="right")
        ui.Button(br, text=_("Abbrechen"), command=d.destroy).pack(side="right", padx=6)
        d.bind("<Escape>", lambda e: d.destroy())
        self._mode_changed()
        tooltip.attach_all(d)
        app._dialog(d)                           # the window shows it

    # ---------------------------------------------------------------- helpers
    def _realm_guess(self, text: str) -> str:
        k = self.app.catalog._known_realm(text) if text else None
        return k or (text.title() if text.isupper() else text)

    def _selected(self):
        if self.map_var.get() in self.labels:
            return self.choices[self.labels.index(self.map_var.get())]
        return None

    def _mode_changed(self):
        new = self.mode.get() == "new"
        self.map_cb.configure(state="disabled" if new else "readonly")
        self.name_entry.configure(state="normal" if new else "disabled")
        self.realm_cb.configure(state="normal" if new else "disabled")
        self._update_buttons()
        self._render_preview(again=False)

    def _update_buttons(self):
        sel = self._selected()
        own = self.mode.get() == "replace" and sel and self.app.catalog.is_own(*sel)
        self.del_btn.configure(state="normal" if own else "disabled")
        self.save_btn.configure(state="normal" if self.src else "disabled")

    def choose(self, path=None):
        if path is None:                            # the window asks for the file, then calls again
            self.app._qt_file("open", _("Kartenbild wählen"), "", self.choose,
                              _("Bilder") + " (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
            return
        if not self.dlg.winfo_exists():
            return
        try:
            with Image.open(path) as im:
                im.load()
        except OSError as e:
            self.msg.set(_("Das ist kein lesbares Bild: {error}", error=e))
            return
        self.src = path
        self.file_var.set(os.path.basename(path))
        self._render_preview()
        self._update_buttons()

    def _title(self) -> str:
        """Name to put on top of the picture ("" = none)."""
        if not self.title_var.get():
            return ""
        if self.mode.get() == "new":
            return self.name_var.get().strip()
        sel = self._selected()
        return self.app.catalog.maps[sel[0]].label(sel[1]) if sel else ""

    def _render_preview(self, again: bool = True):
        """``again``: the picture or the background option changed (else only the name on top)."""
        if not self.src:
            return
        try:
            with Image.open(self.src) as im:
                im.load()
                note = ""
                if mi.is_animated(self.src):
                    self._base = None
                    result, note = im.convert("RGBA"), _("Animiertes GIF: wird unverändert übernommen.")
                else:
                    if again or self._base is None:
                        self._base = mi.prepare(im, self.bg_var.get())
                    if self._title() and mi.title_split(self._base) is not None:
                        note = _("Das Bild hat oben schon einen Namen – es wird keiner hinzugefügt.")
                    result = mi.convert(self._base, height=PREVIEW_H, title=self._title(), prepared=True)
                before = preview(im)
        except (OSError, ValueError) as e:
            self.msg.set(_("Bild konnte nicht verarbeitet werden: {error}", error=e))
            return
        self.before._dbdms_pil, self.after._dbdms_pil = before, preview(result)
        self.msg.set(note)

    # ---------------------------------------------------------------- actions
    def _target(self):
        """(relative stem, map_id or None, variant) or an error text."""
        cat = self.app.catalog
        if self.mode.get() == "replace":
            sel = self._selected()
            if not sel:
                return _("Bitte eine Map auswählen.")
            stem = cat.own_stem(*sel)
            return (stem, sel[0], sel[1]) if stem else _("Für diese Map lässt sich kein Bild speichern.")
        name = mi.safe_name(self.name_var.get())
        if len(fold(name)) < 3:
            return _("Bitte den Namen der Map eingeben.")
        taken = {h.map_id for h in cat.hypotheses if h.name_key == fold(name) and h.lang != "alias"}
        if taken:
            other = cat.maps[sorted(taken)[0]]
            return _("„{name}“ gibt es schon ({map}) – dann „Bild einer vorhandenen Map ersetzen“ wählen.", name=name,
                     map=other.name)
        realm = self._realm_guess(self.realm_var.get().strip())
        return f"{mi.safe_name(realm) or 'Eigene Maps'}/{name}", None, 1

    def save(self):
        if not self.src:
            self.msg.set(_("Erst ein Bild wählen."))
            return
        t = self._target()
        if isinstance(t, str):
            self.msg.set(t)
            return
        stem, map_id, variant = t
        dest = mi.target_path(self.app.root_dir, stem, mi.is_animated(self.src))
        try:
            mi.save(self.src, dest, self.bg_var.get(), self._title())
        except (OSError, ValueError) as e:
            self.msg.set(_("Speichern fehlgeschlagen: {error}", error=e))
            return
        self.app.picture_saved(dest, map_id, variant)
        self.dlg.destroy()

    def delete(self):
        sel = self._selected()
        cat = self.app.catalog
        if not sel or not cat.is_own(*sel):
            return
        path, _v = cat.image_path(*sel)
        label = cat.maps[sel[0]].label(sel[1])
        if not self.app._ask(_("Eigenes Bild löschen"), _("Eigenes Bild für „{map}“ löschen?", map=label) + f"\n\n{path}",
                             self.delete, parent=self.dlg):
            return
        try:
            os.remove(path)
        except OSError as e:
            self.msg.set(_("Löschen fehlgeschlagen: {error}", error=e))
            return
        self.app.picture_deleted(label)
        self.dlg.destroy()

    def open_dir(self):
        path = os.path.join(self.app.root_dir, mi.USER_DIR)
        if not open_folder(path):
            self.msg.set(path)
