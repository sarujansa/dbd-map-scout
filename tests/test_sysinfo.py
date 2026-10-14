"""System values HUD: HWiNFO shared memory parsing, CPU load, rows, placement (pure logic)."""
import importlib.util
import struct
import sys

import numpy as np

if "tkinter" not in sys.modules and importlib.util.find_spec("tkinter") is None:   # headless CI: overlay_win32 imports Tk only for its fallback
    from unittest import mock
    sys.modules["tkinter"] = mock.MagicMock()

from dbdmapscout import layout, sysinfo  # noqa: E402
from dbdmapscout.overlay_win32 import render_hud  # noqa: E402


def _hwinfo(readings, poll=1000, sig=0x53695748):
    """Shared memory as HWiNFO writes it: header, no sensor section, then the readings."""
    r_off, r_size = sysinfo.HWINFO_HEADER.size, sysinfo.HWINFO_READING.size + 144   # newer versions: utf8 fields
    head = sysinfo.HWINFO_HEADER.pack(sig, 2, 1, poll, r_off, 264, 0, r_off, r_size, len(readings))
    body = b""
    for kind, label, unit, value in readings:
        rec = sysinfo.HWINFO_READING.pack(kind, 0, 0, label.encode("cp1252"), b"", unit.encode("cp1252"),
                                          value, 0, 0, 0)
        body += rec + b"\0" * (r_size - len(rec))
    return head + body


def test_hwinfo_picks_cpu_package_and_gpu_temperature():
    buf = _hwinfo([(1, "Core Max", "°C", 70.0), (7, "CPU Package", "%", 50.0), (1, "CPU Package", "°C", 63.5),
                   (1, "GPU Temperature", "°C", 71.0)])
    assert sysinfo.parse_hwinfo(buf, now=1001) == {"cpu_temp": 63.5, "gpu_temp": 71.0, "gpu_hot": None,
                                                   "gpu_mem": None}


def test_hwinfo_amd_fahrenheit_stale_and_dead():
    buf = _hwinfo([(1, "CPU (Tctl/Tdie)", "°F", 158.0)])
    assert round(sysinfo.parse_hwinfo(buf, now=1000)["cpu_temp"]) == 70
    assert sysinfo.parse_hwinfo(buf, now=1000 + sysinfo.HWINFO_STALE + 1) is None    # HWiNFO stopped polling
    assert sysinfo.parse_hwinfo(_hwinfo([], sig=struct.unpack("<I", b"DEAD")[0]), now=1000) is None
    assert sysinfo.parse_hwinfo(b"", now=1000) is None
    assert sysinfo.parse_hwinfo(_hwinfo([(1, "Motherboard", "°C", 40.0)]), now=1000) == dict.fromkeys(
        ("cpu_temp", "gpu_temp", "gpu_hot", "gpu_mem"))


def test_cpu_load_from_system_times():
    assert sysinfo.cpu_load(None, (1, 2, 3)) is None
    assert sysinfo.cpu_load((100, 200, 100), (150, 300, 100)) == 50.0       # kernel includes idle
    assert sysinfo.cpu_load((1, 1, 1), (1, 1, 1)) is None


def test_hud_rows_only_known_values_and_colours():
    s = sysinfo.Snapshot(cpu_load=45.2, gpu_temp=88, gpu_load=97, gpu_power=221.4, vram_used=6.12, vram_total=8.0,
                         ram_used=12.3, ram_total=31.9)
    rows = sysinfo.hud_rows(s)
    texts = ["".join(t for t, _ in r) for r in rows]
    assert texts == ["CPU 45 %", "GPU 88°C · 97 % · 221 W", "VRAM 6.1 / 8 GB", "RAM 12.3 / 32 GB"]
    assert rows[1][1] == ("88°C", sysinfo.HOT)
    assert sysinfo.hud_rows(sysinfo.Snapshot()) == []
    assert sysinfo.temp_colour(60, sysinfo.CPU_WARM, sysinfo.CPU_HOT) == sysinfo.GOOD


def test_hud_fits_the_bar_and_map_moves_below():
    rows = sysinfo.hud_rows(sysinfo.Snapshot(cpu_load=45, cpu_temp=62, gpu_temp=71, gpu_load=97, gpu_power=220,
                                             vram_used=6.1, vram_total=8, ram_used=12.3, ram_total=31.9))
    pic = render_hud(rows, 1440)
    a = np.asarray(pic)
    assert pic.width < 440 - 2 * 17 and pic.height < 0.15 * 1440      # inside the bar, above fills_bars' band
    assert a[..., 3].max() > 200
    assert layout.hud_x("left", 0, 3440, 17, 300) == 17
    assert layout.hud_x("right", 0, 3440, 17, 300) == 3440 - 17 - 300
    assert layout.below_hud("left", "auto") and layout.below_hud("left", "top-left")
    assert not layout.below_hud("right", "auto") and layout.below_hud("right", "top-right")
    assert not layout.below_hud(None, "auto") and not layout.below_hud("left", "bottom-left")
    assert layout.below_hud("above", "auto") and layout.below_hud("above", "top-right")      # map moves down
    assert not layout.below_hud("above", "custom") and not layout.below_hud("above", "bottom-left")


