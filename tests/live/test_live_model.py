"""Live tests (plan 6, level 3): the real model, through the same wiring the game
uses (in the box: the credential broker). Run only on request:

    uv run pytest -m live

Each run costs a fraction of a cent with Haiku; calls are logged under the
campaign 'live-tests', so `uv run solo-dm cost` shows them."""

import os

import pytest

from solo_dm.composition_root import PROJECT_ROOT, SOLO_ACTOR, build_terminal_game
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.outcome import TurnOutcome
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.anthropic_llm import AnthropicLLM, make_anthropic_client
from solo_dm.infrastructure.llm.cost_log import CostLog
from solo_dm.infrastructure.settings import anthropic_connection, load_settings

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def llm():
    settings = load_settings(PROJECT_ROOT)
    client = make_anthropic_client(anthropic_connection(settings, os.environ))
    log = CostLog(settings.paths.llm_call_log, settings.cost.daily_cap_usd)
    return AnthropicLLM(client, settings.llm, log, campaign="live-tests")


def _session(llm, moves=()):
    from rich.console import Console

    game = build_terminal_game("core_five_rooms", SeededDice(0), llm, Console(quiet=True))
    for move in moves:  # walk there with exact intents, no model calls
        exit_id = next(e.exit_id for e in game.session.scene().exits if e.direction == move)
        game.session.state = _apply_move(game, exit_id)
    return game.session


def _apply_move(game, exit_id):
    from solo_dm.core.state.apply import apply_events
    from solo_dm.core.turn.resolve import resolve_intent

    session = game.session
    intent = Intent(action="move", target_id=exit_id)
    resolution = resolve_intent(session.state, session.adventure, SOLO_ACTOR, intent, SeededDice(0))
    return apply_events(session.state, resolution.events)


def _intent(llm, session, text) -> Intent:
    return Intent.model_validate(llm.interpret(text, session.scene()))


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("I walk north through the gate", "move"),
        ("head through the open gate", "move"),
        ("I look around", "look"),
        ("search the area for anything hidden", "search"),
    ],
)
def test_typical_inputs_at_the_entrance_become_valid_intents(llm, text, action):
    session = _session(llm)
    intent = _intent(llm, session, text)
    assert intent.action == action
    assert intent.target_id is None or intent.target_id in session.scene().valid_ids()


def test_attacking_the_goblin_targets_it(llm):
    session = _session(llm, moves=["north", "east"])
    intent = _intent(llm, session, "I swing my greatsword at the goblin!")
    goblin = next(c.creature_id for c in session.scene().creatures)
    assert (intent.action, intent.target_id) == ("attack", goblin)


def test_something_without_a_rule_becomes_an_ability_check_without_a_number(llm):
    session = _session(llm, moves=["north", "east"])
    intent = _intent(llm, session, "I try to talk the goblin into letting me pass peacefully")
    assert intent.action == "ability_check"
    assert intent.ability == "CHA" and intent.task_category is not None


def test_the_full_pipeline_plays_a_turn_and_the_narration_hides_the_dc(llm):
    session = _session(llm)
    turn = session.play_turn(SOLO_ACTOR, "I search the stairs carefully")
    assert turn.intent is not None and turn.intent.action == "search"
    assert turn.narration and "DC" not in turn.narration
    assert "difficulty" not in turn.narration.lower()


def test_the_narrator_tells_a_blocked_action_without_changing_it(llm):
    session = _session(llm)
    outcome = TurnOutcome(actor_id=SOLO_ACTOR, intent=Intent(action="take", target_id="x"),
                          events=[], blocked="There is no lantern here.")
    text = llm.narrate(outcome, session.scene())
    assert text and "(narrator unavailable" not in text


# Jelle's play test, 2026-11-13 (playtest-flags.md 2, 3, 5, 6).

