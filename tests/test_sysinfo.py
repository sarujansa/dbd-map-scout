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
    assert sysinfo.parse_hwinfo(buf, now=1001) == {"cpu_temp": 63.5, "gpu_temp": 71.0}


def test_hwinfo_amd_fahrenheit_stale_and_dead():
    buf = _hwinfo([(1, "CPU (Tctl/Tdie)", "°F", 158.0)])
    assert round(sysinfo.parse_hwinfo(buf, now=1000)["cpu_temp"]) == 70
    assert sysinfo.parse_hwinfo(buf, now=1000 + sysinfo.HWINFO_STALE + 1) is None    # HWiNFO stopped polling
    assert sysinfo.parse_hwinfo(_hwinfo([], sig=struct.unpack("<I", b"DEAD")[0]), now=1000) is None
    assert sysinfo.parse_hwinfo(b"", now=1000) is None
    assert sysinfo.parse_hwinfo(_hwinfo([(1, "Motherboard", "°C", 40.0)]), now=1000) == {"cpu_temp": None,
                                                                                          "gpu_temp": None}


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
