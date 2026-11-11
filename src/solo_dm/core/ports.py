"""Abstract ports. Core depends on these; infrastructure implements them."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class RollResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expression: str
    rolls: list[int]
    modifier: int
    total: int


class DicePort(ABC):
    @abstractmethod
    def roll(self, expression: str) -> RollResult:
        """Roll dice notation such as '1d20+5' and return every die face."""
