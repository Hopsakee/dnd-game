import pytest
from pydantic import ValidationError

from solo_dm.core.adventure.initial_state import initial_state

from .adventure_fixture import ADVENTURE, BESTIARY, tiny_adventure
from .builders import fighter


def test_valid_adventure_loads():
    assert tiny_adventure().start_location == "hall"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start_location": "nowhere"}, "start_location 'nowhere'"),
        ({"locks": [{"exit": "no_exit", "key": "iron_key"}]}, "lock exit 'no_exit'"),
        ({"locks": [{"exit": "hall_to_shrine", "key": "no_key"}]}, "lock key 'no_key'"),
        ({"items": [*ADVENTURE["items"], {"id": "hall", "name": "X", "location": "hall"}]},
         "duplicate id 'hall'"),
        ({"win_condition": {"flag": "never_set"}}, "win flag 'never_set'"),
    ],
)
def test_broken_references_fail_loudly(changes, message):
    with pytest.raises(ValidationError, match=message):
        tiny_adventure(**changes)


def test_initial_state_places_party_creatures_items_and_locks():
    state = initial_state(tiny_adventure(), [fighter("ally"), fighter("hero")], BESTIARY)
    assert list(state.party) == ["ally", "hero"]
    assert (state.party_location, state.discovered_locations) == ("hall", ("hall",))
    assert state.creatures["goblin"].location == "den"
    assert state.creatures["goblin"].hp == 10
    assert state.items_on_floor == {"iron_key": "den", "amulet": "shrine"}
    assert state.locked_exits == ("hall_to_shrine",)
    assert (state.quest_flags, state.outcome) == ((), "playing")
