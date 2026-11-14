"""M3: the ability-check fallback (plan 3.7). The interpreter picks ability and
task category; Python sets the DC, rolls, and applies only consequences the
adventure data defines: since 2026-11-14 only through a challenge it aims at.

The test Fighter has STR 16 (+3, athletics proficient: +5) and CHA 10 (+0)."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.rules.rules_difficulty import fallback_dc
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.session import GameSession

from ..fakes import FixedDice, ScriptedLLM
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

ADVENTURE = tiny_adventure(
    entities=[{"id": "goblin", "srd_ref": "goblin_warrior", "location": "hall",
               "attitude": "indifferent",
               "checks": [{"id": "befriend", "goal": "win the goblin over", "ability": "CHA",
                           "on_success": {"set_flag": "goblin_allied"}}]}],
    locations=[
        {"id": "hall", "name": "Hall", "description": "A hall.",
         "exits": [{"id": "hall_to_shrine", "to": "shrine", "direction": "north"}],
         "checks": [{"id": "climb", "goal": "climb the wall", "ability": "STR",
                     "skill": "athletics", "on_success": {"set_flag": "got_amulet"}}]},
        {"id": "shrine", "name": "Shrine", "description": "A shrine.",
         "exits": [{"id": "shrine_to_hall", "to": "hall", "direction": "south"}]},
    ],
    items=[{"id": "amulet", "name": "Amulet", "location": "shrine",
            "on_take": {"set_flag": "got_amulet"}}],
    locks=[],
)


def _start():
    return initial_state(ADVENTURE, [fighter()], BESTIARY)


def _check(**fields) -> Intent:
    return Intent(action="ability_check", **fields)


def test_python_maps_the_task_category_to_a_dc():
    assert [fallback_dc(c, None) for c in ("trivial", "easy", "medium", "hard")] == [
        5, 10, 15, 20]


def test_a_creatures_attitude_moves_the_dc():
    assert fallback_dc("medium", "hostile") == 20
    assert fallback_dc("medium", "indifferent") == 15
    assert fallback_dc("medium", "friendly") == 10


def test_a_check_without_a_consequence_rolls_and_changes_nothing_else():
    state = _start()
    intent = _check(ability="DEX", task_category="easy", approach="juggle three stones")
    result = resolve_intent(state, ADVENTURE, "hero", intent, FixedDice([9]))
    (check,) = result.events
    assert (check.type, check.ability, check.dc, check.total, check.success) == (
        "check_rolled", "DEX", 10, 11, True)


def test_a_missing_task_category_counts_as_medium():
    intent = _check(ability="INT")
    (check,) = resolve_intent(_start(), ADVENTURE, "hero", intent, FixedDice([10])).events
    assert check.dc == 15


def test_success_against_a_creature_sets_the_flag_the_adventure_defines():
    intent = _check(ability="CHA", skill="persuasion", target_id="befriend", task_category="easy")
    events = resolve_intent(_start(), ADVENTURE, "hero", intent, FixedDice([10])).events
    assert [e.type for e in events] == ["check_rolled", "quest_flag_set"]
    assert events[0].dc == 10  # easy, indifferent
    assert "goblin_allied" in apply_events(_start(), events).quest_flags


def test_failure_sets_nothing():
    intent = _check(ability="CHA", target_id="befriend", task_category="easy")
    events = resolve_intent(_start(), ADVENTURE, "hero", intent, FixedDice([3])).events
    assert [e.type for e in events] == ["check_rolled"]


def test_a_check_aimed_at_the_creature_but_not_its_challenge_sets_nothing():
    aimed = _check(ability="CHA", target_id="goblin", task_category="easy")
    events = resolve_intent(_start(), ADVENTURE, "hero", aimed, FixedDice([20])).events
    assert [e.type for e in events] == ["check_rolled"]


def test_a_check_that_sets_the_win_flag_wins():
    intent = _check(ability="STR", target_id="climb", task_category="medium")
    events = resolve_intent(_start(), ADVENTURE, "hero", intent, FixedDice([12])).events
    assert [e.type for e in events] == ["check_rolled", "quest_flag_set", "adventure_won"]


def test_a_check_without_an_ability_is_blocked():
    result = resolve_intent(_start(), ADVENTURE, "hero", _check(), FixedDice([]))
    assert result.blocked and result.events == []


def test_the_turn_log_tags_fallback_turns():
    llm = ScriptedLLM([{"action": "ability_check", "ability": "DEX", "task_category": "easy"},
                       {"action": "look"}])
    session = GameSession(ADVENTURE, _start(), llm, FixedDice([15]))
    assert session.play_turn("hero", "I juggle").fallback is True
    assert session.play_turn("hero", "look around").fallback is False


def test_adventure_check_flags_count_for_the_win_condition():
    adventure = tiny_adventure(
        win_condition={"flag": "goblin_allied"},
        entities=[{"id": "goblin", "srd_ref": "goblin_warrior", "location": "hall",
                   "attitude": "indifferent",
                   "checks": [{"id": "befriend", "goal": "win the goblin over",
                               "ability": "CHA", "on_success": {"set_flag": "goblin_allied"}}]}],
    )
    assert adventure.win_condition.flag == "goblin_allied"


def test_a_dc_the_adventure_gives_wins_over_the_task_category():
    # M7: books state DCs ("DC 10 Acrobatics check to get on the platform").
    from .adventure_fixture import ADVENTURE as BASE

    shrine = {**BASE["locations"][2], "checks": [
        {"id": "leap", "goal": "leap onto the altar", "ability": "DEX", "skill": "acrobatics",
         "dc": 10, "on_success": {"set_flag": "got_amulet"}}]}
    adventure = tiny_adventure(entities=[], locks=[],
                               locations=[*BASE["locations"][:2], shrine])
    state = initial_state(adventure, [fighter()], BESTIARY)
    state = apply_events(state, resolve_intent(state, adventure, "hero", Intent(
        action="move", target_id="hall_to_shrine"), FixedDice([])).events)
    resolution = resolve_intent(state, adventure, "hero", _check(
        ability="DEX", target_id="leap", task_category="hard"), FixedDice([8]))
    check = resolution.events[0]
    assert (check.dc, check.total, check.success) == (10, 10, True)  # 8 + DEX 2
