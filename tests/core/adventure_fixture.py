"""A tiny adventure written in Python for core tests (the YAML ones are tested
through the loader)."""

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.state.models import AttackProfile, CreatureStatBlock

ADVENTURE = {
    "id": "tiny",
    "title": "Tiny",
    "start_location": "hall",
    "win_condition": {"flag": "got_amulet"},
    "locations": [
        {"id": "hall", "name": "Hall", "description": "A hall.",
         "exits": [{"id": "hall_to_den", "to": "den", "direction": "east"},
                   {"id": "hall_to_shrine", "to": "shrine", "direction": "north"}]},
        {"id": "den", "name": "Den", "description": "A den.",
         "exits": [{"id": "den_to_hall", "to": "hall", "direction": "west"}]},
        {"id": "shrine", "name": "Shrine", "description": "A shrine.",
         "exits": [{"id": "shrine_to_hall", "to": "hall", "direction": "south"}]},
    ],
    "entities": [{"id": "goblin", "srd_ref": "goblin_warrior", "location": "den",
                  "attitude": "hostile"}],
    "items": [
        {"id": "iron_key", "name": "Iron Key", "location": "den"},
        {"id": "amulet", "name": "Amulet", "location": "shrine",
         "on_take": {"set_flag": "got_amulet"}},
    ],
    "locks": [{"exit": "hall_to_shrine", "key": "iron_key", "pick_dc": 15}],
}

BESTIARY = {
    "goblin_warrior": CreatureStatBlock(
        stat_block_id="goblin_warrior", name="Goblin Warrior", armor_class=15, hit_points=10,
        initiative_bonus=2,
        abilities={"STR": 8, "DEX": 15, "CON": 10, "INT": 10, "WIS": 8, "CHA": 8},
        attacks=[AttackProfile(name="Scimitar", attack_bonus=4, damage_dice="1d6",
                               damage_modifier=2, damage_type="slashing")],
    )
}


def tiny_adventure(**changes) -> Adventure:
    return Adventure.model_validate({**ADVENTURE, **changes})
