"""Events: the only way state changes. Rolls are recorded inside events so a
replay of the log reproduces the game without dice."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from solo_dm.core.state.models import Ability, Attitude


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
    reason: Literal["hostiles_defeated", "party_defeated", "party_left"]


class AdventureLost(Event):
    type: Literal["adventure_lost"] = "adventure_lost"
    reason: str


class MovedTo(Event):
    type: Literal["moved_to"] = "moved_to"
    location_id: str


class LocationDiscovered(Event):
    type: Literal["location_discovered"] = "location_discovered"
    location_id: str


class DoorUnlocked(Event):
    type: Literal["door_unlocked"] = "door_unlocked"
    exit_id: str
    method: Literal["key", "picked"]


class ItemTaken(Event):
    type: Literal["item_taken"] = "item_taken"
    item_id: str


class HiddenFound(Event):
    """A hidden item or exit is found: by passive Perception on entering, or by a search."""

    type: Literal["hidden_found"] = "hidden_found"
    target_id: str
    method: Literal["passive", "search"]


class BodySearched(Event):
    """A dead creature is searched; what it carried now lies in its location."""

    type: Literal["body_searched"] = "body_searched"
    target_id: str
    item_ids: list[str]


class QuestFlagSet(Event):
    type: Literal["quest_flag_set"] = "quest_flag_set"
    flag: str


class AttitudeChanged(Event):
    type: Literal["attitude_changed"] = "attitude_changed"
    target_id: str
    attitude: Attitude


class AdventureWon(Event):
    type: Literal["adventure_won"] = "adventure_won"
