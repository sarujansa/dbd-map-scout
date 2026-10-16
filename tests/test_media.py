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
    # 1.65.2 (user: "untereinander und mittig"): centred under the system values / in the middle of the bar
    assert layout.media_xy("below", game, size, m, hud=(3130, 17, 290, 300)) == (3140, 17 + 300 + 8)
    assert layout.media_xy("below", game, size, m) == (3220 - 135, 17)               # no system values shown
    assert layout.media_xy("below", game, size, m, hud=(3300, 17, 120, 50))[0] == 3440 - 17 - 270   # stays inside
    assert layout.media_xy("bottom_right", game, size, m) == (3220 - 135, 1440 - 17 - 90)
    assert layout.media_xy("bottom_left", game, size, m) == (220 - 135, 1333)
    assert layout.hud_x("right", 0, 3440, m, 300, 440) == 3220 - 150                 # system values: centred too
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
    assert Settings(str(p))["overlay"]["media_pos"] == "under_today"      # 1.2.7: below "today", as 1.2.6 showed it
    p.write_text(json.dumps({"settings_version": 6, "overlay": {"media_pos": "below"}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["media_pos"] == "below"


def test_the_whole_title_wraps_instead_of_being_cut():
    """1.65 (user: "der ganze Titel soll angezeigt werden"); since 1.65.2 one row – the card sets it smaller."""
    title = "Somebody That I Used To Know (feat. Kimbra)"
    lines = media.wrap(title)
    assert " ".join(lines) == title and all(len(line) <= media.MAX_CHARS for line in lines)
    assert media.wrap("x" * 50) == ["x" * 22, "x" * 22, "x" * 6]          # one long word is cut, not lost
    long = media.wrap("word " * 40)
    assert len(long) == media.TITLE_LINES and long[-1].endswith("…")       # only far too long ends with "…"
    now = media.NowPlaying(title, "Gotye", True, 100.0)
    rows = media.rows(now, 101.0, "", "dim", "white")
    assert [r[0][0] for r in rows] == [title, "Gotye"] and rows[-1][0][1] == "dim"


def test_a_long_title_gets_smaller_text_before_it_wraps():
    """1.65.2 (user: "lieber die Schrift kleiner statt Zeilenumbruch")."""
    from dbdmapscout.overlay_win32 import fit_lines, render_hud
    white = (255, 255, 255, 255)
    short, longer = [[("Blinding Lights", white)]], [[("Somebody That I Used To Know", white)]]
    full = render_hud(longer, 1440)
    one = fit_lines(longer, 1440)
    assert len(one) == 1 and one[0].height < full.height                 # one line, a bit smaller
    assert fit_lines(short, 1440)[0].size == render_hud(short, 1440).size  # short: untouched
    very = fit_lines([[("Somebody That I Used To Know And Then Some More Words Here", white)]], 1440)
    assert len(very) > 1                                                 # far too long: wraps, at the small size


def test_accent_colour_from_the_cover():
    """1.2.4: the bar takes the cover's main colour, lifted to read on black; grey covers have none."""
    import colorsys
    from PIL import Image, ImageDraw
    cover = Image.new("RGB", (160, 160), (10, 10, 10))
    ImageDraw.Draw(cover).rectangle((0, 0, 159, 100), fill=(20, 60, 160))          # dark blue, most of it
    r, g, b, a = media.accent(cover)
    h, light, _s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    assert b > r and b > g and light >= media.ACCENT_LIGHT - 0.01 and a == 255
    assert media.accent(Image.new("RGB", (64, 64), (128, 128, 128))) is None        # grey: the bar stays white
    assert media.accent(None) is None


def test_music_card_look_options():
    """1.2.4 (user's pick 4–7): accent bar, time left, dark area behind the card."""
    from PIL import Image
    from dbdmapscout.overlay_win32 import CARD_BACKDROP, progress_strip, render_music
    rows = [[("Blinding Lights", (255, 255, 255, 255))], [("The Weeknd", (150, 156, 170, 255))]]
    cover = Image.new("RGBA", (160, 160), (200, 30, 60, 255))
    plain = render_music(rows, cover, 1440, "big", (70, 200))
    boxed = render_music(rows, cover, 1440, "big", (70, 200), ("backdrop",))
    assert boxed.width > plain.width and boxed.height > plain.height
    assert boxed.getpixel((boxed.width // 2, boxed.height - 3)) == CARD_BACKDROP     # the area at the bottom edge
    white = progress_strip(300, 100, 200, 1440)
    red = progress_strip(300, 100, 200, 1440, accent=(220, 40, 60, 255))
    bar = [red.getpixel((x, red.height // 2)) for x in range(red.width)]
    assert (220, 40, 60, 235) in bar and white.tobytes() != red.tobytes()
    assert progress_strip(300, 100, 200, 1440, remaining=True).tobytes() != white.tobytes()
    assert media.look({}) == ("accent", "remaining", "backdrop")
    assert media.look({"media_remaining": False, "media_backdrop": False}) == ("accent",)


def test_fader_eases_in_and_out():
    f = media.Fader()
    f.go(1, 10.0, start=0.0)
    assert f.value == 0.0 and not f.step(10.1) and 0 < f.value < 0.5
    assert f.step(10.0 + f.IN_S) and f.value == 1.0
    f.go(0, 20.0)
    assert not f.step(20.1) and 0.3 < f.value < 1
    assert f.step(20.0 + f.OUT_S) and f.value == 0.0


def test_an_own_place_of_the_music_card_is_its_centre():
    """1.2.5 (user: a wider card for a long title moved and was no longer centred): the own place is where the
    card's centre is, so a card of another width or height stays around the same spot."""
    from dbdmapscout import layout
    game = (0, 0, 3440, 1440)
    own = layout.media_own(3440, 1440, (270, 90), 1585, 600)
    assert own == (0.5, round(645 / 1440, 4))
    narrow = layout.media_xy("custom", game, (270, 90), 17, own=own)
    wide = layout.media_xy("custom", game, (400, 120), 17, own=own)
    assert narrow[0] + 135 == wide[0] + 200 and abs(narrow[1] + 45 - (wide[1] + 60)) <= 1    # same centre
    assert layout.media_xy("custom", game, (400, 120), 17, own=(1.0, 1.0)) == (3040, 1320)   # never off screen
    assert layout.media_own(3440, 1440, (270, 90), 3170, 1350) == (0.9608, 0.9688)


def test_old_today_at_its_own_place_becomes_a_card_at_that_place(tmp_path):
    """1.2.6: "today" alone (system values off) dragged somewhere → its own card at that place."""
    import json
    from dbdmapscout.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 4, "sysinfo": "off", "today_side": "custom",
                             "sysinfo_pos": [0.2, 0.7], "overlay": {}, "hotkeys": {}}))
    s = Settings(str(p))
    assert s["overlay"]["today_pos"] == "custom" and s["overlay"]["today_xy"] == [0.2, 0.7]
    assert "today_side" not in s.data
    p.write_text(json.dumps({"settings_version": 4, "sysinfo": "right", "today_side": "custom",
                             "sysinfo_pos": [0.2, 0.7], "overlay": {}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["today_pos"] == "below"          # it hung below the system values


def test_old_single_opacity_becomes_every_cards_opacity(tmp_path):
    """1.2.7: one opacity for everything → each card keeps that value as its own; music "below" under "today"."""
    import json
    from dbdmapscout.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 5, "overlay": {"opacity": 0.6, "media_pos": "below"}, "hotkeys": {}}))
    o = Settings(str(p))["overlay"]
    assert (o["hud_opacity"], o["today_opacity"], o["media_opacity"]) == (0.6, 0.6, 0.6)
    assert o["media_pos"] == "under_today"
