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

