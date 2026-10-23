"""1.8.60: a clip from the Clips tab opens in the clip editor like a recording."""
from fogscout import obsrec
from fogscout.app_recordings import clip_round


def test_a_clip_opens_with_the_round_it_came_from():
    rec = obsrec.Recording(t=100.0, file="round.mkv", marks=[12.0, 40.0],
                           extra={"sources": ["dbd", "discord", "mic"]})
    c = obsrec.Clip(file="x (Sofort-Clip).mp4", kind="instant", source=100.0, map_id="coal", label="Coal Tower",
                    role="killer", killer="nurse", farming=True)
    r = clip_round(c, [obsrec.Recording(t=50.0, file="other.mkv"), rec])
    assert r.t == 100.0                                   # a clip saved from it belongs to the same round
    assert r.extra == {"sources": ["dbd", "discord", "mic"]}
    assert r.marks == []                                  # the recording's marks count from its own start
    assert (r.map_id, r.label, r.role, r.killer, r.farming) == ("coal", "Coal Tower", "killer", "nurse", True)


def test_a_clip_without_its_recording_has_unknown_sources():
    c = obsrec.Clip(file="old.mp4", source=0.0)
    r = clip_round(c, [obsrec.Recording(t=0.0, file="z.mkv", extra={"sources": ["dbd"]})])
    assert r.extra == {} and r.t == 0.0                    # source 0 = unknown, never matched to a recording
