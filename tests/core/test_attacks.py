from solo_dm.core.rules.rules_attacks import character_attack, resolve_attack
from solo_dm.core.state.apply import apply_events

from ..fakes import FixedDice
from .builders import fighter, goblin, state_with


def test_fighter_greatsword_profile_uses_strength_and_proficiency():
    profile = character_attack(fighter(), "greatsword")
    assert (profile.attack_bonus, profile.damage_dice, profile.damage_modifier) == (5, "2d6", 3)


def test_hit_that_drops_a_creature_to_zero_kills_it():
    state = state_with(fighter(), creatures=[goblin()])
    attack = character_attack(fighter(), "greatsword")
    # d20 10 + 5 = 15 vs AC 15 hits; 2d6 = 4 + 5, +3 -> 12 damage, goblin has 10 HP.
    events = resolve_attack(state, "hero", "goblin", attack, FixedDice([10, 4, 5]))
    assert [e.type for e in events] == ["attack_rolled", "damage_dealt", "creature_died"]
    assert events[1].amount == 12
    after = apply_events(state, events)
    assert after.creatures["goblin"].hp == 0
    assert after.creatures["goblin"].alive is False


def test_hit_that_leaves_hp_reduces_it():
    state = state_with(fighter(), creatures=[goblin()])
    attack = character_attack(fighter(), "greatsword")
    events = resolve_attack(state, "hero", "goblin", attack, FixedDice([15, 1, 2]))  # 6 damage
    after = apply_events(state, events)
    assert [e.type for e in events] == ["attack_rolled", "damage_dealt"]
    assert after.creatures["goblin"].hp == 4
    assert after.creatures["goblin"].alive is True


def test_roll_below_armor_class_misses_without_damage():
    state = state_with(fighter(), creatures=[goblin()])
    attack = character_attack(fighter(), "greatsword")
    events = resolve_attack(state, "hero", "goblin", attack, FixedDice([9]))  # 14 vs AC 15
    assert [e.type for e in events] == ["attack_rolled"]
    assert events[0].hit is False
    assert apply_events(state, events) == state


def test_natural_one_always_misses_and_natural_twenty_crits_with_double_dice():
    state = state_with(fighter(), creatures=[goblin(hp=40)])
    attack = character_attack(fighter(), "greatsword")
    assert resolve_attack(state, "hero", "goblin", attack, FixedDice([1]))[0].hit is False
    # Critical: 4d6 instead of 2d6 (1+1+1+1), modifier once: 4 + 3 = 7.
    events = resolve_attack(state, "hero", "goblin", attack, FixedDice([20, 1, 1, 1, 1]))
    assert events[0].critical is True
    assert events[1].amount == 7


def test_creature_hit_that_drops_a_character_to_zero_defeats_them():
    state = state_with(fighter(hp=3), creatures=[goblin()])
    scimitar = state.creatures["goblin"].attacks[0]
    # d20 13 + 4 = 17 vs AC 17 hits; 1d6 = 2, +2 -> 4 damage.
    events = resolve_attack(state, "goblin", "hero", scimitar, FixedDice([13, 2]))
    assert [e.type for e in events] == ["attack_rolled", "damage_dealt", "character_defeated"]
    after = apply_events(state, events)
    assert (after.party["hero"].hp, after.party["hero"].defeated) == (0, True)
