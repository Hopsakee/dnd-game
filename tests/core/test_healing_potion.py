"""M7: a healing potion (Revenge of Azzinax: "a healing potion (2d4+2)"). Drunk
anywhere, it heals the drinker up to their maximum and is used up."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

ADVENTURE = tiny_adventure(
    entities=[],
    items=[{"id": "potion", "name": "Potion of Healing", "location": "hall",
            "effect": {"heal": "2d4+2"}}, *BASE["items"]],
)


def drink(hp, faces):
    state = initial_state(ADVENTURE, [fighter(hp=hp)], BESTIARY)
    state = apply_events(state, resolve_intent(state, ADVENTURE, "hero", Intent(
        action="take", target_id="potion"), FixedDice([])).events)
    resolution = resolve_intent(state, ADVENTURE, "hero",
                                Intent(action="use_item", item_id="potion"), FixedDice(faces))
    return resolution, apply_events(state, resolution.events)


def test_drinking_the_potion_heals_and_uses_it_up():
    resolution, after = drink(hp=3, faces=[2, 3])  # 2 + 3 + 2 = 7
    used, healed = resolution.events
    assert (used.item_id, used.used_up) == ("potion", True)
    assert (healed.target_id, healed.rolls, healed.amount) == ("hero", [2, 3], 7)
    assert after.party["hero"].hp == 10
    assert "potion" not in after.party["hero"].inventory


def test_healing_stops_at_maximum_hit_points():
    resolution, after = drink(hp=10, faces=[4, 4])  # 10 would be 20; max is 12
    assert resolution.events[1].amount == 2
    assert after.party["hero"].hp == 12
