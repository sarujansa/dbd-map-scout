"""1.10: the YouTube upload inside the program (Qt offscreen) – the settings card, the recordings tab's buttons and
right-click entries, the queue mirror, auto-upload of new clips and the index link when a video is done."""
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import obsrec, ytupload  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def app_root(tmp_path):
    if sys.platform == "win32":
        pytest.skip("Linux: the Windows job tests the native parts; the app would touch the system there")
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(ROOT, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    return tmp_path


def _recordings(folder, t):
    """One recording and one clip in a recordings folder of their own."""
    os.makedirs(os.path.join(folder, obsrec.CLIPS_DIR))
    with open(os.path.join(folder, "2026-10-17 21-40 Coal Tower – Nurse.mkv"), "wb") as fh:
        fh.write(b"\x1a\x45\xdf\xa3" + b"\0" * 2000)
    with open(os.path.join(folder, obsrec.CLIPS_DIR, "clip1.mp4"), "wb") as fh:
        fh.write(b"\0" * 1000)
    obsrec.save_index(folder, [obsrec.Recording(t=t, file="2026-10-17 21-40 Coal Tower – Nurse.mkv", map_id="coal",
                                                label="Coal Tower", role="killer", killer="The Nurse", end=t + 600,
                                                size=2004)])
    obsrec.save_clips(os.path.join(folder, obsrec.CLIPS_DIR),
                      [obsrec.Clip(file="clip1.mp4", t=t + 100, kind="instant", source=t, label="Coal Tower",
                                   role="killer", killer="The Nurse", seconds=30.0, size=1000)])


def test_the_app_queues_rounds_on_request_and_clips_by_themselves(app_root, tmp_path, monkeypatch):
    from fogscout.app import App
    folder = str(tmp_path / "rec")
    t = time.mktime((2026, 10, 17, 21, 40, 0, 0, 0, -1))
    _recordings(folder, t)
    (app_root / "settings.json").write_text(json.dumps({"welcome_seen": True, "rec_on": True, "rec_folder": folder}),
                                            encoding="utf-8")
    app = App(str(app_root), simulate=str(app_root / "sim"))
    added, links = [], []
    try:
        monkeypatch.setattr(app.recorder, "folder", lambda: folder)
        monkeypatch.setattr(app.recorder, "set_link", lambda kind, rel, vid: links.append((kind, rel, vid)))
        monkeypatch.setattr(app.youtube, "add", lambda job: added.append(job))
        # the settings card is there, every widget the page names was made
        for key in ("st.more.youtube", "st.more.yt_on", "st.more.yt_id", "st.more.yt_secret", "st.more.yt_privacy",
                    "st.more.yt_login", "st.more.yt_logout", "st.more.yt_status", "st.more.yt_text", "st.more.yt_file",
                    "st.more.yt_pl_on", "st.more.yt_pl_load", "st.more.yt_pl_clip", "st.more.yt_pl_round"):
            assert key in app._qt_reg, key
        # not connected: nothing can be uploaded, the menu entry is there but greyed
        app._rec_render(force=True)
        iid = next(iter(app._rec_rows))
        app.rec_table.selection_set(iid)
        app._rec_buttons()
        assert app.rec_yt_btn.cget("state") == "disabled"
        assert ("youtube", "Auf YouTube hochladen", False) in app._rec_menu_items()
        app._rec_youtube()
        assert added == []
        # connected (a refresh token is there): the round goes into the queue on request, with map/killer title
        app.youtube._refresh = "ref"
        app._rec_buttons()
        assert app.rec_yt_btn.cget("state") == "normal"
        app._rec_menu_act("youtube")
        assert len(added) == 1 and added[0].kind == "round" and added[0].rel == "2026-10-17 21-40 Coal Tower – Nurse.mkv"
        assert added[0].title == "Coal Tower – Nurse · 17.10.2026 21:40" and "10:00" in added[0].description
        assert app.rec_yt_btn.cget("state") == "disabled" and app._yt_mark(added[0].rel, "") == "…"   # queued once
        app._rec_render(force=True)
        assert app.rec_table.item(iid, "values")[8] == "…"
        # clips: by hand through the clips tab …
        app.clip_table.selection_set("clip1.mp4")
        app._clip_buttons()
        assert app.clip_yt_btn.cget("state") == "normal"
        assert ("youtube", "Auf YouTube hochladen", True) in app._clip_menu_items()
        app._clip_youtube()
        assert added[1].kind == "clip" and added[1].rel == "Clips/clip1.mp4" and added[1].title.startswith("Clip: Coal Tower – Nurse")
        # … and by themselves only with the box ticked: a new F8 clip, a still never
        app._rec_event("clip", {"ok": True, "file": "clip2.mp4", "seconds": 30, "label": "Coal Tower", "role": "killer",
                                "killer": "The Nurse", "source": t})
        assert len(added) == 2
        app.yt_on_var.set(True)
        app._youtube_setting()
        assert app.settings.get("youtube_on") is True
        app._rec_event("clip", {"ok": True, "file": "clip2.mp4", "seconds": 30, "label": "Coal Tower", "role": "killer",
                                "killer": "The Nurse", "source": t})
        assert added[2].rel == "Clips/clip2.mp4" and added[2].kind == "clip"
        app._yt_auto_clip("still.png", "Coal Tower", "killer", "The Nurse", t)
        app._yt_auto_clip("clip2.mp4", "Coal Tower", "killer", "The Nurse", t)        # already queued
        assert len(added) == 3
        # the thread says a video is done: the index gets the id, the log a line with the link
        app._youtube_event("done", {"rel": "Clips/clip1.mp4", "kind": "clip", "id": "vid1", "url": "https://youtu.be/vid1"})
        assert links == [("clip", "Clips/clip1.mp4", "vid1")]
        assert any("youtu.be/vid1" in str(e) for e in app._log_entries)
        # the queue the thread reports is kept in the settings and mirrored for the tables
        app._youtube_event("queue", [{"rel": "Clips/clip2.mp4", "kind": "clip"}])
        assert app.settings.get("youtube_queue") == [{"rel": "Clips/clip2.mp4", "kind": "clip"}]
        assert app._yt_queued == {"Clips/clip2.mp4"} and app._yt_mark("Clips/clip1.mp4", "") == ""
        app._youtube_event("quota", {"day": "2026-10-17", "used": 1600})
        assert app.settings.get("youtube_quota") == {"day": "2026-10-17", "used": 1600}
        # links of an uploaded clip: copy / open in the menu, no second upload
        app._clips_render(folder, obsrec.load_index(folder))
        c = app._clip_rows["clip1.mp4"]
        c.yt = "vid1"
        app.clip_table.selection_set("clip1.mp4")
        items = [i[0] for i in app._clip_menu_items() if i]
        assert "yt_link" in items and "yt_open" in items and "youtube" not in items
        copied = []
        app.root.clipboard_set = copied.append
        app._clip_menu_act("yt_link")
        assert copied == ["https://youtu.be/vid1"]
        # the thread learns about rounds (pause) and the folder once, not every tick
        app._yt_sent, app._yt_folder_at = None, 0.0
        sent = []
        monkeypatch.setattr(app.youtube, "set_paused", lambda p: sent.append(("pause", p)))
        monkeypatch.setattr(app.youtube, "set_folder", lambda f: sent.append(("folder", f)))
        app._youtube_tick()
        app._youtube_tick()
        assert sent == [("pause", False), ("folder", folder)]
        # 1.11.2: paused from the lobby on while the game window is there – not without the game
        app._yt_sent, app.game, app._queue = None, object(), {"state": "lobby"}
        app._youtube_tick()
        assert sent[-2:] == [("pause", True), ("folder", folder)]
        app._yt_sent, app._queue = None, {"state": "idle"}
        app._youtube_tick()
        assert sent[-2:] == [("pause", False), ("folder", folder)]
        app._yt_sent, app._queue, app.game = None, {"state": "search"}, None
        app._youtube_tick()
        assert sent[-2:] == [("pause", False), ("folder", folder)]
        # 1.10.1: the client file from Google fills both fields (the dialog starts in the download folder) …
        asked = []
        monkeypatch.setattr(app, "_qt_file", lambda mode, title, initial, cb, pattern="JSON (*.json)":
                            asked.append((mode, cb)))
        app._youtube_file()
        assert asked == [("open", app._youtube_file)]
        cfile = tmp_path / "client_secret_1234567890-abc.apps.googleusercontent.com.json"
        cfile.write_text(json.dumps({"installed": {"client_id": "1234567890-abc.apps.googleusercontent.com",
                                                   "client_secret": "GOCSPX-fromfile"}}), encoding="utf-8")
        app._youtube_file(str(cfile))
        assert app.yt_id_var.get() == "1234567890-abc.apps.googleusercontent.com"
        assert app.settings.get("youtube_client_id") == "1234567890-abc.apps.googleusercontent.com"
        assert ytupload.spotify.unprotect(app.settings.get("youtube_client_secret")) == "GOCSPX-fromfile"
        assert cfile.name in app.yt_status_var.get() and cfile.exists()
        assert not any("GOCSPX-fromfile" in str(e) for e in app._log_entries)
        # … a wrong file changes nothing and says why
        (tmp_path / "web.json").write_text(json.dumps({"web": {"client_id": "x", "client_secret": "y"}}), encoding="utf-8")
        app._youtube_file(str(tmp_path / "web.json"))
        assert app.yt_id_var.get() == "1234567890-abc.apps.googleusercontent.com"
        assert app._qt_question is not None and "Desktop-App" in app._qt_question[1]
        app._qt_question = None
        # 1.11: playlists – the thread lists them, the two choices fill, the pick is kept and handed on
        cfg = []
        monkeypatch.setattr(app.youtube, "configure", lambda *a, **kw: cfg.append((a, kw)))
        assert app.yt_pl_cbs["clip"].cget("values") == ["(keine)"] and app.yt_pl_vars["clip"].get() == "(keine)"
        app._youtube_event("playlists", {"ok": True, "why": "", "items": [["PL2", "Runden"], ["PL1", "Clips"], ["PL3", "Clips"]]})
        assert app.settings.get("youtube_playlist_names") == {"PL2": "Runden", "PL1": "Clips", "PL3": "Clips"}
        assert app.yt_pl_cbs["round"].cget("values") == ["(keine)", "Clips", "Clips (PL3)", "Runden"]
        assert "3 Playlists" in app.yt_status_var.get()
        app.yt_pl_var.set(True)
        app.yt_pl_vars["clip"].set("Clips")
        app.yt_pl_vars["round"].set("Runden")
        app._youtube_setting()
        assert app.settings.get("youtube_playlists") is True
        assert (app.settings.get("youtube_playlist_clip"), app.settings.get("youtube_playlist_round")) == ("PL1", "PL2")
        assert cfg[-1][1] == {"manage": True, "playlists": {"clip": "PL1", "round": "PL2"}}
        app._yt_playlists_fill()                                                    # re-filled: the pick stays
        assert app.yt_pl_vars["round"].get() == "Runden"
        app._youtube_event("playlist", {"rel": "Clips/clip1.mp4", "kind": "clip", "ok": True, "playlist": "PL1", "why": ""})
        assert any("clip1.mp4" in str(e) and "„Clips“" in str(e) for e in app._log_entries)
        app._youtube_event("playlist", {"rel": "r.mkv", "kind": "round", "ok": False, "playlist": "PL2",
                                        "why": "Berechtigung fehlt"})
        assert any("Berechtigung fehlt" in str(e) for e in app._log_entries)
        app._youtube_event("playlists", {"ok": False, "why": "Insufficient Permission", "items": []})
        assert any("Insufficient Permission" in str(e) for e in app._log_entries)
        assert app.settings.get("youtube_playlist_names") == {"PL2": "Runden", "PL1": "Clips", "PL3": "Clips"}
        # the secret is stored protected, never plain
        app.yt_secret_var.set("GOCSPX-abc")
        app._youtube_setting()
        assert app.settings.get("youtube_client_secret") != "GOCSPX-abc" and \
            ytupload.spotify.unprotect(app.settings.get("youtube_client_secret")) == "GOCSPX-abc"
        from fogscout import diagnose
        line = next(ln for ln in diagnose.collect(app).splitlines() if ln.startswith("YouTube:"))
        assert "GOCSPX" not in line and "Warteschlange=" in line
    finally:
        app.quit()
