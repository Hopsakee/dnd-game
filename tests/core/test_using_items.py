"""M7: using an item at a place sets a flag, and locks can open on a flag
(Revenge of Azzinax: a coin tossed into the fountain opens all the doors of
room 3; the coin is gone)."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HALL = {**BASE["locations"][0],
        "uses": [{"item": "coin", "set_flag": "fountain_paid", "used_up": True}]}
ADVENTURE = tiny_adventure(
    entities=[],
    locations=[HALL, *BASE["locations"][1:]],
    items=[{"id": "coin", "name": "Copper Coin", "location": "hall"},
           *BASE["items"][1:]],
    locks=[{"exit": "hall_to_shrine", "opens_on_flag": "fountain_paid"},
           {"exit": "hall_to_den", "opens_on_flag": "fountain_paid"}],
)


def do(state, action, **intent):
    resolution = resolve_intent(state, ADVENTURE, "hero", Intent(action=action, **intent),
                                FixedDice([]))
    return resolution, apply_events(state, resolution.events)


def holding_the_coin():
    return do(initial_state(ADVENTURE, [fighter()], BESTIARY), "take", target_id="coin")[1]


def test_using_the_item_where_it_belongs_opens_every_door_on_that_flag():
    resolution, after = do(holding_the_coin(), "use_item", item_id="coin")
    assert [e.type for e in resolution.events] == [
        "item_used", "quest_flag_set", "door_unlocked", "door_unlocked"]
    assert after.locked_exits == ()
    assert "coin" not in after.party["hero"].inventory  # used up


def test_a_door_locked_on_both_sides_opens_once():
    # Azzinax: 3b and 5d are one door; the narrator should hear one door, not two.
    both = tiny_adventure(
        entities=[], locations=[HALL, *BASE["locations"][1:]],
        items=[{"id": "coin", "name": "Copper Coin", "location": "hall"}, *BASE["items"][1:]],
        locks=[{"exit": "hall_to_shrine", "opens_on_flag": "fountain_paid"},
               {"exit": "shrine_to_hall", "opens_on_flag": "fountain_paid"},
               {"exit": "hall_to_den", "opens_on_flag": "fountain_paid"}])
    start = initial_state(both, [fighter()], BESTIARY)
    start = apply_events(start, resolve_intent(start, both, "hero",
                         Intent(action="take", target_id="coin"), FixedDice([])).events)
    resolution = resolve_intent(start, both, "hero", Intent(action="use_item", item_id="coin"),
                                FixedDice([]))
    doors = [e.exit_id for e in resolution.events if e.type == "door_unlocked"]
    assert sorted(doors) == ["hall_to_den", "hall_to_shrine"]
    assert apply_events(start, resolution.events).locked_exits == ()


def test_doors_on_a_flag_cannot_be_unlocked_picked_or_forced():
    start = holding_the_coin()
    for action in ("unlock", "open"):
        assert do(start, action, target_id="hall_to_shrine")[0].blocked is not None


def test_an_item_with_no_use_here_does_nothing():
    state = holding_the_coin()
    state = do(state, "move", target_id="hall_to_den")
    assert state[0].blocked  # still locked: the coin is not used yet
    resolution, after = do(holding_the_coin().model_copy(update={"party_location": "den"}),
                           "use_item", item_id="coin")
    assert resolution.blocked == "Nothing here to use the Copper Coin on."
    assert "coin" in after.party["hero"].inventory


def test_only_a_carried_item_can_be_used():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    assert do(start, "use_item", item_id="coin")[0].blocked == "You are not carrying that."
