"""Attack rolls vs AC, damage and dropping to 0 HP (SRD 5.2).

A natural 20 always hits and is a critical hit (damage dice rolled twice);
a natural 1 always misses. A creature at 0 HP dies; a character at 0 HP is
defeated (plan section 2: no death saves in v1)."""

from solo_dm.core.ports import DicePort
from solo_dm.core.rules.dice_expression import parse_dice
from solo_dm.core.state.combatants import armor_class_of, hp_of, is_party_member
from solo_dm.core.state.events import (
    AttackRolled,
    CharacterDefeated,
    CreatureDied,
    DamageDealt,
    Event,
)
from solo_dm.core.state.models import AttackProfile, Character, GameState


def character_attack(character: Character, weapon_id: str) -> AttackProfile:
    weapon = next(w for w in character.weapons if w.weapon_id == weapon_id)
    ability_modifier = character.abilities.modifier(weapon.ability)
    return AttackProfile(
        name=weapon.name,
        attack_bonus=ability_modifier + character.proficiency_bonus,
        damage_dice=weapon.damage_dice,
        damage_modifier=ability_modifier,
        damage_type=weapon.damage_type,
    )


def resolve_attack(
    state: GameState, attacker_id: str, target_id: str, attack: AttackProfile, dice: DicePort
) -> list[Event]:
    d20 = dice.roll("1d20").rolls[0]
    target_ac = armor_class_of(state, target_id)
    critical = d20 == 20
    hit = critical or (d20 != 1 and d20 + attack.attack_bonus >= target_ac)
    events: list[Event] = [
        AttackRolled(
            actor_id=attacker_id,
            target_id=target_id,
            attack_name=attack.name,
            d20=d20,
            attack_bonus=attack.attack_bonus,
            target_armor_class=target_ac,
            hit=hit,
            critical=critical,
        )
    ]
    if not hit:
        return events

    damage = parse_dice(attack.damage_dice)
    count = damage.count * 2 if critical else damage.count
    rolls = dice.roll(f"{count}d{damage.sides}").rolls
    modifier = damage.modifier + attack.damage_modifier
    amount = max(0, sum(rolls) + modifier)
    events.append(
        DamageDealt(
            actor_id=attacker_id,
            target_id=target_id,
            rolls=rolls,
            modifier=modifier,
            amount=amount,
            damage_type=attack.damage_type,
        )
    )
    if hp_of(state, target_id) - amount <= 0:
        dropped = CharacterDefeated if is_party_member(state, target_id) else CreatureDied
        events.append(dropped(actor_id=attacker_id, target_id=target_id))
    return events
