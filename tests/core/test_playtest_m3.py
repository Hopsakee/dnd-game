"""Jelle's M3 play test with Haiku, 2026-11-13 (playtest-flags.md 2, 4, 5, 7):
plain talk and questions about your own character are things you can always do,
a missing rule is said plainly, and a doubtful intent is asked back as a real
question built from the scene."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.core.turn.session import GameSession

from ..fakes import FixedDice, ScriptedLLM
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter


def _session(llm, faces=(), at_den=False, attitude="hostile"):
    goblin = {"id": "goblin", "srd_ref": "goblin_warrior", "location": "den",
              "attitude": attitude}
    adventure = tiny_adventure(entities=[goblin])
    state = initial_state(adventure, [fighter()], BESTIARY)
    if at_den:
        state = state.model_copy(update={"party_location": "den"})
    return GameSession(adventure, state, llm, FixedDice(list(faces)))


def test_talking_to_a_creature_is_narrated_and_changes_nothing():
    # Flag 2: "Ask the Goblin its name" was Blocked: talk had no rule.
    llm = ScriptedLLM([{"action": "talk", "target_id": "goblin", "approach": "ask its name"}])
    session = _session(llm, at_den=True, attitude="indifferent")
    before = session.state
    turn = session.play_turn("hero", "Ask the goblin its name")
    outcome, _ = llm.narrated[0]
    assert outcome.blocked is None and outcome.events == []
    assert turn.narration == "narration 1"
    assert session.state.model_dump(exclude={"turn_number"}) == before.model_dump(
        exclude={"turn_number"})


def test_talking_to_something_that_is_not_a_creature_is_blocked():
    session = _session(ScriptedLLM([]))
    intent = Intent(action="talk", target_id="hall_to_den")
    resolution = resolve_intent(session.state, session.adventure, "hero", intent, FixedDice([]))
    assert resolution.blocked == "You can only talk to someone who is here."


def test_talking_in_combat_uses_your_turn():
    llm = ScriptedLLM([{"action": "move", "target_id": "hall_to_den"},
                       {"action": "talk", "target_id": "goblin"}])
    # Initiative: hero 15, goblin 1; after the talk the goblin takes its turn and attacks.
    session = _session(llm, faces=[15, 1, 1, 2])
    session.play_turn("hero", "go east")
    turn = session.play_turn("hero", "Hello goblin, join my quest?")
    attacks = [e for e in turn.events if e.type == "attack_rolled"]
    assert [a.actor_id for a in attacks] == ["goblin"]


def test_a_missing_rule_is_said_plainly_without_the_narrator():
    # Flags 2 and 4: the narrator dressed "no rule yet" up as "you cannot".
    llm = ScriptedLLM([{"action": "use_item"}])
    turn = _session(llm).play_turn("hero", "use the iron key")
    assert llm.narrated == []
    assert turn.narration == (
        "The game has no rule for that yet (use_item), so nothing happened. "
        "Try saying it another way."
    )


def test_input_that_is_not_a_game_action_gets_the_clarifying_question():
    llm = ScriptedLLM([{"action": "other", "approach": "tells a joke"}])
    turn = _session(llm).play_turn("hero", "why did the owlbear cross the road")
    assert llm.narrated == []
    assert turn.narration.startswith("I did not understand that. Do you want to go east")


def test_low_confidence_asks_back_in_words_built_from_the_scene():
    # Flag 7: "Do you mean: attacks the Goblin Warrior with a rifle, though ..."
    llm = ScriptedLLM([{"action": "attack", "target_id": "goblin", "confidence": "low",
                        "approach": "attacks with a rifle, though the fighter has none"}])
    session = _session(llm, at_den=True, attitude="indifferent")
    turn = session.play_turn("hero", "attack with my M16")
    assert turn.narration == "Do you mean to attack the Goblin Warrior, or something else?"
    assert llm.narrated == []


def test_the_scene_tells_the_model_what_the_party_wears_and_wields():
    # Flag 5: "No reason why I can't know what I am wearing."
    (member,) = _session(ScriptedLLM([])).scene().party
    assert member.weapons == ["Greatsword"]
    assert member.armor_class == 17
