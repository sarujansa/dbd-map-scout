"""Info texts shown when the mouse rests on a button or checkbox (Tk, no extra package).

``attach_all(root, lookup)`` walks the widget tree once after the UI is built and gives every
button/checkbox a tooltip whose text ``lookup(widget)`` returns (a string, a callable returning
one – for buttons whose label changes – or None). The texts themselves are in ``TIPS`` below,
keyed by the button label, so they stay in one place.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .i18n import _, source

DELAY_MS = 550
WRAP = 320

# German label -> German info text (buttons/checkboxes with a fixed label); both translated via i18n
TIPS = {
    # main window
    "Map-Namen oben einfügen (wie bei den mitgelieferten Karten)":
        "Schreibt den Map-Namen weiss mit Schatten über die Karte, im Stil der mitgelieferten Karten. Hat das Bild "
        "oben schon einen Namen, passiert nichts. Beim Drehen bleibt der Name aufrecht.",
    "Killer": "Diese Runde als Killer-Runde zählen (falls die Erkennung falsch lag).",
    "Survivor": "Diese Runde als Survivor-Runde zählen (falls die Erkennung falsch lag).",
    "Custom Game": "Diese Runde als Custom Game zählen – sie fliesst dann nicht in die Wartezeit ein.",
    "Drehen ↻": "Dreht die angezeigte Karte um 90° im Uhrzeigersinn (für jede Map gemerkt). Der Map-Name "
                "darüber bleibt aufrecht, die Zahlen in der Karte drehen sich mit.",
    "Scannen": "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen – falls die "
               "automatische Erkennung das Banner verpasst hat.",
    "Bild hinzufügen …": "Eigenes Kartenbild für diese unbekannte Map anlegen – Name und Realm sind schon "
                         "eingetragen, der Hintergrund wird automatisch entfernt.",
    "Zuordnen …": "Der gelesene Name gehört zu einer vorhandenen Map (z. B. anders geschrieben)? Einmal "
                  "zuordnen – danach wird er automatisch erkannt.",
    "✕": "Hinweis ausblenden.",
    # maps tab
    "Kartenbild hinzufügen …": "Eigenes Bild für eine Map wählen: vorhandenes Bild ersetzen oder neue Map "
                               "anlegen. Rand und Hintergrund werden automatisch entfernt.",
    # overlay tab
    "Für diese Map zurücksetzen": "Entfernt eigene Grösse und Drehung der angezeigten Map – danach gilt wieder "
                                  "der Schieberegler für alle Maps.",
    "Zurücksetzen": "Position wieder auf „automatisch“ stellen (auf Ultrawide im linken schwarzen Rand).",
    "Karte im schwarzen Rand halten (Ultrawide: nie ins Spielbild ragen)":
        "Auf breiten Monitoren bleibt die Karte im schwarzen Balken, in dem sie liegt, und wird bei Bedarf "
        "verkleinert. Mitten über dem Spiel platziert gilt keine Begrenzung.",
    "Karte anzeigen (aus: nur Timer, Ort und Ping)": "Aus: Das Overlay zeigt nur Rundentimer, Serverregion und Ping – "
                                                     "ohne Karte. Erkennung, Rundenende und Statistik laufen wie "
                                                     "gewohnt.",
    "Nur zeigen, wenn DBD das aktive Fenster ist": "Karte ausblenden, solange ein anderes Fenster "
                                                   "(Browser, Discord …) im Vordergrund ist.",
    "Map-Namen über der Karte anzeigen": "Zusätzliche Namenszeile über der Karte – die meisten Kartenbilder "
                                        "tragen den Namen schon selbst.",
    "Rundentimer unter der Karte anzeigen": "Zeit seit dem Einblenden der Karte, gross unter der Karte.",
    "Verbundenen Server unter der Karte anzeigen (Tab Server)":
        "Region und Ping des Spielservers unter der Karte. Braucht „Verbundener Spielserver“ im Tab Server.",
    "Transparenter Rand um die Karte": "Aus: Karte liegt auf einem dunklen Rechteck – besser lesbar über hellen "
                                       "Spielszenen.",
    # detection tab
    "Map beim Match-Start automatisch erkennen": "Liest das Map-Banner am Match-Anfang und blendet die "
                                                 "passende Karte ein. Aus: Map nur von Hand wählen.",
    "Overlay ausblenden, sobald ich nicht mehr in der Runde bin":
        "Blendet die Karte nach der Runde aus (Ergebnisbildschirm, Lobby, Ladebildschirm, DBD beendet).",
    "Overlay pausieren, solange ein DBD-Menü offen ist":
        "Karte verschwindet, solange der Mauszeiger im Spiel sichtbar ist (ESC-Menü), und kommt danach "
        "wieder.",
    "Auch erkennen, wenn andere Fenster über DBD liegen":
        "Fensteraufnahme wie bei OBS: erkennt das Banner auch, wenn DBD verdeckt ist. Nur solange DBD im "
        "Hintergrund ist.",
    "Debug-Bilder speichern (Ordner debug/)": "Speichert gelesene Banner und verkleinerte Bilder der Runde – "
                                              "nur zur Fehlersuche, kostet Speicherplatz.",
    "Bildschirm jetzt scannen": "Sucht sofort auf dem ganzen Bildschirm nach einem Map- oder Realm-Namen.",
    "Diagnose kopieren": "Kopiert technische Infos (Fenster, Overlay, letzte Rundenende-Prüfungen) in die "
                         "Zwischenablage – zum Weitergeben bei Problemen.",
    # server tab
    "Anzeigen, mit welchem Server DBD verbunden ist":
        "Zeigt Region und Ping des Spielservers (liest nur Paketköpfe, nie Inhalte). Braucht "
        "Administratorrechte.",
    "Ping messen": "Misst den Ping zu allen AWS-Regionen (UDP-Beacon von Amazon GameLift).",
    "Auswahl anwenden": "Nur die angehakten Regionen erlauben – trägt die übrigen in die Windows-hosts-Datei "
                        "ein (fragt nach Administratorrechten).",
    "Alles freigeben": "Entfernt die Einträge des Programms aus der hosts-Datei – alle Regionen wieder "
                       "erlaubt.",
    # log tab
    "Leeren": "Log-Anzeige leeren (die Log-Datei bleibt).",
    "Log-Datei öffnen": "Öffnet dbdmapscout.log mit allen Details.",
    # settings tab
    "Dark Mode": "Dunkle oder helle Darstellung des Steuerfensters.",
    "Standard": "Alle Hotkeys auf die Voreinstellung zurücksetzen.",
    "Beim Minimieren in den Infobereich (neben der Uhr)":
        "Minimieren versteckt das Fenster im Infobereich; Doppelklick auf das Symbol holt es zurück.",
    "Mit Windows starten (im Infobereich, ohne Windows-Abfrage)":
        "Startet das Programm bei der Anmeldung im Infobereich. Nur als Administrator änderbar.",
    "Beim Start nach Updates suchen und installieren (GitHub)":
        "Holt beim Start über die Verknüpfung den neuen Stand von GitHub. Eigene Änderungen werden nie "
        "überschrieben.",
    "Jetzt nach Updates suchen": "Fragt GitHub, ob es eine neue Version gibt (nur bei diesem Klick). Installiert "
                                 "wird erst mit „Aktualisieren und neu starten“.",
    "Aktualisieren und neu starten": "Beendet das Programm und startet es über start.bat neu – dabei wird das "
                                     "Update installiert.",
    "Verlauf löschen": "Löscht alle gespeicherten Runden (Datei rounds.jsonl).",
    "Alle löschen": "Alle eigenen Map-Zuordnungen löschen (die Namen werden dann wieder als unbekannt "
                    "gemeldet).",
    "Programmordner öffnen": "Öffnet den Ordner des Programms im Explorer.",
    "Karten-Ordner öffnen": "Öffnet den Ordner mit den mitgelieferten Kartenbildern.",
    # dialogs
    "Bild wählen …": "PNG, JPG, WebP oder GIF auswählen – zum Beispiel ein Original mit Hintergrund.",
    "Bild einer vorhandenen Map ersetzen": "Dein Bild ersetzt das mitgelieferte Bild dieser Map (bzw. dieses "
                                           "Layouts). Löschen stellt das Original wieder her.",
    "Neue Map (fehlt im Programm)": "Legt eine neue Map an. Sie wird erkannt, wenn der Name so geschrieben ist "
                                    "wie im Map-Banner.",
    "Ordner öffnen": "Öffnet den Ordner user_maps mit deinen eigenen Kartenbildern.",
    "Eigenes Bild löschen": "Löscht dein Bild für die gewählte Map – danach gilt wieder das mitgelieferte.",
    "Speichern": "Bild umwandeln und speichern; die Karte wird sofort angezeigt.",
    "Abbrechen": "Schliessen, ohne etwas zu ändern.",
}
_PREFIX = [("Hintergrund entfernen", "Macht Dunkelblau (#282a42) und Graulila (#535781) der "
            "Community-Karten transparent, schneidet den gleichfarbigen Rand ab und bringt das Bild auf "
            "1280 px Höhe.")]


def tip_for_label(text: str):
    """Info text for a (translated) label – the table is keyed by the German label."""
    key = source(text)
    if key in TIPS:
        return _(TIPS[key])
    for prefix, tip in _PREFIX:
        if key.startswith(prefix):
            return _(tip)
    return None


class Tooltip:
    """Small borderless window next to the mouse after a short rest on ``widget``."""
    colours = ("#2b2d31", "#e3e5e8", "#3a3c42")            # bg, fg, border – set by the app (theme)

    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self._after = self._win = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")
        widget._dbdms_tip = self

    def _text(self):
        t = self.text() if callable(self.text) else self.text
        return t or ""

    def _schedule(self, _e=None):
        self._cancel()
        self._after = self.widget.after(DELAY_MS, self.show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def show(self):
        self._after = None
        text = self._text()
        if not text or self._win:
            return
        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        bg, fg, border = Tooltip.colours
        w = self._win = tk.Toplevel(self.widget)
        w.wm_overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(w, background=border, padx=1, pady=1)
        frame.pack()
        tk.Label(frame, text=text, justify="left", wraplength=WRAP, background=bg, foreground=fg,
                 font=("Segoe UI", 9), padx=8, pady=5).pack()
        w.update_idletasks()
        # keep it on the screen
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        tw, th = w.winfo_reqwidth(), w.winfo_reqheight()
        x = min(x, sw - tw - 4)
        if y + th > sh - 4:
            y = self.widget.winfo_rooty() - th - 6
        w.geometry(f"+{max(0, x)}+{max(0, y)}")

    def hide(self, _e=None):
        self._cancel()
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None


TIPPABLE = (ttk.Button, ttk.Checkbutton, ttk.Radiobutton)


def attach_all(root, lookup=None):
    """Tooltip for every button/checkbox below ``root`` that has none yet.
    ``lookup(widget)`` may return a text/callable for widgets not covered by the label table."""
    count = 0
    stack = [root]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if not isinstance(w, TIPPABLE) or getattr(w, "_dbdms_tip", None):
            continue
        text = lookup(w) if lookup else None
        if text is None:
            try:
                text = tip_for_label(str(w.cget("text")))
            except tk.TclError:
                text = None
        if text:
            Tooltip(w, text)
            count += 1
    return count


def missing(root):
    """Buttons/checkboxes without a tooltip (labels) – used by the test to keep the table complete."""
    out, stack = [], [root]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if isinstance(w, TIPPABLE) and not getattr(w, "_dbdms_tip", None):
            out.append(str(w.cget("text")))
    return out
