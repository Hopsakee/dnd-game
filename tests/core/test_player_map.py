"""The book's player map (after M7, Azzinax flag 22: "It would be better to have
parts of the actual map instead of this map-scheme"). map.yaml gives each
location its cells on the map's grid; only the cells of discovered locations,
and the openings out of them, are shown."""

import pytest

from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.player_view import revealed_map

MAP = {
    "image": "dm.png", "player_image": "player.png", "cell_px": 20,
    "locations": {
        "hall": {"cells": [[1, 1, 3, 4]], "openings": [
            {"id": "hall_a", "kind": "door", "direction": "east", "at": [90, 50],
             "meets": "passage_a"}]},
        "passage": {"cells": [[5, 2, 6, 2]], "openings": [
            {"id": "passage_a", "kind": "door", "direction": "west", "at": [90, 50],
             "meets": "hall_a"}]},
    },
    "off_map": {"road": {"openings": []}},
}


def at(location: str, *discovered: str) -> GameState:
    return GameState(party={}, party_location=location,
                     discovered_locations=(location, *discovered))


def test_only_discovered_locations_and_their_openings_are_shown():
    seen = revealed_map(at("hall"), AdventureMap.model_validate(MAP))
    assert seen.seen == [(20, 20, 60, 80), (80, 40, 20, 20)]  # x, y, width, height
    assert seen.here == [(20, 20, 60, 80)]


def test_the_view_is_cut_to_what_is_seen_plus_a_cell_around_it():
    seen = revealed_map(at("passage", "hall"), AdventureMap.model_validate(MAP))
    assert seen.view == (0, 0, 160, 120)
    assert seen.here == [(100, 40, 40, 20)]


def test_off_the_map_nothing_is_here_and_nothing_seen_yet_shows_nothing():
    assert revealed_map(at("road"), AdventureMap.model_validate(MAP)) is None
    seen = revealed_map(at("road", "hall"), AdventureMap.model_validate(MAP))
    assert seen.here == [] and seen.seen


def test_without_a_player_image_there_is_no_player_map():
    plain = {k: v for k, v in MAP.items() if k not in ("player_image", "cell_px")}
    assert revealed_map(at("hall"), AdventureMap.model_validate(plain)) is None


def test_a_player_image_needs_a_grid_and_a_plain_file_name():
    with pytest.raises(ValueError, match="cell_px"):
        AdventureMap.model_validate({**MAP, "cell_px": None})
    with pytest.raises(ValueError, match="file name"):
        AdventureMap.model_validate({**MAP, "player_image": "../secret.png"})
