"""Multiplayer readiness (plan 6): rules and combat with two party members,
both controlled by one test player."""

from solo_dm.core.rules.rules_attacks import character_attack, resolve_attack
from solo_dm.core.rules.rules_checks import ability_check
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.combat import active_combatant, end_party_turn, start_combat
from solo_dm.infrastructure.dice.seeded_dice import SeededDice

from ..fakes import FixedDice
from .builders import fighter, goblin, state_with


def test_each_party_member_acts_on_their_own_turn_and_a_fallen_member_does_not_lose():
    state = state_with(fighter("ally", hp=3), fighter("hero"), creatures=[goblin()])
    # Initiative: ally 18 + 2 = 20, goblin 15 + 2 = 17, hero 3 + 2 = 5.
    state = apply_events(state, start_combat(state, FixedDice([18, 3, 15])))
    assert state.turn_order == ("ally", "goblin", "hero")
    assert active_combatant(state) == "ally"
    # Ally misses (2 + 5). Goblin picks target 1 of [ally, hero] -> ally, hits 15 + 4
    # for 1 + 2 = 3: ally defeated. Then the hero's turn, the adventure goes on.
    events = end_party_turn(state, FixedDice([1, 15, 1]))
    state = apply_events(state, events)
    assert state.party["ally"].defeated is True
    assert (active_combatant(state), state.outcome) == ("hero", "playing")
    # Hero misses; next round skips the fallen ally, the goblin can only pick the hero.
    events = end_party_turn(state, FixedDice([1, 2]))
    assert [(e.type, getattr(e, "target_id", None)) for e in events[:2]] == [
        ("turn_started", None), ("attack_rolled", "hero"),
    ]
    assert events[0].actor_id == "goblin" and events[0].combat_round == 2


def test_checks_and_attacks_work_for_any_party_member():
    state = state_with(fighter("ally"), fighter("hero"), creatures=[goblin()])
    check = ability_check(state.party["ally"], "STR", "athletics", 12, FixedDice([7]))
    assert (check.actor_id, check.success) == ("ally", True)
    attack = character_attack(state.party["ally"], "greatsword")
    events = resolve_attack(state, "ally", "goblin", attack, FixedDice([12, 2, 2]))
    assert apply_events(state, events).creatures["goblin"].hp == 3


def test_seeded_battles_of_two_against_two_always_end_with_one_side_down():
    for seed in range(40):
        dice = SeededDice(seed)
        state = state_with(
            fighter("ally"), fighter("hero"), creatures=[goblin("a"), goblin("b")]
        )
        state = apply_events(state, start_combat(state, dice))
        for _ in range(200):
            if not state.in_combat:
                break
            actor = active_combatant(state)
            target = next(c.creature_id for c in state.creatures.values() if c.alive)
            attack = character_attack(state.party[actor], "greatsword")
            state = apply_events(state, resolve_attack(state, actor, target, attack, dice))
            state = apply_events(state, end_party_turn(state, dice))
        party_down = all(m.defeated for m in state.party.values())
        hostiles_down = not any(c.alive for c in state.creatures.values())
        assert not state.in_combat
        assert party_down != hostiles_down
        assert state.outcome == ("lost" if party_down else "playing")
