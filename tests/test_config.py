import json

from fogscout import config


def test_a_broken_settings_file_is_kept_and_never_overwritten_with_defaults(tmp_path):
    """1.8.38 (QA audit): a file that could not be read gave the defaults – and the next save replaced the user's
    hotkeys, layouts and OBS password with them."""
    path = tmp_path / "settings.json"
    path.write_text('{"overlay": {"height": 0.7}, "hotkeys": ', encoding="utf-8")       # cut off
    s = config.Settings(str(path))
    assert s.load_error and s["overlay"]["height"] == config.DEFAULTS["overlay"]["height"]
    assert (tmp_path / "settings.json.broken").read_text(encoding="utf-8").startswith('{"overlay"')
    s.save()                                                                    # the copy stays as it was
    assert (tmp_path / "settings.json.broken").read_text(encoding="utf-8").endswith('"hotkeys": ')


def test_odd_values_in_the_settings_file_do_not_stop_the_start(tmp_path):
    """1.8.38: a string version raised TypeError (the program did not start), "overlay": null left None behind."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"settings_version": "8", "overlay": None, "sysinfo": "left"}), encoding="utf-8")
    s = config.Settings(str(path))
    assert not s.load_error and s["sysinfo"] == "left"
    assert s["overlay"] == config.DEFAULTS["overlay"] and s["settings_version"] == config.SETTINGS_VERSION
    path.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert config.Settings(str(path)).load_error                            # no object at all: defaults, kept aside
    path.write_text(json.dumps({"settings_version": 2, "overlay": {"custom_x": None}}), encoding="utf-8")
    s = config.Settings(str(path))
    assert s.load_error and isinstance(s["overlay"], dict)                  # a broken migration: nothing half-merged


def test_the_backup_leaves_out_the_obs_password_and_the_spotify_token(tmp_path):
    """1.8.38: backups get shared and synced – the OBS password (plain text) and the token stay on this PC."""
    data = dict(config.DEFAULTS, rec_password="hunter2", spotify_token="dpapi:AAAA", sysinfo="left")
    out = tmp_path / "backup.json"
    config.export_settings(data, str(out))
    text = out.read_text(encoding="utf-8")
    assert "hunter2" not in text and "dpapi:AAAA" not in text and '"sysinfo": "left"' in text
    back = config.read_backup(str(out), {"rec_password": "mine", "spotify_token": "dpapi:MINE"})
    assert back["rec_password"] == "mine" and back["spotify_token"] == "dpapi:MINE"


def test_reset_data_keeps_only_the_pc_specific_values():
    """1.2.19: "Alle Einstellungen zurücksetzen" – defaults, the PC-specific keys and welcome_seen stay."""
    current = {"overlay": {"anchor": "custom", "height": 0.7}, "sysinfo": "left", "qt_geometry": "AAAA",
               "setup_version": 3, "setup_root": "C:/x", "official_dir": "D:/dl", "welcome_seen": True,
               "layouts": {"3440x1440": {}}, "layout_key": "3440x1440", "hotkeys": {"toggle_overlay": "ctrl+alt+q"}}
    data = config.reset_data(current)
    assert data["overlay"]["anchor"] == config.DEFAULTS["overlay"]["anchor"] and data["sysinfo"] == config.DEFAULTS["sysinfo"]
    assert data["hotkeys"] == config.DEFAULTS["hotkeys"]
    assert (data["qt_geometry"], data["setup_version"], data["setup_root"], data["official_dir"]) == ("AAAA", 3, "C:/x", "D:/dl")
    assert data["welcome_seen"] is True and data.get("layouts", {}) == config.DEFAULTS.get("layouts", {})
    assert config.reset_data({}).get("welcome_seen") in (None, False)


def test_old_settings_forget_the_detection_page(tmp_path):
    """1.8.78: the page "Erkennung" is gone – a saved navigation/card/tab order that names it is cleaned once."""
    import json
    from fogscout.config import Settings, SETTINGS_VERSION
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 9, "nav_order": ["log", "detect", "overview"],
                             "card_order": {"detect": {}, "settings": {"a": ["x"]}},
                             "tab_order": {"detect": {}, "overlay": {"t": ["a"]}}, "hotkeys": {}}))
    s = Settings(str(p))
    assert s["nav_order"] == ["log", "overview"] and s["card_order"] == {"settings": {"a": ["x"]}}
    assert s["tab_order"] == {"overlay": {"t": ["a"]}} and s["settings_version"] == SETTINGS_VERSION


def test_the_old_instant_clip_sound_default_follows_the_new_one(tmp_path):
    """1.11.4 (user: "es soll auch Discord-Sound etc. beinhalten in Clips"): F8 clips keep every source by default;
    a settings file still on the 1.8.6 default (game + microphone) is moved along once, an own choice stays."""
    import json
    from fogscout import obsrec
    from fogscout.config import DEFAULTS, Settings, SETTINGS_VERSION
    assert DEFAULTS["rec_clip_sources"] == list(obsrec.SOURCES) == ["dbd", "discord", "mic", "other"]
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 10, "rec_clip_sources": ["dbd", "mic"], "hotkeys": {}}))
    s = Settings(str(p))
    assert s["rec_clip_sources"] == ["dbd", "discord", "mic", "other"] and s["settings_version"] == SETTINGS_VERSION
    p.write_text(json.dumps({"settings_version": 10, "rec_clip_sources": ["dbd"], "hotkeys": {}}))
    assert Settings(str(p))["rec_clip_sources"] == ["dbd"]
    p.write_text(json.dumps({"settings_version": 11, "rec_clip_sources": ["dbd", "mic"], "hotkeys": {}}))
    assert Settings(str(p))["rec_clip_sources"] == ["dbd", "mic"]                 # chosen after 1.11.4: kept
