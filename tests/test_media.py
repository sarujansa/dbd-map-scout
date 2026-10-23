"""1.64 "Läuft gerade": music in the black bar (pure parts; the WinRT reading runs in tests/test_windows.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import media  # noqa: E402

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
    from fogscout import layout
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
    from fogscout.overlay_win32 import render_music
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
    from fogscout import sysinfo
    from fogscout.overlay_win32 import render_hud
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
    from fogscout.config import Settings
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
    from fogscout.overlay_win32 import fit_lines, render_hud
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
    from fogscout.overlay_win32 import CARD_BACKDROP, progress_strip, render_music
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
    from fogscout import layout
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
    from fogscout.config import Settings
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
    from fogscout.config import Settings
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 5, "overlay": {"opacity": 0.6, "media_pos": "below"}, "hotkeys": {}}))
    o = Settings(str(p))["overlay"]
    assert (o["hud_opacity"], o["today_opacity"], o["media_opacity"]) == (0.6, 0.6, 0.6)
    assert o["media_pos"] == "under_today"


def test_old_settings_turn_the_pre_roll_and_the_joining_off(tmp_path):
    """1.5.5 (user: no lobby in the recording; the joined file played too fast in the round): both off once,
    switched on again later they stay on."""
    import json
    from fogscout.config import Settings, DEFAULTS, SETTINGS_VERSION
    assert DEFAULTS["rec_pre"] is False and DEFAULTS["rec_merge"] is False
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 6, "rec_pre": True, "rec_merge": True, "hotkeys": {}}))
    s = Settings(str(p))
    assert s["rec_pre"] is False and s["rec_merge"] is False and s["settings_version"] == SETTINGS_VERSION
    p.write_text(json.dumps({"settings_version": 7, "rec_pre": True, "rec_merge": True, "hotkeys": {}}))
    assert Settings(str(p))["rec_pre"] is True


def test_the_limiter_lines_of_each_bar_are_its_own_after_the_update(tmp_path):
    """1.8.17 (user: "nicht gleich auf beiden Seiten … links eigene und rechts eigene"): off by default and
    switched off once for older settings; switched on again later it stays on."""
    import json
    from fogscout.config import Settings, DEFAULTS
    assert DEFAULTS["overlay"]["bar_limits_same"] is False
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"settings_version": 7, "overlay": {"bar_limits_same": True}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["bar_limits_same"] is False
    p.write_text(json.dumps({"settings_version": 8, "overlay": {"bar_limits_same": True}, "hotkeys": {}}))
    assert Settings(str(p))["overlay"]["bar_limits_same"] is True


def test_alignment_in_the_bar_and_the_stack_gap():
    """1.2.8 (user's picks 22 + 24): left / centred / right in the bar and under the card above; one gap."""
    from fogscout import layout
    game, size, m = (0, 0, 3440, 1440), (270, 90), 17
    assert layout.hud_x("right", 0, 3440, m, 300, 440, "left") == 3000 + 17
    assert layout.hud_x("right", 0, 3440, m, 300, 440, "right") == 3440 - 17 - 300
    assert layout.hud_x("left", 0, 3440, m, 300, 440, "right") == 440 - 17 - 300
    hud = (3130, 17, 290, 300)
    assert layout.media_xy("below", game, size, m, hud=hud, align="left")[0] == 3130
    assert layout.media_xy("below", game, size, m, hud=hud, align="right")[0] == 3130 + 290 - 270
    assert layout.media_xy("below", game, size, m, hud=hud, gap=30)[1] == 17 + 300 + 30
    assert layout.media_xy("bottom_left", game, size, m, align="left") == (17, 1333)
    assert layout.stack_gap({"stack_gap": 8}, 1440) == 8 and layout.stack_gap({"stack_gap": 8}, 1080) == 6
    assert layout.stack_gap({}, 1440) == 8 and layout.stack_gap({"stack_gap": 0}, 1440) == 0
    assert layout.preview_place(3440, 1440, "auto", 0, 0, m, True, 300, 400, align="right")[0] == 440 - 17 - 300
    assert layout.preview_place(3440, 1440, "auto", 0, 0, m, True, 300, 400, align="left")[0] == 17


def _reference_hud(rows, height):
    """render_hud as it was before 1.2.13: every character with ImageDraw.text (no cache)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    from fogscout.overlay_win32 import DIM_LABEL, FIRA
    size = max(13, height // 60)
    font = ImageFont.truetype(FIRA, size)
    gap, blur, halo = max(3, height // 160), max(2, height // 300), max(1, height // 400)
    pad = 3 * blur
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    def width(text):
        return sum(d0.textlength(c, font=font) for c in text)
    labelled = [len(row) >= 2 and row[0][1] == DIM_LABEL and row[0][0].strip() for row in rows]
    col = max((int(width(row[0][0])) for row, lab in zip(rows, labelled) if lab), default=0)
    texts = ["".join(t for t, _ in (row[1:] if lab else row)) for row, lab in zip(rows, labelled)]
    widths = [int(width(t)) + (col if lab else 0) for t, lab in zip(texts, labelled)]
    asc, desc = font.getmetrics()
    line_h = asc + desc
    w, h = max(widths, default=0) + 2 * pad, len(rows) * line_h + gap * max(0, len(rows) - 1) + 2 * pad
    dark = (0, 0, 0, 230)

    def draw(d, shadow):
        y = pad
        for row, lab in zip(rows, labelled):
            x = pad
            for i, (text, colour) in enumerate(row):
                if lab and i == 1:
                    x = pad + col
                for ch in text:
                    d.text((x, y), ch, font=font, fill=dark if shadow else colour,
                           stroke_width=halo if shadow else 0, stroke_fill=dark)
                    x += d.textlength(ch, font=font)
            y += line_h + gap
    pic = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", pic.size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(shadow), True)
    pic.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)), (0, 0))
    draw(ImageDraw.Draw(pic), False)
    return pic


def test_text_is_drawn_exactly_like_character_by_character():
    """1.2.13 (analysis points 5/6): the glyph cache draws the system values pixel for pixel like the
    character-by-character ImageDraw.text of 1.49 – cold and warm – in every size."""
    from fogscout import sysinfo
    from fogscout.overlay_win32 import _GLYPHS, render_hud
    from fogscout.preview import sample_snapshot
    hud = sysinfo.hud_rows(sample_snapshot(), None)
    text = [[("Blinding Lights – jäöü ÄÖÜ ß é 12:34 °C %", sysinfo.WHITE)], [("The Weeknd", sysinfo.DIM)]]
    _GLYPHS.clear()
    for height in (300, 720, 1017, 1080, 1440, 2160):
        for rows in (hud, text):
            want = _reference_hud(rows, height)
            cold, warm = render_hud(rows, height), render_hud(rows, height)
            assert cold.size == want.size and cold.tobytes() == want.tobytes(), height
            assert warm.tobytes() == want.tobytes(), height
    assert 0 < len(_GLYPHS) < 3000


def test_music_card_is_its_body_plus_the_progress_strip():
    """1.2.13: HudWindow keeps the body (cover + text) while a song plays and only draws the strip – the card
    from the parts equals the card drawn in one go, for every style and look."""
    from PIL import Image
    from fogscout.overlay_win32 import music_body, music_card, render_music
    rows = [[("Blinding Lights", (255, 255, 255, 255))], [("The Weeknd", (150, 156, 170, 255))]]
    cover = Image.new("RGBA", (160, 160), (200, 30, 60, 255))
    for style in ("big", "compact"):
        for look in ((), ("accent",), ("accent", "backdrop", "remaining")):
            body = music_body(rows, cover, 1440, style, look)
            for progress in (None, (70, 176), (71, 176)):
                a = render_music(rows, cover, 1440, style, progress, look)
                b = music_card(body, 1440, style, progress, look)
                assert a.size == b.size and a.tobytes() == b.tobytes(), (style, look, progress)
    pic, strip_w, accent = music_body(rows, cover, 1440, "big", ("accent",))
    assert strip_w > 0 and accent is not None and music_body(rows, None, 1440, "big", ())[2] is None


def test_the_fast_premultiply_gives_the_same_bytes_and_the_cover_colour_is_worked_out_once():
    """1.6.1 (overlay tick 30–70 ms once a second at the user's PC): Pillow's "RGBa" instead of numpy – byte for
    byte the same; the cover's accent colour and the scaled covers are kept on the cover."""
    import numpy as np
    from PIL import Image
    from fogscout import overlay_win32 as ow, preview, skin
    rng = np.random.default_rng(1)
    px = rng.integers(0, 256, (37, 53, 4), dtype=np.uint8)
    px[0, :, 3], px[1, :, 3], px[2, :, 3] = 0, 255, 1                  # the edges of alpha
    for img in (Image.fromarray(px, "RGBA"), Image.fromarray(px[:, :, :3], "RGB")):
        assert ow.premultiplied_bgra(img) == ow.premultiplied_bgra_numpy(img)
    cover = preview.sample_cover()
    first = media.accent(cover)
    assert cover.info["_dbdms_accent"] == first and media.accent(cover) == first
    a = skin._round_cover(cover, 120, 20)
    assert skin._round_cover(cover, 120, 20) is a and a.size == (120, 120)
    assert skin._round_cover(cover, 60, 20).size == (60, 60)


def test_videos_are_told_from_music_and_marked():
    """1.8.4 (user: YouTube Music and YouTube videos in the browser): PlaybackType VIDEO is a video; a browser
    (which reports MUSIC for everything) is a video without an album and music with one; other players are
    music. A video's title row starts with the mark, the channel stays the second row; the diagnosis names
    kind and app, never the title."""
    assert media.classify(media.VIDEO, "", "Microsoft.ZuneVideo_8wekyb3d8bbwe!Microsoft.ZuneVideo") == "video"
    assert media.classify(media.MUSIC, "", "Chrome") == "video"                   # browsers say MUSIC for all
    assert media.classify(media.MUSIC, "After Hours", "chrome") == "music"         # YouTube Music, Spotify Web
    assert media.classify(0, "", "MSEdge") == "video" and media.classify(0, "", "firefox") == "video"
    assert media.classify(media.MUSIC, "", "Spotify.exe") == "music" and media.classify(0, "", "") == "music"
    video = media.NowPlaying("Hillbilly guide", "Otzdarva", True, 100.0, kind="video", app="chrome")
    assert media.rows(video, 101, "", DIM, WHITE) == [[(media.VIDEO_MARK + "Hillbilly guide", WHITE)], [("Otzdarva", DIM)]]
    song = media.NowPlaying("Blinding Lights", "The Weeknd", True, 100.0, kind="music", app="chrome")
    assert media.rows(song, 101, "", DIM, WHITE)[0] == [("Blinding Lights", WHITE)]
    w = media.MediaWatcher(reader=_Reader([video]))
    w.active = True
    w.look()
    line = w.diag_line()
    assert "Art=video" in line and "App=chrome" in line and "Hillbilly" not in line and "Otzdarva" not in line
