"""1.8.54 (user: "Mach das mit den Notizen für die Map"): own notes per map – written on the maps page, shown in the
game with the map's lines."""
import os
import queue
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from fogscout import mapnotes, preview, skin  # noqa: E402
from fogscout import overlay_win32 as ow  # noqa: E402
from fogscout.config import DEFAULTS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COAL = os.path.join(ROOT, "maps", "McMillan", "Coal Tower.webp")
NOTE = "Shack links vom Main\nGen im Keller oft schwach"


class _Root:
    def after(self, *a):
        return None

    def after_cancel(self, *a):
        pass


class _Overlay(ow.PictureOverlay):
    def _push(self, *a):
        pass


def test_a_note_is_stored_clean_and_an_empty_one_is_removed():
    assert mapnotes.clean("  \r\nerste  \r\nzweite\n\n") == "erste\nzweite"
    assert len(mapnotes.clean("x" * 1000)) == mapnotes.MAX_CHARS
    notes = mapnotes.put({}, "coal", " Shack links ")
    assert notes == {"coal": "Shack links"} and mapnotes.get(notes, "coal") == "Shack links"
    assert mapnotes.put(notes, "coal", " \n ") == {} and notes == {"coal": "Shack links"}   # a new dict
    assert mapnotes.get(None, "coal") == "" and mapnotes.get("broken", "coal") == ""
    assert DEFAULTS[mapnotes.KEY] == {} and DEFAULTS["overlay"]["show_notes"] is True


def test_the_game_shows_at_most_four_short_lines():
    assert mapnotes.lines("") == ()
    assert mapnotes.lines(NOTE) == ("Shack links vom Main", "Gen im Keller oft schwach")
    long = mapnotes.lines(" ".join(["Pallet"] * 80))
    assert len(long) == mapnotes.MAX_LINES and long[-1].endswith("…")
    assert all(len(line) <= mapnotes.LINE_CHARS for line in long)
    assert len(mapnotes.lines("\n".join("abcdef"))) == mapnotes.MAX_LINES


def test_the_note_is_drawn_below_the_lines_in_every_style():
    memo = mapnotes.lines(NOTE)
    plain = ow.add_info(Image.new("RGBA", (300, 300)), "3:27", "", 300, record="Ø 2,8 Kills")
    noted = ow.add_info(Image.new("RGBA", (300, 300)), "3:27", "", 300, record="Ø 2,8 Kills", memo=memo)
    assert noted.height > plain.height
    alone = ow.add_info(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), "", "", 300, memo=memo)
    assert alone.height > 1                                   # a note alone is drawn too
    body = Image.new("RGBA", (260, 260), (40, 40, 40, 255))
    for style in skin.STYLES:
        if style == "classic":
            continue
        a = skin.map_card(body, "Coal Tower", "MacMillan", "3:27", "", "", "", None, (), 300, style)
        b = skin.map_card(body, "Coal Tower", "MacMillan", "3:27", "", "", "", None, (), 300, style, memo=memo)
        assert b.height > a.height and b.width == a.width     # four short lines never widen the card
        top = skin.map_card(body, "Coal Tower", "MacMillan", "3:27", "", "", "", None, (), 300, style,
                            memo=memo, lines_top=True)
        assert top.size == b.size                              # above or below the map: the same card
    card = ow.info_card("", "", None, "", "", 300, "glass", memo=memo)
    assert card is not None and card.height > 0


def test_the_overlay_draws_the_note_of_the_map_on_display():
    ov = _Overlay(_Root())
    ov.set_map(COAL, "Coal Tower")
    w0, h0 = ov.render(400, push=False)
    assert not ov.has_info()
    ov.set_memo(mapnotes.lines(NOTE))
    assert ov.has_info()
    w1, h1 = ov.render(400, push=False)
    assert h1 > h0
    ov.set_info_apart(True)                                   # the lines as their own element: the note goes along
    assert ov.render(400, push=False)[1] < h1 and ov.info_picture(300) is not None
    ov.set_memo(())
    assert ov.info_picture(300) is None


