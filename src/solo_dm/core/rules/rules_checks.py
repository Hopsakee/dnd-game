"""Ability checks (SRD 5.2): d20 + ability modifier (+ proficiency) vs DC."""

from solo_dm.core.ports import DicePort
from solo_dm.core.state.events import CheckRolled
from solo_dm.core.state.models import Ability, Character


def ability_check(
    character: Character, ability: Ability, skill: str | None, dc: int, dice: DicePort
) -> CheckRolled:
    modifier = character.abilities.modifier(ability)
    if skill is not None and skill in character.skill_proficiencies:
        modifier += character.proficiency_bonus
    d20 = dice.roll("1d20").rolls[0]
    total = d20 + modifier
    return CheckRolled(
        actor_id=character.character_id,
        ability=ability,
        skill=skill,
        d20=d20,
        modifier=modifier,
        dc=dc,
        total=total,
        success=total >= dc,
    )
