"""Scripted playthroughs (plan 6, level 2): the real wiring and terminal harness,
FakeLLM for interpretation and narration, SeededDice for rolls."""

import io

from rich.console import Console

from solo_dm.composition_root import build_terminal_game
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM

CORE_WIN = (
    ["go north", "go east"] + ["attack goblin"] * 8
    + ["take key", "go west", "unlock north", "go north", "take amulet"]
)
GOBLIN_FIGHT = ["go east"] + ["attack goblin"] * 10 + ["take totem"]


def play(adventure_id, lines, seed=0):
    output = io.StringIO()
    game = build_terminal_game(
        adventure_id, SeededDice(seed), FakeLLM(), Console(file=output, width=100)
    )
    remaining = iter(lines)

    def read_line():
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    outcome = game.run(read_line)
    events = [e.type for turn in game.session.turns for e in turn.events]
    return outcome, events, game, output.getvalue()


def test_core_five_rooms_plays_from_start_to_win():
    outcome, events, game, text = play("core_five_rooms", CORE_WIN, seed=0)
    assert outcome == "won"
    assert "creature_died" in events and "door_unlocked" in events
    assert game.session.state.party["hero"].inventory == ("iron_key", "sunken_amulet")
    assert "You have won the adventure!" in text


def test_core_five_rooms_can_be_lost():
    outcome, events, game, text = play("core_five_rooms", CORE_WIN, seed=4)
    assert outcome == "lost"
    assert events[-2:] == ["combat_ended", "adventure_lost"]
    assert game.session.state.party["hero"].defeated is True


def test_scenario_goblin_fight_won_and_lost():
    assert play("scenarios/goblin_fight", GOBLIN_FIGHT, seed=0)[0] == "won"
    assert play("scenarios/goblin_fight", GOBLIN_FIGHT, seed=4)[0] == "lost"


def test_scenario_locked_door_with_the_key():
    lines = ["go north", "take key", "unlock north", "go north", "take token"]
    outcome, events, _, text = play("scenarios/locked_door", lines)
    assert outcome == "won"
    assert "The way north is locked." in text  # the first 'go north' was blocked


def test_scenario_locked_door_by_picking_the_lock():
    lines = ["unlock north"] * 8 + ["go north", "take token"]
    outcome, events, game, _ = play("scenarios/locked_door", lines, seed=0)
    assert outcome == "won"
    unlocked = [e for t in game.session.turns for e in t.events if e.type == "door_unlocked"]
    assert unlocked[0].method == "picked"


def test_builtin_commands_answer_without_a_model_turn():
    lines = ["go north", "help", "inv", "hp", "look", "map", "flag too vague", "save"]
    _, _, game, text = play("core_five_rooms", lines)
    assert len(game.session.turns) == 1  # only 'go north' went through the pipeline
    assert game.session.turns[0].flag_note == "too vague"
    assert "Fighter: nothing" in text and "Fighter: 12/12 HP" in text
    assert "* Pillared Hall: south -> Mossy Entrance" in text
    assert "east (unexplored)" in text and "north (unexplored, locked)" in text
    assert "Saving arrives with campaigns in M4." in text



def test_entering_a_room_shows_it_without_look():
    _, _, _, text = play("core_five_rooms", ["go north"])
    after_move = text.split("You enter the Pillared Hall.", 1)[1]
    assert "Four cracked pillars hold up a low ceiling." in after_move
    assert "Exits:" in after_move


def test_a_turn_without_moving_does_not_repeat_the_room():
    _, _, _, text = play("core_five_rooms", ["attack nothing"])
    assert text.count("Damp stone stairs lead down") == 1
