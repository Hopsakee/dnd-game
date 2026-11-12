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
