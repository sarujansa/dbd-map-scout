"""Tab „Server“: region choice via the hosts file, pings, connected game server.

Mixin of App (app.py) – the methods use App's attributes; split out of app.py unchanged."""
from __future__ import annotations

import threading
import time
from . import connwatch, regions
from . import uimodel as ui
from .capture import IS_WIN
from .i18n import _


class ServerTab:
    # ----------------------------------------------------------- tab: server
    def _tab_server(self):
        outer, f = self._scroll_tab()
        conn = ui.LabelFrame(f, text=_("Verbundener Spielserver"), padding=8)
        conn.pack(fill="x")
        self.conn_show_var = ui.BooleanVar(value=bool(self.settings.get("show_connection")))
        ui.Checkbutton(conn, text=_("Anzeigen, mit welchem Server DBD verbunden ist"),
                        variable=self.conn_show_var, command=self._conn_toggled).pack(anchor="w")
        self.conn_tab_var = ui.StringVar(value="")
        ui.Label(conn, textvariable=self.conn_tab_var, style="Big.TLabel", wraplength=540).pack(anchor="w", pady=(2, 0))
        ui.Label(conn, text=_("Zeigt Region und Ping des Spielservers, auch im Overlay (braucht "
                               "Administratorrechte)."), style="Dim.TLabel", wraplength=540).pack(anchor="w")

        reg = ui.LabelFrame(f, text=_("Serverregionen"), padding=8)
        reg.pack(fill="x", pady=(8, 0))
        ui.Label(reg, text=_("DBD sucht Matches nur in den angehakten Regionen (über die Windows-hosts-Datei, "
                              "das Spiel wird nicht verändert). Nach „Auswahl anwenden“ DBD neu starten."),
                  style="Dim.TLabel", wraplength=430).pack(anchor="w")
        f_outer, f = f, reg
        row = ui.Frame(f)
        row.pack(fill="x", pady=(6, 0))          # above the list (1.61): one sees them without scrolling
        self.srv_btns = [ui.Button(row, text=_("Ping messen"), command=self.srv_measure),
                         ui.Button(row, text=_("Auswahl anwenden"), command=self.srv_apply),
                         ui.Button(row, text=_("Alles freigeben"), command=self.srv_release)]
        self.srv_btns[0].pack(side="left")
        self.srv_btns[1].pack(side="left", padx=6)
        self.srv_btns[2].pack(side="left")
        self.srv_summary = ui.StringVar(value="")        # 1.2.19: "3 von 15 Regionen freigegeben"
        ui.Label(f, textvariable=self.srv_summary, style="Big.TLabel").pack(anchor="w", pady=(6, 0))
        self.srv_status = ui.StringVar(value="")
        ui.Label(f, textvariable=self.srv_status, wraplength=430).pack(anchor="w", pady=(2, 0))
        tf = ui.Frame(f)
        tf.pack(fill="x", pady=(6, 0))
        t = ui.Treeview(tf, columns=("ping", "state"), show="tree headings", height=11, selectmode="browse")
        t.heading("#0", text=_("Region"), anchor="w")
        t.heading("ping", text="Ping", anchor="e")
        t.heading("state", text=_("hosts-Datei"), anchor="w")
        t.column("#0", width=215, stretch=True)
        t.column("ping", width=78, anchor="e", stretch=False)
        t.column("state", width=120, anchor="w", stretch=False)
        t.pack(side="left", fill="x")             # as tall as its rows, no empty box below (1.58.1)
        self.srv_tree = t
        t._dbdms_click = self._srv_toggle         # a click toggles the region (also from the Qt window)
        saved = self.settings.get("regions_selected")
        self.srv_sel = set(saved) if saved else {c for c, _, _ in regions.REGIONS}
        for g in regions.GROUPS:
            t.insert("", "end", iid=f"g:{g}", text=_(g), open=True, tags=("group",))
            for code, name, grp in regions.REGIONS:
                if grp == g:
                    t.insert(f"g:{g}", "end", iid=f"r:{code}", text=_(name), values=("", ""))
        ui.Label(f_outer, text=_("Mit VPN unzuverlässig. Region-Tools sind von BHVR weder erlaubt noch verboten – "
                                  "auf eigene Verantwortung."), style="Dim.TLabel", wraplength=440).pack(
            anchor="w", pady=(6, 0))
        self._srv_render()
        return outer

    # ---------------------------------------------------------- connected server
    def _conn_toggled(self):
        on = bool(self.conn_show_var.get())
        self.settings.set("show_connection", on)
        self._save_soon()
        if on:
            self._conn_start()
        else:
            self.conn.stop()
            self._conn_idle.reset()
            self._log(_("Anzeige des Spielservers beendet."), "System")
            self._conn_tick(force=True)

    def _conn_start(self):
        if self.conn.running or self._conn_busy:
            return
        self._conn_busy = True
        self.conn_tab_var.set(_("Warte auf Windows (Administratorrechte) …"))
        hwnd = self._main_hwnd()

        def work():
            try:
                err = self.conn.start(hwnd)
            except Exception as e:
                err = {"error": f"{type(e).__name__}: {e}"}
            self.events.put(("conn_started", err))
        threading.Thread(target=work, daemon=True, name="netwatch").start()

    def _conn_started(self, err):
        self._conn_busy = False
        if not err and not self.conn_show_var.get():      # unticked while Windows was asking
            self.conn.stop()
        elif err:
            self._log(_("Spielserver-Anzeige: {error}", error=err.get("error") or _("Fehler")), "Fehler")
            self.conn.error = err.get("error", "")
            if err.get("cancelled") or not IS_WIN:
                self.conn_show_var.set(False)
                self.settings.set("show_connection", False)
                self._save_soon()
                self.conn.error = ""
        else:
            self._log(_("Spielserver-Anzeige läuft (liest nur Paketköpfe, keine Inhalte)."), "System")
        self._conn_tick(force=True)

    def _conn_tick(self, force=False):
        now = time.time()
        if not force and now < self._conn_next:
            return
        self._conn_next = now + 1.0
        if self.conn_show_var.get() and not self._conn_busy:
            act = self._conn_idle.update(now, self.game is not None, self.conn.running, self.conn.in_process)
            if act == "pause":
                self.conn.stop()
                self._log(_("Spielserver-Anzeige pausiert – DBD läuft nicht (startet automatisch mit DBD)."), "System")
            elif act == "resume" and not self.conn.running:
                self._conn_start()
        was_running = self.conn.running
        self.conn.poll(now)
        if was_running and not self.conn.running and self.conn.error:
            self._log(_("Spielserver-Anzeige beendet: {error}", error=self.conn.error), "Fehler")
        srv = self.conn.server
        if srv and self._hist is not None and srv["region"] != connwatch.UNKNOWN:
            self._hist["region"] = srv["region"]           # region only, never the address
            if self.conn.ping_ms is not None:
                self._hist.setdefault("pings", []).append(float(self.conn.ping_ms))
        key = (srv["ip"], srv["region"]) if srv else None
        if key != self._conn_last:
            self._conn_last = key
            if srv:
                note = "" if srv["region"] in self.srv_sel or srv["region"] == connwatch.UNKNOWN \
                    else _(" – nicht in deiner Regionsauswahl")
                # region only: the log file is kept on disk, the server address is shown live in the window only
                self._log(_("Verbunden mit Spielserver: {region}{note}.", region=connwatch.region_name(srv["region"]),
                            note=note), "System")
        text = self.conn.text()
        if self._conn_busy:
            text = _("Warte auf Windows (Administratorrechte) …")
        elif self._conn_idle.paused:
            text = _("pausiert, bis DBD läuft")
        # 1.8.75: off = nothing here (the unticked box says it; the bold "Aus" read like a heading)
        self.conn_tab_var.set(_("Verbunden mit: {server}", server=text) if text and self.conn.running else text)
        show = self.settings["overlay"].get("show_server", True)
        self.overlay.set_server(connwatch.region_name(srv["region"]) if srv and show else "",
                                self.conn.ping_ms)

    def _srv_toggle(self, iid):
        if not iid or self._srv_busy:
            return
        if iid.startswith("g:"):
            codes = [c for c, _, g in regions.REGIONS if g == iid[2:]]
            if all(c in self.srv_sel for c in codes):
                self.srv_sel.difference_update(codes)
            else:
                self.srv_sel.update(codes)
        elif iid.startswith("r:"):
            self.srv_sel ^= {iid[2:]}
        self.settings.set("regions_selected", sorted(self.srv_sel))
        self._save_soon()
        self._srv_render()

    def _srv_render(self):
        t = self.srv_tree
        states = self.srv_state.get("regions", {})
        for g in regions.GROUPS:
            codes = [c for c, _, grp in regions.REGIONS if grp == g]
            n = sum(c in self.srv_sel for c in codes)
            box = ui.CHECK_ON if n == len(codes) else ui.CHECK_OFF if n == 0 else ui.CHECK_PART
            t.item(f"g:{g}", text=_(g), tags=("group", box))
            for c in codes:
                p = self.srv_ping.get(c)
                ms = p.get("ms") if p else None
                ping = "…" if self._srv_busy and p is None else ("–" if ms is None else f"{ms:.0f} ms")
                tag = ("p_na" if ms is None else "p_good" if ms < 80 else "p_mid" if ms < 130 else "p_bad")
                state = states.get(c)
                t.item(f"r:{c}", text=_(regions.NAMES[c]), values=(ping, _(state) if state else "–"),   # 1.8.75: no "?"
                       tags=(tag, ui.CHECK_ON if c in self.srv_sel else ui.CHECK_OFF))

    def _srv_refresh(self, log_summary=False):
        """Read the hosts file (no administrator rights needed)."""
        self.srv_state = regions.current_state()
        st = self.srv_state
        if st.get("error"):
            self.srv_status.set(_("hosts-Datei nicht lesbar: {error}", error=st["error"]))
            self._srv_render()
            return
        rs = st["regions"]
        visible = [c for c, _, _ in regions.REGIONS]
        free = [c for c in visible if rs.get(c) == "frei"]
        self.srv_summary.set(_("{free} von {total} Regionen freigegeben", free=len(free), total=len(visible)))
        if st["own"] and not self.settings.get("regions_selected"):
            self.srv_sel = set(free)                          # show what is actually active
        if st["own"]:
            text = _("Aktiv: nur {regions} erlaubt.", regions=", ".join(_(regions.NAMES[c]) for c in free) or _("(keine)"))
        elif any(v != "frei" for v in rs.values()):
            text = _("Keine eigene Auswahl aktiv, aber andere Einträge sperren Regionen.")
        else:
            text = _("Keine Region gesperrt – DBD wählt selbst.")
        if st["foreign"]:
            who = "Make Your Choice" if st["myc"] else _("anderen Programmen")
            text += _(" Es gibt {n} Einträge von {who} für DBD-Server (werden beim Anwenden ersetzt).",
                      n=st["foreign"], who=who)
        self.srv_status.set(text)
        self._srv_render()
        if log_summary and (st["own"] or st["foreign"]):
            self._log(_("Serverregionen: {text}", text=text), "System")

    def srv_measure(self):
        if self._srv_busy:
            return
        self._srv_busy = True
        self.srv_ping = {}
        self._srv_render()
        self.srv_status.set(_("Messe Ping zu den Serverregionen …"))
        for b in self.srv_btns:
            b.state(["disabled"])

        def work():
            try:
                res = regions.measure_all()
            except Exception as e:  # pragma: no cover
                res = {"_error": str(e)}
            self.events.put(("srv_ping", res))
        threading.Thread(target=work, daemon=True, name="ping").start()

    def _srv_ping_done(self, res):
        self._srv_busy = False
        self._srv_last_ping = time.time()
        for b in self.srv_btns:
            b.state(["!disabled"])
        if "_error" in res:
            self._srv_render()
            self.srv_status.set(_("Ping fehlgeschlagen: {error}", error=res["_error"]))
            return
        self.srv_ping = res
        ok = {c: r["ms"] for c, r in res.items() if r.get("ms") is not None}
        self._srv_refresh()
        if ok:
            best = sorted(ok, key=ok.get)[:3]
            self.srv_status.set(self.srv_status.get() + "  " + _("Am schnellsten: {list}.", list=", ".join(
                f"{_(regions.NAMES[c])} {ok[c]:.0f} ms" for c in best)))
        else:
            self.srv_status.set(_("Keine Region hat geantwortet (Internet/Firewall/VPN?)."))

    def srv_apply(self):
        if self._srv_busy:
            return
        sel = [c for c, _, _ in regions.REGIONS if c in self.srv_sel]
        if not sel:
            self._inform(_("Serverregionen"), _("Bitte mindestens eine Region anhaken."))
            return
        if len(sel) == len(regions.REGIONS):
            self.srv_release()
            return
        names = ", ".join(_(regions.NAMES[c]) for c in sel)
        foreign = self.srv_state.get("foreign", 0)
        msg = _("Erlaubt bleiben: {names}.\n\nAlle anderen DBD-Serverregionen werden in der Windows-hosts-Datei "
                "gesperrt. Windows fragt gleich nach Administratorrechten.", names=names)
        if foreign:
            msg += "\n\n" + _("{n} vorhandene Einträge anderer Programme (z. B. Make Your Choice) für DBD-Server "
                                 "werden dabei entfernt.", n=foreign)
        msg += "\n\n" + _("Danach DBD neu starten, damit es wirkt.")
        if not self._ask(_("Serverregionen anwenden"), msg, self.srv_apply):
            return
        self._srv_run({"block": regions.block_list(sel), "allowed": sel, "remove_foreign": True},
                      _("Nur noch {names} erlaubt", names=names))

    def srv_release(self):
        if self._srv_busy:
            return
        st = self.srv_state
        if not st.get("own") and not st.get("foreign"):
            self.srv_status.set(_("Es ist nichts gesperrt."))
            return
        msg = (_("Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen (auch die von Make Your Choice)?")
               if st.get("myc") else _("Alle Sperren für DBD-Serverregionen aus der hosts-Datei entfernen?"))
        msg += "\n\n" + _("Windows fragt gleich nach Administratorrechten. Danach DBD neu starten.")
        if not self._ask(_("Serverregionen freigeben"), msg, self.srv_release):
            return
        self._srv_run({"block": [], "remove_foreign": True}, _("Alle Regionen freigegeben"))

    def _srv_run(self, job, label):
        self._srv_busy = True
        for b in self.srv_btns:
            b.state(["disabled"])
        self.srv_status.set(_("Warte auf Windows (Administratorrechte) …"))
        hwnd = self._main_hwnd()

        def work():
            try:
                res = regions.run_job(job, hwnd=hwnd)
            except Exception as e:
                res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self.events.put(("srv_job", res, label))
        threading.Thread(target=work, daemon=True, name="hosts").start()

    def _srv_job_done(self, res, label):
        self._srv_busy = False
        for b in self.srv_btns:
            b.state(["!disabled"])
        self._srv_refresh()
        if res.get("ok"):
            if res.get("changed", True):
                self._log(_("Serverregionen: {text}. DBD neu starten, damit es wirkt.", text=label), "System")
                self.srv_status.set(_("{text}. DBD jetzt neu starten.", text=label) + "  " + self.srv_status.get()
                                    + ("  " + _("DBD läuft gerade – die Änderung gilt erst nach einem Neustart von DBD.")
                                       if self.game is not None else ""))
            else:
                self.srv_status.set(_("Keine Änderung nötig.") + "  " + self.srv_status.get())
        else:
            err = res.get("error") or _("unbekannter Fehler")
            self._log(_("Serverregionen: {text}", text=err), "System" if res.get("cancelled") else "Fehler")
            self.srv_status.set(err)
