"""Abstract ports. Core depends on these; infrastructure implements them."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from solo_dm.core.adventure.schema import Adventure
    from solo_dm.core.state.models import GameState
    from solo_dm.core.turn.outcome import TurnOutcome
    from solo_dm.core.turn.scene import SceneContext
    from solo_dm.core.turn.session import StoredCampaign, TurnRecord


class RollResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expression: str
    rolls: list[int]
    modifier: int
    total: int


class LoreSnippet(BaseModel):
    """One lore file: background the model may use. Never mechanics (plan 3.8)."""

    model_config = ConfigDict(frozen=True)

    topic: str
    tags: tuple[str, ...]
    text: str


class LorePort(ABC):
    @abstractmethod
    def search(self, query: str | None = None, tags: Iterable[str] = ()) -> list[LoreSnippet]:
        """Lore carrying any of the tags, plus the best full-text matches for query."""


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


class CampaignSummary(BaseModel):
    campaign_id: int
    adventure_id: str
    title: str
    created_at: str
    turns: int
    outcome: str


class CampaignStorePort(ABC):
    @abstractmethod
    def create(self, adventure: "Adventure", initial_state: "GameState") -> int:
        """Start a campaign with a frozen copy of the adventure; returns its id."""

    @abstractmethod
    def record_turn(self, campaign_id: int, turn: "TurnRecord", state: "GameState") -> None:
        """Store one turn, its events and the snapshot after it, in one transaction."""

    @abstractmethod
    def flag_turn(self, campaign_id: int, turn_number: int, note: str) -> None:
        """Attach the player's flag note to a turn in play."""

    @abstractmethod
    def load(self, campaign_id: int) -> "StoredCampaign":
        """Read a campaign back to resume it."""

    @abstractmethod
    def list_campaigns(self) -> list[CampaignSummary]:
        """Every campaign, oldest first."""

    @abstractmethod
    def rewind(self, campaign_id: int, to_turn: int) -> None:
        """Return to the state after to_turn (0: the start). Later turns are marked
        superseded, never deleted."""
