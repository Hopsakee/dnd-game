"""Flags from Jelle's play test of Revenge of Azzinax on the phone, 2026-11-14
(brain playtest-flags.md, 16-28)."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

LAIR = tiny_adventure(
    start_location="den",
    entities=[
        {"id": "boss", "srd_ref": "goblin_warrior", "location": "den", "attitude": "indifferent",
         "activity": "sits sharpening a knife", "group": "lair"},
        {"id": "runt", "srd_ref": "goblin_warrior", "location": "den", "attitude": "indifferent",
         "group": "lair"},
    ],
)


def do(state, adventure, faces, **intent):
    resolution = resolve_intent(state, adventure, "hero", Intent(**intent), FixedDice(faces))
    return resolution, apply_events(state, resolution.events)


def test_what_a_creature_is_doing_lasts_only_until_the_fight(  # flag 25
):
    start = initial_state(LAIR, [fighter()], BESTIARY)
    boss = next(c for c in build_scene(start, LAIR).creatures if c.creature_id == "boss")
    assert boss.activity == "sits sharpening a knife"
    _, fighting = do(start, LAIR, [4] * 20, action="attack", target_id="boss")
    boss = next(c for c in build_scene(fighting, LAIR).creatures if c.creature_id == "boss")
    assert boss.activity is None


def test_attacking_one_of_a_group_brings_the_whole_group_into_the_fight():  # flag 24
    start = initial_state(LAIR, [fighter()], BESTIARY)
    resolution, after = do(start, LAIR, [4] * 20, action="attack", target_id="boss")
    assert {c: after.creatures[c].attitude for c in ("boss", "runt")} == {
        "boss": "hostile", "runt": "hostile"}
    started = next(e for e in resolution.events if e.type == "combat_started")
    assert set(started.turn_order) == {"hero", "boss", "runt"}


WITH_SPIRIT = tiny_adventure(guardian={"name": "Spiritus Magehunter", "rescues": 1})


def test_the_guardian_travels_along_and_can_be_talked_to():  # flag 16
    start = initial_state(WITH_SPIRIT, [fighter()], BESTIARY)
    scene = build_scene(start, WITH_SPIRIT)
    assert [(c.companion_id, c.name) for c in scene.companions] == [
        ("guardian", "Spiritus Magehunter")]
    assert "guardian" in scene.valid_ids()
    resolution, _ = do(start, WITH_SPIRIT, [], action="talk", target_id="guardian")
    assert resolution.blocked is None


def test_a_guardian_who_gave_his_last_rescue_is_gone():
    start = initial_state(WITH_SPIRIT, [fighter()], BESTIARY)
    spent = start.model_copy(update={"rescues_left": 0})
    assert build_scene(spent, WITH_SPIRIT).companions == []


def test_the_hero_can_start_with_an_item_of_his_own():  # flag 18: his own coins
    purse = {"id": "own_purse", "name": "Coin Purse", "carried_by": "party"}
    adventure = tiny_adventure(items=[*BASE["items"], purse])
    start = initial_state(adventure, [fighter()], BESTIARY)
    assert "own_purse" in start.party["hero"].inventory
    assert "own_purse" not in start.items_carried
