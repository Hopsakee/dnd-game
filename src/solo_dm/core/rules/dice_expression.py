"""Dice notation ("2d6+3") parsing. Pure: rolling happens behind DicePort."""

import re

from pydantic import BaseModel, ConfigDict, Field

_DICE_PATTERN = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")


class DiceExpression(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int = Field(ge=1)
    sides: int = Field(ge=1)
    modifier: int = 0


def parse_dice(text: str) -> DiceExpression:
    match = _DICE_PATTERN.match(text.replace(" ", ""))
    if match is None:
        raise ValueError(f"not a dice expression: {text!r}")
    count, sides, modifier = match.groups()
    count_value = int(count) if count else 1
    if count_value < 1 or int(sides) < 1:
        raise ValueError(f"dice count and sides must be at least 1: {text!r}")
    return DiceExpression(count=count_value, sides=int(sides), modifier=int(modifier or 0))
