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


def _hwinfo(readings, poll=1000, sig=0x53695748, sensors=()):
    """Shared memory as HWiNFO writes it: header, sensor section (names), then the readings. A reading is
    (type, label, unit, value) or (type, label, unit, value, sensor index)."""
    s_off, s_size = sysinfo.HWINFO_HEADER.size, 392                               # newer versions: utf8 name too
    r_off, r_size = s_off + s_size * len(sensors), sysinfo.HWINFO_READING.size + 144   # newer versions: utf8 fields
    head = sysinfo.HWINFO_HEADER.pack(sig, 2, 1, poll, s_off, s_size, len(sensors), r_off, r_size, len(readings))
    body = b""
    for i, name in enumerate(sensors):
        rec = sysinfo.HWINFO_SENSOR.pack(i, 0, name.encode("cp1252"))
        body += rec + b"\0" * (s_size - len(rec))
    for kind, label, unit, value, *sensor in readings:
        rec = sysinfo.HWINFO_READING.pack(kind, sensor[0] if sensor else 0, 0, label.encode("cp1252"), b"",
                                          unit.encode("cp1252"), value, 0, 0, 0)
        body += rec + b"\0" * (r_size - len(rec))
    return head + body


NONE = {"cpu_power": None, "core_max": None, "cpu_throttle": "", "fps": None}


def test_hwinfo_picks_cpu_package_and_gpu_temperature():
    buf = _hwinfo([(1, "Core Max", "°C", 70.0), (7, "CPU Package", "%", 50.0), (1, "CPU Package", "°C", 63.5),
                   (1, "GPU Temperature", "°C", 71.0)])
    assert sysinfo.parse_hwinfo(buf, now=1001) == {"cpu_temp": 63.5, "gpu_temp": 71.0, "gpu_hot": None,
                                                   "gpu_mem": None, **NONE}


def test_hwinfo_amd_fahrenheit_stale_and_dead():
    buf = _hwinfo([(1, "CPU (Tctl/Tdie)", "°F", 158.0)])
    assert round(sysinfo.parse_hwinfo(buf, now=1000)["cpu_temp"]) == 70
    assert sysinfo.parse_hwinfo(buf, now=1000 + sysinfo.HWINFO_STALE + 1) is None    # HWiNFO stopped polling
    assert sysinfo.parse_hwinfo(_hwinfo([], sig=struct.unpack("<I", b"DEAD")[0]), now=1000) is None
    assert sysinfo.parse_hwinfo(b"", now=1000) is None
    assert sysinfo.parse_hwinfo(_hwinfo([(1, "Motherboard", "°C", 40.0)]), now=1000) == {**dict.fromkeys(
        ("cpu_temp", "gpu_temp", "gpu_hot", "gpu_mem")), **NONE}


def test_hwinfo_cpu_power_busiest_thread_and_throttling():
    """1.2.1 (HWiNFO Pro, sharing stays on): CPU package power, the busiest thread and thermal throttling –
    Yes/No readings only from the CPU's sensors, power limits are no warning."""
    sensors = ("System: DESKTOP", "CPU [#0]: Intel Core i7-13700K", "CPU [#0]: Intel Core i7-13700K: DTS",
               "GPU [#0]: NVIDIA GeForce RTX 4070")
    rows = [(1, "CPU Package", "°C", 71.0, 2), (5, "CPU Package Power", "W", 118.4, 1),
            (7, "Max CPU/Thread Usage", "%", 97.0, 0), (7, "Core 0 T0 Usage", "%", 60.0, 1),
            (8, "Core Thermal Throttling", "", 0.0, 2), (8, "Package/Ring Power Limit Exceeded", "", 1.0, 2),
            (8, "Performance Limit - Thermal", "", 1.0, 3), (5, "GPU Power", "W", 210.0, 3)]
    hw = sysinfo.parse_hwinfo(_hwinfo(rows, sensors=sensors), now=1000)
    assert (hw["cpu_temp"], hw["cpu_power"], hw["core_max"], hw["cpu_throttle"]) == (71.0, 118.4, 97.0, "")
    rows[4] = (8, "Core Thermal Throttling", "", 1.0, 2)
    assert sysinfo.parse_hwinfo(_hwinfo(rows, sensors=sensors), now=1000)["cpu_throttle"] == "thermal"
    # AMD, no "Max CPU/Thread Usage": the busiest thread from the per-thread readings
    amd = ("CPU [#0]: AMD Ryzen 7 7800X3D", "CPU [#0]: AMD Ryzen 7 7800X3D: Enhanced")
    rows = [(7, "Core 0 T0 Usage", "%", 41.0, 0), (7, "Core 3 T1 Usage", "%", 88.5, 0), (7, "Total CPU Usage", "%", 30.0, 0),
            (5, "CPU PPT", "W", 64.0, 1), (8, "Thermal Throttling (HTC)", "", 1.0, 1)]
    hw = sysinfo.parse_hwinfo(_hwinfo(rows, sensors=amd), now=1000)
    assert (hw["cpu_power"], hw["core_max"], hw["cpu_throttle"]) == (64.0, 88.5, "thermal")


