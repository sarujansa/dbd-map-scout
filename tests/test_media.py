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

    def read(self):
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
