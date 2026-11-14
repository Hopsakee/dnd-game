"""M3: the Anthropic adapter, against a fake client shaped like the SDK's
(client.messages.create -> response with .content blocks and .usage)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from solo_dm.core.state.events import CheckRolled, QuestFlagSet
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.outcome import TurnOutcome
from solo_dm.core.turn.scene import SceneContext
from solo_dm.infrastructure.llm.anthropic_llm import AnthropicLLM
from solo_dm.infrastructure.llm.cost_log import CostLog, DailyCapReached
from solo_dm.infrastructure.settings import load_settings

ROOT = Path(__file__).parent.parent.parent
SCENE = SceneContext(
    location_id="hall", location_name="Hall", description="A hall.", exits=[], creatures=[],
    items=[], party=[], in_combat=False, active_combatant=None,
)


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **request):
        self.calls.append(request)
        text = self.replies.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
            stop_reason="end_turn",
        )


def _llm(tmp_path, replies, cap=None):
    client = SimpleNamespace(messages=FakeMessages(replies))
    log = CostLog(tmp_path / "calls.jsonl", daily_cap_usd=cap,
                  clock=lambda: datetime(2026, 11, 12, tzinfo=UTC))
    llm = AnthropicLLM(client, load_settings(ROOT).llm, log, campaign="core@1")
    return llm, client.messages, log


def test_interpret_returns_the_json_the_model_wrote(tmp_path):
    llm, messages, _ = _llm(tmp_path, ['{"action": "search"}'])
    assert llm.interpret("I search the room", SCENE) == {"action": "search"}
    request = messages.calls[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["max_tokens"] == 2048
    assert request["output_config"] == {"effort": "low"}
    assert "temperature" not in request  # Haiku 5.5 refuses a non-default one


def test_the_interpreter_prompt_carries_the_intent_schema_and_the_scene(tmp_path):
    llm, messages, _ = _llm(tmp_path, ['{"action": "look"}'])
    llm.interpret("look", SCENE)
    request = messages.calls[0]
    assert json.dumps(Intent.model_json_schema()["properties"]["action"]) in request["system"]
    user = request["messages"][0]["content"]
    assert '"location_id": "hall"' in user and "look" in user


def test_a_fenced_json_reply_is_accepted(tmp_path):
    llm, _, _ = _llm(tmp_path, ['```json\n{"action": "look"}\n```'])
    assert llm.interpret("look", SCENE) == {"action": "look"}


def test_a_reply_that_is_not_json_comes_back_as_something_core_will_reject(tmp_path):
    llm, _, _ = _llm(tmp_path, ["I think you want to look."])
    raw = llm.interpret("look", SCENE)
    with pytest.raises(ValueError):
        Intent.model_validate(raw)


def test_the_retry_tells_the_model_what_was_wrong(tmp_path):
    llm, messages, _ = _llm(tmp_path, ['{"action": "look"}'])
    llm.interpret("look", SCENE, previous_error="unknown ids ['dragon']")
    assert "unknown ids ['dragon']" in messages.calls[0]["messages"][0]["content"]


def test_narrate_returns_the_text_and_never_shows_the_model_a_dc(tmp_path):
    llm, messages, _ = _llm(tmp_path, ["  You search the dusty hall and find nothing.  "])
    check = CheckRolled(actor_id="hero", ability="WIS", skill="perception", d20=4, modifier=3,
                        dc=15, total=7, success=False)
    outcome = TurnOutcome(actor_id="hero", intent=Intent(action="search"), events=[check])
    assert llm.narrate(outcome, SCENE) == "You search the dusty hall and find nothing."
    request = messages.calls[0]
    assert request["output_config"] == {"effort": "medium"}
    sent = request["messages"][0]["content"]
    assert '"total": 7' in sent and '"dc"' not in sent and "15" not in sent
    assert "Never state a DC" in request["system"]


def test_every_call_is_logged_with_role_tokens_and_campaign(tmp_path):
    llm, _, log = _llm(tmp_path, ['{"action": "look"}', "You look around."])
    llm.interpret("look", SCENE)
    flag = QuestFlagSet(actor_id="hero", flag="x")
    llm.narrate(TurnOutcome(actor_id="hero", intent=Intent(action="look"), events=[flag]), SCENE)
    lines = [json.loads(line) for line in log.path.read_text().splitlines()]
    assert [(e["role"], e["input_tokens"], e["output_tokens"], e["campaign"]) for e in lines] == [
        ("interpreter", 1000, 100, "core@1"), ("narrator", 1000, 100, "core@1")]
    assert llm.spent_usd == pytest.approx(2 * (1000 * 0.10 + 100 * 0.50) / 1_000_000)


def test_the_daily_cap_stops_a_call_before_it_is_made(tmp_path):
    llm, messages, log = _llm(tmp_path, [], cap=0.0)
    with pytest.raises(DailyCapReached):
        llm.interpret("look", SCENE)
    assert messages.calls == []


class BrokenMessages:
    def create(self, **request):
        raise ConnectionError("broker unreachable")


def _broken(tmp_path):
    from solo_dm.infrastructure.llm.anthropic_llm import LLMUnavailable

    log = CostLog(tmp_path / "calls.jsonl")
    llm = AnthropicLLM(SimpleNamespace(messages=BrokenMessages()), load_settings(ROOT).llm, log,
                       campaign="c")
    return llm, LLMUnavailable


def test_an_unreachable_model_is_one_clear_error_for_the_interpreter(tmp_path):
    llm, LLMUnavailable = _broken(tmp_path)
    with pytest.raises(LLMUnavailable, match="broker unreachable"):
        llm.interpret("look", SCENE)


def test_a_cap_reached_is_also_unavailable(tmp_path):
    from solo_dm.infrastructure.llm.anthropic_llm import LLMUnavailable

    assert issubclass(DailyCapReached, LLMUnavailable)


def test_the_narrator_falls_back_to_plain_narration_so_a_decided_turn_is_never_lost(tmp_path):
    llm, _ = _broken(tmp_path)
    flag = QuestFlagSet(actor_id="hero", flag="x")
    text = llm.narrate(TurnOutcome(actor_id="hero", intent=Intent(action="look"), events=[flag]),
                       SCENE)
    assert text.startswith("(narrator unavailable: broker unreachable)")


def test_the_narrator_hears_next_door_only_on_turns_about_perceiving(tmp_path):
    from solo_dm.core.turn.scene import SceneSense

    scene = SCENE.model_copy(update={"nearby": [SceneSense(direction="east", senses="woodsmoke")]})
    llm, messages, _ = _llm(tmp_path, ["You look.", "You take it."])
    llm.narrate(TurnOutcome(actor_id="hero", intent=Intent(action="look"), events=[]), scene)
    llm.narrate(TurnOutcome(actor_id="hero", intent=Intent(action="take"), events=[]), scene)
    look, take = (call["messages"][0]["content"] for call in messages.calls)
    assert "woodsmoke" in look and "woodsmoke" not in take


def test_only_the_narration_reaches_the_player_not_the_models_planning(tmp_path):
    # Azzinax play test, 2026-11-14 (flag 28): the narrator wrote its reasoning
    # ("Only the move happened, so I narrate just that.") above the story.
    reply = ("The player walks east. Only the move happened, so I narrate just that.\n\n"
             "<narration>\nYou step out into the North Corridor.\n</narration>")
    llm, messages, _ = _llm(tmp_path, [reply, "You step out into the corridor."])
    outcome = TurnOutcome(actor_id="hero", intent=Intent(action="look"), events=[])
    assert llm.narrate(outcome, SCENE) == "You step out into the North Corridor."
    assert "<narration>" in messages.calls[0]["system"]
    # A reply without the tags is taken whole, rather than lost.
    assert llm.narrate(outcome, SCENE) == "You step out into the corridor."


def test_the_narrator_is_not_shown_initiative_rolls(tmp_path):
    # Flag 23: "Don't narrate that initiative is rolled. Just tell that I am quicker."
    from solo_dm.core.state.events import CombatStarted, InitiativeRoll
    llm, messages, _ = _llm(tmp_path, ["You are quicker."])
    started = CombatStarted(initiative=[InitiativeRoll(combatant_id="hero", d20=15, bonus=1,
                                                       total=16)],
                            turn_order=["hero"])
    llm.narrate(TurnOutcome(actor_id="hero", intent=Intent(action="move"), events=[started]),
                SCENE)
    sent = messages.calls[0]["messages"][0]["content"]
    assert '"turn_order"' in sent and "initiative" not in sent