def test_cpu_throttling_shows_in_the_hud_and_counts_only_with_hwinfo():
    from dbdmapscout.sysinfo import MIN_SAMPLES, Snapshot, SysRecorder
    texts = ["".join(t for t, _ in r) for r in sysinfo.hud_rows(Snapshot(cpu_temp=95, cpu_throttle="thermal"))]
    assert "CPU DROSSELT (TEMP.)" in texts
    rec = SysRecorder()
    for i in range(MIN_SAMPLES + 2):
        rec.add(Snapshot(t=i + 1, gpu_temp=70, hwinfo=True, cpu_power=100 + i, core_max=90,
                         cpu_throttle="thermal" if i < 3 else ""))
    out = rec.summary()
    assert out["cpu_throttle_s"] == 3.0 and out["core_max"] == 90 and out["cpu_power_max"] == 100 + MIN_SAMPLES + 1
    rec = SysRecorder()                              # without HWiNFO nobody knows whether the CPU throttled
    for i in range(MIN_SAMPLES + 2):
        rec.add(Snapshot(t=i + 1, gpu_temp=70))
    assert "cpu_throttle_s" not in rec.summary()


def test_cpu_load_from_system_times():
    assert sysinfo.cpu_load(None, (1, 2, 3)) is None
    assert sysinfo.cpu_load((100, 200, 100), (150, 300, 100)) == 50.0       # kernel includes idle
    assert sysinfo.cpu_load((1, 1, 1), (1, 1, 1)) is None


def test_hud_rows_only_known_values_and_colours():
    s = sysinfo.Snapshot(cpu_load=45.2, gpu_temp=88, gpu_load=97, gpu_power=221.4, vram_used=6.12, vram_total=8.0,
                         ram_used=12.3, ram_total=31.9)
    rows = sysinfo.hud_rows(s)
    texts = ["".join(t for t, _ in r) for r in rows]
    assert texts == ["CPU 45 %", "GPU 88°C · 97 %", "VRAM 6.1 / 8 GB", "RAM 12.3 / 32 GB"]
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


def test_temperature_line_breaks_at_gaps():
    from dbdmapscout import trendchart
    pts = [(0, 70), None, (2, 72), (3, 75)]
    assert trendchart.segments(pts) == [((2, 72), (3, 75))]       # one segment c–d; "a" stands alone (gap)
    assert trendchart.segments([]) == [] and trendchart.segments([None, None]) == []



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


def test_statistics_know_cpu_throttling_only_from_rounds_with_hwinfo():
    from types import SimpleNamespace
    from dbdmapscout import history
    from dbdmapscout.app_stats import sys_tiles
    rounds = [SimpleNamespace(t=1, map="Coal Tower", sys={"gpu_temp": 70, "core_max": 92, "cpu_power": 110,
                                                          "cpu_power_max": 140, "cpu_throttle_s": 30.0}),
              SimpleNamespace(t=2, map="Coal Tower", sys={"gpu_temp": 72, "core_max": 88, "cpu_power": 100,
                                                          "cpu_throttle_s": 0.0}),
              SimpleNamespace(t=3, map="Badham", sys={"gpu_temp": 65})]              # no HWiNFO in that round
    avg = history.sys_average(rounds)
    assert (avg["cpu_known"], avg["cpu_throttle_rounds"], avg["cpu_throttle_s"], avg["core_max"]) == (2, 1, 30.0, 90)
    titles = {t.title: t.value for t in sys_tiles(avg)}
    assert titles["CPU gedrosselt"] == "1 von 2" and titles["Ø stärkster CPU-Kern"] == "90 %"
    by_map = {key: vals for key, _n, vals in history.sys_by(rounds, "map")}
    assert by_map["Coal Tower"]["cpu_throttle_s"] == 30.0 and "cpu_throttle_s" not in by_map["Badham"]
    peaks = {key: v for key, v, _r in history.sys_peaks(rounds)}
    assert peaks["cpu_power_max"] == 140 and peaks["cpu_throttle_s"] == 30.0
    assert "CPU gedrosselt" not in {t.title for t in sys_tiles(history.sys_average(rounds[2:]))}


def test_frame_rate_from_hwinfo_and_the_slowest_seconds_of_a_round():
    """1.2.2 (user's decision): FPS only from HWiNFO's shared memory (PresentMon / RivaTuner there); 0 = no 3D
    picture and does not count. FPS low = the slowest 1 % of the seconds, the worst round is the lowest."""
    from types import SimpleNamespace
    from dbdmapscout import history
    from dbdmapscout.sysinfo import MIN_SAMPLES, Snapshot, SysRecorder
    rows = [(8, "Framerate (Displayed)", "FPS", 140.0), (8, "Framerate (Presented)", "FPS", 143.5),
            (8, "Frame Time", "ms", 7.0)]
    assert sysinfo.parse_hwinfo(_hwinfo(rows), now=1000)["fps"] == 143.5
    assert sysinfo.parse_hwinfo(_hwinfo([(8, "Framerate", "FPS", 0.0)]), now=1000)["fps"] is None
    rec = SysRecorder()
    for i in range(200):
        rec.add(Snapshot(t=i + 1, fps=40.0 if i < 2 else 140.0 if i % 2 else None))
    out = rec.summary()
    assert out["fps_low"] == 40.0 and out["fps"] == 138.0          # zeros (None) are no samples
    assert MIN_SAMPLES <= 101
    rounds = [SimpleNamespace(t=1, map="A", sys={"fps": 140, "fps_low": 90}),
              SimpleNamespace(t=2, map="B", sys={"fps": 120, "fps_low": 55})]
    peaks = {key: (v, r.map) for key, v, r in history.sys_peaks(rounds)}
    assert peaks["fps_low"] == (55, "B")
    assert history.sys_average(rounds)["fps_low"] == 72.5
