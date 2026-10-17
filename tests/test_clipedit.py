"""Clip editor (1.5.1), the ffmpeg side: probing, single frames, the timeline's moments, cutting (stream copy and
frame exact), the sound stretch and the frame player – on a small clip ffmpeg generates itself. Skipped without
imageio-ffmpeg."""
import os
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dbdmapscout import clipedit, obsrec  # noqa: E402

FF = obsrec.ffmpeg_exe()
pytestmark = pytest.mark.skipif(FF is None, reason="imageio-ffmpeg not installed")


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("clip") / "2026-10-17 21-40 Coal Tower – Nurse.mkv")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=duration=12:size=320x180:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
                    "-c:v", "libx264", "-preset", "veryfast", "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", path], check=True, timeout=120)
    return path


def test_probe_reads_length_size_and_frame_rate(clip, tmp_path):
    info = clipedit.probe(clip, FF)
    assert info.ok and 11.5 <= info.duration <= 12.5 and (info.width, info.height) == (320, 180) and info.fps == 30
    assert not clipedit.probe(str(tmp_path / "nothing.mkv"), FF).ok
    assert clipedit.scaled(info, 90) == (160, 90) and clipedit.scaled(info, 540) == (320, 180)   # never upscaled
    assert clipedit.scaled(clipedit.Info(), 90)[1] == 90


def test_a_single_frame_comes_as_a_small_picture(clip):
    info = clipedit.probe(clip, FF)
    t0 = time.time()
    img = clipedit.frame_at(clip, 7.5, height=90, info=info, ffmpeg=FF)
    assert img is not None and img.size == (160, 90) and img.mode == "RGB"
    assert time.time() - t0 < 5
    assert clipedit.frame_at(clip, 7.5, info=clipedit.Info(), ffmpeg=FF) is None     # nothing known: no picture
    a, b = clipedit.frame_at(clip, 1.0, 90, info, FF), clipedit.frame_at(clip, 9.0, 90, info, FF)
    assert a.tobytes() != b.tobytes()                                              # testsrc moves: other moment


def test_timeline_moments_names_and_positions():
    assert clipedit.thumb_times(10.0, 4) == [1.25, 3.75, 6.25, 8.75]
    assert clipedit.fmt_pos(192.46) == "3:12.5" and clipedit.fmt_pos(0) == "0:00.0" and clipedit.fmt_pos(-1) == "0:00.0"
    name = clipedit.clip_name("D:\\DBD\\2026-10-17 21-40 Coal Tower – Nurse.mkv", 192.4, 220.0)
    assert name == "2026-10-17 21-40 Coal Tower – Nurse – Clip 3m12s-3m40s"
    assert "/" not in clipedit.clip_name("a/b:c.mkv", 0, 1)


def test_cutting_by_copy_and_frame_exact(clip, tmp_path):
    out = clipedit.unique_path(str(tmp_path), "clip", ".mp4")
    ok, why = clipedit.cut(clip, 4.2, 7.9, out, "copy", FF)
    assert ok and why == "" and os.path.getsize(out) > 1000
    d = clipedit.probe(out, FF).duration
    assert 3.4 <= d <= 5.2                                            # starts at the key frame before 4.2 (GOP 1 s)
    out2 = clipedit.unique_path(str(tmp_path), "clip", ".mp4")
    assert out2.endswith("clip (2).mp4")
    ok, why = clipedit.cut(clip, 4.2, 7.9, out2, "exact", FF)
    assert ok and 3.5 <= clipedit.probe(out2, FF).duration <= 3.9     # frame exact: 3.7 s
    ok, why = clipedit.cut(clip, 5.0, 4.0, str(tmp_path / "x.mp4"), "copy", FF)
    assert not ok and "Ende" in why
    ok, why = clipedit.cut(str(tmp_path / "missing.mkv"), 0, 1, str(tmp_path / "y.mp4"), "copy", FF)
    assert not ok and why and not os.path.exists(str(tmp_path / "y.mp4"))
    ok, why = clipedit.cut(clip, 0, 1, str(tmp_path / "z.mp4"), "copy", FF, run=lambda a: (1, b"boom"))
    assert not ok and why == "boom"


