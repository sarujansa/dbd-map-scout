"""1.64 "Läuft gerade": music in the black bar (pure parts; the WinRT reading runs in tests/test_windows.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbdmapscout import media  # noqa: E402

DIM, WHITE = (1,), (2,)


def test_rows_only_while_something_plays_and_fresh():
    now = media.NowPlaying("Bohemian Rhapsody", "Queen", True, 100.0)
    assert media.rows(now, 101, "MUSIK ", DIM, WHITE) == [[("MUSIK ", DIM), ("Bohemian Rhapsody", WHITE)],
                                                         [("Queen", DIM)]]
    assert media.rows(media.NowPlaying("x y z", "", False, 100.0), 101, "M", DIM, WHITE) == []   # paused
    assert media.rows(now, 100 + media.STALE_AFTER + 1, "M", DIM, WHITE) == []                # old reading
    assert media.rows(media.NowPlaying("", "Queen", True, 100.0), 101, "M", DIM, WHITE) == []   # no title
    assert len(media.rows(media.NowPlaying("Intro", "", True, 100.0), 101, "M", DIM, WHITE)) == 1


def test_long_titles_are_cut_at_a_word():
    title = "Symphony No. 9 in D minor, Op. 125 – IV. Presto – Allegro assai"
    out = media.clip(title)
    assert len(out) <= media.MAX_CHARS and out.endswith("…") and out.startswith("Symphony No. 9")
    assert media.clip("  kurz   und\nknapp ") == "kurz und knapp"
    assert len(media.clip("A" * 80)) == media.MAX_CHARS


class _Reader:
    def __init__(self, results):
        self.results = list(results)

    def read(self, want_cover=False):
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_watcher_reads_only_while_active_and_survives_errors():
    song = media.NowPlaying("Song", "Band", True, 5.0)
    w = media.MediaWatcher(reader=_Reader([song, OSError("no media controls")]))
    w.look()
    assert w.now == media.NowPlaying() and w.diag_line().startswith("Musik: aktiv=False")   # off: no reading
    w.active = True
    w.look()
    assert w.now == song and w.error == ""
    assert "Song" not in w.diag_line() and "spielt" in w.diag_line()     # never the title in the diagnosis
    w.look()                                                              # the reader fails
    assert w.now == media.NowPlaying() and "OSError" in w.error
    assert w._reader is None                                              # a fresh one next time


def test_cover_is_decoded_small_and_broken_data_is_none():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (640, 640), (200, 30, 60)).save(buf, "JPEG")
    img = media.decode_cover(buf.getvalue())
    assert img is not None and img.mode == "RGBA" and max(img.size) <= media.COVER_PX
    assert media.decode_cover(b"") is None and media.decode_cover(b"not a picture") is None
    assert media.decode_cover(b"x" * (media.MAX_COVER_BYTES + 1)) is None


def test_music_card_places():
    from dbdmapscout import layout
    game, size, m = (0, 0, 3440, 1440), (270, 90), 17
    assert layout.media_xy("below", game, size, m, hud=(3130, 17, 290, 300)) == (3130, 17 + 300 + 8)
    assert layout.media_xy("below", game, size, m) == (3440 - 17 - 270, 17)          # no system values shown
    assert layout.media_xy("below", game, size, m, hud=(3300, 17, 120, 50))[0] == 3440 - 17 - 270   # stays inside
    assert layout.media_xy("bottom_right", game, size, m) == (3153, 1440 - 17 - 90)
    assert layout.media_xy("bottom_left", game, size, m) == (17, 1333)
    assert layout.media_xy("custom", game, size, m, own=(0.5, 0.0)) == (1585.0, 0.0)
    assert layout.media_xy("custom", game, size, m) == (3170.0, 1350.0)             # never dragged: bottom right



def test_progress_runs_on_from_the_last_report():
    """1.64.7: players report the position only now and then – it runs on while the song plays, never past the
    end, stands still while paused; no length = no bar."""
    playing = media.NowPlaying("S", "A", True, 100.0, position=70.0, duration=176.0, at=100.0)
    assert media.progress(playing, 110.0) == (80.0, 176.0)
    assert media.progress(playing, 1000.0) == (176.0, 176.0)
    paused = media.NowPlaying("S", "A", False, 100.0, position=70.0, duration=176.0, at=100.0)
    assert media.progress(paused, 500.0) == (70.0, 176.0)
    assert media.progress(media.NowPlaying("S", "A", True, 100.0), 110.0) is None
    assert media.clock(70) == "1:10" and media.clock(3725) == "1:02:05"


def test_music_card_styles_and_progress_strip():
    from PIL import Image
    from dbdmapscout.overlay_win32 import render_music
    rows = [[("Blinding Lights", (255, 255, 255, 255))], [("The Weeknd", (150, 156, 170, 255))]]
    cover = Image.new("RGBA", (160, 160), (200, 30, 60, 255))
    big = render_music(rows, cover, 1440, "big")
    compact = render_music(rows, cover, 1440, "compact")
    assert big.height > big.width > 1440 // 6                  # cover on top: taller than wide
    assert compact.width > compact.height                      # cover left: a row
    with_bar = render_music(rows, cover, 1440, "big", (70, 176))
    assert with_bar.height > big.height and with_bar.width == big.width
    assert render_music(rows, None, 1440, "big").height < big.height     # no cover: only the text


def test_hud_values_stand_in_one_column():
    """1.64.7 (user: "alles schön untereinander"): the values of all labelled rows start at the same x."""
    from dbdmapscout import sysinfo
    from dbdmapscout.overlay_win32 import render_hud
    W = sysinfo.WHITE

    def first_value_x(label):
        pic = render_hud([[(label, sysinfo.DIM), ("88", W)], [("Ø KILLS ", sysinfo.DIM), ("2.9", W)]], 1440)
        row = pic.crop((0, 0, pic.width, pic.height // 2)).convert("RGB")
        px = row.load()
        return next(x for x in range(row.width) for y in range(row.height) if px[x, y] == (255, 255, 255))
    assert abs(first_value_x("CPU ") - first_value_x("VRAM ")) <= 1


def test_old_settings_move_the_music_card_out_of_the_system_values(tmp_path):
    """1.64.7: "below the system values" was the old default – once moved to bottom right; chosen later, it stays."""
    import json
    from dbdmapscout.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 3, "overlay": {"media_pos": "below"}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["media_pos"] == "bottom_right"
    p.write_text(json.dumps({"settings_version": 4, "overlay": {"media_pos": "below"}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["media_pos"] == "below"


def test_the_whole_title_wraps_instead_of_being_cut():
    """1.65 (user: "der ganze Titel soll angezeigt werden")."""
    title = "Somebody That I Used To Know (feat. Kimbra)"
    lines = media.wrap(title)
    assert " ".join(lines) == title and all(len(line) <= media.MAX_CHARS for line in lines)
    assert media.wrap("x" * 50) == ["x" * 22, "x" * 22, "x" * 6]          # one long word is cut, not lost
    long = media.wrap("word " * 40)
    assert len(long) == media.TITLE_LINES and long[-1].endswith("…")       # only far too long ends with "…"
    now = media.NowPlaying(title, "Gotye", True, 100.0)
    rows = media.rows(now, 101.0, "", "dim", "white")
    assert [r[0][0] for r in rows] == lines + ["Gotye"] and rows[-1][0][1] == "dim"
