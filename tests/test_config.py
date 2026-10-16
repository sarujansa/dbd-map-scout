from dbdmapscout import config


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
