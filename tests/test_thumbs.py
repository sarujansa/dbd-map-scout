"""1.8.72: the tiles' small pictures – cache on disk, decoding in a thread (thumbs.py, no Qt)."""
import os
import time

from PIL import Image

from dbdmapscout import thumbs


def _picture(path, size=(1280, 900), colour="red"):
    Image.new("RGBA", size, colour).save(path)
    return str(path)


def test_the_cache_name_follows_the_picture_and_the_box(tmp_path):
    """A replaced picture (other mtime or size) and another tile size never show an old thumbnail."""
    pic = _picture(tmp_path / "a.png")
    name = thumbs.cache_name(pic, (126, 116))
    assert name.endswith(".png") and name == thumbs.cache_name(pic, (126, 116))
    assert name != thumbs.cache_name(pic, (252, 232))
    time.sleep(0.01)
    _picture(pic, size=(1280, 901))                                    # the file changed
    assert name != thumbs.cache_name(pic, (126, 116))
    assert thumbs.cache_name(str(tmp_path / "missing.png"), (126, 116)).endswith(".png")


def test_a_thumbnail_is_made_once_and_then_read_from_the_cache(tmp_path):
    pic = _picture(tmp_path / "a.png", colour=(200, 30, 30, 255))
    cache = str(tmp_path / "cache")
    t = thumbs.thumbnail(pic, (126, 116), cache)
    assert t.size == (126, 89) and t.mode == "RGBA" and t.getpixel((5, 5)) == (200, 30, 30, 255)
    files = os.listdir(cache)
    assert files == [thumbs.cache_name(pic, (126, 116))] and not any(f.endswith(".tmp") for f in files)
    old = os.path.join(cache, files[0])
    os.utime(old, (1, 1))                                               # as if used long ago
    again = thumbs.thumbnail(pic, (126, 116), cache)
    assert again.size == (126, 89) and os.stat(old).st_mtime > 1      # read from the cache: its mtime refreshed
    Image.new("RGBA", (10, 10), "blue").save(old)                       # the cache file is what is read
    assert thumbs.thumbnail(pic, (126, 116), cache).getpixel((1, 1)) == (0, 0, 255, 255)
    assert thumbs.thumbnail(pic, (126, 116), None).size == (126, 89)   # no cache folder: made every time


def test_a_broken_cache_file_is_made_anew_and_old_ones_are_pruned(tmp_path):
    pic = _picture(tmp_path / "a.png")
    cache = str(tmp_path / "cache")
    thumbs.thumbnail(pic, (126, 116), cache)
    target = os.path.join(cache, thumbs.cache_name(pic, (126, 116)))
    with open(target, "wb") as f:
        f.write(b"not a png")
    assert thumbs.thumbnail(pic, (126, 116), cache).size == (126, 89)
    with Image.open(target) as im:
        assert im.size == (126, 89)                                     # written again
    stale = os.path.join(cache, "stale.png")
    Image.new("RGBA", (2, 2)).save(stale)
    os.utime(stale, (1, 1))
    with open(os.path.join(cache, "other.txt"), "w") as f:
        f.write("mine")
    assert thumbs.prune(cache) == 1
    assert sorted(os.listdir(cache)) == sorted([os.path.basename(target), "other.txt"])
    assert thumbs.prune(str(tmp_path / "nowhere")) == 0


def test_the_loader_makes_thumbnails_in_a_thread_and_the_newest_request_wins(tmp_path):
    pics = [_picture(tmp_path / f"{i}.png", colour=(i * 20, 0, 0, 255)) for i in range(6)]
    loader = thumbs.Loader((126, 116), str(tmp_path / "cache"))
    assert loader.make(pics[0])[:3] == (pics[0], 126, 89)
    assert loader.make(str(tmp_path / "missing.png")) == (str(tmp_path / "missing.png"), 0, 0, b"")
    loader.request(pics[:3])
    loader.request(pics[3:])                                            # replaces what was still to do
    got = {}
    end = time.time() + 10
    while not set(got) >= set(pics[3:]) and time.time() < end:    # 1.8.74: all three of the second request – the
        for path, w, h, data in loader.take():                     # one picture the thread had in hand from the
            got[path] = (w, h, len(data))                          # first may come first (the test waited for 3)
        time.sleep(0.01)
    assert set(got) >= set(pics[3:]) and all(v == (126, 89, 126 * 89 * 4) for v in got.values())
    assert not (set(got) - set(pics)) and len(got) <= 4                 # at most one of the first request
    assert not loader.busy
    assert all(os.path.isfile(os.path.join(str(tmp_path / "cache"), thumbs.cache_name(p, (126, 116))))
               for p in pics[3:])
