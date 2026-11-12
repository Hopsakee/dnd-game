"""M3: every model call is logged with its tokens and estimated cost (plan 3.9)."""

import json
from datetime import UTC, datetime

import pytest

from solo_dm.infrastructure.llm.cost_log import CostLog, DailyCapReached, estimate_cost_usd

NOV_12 = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)
NOV_13 = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def test_cost_is_estimated_from_the_models_price_per_million_tokens():
    # Haiku 5.5: $0.10 in, $0.50 out per million tokens.
    assert estimate_cost_usd("claude-haiku-5-5", 1_000_000, 2_000_000) == pytest.approx(1.10)
    assert estimate_cost_usd("claude-sonnet-5-5", 1000, 1000) == pytest.approx(0.012)


def test_an_unknown_model_has_no_price_and_says_so():
    with pytest.raises(KeyError, match="no price"):
        estimate_cost_usd("claude-mystery", 1, 1)


def test_each_call_is_one_json_line_without_prompt_or_reply_text(tmp_path):
    log = CostLog(tmp_path / "logs" / "calls.jsonl", clock=lambda: NOV_12)
    log.record("interpreter", "claude-haiku-5-5", 1200, 80, campaign="c1")
    (line,) = (tmp_path / "logs" / "calls.jsonl").read_text().splitlines()
    entry = json.loads(line)
    assert entry == {
        "timestamp": "2026-11-12T20:00:00+00:00", "role": "interpreter",
        "model": "claude-haiku-5-5", "input_tokens": 1200, "output_tokens": 80,
        "cost_usd": pytest.approx(0.00016), "campaign": "c1",
    }


def test_spend_is_summed_per_day_and_per_campaign(tmp_path):
    now = [NOV_12]
    log = CostLog(tmp_path / "calls.jsonl", clock=lambda: now[0])
    log.record("interpreter", "claude-haiku-5-5", 1_000_000, 0, campaign="a")
    log.record("narrator", "claude-haiku-5-5", 0, 1_000_000, campaign="b")
    now[0] = NOV_13
    log.record("narrator", "claude-haiku-5-5", 0, 2_000_000, campaign="b")
    assert log.per_day() == {"2026-11-12": pytest.approx(0.60), "2026-11-13": pytest.approx(1.0)}
    assert log.per_campaign() == {"a": pytest.approx(0.10), "b": pytest.approx(1.50)}
    assert log.campaign_spend("b") == pytest.approx(1.50)


def test_an_empty_log_has_no_spend(tmp_path):
    log = CostLog(tmp_path / "missing.jsonl")
    assert log.per_day() == {} and log.campaign_spend("x") == 0


def test_the_daily_cap_refuses_new_calls_once_reached(tmp_path):
    now = [NOV_12]
    log = CostLog(tmp_path / "calls.jsonl", daily_cap_usd=0.5, clock=lambda: now[0])
    log.check_cap()
    log.record("narrator", "claude-haiku-5-5", 0, 1_000_000, campaign="a")  # $0.50
    with pytest.raises(DailyCapReached, match="0.50"):
        log.check_cap()
    now[0] = NOV_13  # a new day starts from zero
    log.check_cap()


def test_no_cap_never_refuses(tmp_path):
    log = CostLog(tmp_path / "calls.jsonl", clock=lambda: NOV_12)
    log.record("narrator", "claude-haiku-5-5", 0, 100_000_000, campaign="a")
    log.check_cap()
