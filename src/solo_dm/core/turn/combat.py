"""Combat rounds (plan 3.5.1): initiative, creature turns, start and end.

Creatures act by fixed Python rules (plan section 2, "Monster behaviour"): a
hostile creature attacks a random conscious party member in reach and never
flees. Positioning is abstract: everyone in a location is in melee reach."""

from solo_dm.core.ports import DicePort
from solo_dm.core.rules.rules_attacks import resolve_attack
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.combatants import is_party_member, is_up
from solo_dm.core.state.events import (
    AdventureLost,
    CombatEnded,
    CombatStarted,
    Event,
    InitiativeRoll,
    TurnStarted,
)
from solo_dm.core.state.models import CreatureState, GameState


def hostiles_present(state: GameState) -> list[CreatureState]:
    return [
        c
        for c in state.creatures.values()
        if c.alive and c.attitude == "hostile" and c.location == state.party_location
    ]


def should_start_combat(state: GameState) -> bool:
    return not state.in_combat and bool(hostiles_present(state))


def active_combatant(state: GameState) -> str | None:
    if not state.in_combat:
        return None
    return state.turn_order[state.active_turn_index]


def start_combat(state: GameState, dice: DicePort) -> list[Event]:
    """Roll initiative and run every creature turn before the first party turn."""
    rolls = [_initiative(state, combatant_id, dice) for combatant_id in _combatants(state)]
    order = sorted(range(len(rolls)), key=lambda i: (-rolls[i].total, -rolls[i].bonus, i))
    events: list[Event] = [
        CombatStarted(initiative=rolls, turn_order=[rolls[i].combatant_id for i in order])
    ]
    state = apply_events(state, events)
    first = TurnStarted(actor_id=state.turn_order[0], turn_index=0, combat_round=1)
    events.append(first)
    return events + _run_creature_turns(apply_events(state, [first]), dice)


def _advance(state: GameState, dice: DicePort) -> list[Event]:
    ending = _combat_end(state)
    if ending:
        return ending
    turn = _next_turn(state)
    return [turn] + _run_creature_turns(apply_events(state, [turn]), dice)


def _combat_end(state: GameState) -> list[Event]:
    if not any(is_up(state, cid) for cid in state.party):
        return [
            CombatEnded(reason="party_defeated"),
            AdventureLost(reason="every party member was defeated"),
        ]
    if not hostiles_present(state):
        return [CombatEnded(reason="hostiles_defeated")]
    return []


def end_party_turn(state: GameState, dice: DicePort) -> list[Event]:
    """Close the active party member's turn: end combat or move on, running the
    creature turns that come before the next party member."""
    return _advance(state, dice)


def _combatants(state: GameState) -> list[str]:
    party = [cid for cid in state.party if is_up(state, cid)]
    return party + [c.creature_id for c in hostiles_present(state)]


def _initiative(state: GameState, combatant_id: str, dice: DicePort) -> InitiativeRoll:
    if is_party_member(state, combatant_id):
        bonus = state.party[combatant_id].abilities.modifier("DEX")
    else:
        bonus = state.creatures[combatant_id].initiative_bonus
    d20 = dice.roll("1d20").rolls[0]
    return InitiativeRoll(combatant_id=combatant_id, d20=d20, bonus=bonus, total=d20 + bonus)


def _run_creature_turns(state: GameState, dice: DicePort) -> list[Event]:
    """From the active combatant on, let creatures act until a party member is up."""
    events: list[Event] = []
    while state.in_combat and not is_party_member(state, active_combatant(state)):
        attack = _creature_turn(state, active_combatant(state), dice)
        state = apply_events(state, attack)
        after = _combat_end(state) or [_next_turn(state)]
        state = apply_events(state, after)
        events += attack + after
    return events


def _creature_turn(state: GameState, creature_id: str, dice: DicePort) -> list[Event]:
    targets = sorted(cid for cid in state.party if is_up(state, cid))
    pick = dice.roll(f"1d{len(targets)}").rolls[0]
    attack = state.creatures[creature_id].attacks[0]
    return resolve_attack(state, creature_id, targets[pick - 1], attack, dice)


def _next_turn(state: GameState) -> TurnStarted:
    index, combat_round = state.active_turn_index, state.combat_round
    while True:
        index += 1
        if index == len(state.turn_order):
            index, combat_round = 0, combat_round + 1
        combatant_id = state.turn_order[index]
        if is_up(state, combatant_id):
            return TurnStarted(actor_id=combatant_id, turn_index=index, combat_round=combat_round)
