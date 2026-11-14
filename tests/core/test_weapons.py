"""Choosing a weapon (after M7, Azzinax play test flag 21: "I can't choose which
weapon to use"). A found weapon has stats; taking it adds it to the weapons,
wielding it makes attacks use it, and the Cursed Warhammer subtracts 1d4 from
every hit's damage."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

HAMMER = {"id": "hammer", "name": "Bejewelled Warhammer", "location": "hall",
          "weapon": {"ability": "STR", "damage_dice": "1d8", "damage_type": "bludgeoning",
                     "damage_penalty": "1d4"}}
ADVENTURE = tiny_adventure(items=[*BASE["items"], HAMMER])


def do(state, faces=(), **intent):
    resolution = resolve_intent(state, ADVENTURE, "hero", Intent(**intent), FixedDice(list(faces)))
    return resolution, apply_events(state, resolution.events)


def holding_the_hammer():
    return do(initial_state(ADVENTURE, [fighter()], BESTIARY), action="take",
              target_id="hammer")[1]


def test_a_found_weapon_joins_the_weapons_not_the_pack():
    hero = holding_the_hammer().party["hero"]
    assert [w.name for w in hero.weapons] == ["Greatsword", "Bejewelled Warhammer"]
    assert "hammer" not in hero.inventory
    assert hero.wielded is None  # still the greatsword, the first weapon


def test_wielding_a_carried_weapon_makes_the_attacks_use_it_with_its_curse():
    resolution, armed = do(holding_the_hammer(), action="wield", item_id="hammer")
    assert [e.type for e in resolution.events] == ["weapon_wielded"]
    in_den = armed.model_copy(update={"party_location": "den"})
    # Initiative: hero 15+2, goblin 1+2; attack d20 15 hits; d8 5, +3 STR, -d4 3.
    resolution, _ = do(in_den, [15, 1, 15, 5, 3], action="attack", target_id="goblin")
    attack = next(e for e in resolution.events if e.type == "attack_rolled")
    damage = next(e for e in resolution.events if e.type == "damage_dealt")
    assert attack.attack_name == "Bejewelled Warhammer"
    assert (damage.rolls, damage.penalty_rolls, damage.amount) == ([5], [3], 5)


def test_the_curse_never_heals_the_target():
    _, armed = do(holding_the_hammer(), action="wield", item_id="hammer")
    in_den = armed.model_copy(update={"party_location": "den"})
    resolution, _ = do(in_den, [15, 1, 15, 1, 4], action="attack", target_id="goblin")
    damage = next(e for e in resolution.events if e.type == "damage_dealt")
    assert damage.amount == 0  # 1 + 3 - 4


def test_only_a_carried_weapon_can_be_wielded():
    start = initial_state(ADVENTURE, [fighter()], BESTIARY)
    resolution, _ = do(start, action="wield", item_id="hammer")
    assert resolution.blocked == "You are not carrying that weapon."


def test_wielding_the_weapon_already_in_hand_changes_nothing():
    resolution, _ = do(holding_the_hammer(), action="wield", item_id="greatsword")
    assert resolution.blocked == "You already wield the Greatsword."


def test_the_scene_says_which_weapon_is_in_hand():
    _, armed = do(holding_the_hammer(), action="wield", item_id="hammer")
    weapons = build_scene(armed, ADVENTURE).party[0].weapons
    assert [(w.weapon_id, w.name, w.wielded) for w in weapons] == [
        ("greatsword", "Greatsword", False), ("hammer", "Bejewelled Warhammer", True)]
    assert weapons[1].stats == "1d8 bludgeoning, -1d4 damage"
    assert "hammer" in build_scene(armed, ADVENTURE).valid_ids()
