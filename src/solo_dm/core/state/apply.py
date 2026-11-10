"""apply_event: the one pure function that turns an event into a new state."""

from collections.abc import Iterable

from solo_dm.core.state.combatants import hp_of
from solo_dm.core.state.events import (
    AdventureLost,
    CharacterDefeated,
    CombatEnded,
    CombatStarted,
    CreatureDied,
    DamageDealt,
    Event,
    TurnStarted,
)
from solo_dm.core.state.models import GameState


def apply_event(state: GameState, event: Event) -> GameState:
    match event:
        case DamageDealt(target_id=target_id, amount=amount):
            return _update_combatant(state, target_id, hp=max(0, hp_of(state, target_id) - amount))
        case CreatureDied(target_id=target_id):
            return _update_combatant(state, target_id, alive=False)
        case CharacterDefeated(target_id=target_id):
            return _update_combatant(state, target_id, defeated=True)
        case CombatStarted(turn_order=turn_order):
            return state.model_copy(
                update={"in_combat": True, "turn_order": tuple(turn_order), "combat_round": 1}
            )
        case TurnStarted(turn_index=turn_index, combat_round=combat_round):
            return state.model_copy(
                update={"active_turn_index": turn_index, "combat_round": combat_round}
            )
        case CombatEnded():
            return state.model_copy(
                update={"in_combat": False, "turn_order": (), "active_turn_index": 0,
                        "combat_round": 0}
            )
        case AdventureLost():
            return state.model_copy(update={"outcome": "lost"})
        case _:
            return state


def apply_events(state: GameState, events: Iterable[Event]) -> GameState:
    for event in events:
        state = apply_event(state, event)
    return state


def _update_combatant(state: GameState, combatant_id: str, **changes) -> GameState:
    if combatant_id in state.party:
        member = state.party[combatant_id].model_copy(update=changes)
        return state.model_copy(update={"party": {**state.party, combatant_id: member}})
    creature = state.creatures[combatant_id].model_copy(update=changes)
    return state.model_copy(update={"creatures": {**state.creatures, combatant_id: creature}})
