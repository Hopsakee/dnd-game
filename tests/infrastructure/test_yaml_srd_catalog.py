from pathlib import Path

import pytest

from solo_dm.core.rules.rules_attacks import character_attack
from solo_dm.infrastructure.srd.yaml_srd_catalog import YamlSrdCatalog

SRD = Path(__file__).parent.parent.parent / "srd"


def test_premade_level_one_fighter_follows_srd_rules():
    fighter = YamlSrdCatalog(SRD).premade_character(
        "fighter_level_1", character_id="hero", player_id="jelle"
    )
    assert (fighter.character_id, fighter.player_id, fighter.level) == ("hero", "jelle", 1)
    # Level 1 Fighter HP = 10 + CON modifier (CON 15 -> +2).
    assert (fighter.max_hp, fighter.hp) == (12, 12)
    # Chain Mail 16 + Defense fighting style 1.
    assert fighter.armor_class == 17
    assert fighter.armor == "Chain Mail"
    greatsword = character_attack(fighter, "greatsword")
    assert (greatsword.attack_bonus, greatsword.damage_dice, greatsword.damage_modifier) == (
        5, "2d6", 3,
    )


def test_goblin_warrior_becomes_a_creature_in_the_game():
    creature = YamlSrdCatalog(SRD).creature(
        "goblin_warrior", creature_id="goblin_scout", location="guard_room", attitude="hostile"
    )
    assert (creature.creature_id, creature.location, creature.attitude) == (
        "goblin_scout", "guard_room", "hostile",
    )
    assert (creature.armor_class, creature.max_hp, creature.hp) == (15, 10, 10)
    assert creature.initiative_bonus == 2
    scimitar = creature.attacks[0]
    assert (scimitar.attack_bonus, scimitar.damage_dice, scimitar.damage_modifier) == (4, "1d6", 2)


def test_a_character_naming_an_unknown_weapon_fails_loudly(tmp_path):
    (tmp_path / "characters").mkdir()
    (tmp_path / "weapons.yaml").write_text("[]\n")
    (tmp_path / "characters" / "broken.yaml").write_text(
        (SRD / "characters" / "fighter_level_1.yaml").read_text()
    )
    with pytest.raises(ValueError, match="greatsword"):
        YamlSrdCatalog(tmp_path).premade_character("broken", character_id="x", player_id="y")
