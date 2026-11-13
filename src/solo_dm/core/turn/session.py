"""The turn pipeline (plan 3.5): interpret -> validate -> resolve -> apply ->
narrate, with a turn log. Persistence of the log arrives in M4."""

from pydantic import BaseModel, ValidationError

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import DicePort, LLMPort
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.events import Event
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.outcome import TurnOutcome
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.scene import SceneContext, build_scene

COMPOUND_NOTE = "(Only the first action was done.)"
NO_RULE_HINT = "so nothing happened. Try saying it another way."


class TurnRecord(BaseModel):
    turn_number: int
    actor_id: str
    player_id: str
    player_input: str
    intent: Intent | None
    validation_error: str | None
    events: list[Event]
    narration: str
    fallback: bool = False
    compound: bool = False
    flag_note: str | None = None


class GameSession:
    def __init__(
        self, adventure: Adventure, state: GameState, llm: LLMPort, dice: DicePort
    ) -> None:
        self.adventure = adventure
        self.state = state
        self._llm = llm
        self._dice = dice
        self.turns: list[TurnRecord] = []

    def scene(self) -> SceneContext:
        return build_scene(self.state, self.adventure)

    def play_turn(self, actor_id: str, player_input: str) -> TurnRecord:
        scene = self.scene()
        intent, error = self._interpret(player_input, scene)
        if intent is None or intent.action == "other":
            # Not an action in the game: ask what they want, from the scene.
            return self._record(actor_id, player_input, intent, error, [],
                                clarifying_question(scene))
        if intent.confidence == "low":
            question = f"Do you mean to {describe_intent(intent, scene)}, or something else?"
            return self._record(actor_id, player_input, intent, None, [], question)

        resolution = resolve_intent(self.state, self.adventure, actor_id, intent, self._dice)
        if resolution.rule_missing:
            # Said plainly: the narrator would turn it into "you cannot" in the fiction.
            narration = f"{resolution.blocked.rstrip('.')}, {NO_RULE_HINT}"
            return self._record(actor_id, player_input, intent, None, [], narration)
        self.state = apply_events(self.state, resolution.events)
        outcome = TurnOutcome(
            actor_id=actor_id, intent=intent, events=resolution.events,
            blocked=resolution.blocked, player_input=player_input,
        )
        narration = self._llm.narrate(outcome, self.scene())
        if intent.compound:
            narration = f"{narration} {COMPOUND_NOTE}"
        return self._record(actor_id, player_input, intent, None, resolution.events, narration)

    def flag_last_turn(self, note: str) -> None:
        last = self.turns[-1]
        self.turns[-1] = last.model_copy(update={"flag_note": note})

    def _interpret(self, player_input: str, scene: SceneContext):
        error = None
        for _ in range(2):  # one retry with the validation error
            raw = self._llm.interpret(player_input, scene, error)
            try:
                intent = Intent.model_validate(raw)
            except ValidationError as invalid:
                error = str(invalid)
                continue
            known = scene.valid_ids()
            unknown = [i for i in (intent.target_id, intent.item_id) if i and i not in known]
            if not unknown:
                return intent, None
            error = f"unknown ids {unknown}; choose from {sorted(known)}"
        return None, error

    def _record(self, actor_id, player_input, intent, error, events, narration) -> TurnRecord:
        record = TurnRecord(
            turn_number=len(self.turns) + 1,
            actor_id=actor_id,
            player_id=self.state.party[actor_id].player_id,
            player_input=player_input,
            intent=intent,
            validation_error=error,
            events=events,
            narration=narration,
            compound=bool(intent and intent.compound),
            fallback=bool(intent and intent.action == "ability_check"),
        )
        self.turns.append(record)
        return record


def describe_intent(intent: Intent, scene: SceneContext) -> str:
    """An intent in plain words, from the scene's names, to ask back with."""
    names = {e.exit_id: f"the way {e.direction}" for e in scene.exits}
    names |= {c.creature_id: f"the {c.name}" for c in scene.creatures}
    names |= {i.item_id: f"the {i.name}" for i in scene.items}
    names |= {i.item_id: f"the {i.name}" for m in scene.party for i in m.inventory}
    target = names.get(intent.target_id or "", "")
    exit_ = next((e for e in scene.exits if e.exit_id == intent.target_id), None)
    if intent.action == "ability_check":
        how = (intent.skill or intent.ability or "an ability").replace("_", " ")
        return f"try it with {how}" + (f" on {target}" if target else "")
    verb = {
        "move": f"go {exit_.direction}" if exit_ else "go somewhere",
        "attack": "attack", "take": "take", "use_item": "use", "open": "open",
        "unlock": "unlock", "talk": "talk to", "look": "look around", "search": "search",
    }[intent.action]
    if intent.action in ("move", "look"):
        return verb
    if intent.action == "search" and not target:
        target = "the room"
    return f"{verb} {target}".strip()


def clarifying_question(scene: SceneContext) -> str:
    """Asked after the retry also failed (plan 3.5 step 3): what can be done here,
    built from the scene so it needs no model call and names nothing hidden."""
    options = [f"go {e.direction}" for e in scene.exits]
    for c in scene.creatures:
        if not c.alive:
            options.append(f"search the {c.name}")
        elif c.attitude == "hostile":
            options.append(f"attack {c.name}")
        else:
            options.append(f"talk to {c.name}")
    options += [f"take {i.name}" for i in scene.items]
    listed = " or ".join(options) if len(options) <= 2 else (
        ", ".join(options[:-1]) + " or " + options[-1])
    return f"I did not understand that. Do you want to {listed}, or something else?"
