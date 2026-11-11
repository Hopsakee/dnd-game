from pathlib import Path

import pytest

from solo_dm.infrastructure.adventures.yaml_adventure_source import YamlAdventureSource

ADVENTURES = Path(__file__).parent.parent.parent / "adventures"


@pytest.mark.parametrize(
    "adventure_id", ["core_five_rooms", "scenarios/locked_door", "scenarios/goblin_fight"]
)
def test_every_adventure_in_the_repo_loads_and_validates(adventure_id):
    adventure = YamlAdventureSource(ADVENTURES).load(adventure_id)
    assert adventure.win_condition.flag


def test_core_five_rooms_has_the_planned_shape():
    adventure = YamlAdventureSource(ADVENTURES).load("core_five_rooms")
    assert len(adventure.locations) == 5
    assert [e.srd_ref for e in adventure.entities] == ["goblin_warrior"]
    (lock,) = adventure.locks
    assert lock.key is not None and lock.pick_dc is not None
    assert adventure.win_condition.flag == "amulet_retrieved"


def test_a_broken_reference_names_the_file_and_the_problem(tmp_path):
    (tmp_path / "broken").mkdir()
    text = (ADVENTURES / "core_five_rooms" / "adventure.yaml").read_text()
    (tmp_path / "broken" / "adventure.yaml").write_text(text.replace("to: shrine", "to: nowhere"))
    with pytest.raises(ValueError, match=r"(?s)broken.*unknown location 'nowhere'"):
        YamlAdventureSource(tmp_path).load("broken")
