"""Jelle's second M3 play test, 2026-11-13 (playtest-flags.md 8): what can be
smelt or heard from a neighbouring room reaches the scene, by direction, only
as the adventure wrote it, and never through a hidden exit."""

from solo_dm.core.adventure.initial_state import initial_state

from .adventure_fixture import ADVENTURE, BESTIARY, tiny_adventure
from .builders import fighter


def _scene(**den_changes):
    hall, den, shrine = ADVENTURE["locations"]
    den = {**den, "senses": "woodsmoke and the smell of old meat", **den_changes}
    adventure = tiny_adventure(locations=[hall, den, shrine])
    return initial_state(adventure, [fighter()], BESTIARY), adventure


def test_a_neighbouring_rooms_senses_reach_the_scene_with_their_direction():
    from solo_dm.core.turn.scene import build_scene

    state, adventure = _scene()
    nearby = build_scene(state, adventure).nearby
    assert [(n.direction, n.senses) for n in nearby] == [
        ("east", "woodsmoke and the smell of old meat")]


def test_a_room_without_senses_adds_nothing():
    from solo_dm.core.turn.scene import build_scene

    state, adventure = _scene(senses=None)
    assert build_scene(state, adventure).nearby == []


def test_senses_do_not_give_away_a_hidden_exit():
    from solo_dm.core.turn.scene import build_scene

    hall, den, shrine = ADVENTURE["locations"]
    hidden_way = {**hall["exits"][0], "hidden": {"dc": 20}}
    hall = {**hall, "exits": [hidden_way, hall["exits"][1]]}
    den = {**den, "senses": "woodsmoke"}
    adventure = tiny_adventure(locations=[hall, den, shrine])
    state = initial_state(adventure, [fighter()], BESTIARY)
    assert build_scene(state, adventure).nearby == []
