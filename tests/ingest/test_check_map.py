"""check map: the map step's file on its own, before anything is built on it
(the map convention, BUILD_PLAN M8)."""

from adventure_ingest.check import check

from .conftest import AZZINAX, GOLD, needs_azzinax


def opening(folder, opening_id):
    data = folder.read("map.yaml")
    places = {**data["locations"], **data.get("off_map", {})}
    return data, next(o for p in places.values() for o in p["openings"] if o["id"] == opening_id)


def change_opening(folder, opening_id, **fields):
    data, found = opening(folder, opening_id)
    found.update(fields)
    folder.write("map.yaml", data)


def test_the_gold_map_passes():
    assert check("map", GOLD) == []


@needs_azzinax
def test_the_gold_azzinax_map_passes():
    assert check("map", AZZINAX) == []


def test_an_opening_that_meets_nothing(gold):
    change_opening(gold, "c4c", meets="c7a")
    assert "'c4c' meets 'c7a', which is no opening" in check("map", gold.path)


def test_an_opening_whose_partner_does_not_name_it_back(gold):
    change_opening(gold, "c4c", meets="c5a")
    assert "'c4c' meets 'c5a', but 'c5a' meets 'c4b'" in check("map", gold.path)


def test_partners_of_different_kinds(gold):
    change_opening(gold, "c2a", kind="door")
    assert "'c2a' is a door but its partner '1b' is an archway" in check("map", gold.path)


def test_partners_in_different_places_on_the_map(gold):
    change_opening(gold, "c2a", at=[140, 300])
    assert "'c2a' is at [140, 300] but its partner '1b' at [140, 280]" in check("map", gold.path)


def test_an_opening_named_after_another_place(gold):
    change_opening(gold, "c4c", id="c5d")
    change_opening(gold, "c6a", meets="c5d")
    assert "'c5d' is in 'c4', so its name starts with 'c4'" in check("map", gold.path)


def test_openings_lettered_out_of_order(gold):
    change_opening(gold, "1c", id="1d")
    change_opening(gold, "yard_a", meets="1d")
    assert "the openings of 'room1' are lettered 1a, 1b, 1d; expected 1a, 1b, 1c" in check(
        "map", gold.path)


def test_two_openings_of_one_place_with_the_same_direction(gold):
    change_opening(gold, "c4c", direction="east")
    assert "'c4' has two openings to the east: c4b, c4c" in check("map", gold.path)


def test_cells_that_belong_to_two_places(gold):
    gold.edit("map.yaml", lambda m: m["locations"]["c1"].update(cells=[[6, 4, 11, 4]]))
    assert "cell [6, 4] belongs to both 'room1' and 'c1'" in check("map", gold.path)