def test_the_sound_stretch_is_a_wav(clip):
    wav = clipedit.sound_wav(clip, 2.0, 4.0, FF)
    try:
        assert wav and os.path.getsize(wav) > 44100 * 2 * 2 * 1.9 and open(wav, "rb").read(4) == b"RIFF"
    finally:
        if wav:
            os.remove(wav)
    assert clipedit.sound_wav(clip, 4.0, 2.0, FF) is None


def test_the_frame_player_streams_frames_at_the_files_pace_and_stops(clip):
    info = clipedit.probe(clip, FF)
    got, ended = [], threading.Event()
    pl = clipedit.FramePlayer(clip, 10.0, info, lambda t, img: got.append((t, img.size)), ended.set, height=90, ffmpeg=FF)
    t0 = time.monotonic()
    pl.start()
    assert ended.wait(10)
    took = time.monotonic() - t0
    assert got and got[0][1] == (160, 90) and abs(got[0][0] - 10.0) < 0.05 and got[-1][0] <= 12.1
    assert 1.5 <= took <= 4.0                                         # ~2 s of film took ~2 s
    # a stretch with an end, stopped early
    got, ended = [], threading.Event()
    pl = clipedit.FramePlayer(clip, 1.0, info, lambda t, img: got.append(t), ended.set, end=8.0, height=90, ffmpeg=FF)
    pl.start()
    time.sleep(0.6)
    pl.stop()
    assert ended.wait(5) and got and got[-1] < 3.0