def test_recorder_averages_and_maxima_per_round():
    from dbdmapscout.sysinfo import MIN_SAMPLES, Snapshot, SysRecorder
    rec = SysRecorder()
    for i in range(MIN_SAMPLES):
        snap = Snapshot(t=100 + i, gpu_temp=70 + i, gpu_load=90, cpu_temp=None if i else 60)
        rec.add(snap)
        rec.add(snap)                                       # the UI ticks faster than the readings: counted once
    s = rec.summary()
    assert s["gpu_temp"] == round(70 + (MIN_SAMPLES - 1) / 2, 1) and s["gpu_temp_max"] == 70 + MIN_SAMPLES - 1
    assert s["gpu_load"] == 90 and "cpu_temp" not in s       # one CPU reading is not enough
    assert SysRecorder().summary() is None


def test_round_keeps_system_values_and_stats(tmp_path):
    from dbdmapscout import history
    path = str(tmp_path / "rounds.jsonl")
    hot = {"gpu_temp": 78.0, "gpu_temp_max": 84.0, "cpu_temp": 66.0, "cpu_temp_max": 91.0, "gpu_power_max": 240.0}
    cool = {"gpu_temp": 62.0, "gpu_temp_max": 70.0, "gpu_load": 80.0}
    history.append(path, history.Round(t=1_700_000_000, seconds=600, map_id="a", map="Coal Tower", sys=hot,
                                       role="killer", killer="The Nurse"))
    history.append(path, history.Round(t=1_700_003_600, seconds=600, map_id="b", map="Badham", sys=cool))
    history.append(path, history.Round(t=1_700_007_200, seconds=600, map_id="b", map="Badham"))
    history.append_lost(path, 1_700_010_000, "Badham", "banner", sys={"gpu_temp": 1.0, "bad": "x"})
    rounds = history.load(path)
    assert rounds[0].sys == hot and rounds[2].sys is None
    assert history.load_lost_rounds(path)[0].sys == {"gpu_temp": 1.0}
    by_map = history.sys_by(rounds, "map")
    assert [(k, n) for k, n, _v in by_map] == [("Coal Tower", 1), ("Badham", 1)]       # hottest first
    assert history.sys_by(rounds, "killer") == [("The Nurse", 1, {k: v for k, v in hot.items()
                                                                  if k in history.SYS_COLUMNS})]
    peaks = {k: (v, r.map) for k, v, r in history.sys_peaks(rounds)}
    assert peaks["gpu_temp_max"] == (84.0, "Coal Tower") and peaks["cpu_temp_max"] == (91.0, "Coal Tower")
    avg = history.sys_average(rounds)
    assert avg["n"] == 2 and avg["gpu_temp"] == 70.0 and avg["cpu_temp"] == 66.0
    assert len(history.sys_by(rounds, "hour")) >= 1


def test_hotspot_memory_and_throttling():
    buf = _hwinfo([(1, "GPU Hot Spot Temperature", "°C", 92.0), (1, "GPU Memory Junction Temperature", "°C", 106.0)])
    hw = sysinfo.parse_hwinfo(buf, now=1000)
    assert hw["gpu_hot"] == 92.0 and hw["gpu_mem"] == 106.0
    assert sysinfo.throttle_kind(0x4) == ""                    # power cap under full load: normal, no warning
    assert sysinfo.throttle_kind(0x1 | 0x20) == "thermal" and sysinfo.throttle_kind(0x40) == "thermal"
    assert sysinfo.throttle_kind(0x8) == "hw" and sysinfo.throttle_kind(0x80) == "hw"
    rows = sysinfo.hud_rows(sysinfo.Snapshot(gpu_temp=80, gpu_hot=92.0, gpu_mem=106.0, throttle="thermal"))
    texts = ["".join(t for t, _ in r) for r in rows]
    assert texts == ["GPU 80°C", "HOTSPOT 92°C · MEM 106°C", "GPU DROSSELT (TEMP.)"]
    assert rows[1][1] == ("92°C", sysinfo.GOOD) and rows[1][-1] == ("106°C", sysinfo.HOT)


