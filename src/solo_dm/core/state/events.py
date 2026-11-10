"""Events: the only way state changes. Rolls are recorded inside events so a
replay of the log reproduces the game without dice."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from solo_dm.core.state.models import Ability


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    actor_id: str | None = None


class CheckRolled(Event):
    type: Literal["check_rolled"] = "check_rolled"
    ability: Ability
    skill: str | None
    d20: int
    modifier: int
    dc: int
    total: int
    success: bool


class AttackRolled(Event):
    type: Literal["attack_rolled"] = "attack_rolled"
    target_id: str
    attack_name: str
    d20: int
    attack_bonus: int
    target_armor_class: int
    hit: bool
    critical: bool


class DamageDealt(Event):
    type: Literal["damage_dealt"] = "damage_dealt"
    target_id: str
    rolls: list[int]
    modifier: int
    amount: int
    damage_type: str


class CreatureDied(Event):
    type: Literal["creature_died"] = "creature_died"
    target_id: str


class CharacterDefeated(Event):
    type: Literal["character_defeated"] = "character_defeated"
    target_id: str


class InitiativeRoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    combatant_id: str
    d20: int
    bonus: int
    total: int


class CombatStarted(Event):
    type: Literal["combat_started"] = "combat_started"
    initiative: list[InitiativeRoll]
    turn_order: list[str]


class TurnStarted(Event):
    """actor_id is the combatant whose turn it now is."""

    type: Literal["turn_started"] = "turn_started"
    turn_index: int
    combat_round: int


class CombatEnded(Event):
    type: Literal["combat_ended"] = "combat_ended"
    reason: Literal["hostiles_defeated", "party_defeated"]


class AdventureLost(Event):
    type: Literal["adventure_lost"] = "adventure_lost"
    reason: str