def test_the_clip_window_shows_frames_cuts_at_the_marks_and_saves(clip, tmp_path):
    """1.5.1: the editor offscreen – thumbnails and a preview picture arrive from the threads, the range follows
    the first mark, I/O set start/end, the clip is written into "Clips" and reported."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)     # platform: conftest (offscreen on Linux only –
    # setting it here too made the Win32 window tests after this file run offscreen on Windows CI)
    from PySide6.QtWidgets import QApplication
    from dbdmapscout import qt_clip
    app = QApplication.instance() or QApplication([])
    saved, settings, logs = [], {}, []
    clips = str(tmp_path / "Clips")
    win = qt_clip.ClipWindow(clip, [8.0], clips, mode="copy", sound=False, on_saved=saved.append,
                             on_setting=lambda k, v: settings.__setitem__(k, v), log=lambda t, k="System": logs.append((t, k)))
    try:
        win.show()
        assert win.info.ok and win.timeline.marks == [8.0]
        assert (win.timeline.start, win.timeline.end) == (0.0, pytest.approx(min(win.info.duration, 18.0)))   # 20 s before … 10 s after
        deadline = time.time() + 15
        while time.time() < deadline and (len(win.timeline.thumbs) < clipedit.THUMBS or win.preview.pixmap().isNull()):
            app.processEvents()
            time.sleep(0.02)
        assert len(win.timeline.thumbs) == clipedit.THUMBS and not win.preview.pixmap().isNull()
        win.goto(3.0)
        win.set_start()
        win.goto(6.5)
        win.set_end()
        assert (win.timeline.start, win.timeline.end) == (3.0, 6.5) and "3.5 s" in win.range_label.text()
        assert win.name_edit.text().endswith("Clip 0m03s-0m06s")
        win.next_mark()
        assert win.timeline.pos == 8.0
        win.mode_box.setCurrentIndex(1)
        assert settings == {"clip_mode": "exact"}
        win.mode_box.setCurrentIndex(0)
        win.save()
        deadline = time.time() + 30
        while time.time() < deadline and not saved:
            app.processEvents()
            time.sleep(0.02)
        assert saved and saved[0].startswith(clips) and saved[0].endswith(".mp4") and os.path.getsize(saved[0]) > 1000
        assert "Gespeichert" in win.status.text() and logs and logs[-1][1] == "System"
        # playback: frames come, the playhead moves, pause stops it
        win.goto(1.0)
        win.toggle_play()
        assert win.playing and win.player is not None
        deadline = time.time() + 5
        while time.time() < deadline and win.timeline.pos < 1.3:
            app.processEvents()
            time.sleep(0.02)
        assert win.timeline.pos >= 1.3
        win.toggle_play()
        assert not win.playing and win.player is None
    finally:
        win.close()
        app.processEvents()


def test_the_discord_plan_fits_the_size_and_drops_resolution_when_room_is_short():
    info = clipedit.Info(duration=600, width=2560, height=1440, fps=60.0)
    kbps, h, fps = clipedit.discord_plan(30, 10, info)               # 30 s in 10 MB: ~2.3 Mbit/s
    assert 2000 <= kbps < 2500 and (h, fps) == (720, 30.0)
    assert (kbps + clipedit.AUDIO_KBPS) * 30 / 8 / 1024 < 10          # fits with room to spare
    assert clipedit.discord_plan(30, 500, info)[1:] == (1080, 60.0)   # Nitro: full HD, 60 fps
    assert clipedit.discord_plan(120, 10, info)[1] == 360             # two minutes in 10 MB: small picture
    small = clipedit.Info(duration=60, width=640, height=360, fps=24.0)
    assert clipedit.discord_plan(10, 500, small)[1:] == (360, 24.0)   # never bigger than the recording


def test_a_discord_cut_stays_under_its_target(clip, tmp_path):
    out = str(tmp_path / "d.mp4")
    ok, why = clipedit.cut(clip, 1.0, 9.0, out, "discord", target_mb=1, info=clipedit.probe(clip))
    assert ok, why
    assert os.path.getsize(out) < 1024 * 1024 and clipedit.probe(out).height <= 360


def test_the_clip_window_offers_discord_and_plays_just_the_clip(clip, tmp_path):
    """1.6.1: the format list has "Für Discord" with a target size (remembered), the size line says what comes
    out, "Clip ansehen" plays the clip and lands on its start again, the saved clip can be shown."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QApplication
    from dbdmapscout import qt_clip
    app = QApplication.instance() or QApplication([])
    saved, settings = [], {}
    win = qt_clip.ClipWindow(clip, [], str(tmp_path / "Clips"), mode="discord", sound=False, on_saved=saved.append,
                             on_setting=lambda k, v: settings.__setitem__(k, v), target_mb=25)
    try:
        win.show()
        assert win.mode_box.currentData() == "discord" and not win.target_box.isHidden()
        assert win.target_box.currentData() == 25 and "unter 25 MB" in win.size_label.text()
        win.target_box.setCurrentIndex(0)
        assert settings == {"clip_target_mb": 10} and "unter 10 MB" in win.size_label.text()
        win.mode_box.setCurrentIndex(0)
        assert win.target_box.isHidden() and "MB" in win.size_label.text()
        win.goto(2.0)
        win.set_start()
        win.goto(3.0)
        win.set_end()
        win.watch_clip()
        assert win.playing and win.timeline.pos == 2.0
        deadline = time.time() + 10
        while time.time() < deadline and win.playing:
            app.processEvents()
            time.sleep(0.02)
        assert not win.playing and win.timeline.pos == 2.0             # back at the clip's start
        assert not win.show_btn.isEnabled()
        win.save()
        deadline = time.time() + 30
        while time.time() < deadline and not saved:
            app.processEvents()
            time.sleep(0.02)
        assert saved and win.show_btn.isEnabled() and "MB)" in win.status.text()
    finally:
        win.close()
        app.processEvents()


def test_the_whole_strip_comes_from_one_ffmpeg_run(clip):
    """1.7.1 (user: the strip loaded slowly): thumb_strip streams every picture of the strip from a single
    key-frame-only run, in order and at the strip size; a stop ends it early without a hanging process."""
    info = clipedit.probe(clip, FF)
    times = clipedit.thumb_times(info.duration, clipedit.THUMBS)
    t0 = time.time()
    got = list(clipedit.thumb_strip(clip, times, 54, info, FF))
    assert [i for i, _img in got] == list(range(clipedit.THUMBS))
    assert all(img.size == (96, 54) and img.mode == "RGB" for _i, img in got)
    assert time.time() - t0 < 10
    assert got[0][1].tobytes() != got[-1][1].tobytes()            # key frames every second: the picture moves
    assert list(clipedit.thumb_strip(clip, times[:1], 54, info, FF)) == []       # one moment: nothing to space
    stopped = list(clipedit.thumb_strip(clip, times, 54, info, FF, stop=lambda: True))
    assert stopped == []
