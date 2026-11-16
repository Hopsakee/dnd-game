"""Attack rolls vs AC, damage and dropping to 0 HP (SRD 5.2).

A natural 20 always hits and is a critical hit (damage dice rolled twice);
a natural 1 always misses. A creature at 0 HP dies; a character at 0 HP is
defeated (plan section 2: no death saves in v1)."""

from solo_dm.core.ports import DicePort
from solo_dm.core.rules.dice_expression import parse_dice
from solo_dm.core.rules.rules_d20 import character_d20, roll_d20
from solo_dm.core.rules.rules_defeat import dropped_to_zero
from solo_dm.core.state.combatants import armor_class_of, hp_of
from solo_dm.core.state.events import AttackRolled, DamageDealt, Event
from solo_dm.core.state.models import AttackProfile, Character, GameState


def character_attack(character: Character) -> AttackProfile:
    """The attack with the weapon in hand."""
    weapon = character.weapon_in_hand()
    ability_modifier = character.abilities.modifier(weapon.ability)
    return AttackProfile(
        name=weapon.name,
        attack_bonus=ability_modifier + character.proficiency_bonus,
        damage_dice=weapon.damage_dice,
        damage_modifier=ability_modifier,
        damage_type=weapon.damage_type,
        damage_penalty=weapon.damage_penalty,
    )


def resolve_attack(
    state: GameState, attacker_id: str, target_id: str, attack: AttackProfile, dice: DicePort
) -> list[Event]:
    if attacker_id in state.party:
        d20, rolls, mode, ends = character_d20(state.party[attacker_id], dice)
    else:
        (d20, rolls, mode), ends = roll_d20(dice), None
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
            d20_rolls=rolls,
            roll_mode=mode,
            ends_condition=ends,
        )
    ]
    if not hit:
        return events

    damage = parse_dice(attack.damage_dice)
    count = damage.count * 2 if critical else damage.count
    rolls = dice.roll(f"{count}d{damage.sides}").rolls
    modifier = damage.modifier + attack.damage_modifier
    penalty = dice.roll(attack.damage_penalty).rolls if attack.damage_penalty else []
    amount = max(0, sum(rolls) + modifier - sum(penalty))
    events.append(
        DamageDealt(
            actor_id=attacker_id,
            target_id=target_id,
            rolls=rolls,
            modifier=modifier,
            amount=amount,
            damage_type=attack.damage_type,
            penalty_rolls=penalty,
        )
    )
    if hp_of(state, target_id) - amount <= 0:
        events.append(dropped_to_zero(state, target_id, attacker_id))
    return events
