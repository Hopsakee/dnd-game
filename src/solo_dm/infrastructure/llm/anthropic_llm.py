"""AnthropicLLM (plan 3.3, 3.9): interpreter and narrator on the Messages API.

Prompts live in prompts/*.md and stay provider-neutral: the interpreter is asked
for plain JSON, which core validates with its own Pydantic schema, so no
provider-specific structured-output feature is needed. Every call is logged
with its tokens and estimated cost, and refused once the daily cap is reached.

The client is passed in (the SDK's `anthropic.Anthropic`, or a fake in tests);
`make_anthropic_client` builds the real one from the resolved connection."""

import json
import re
from pathlib import Path
from typing import Any

from solo_dm.core.ports import LLMPort
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.outcome import TurnOutcome
from solo_dm.core.turn.scene import SceneContext
from solo_dm.infrastructure.llm.cost_log import CostLog, LLMUnavailable
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.settings import AnthropicConnection, LlmSettings, Role

PROMPTS = Path(__file__).parent / "prompts"
FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def interpreter_prompt() -> str:
    schema = json.dumps(Intent.model_json_schema(), indent=None)
    return (PROMPTS / "interpreter.md").read_text().replace("{{INTENT_SCHEMA}}", schema)


def narrator_prompt() -> str:
    return (PROMPTS / "narrator.md").read_text()


def make_anthropic_client(connection: AnthropicConnection):
    import anthropic  # only the live path needs the SDK

    return anthropic.Anthropic(
        api_key=connection.api_key.get_secret_value(),
        base_url=connection.base_url,
        default_headers=connection.headers,
    )


class AnthropicLLM(LLMPort):
    def __init__(self, client, settings: LlmSettings, cost_log: CostLog, campaign: str) -> None:
        self._client = client
        self._settings = settings
        self._cost_log = cost_log
        self._campaign = campaign
        self._system = {"interpreter": interpreter_prompt(), "narrator": narrator_prompt()}
        self.spent_usd = 0.0

    def interpret(
        self, player_input: str, scene: SceneContext, previous_error: str | None = None
    ) -> dict[str, Any]:
        content = f"<scene>\n{scene.model_dump_json(indent=1)}\n</scene>\n\n"
        content += f"<player_input>\n{player_input}\n</player_input>"
        if previous_error:
            content += (
                f"\n\nYour previous reply was invalid: {previous_error}\n"
                "Reply with the corrected JSON object only."
            )
        return _parse_intent(self._call("interpreter", content))

    def narrate(self, outcome: TurnOutcome, scene: SceneContext) -> str:
        decided = outcome.model_dump(mode="json", serialize_as_any=True)
        for event in decided["events"]:
            event.pop("dc", None)  # the narrator must not be able to give a DC away
        content = f"<outcome>\n{json.dumps(decided, indent=1)}\n</outcome>\n\n"
        content += f"<scene>\n{scene.model_dump_json(indent=1)}\n</scene>"
        try:
            return self._call("narrator", content).strip()
        except LLMUnavailable as unavailable:
            # The turn is already decided and applied; tell it plainly rather than lose it.
            plain = FakeLLM().narrate(outcome, scene)
            return f"(narrator unavailable: {unavailable}) {plain}"

    def _call(self, role: Role, content: str) -> str:
        self._cost_log.check_cap()
        settings = self._settings.role(role)
        model = self._settings.model_for(role)
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=settings.max_tokens,
                system=self._system[role],
                messages=[{"role": "user", "content": content}],
                output_config={"effort": settings.effort},
            )
        except Exception as failure:  # the SDK's errors, after its own retries
            raise LLMUnavailable(str(failure) or type(failure).__name__) from failure
        self.spent_usd += self._cost_log.record(
            role, model, response.usage.input_tokens, response.usage.output_tokens,
            campaign=self._campaign,
        )
        return "".join(b.text for b in response.content if b.type == "text")


def _parse_intent(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        # Core's validation rejects this key and retries with the error.
        return {"reply_was_not_a_json_object": text[:200]}
    return parsed
