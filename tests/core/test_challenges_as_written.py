"""M8.5: a challenge as the book sets it (Revenge of Azzinax, the room 4
platform): DC 10 Acrobatics, a 10 ft fall on a failure (1d6 bludgeoning, SRD
5.2), DC 5 for every attempt after a failed one; success puts the hero on the
platform.

The test Fighter: DEX (Acrobatics) d20 + 2, 12 HP."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HALL, DEN, SHRINE = BASE["locations"]
LEAP = {"id": "leap_to_ledge", "goal": "leap onto the ledge", "ability": "DEX",
        "skill": "acrobatics", "dc": 10, "retry_dc": 5,
        "on_failure": {"damage_dice": "1d6", "damage_type": "bludgeoning"},
        "on_success": {"set_flag": "on_ledge", "move_to": "shrine"}}
ADVENTURE = tiny_adventure(
    entities=[], locks=[], win_condition={"flag": "got_amulet"},
    locations=[{**HALL, "checks": [LEAP]}, DEN, SHRINE])


def leap(state, faces):
    resolution = resolve_intent(state, ADVENTURE, "hero", Intent(
        action="ability_check", target_id="leap_to_ledge", ability="DEX", skill="acrobatics",
        task_category="medium"), FixedDice(faces))
    assert resolution.blocked is None, resolution.blocked
    return resolution.events, apply_events(state, resolution.events)


def start(hp=12):
    return initial_state(ADVENTURE, [fighter(hp=hp)], BESTIARY)


def test_a_failed_attempt_costs_the_fall():
    events, after = leap(start(), [7, 4])  # 7 + 2 = 9 < 10; fall 4
    assert [e.type for e in events] == ["check_rolled", "challenge_failed", "damage_dealt"]
    assert after.party["hero"].hp == 8
    assert after.party_location == "hall"


def test_after_a_failure_every_attempt_has_the_retry_dc():
    _, after = leap(start(), [7, 4])
    events, after = leap(after, [3])  # 3 + 2 = 5 meets DC 5
    assert (events[0].dc, events[0].success) == (5, True)


def test_success_moves_the_hero_there():
    events, after = leap(start(), [8])
    assert [e.type for e in events] == ["check_rolled", "quest_flag_set", "moved_to",
                                        "location_discovered"]
    assert after.party_location == "shrine"
    assert "on_ledge" in after.quest_flags


def test_a_fall_that_drops_the_hero_to_zero_loses_the_adventure():
    events, after = leap(start(hp=3), [1, 5])
    assert [e.type for e in events][-2:] == ["character_defeated", "adventure_lost"]
    assert after.outcome == "lost"