def test_asking_a_creature_something_is_talk_and_is_narrated_as_speech(llm):
    session = _session(llm, moves=["north", "east"])  # the guard room's goblin
    turn = session.play_turn(SOLO_ACTOR, "I ask the goblin what its name is")
    assert turn.intent is not None and turn.intent.action == "talk"
    assert "no rule" not in turn.narration


def test_a_question_about_your_own_gear_is_answered_from_the_scene(llm):
    session = _session(llm)
    turn = session.play_turn(SOLO_ACTOR, "What armor am I wearing, and do I have a weapon?")
    assert turn.intent is not None and turn.intent.action == "look"
    text = turn.narration.lower()
    assert "chain mail" in text and "greatsword" in text


def test_a_door_opened_with_the_key_is_not_narrated_as_lock_picking(llm):
    from solo_dm.core.state.events import DoorUnlocked

    session = _session(llm, moves=["north"])
    unlocked = DoorUnlocked(actor_id=SOLO_ACTOR, exit_id="hall_to_shrine", method="key")
    outcome = TurnOutcome(actor_id=SOLO_ACTOR, events=[unlocked], intent=Intent(
        action="unlock", target_id="hall_to_shrine", approach="use the key I found"))
    text = llm.narrate(outcome, session.scene()).lower()
    assert "key" in text and "pick" not in text and "pins" not in text


def test_a_failed_persuasion_does_not_name_the_skill(llm):
    from solo_dm.core.state.events import CheckRolled

    session = _session(llm)
    check = CheckRolled(actor_id=SOLO_ACTOR, ability="CHA", skill="persuasion", d20=3,
                        modifier=0, dc=15, total=3, success=False)
    outcome = TurnOutcome(actor_id=SOLO_ACTOR, events=[check], intent=Intent(
        action="ability_check", ability="CHA", skill="persuasion",
        approach="ask the empty stairs to let me pass"))
    text = llm.narrate(outcome, session.scene()).lower()
    assert "persuasion" not in text and "charisma" not in text and "check" not in text


# Jelle's second play test, 2026-11-13 (playtest-flags.md 8, 9, 11, 12).

def test_listening_in_the_hall_picks_up_the_smoke_from_the_guard_room(llm):
    session = _session(llm, moves=["north"])
    turn = session.play_turn(SOLO_ACTOR, "I stand still, listen and sniff the air")
    assert turn.intent is not None and turn.intent.action == "look"
    assert "smoke" in turn.narration.lower()


def test_combat_starting_is_told_without_mechanics(llm):
    session = _session(llm, moves=["north"])
    turn = session.play_turn(SOLO_ACTOR, "go east")
    assert "combat_started" in [e.type for e in turn.events]
    text = turn.narration.lower()
    assert "initiative" not in text and "your turn" not in text and "rolled" not in text


def test_a_picked_up_item_is_not_given_magic_it_does_not_have(llm):
    session = _session(llm, moves=["north"])
    turn = session.play_turn(SOLO_ACTOR, "pick up the tarnished ring")
    assert [e.type for e in turn.events] == ["item_taken"]
    text = turn.narration.lower()
    assert not any(word in text for word in ("warm", "glow", "hum", "tingl", "inventory"))


def test_stowing_a_carried_item_is_understood_and_changes_nothing(llm):
    session = _session(llm, moves=["north"])
    hero = session.state.party[SOLO_ACTOR]
    party = {SOLO_ACTOR: hero.model_copy(update={"inventory": ("tarnished_ring",)})}
    session.state = session.state.model_copy(update={"party": party})
    turn = session.play_turn(SOLO_ACTOR, "Put the ring in my backpack")
    assert turn.intent is not None and turn.intent.action == "look"
    assert turn.events == [] and "no rule" not in turn.narration


def test_next_door_senses_are_left_out_of_a_turn_that_is_not_about_them(llm):
    session = _session(llm, moves=["north"])
    turn = session.play_turn(SOLO_ACTOR, "pick up the tarnished ring")
    assert "smoke" not in turn.narration.lower()
