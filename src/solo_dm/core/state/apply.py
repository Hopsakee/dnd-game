"""apply_event: the one pure function that turns an event into a new state."""

from collections.abc import Iterable

from solo_dm.core.state.combatants import hp_of
from solo_dm.core.state.events import (
    AdventureLost,
    AdventureWon,
    AttitudeChanged,
    BodySearched,
    CharacterDefeated,
    CombatEnded,
    CombatStarted,
    CreatureDied,
    DamageDealt,
    DoorUnlocked,
    Event,
    GuardianRescued,
    HazardSprung,
    Healed,
    HiddenFound,
    ItemTaken,
    ItemUsed,
    LocationDiscovered,
    MovedTo,
    QuestFlagSet,
    TurnStarted,
)
from solo_dm.core.state.models import GameState


def apply_event(state: GameState, event: Event) -> GameState:
    match event:
        case DamageDealt(target_id=target_id, amount=amount):
            return _update_combatant(state, target_id, hp=max(0, hp_of(state, target_id) - amount))
        case GuardianRescued(target_id=target_id):
            state = _update_combatant(state, target_id, hp=state.party[target_id].max_hp)
            return state.model_copy(update={"rescues_left": state.rescues_left - 1})
        case Healed(target_id=target_id, amount=amount):
            return _update_combatant(state, target_id, hp=hp_of(state, target_id) + amount)
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
        case MovedTo(location_id=location_id):
            return state.model_copy(update={"party_location": location_id})
        case LocationDiscovered(location_id=location_id):
            discovered = (*state.discovered_locations, location_id)
            return state.model_copy(update={"discovered_locations": discovered})
        case DoorUnlocked(exit_id=exit_id):
            locked = tuple(e for e in state.locked_exits if e != exit_id)
            return state.model_copy(update={"locked_exits": locked})
        case ItemTaken(actor_id=actor_id, item_id=item_id):
            floor = {i: loc for i, loc in state.items_on_floor.items() if i != item_id}
            holder = state.party[actor_id]
            state = _update_combatant(state, actor_id, inventory=(*holder.inventory, item_id))
            return state.model_copy(update={"items_on_floor": floor})
        case HiddenFound(target_id=target_id):
            unfound = tuple(i for i in state.hidden_unfound if i != target_id)
            return state.model_copy(update={"hidden_unfound": unfound})
        case BodySearched(target_id=target_id, item_ids=item_ids):
            where = state.creatures[target_id].location
            carried = {i: c for i, c in state.items_carried.items() if i not in item_ids}
            floor = {**state.items_on_floor, **{i: where for i in item_ids}}
            return state.model_copy(update={"items_carried": carried, "items_on_floor": floor})
        case ItemUsed(actor_id=actor_id, item_id=item_id, used_up=True):
            kept = tuple(i for i in state.party[actor_id].inventory if i != item_id)
            return _update_combatant(state, actor_id, inventory=kept)
        case HazardSprung(hazard_id=hazard_id):
            return state.model_copy(update={"sprung_hazards": (*state.sprung_hazards, hazard_id)})
        case QuestFlagSet(flag=flag):
            return state.model_copy(update={"quest_flags": (*state.quest_flags, flag)})
        case AttitudeChanged(target_id=target_id, attitude=attitude):
            return _update_combatant(state, target_id, attitude=attitude)
        case AdventureWon():
            return state.model_copy(update={"outcome": "won"})
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
