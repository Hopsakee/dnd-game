from solo_dm.core.rules.rules_attacks import character_attack, resolve_attack
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.combat import active_combatant, should_start_combat, start_combat

from ..fakes import FixedDice
from .builders import fighter, goblin, state_with


def test_combat_starts_when_a_hostile_creature_shares_the_party_location():
    assert should_start_combat(state_with(fighter(), creatures=[goblin(location="cave")]))
    assert not should_start_combat(state_with(fighter(), creatures=[goblin(location="hall")]))


def test_initiative_orders_combatants_and_creatures_before_the_party_act_first():
    state = state_with(fighter(), creatures=[goblin()])
    # Initiative: hero d20 10 + DEX 2 = 12; goblin 15 + 2 = 17 -> goblin first.
    # Goblin picks a target (1d1 = 1, only the hero), attacks: 5 + 4 = 9 vs AC 17, miss.
    events = start_combat(state, FixedDice([10, 15, 1, 5]))
    assert [e.type for e in events] == [
        "combat_started", "turn_started", "attack_rolled", "turn_started",
    ]
    assert events[0].turn_order == ["goblin", "hero"]
    after = apply_events(state, events)
    assert after.in_combat is True
    assert after.turn_order == ("goblin", "hero")
    assert active_combatant(after) == "hero"
    assert after.combat_round == 1


def _hero_attacks(state, target_id, dice):
    attack = character_attack(state.party["hero"], "greatsword")
    return resolve_attack(state, "hero", target_id, attack, dice)


def test_full_combat_the_party_wins():
    from solo_dm.core.turn.combat import end_party_turn

    state = state_with(fighter(), creatures=[goblin()])
    # Initiative: hero 15 + 2 = 17, goblin 2 + 2 = 4 -> hero first.
    state = apply_events(state, start_combat(state, FixedDice([15, 2])))
    assert active_combatant(state) == "hero"
    # Round 1: hero misses (3 + 5 = 8); goblin hits (14 + 4 = 18) for 1d6 3 + 2 = 5.
    dice = FixedDice([3, 1, 14, 3])
    state = apply_events(state, _hero_attacks(state, "goblin", dice))
    state = apply_events(state, end_party_turn(state, dice))
    assert (state.party["hero"].hp, state.combat_round, active_combatant(state)) == (7, 2, "hero")
    # Round 2: hero hits (18 + 5) for 2d6 4 + 4 + 3 = 11: the goblin dies, combat ends.
    dice = FixedDice([18, 4, 4])
    state = apply_events(state, _hero_attacks(state, "goblin", dice))
    events = end_party_turn(state, dice)
    assert [e.type for e in events] == ["combat_ended"]
    assert events[0].reason == "hostiles_defeated"
    state = apply_events(state, events)
    assert (state.in_combat, state.outcome, active_combatant(state)) == (False, "playing", None)


def test_full_combat_the_party_loses_and_the_adventure_is_lost():
    state = state_with(fighter(hp=4), creatures=[goblin()])
    # Goblin first (18 vs 3), picks the hero, hits (15 + 4 = 19) for 2 + 2 = 4: hero at 0.
    events = start_combat(state, FixedDice([1, 16, 1, 15, 2]))
    assert [e.type for e in events][-4:] == [
        "damage_dealt", "character_defeated", "combat_ended", "adventure_lost",
    ]
    state = apply_events(state, events)
    assert state.party["hero"].defeated is True
    assert (state.in_combat, state.outcome) == (False, "lost")


def test_creature_turns_see_damage_from_earlier_creature_turns():
    # Two goblins act before the hero (hp 9). Goblin a hits for 2 + 2 = 4, goblin b
    # for 1 + 2 = 3: the hero ends at 2 HP, still standing, and it is the hero's turn.
    state = state_with(fighter(hp=9), creatures=[goblin("a"), goblin("b")])
    events = start_combat(state, FixedDice([1, 18, 17, 1, 15, 2, 1, 15, 1]))
    state = apply_events(state, events)
    assert [e.amount for e in events if e.type == "damage_dealt"] == [4, 3]
    assert "character_defeated" not in [e.type for e in events]
    assert (state.party["hero"].hp, active_combatant(state)) == (2, "hero")