def test_recorder_counts_throttled_seconds_and_trend():
    from dbdmapscout import history
    rec = sysinfo.SysRecorder()
    for i in range(12):
        rec.add(sysinfo.Snapshot(t=100 + i, gpu_temp=70, gpu_hot=85 + i, throttle="thermal" if i < 3 else ""))
    s = rec.summary()
    assert s["throttle_s"] == 3.0 and s["gpu_hot_max"] == 96.0
    day = 1_700_000_000
    rounds = [history.Round(t=day, seconds=600, map_id="a", map="A", sys={"gpu_temp": 70.0, "gpu_temp_max": 75.0}),
              history.Round(t=day + 3 * 86400, seconds=600, map_id="a", map="A",
                            sys={"gpu_temp": 74.0, "gpu_temp_max": 80.0, "gpu_hot_max": 93.0, "throttle_s": 5.0}),
              history.Round(t=day + 3 * 86400 + 60, seconds=600, map_id="b", map="B", sys={"throttle_s": 0.0})]
    trend = history.sys_trend(rounds, "day")
    assert len(trend) == 4 and trend[1][1] == [] and trend[-1][1:] == ([74.0], [80.0], [93.0])   # empty days kept
    avg = history.sys_average(rounds)
    assert avg["throttle_rounds"] == 1 and avg["throttle_s"] == 5.0
    peaks = {k: v for k, v, _r in history.sys_peaks(rounds)}
    assert peaks["throttle_s"] == 5.0 and peaks["gpu_hot_max"] == 93.0
    by = dict((k, v) for k, _n, v in history.sys_by(rounds, "map"))
    assert by["A"]["throttle_s"] == 5.0 and by["B"]["throttle_s"] == 0.0     # summed, not averaged


def test_temperature_line_draws_points_and_breaks_at_gaps():
    from dbdmapscout import trendchart

    class Canvas:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def call(*args, **kw):
                self.calls.append((name, args, kw))
                return len(self.calls)
            return call

        def winfo_width(self):
            return 600

        def cget(self, key):
            return "#1e1f22"

    chart = trendchart.TrendChart.__new__(trendchart.TrendChart)
    chart.dark, chart.panels, chart.canvas, chart._hits, chart._hover = True, ("temp",), Canvas(), [], None
    chart.data = {"temp": {"title": "T", "kind": "line", "min": 60, "max": 80, "ticks": [(60, "60"), (80, "80")],
                           "bars": [(70, "a", "x"), (None, "b", ""), (72, "c", "y"), (75, "d", "z")],
                           "last": "75 °C", "empty": "-"}}
    chart._redraw()
    kinds = [c[0] for c in chart.canvas.calls]
    assert kinds.count("create_oval") == 3 and len(chart._hits) == 3
    lines = [c for c in chart.canvas.calls if c[0] == "create_line" and c[2].get("width") == 2]
    assert len(lines) == 1 and len(lines[0][1]) == 4              # one segment c–d; "a" stands alone (gap)
    ovals = [c[1] for c in chart.canvas.calls if c[0] == "create_oval"]
    assert ovals[0][1] > ovals[2][1]                              # 70 °C lower on screen than 75 °C


def test_info_beside_the_map_for_low_bars():
    from PIL import Image
    from dbdmapscout.overlay_win32 import add_info
    pic = Image.new("RGBA", (120, 160), (200, 200, 255, 255))
    below = add_info(pic, "1:42", "Frankfurt", 160, ping=24)
    beside = add_info(pic, "1:42", "Frankfurt", 160, ping=24, beside=True)
    assert below.height > pic.height and below.width < pic.width + 20      # under the map (normal)
    assert beside.height == pic.height and beside.width > pic.width + 40   # right of it: no extra height
    assert beside.getpixel((10, 80))[3] == 255 and beside.getpixel((beside.width - 1, 0))[3] == 0


def test_system_values_follow_the_map():
    from types import SimpleNamespace
    from dbdmapscout.app_sysinfo import SysInfo
    shown = []
    hud = SimpleNamespace(size=(300, 120), show_at=lambda x, y: shown.append((x, y)), hide=lambda: shown.append(None))
    app = SysInfo()
    app.hud, app.overlay, app.worker = hud, SimpleNamespace(shown=True), SimpleNamespace(hud_rect=None)
    app._hud_pending = "above"
    app._hud_follow_map((47, 300, 346, 500), 0, 0, 3440, 1440, 17)       # map in the left bar, room above it
    assert shown[-1] == (70, 300 - 8 - 120) and app.worker.hud_rect == (70, 172, 300, 120)
    app._hud_pending = "above"
    app._hud_follow_map((10, 5, 200, 400), 0, 0, 3440, 1440, 17)          # no room above: below the map
    assert shown[-1][1] == 5 + 400 + 8 and 8 <= shown[-1][0] <= 440 - 8 - 300   # and inside the left bar
    app._hud_pending = "above"
    app.overlay.shown = False
    app._hud_follow_map((10, 5, 200, 400), 0, 0, 3440, 1440, 17)          # map hidden: values hidden too
    assert shown[-1] is None and app.worker.hud_rect is None
    shown.clear()
    app._hud_follow_map((10, 5, 200, 400), 0, 0, 3440, 1440, 17)          # nothing pending: untouched
    assert shown == []

    app.overlay.shown = True
    app._hud_pending = "beside"                                          # narrow window: right of the map
    app._hud_follow_map((17, 1180, 281, 166), 0, 0, 1718, 1359, 16)
    assert shown[-1] == (17 + 281 + 24, 1180 + 23) and app.worker.hud_rect[1] == 1203
