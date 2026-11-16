"""M8.5: advantage and disadvantage, and a condition that gives it (Revenge of
Azzinax: the mushroom gas, CON 15 save or disadvantage on the next attack roll,
ability check or saving throw; no damage).

Every d20 a character rolls goes through one roll: with advantage or
disadvantage two dice, keeping the higher or the lower; both at once cancel
(SRD 5.2). The condition is used up by the next d20 its bearer rolls.

The test Fighter: CON save d20 + 4, STR (Athletics) d20 + 5, greatsword +5."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.rules.rules_d20 import roll_d20
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

GAS = {"id": "spore_gas", "name": "Spore Gas", "save": {"ability": "CON", "dc": 15},
       "condition": "disadvantage_on_next_roll"}


def gassed_den(entities=()):
    den = {**BASE["locations"][1], "hazards": [GAS]}
    return tiny_adventure(entities=list(entities),
                          locations=[BASE["locations"][0], den, BASE["locations"][2]])


def act(adventure, state, intent, faces):
    resolution = resolve_intent(state, adventure, "hero", intent, FixedDice(faces))
    assert resolution.blocked is None, resolution.blocked
    return resolution.events, apply_events(state, resolution.events)


def enter_gas(faces):
    adventure = gassed_den()
    start = initial_state(adventure, [fighter()], BESTIARY)
    return adventure, *act(adventure, start, Intent(action="move", target_id="hall_to_den"), faces)


def test_a_failed_save_against_the_gas_gives_the_condition_and_no_damage():
    _, events, after = enter_gas([10])  # 10 + 4 = 14 < 15
    assert [e.type for e in events][-3:] == ["hazard_sprung", "saving_throw_rolled",
                                             "condition_gained"]
    assert after.party["hero"].conditions == ("disadvantage_on_next_roll",)
    assert after.party["hero"].hp == 12


def test_a_successful_save_against_the_gas_gives_nothing():
    _, events, after = enter_gas([11])
    assert "condition_gained" not in [e.type for e in events]
    assert after.party["hero"].conditions == ()


def test_the_condition_shows_in_the_scene():
    adventure, _, after = enter_gas([10])
    assert build_scene(after, adventure).party[0].conditions == ["disadvantage_on_next_roll"]


def test_the_next_check_rolls_two_dice_keeps_the_lower_and_ends_the_condition():
    adventure, _, gassed = enter_gas([10])
    events, after = act(adventure, gassed, Intent(
        action="ability_check", ability="STR", skill="athletics", task_category="easy"), [17, 4])
    check = events[0]
    assert (check.d20_rolls, check.d20, check.roll_mode) == ([17, 4], 4, "disadvantage")
    assert check.total == 9
    assert after.party["hero"].conditions == ()
    events, _ = act(adventure, after, Intent(
        action="ability_check", ability="STR", skill="athletics", task_category="easy"), [4])
    assert (events[0].d20_rolls, events[0].roll_mode) == ([4], None)


def test_the_next_attack_roll_has_disadvantage_too():
    goblin = {"id": "goblin", "srd_ref": "goblin_warrior", "location": "den",
              "attitude": "indifferent"}
    adventure = gassed_den([goblin])
    start = initial_state(adventure, [fighter()], BESTIARY)
    _, gassed = act(adventure, start, Intent(action="move", target_id="hall_to_den"), [10])
    # initiative: hero 20 + 2, goblin 1 + 2; attack 19 and 3: 3 + 5 = 8 misses AC 15
    events, after = act(adventure, gassed, Intent(action="attack", target_id="goblin"),
                        [20, 1, 19, 3, 1, 1, 1])
    attack = next(e for e in events if e.type == "attack_rolled")
    assert (attack.d20_rolls, attack.d20, attack.hit) == ([19, 3], 3, False)
    assert after.party["hero"].conditions == ()


def test_the_next_saving_throw_has_disadvantage_too():
    rocks = {"id": "falling_rocks", "name": "Falling Rocks",
             "save": {"ability": "DEX", "dc": 10}, "damage_dice": "1d4",
             "damage_type": "bludgeoning"}
    den = {**BASE["locations"][1], "hazards": [GAS]}
    shrine = {**BASE["locations"][2], "hazards": [rocks]}
    hall = {**BASE["locations"][0], "exits": [
        {"id": "hall_to_den", "to": "den", "direction": "east"},
        {"id": "hall_to_shrine", "to": "shrine", "direction": "north"}]}
    adventure = tiny_adventure(entities=[], locks=[], locations=[hall, den, shrine])
    start = initial_state(adventure, [fighter()], BESTIARY)
    _, gassed = act(adventure, start, Intent(action="move", target_id="hall_to_den"), [10])
    _, back = act(adventure, gassed, Intent(action="move", target_id="den_to_hall"), [])
    events, after = act(adventure, back, Intent(action="move", target_id="hall_to_shrine"),
                        [15, 2, 3])  # DEX save: 2 + 2 = 4 fails; damage 3
    save = next(e for e in events if e.type == "saving_throw_rolled")
    assert (save.d20_rolls, save.d20, save.success) == ([15, 2], 2, False)
    assert after.party["hero"].hp == 9 and after.party["hero"].conditions == ()


def test_advantage_keeps_the_higher_die():
    assert roll_d20(FixedDice([4, 17]), advantage=True) == (17, [4, 17], "advantage")


def test_advantage_and_disadvantage_cancel_to_one_die():
    assert roll_d20(FixedDice([4]), advantage=True, disadvantage=True) == (4, [4], None)


def test_a_hazard_needs_damage_or_a_condition():
    import pytest
    from pydantic import ValidationError

    bare = {k: v for k, v in GAS.items() if k != "condition"}
    den = {**BASE["locations"][1], "hazards": [bare]}
    with pytest.raises(ValidationError, match="damage or a condition"):
        tiny_adventure(entities=[], locations=[BASE["locations"][0], den, BASE["locations"][2]])
