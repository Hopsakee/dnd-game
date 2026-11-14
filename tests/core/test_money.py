"""Money as amounts (after M7, Azzinax play test flags 18-19): coins are counted
per denomination, picking up a purse adds its coins, and paying one coin at the
fountain leaves the rest ("I threw one piece of silver in the fountain. I
received 8. Now I have none.")."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.models import Coins
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import COINS_ID, build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HALL = {**BASE["locations"][0], "uses": [{"pay": 1, "set_flag": "fountain_paid"}]}
ADVENTURE = tiny_adventure(
    entities=[],
    locations=[HALL, *BASE["locations"][1:]],
    items=[{"id": "purse", "name": "Worn Purse", "location": "hall", "coins": {"sp": 8}},
           *BASE["items"][1:]],
    locks=[{"exit": "hall_to_shrine", "opens_on_flag": "fountain_paid"}],
)


def do(state, action, **intent):
    resolution = resolve_intent(state, ADVENTURE, "hero", Intent(action=action, **intent),
                                FixedDice([]))
    return resolution, apply_events(state, resolution.events)


def start(coins: Coins | None = None):
    hero = fighter().model_copy(update={"coins": coins or Coins()})
    return initial_state(ADVENTURE, [hero], BESTIARY)


def test_taking_a_purse_adds_its_coins_and_no_purse_item():
    resolution, after = do(start(Coins(gp=2)), "take", target_id="purse")
    assert [e.type for e in resolution.events] == ["coins_taken"]
    assert after.party["hero"].coins == Coins(gp=2, sp=8)
    assert "purse" not in after.party["hero"].inventory
    assert "purse" not in after.items_on_floor


def test_paying_one_coin_spends_the_cheapest_and_keeps_the_rest():
    _, rich = do(start(Coins(gp=2)), "take", target_id="purse")
    resolution, after = do(rich, "use_item", item_id=COINS_ID)
    assert [e.type for e in resolution.events] == [
        "coins_spent", "quest_flag_set", "door_unlocked"]
    assert after.party["hero"].coins == Coins(gp=2, sp=7)


def test_without_coins_there_is_nothing_to_pay_with():
    resolution, _ = do(start(), "use_item", item_id=COINS_ID)
    assert resolution.blocked == "You have no coins."


def test_coins_cannot_be_spent_where_nothing_takes_them():
    moved = start(Coins(gp=1)).model_copy(update={"party_location": "den"})
    resolution, _ = do(moved, "use_item", item_id=COINS_ID)
    assert resolution.blocked == "Nothing here to spend coins on."


def test_the_scene_shows_the_coins_carried_as_one_thing_in_the_pack():
    hero = build_scene(start(Coins(gp=2, sp=7, cp=0)), ADVENTURE).party[0]
    coins = next(i for i in hero.inventory if i.item_id == COINS_ID)
    assert coins.name == "Coins (2 gp, 7 sp)"
    broke = build_scene(start(), ADVENTURE).party[0]
    assert not any(i.item_id == COINS_ID for i in broke.inventory)


def test_a_use_pays_coins_or_uses_an_item_not_both():
    import pytest
    with pytest.raises(ValueError, match="either an item or coins"):
        tiny_adventure(locations=[
            {**HALL, "uses": [{"item": "amulet", "pay": 1, "set_flag": "x"}]},
            *BASE["locations"][1:]])
