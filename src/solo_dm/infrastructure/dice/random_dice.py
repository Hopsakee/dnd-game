"""Dice backed by a Python random generator: the real game's dice."""

import random

from solo_dm.core.ports import DicePort, RollResult
from solo_dm.core.rules.dice_expression import parse_dice


class RandomDice(DicePort):
    def __init__(self, generator: random.Random | None = None) -> None:
        self._generator = generator or random.Random()

    def roll(self, expression: str) -> RollResult:
        parsed = parse_dice(expression)
        rolls = [self._generator.randint(1, parsed.sides) for _ in range(parsed.count)]
        return RollResult(
            expression=expression,
            rolls=rolls,
            modifier=parsed.modifier,
            total=sum(rolls) + parsed.modifier,
        )