def test_the_preview_shows_the_note_like_the_game():
    pic = Image.open(COAL).convert("RGBA")
    o = dict(DEFAULTS["overlay"])
    info = {"timer": "3:27", "name": "Coal Tower", "realm": "MacMillan Estate"}
    a, _r = preview.layers(3440, 1440, o, "", [], None, pic, "", info, 0.3)
    b, _r = preview.layers(3440, 1440, o, "", [], None, pic, "", dict(info, memo=mapnotes.lines(NOTE)), 0.3)
    size = {n: img.size for n, img, _x, _y in a}
    noted = {n: img.size for n, img, _x, _y in b}
    assert noted["text"][1] > size["text"][1]


# ------------------------------------------------------------------ the maps page (offscreen / Windows)
@pytest.fixture
def page():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import shiboken6
    from fogscout import qt_window
    qapp = qt_window.application()
    posted = queue.Queue()
    p = qt_window.MapsPage(lambda a, arg=None: posted.put((a, arg)))
    p.posted = posted
    yield p
    if shiboken6.isValid(p):
        p.hide()
        shiboken6.delete(p)
    qapp.processEvents()


def _posts(page):
    out = []
    while not page.posted.empty():
        out.append(page.posted.get_nowait())
    return out


def test_the_maps_page_saves_the_note_of_the_map_shown_big(page):
    assert not page.p_note.isEnabled()                         # nothing selected: nothing to write on
    page.show_preview(("coal", 1, "Coal Tower", "MacMillan", None, "alt"))
    assert page.p_note.isEnabled() and page.p_note.toPlainText() == "alt"
    assert _posts(page) == []                                   # showing a note saves nothing
    page.p_note.setPlainText("neu")
    assert page._note_saver.isActive()
    page.show_preview(("coal", 1, "Coal Tower", "MacMillan", None, "alt"))   # a refresh keeps what is typed
    assert page.p_note.toPlainText() == "neu"
    page.show_preview(("pit", 1, "Suffocation Pit", "MacMillan", None, ""))  # another map: the last one saved
    assert ("map_note", ("coal", "neu")) in _posts(page)
    assert page.p_note.toPlainText() == ""
    page.p_note.setPlainText("y" * (mapnotes.MAX_CHARS + 50))
    assert len(page.p_note.toPlainText()) == mapnotes.MAX_CHARS
    page.close_big()                                            # leaving the big view saves at once
    assert _posts(page) == [("map_note", ("pit", "y" * mapnotes.MAX_CHARS))]
    page.close_big()
    assert _posts(page) == []                                   # nothing new: no second save


def test_the_context_menu_opens_the_note(page):
    page.show_maps([("MacMillan", "Coal Tower", "coal", 1)], None)
    assert [a for a, _l, _e in page.menu_entries(("coal", 1))][-1] == "note"
    page.edit_note(("coal", 1))
    assert page.stack.currentIndex() == 1
    assert ("map_preview", ("coal", 1)) in _posts(page)


@pytest.mark.skipif(sys.platform == "win32", reason="Linux: the Windows job tests the native parts")
def test_the_program_keeps_the_note_and_shows_it_with_the_map(tmp_path):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    for name in ("maps", "models", "maps.json"):
        os.symlink(os.path.join(ROOT, name), tmp_path / name)
    (tmp_path / "sim").mkdir()
    from fogscout.app import App
    app = App(str(tmp_path), simulate=str(tmp_path / "sim"))
    try:
        mid, other = list(app.catalog.maps)[:2]
        app.show_map(mid, 1, "manual")
        assert app.overlay._memo == ()
        app._qt_event("map_note", (mid, NOTE + "\n"))
        assert app.settings.get(mapnotes.KEY) == {mid: NOTE}
        assert app.overlay._memo == mapnotes.lines(NOTE)                     # the map on display shows it at once
        assert app._qt_preview((mid, 1))[5] == NOTE                          # the maps page reads it back
        assert "✎" in app._qt_marks([("", "", mid, 1)])[(mid, 1)][0]          # and marks the tile
        assert app._preview_data() is not None
        app._qt_event("map_note", ("no such map", "x"))                     # unknown ids are never stored
        assert set(app.settings.get(mapnotes.KEY)) == {mid}
        app.show_map(other, 1, "manual")
        assert app.overlay._memo == ()                                       # another map: its own note (none)
        app.show_map(mid, 1, "manual")
        app.notes_var.set(False)
        app._overlay_flags_changed()
        assert app.overlay._memo == () and app.settings["overlay"]["show_notes"] is False
        app._qt_event("map_note", (mid, ""))
        assert app.settings.get(mapnotes.KEY) == {}
    finally:
        app.quit()
