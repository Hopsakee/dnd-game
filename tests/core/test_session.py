from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.turn.session import GameSession

from ..fakes import FixedDice, ScriptedLLM
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter


def _session(llm, faces=()):
    adventure = tiny_adventure()
    state = initial_state(adventure, [fighter()], BESTIARY)
    return GameSession(adventure, state, llm, FixedDice(list(faces)))


def test_a_turn_interprets_resolves_and_narrates_the_outcome():
    llm = ScriptedLLM([{"action": "move", "target_id": "hall_to_den"}])
    session = _session(llm, faces=[15, 1])
    turn = session.play_turn("hero", "I head east")
    assert session.state.party_location == "den"
    assert turn.intent.action == "move"
    assert turn.narration == "narration 1"
    # The narrator gets the decided events and the scene after them.
    outcome, scene = llm.narrated[0]
    assert outcome.events[0].type == "moved_to" and scene.location_id == "den"


def test_an_invalid_intent_is_retried_once_with_the_error_then_a_question_is_asked():
    llm = ScriptedLLM([{"action": "dance"}, {"action": "move", "target_id": "hall_to_den"}])
    session = _session(llm, faces=[15, 1])
    turn = session.play_turn("hero", "I go east")
    assert "action" in llm.errors[1] and session.state.party_location == "den"
    assert turn.validation_error is None

    llm = ScriptedLLM([{"action": "dance"}, {"target_id": 3}])
    session = _session(llm)
    turn = session.play_turn("hero", "I boogie")
    assert turn.intent is None and turn.validation_error
    # The question names what can be done here, from the scene, with no model call.
    assert turn.narration == (
        "I did not understand that. Do you want to go east or go north, or something else?"
    )
    assert llm.narrated == []


def test_a_target_the_party_cannot_perceive_counts_as_invalid():
    llm = ScriptedLLM([{"action": "take", "target_id": "amulet"}] * 2)
    turn = _session(llm).play_turn("hero", "grab the amulet")
    assert "amulet" in turn.validation_error


def test_low_confidence_asks_to_confirm_instead_of_resolving():
    llm = ScriptedLLM(
        [{"action": "move", "target_id": "hall_to_den", "confidence": "low",
          "approach": "wander east"}]
    )
    session = _session(llm)
    turn = session.play_turn("hero", "maybe east?")
    assert turn.narration == "Do you mean to go east, or something else?"
    assert session.state.party_location == "hall"


def test_compound_input_resolves_the_first_action_and_says_so():
    llm = ScriptedLLM([{"action": "move", "target_id": "hall_to_den", "compound": True}])
    turn = _session(llm, faces=[15, 1]).play_turn("hero", "go east and attack")
    assert turn.compound is True
    assert turn.narration.endswith("(Only the first action was done.)")


def test_flag_marks_the_last_turn():
    llm = ScriptedLLM([{"action": "look"}])
    session = _session(llm)
    session.play_turn("hero", "look around")
    session.flag_last_turn("the narrator invented a door")
    assert session.turns[-1].flag_note == "the narrator invented a door"


def test_the_clarifying_question_offers_the_creatures_and_items_here():
    llm = ScriptedLLM([{"action": "move", "target_id": "hall_to_den"}, {}, {}])
    session = _session(llm, faces=[1] * 10)
    session.play_turn("hero", "go east")
    question = session.play_turn("hero", "flibber").narration
    assert "attack Goblin Warrior" in question and "take Iron Key" in question


def test_the_narrator_hears_the_last_three_turns():
    # Azzinax play test, 2026-11-14 (flag 25): Azzinax dropped his knife, and the
    # next turn he was sharpening it again; the narrator got no earlier turns.
    llm = ScriptedLLM([{"action": "look"}] * 5)
    session = _session(llm)
    for line in ["one", "two", "three", "four", "five"]:
        session.play_turn("hero", line)
    _, scene = llm.narrated[-1]
    assert [(t.player_input, t.narration) for t in scene.recent] == [
        ("two", "narration 2"), ("three", "narration 3"), ("four", "narration 4")]
