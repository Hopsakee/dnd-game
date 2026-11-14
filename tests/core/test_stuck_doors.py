"""M7: a stuck door is forced open with Strength (Athletics) against its DC
(Revenge of Azzinax: "Stuck Simple Wooden Door").

The test Fighter has STR 16 (+3) and is proficient in Athletics (+2): d20 + 5."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

ADVENTURE = tiny_adventure(
    entities=[], locks=[{"exit": "hall_to_shrine", "force_dc": 12}],
)


def _open(state, faces):
    resolution = resolve_intent(state, ADVENTURE, "hero",
                                Intent(action="open", target_id="hall_to_shrine"),
                                FixedDice(faces))
    return resolution, apply_events(state, resolution.events)


def test_a_strong_enough_shove_forces_a_stuck_door():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    resolution, after = _open(start, [7])  # 7 + 5 = 12, meets DC 12
    check, unlocked = resolution.events
    assert (check.ability, check.skill, check.total, check.success) == (
        "STR", "athletics", 12, True)
    assert (unlocked.exit_id, unlocked.method) == ("hall_to_shrine", "forced")
    assert "hall_to_shrine" not in after.locked_exits


def test_a_failed_shove_leaves_it_stuck_and_can_be_tried_again():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    resolution, after = _open(start, [6])  # 11 < 12
    assert [e.type for e in resolution.events] == ["check_rolled"]
    assert "hall_to_shrine" in after.locked_exits
    assert _open(after, [20])[1].locked_exits == ()


def test_a_locked_door_without_force_dc_still_cannot_be_opened_by_force():
    locked = tiny_adventure(entities=[])  # the fixture's lock: key or pick, no force
    start = initial_state(locked, [fighter()], BESTIARY)
    resolution = resolve_intent(start, locked, "hero",
                                Intent(action="open", target_id="hall_to_shrine"), FixedDice([]))
    assert resolution.blocked == "The way north is locked."


def test_a_stuck_door_is_called_stuck_not_locked():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    def blocked(action):
        return resolve_intent(start, ADVENTURE, "hero",
                              Intent(action=action, target_id="hall_to_shrine"),
                              FixedDice([])).blocked
    assert blocked("move") == "The way north is stuck; force it open."
    assert blocked("unlock") == "It is not locked but stuck; force it open."
    north = next(e for e in build_scene(start, ADVENTURE).exits if e.direction == "north")
    assert (north.locked, north.stuck) == (False, True)


def test_a_door_forced_from_one_side_is_open_from_the_other_too():
    # One door, two exits (Azzinax: 5a and 6b are the same iron door). Found in
    # the opening-name pass, 2026-11-14.
    both_sides = tiny_adventure(entities=[], locks=[
        {"exit": "hall_to_shrine", "force_dc": 12}, {"exit": "shrine_to_hall", "force_dc": 12}])
    start = initial_state(both_sides, [fighter()], BESTIARY)
    resolution = resolve_intent(start, both_sides, "hero",
                                Intent(action="open", target_id="hall_to_shrine"),
                                FixedDice([20]))
    assert apply_events(start, resolution.events).locked_exits == ()
