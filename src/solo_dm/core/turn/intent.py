"""The interpreter's output (plan 3.6). The acting character is attached by
Python, never produced by the model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from solo_dm.core.state.models import Ability

Action = Literal[
    "move", "attack", "take", "use_item", "open", "unlock", "talk", "ability_check", "look",
    "search", "other",
]


class Intent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    target_id: str | None = None
    item_id: str | None = None
    ability: Ability | None = None
    skill: str | None = None
    approach: str = ""
    task_category: Literal["trivial", "easy", "medium", "hard"] | None = None
    lore_query: str | None = None
    confidence: Literal["low", "medium", "high"] = "high"
    compound: bool = False  # the input held more actions; only the first is resolved
