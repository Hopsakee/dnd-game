"""eval: a conversion against its gold, field by field, as precision (how much
of what it wrote is right) and recall (how much of the gold it found)."""

from adventure_ingest.evaluate import evaluate

from .conftest import GOLD


def test_the_gold_against_itself_scores_full_marks():
    report = evaluate(GOLD, GOLD)
    assert {name: (s.precision, s.recall) for name, s in report.items()} == {
        name: (1.0, 1.0) for name in ("locations", "links", "monsters", "items", "locks",
                                      "checks", "hazards", "goal", "stat blocks",
                                      "map places", "map openings")}


def test_a_conversion_that_misses_the_talk_and_misjudges_the_stuck_door(gold):
    def change(adventure):
        grist = next(e for e in adventure["entities"] if e["id"] == "old_grist")
        del grist["checks"]
        for lock in adventure["locks"]:
            if lock["exit"] in ("3b", "c5c"):
                lock["force_dc"] = 10
    gold.edit("adventure.yaml", change)
    report = evaluate(gold.path, GOLD)
    checks, locks = report["checks"], report["locks"]
    assert (checks.precision, checks.recall) == (1.0, 2 / 3)
    assert checks.missing == ["CHA (persuasion) DC 15 at room3, after defeating 2"]
    assert (locks.precision, locks.recall) == (6 / 8, 6 / 8)
    assert locks.extra == ["3b: force DC 10", "c5c: force DC 10"]


def test_items_are_compared_by_what_and_where_not_by_their_names(gold):
    gold.edit("adventure.yaml", lambda a: [i.update(id=f"thing_{n}", name=f"Thing {n}")
                                           for n, i in enumerate(a["items"])])
    gold.edit("adventure.yaml", lambda a: a.update(locks=[
        {**lock, "key": "thing_3"} if "key" in lock else lock for lock in a["locks"]]))
    score = evaluate(gold.path, GOLD)["items"]
    assert (score.precision, score.recall) == (1.0, 1.0)


def test_a_map_that_folds_a_corridor_away(gold):
    def fold_c2(m):
        del m["locations"]["c2"]
        rooms = m["locations"]
        rooms["room1"]["openings"][1].update(meets="4a")
        rooms["room4"]["openings"][0].update(meets="1b")
    gold.edit("map.yaml", fold_c2)
    score = evaluate(gold.path, GOLD)["map openings"]
    # 24 gold openings, off the map too: c2a and c2b gone, 1b and 4a now meet each other.
    assert (score.precision, score.recall) == (20 / 22, 20 / 24)
    assert score.missing == ["1b archway meets c2a", "4a archway meets c2b",
                             "c2a archway meets 1b", "c2b archway meets 4a"]
    assert score.extra == ["1b archway meets 4a", "4a archway meets 1b"]
