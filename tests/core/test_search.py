"""M2.5: hidden things, passive Perception and the search action.

The test Fighter has WIS 12 and is proficient in Perception (+2), so his
passive Perception is 10 + 1 + 2 = 13 and an active search is d20 + 3."""

import pytest

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import build_scene
from solo_dm.core.turn.session import GameSession

from ..fakes import FixedDice
from .adventure_fixture import ADVENTURE as BASE
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

LOCATIONS = [
    {"id": "hall", "name": "Hall", "description": "A hall.",
     "exits": [{"id": "hall_to_den", "to": "den", "direction": "east"},
               {"id": "hall_to_shrine", "to": "shrine", "direction": "north"}]},
    {"id": "den", "name": "Den", "description": "A den.",
     "exits": [{"id": "den_to_hall", "to": "hall", "direction": "west"},
               {"id": "den_to_cellar", "to": "cellar", "direction": "down",
                "hidden": {"dc": 15}}]},
    {"id": "shrine", "name": "Shrine", "description": "A shrine.",
     "exits": [{"id": "shrine_to_hall", "to": "hall", "direction": "south"}]},
    {"id": "cellar", "name": "Cellar", "description": "A cellar.",
     "exits": [{"id": "cellar_to_den", "to": "den", "direction": "up"}]},
]
ITEMS = [
    {"id": "iron_key", "name": "Iron Key", "carried_by": "goblin"},
    {"id": "amulet", "name": "Amulet", "location": "shrine", "on_take": {"set_flag": "got_amulet"}},
    {"id": "coin", "name": "Coin", "location": "den", "hidden": {"dc": 13}},  # passive finds it
    {"id": "gem", "name": "Gem", "location": "den", "hidden": {"dc": 15}},  # needs a search
]
ADVENTURE = tiny_adventure(
    locations=LOCATIONS,
    items=ITEMS,
    entities=[{"id": "goblin", "srd_ref": "goblin_warrior", "location": "den",
               "attitude": "indifferent"}],
)


def _start():
    return initial_state(ADVENTURE, [fighter()], BESTIARY)


def _do(state, action, target=None, faces=()):
    resolution = resolve_intent(
        state, ADVENTURE, "hero", Intent(action=action, target_id=target), FixedDice(list(faces))
    )
    return resolution, apply_events(state, resolution.events)


def _in_den():
    return _do(_start(), "move", "hall_to_den")[1]


def _scene_ids(state):
    return build_scene(state, ADVENTURE).valid_ids()


# ── Adventure schema ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "item, message",
    [
        ({"id": "x", "name": "X"}, "'x' needs a location or carried_by"),
        ({"id": "x", "name": "X", "location": "den", "carried_by": "goblin"},
         "'x' has both a location and carried_by"),
        ({"id": "x", "name": "X", "carried_by": "nobody"}, "'x' is carried by unknown entity"),
        ({"id": "x", "name": "X", "carried_by": "goblin", "hidden": {"dc": 10}},
         "'x' is carried, so it cannot be hidden"),
    ],
)
def test_item_placement_is_validated(item, message):
    with pytest.raises(ValueError, match=message):
        tiny_adventure(items=[*BASE["items"], item])


# ── What the party can perceive ─────────────────────────────────────────────

def test_hidden_and_carried_things_are_not_in_the_scene():
    state = _do(_start(), "move", "hall_to_den", faces=[])[1]
    ids = _scene_ids(state)
    assert "gem" not in ids and "den_to_cellar" not in ids  # hidden, not yet found
    assert "iron_key" not in ids  # on the goblin's body
    assert "goblin" in ids


def test_a_hidden_exit_cannot_be_used_before_it_is_found():
    resolution, after = _do(_in_den(), "move", "den_to_cellar")
    assert resolution.blocked and after.party_location == "den"


# ── Passive Perception on entering ──────────────────────────────────────────

def test_entering_a_room_finds_what_passive_perception_meets():
    resolution, state = _do(_start(), "move", "hall_to_den")
    found = [(e.target_id, e.method) for e in resolution.events if e.type == "hidden_found"]
    assert found == [("coin", "passive")]  # DC 13 <= 13; the gem and the exit are DC 15
    assert "coin" in _scene_ids(state)


def test_a_hidden_thing_in_the_start_room_is_noticed_at_the_start():
    items = [*ITEMS, {"id": "pin", "name": "Pin", "location": "hall", "hidden": {"dc": 12}}]
    adventure = tiny_adventure(locations=LOCATIONS, items=items)
    state = initial_state(adventure, [fighter()], BESTIARY)
    assert "pin" in build_scene(state, adventure).valid_ids()


# ── Active search ───────────────────────────────────────────────────────────

def test_a_successful_search_finds_everything_its_total_meets():
    resolution, state = _do(_in_den(), "search", faces=[12])  # 12 + 3 = 15
    check = resolution.events[0]
    assert (check.type, check.ability, check.skill, check.total) == (
        "check_rolled", "WIS", "perception", 15)
    found = {e.target_id for e in resolution.events if e.type == "hidden_found"}
    assert found == {"gem", "den_to_cellar"}
    assert {"gem", "den_to_cellar"} <= _scene_ids(state)


def test_a_failed_search_finds_nothing_and_can_be_tried_again():
    resolution, state = _do(_in_den(), "search", faces=[11])  # 14 < 15
    assert [e.type for e in resolution.events] == ["check_rolled"]
    assert "gem" not in _scene_ids(state)
    resolution, state = _do(state, "search", faces=[20])
    assert "gem" in _scene_ids(state)


def test_a_search_only_finds_things_in_this_room():
    resolution, _ = _do(_start(), "search", faces=[20])  # in the hall; the gem is in the den
    assert [e.type for e in resolution.events] == ["check_rolled"]


def test_searching_a_dead_creature_needs_no_roll_and_drops_what_it_carried():
    state = _in_den()
    goblin = state.creatures["goblin"].model_copy(update={"alive": False, "hp": 0})
    state = state.model_copy(update={"creatures": {"goblin": goblin}})
    resolution, state = _do(state, "search", "goblin", faces=[])
    assert [(e.type, e.item_ids) for e in resolution.events] == [("body_searched", ["iron_key"])]
    assert "iron_key" in _scene_ids(state)
    _, state = _do(state, "take", "iron_key")
    assert state.party["hero"].inventory == ("iron_key",)


def test_a_living_creature_cannot_be_searched():
    resolution, _ = _do(_in_den(), "search", "goblin")
    assert resolution.blocked == "You cannot search the Goblin Warrior while it is alive."


# ── The model never sees what has not been found ────────────────────────────

class SpyLLM:
    """Records every scene the interpreter and narrator receive."""

    def __init__(self, intents):
        self._intents = list(intents)
        self.scenes = []

    def interpret(self, player_input, scene, previous_error=None):
        self.scenes.append(scene)
        return self._intents.pop(0)

    def narrate(self, outcome, scene):
        self.scenes.append(scene)
        self.scenes.append(outcome)
        return "ok"


def test_neither_interpreter_nor_narrator_sees_unfound_things():
    llm = SpyLLM([{"action": "move", "target_id": "hall_to_den"}, {"action": "look"}])
    session = GameSession(ADVENTURE, _start(), llm, FixedDice([]))
    session.play_turn("hero", "go east")
    session.play_turn("hero", "look")
    seen = " ".join(s.model_dump_json() for s in llm.scenes)
    assert "coin" in seen  # found passively
    for unfound in ("gem", "Gem", "den_to_cellar", "Cellar", "iron_key", "Iron Key"):
        assert unfound not in seen
