"""Cost control (plan 3.9): one JSON line per model call with its tokens and
estimated cost, spend per day and per campaign, and an optional daily cap.
No prompt or reply text is logged."""

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

# USD per million tokens (input, output), Anthropic list prices 2026-11.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


class LLMUnavailable(RuntimeError):
    """No model call could be made: the API failed or the daily cap is reached."""


class DailyCapReached(LLMUnavailable):
    pass


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in PRICES_PER_MTOK:
        raise KeyError(f"no price for model '{model}'; add it to PRICES_PER_MTOK")
    price_in, price_out = PRICES_PER_MTOK[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class CostLog:
    def __init__(
        self,
        path: Path,
        daily_cap_usd: float | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.daily_cap_usd = daily_cap_usd
        self._clock = clock

    def record(
        self, role: str, model: str, input_tokens: int, output_tokens: int, campaign: str
    ) -> float:
        cost = estimate_cost_usd(model, input_tokens, output_tokens)
        entry = {
            "timestamp": self._clock().isoformat(),
            "role": role,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "campaign": campaign,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as log:
            log.write(json.dumps(entry) + "\n")
        return cost

    def check_cap(self) -> None:
        """Refuse a new model call once today's spend has reached the cap."""
        if self.daily_cap_usd is None:
            return
        today = self.per_day().get(self._clock().date().isoformat(), 0.0)
        if today >= self.daily_cap_usd:
            raise DailyCapReached(
                f"Today's model spend ${today:.2f} has reached the cap of "
                f"${self.daily_cap_usd:.2f} (settings.yaml cost.daily_cap_usd)."
            )

    def per_day(self) -> dict[str, float]:
        return self._sum_by(lambda e: e["timestamp"][:10])

    def per_campaign(self) -> dict[str, float]:
        return self._sum_by(lambda e: e["campaign"])

    def campaign_spend(self, campaign: str) -> float:
        return self.per_campaign().get(campaign, 0.0)

    def report(self) -> str:
        """The text of `solo-dm cost`."""
        entries = self._entries()
        if not entries:
            return f"No model calls logged yet ({self.path})."
        lines = [f"Model spend, {len(entries)} calls, ${sum(e['cost_usd'] for e in entries):.4f}"
                 " in total (estimated from list prices)", "", "Per day:"]
        lines += [f"  {day}  ${cost:.4f}" for day, cost in sorted(self.per_day().items())]
        lines += ["", "Per campaign:"]
        lines += [f"  {name}  ${cost:.4f}" for name, cost in sorted(self.per_campaign().items())]
        return "\n".join(lines)

    def _entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

    def _sum_by(self, key: Callable[[dict], str]) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for entry in self._entries():
            totals[key(entry)] += entry["cost_usd"]
        return dict(totals)
