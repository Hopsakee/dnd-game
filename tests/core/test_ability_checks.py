from solo_dm.core.rules.rules_checks import ability_check

from ..fakes import FixedDice
from .builders import fighter


def test_proficient_check_adds_ability_modifier_and_proficiency_and_meets_dc():
    # STR 16 -> +3, proficient in Athletics -> +2; d20 = 10 -> 15 vs DC 15.
    event = ability_check(fighter(), "STR", "athletics", dc=15, dice=FixedDice([10]))
    assert event.actor_id == "hero"
    assert (event.d20, event.modifier, event.total, event.success) == (10, 5, 15, True)


def test_unproficient_skill_uses_only_the_ability_modifier():
    # DEX 14 -> +2, not proficient in Stealth; d20 = 12 -> 14 vs DC 15.
    event = ability_check(fighter(), "DEX", "stealth", dc=15, dice=FixedDice([12]))
    assert (event.modifier, event.total, event.success) == (2, 14, False)


def test_plain_ability_check_without_skill():
    # INT 8 -> -1; d20 = 11 -> 10 vs DC 10.
    event = ability_check(fighter(), "INT", None, dc=10, dice=FixedDice([11]))
    assert (event.skill, event.total, event.success) == (None, 10, True)
