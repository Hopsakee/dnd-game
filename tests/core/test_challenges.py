"""Azzinax play test, 2026-11-14 (flag 27): a check the book sets in a room is a
challenge with a goal. The interpreter sees the goal, so any attempt at it
(climbing, cutting the ropes) rolls the book's check, not an unrelated one.

The test Fighter has DEX 14 (+2), not proficient in Acrobatics: d20 + 2."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HALL = {**BASE["locations"][0], "checks": [
    {"id": "free_min_soo", "goal": "reach the hanging platform and free Min-soo",
     "ability": "DEX", "skill": "acrobatics", "dc": 10,
     "on_success": {"set_flag": "got_amulet"}}]}
ADVENTURE = tiny_adventure(entities=[], locations=[HALL, *BASE["locations"][1:]])


def attempt(state, faces, ability="STR", skill="athletics"):
    resolution = resolve_intent(
        state, ADVENTURE, "hero",
        Intent(action="ability_check", target_id="free_min_soo", ability=ability, skill=skill,
               approach="cut the ropes", task_category="hard"),
        FixedDice(faces))
    return resolution, apply_events(state, resolution.events)


def test_the_scene_shows_the_goal_of_a_challenge():
    scene = build_scene(initial_state(ADVENTURE, [fighter()], BESTIARY), ADVENTURE)
    assert [(c.challenge_id, c.goal) for c in scene.challenges] == [
        ("free_min_soo", "reach the hanging platform and free Min-soo")]
    assert "free_min_soo" in scene.valid_ids()


def test_any_attempt_at_the_goal_rolls_the_books_check():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    resolution, after = attempt(start, [8])  # 8 + 2 = 10, meets DC 10
    check = resolution.events[0]
    assert (check.ability, check.skill, check.dc, check.success) == ("DEX", "acrobatics", 10, True)
    assert after.outcome == "won"


# Every check is a challenge (Jelle, 2026-11-14): a check without a goal only
# counted when the model happened to pick its exact ability, which is how
# Min-soo could not be freed. Now the adventure is refused at loading instead.

def test_an_adventure_with_a_check_without_a_goal_is_refused():
    import pytest
    from pydantic import ValidationError

    bare = {**BASE["locations"][0], "checks": [
        {"ability": "STR", "skill": "athletics", "on_success": {"set_flag": "got_amulet"}}]}
    with pytest.raises(ValidationError, match="goal"):
        tiny_adventure(entities=[], locations=[bare, *BASE["locations"][1:]])


GATE = tiny_adventure(entities=[
    {"id": "guard", "srd_ref": "goblin_warrior", "location": "hall", "attitude": "indifferent",
     "checks": [{"id": "get_past_guard", "goal": "talk the guard into letting you pass",
                 "ability": "CHA", "skill": "persuasion",
                 "on_success": {"set_flag": "got_amulet"}}]}])


def test_a_creature_challenge_is_shown_while_the_creature_is_here_and_alive():
    start = initial_state(GATE, [fighter()], BESTIARY)
    assert [(c.challenge_id, c.creature_id) for c in build_scene(start, GATE).challenges] == [
        ("get_past_guard", "guard")]
    dead = start.model_copy(update={"creatures": {
        "guard": start.creatures["guard"].model_copy(update={"alive": False})}})
    assert build_scene(dead, GATE).challenges == []


def test_bribing_or_deceiving_the_guard_rolls_the_books_check_against_his_attitude():
    start = initial_state(GATE, [fighter()], BESTIARY)
    resolution = resolve_intent(start, GATE, "hero", Intent(
        action="ability_check", target_id="get_past_guard", ability="CHA", skill="deception",
        approach="offer him a coin", task_category="medium"), FixedDice([15]))
    check = resolution.events[0]
    # No DC in the book: medium 15, indifferent +0 (plan 3.7). CHA 10: +0.
    assert (check.ability, check.skill, check.dc, check.total) == ("CHA", "persuasion", 15, 15)
    assert apply_events(start, resolution.events).outcome == "won"


def test_a_check_aimed_at_no_challenge_changes_nothing_even_with_the_right_ability():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    resolution = resolve_intent(start, ADVENTURE, "hero", Intent(
        action="ability_check", ability="DEX", skill="acrobatics", task_category="easy"),
        FixedDice([20]))
    assert [e.type for e in resolution.events] == ["check_rolled"]
