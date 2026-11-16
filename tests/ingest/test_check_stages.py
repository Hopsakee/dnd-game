"""check <stage> for the stages after the map: each file against its schema and
against what the stages before it decided (places from the map, creatures)."""

import pytest

from adventure_ingest.check import check

from .conftest import STAGES


@pytest.mark.parametrize("stage", ["locations", "creatures", "items", "challenges"])
def test_the_gold_stages_pass(stage):
    assert check(stage, STAGES) == []


def test_a_place_on_the_map_without_text(stages):
    stages.edit("locations.yaml", lambda s: s.update(locations=s["locations"][:-1]))
    assert "'c6' is on the map but has no name or description" in check("locations", stages.path)


def test_a_hidden_exit_that_is_no_opening(stages):
    stages.edit("locations.yaml", lambda s: s["locations"][1].update(hidden_exits={"1d": 12}))
    assert "hidden exit '1d' is no opening of 'room1'" in check("locations", stages.path)


def test_a_creature_somewhere_off_the_map(stages):
    stages.edit("creatures.yaml", lambda s: s["creatures"][0].update(location="room9"))
    assert "'goblin_1' is in 'room9', which is no place" in check("creatures", stages.path)


def test_a_creature_without_a_stat_block(stages):
    stages.edit("creatures.yaml", lambda s: s["creatures"][0].update(srd_ref="giant_rat"))
    assert ("'goblin_1' has no stat block 'giant_rat' in the SRD or creatures/"
            in check("creatures", stages.path))


def test_a_lock_on_no_opening(stages):
    stages.edit("items.yaml", lambda s: s["locks"][0].update(exit="2c"))
    assert "lock on '2c', which is no opening" in check("items", stages.path)


def test_an_item_carried_by_nobody(stages):
    stages.edit("items.yaml", lambda s: next(
        i for i in s["items"] if i["id"] == "iron_key").update(carried_by="goblin_9"))
    assert "'iron_key' is carried by 'goblin_9', who is no creature" in check(
        "items", stages.path)


def test_a_challenge_at_no_place_or_creature(stages):
    stages.edit("challenges.yaml", lambda s: s["challenges"][0].update(at="mill"))
    assert "challenge 'turn_millstone' is at 'mill', which is no place or creature" in check(
        "challenges", stages.path)


def test_a_stage_that_breaks_its_schema(stages):
    stages.edit("challenges.yaml", lambda s: s["challenges"][0].update(ability="STRENGTH"))
    problems = check("challenges", stages.path)
    assert len(problems) == 1 and problems[0].startswith("challenges.yaml: Input should be")


# M8.5: a place inside a room is not on the map; its inner exits are.

def test_a_place_inside_a_room_named_after_another_room(stages):
    def change(s):
        loft = next(p for p in s["locations"] if p["id"] == "room2_loft")
        loft["within"] = "room3"
    stages.edit("locations.yaml", change)
    problems = check("locations", stages.path)
    assert "'room2_loft' is inside 'room3', so its id starts with 'room3_'" in problems
    assert ("inner exit 'room2_up' leads from 'room2' to 'room2_loft'; an inner exit leads "
            "between a room and a place inside it") in problems


def test_an_inner_exit_named_against_the_convention(stages):
    stages.edit("locations.yaml", lambda s: next(
        p for p in s["locations"] if p["id"] == "room2")["inner_exits"][0].update(id="ladder"))
    assert "inner exit 'ladder' of 'room2' should be named 'room2_up'" in check(
        "locations", stages.path)
