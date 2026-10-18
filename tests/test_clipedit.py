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


@pytest.fixture(scope="module")
def two_track(tmp_path_factory):
    """A 1.8.5 recording with two audio tracks – track 1 with sound, track 2 (all but Discord) silent."""
    path = str(tmp_path_factory.mktemp("clip2") / "2026-10-18 20-10 Ormond – Nurse.mkv")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=duration=6:size=320x180:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", path], check=True, timeout=120)
    return path


@pytest.fixture(scope="module")
def four_track(tmp_path_factory):
    """1.8.6: a recording as OBS writes it with the four tracks – 1 everything (loud), 2 game (loud, 440 Hz),
    3 Discord (quiet, −20 dB), 4 microphone (silent)."""
    path = str(tmp_path_factory.mktemp("clip4") / "2026-10-18 20-30 Ormond – Nurse.mkv")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=duration=6:size=320x180:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-f", "lavfi", "-i", "sine=frequency=880:duration=6",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", "[3:a]volume=0.1[q]",
                    "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "[q]", "-map", "4:a",
                    "-c:v", "libx264", "-preset", "veryfast", "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", path], check=True, timeout=120)
    return path


def _max_volume(path, track=None):
    """Loudest moment of an audio track in dB (ffmpeg volumedetect); silence reads about -91 dB."""
    pick = [] if track is None else ["-map", f"0:a:{track}"]
    p = subprocess.run([FF, "-hide_banner", "-i", path, *pick, "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
    import re
    m = re.search(rb"max_volume: (-?[\d.]+) dB", p.stderr)
    return float(m.group(1)) if m else None


def test_probe_reads_length_size_and_frame_rate(clip, tmp_path):
    info = clipedit.probe(clip, FF)
    assert info.ok and 11.5 <= info.duration <= 12.5 and (info.width, info.height) == (320, 180) and info.fps == 30
    assert info.audio_tracks == 1                                                   # 1.8.5
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


def test_a_clip_is_mixed_from_the_recordings_own_tracks(four_track, two_track, tmp_path):
    """1.8.6: ``mix`` picks and levels the sources from OBS's tracks – one source as it is stays a stream copy,
    a level or several sources re-encode only the sound (also with censor boxes and in the preview sound); a 1.8.5
    two-track file still gives all or all-but-Discord."""
    assert clipedit.probe(four_track, FF).audio_tracks == 4 and obsrec.audio_tracks(four_track, FF) == 4
    assert _max_volume(four_track, 1) > -20 and -45 < _max_volume(four_track, 2) < -30 and _max_volume(four_track, 3) < -80
    out = lambda n: str(tmp_path / f"{n}.mp4")                                 # noqa: E731
    ok, why = clipedit.cut(four_track, 1.0, 3.0, out("mic"), "copy", FF, mix={"dbd": 0, "discord": 0, "mic": 1.0})
    assert ok, why
    assert clipedit.probe(out("mic"), FF).audio_tracks == 1 and _max_volume(out("mic")) < -80      # microphone only: silent
    ok, why = clipedit.cut(four_track, 1.0, 3.0, out("disc"), "copy", FF, mix={"dbd": 0, "discord": 1.0, "mic": 0})
    assert ok, why
    assert -45 < _max_volume(out("disc")) < -30                                                     # Discord only, as recorded
    ok, why = clipedit.cut(four_track, 1.0, 3.0, out("half"), "copy", FF, mix={"dbd": 0.5, "discord": 0, "mic": 0})
    assert ok, why
    assert -27 < _max_volume(out("half")) < -21                                                     # the game at −6 dB
    ok, why = clipedit.cut(four_track, 1.0, 3.0, out("both"), "copy", FF, mix={"dbd": 1.0, "discord": 1.0, "mic": 1.0})
    assert ok, why
    assert clipedit.probe(out("both"), FF).audio_tracks == 1 and _max_volume(out("both")) > -20
    ok, why = clipedit.cut(four_track, 1.0, 3.0, out("none"), "copy", FF, mix={"dbd": 0, "discord": 0, "mic": 0})
    assert ok, why
    assert clipedit.probe(out("none"), FF).audio_tracks == 0                                        # no sound at all
    ok, why = clipedit.cut(four_track, 1.0, 2.0, out("exact"), "exact", FF, censor=[[0.1, 0.1, 0.3, 0.3]],
                           mix={"dbd": 0, "discord": 0, "mic": 1.0})
    assert ok, why
    assert clipedit.probe(out("exact"), FF).audio_tracks == 1 and _max_volume(out("exact")) < -80
    assert clipedit.sound_wav(four_track, 1.0, 2.0, FF, mix={"dbd": 0, "discord": 0, "mic": 0}, n_tracks=4) is None
    wav = clipedit.sound_wav(four_track, 1.0, 2.0, FF, mix={"dbd": 0, "discord": 1.0, "mic": 0}, n_tracks=4)
    try:
        assert wav and -45 < _max_volume(wav) < -30
    finally:
        if wav:
            os.remove(wav)
    ok, why = clipedit.cut(two_track, 1.0, 3.0, out("legacy"), "copy", FF, mix={"dbd": 1.0, "discord": 0})
    assert ok, why
    assert _max_volume(out("legacy")) < -80                                                         # 1.8.5 file: track 2


def test_the_clip_window_mixes_the_sound_only_with_the_tracks_for_it(clip, four_track, tmp_path):
    """1.8.6: a four-track recording gets a box and a level per source (remembered, applied to the mix), a
    one-track recording only the hint."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QApplication
    from dbdmapscout import qt_clip
    app = QApplication.instance() or QApplication([])
    settings = {}
    win = qt_clip.ClipWindow(four_track, [], str(tmp_path / "Clips"), sound=False,
                             mix_on={"discord": False}, mix_vol={"dbd": 120},
                             on_setting=lambda k, v: settings.__setitem__(k, v))
    try:
        win.show()
        assert win.mix_hint.isHidden() and all(win.mix_boxes[k].isEnabled() for k in ("dbd", "discord", "mic"))
        assert win.mix() == {"dbd": 1.2, "discord": 0.0, "mic": 1.0} and win.mix_values["dbd"].text() == "120 %"
        win.mix_boxes["discord"].setChecked(True)
        win.mix_sliders["mic"].setValue(0)
        assert win.mix() == {"dbd": 1.2, "discord": 1.0, "mic": 0.0}
        assert settings["clip_mix_on"] == {"dbd": True, "discord": True, "mic": True}
        assert settings["clip_mix_vol"] == {"dbd": 120, "discord": 100, "mic": 0}
        assert "Ton neu gemischt" in win.size_label.text()
        win.mix_boxes["dbd"].setChecked(False)
        win.mix_boxes["discord"].setChecked(False)
        assert "ohne Ton" in win.size_label.text()
    finally:
        win.close()
        app.processEvents()
    win = qt_clip.ClipWindow(clip, [], str(tmp_path / "Clips"), sound=False)
    try:
        win.show()
        assert not win.mix_hint.isHidden() and win.mix_boxes["dbd"].isHidden() and win.mix() is None
        assert "Spur 1–4" in win.mix_hint.text()
    finally:
        win.close()
        app.processEvents()


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
        assert win.loading is not None and win.loading.isVisible() and not win.loading.finished   # 1.8.3: loading screen
        assert win.loading.geometry() == win.rect() and win.loading.bar.maximum() == clipedit.THUMBS + 1
        deadline = time.time() + 15
        while time.time() < deadline and not win.loading.finished:
            app.processEvents()
            time.sleep(0.02)
        assert win.loading.finished and win.loading.isHidden()       # gone once picture and strip are in, not by timeout
        assert win.loading.done_n == clipedit.THUMBS + 1 and "Bildern" in win.loading.detail.text()
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


def test_the_strip_comes_from_parallel_key_frame_seeks(clip):
    """1.8.3 (user: "das Laden optimieren"; 1.7.1 streamed one run over the whole file): thumb_strip fetches every
    picture of the strip as a key frame, several at once, at the strip size; the order is the order of finishing;
    a stop ends it early. frame_at(keyframe=True) gives the key frame at or before the moment."""
    info = clipedit.probe(clip, FF)
    times = clipedit.thumb_times(info.duration, clipedit.THUMBS)
    t0 = time.time()
    got = list(clipedit.thumb_strip(clip, times, 54, info, FF))
    assert sorted(i for i, _img in got) == list(range(clipedit.THUMBS))
    assert all(img.size == (96, 54) and img.mode == "RGB" for _i, img in got)
    assert time.time() - t0 < 10
    by_index = dict(got)
    assert by_index[0].tobytes() != by_index[clipedit.THUMBS - 1].tobytes()   # key frames every second: the picture moves
    quick = clipedit.frame_at(clip, 7.5, 54, info, FF, keyframe=True)        # key frames at whole seconds (-g 30)
    assert quick is not None and quick.size == (96, 54)
    assert quick.tobytes() == clipedit.frame_at(clip, 7.0, 54, info, FF).tobytes()   # = the key frame at 7.0, not 7.5
    last = clipedit.frame_at(clip, info.duration - 0.2, 54, info, FF, keyframe=True)   # past the last key frame: the
    assert last is not None and last.tobytes() == clipedit.frame_at(clip, 11.0, 54, info, FF).tobytes()   # last one
    assert list(clipedit.thumb_strip(clip, times[:1], 54, info, FF)) == []       # one moment: nothing to space
    stopped = list(clipedit.thumb_strip(clip, times, 54, info, FF, stop=lambda: True))
    assert stopped == []


def test_censor_boxes_are_hidden_in_the_saved_clip(clip, tmp_path):
    """1.7.2 (user: censor the names on the left): names_box lies bottom left of the 16:9 game picture (shifted
    by the bars of a wider frame), the filter graph names every box, a black box really is black in the saved
    clip and the picture outside it stays, "copy" becomes a re-encode."""
    assert clipedit.names_box(2560, 1440) == pytest.approx(clipedit.NAMES_BOX)
    wide = clipedit.names_box(3440, 1440)                          # ultrawide: the game picture starts at 440 px
    nx, _ny, nw, _nh = clipedit.NAMES_BOX
    assert wide[0] == pytest.approx(440 / 3440 + nx * 2560 / 3440) and wide[2] == pytest.approx(nw * 2560 / 3440)
    assert clipedit.box_px((0.5, 0.5, 0.25, 0.25), 321, 181) == (160, 90, 80, 46)   # even, inside the frame
    g = clipedit.censor_graph([(0.1, 0.1, 0.2, 0.2), (0.5, 0.5, 0.1, 0.1)], "pixel", 320, 180, "scale=-2:90")
    assert g.count("overlay") == 2 and g.endswith("scale=-2:90[vout]") and "flags=neighbor" in g
    assert "drawbox" in clipedit.censor_graph([(0, 0, 0.5, 0.5)], "black", 320, 180)
    assert "boxblur" in clipedit.censor_graph([(0, 0, 0.5, 0.5)], "blur", 320, 180)
    info = clipedit.probe(clip, FF)
    out = str(tmp_path / "censored.mp4")
    ok, why = clipedit.cut(clip, 2.0, 4.0, out, "copy", FF, info=info, censor=[(0.0, 0.5, 0.5, 0.5)],
                           censor_style="black")
    assert ok, why
    img = clipedit.frame_at(out, 1.0, 180, info=clipedit.probe(out, FF), ffmpeg=FF)
    assert img is not None
    assert max(img.getpixel((40, 150))) < 24 and max(img.getpixel((200, 150))) > 60     # black box left, colour right
    for style in ("pixel", "blur"):
        ok, why = clipedit.cut(clip, 2.0, 3.0, str(tmp_path / f"{style}.mp4"), "discord", FF, target_mb=5,
                               info=info, censor=[clipedit.names_box(320, 180)], censor_style=style)
        assert ok, why


def test_the_clip_window_censors_with_remembered_boxes(clip, tmp_path):
    """1.7.2: the window shows remembered boxes, "Namen links unten" adds one and switches the censoring on,
    the tool draws/removes boxes, every change is saved as a setting, and saving passes the boxes to cut()."""
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from dbdmapscout import qt_clip
    app = QApplication.instance() or QApplication([])
    settings, saved = {}, []
    win = qt_clip.ClipWindow(clip, [], str(tmp_path / "Clips"), mode="copy", sound=False, on_saved=saved.append,
                             on_setting=lambda k, v: settings.__setitem__(k, v), censor_on=False,
                             censor_boxes=[[0.5, 0.5, 0.2, 0.2]])
    try:
        win.show()
        assert win.preview.boxes == [[0.5, 0.5, 0.2, 0.2]] and not win.preview.active
        win._add_names_box()
        assert len(win.preview.boxes) == 2 and win.censor_box.isChecked() and settings["clip_censor_on"] is True
        assert settings["clip_censor_boxes"][1][0] == pytest.approx(clipedit.NAMES_BOX[0], abs=1e-3)
        assert "neu kodiert" in win.size_label.text()
        win.tool_btn.setChecked(True)
        win._tool_toggled()
        assert win.preview.editing
        deadline = time.time() + 15                                  # drawing needs the picture on display
        while time.time() < deadline and win.preview.pixmap().isNull():
            app.processEvents()
            time.sleep(0.02)
        assert not win.preview.pixmap().isNull()
        f = win.preview.frame_rect()                                 # draw a box by dragging on the picture

        def mouse(kind, fx, fy):
            pt = QPointF(f.left() + fx * f.width(), f.top() + fy * f.height())
            ev = QMouseEvent(kind, pt, pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            getattr(win.preview, {QMouseEvent.Type.MouseButtonPress: "mousePressEvent",
                                  QMouseEvent.Type.MouseMove: "mouseMoveEvent",
                                  QMouseEvent.Type.MouseButtonRelease: "mouseReleaseEvent"}[kind])(ev)
        mouse(QMouseEvent.Type.MouseButtonPress, 0.1, 0.1)
        mouse(QMouseEvent.Type.MouseMove, 0.3, 0.25)
        mouse(QMouseEvent.Type.MouseButtonRelease, 0.3, 0.25)
        assert len(win.preview.boxes) == 3 and win.preview.boxes[2] == pytest.approx([0.1, 0.1, 0.2, 0.15], abs=0.02)
        assert win.preview.selected == 2
        win.preview.remove_selected()
        assert len(win.preview.boxes) == 2 and len(settings["clip_censor_boxes"]) == 2
        win.style_box.setCurrentIndex(2)
        assert settings["clip_censor_style"] == "black" and win.preview.style == "black"
        calls = []
        real_cut = clipedit.cut
        qt_clip.clipedit.cut = lambda *a, **k: (calls.append(k), real_cut(*a, **k))[1]
        try:
            win.goto(1.0)
            win.set_start()
            win.goto(2.0)
            win.set_end()
            win.save()
            deadline = time.time() + 30
            while time.time() < deadline and not saved:
                app.processEvents()
                time.sleep(0.02)
        finally:
            qt_clip.clipedit.cut = real_cut
        assert saved and calls and calls[0]["censor_style"] == "black" and len(calls[0]["censor"]) == 2
        win.censor_box.setChecked(False)
        assert win._censor_args() == {} and "neu kodiert" not in win.size_label.text()
    finally:
        win.close()
        app.processEvents()


def test_the_retouch_style_paints_the_box_over_from_its_surroundings(clip, tmp_path):
    """1.7.3 (user: "retouch, make it unrecognisable"): delogo hides the box without a visible block; a box at
    the frame edge is moved EDGE_PX inwards (delogo refuses boxes touching the edge); the preview knows the style."""
    g = clipedit.censor_graph([(0.0, 0.5, 0.5, 0.5)], "retouch", 320, 180)
    assert g.startswith("[0:v]delogo=x=2:y=90:w=160:h=88[c0]") and g.endswith("null[vout]")
    info = clipedit.probe(clip, FF)
    out = str(tmp_path / "retouch.mp4")
    ok, why = clipedit.cut(clip, 2.0, 3.0, out, "copy", FF, info=info, censor=[clipedit.names_box(320, 180)],
                           censor_style="retouch")
    assert ok, why
    before = clipedit.frame_at(clip, 2.5, 180, info=info, ffmpeg=FF)
    after = clipedit.frame_at(out, 0.5, 180, info=clipedit.probe(out, FF), ffmpeg=FF)
    x, y, w, h = clipedit.box_px(clipedit.names_box(320, 180), 320, 180)
    inside = sum(abs(a - b) for px in ((x + w // 2, y + h // 2),) for a, b in zip(before.getpixel(px), after.getpixel(px)))
    outside = sum(abs(a - b) for a, b in zip(before.getpixel((250, 60)), after.getpixel((250, 60))))
    assert inside > 30 and outside < 30                     # changed inside the box, untouched outside
    assert "retouch" in clipedit.CENSOR_STYLES


def test_marking_a_recording_shows_the_compact_editor_beside_the_table(four_track, tmp_path):
    """1.8.8 (user: "click on it and a preview comes where I can play it and quickly edit, sound tracks on/off"):
    marking a row puts a compact clip editor beside the recordings table – picture, sources on/off, start/end,
    save; another row replaces it, no row hides it, "Grosser Editor" opens the full window at the same range."""
    if sys.platform == "win32":
        pytest.skip("Linux: the whole program offscreen (like tests/test_uimodel.py)")
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import json
    import shutil
    from PySide6.QtWidgets import QApplication
    from dbdmapscout.app import App
    from dbdmapscout.app_qt import ui_shown
    root = os.path.join(os.path.dirname(__file__), "..")
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.abspath(os.path.join(root, name)), tmp_path / name)
    (tmp_path / "sim").mkdir()
    folder = tmp_path / "rec"
    folder.mkdir()
    shutil.copy(four_track, folder / "one.mkv")
    t1 = time.time() - 600
    obsrec.save_index(str(folder), [obsrec.Recording(t=t1, file="one.mkv", label="Ormond", end=t1 + 6, size=1,
                                                     marks=[2.0])])
    (tmp_path / "settings.json").write_text(json.dumps({"rec_on": True, "rec_folder": str(folder),
                                                       "welcome_seen": True,
                                                       "clip_mix_on": {"discord": False}}), encoding="utf-8")
    app = App(str(tmp_path), simulate=str(tmp_path / "sim"))
    try:
        qapp = QApplication.instance()
        app._rec_render()
        host = app.qt.host(str(app.rec_host))
        assert host is not None and host.content is None and not ui_shown(app.rec_host)
        app.rec_table.selection_set(repr(t1))
        app.rec_table.event_generate("<<TreeviewSelect>>")
        ed = host.content
        assert ed is not None and ed.compact and not ed.isWindow() and ui_shown(app.rec_host)
        assert ed.info.audio_tracks == 4 and ed.mix() == {"dbd": 1.0, "discord": 0.0, "mic": 1.0}
        assert ed.mix_boxes["dbd"].isVisibleTo(ed) and not ed.mix_sliders["dbd"].isVisibleTo(ed)   # on/off only
        assert ed.expand_btn is not None and not ed.open_btn.isVisibleTo(ed)
        app._rec_buttons()                                          # the same row again: the same editor
        assert host.content is ed
        ed.timeline.set_range(1.0, 3.0)
        ed.goto(2.0)
        ed.expand_btn.click()
        full = app._clip_windows[-1]
        assert full is not ed and full.isWindow() and not full.compact
        assert (full.timeline.start, full.timeline.end) == (1.0, 3.0)
        full.close()
        app.rec_table.selection_remove(repr(t1))
        app.rec_table.event_generate("<<TreeviewSelect>>")
        qapp.processEvents()
        assert host.content is None and not ui_shown(app.rec_host)
    finally:
        app.quit()
