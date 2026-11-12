"""Difficulty for the ability-check fallback (plan 3.7). The interpreter picks a
task category, never a number; Python maps it to a DC (SRD 5.2 typical DCs) and
adjusts it by the target creature's attitude."""

from typing import Literal

from solo_dm.core.state.models import Attitude

TaskCategory = Literal["trivial", "easy", "medium", "hard"]

DC_BY_TASK_CATEGORY: dict[TaskCategory, int] = {"trivial": 5, "easy": 10, "medium": 15, "hard": 20}
DC_SHIFT_BY_ATTITUDE: dict[Attitude, int] = {"hostile": 5, "indifferent": 0, "friendly": -5}
DEFAULT_TASK_CATEGORY: TaskCategory = "medium"


def fallback_dc(category: TaskCategory | None, attitude: Attitude | None) -> int:
    dc = DC_BY_TASK_CATEGORY[category or DEFAULT_TASK_CATEGORY]
    return dc + (DC_SHIFT_BY_ATTITUDE[attitude] if attitude else 0)
