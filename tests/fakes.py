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


class ScriptedLLM:
    """LLMPort fake: returns scripted raw intents and numbered placeholder narration."""

    def __init__(self, intents: list[dict]) -> None:
        self._intents = list(intents)
        self.errors: list[str | None] = []
        self.narrated: list = []

    def interpret(self, player_input, scene, previous_error=None):
        self.errors.append(previous_error)
        return self._intents.pop(0)

    def narrate(self, outcome, scene):
        self.narrated.append((outcome, scene))
        return f"narration {len(self.narrated)}"
