"""M8.5: one guard, `requires`, on what the book lets happen only after
something else (Revenge of Azzinax): the platform only once Azzinax is
defeated; Hye-young's potion only if the hero did not press for payment, the
8 sp only if he did not take the potion; the win on coming back to the village
with Min-soo freed.

requires: {flags: set, not_flags: not set, defeated: creatures dead}."""

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
GOBLIN = BASE["entities"][0]


def act(adventure, state, intent, faces=()):
    resolution = resolve_intent(state, adventure, "hero", intent, FixedDice(list(faces)))
    assert resolution.blocked is None, resolution.blocked
    return resolution.events, apply_events(state, resolution.events)


def start(adventure):
    return initial_state(adventure, [fighter()], BESTIARY)


# --- a challenge -------------------------------------------------------------

LEAP = {"id": "leap_to_ledge", "goal": "leap onto the ledge", "ability": "DEX",
        "skill": "acrobatics", "dc": 10, "on_success": {"set_flag": "got_amulet"},
        "requires": {"defeated": ["goblin"]}}
GUARDED = tiny_adventure(locations=[HALL, {**DEN, "checks": [LEAP]}, SHRINE])


def test_a_challenge_is_not_open_until_its_requirement_holds():
    state = start(GUARDED)
    _, state = act(GUARDED, state, Intent(action="move", target_id="hall_to_den"),
                   [20, 1, 1])  # hero first; the goblin waits
    assert build_scene(state, GUARDED).challenges == []
    # greatsword 2d6+3 (the 20 is a critical hit: 4d6) kills the goblin (10 HP)
    _, state = act(GUARDED, state, Intent(action="attack", target_id="goblin"), [20, 6, 6, 1, 1])
    assert not state.creatures["goblin"].alive
    assert [c.challenge_id for c in build_scene(state, GUARDED).challenges] == ["leap_to_ledge"]


# --- items -------------------------------------------------------------------

POTION = {"id": "potion", "name": "Potion of Healing", "location": "hall",
          "effect": {"heal": "2d4+2"}, "on_take": {"set_flag": "took_potion"},
          "requires": {"not_flags": ["pressed_for_pay"]}}
PAY = {"id": "pay", "name": "Eight Silver", "location": "hall", "coins": {"sp": 8},
       "on_take": {"set_flag": "pressed_for_pay"},
       "requires": {"not_flags": ["took_potion"]}}
OFFERS = tiny_adventure(entities=[], items=[*BASE["items"], POTION, PAY])


def visible_items(state, adventure=OFFERS):
    return sorted(i.item_id for i in build_scene(state, adventure).items)


def test_both_offers_are_there_until_one_is_taken():
    state = start(OFFERS)
    assert visible_items(state) == ["pay", "potion"]
    _, after = act(OFFERS, state, Intent(action="take", target_id="pay"))
    assert visible_items(after) == []
    _, after = act(OFFERS, state, Intent(action="take", target_id="potion"))
    assert visible_items(after) == []


def test_an_item_whose_requirement_fails_cannot_be_taken():
    _, state = act(OFFERS, start(OFFERS), Intent(action="take", target_id="pay"))
    blocked = resolve_intent(state, OFFERS, "hero", Intent(action="take", target_id="potion"),
                             FixedDice([]))
    assert blocked.blocked is not None


# --- a use -------------------------------------------------------------------

def test_a_use_does_nothing_until_its_requirement_holds():
    bell = {"id": "bell", "name": "Bell", "location": "hall"}
    hall = {**HALL, "uses": [{"item": "bell", "set_flag": "got_amulet",
                              "requires": {"flags": ["pressed_for_pay"]}}]}
    adventure = tiny_adventure(entities=[], locations=[hall, DEN, SHRINE],
                               items=[*BASE["items"], bell, PAY])
    _, state = act(adventure, start(adventure), Intent(action="take", target_id="bell"))
    blocked = resolve_intent(state, adventure, "hero",
                             Intent(action="use_item", item_id="bell"), FixedDice([]))
    assert blocked.blocked is not None
    _, state = act(adventure, state, Intent(action="take", target_id="pay"))
    _, state = act(adventure, state, Intent(action="use_item", item_id="bell"))
    assert state.outcome == "won"


# --- arriving ----------------------------------------------------------------

HOME = tiny_adventure(
    entities=[], win_condition={"flag": "back_home"},
    items=[{**BASE["items"][1], "on_take": {"set_flag": "got_amulet"}}],
    locks=[],
    locations=[{**HALL, "on_enter": [{"set_flag": "back_home",
                                      "requires": {"flags": ["got_amulet"]}}]},
               DEN, SHRINE])


def test_arriving_sets_a_flag_once_its_requirement_holds():
    state = start(HOME)
    _, state = act(HOME, state, Intent(action="move", target_id="hall_to_shrine"))
    _, state = act(HOME, state, Intent(action="move", target_id="shrine_to_hall"))
    assert state.outcome == "playing"  # not yet: the amulet is still in the shrine
    _, state = act(HOME, state, Intent(action="move", target_id="hall_to_shrine"))
    _, state = act(HOME, state, Intent(action="take", target_id="amulet"))
    events, state = act(HOME, state, Intent(action="move", target_id="shrine_to_hall"))
    assert [e.type for e in events][-2:] == ["quest_flag_set", "adventure_won"]
    assert state.outcome == "won"


# --- loading -----------------------------------------------------------------

def test_a_requirement_on_an_unknown_creature_is_refused():
    bad = {**LEAP, "requires": {"defeated": ["dragon"]}}
    with pytest.raises(ValidationError, match="dragon"):
        tiny_adventure(locations=[HALL, {**DEN, "checks": [bad]}, SHRINE])


def test_a_requirement_on_a_flag_nobody_sets_is_refused():
    bad = {**LEAP, "requires": {"flags": ["never_set"]}}
    with pytest.raises(ValidationError, match="never_set"):
        tiny_adventure(locations=[HALL, {**DEN, "checks": [bad]}, SHRINE])
