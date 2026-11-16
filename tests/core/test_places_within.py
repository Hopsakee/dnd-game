"""M8.5: a place inside a room (Revenge of Azzinax: the catwalk in room 8,
reached by a rope, DC 10 Athletics). It is a location with `within` its room;
a challenge puts the hero there, and its flag opens the way up and down, so
he can climb back down and up again without another roll.

The test Fighter: STR (Athletics) d20 + 5."""

import pytest
from pydantic import ValidationError

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HALL, DEN, SHRINE = BASE["locations"]
CLIMB = {"id": "climb_rope", "goal": "climb the rope to the ledge", "ability": "STR",
         "skill": "athletics", "dc": 10,
         "on_success": {"set_flag": "rope_climbed", "move_to": "ledge"}}
LEDGE = {"id": "ledge", "name": "Ledge", "description": "A narrow ledge.", "within": "hall",
         "exits": [{"id": "ledge_down", "to": "hall", "direction": "down"}]}
HALL_UP = {**HALL, "checks": [CLIMB],
           "exits": [*HALL["exits"], {"id": "hall_up", "to": "ledge", "direction": "up"}]}
CHEST = {"id": "chest", "name": "Small Chest", "location": "ledge"}
ADVENTURE = tiny_adventure(
    entities=[], locations=[HALL_UP, DEN, SHRINE, LEDGE], items=[*BASE["items"], CHEST],
    locks=[*BASE["locks"], {"exit": "hall_up", "opens_on_flag": "rope_climbed"},
           {"exit": "ledge_down", "opens_on_flag": "rope_climbed"}])


def act(state, intent, faces=()):
    resolution = resolve_intent(state, ADVENTURE, "hero", intent, FixedDice(list(faces)))
    assert resolution.blocked is None, resolution.blocked
    return apply_events(state, resolution.events)


def test_the_ledge_is_out_of_sight_from_below_and_the_way_up_is_shut():
    state = initial_state(ADVENTURE, [fighter()], BESTIARY)
    scene = build_scene(state, ADVENTURE)
    assert "chest" not in scene.valid_ids()
    assert next(e for e in scene.exits if e.exit_id == "hall_up").locked


def test_climbing_puts_the_hero_up_there_and_opens_the_way_both_ways():
    state = act(initial_state(ADVENTURE, [fighter()], BESTIARY), Intent(
        action="ability_check", target_id="climb_rope", ability="STR", skill="athletics",
        task_category="medium"), [5])
    assert state.party_location == "ledge"
    assert "chest" in build_scene(state, ADVENTURE).valid_ids()  # in plain view up here
    state = act(state, Intent(action="move", target_id="ledge_down"))
    state = act(state, Intent(action="move", target_id="hall_up"))
    assert state.party_location == "ledge"


def test_within_must_name_a_location():
    with pytest.raises(ValidationError, match="attic"):
        tiny_adventure(entities=[], locations=[HALL, DEN, SHRINE, {**LEDGE, "within": "attic"}])
