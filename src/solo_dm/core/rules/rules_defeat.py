"""Dropping to 0 hit points (SRD 5.2, simplified in plan 2): a creature dies; a
character is defeated, unless the adventure's guardian still has a rescue (M7)."""

from solo_dm.core.state.combatants import is_party_member
from solo_dm.core.state.events import CharacterDefeated, CreatureDied, Event, GuardianRescued
from solo_dm.core.state.models import GameState


def dropped_to_zero(state: GameState, target_id: str, actor_id: str | None) -> Event:
    if not is_party_member(state, target_id):
        return CreatureDied(actor_id=actor_id, target_id=target_id)
    if state.guardian is not None and state.rescues_left > 0:
        return GuardianRescued(actor_id=actor_id, target_id=target_id, guardian=state.guardian)
    return CharacterDefeated(actor_id=actor_id, target_id=target_id)
