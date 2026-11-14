"""Healing (M7): dice of hit points regained, never past the maximum."""

from solo_dm.core.ports import DicePort
from solo_dm.core.rules.dice_expression import parse_dice
from solo_dm.core.state.events import Healed
from solo_dm.core.state.models import Character


def heal(character: Character, expression: str, dice: DicePort) -> Healed:
    parsed = parse_dice(expression)
    rolls = dice.roll(f"{parsed.count}d{parsed.sides}").rolls
    rolled = sum(rolls) + parsed.modifier
    return Healed(actor_id=character.character_id, target_id=character.character_id,
                  rolls=rolls, modifier=parsed.modifier,
                  amount=max(0, min(rolled, character.max_hp - character.hp)))
