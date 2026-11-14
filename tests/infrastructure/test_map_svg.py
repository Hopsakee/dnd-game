"""The web app's node map: rooms placed by the direction of their exits."""

from solo_dm.composition_root import build_session
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.web.map_svg import grid_positions, map_svg


def explored(*locations, at="hall"):
    session = build_session("core_five_rooms", SeededDice(0), FakeLLM())
    state = session.state.model_copy(
        update={"discovered_locations": locations, "party_location": at})
    return state, session.adventure


def test_rooms_sit_one_step_away_in_the_direction_of_the_exit():
    state, adventure = explored("entrance", "hall", "guard_room", "storeroom", "shrine")
    assert grid_positions(state, adventure) == {
        "entrance": (0, 0), "hall": (0, -1), "guard_room": (1, -1),
        "storeroom": (-1, -1), "shrine": (0, -2),
    }


def test_only_discovered_rooms_are_drawn_and_the_partys_room_is_marked():
    state, adventure = explored("entrance", "hall")
    svg = str(map_svg(state, adventure))
    assert "Pillared Hall" in svg and "Guard Room" not in svg
    assert svg.count('class="room current"') == 1
