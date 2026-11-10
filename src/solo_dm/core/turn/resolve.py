"""Resolution (plan 3.5 step 4-6): check an intent against state and adventure,
pick the rule, roll, and return events. Illegal actions are Blocked with a
reason and change nothing."""

from pydantic import BaseModel

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import DicePort
from solo_dm.core.rules.rules_attacks import character_attack, resolve_attack
from solo_dm.core.rules.rules_checks import ability_check
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.events import (
    AdventureWon,
    AttitudeChanged,
    CombatEnded,
    DoorUnlocked,
    Event,
    ItemTaken,
    LocationDiscovered,
    MovedTo,
    QuestFlagSet,
)
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.combat import (
    active_combatant,
    end_party_turn,
    should_start_combat,
    start_combat,
)
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.scene import build_scene


class Resolution(BaseModel):
    events: list[Event] = []
    blocked: str | None = None


class Blocked(Exception):
    pass


def resolve_intent(
    state: GameState, adventure: Adventure, actor_id: str, intent: Intent, dice: DicePort
) -> Resolution:
    try:
        if state.outcome != "playing":
            raise Blocked("The adventure is over.")
        if state.in_combat and active_combatant(state) != actor_id:
            raise Blocked("It is not your turn.")
        if intent.target_id is not None and intent.target_id not in build_scene(
            state, adventure
        ).valid_ids():
            raise Blocked(f"There is no {intent.target_id.replace('_', ' ')} here.")
        events = _ACTIONS.get(intent.action, _no_rule_yet)(state, adventure, actor_id, intent, dice)
    except Blocked as blocked:
        return Resolution(blocked=str(blocked))
    return Resolution(events=events + _aftermath(state, apply_events(state, events), dice))


def _aftermath(before: GameState, after: GameState, dice: DicePort) -> list[Event]:
    """Creature turns after a party turn in combat, or combat starting on arrival."""
    if after.outcome != "playing":
        return []
    if before.in_combat and after.in_combat:
        return end_party_turn(after, dice)
    if not after.in_combat and should_start_combat(after):
        return start_combat(after, dice)
    return []


def _move(state, adventure, actor_id, intent, dice) -> list[Event]:
    exit_ = _require_exit(adventure, intent)
    if exit_.id in state.locked_exits:
        raise Blocked(f"The way {exit_.direction} is locked.")
    events: list[Event] = []
    if state.in_combat:
        events.append(CombatEnded(reason="party_left"))
    events.append(MovedTo(actor_id=actor_id, location_id=exit_.to))
    if exit_.to not in state.discovered_locations:
        events.append(LocationDiscovered(actor_id=actor_id, location_id=exit_.to))
    return events


def _attack(state, adventure, actor_id, intent, dice) -> list[Event]:
    creature = state.creatures.get(intent.target_id or "")
    if creature is None or not creature.alive:
        raise Blocked("There is nothing there to attack.")
    events: list[Event] = []
    if creature.attitude != "hostile":
        events.append(
            AttitudeChanged(actor_id=actor_id, target_id=creature.creature_id, attitude="hostile")
        )
    if not state.in_combat:
        events += start_combat(apply_events(state, events), dice)
        state = apply_events(state, events)
        if not state.in_combat or active_combatant(state) != actor_id:
            return events
    attacker = state.party[actor_id]
    attack = character_attack(attacker, attacker.weapons[0].weapon_id)
    return events + resolve_attack(state, actor_id, creature.creature_id, attack, dice)


def _take(state, adventure, actor_id, intent, dice) -> list[Event]:
    if intent.target_id not in state.items_on_floor:
        raise Blocked("You cannot take that.")
    item = adventure.item(intent.target_id)
    events: list[Event] = [ItemTaken(actor_id=actor_id, item_id=item.id)]
    if item.on_take:
        events.append(QuestFlagSet(actor_id=actor_id, flag=item.on_take.set_flag))
        if item.on_take.set_flag == adventure.win_condition.flag:
            events.append(AdventureWon(actor_id=actor_id))
    return events


def _unlock(state, adventure, actor_id, intent, dice) -> list[Event]:
    exit_ = _require_exit(adventure, intent)
    lock = adventure.lock(exit_.id)
    if lock is None or exit_.id not in state.locked_exits:
        raise Blocked("It is not locked.")
    if lock.key is not None and lock.key in state.party[actor_id].inventory:
        return [DoorUnlocked(actor_id=actor_id, exit_id=exit_.id, method="key")]
    if lock.pick_dc is None:
        raise Blocked("You need the key for this lock.")
    check = ability_check(state.party[actor_id], "DEX", "sleight_of_hand", lock.pick_dc, dice)
    if not check.success:
        return [check]
    return [check, DoorUnlocked(actor_id=actor_id, exit_id=exit_.id, method="picked")]


def _open(state, adventure, actor_id, intent, dice) -> list[Event]:
    exit_ = _require_exit(adventure, intent)
    if exit_.id in state.locked_exits:
        raise Blocked(f"The way {exit_.direction} is locked.")
    raise Blocked(f"The way {exit_.direction} is already open.")


def _look(state, adventure, actor_id, intent, dice) -> list[Event]:
    return []


def _no_rule_yet(state, adventure, actor_id, intent, dice) -> list[Event]:
    raise Blocked("There is no rule for that yet.")


def _require_exit(adventure: Adventure, intent: Intent):
    exits = {e.id for loc in adventure.locations for e in loc.exits}
    if intent.target_id not in exits:
        raise Blocked("Which way?")
    return adventure.exit(intent.target_id)


_ACTIONS = {
    "move": _move,
    "attack": _attack,
    "take": _take,
    "unlock": _unlock,
    "open": _open,
    "look": _look,
}
