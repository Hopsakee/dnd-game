"""Read helpers that treat party members and creatures alike."""

from solo_dm.core.state.models import GameState


def is_party_member(state: GameState, combatant_id: str) -> bool:
    return combatant_id in state.party


def hp_of(state: GameState, combatant_id: str) -> int:
    if is_party_member(state, combatant_id):
        return state.party[combatant_id].hp
    return state.creatures[combatant_id].hp


def armor_class_of(state: GameState, combatant_id: str) -> int:
    if is_party_member(state, combatant_id):
        return state.party[combatant_id].armor_class
    return state.creatures[combatant_id].armor_class


def is_up(state: GameState, combatant_id: str) -> bool:
    """Still able to act: a conscious party member or a living creature."""
    if is_party_member(state, combatant_id):
        return not state.party[combatant_id].defeated
    return state.creatures[combatant_id].alive
