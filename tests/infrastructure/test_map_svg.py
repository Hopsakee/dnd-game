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


def door_marks(svg: str) -> list[str]:
    import re
    return re.findall(r'<rect class="(door[^"]*)"', svg)


def test_doors_show_on_the_map_with_whether_they_are_shut():
    # Azzinax flag 17: "It would be good to show where the doors are on the map."
    state, adventure = explored("entrance", "hall", "guard_room", "shrine")
    svg = str(map_svg(state, adventure))
    # The gate to the entrance and the sun door to the shrine; the doorway east is no door.
    assert sorted(door_marks(svg)) == ["door", "door locked"]
    opened = state.model_copy(update={"locked_exits": ()})
    assert sorted(door_marks(str(map_svg(opened, adventure)))) == ["door", "door"]


def test_a_door_mark_sits_in_the_gap_next_to_its_room_not_on_another_room():
    import re

    from solo_dm.core.adventure.schema import Adventure
    from solo_dm.core.state.models import GameState
    # Azzinax: room 3's door north leads to room 5, two cells up; the line passes
    # the cave entrance between them, and the door mark sat on its name.
    adventure = Adventure.model_validate({
        "id": "x", "title": "X", "start_location": "cave", "win_condition": {"flag": "f"},
        "locations": [
            {"id": "cave", "name": "Cave", "description": ".", "exits": [
                {"id": "c_n", "to": "hall", "direction": "north"},
                {"id": "c_s", "to": "fountain", "direction": "south"}]},
            {"id": "hall", "name": "Hall", "description": ".", "exits": [
                {"id": "h_s", "to": "cave", "direction": "south"},
                {"id": "h_d", "to": "fountain", "direction": "south", "door": True}]},
            {"id": "fountain", "name": "Fountain", "description": ".", "exits": [
                {"id": "f_n", "to": "cave", "direction": "north"},
                {"id": "f_d", "to": "hall", "direction": "north", "door": True}]}],
        "items": [{"id": "i", "name": "I", "location": "cave", "on_take": {"set_flag": "f"}}]})
    state = GameState(party={}, party_location="fountain",
                      discovered_locations=("cave", "hall", "fountain"))
    svg = str(map_svg(state, adventure))
    boxes = [tuple(map(int, b)) for b in re.findall(
        r'<rect x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)" rx', svg)]
    doors = [tuple(map(int, d)) for d in re.findall(
        r'class="door[^"]*" x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"', svg)]
    assert len(boxes) == 3 and len(doors) == 1
    for dx, dy, dw, dh in doors:
        for bx, by, bw, bh in boxes:
            assert dx + dw <= bx or bx + bw <= dx or dy + dh <= by or by + bh <= dy
