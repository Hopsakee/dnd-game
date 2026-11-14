"""M7: saving throws (SRD 5.2): d20 + ability modifier, + proficiency bonus in
the saves the class is proficient in. A Fighter is proficient in STR and CON.

The test Fighter: STR 16 (+3), DEX 14 (+2), CON 15 (+2), proficiency +2."""

from solo_dm.core.rules.rules_checks import saving_throw

from ..fakes import FixedDice
from .builders import fighter


def test_a_proficient_save_adds_the_proficiency_bonus():
    save = saving_throw(fighter(), "CON", 15, FixedDice([11]))
    assert (save.ability, save.d20, save.modifier, save.total, save.success) == (
        "CON", 11, 4, 15, True)


def test_a_save_without_proficiency_adds_only_the_ability_modifier():
    save = saving_throw(fighter(), "DEX", 15, FixedDice([12]))
    assert (save.modifier, save.total, save.success) == (2, 14, False)
