"""Build statistics (fogscout/builds.py, 1.8.48) – pure logic on (round, match) pairs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fogscout import builds  # noqa: E402
from fogscout.official import Match, Player  # noqa: E402

T0 = 1791030420.0


def _killer(kills, perks, addons=(), offering=None, power=None, killer="The Nurse"):
    stats = ["SACRIFICED"] * kills + ["ESCAPED"] * (4 - kills)
    return Match(t=T0, map="Coal Tower", role="killer", character=killer,
                 opp=[Player(role="survivor", status=s) for s in stats],
                 perks=[[p.replace(" ", "_"), p] for p in perks], addons=[[a, a] for a in addons],
                 offering=[offering, offering] if offering else [], power=[power, power] if power else [])


def _survivor(escaped, perks, item=None):
    return Match(t=T0, map="Badham", role="survivor", character="Meg Thomas",
                 status="ESCAPED" if escaped else "SACRIFICED", perks=[[p, p] for p in perks],
                 power=[item, item] if item else [])


BUILD = ["Lethal Pursuer", "Pop Goes the Weasel", "Grim Embrace", "Deadlock"]


def test_items_count_use_share_and_compare_with_and_without():
    ms = [_killer(4, BUILD, addons=["Kavanagh's"], power="Spencer's Last Breath"),
          _killer(2, BUILD, power="Spencer's Last Breath"),
          _killer(1, ["Lethal Pursuer", "Sloppy Butcher", "Jolt", "Corrupt Intervention"],
                  offering="Ebony Memento Mori", power="Spencer's Last Breath"),
          _survivor(True, ["Dead Hard", "Sprint Burst"], item="Toolbox"),
          _survivor(False, ["Sprint Burst"]),
          Match(t=T0, map="x", role="killer", opp=[])]                        # no loadout (older userscript)
    pairs = [(None, m) for m in ms]
    assert builds.with_loadout(pairs) == 5
    got = {(i.kind, i.role, i.name): i for i in builds.items(pairs)}
    lp = got[("perk", "killer", "Lethal Pursuer")]
    assert lp.n == 3 and lp.share == 1.0 and lp.mean == 7 / 3 and lp.mean_without is None
    pop = got[("perk", "killer", "Pop Goes the Weasel")]
    assert pop.n == 2 and abs(pop.share - 2 / 3) < 1e-9 and pop.mean == 3 and pop.mean_without == 1
    assert got[("addon", "killer", "Kavanagh's")].n == 1
    assert got[("offering", "killer", "Ebony Memento Mori")].mean == 1
    assert got[("power", "killer", "Spencer's Last Breath")].n == 3
    sb = got[("perk", "survivor", "Sprint Burst")]
    assert sb.n == 2 and sb.mean == 0.5 and got[("perk", "survivor", "Dead Hard")].mean_without == 0
    assert got[("power", "survivor", "Toolbox")].mean == 1
    assert builds.items(pairs)[0].name == "Lethal Pursuer"                 # most used first


def test_builds_are_the_same_four_perks_in_any_order_per_killer():
    ms = [_killer(4, BUILD), _killer(2, list(reversed(BUILD))), _killer(3, BUILD, killer="The Blight"),
          _killer(0, BUILD[:3])]                                            # three perks: not a build
    found = builds.builds([(None, m) for m in ms])
    assert len(found) == 1                                                 # the Blight build: only once
    b = found[0]
    assert b.character == "The Nurse" and b.n == 2 and b.mean == 3
    assert b.perks == tuple(sorted(BUILD, key=str.lower))
    assert builds.builds([(None, m) for m in ms], minimum=1)[-1].character == "The Blight"


def test_a_perk_is_grouped_by_the_pages_id_and_shows_the_newest_name():
    a = _killer(4, BUILD)
    b = _killer(2, BUILD)
    b.perks = [[r[0], r[1].upper()] for r in b.perks]                      # same ids, another page language
    got = [i for i in builds.items([(None, a), (None, b)]) if i.kind == "perk"]
    assert len(got) == 4 and all(i.n == 2 for i in got)


def test_emblems_scores_and_ratings_per_role_from_the_real_layout():
    # values as userscript 3 saved them for the user (1.8.51): page names upper case, qualities as words
    k1 = _killer(0, BUILD)
    k1.emblems = [["Emblem_Killer_Chaser", "CHASER", "Iridescent"], ["Emblem_Killer_Devout", "DEVOUT", "Bronze"]]
    k1.score = {"DBD_SlasherScoreCat_Hunter": 10000.0, "DBD_SlasherScoreCat_Brutality": 9000.0}
    k1.killer_status = "THE ENTITY HUNGERS..."
    k2 = _killer(1, BUILD)
    k2.emblems = [["Emblem_Killer_Chaser", "CHASER", "Gold"], ["Emblem_Killer_Devout", "DEVOUT", "None"],
                  ["x", "ODD", "Shiny"]]                                     # unknown quality: left out
    k2.score = {"DBD_SlasherScoreCat_Hunter": 8000.0}
    k2.killer_status = "BRUTAL KILLER"
    s = _survivor(True, ["Dead Hard"])
    s.emblems = [["Emblem_Survivor_Benevolent", "BENEVOLENT", "Gold"]]
    s.score = {"DBD_CamperScoreCat_Objectives": 4911.0}
    k3 = _killer(0, BUILD)
    k3.killer_status = "THE ENTITY HUNGERS..."
    pairs = [(None, m) for m in (k1, k2, s, k3)]
    em = {(e.role, e.name): e for e in builds.emblems(pairs)}
    assert set(em) == {("killer", "Chaser"), ("killer", "Devout"), ("survivor", "Benevolent")}
    chaser = em[("killer", "Chaser")]
    assert chaser.n == 2 and chaser.mean == 3.5 and chaser.share("Iridescent") == 0.5
    assert em[("killer", "Devout")].mean == 0.5
    sc = {(x.role, x.name): x for x in builds.scores(pairs)}
    assert sc[("killer", "Hunter")].mean == 9000 and sc[("killer", "Hunter")].full == 0.5
    assert sc[("killer", "Brutality")].n == 1 and sc[("survivor", "Objectives")].full == 0.0
    assert builds.ratings(pairs) == [("The Entity Hungers...", 2), ("Brutal Killer", 1)]



def _items_before_1_11_10(pairs):
    """The algorithm until 1.11.10 (every item through every match of its role), kept as the reference."""
    matches = [m for _r, m in pairs if m.role in ("killer", "survivor") and builds.has_loadout(m)]
    per_role = {role: [m for m in matches if m.role == role] for role in ("killer", "survivor")}
    found = {}
    for m in matches:
        for kind in builds.KINDS:
            for ref in builds._refs(m, kind):
                it = found.setdefault((kind, m.role, builds._key(ref)), [ref[1] or ref[0], 0, [], []])
                it[0] = ref[1] or it[0]
    for (kind, role, key), it in found.items():
        for m in per_role[role]:
            used = any(builds._key(r) == key for r in builds._refs(m, kind))
            res = builds.result(m)
            if used:
                it[1] += 1
            if res is not None:
                (it[2] if used else it[3]).append(res)
    return {k: (v[0], v[1], (sum(v[2]) / len(v[2]) if v[2] else None), (sum(v[3]) / len(v[3]) if v[3] else None))
            for k, v in found.items()}


def test_the_one_pass_items_give_what_the_old_loop_gave():
    """1.11.10: items() in one pass (190 → ~20 ms with 3000 matches) – the same counts, names and averages with and
    without each item as the old loop, on random loadouts incl. the same perk twice, unknown results, both roles."""
    import random
    rnd = random.Random(11)
    perks = [[f"p{i}", f"Perk {i}"] for i in range(12)]
    ms = []
    for i in range(300):
        role = rnd.choice(["killer", "survivor"])
        opp = ([Player(role="survivor", status=rnd.choice(["Sacrificed", "Escaped", "Killed", ""]))
                for _ in range(4)] if role == "killer" else [])
        ms.append(Match(t=float(i), map="M", role=role, status=rnd.choice(["Escaped", "Sacrificed", ""]),
                          opp=opp, perks=[rnd.choice(perks) for _ in range(rnd.randint(0, 4))],
                          addons=[[f"a{rnd.randint(0, 5)}", ""]] if rnd.random() < 0.5 else [],
                          offering=[f"o{rnd.randint(0, 3)}", "Opfer"] if rnd.random() < 0.3 else []))
    pairs = [(None, m) for m in ms]
    old = _items_before_1_11_10(pairs)
    new = {(it.kind, it.role, it.key): (it.name, it.n, it.mean, it.mean_without) for it in builds.items(pairs)}
    assert new.keys() == old.keys()
    for k in old:
        assert new[k][:2] == old[k][:2], k
        for a, c in zip(new[k][2:], old[k][2:]):
            assert (a is None and c is None) or abs(a - c) < 1e-9, k
