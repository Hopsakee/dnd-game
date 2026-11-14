"""M7: hazards and traps (Revenge of Azzinax: falling rocks, a spike pit).

A hazard sits in a location. One with a notice DC is a hidden thing: passive
Perception on entering (or a search) finds it, and a noticed hazard is avoided.
Otherwise it springs once when the party enters: a saving throw against its DC,
damage on a failure.

The test Fighter: passive Perception 13, DEX save d20 + 2, 12 HP."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter


def with_hazard(**hazard):
    rocks = {"id": "falling_rocks", "name": "Falling Rocks",
             "save": {"ability": "DEX", "dc": 15}, "damage_dice": "1d4",
             "damage_type": "bludgeoning", **hazard}
    den = {**BASE["locations"][1], "hazards": [rocks]}
    return tiny_adventure(entities=[], locations=[BASE["locations"][0], den,
                                                  BASE["locations"][2]])


def enter_den(adventure, faces, hero=None):
    start = initial_state(adventure, [hero or fighter()], BESTIARY)
    resolution = resolve_intent(start, adventure, "hero",
                                Intent(action="move", target_id="hall_to_den"), FixedDice(faces))
    return [e.type for e in resolution.events], apply_events(start, resolution.events)


def back_and_forth(adventure, state, faces):
    for exit_id in ("den_to_hall", "hall_to_den"):
        resolution = resolve_intent(state, adventure, "hero",
                                    Intent(action="move", target_id=exit_id), FixedDice(faces))
        state = apply_events(state, resolution.events)
    return state


def test_an_unnoticed_trap_springs_and_a_failed_save_costs_hit_points():
    adventure = with_hazard()
    types, after = enter_den(adventure, [12, 3])  # save 12 + 2 = 14 < 15; damage 3
    assert types[-3:] == ["hazard_sprung", "saving_throw_rolled", "damage_dealt"]
    assert after.party["hero"].hp == 9


def test_a_sprung_trap_does_not_spring_again():
    adventure = with_hazard()
    _, after = enter_den(adventure, [12, 3])
    assert back_and_forth(adventure, after, []).party["hero"].hp == 9  # no dice needed


def test_a_successful_save_takes_no_damage():
    types, after = enter_den(with_hazard(), [13])  # 13 + 2 = 15
    assert types[-2:] == ["hazard_sprung", "saving_throw_rolled"]
    assert after.party["hero"].hp == 12


def test_a_trap_noticed_on_entering_is_avoided():
    adventure = with_hazard(hidden={"dc": 10})  # passive Perception 13 meets it
    types, after = enter_den(adventure, [])
    assert "hazard_sprung" not in types and "hidden_found" in types
    assert after.party["hero"].hp == 12
    assert [h.name for h in build_scene(after, adventure).hazards] == ["Falling Rocks"]


def test_a_trap_too_well_hidden_to_notice_springs():
    types, _ = enter_den(with_hazard(hidden={"dc": 15}), [1, 2])
    assert "hazard_sprung" in types and "hidden_found" not in types


def test_a_trap_that_drops_the_hero_to_zero_loses_the_adventure():
    types, after = enter_den(with_hazard(), [1, 4], hero=fighter(hp=3))
    assert types[-3:] == ["damage_dealt", "character_defeated", "adventure_lost"]
    assert after.outcome == "lost"


def test_two_traps_in_one_room_both_count_against_the_same_hit_points():
    pit = {"id": "spike_pit", "name": "Spike Pit", "save": {"ability": "DEX", "dc": 10},
           "damage_dice": "1d4", "damage_type": "piercing"}
    rocks = {"id": "falling_rocks", "name": "Falling Rocks",
             "save": {"ability": "DEX", "dc": 15}, "damage_dice": "1d4",
             "damage_type": "bludgeoning"}
    den = {**BASE["locations"][1], "hazards": [rocks, pit]}
    adventure = tiny_adventure(entities=[], locations=[BASE["locations"][0], den,
                                                       BASE["locations"][2]])
    types, after = enter_den(adventure, [1, 3, 1, 3], hero=fighter(hp=5))  # 3, then 3 more
    assert types[-2:] == ["character_defeated", "adventure_lost"]
