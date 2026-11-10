from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene

from ..fakes import FixedDice
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

ADVENTURE = tiny_adventure()


def _start(*members):
    return initial_state(ADVENTURE, members or [fighter()], BESTIARY)


def _do(state, action, target=None, faces=(), actor="hero"):
    resolution = resolve_intent(
        state, ADVENTURE, actor, Intent(action=action, target_id=target), FixedDice(list(faces))
    )
    return resolution, apply_events(state, resolution.events)


def test_scene_shows_only_what_the_party_can_perceive():
    scene = build_scene(_start(), ADVENTURE)
    assert scene.location_id == "hall"
    # Exits to undiscovered rooms show a direction, not where they lead.
    assert [(e.exit_id, e.direction, e.leads_to, e.locked) for e in scene.exits] == [
        ("hall_to_den", "east", None, False), ("hall_to_shrine", "north", None, True),
    ]
    assert scene.creatures == [] and scene.items == []  # goblin and key are in the den
    assert "iron_key" not in scene.valid_ids() and "goblin" not in scene.valid_ids()


def test_a_locked_exit_blocks_movement_without_changing_state():
    resolution, after = _do(_start(), "move", "hall_to_shrine")
    assert resolution.blocked == "The way north is locked."
    assert after == _start()


def test_entering_a_room_with_a_hostile_creature_starts_combat():
    # Initiative: hero 15 + 2 beats goblin 1 + 2, so the hero acts first.
    resolution, after = _do(_start(), "move", "hall_to_den", faces=[15, 1])
    assert [e.type for e in resolution.events] == [
        "moved_to", "location_discovered", "combat_started", "turn_started",
    ]
    assert (after.party_location, after.in_combat) == ("den", True)
    assert build_scene(after, ADVENTURE).exits[0].leads_to == "Hall"


def test_kill_the_goblin_take_the_key_unlock_the_door_and_win():
    state = _do(_start(), "move", "hall_to_den", faces=[15, 1])[1]
    resolution, state = _do(state, "attack", "goblin", faces=[18, 6, 6])  # 15 damage
    assert resolution.events[-1].type == "combat_ended" and not state.in_combat
    state = _do(state, "take", "iron_key")[1]
    assert state.party["hero"].inventory == ("iron_key",)
    state = _do(state, "move", "den_to_hall")[1]
    resolution, state = _do(state, "unlock", "hall_to_shrine")
    assert resolution.events[0].method == "key"
    state = _do(state, "move", "hall_to_shrine")[1]
    resolution, state = _do(state, "take", "amulet")
    assert [e.type for e in resolution.events] == ["item_taken", "quest_flag_set", "adventure_won"]
    assert state.outcome == "won"


def test_without_the_key_the_lock_can_be_picked_with_a_dexterity_check():
    failed, state = _do(_start(), "unlock", "hall_to_shrine", faces=[12])  # 12 + 2 < 15
    assert [e.type for e in failed.events] == ["check_rolled"]
    assert state.locked_exits == ("hall_to_shrine",)
    picked, state = _do(state, "unlock", "hall_to_shrine", faces=[13])  # 13 + 2 = 15
    assert [e.type for e in picked.events] == ["check_rolled", "door_unlocked"]
    assert state.locked_exits == ()


def test_targets_outside_the_scene_and_actions_out_of_turn_are_blocked():
    assert _do(_start(), "take", "amulet")[0].blocked == "There is no amulet here."
    two = _start(fighter("ally"), fighter("hero"))
    # ally 19 + 2, goblin 1 + 2, hero 2 + 2: after entering it is the ally's turn.
    state = _do(two, "move", "hall_to_den", faces=[19, 2, 1])[1]
    assert _do(state, "attack", "goblin", actor="hero")[0].blocked == "It is not your turn."


def test_leaving_during_combat_ends_it_without_attacks_of_opportunity():
    state = _do(_start(), "move", "hall_to_den", faces=[15, 1])[1]
    resolution, state = _do(state, "move", "den_to_hall")
    assert [e.type for e in resolution.events] == ["combat_ended", "moved_to"]
    assert (state.in_combat, state.party_location) == (False, "hall")
