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
