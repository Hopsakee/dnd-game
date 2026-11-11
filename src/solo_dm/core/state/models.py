"""Game state models. Frozen: state changes only through apply_event()."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Ability = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class AbilityScores(FrozenModel):
    STR: int
    DEX: int
    CON: int
    INT: int
    WIS: int
    CHA: int

    def modifier(self, ability: Ability) -> int:
        return (getattr(self, ability) - 10) // 2


class Weapon(FrozenModel):
    weapon_id: str
    name: str
    ability: Ability
    damage_dice: str
    damage_type: str


class Character(FrozenModel):
    character_id: str
    name: str
    player_id: str
    level: int
    abilities: AbilityScores
    max_hp: int
    hp: int
    armor_class: int
    proficiency_bonus: int
    skill_proficiencies: tuple[str, ...] = ()
    weapons: tuple[Weapon, ...] = ()
    inventory: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    defeated: bool = False


Attitude = Literal["hostile", "indifferent", "friendly"]


class AttackProfile(FrozenModel):
    name: str
    attack_bonus: int
    damage_dice: str
    damage_modifier: int
    damage_type: str


class CreatureState(FrozenModel):
    creature_id: str
    name: str
    srd_ref: str
    location: str
    attitude: Attitude
    armor_class: int
    max_hp: int
    hp: int
    initiative_bonus: int
    attacks: tuple[AttackProfile, ...]
    alive: bool = True


class GameState(FrozenModel):
    """Whole-game state. The party is keyed by character_id: never assume one hero."""

    party: dict[str, Character]
    party_location: str
    creatures: dict[str, CreatureState] = {}
    turn_number: int = 0
    turn_order: tuple[str, ...] = ()
    active_turn_index: int = 0
    combat_round: int = 0
    in_combat: bool = False
    outcome: Literal["playing", "won", "lost"] = "playing"
    discovered_locations: tuple[str, ...] = ()
    items_on_floor: dict[str, str] = {}  # item_id -> location_id; held items are in inventory
    items_carried: dict[str, str] = {}  # item_id -> creature_id, until the body is searched
    hidden_unfound: tuple[str, ...] = ()  # ids of hidden items and exits not yet found
    locked_exits: tuple[str, ...] = ()
    quest_flags: tuple[str, ...] = ()


class CreatureStatBlock(FrozenModel):
    """SRD reference data for a creature kind."""

    stat_block_id: str
    name: str
    armor_class: int
    hit_points: int
    initiative_bonus: int
    abilities: AbilityScores
    attacks: tuple[AttackProfile, ...]
    not_implemented: tuple[str, ...] = ()


def creature_from_stat_block(
    block: CreatureStatBlock, creature_id: str, location: str, attitude: Attitude
) -> CreatureState:
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
        attacks=block.attacks,
    )
