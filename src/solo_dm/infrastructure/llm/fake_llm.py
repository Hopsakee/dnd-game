"""FakeLLM: a keyword interpreter and placeholder narrator, so the game runs
with no model (M2) and playthroughs are free and deterministic."""

import re
from typing import Any

from solo_dm.core.ports import LLMPort
from solo_dm.core.turn.outcome import TurnOutcome
from solo_dm.core.turn.scene import SceneContext

# Checked in order, and each entry is a regex: "take" comes before "unlock" so
# that "pick up the key" is not read as "pick the lock", and "use ... key" means
# unlocking, the only thing a key does in this engine.
VERBS = [
    ("take", ["take", "grab", "get", "pick up"]),
    ("unlock", ["unlock", "pick the lock", "pick lock", "pick", r"use\b.*\bkey"]),
    ("attack", ["attack", "hit", "fight", "kill", "strike", "stab"]),
    ("open", ["open"]),
    ("search", ["search", "loot", "frisk", "rummage"]),
    ("look", ["look", "examine"]),
    ("move", ["go", "move", "walk", "head", "run", "enter", "north", "south", "east", "west"]),
]
STOPWORDS = {"the", "a", "an", "to", "at", "of"}


class FakeLLM(LLMPort):
    def interpret(
        self, player_input: str, scene: SceneContext, previous_error: str | None = None
    ) -> dict[str, Any]:
        text = player_input.lower()
        words = set(re.findall(r"[a-z]+", text)) - STOPWORDS
        action = next(
            (a for a, verbs in VERBS if any(re.search(rf"\b{v}\b", text) for v in verbs)),
            "other",
        )
        intent: dict[str, Any] = {"action": action, "approach": player_input}
        target = _target(action, words, scene)
        if target:
            intent["target_id"] = target
        return intent

    def narrate(self, outcome: TurnOutcome, scene: SceneContext) -> str:
        if outcome.blocked:
            return outcome.blocked
        names = _names(scene)
        lines = [_describe(e, names, scene) for e in outcome.events]
        if outcome.intent.action == "search" and not any(
            e.type in ("hidden_found", "body_searched") for e in outcome.events
        ):
            lines.append("You find nothing.")
        return " ".join(line for line in lines if line) or "Nothing much happens."


def _matches(words: set[str], *labels: str | None) -> bool:
    return any(words & set(re.findall(r"[a-z]+", label.lower())) for label in labels if label)


def _target(action: str, words: set[str], scene: SceneContext) -> str | None:
    if action in ("move", "unlock", "open"):
        found = [e.exit_id for e in scene.exits if _matches(words, e.direction, e.leads_to)]
        if not found and action != "move":
            found = [e.exit_id for e in scene.exits if e.locked]
    elif action == "attack":
        alive = [c for c in scene.creatures if c.alive]
        found = [c.creature_id for c in alive if _matches(words, c.creature_id, c.name)]
        if not found and len(alive) == 1:
            found = [alive[0].creature_id]
    elif action == "search":
        # "search" alone searches the room; "search the goblin" or "search the
        # body" searches a creature (resolution refuses a living one).
        found = [c.creature_id for c in scene.creatures if _matches(words, c.creature_id, c.name)]
        dead = [c.creature_id for c in scene.creatures if not c.alive]
        if not found and words & {"body", "corpse"} and len(dead) == 1:
            found = dead
    elif action == "take":
        found = [i.item_id for i in scene.items if _matches(words, i.item_id, i.name)]
    else:
        found = []
    return found[0] if found else None


def _names(scene: SceneContext) -> dict[str, str]:
    names = {c.creature_id: c.name for c in scene.creatures}
    names |= {m.character_id: m.name for m in scene.party}
    names |= {i.item_id: i.name for i in scene.items}
    names |= {i.item_id: i.name for m in scene.party for i in m.inventory}
    return names


def _describe(event, names: dict[str, str], scene: SceneContext) -> str:
    actor = names.get(event.actor_id or "", "")
    match event.type:
        case "moved_to":
            return f"You enter the {scene.location_name}."
        case "combat_started":
            order = ", ".join(names[c] for c in event.turn_order)
            return f"Combat! Initiative order: {order}."
        case "attack_rolled":
            result = "critically hits" if event.critical else "hits" if event.hit else "misses"
            return f"{actor} attacks {names[event.target_id]} and {result}."
        case "damage_dealt":
            return f"{names[event.target_id]} takes {event.amount} {event.damage_type} damage."
        case "creature_died":
            return f"{names[event.target_id]} dies."
        case "character_defeated":
            return f"{names[event.target_id]} falls."
        case "combat_ended":
            return "The fight is over."
        case "check_rolled" if event.skill == "perception":
            # No DC: it would tell whether anything is hidden here.
            return f"{actor} searches (rolls {event.total})."
        case "check_rolled":
            return f"{actor} tries ({event.total} vs DC {event.dc}): " + (
                "success." if event.success else "failure."
            )
        case "door_unlocked":
            return "The lock clicks open."
        case "hidden_found":
            exit_ = next((e for e in scene.exits if e.exit_id == event.target_id), None)
            thing = f"a hidden way {exit_.direction}" if exit_ else f"the {names[event.target_id]}"
            verb = "notice" if event.method == "passive" else "find"
            return f"You {verb} {thing}."
        case "body_searched":
            body = names[event.target_id]
            if not event.item_ids:
                return f"You find nothing on the {body}."
            return f"On the {body} you find: " + ", ".join(names[i] for i in event.item_ids) + "."
        case "item_taken":
            return f"{actor} takes the {names[event.item_id]}."
        case "adventure_won":
            return "You have won the adventure!"
        case "adventure_lost":
            return "The adventure is lost."
        case _:
            return ""
