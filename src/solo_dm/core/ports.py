"""Abstract ports. Core depends on these; infrastructure implements them."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from solo_dm.core.adventure.schema import Adventure
    from solo_dm.core.turn.outcome import TurnOutcome
    from solo_dm.core.turn.scene import SceneContext


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


class LLMPort(ABC):
    @abstractmethod
    def interpret(
        self, player_input: str, scene: "SceneContext", previous_error: str | None = None
    ) -> dict[str, Any]:
        """Turn free text into a raw intent. Core validates it; previous_error is set
        on the one retry after an invalid intent."""

    @abstractmethod
    def narrate(self, outcome: "TurnOutcome", scene: "SceneContext") -> str:
        """Describe an outcome Python already decided."""


class AdventureSourcePort(ABC):
    @abstractmethod
    def load(self, adventure_id: str) -> "Adventure":
        """Load and validate an adventure by id."""
