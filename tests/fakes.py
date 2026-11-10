"""Test doubles for ports."""

from solo_dm.core.ports import DicePort, RollResult
from solo_dm.core.rules.dice_expression import parse_dice


class FixedDice(DicePort):
    """Returns the given die faces in order, one face per die rolled."""

    def __init__(self, faces: list[int]) -> None:
        self._faces = list(faces)
        self.expressions: list[str] = []

    def roll(self, expression: str) -> RollResult:
        parsed = parse_dice(expression)
        rolls = [self._next(parsed.sides) for _ in range(parsed.count)]
        self.expressions.append(expression)
        return RollResult(
            expression=expression,
            rolls=rolls,
            modifier=parsed.modifier,
            total=sum(rolls) + parsed.modifier,
        )

    def _next(self, sides: int) -> int:
        if not self._faces:
            raise AssertionError("FixedDice ran out of faces")
        face = self._faces.pop(0)
        assert 1 <= face <= sides, f"face {face} impossible on a d{sides}"
        return face
