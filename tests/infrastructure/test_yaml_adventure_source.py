from pathlib import Path

import pytest

from solo_dm.infrastructure.adventures.yaml_adventure_source import YamlAdventureSource

ADVENTURES = Path(__file__).parent.parent.parent / "adventures"


@pytest.mark.parametrize(
    "adventure_id", YamlAdventureSource(ADVENTURES).available()
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
    # M2.5: the key is on the goblin; the chalice needs a search (DC above the
    # Fighter's passive 13); the ring is found passively (DC at or below 13).
    assert adventure.item("iron_key").carried_by == "goblin_scout"
    assert adventure.item("silver_chalice").hidden.dc > 13
    assert adventure.item("tarnished_ring").hidden.dc <= 13


def test_a_broken_reference_names_the_file_and_the_problem(tmp_path):
    (tmp_path / "broken").mkdir()
    text = (ADVENTURES / "core_five_rooms" / "adventure.yaml").read_text()
    (tmp_path / "broken" / "adventure.yaml").write_text(text.replace("to: shrine", "to: nowhere"))
    with pytest.raises(ValueError, match=r"(?s)broken.*unknown location 'nowhere'"):
        YamlAdventureSource(tmp_path).load("broken")


def _write(folder: Path, adventure_id: str, title: str) -> Path:
    text = (ADVENTURES / "scenarios" / "goblin_fight" / "adventure.yaml").read_text()
    (folder / adventure_id).mkdir(parents=True)
    (folder / adventure_id / "adventure.yaml").write_text(
        text.replace("title: Goblin Fight", f"title: {title}"))
    return folder / adventure_id


def test_adventures_come_from_every_folder_and_the_first_one_wins(tmp_path):
    # M7: the books live in a separate private repo next to this one.
    public, private = tmp_path / "public", tmp_path / "private"
    _write(public, "shared", "Public Copy")
    _write(private, "shared", "Private Copy")
    _write(private, "azzinax", "Revenge of Azzinax")
    source = YamlAdventureSource(public, private, tmp_path / "not_cloned")
    assert source.available() == ["azzinax", "shared"]
    assert source.load("shared").title == "Public Copy"
    assert source.load("azzinax").title == "Revenge of Azzinax"


def test_an_adventure_brings_its_own_stat_blocks(tmp_path):
    folder = _write(tmp_path, "azzinax", "Revenge of Azzinax")
    (folder / "creatures").mkdir()
    (folder / "creatures" / "goblin_runt.yaml").write_text(
        "stat_block_id: goblin_runt\nname: Goblin Runt\narmor_class: 14\nhit_points: 2\n"
        "initiative_bonus: 4\nabilities: {STR: 5, DEX: 18, CON: 8, INT: 7, WIS: 12, CHA: 4}\n"
        "attacks:\n  - {name: Dagger, attack_bonus: 1, damage_dice: 1d4, damage_modifier: -1,"
        " damage_type: piercing}\n")
    blocks = YamlAdventureSource(tmp_path).stat_blocks("azzinax")
    assert blocks["goblin_runt"].hit_points == 2
    assert YamlAdventureSource(ADVENTURES).stat_blocks("core_five_rooms") == {}
