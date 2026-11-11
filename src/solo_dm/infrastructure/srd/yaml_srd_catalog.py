"""Loads SRD 5.2 reference data (srd/*.yaml) into core models."""

from pathlib import Path

import yaml
from pydantic import BaseModel

from solo_dm.core.state.models import (
    AbilityScores,
    AttackProfile,
    Attitude,
    Character,
    CreatureState,
    Weapon,
)


class CreatureStatBlock(BaseModel):
    stat_block_id: str
    name: str
    armor_class: int
    hit_points: int
    initiative_bonus: int
    abilities: AbilityScores
    attacks: list[AttackProfile]
    not_implemented: list[str] = []


class CharacterTemplate(BaseModel):
    name: str
    level: int
    abilities: AbilityScores
    max_hp: int
    armor_class: int
    proficiency_bonus: int
    skill_proficiencies: list[str]
    weapons: list[str]
    inventory: list[str] = []
    not_implemented: list[str] = []


class YamlSrdCatalog:
    def __init__(self, root: Path) -> None:
        self._root = root

    def creature(
        self, stat_block_id: str, creature_id: str, location: str, attitude: Attitude
    ) -> CreatureState:
        block = CreatureStatBlock.model_validate(
            self._load(self._root / "creatures" / f"{stat_block_id}.yaml")
        )
        return CreatureState(
            creature_id=creature_id,
            name=block.name,
            srd_ref=block.stat_block_id,
            location=location,
            attitude=attitude,
            armor_class=block.armor_class,
            max_hp=block.hit_points,
            hp=block.hit_points,
            initiative_bonus=block.initiative_bonus,
            attacks=tuple(block.attacks),
        )

    def premade_character(self, template_id: str, character_id: str, player_id: str) -> Character:
        template = CharacterTemplate.model_validate(
            self._load(self._root / "characters" / f"{template_id}.yaml")
        )
        weapons = self._weapons()
        missing = [w for w in template.weapons if w not in weapons]
        if missing:
            raise ValueError(f"{template_id}: unknown weapons {missing}")
        return Character(
            character_id=character_id,
            name=template.name,
            player_id=player_id,
            level=template.level,
            abilities=template.abilities,
            max_hp=template.max_hp,
            hp=template.max_hp,
            armor_class=template.armor_class,
            proficiency_bonus=template.proficiency_bonus,
            skill_proficiencies=tuple(template.skill_proficiencies),
            weapons=tuple(weapons[w] for w in template.weapons),
            inventory=tuple(template.inventory),
        )

    def _weapons(self) -> dict[str, Weapon]:
        entries = self._load(self._root / "weapons.yaml")
        return {w.weapon_id: w for w in (Weapon.model_validate(e) for e in entries)}

    @staticmethod
    def _load(path: Path):
        return yaml.safe_load(path.read_text())
