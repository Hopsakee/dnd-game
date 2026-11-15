"""verify, the hard gate (BUILD_PLAN M8): the converter is not done until its
adventure passes."""

from adventure_ingest.verify import verify

from .conftest import AZZINAX, GOLD, SRD, needs_azzinax


def test_the_test_books_gold_passes():
    assert verify(GOLD, SRD) == []


def drop_exits(*exit_ids):
    def change(adventure):
        for location in adventure["locations"]:
            location["exits"] = [e for e in location["exits"] if e["id"] not in exit_ids]
    return change


def test_a_location_no_way_leads_to_is_unreachable(gold):
    gold.edit("adventure.yaml", drop_exits("c4c", "c5b"))
    assert "'c6' cannot be reached from 'yard'" in verify(gold.path, SRD)


def test_a_key_behind_the_door_it_opens(gold):
    def change(adventure):
        key = next(i for i in adventure["items"] if i["id"] == "iron_key")
        del key["carried_by"]
        key["location"] = "room3"
        adventure["locks"] = [lock for lock in adventure["locks"] if lock["exit"] in ("2b", "c1b")]
        adventure["locks"] += [{"exit": e, "key": "iron_key"} for e in ("3b", "c5c", "3a", "c3b")]
    gold.edit("adventure.yaml", change)
    assert "key 'iron_key' lies behind a lock it opens" in verify(gold.path, SRD)


def test_a_door_locked_on_one_side_only(gold):
    gold.edit("adventure.yaml", lambda a: a.update(
        locks=[lock for lock in a["locks"] if lock["exit"] != "c3b"]))
    assert "'3a' is locked but its other side 'c3b' is not" in verify(gold.path, SRD)


def test_the_two_sides_of_a_door_locked_differently(gold):
    gold.edit("adventure.yaml", lambda a: a["locks"][-1].update(force_dc=10))
    assert "the two sides of '3b' and 'c5c' are locked differently" in verify(gold.path, SRD)


def test_a_win_nobody_can_reach(gold):
    def change(adventure):
        for lock in adventure["locks"]:
            if lock["exit"] in ("3b", "c5c"):
                lock.pop("force_dc")
                lock["opens_on_flag"] = "millstone_turned"
        next(loc for loc in adventure["locations"] if loc["id"] == "room2")["checks"][0]["dc"] = 12
        next(i for i in adventure["items"] if i["id"] == "iron_key").update(carried_by="old_grist")
    gold.edit("adventure.yaml", change)
    assert "win flag 'ledger_recovered' cannot be set" in verify(gold.path, SRD)


def test_a_monster_without_a_stat_block(gold):
    gold.edit("adventure.yaml", lambda a: a["entities"][0].update(srd_ref="giant_rat"))
    assert "'goblin_1' has no stat block 'giant_rat'" in verify(gold.path, SRD)


def test_an_obstacle_beyond_a_level_one_hero(gold):
    gold.edit("adventure.yaml", lambda a: a["locks"][-1].update(force_dc=26))
    gold.edit("adventure.yaml", lambda a: a["locks"][-2].update(force_dc=26))
    assert ("'3b' needs DC 26 to force; a level-1 hero rolls 25 at most"
            in verify(gold.path, SRD))


def test_an_opening_on_the_map_without_its_exit(gold):
    gold.edit("adventure.yaml", drop_exits("c4c"))
    assert "opening 'c4c' on the map is no exit of 'c4'" in verify(gold.path, SRD)


def test_an_exit_whose_door_disagrees_with_the_map(gold):
    gold.edit("adventure.yaml", lambda a: a["locations"][1]["exits"][0].update(door=False))
    assert "exit '1a' is a door on the map but not in adventure.yaml" in verify(gold.path, SRD)


def test_an_exit_leading_elsewhere_than_the_map_says(gold):
    gold.edit("adventure.yaml", lambda a: a["locations"][1]["exits"][1].update(to="room4"))
    assert "exit '1b' leads to 'room4', but on the map it meets 'c2a' in 'c2'" in verify(
        gold.path, SRD)


@needs_azzinax
def test_the_gold_azzinax_passes():
    assert verify(AZZINAX, SRD) == []
