"""Overlay layout memory (1.65): snapping, undo, one layout per window size – pure logic."""
from dbdmapscout import layoutmem


def _data():
    return {"overlay": {"anchor": "custom", "pos_x": 0.1, "pos_y": 0.2, "height": 0.36, "map_heights": {"a": 0.5},
                        "hud_scale": 1.0, "media_scale": 1.0, "media_pos": "custom", "media_xy": [1.0, 1.0],
                        "opacity": 0.85},
            "sysinfo": "right", "sysinfo_pos": [1.0, 0.0], "today_side": "right", "dark_mode": True}


def test_snapshot_and_apply_touch_only_the_layout():
    d = _data()
    snap = layoutmem.snapshot(d)
    assert "opacity" not in snap["overlay"] and "dark_mode" not in snap
    d["overlay"]["pos_x"], d["overlay"]["opacity"], d["sysinfo_pos"][0] = 0.9, 0.5, 0.3
    d["overlay"]["map_heights"]["a"] = 0.7
    layoutmem.apply(d, snap)
    assert d["overlay"]["pos_x"] == 0.1 and d["overlay"]["opacity"] == 0.5          # opacity is no layout
    assert d["sysinfo_pos"] == [1.0, 0.0] and d["overlay"]["map_heights"] == {"a": 0.5}
    d["overlay"]["media_xy"][0] = 0.0
    assert snap["overlay"]["media_xy"] == [1.0, 1.0]                                  # a copy, not shared


def test_undo_takes_one_gesture_back_at_a_time():
    u = layoutmem.UndoStack()
    a, b, c = {"x": 1}, {"x": 2}, {"x": 3}
    u.mark(a, 0.0)                      # drag starts at a …
    u.mark({"x": 1.5}, 0.2)             # … and goes on: the same step
    u.mark(b, 5.0)                      # a new change later: its own step
    assert len(u) == 2
    assert u.undo(c) == b and u.undo(b) == a and u.undo(a) is None
    u.mark(a, 10.0)
    assert u.undo(a) is None            # a state equal to now is skipped


def test_undo_keeps_a_bounded_history():
    u = layoutmem.UndoStack()
    for i in range(layoutmem.UNDO_KEPT + 20):
        u.mark({"x": i}, i * 10.0)
    assert len(u) == layoutmem.UNDO_KEPT


def test_snapping_to_the_closest_line():
    xs, ys = layoutmem.snap_lines((3440, 1440), 440, [("map", 20, 20, 400, 600), ("hud", 3100, 20, 300, 200)], "music")
    assert 440 in xs and 3000 in xs and 1720 in xs and 620 in ys
    x, y, lx, ly = layoutmem.snap_rect(1615, 700, 200, 100, xs, ys, 8)      # centre 1715 is 5 px from 1720
    assert (x, lx) == (1620, 1720) and y == 700 and ly is None
    x, y, lx, ly = layoutmem.snap_rect(3005, 225, 300, 100, xs, ys, 8)      # left edge near 3000, top near 220
    assert (x, lx, y, ly) == (3000, 3000, 220, 220)
    assert layoutmem.snap_rect(2000, 900, 50, 50, xs, ys, 8)[2:] == (None, None)    # nothing close: free


def test_layout_presets_only_touch_layout_keys_and_apply():
    """1.2.9 (user's pick 23): ready-made arrangements as partial layouts."""
    from dbdmapscout import layoutmem
    for name, preset in layoutmem.PRESETS.items():
        assert set(preset["overlay"]) <= set(layoutmem.OVERLAY_KEYS), name
        assert set(preset) - {"overlay"} <= set(layoutmem.TOP_KEYS), name
    data = {"overlay": {"anchor": "custom", "pos_x": 0.3, "height": 0.4, "media_pos": "custom"}, "sysinfo": "off"}
    layoutmem.apply(data, layoutmem.PRESETS["right"])
    assert data["overlay"]["anchor"] == "top-right" and data["sysinfo"] == "right"
    assert data["overlay"]["pos_x"] == 0.3 and data["overlay"]["height"] == 0.4      # untouched: size, own place
    assert data["overlay"]["media_pos"] == "under_today"
