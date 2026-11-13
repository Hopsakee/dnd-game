"""Scripted playthroughs (plan 6, level 2): the real wiring and terminal harness,
FakeLLM for interpretation and narration, SeededDice for rolls."""

import io

from rich.console import Console

from solo_dm.composition_root import build_terminal_game
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM

CORE_WIN = (
    ["go north", "go east"] + ["attack goblin"] * 8
    + ["search goblin", "take key", "go west", "unlock north", "go north", "take amulet"]
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
    assert "pack: empty" in text and "Fighter: 12/12 HP" in text
    assert "* Pillared Hall: south -> Mossy Entrance" in text
    assert "east (unexplored)" in text and "north (unexplored, locked)" in text
    assert "Saving arrives with campaigns in M4." in text


def test_pick_up_takes_the_key_instead_of_picking_a_lock():
    _, events, game, _ = play("scenarios/locked_door", ["pick up key"])
    assert "item_taken" in events
    assert "door_unlocked" not in events


def test_use_key_unlocks_the_locked_door():
    lines = ["take key", "use key", "go north", "take token"]
    outcome, events, _, _ = play("scenarios/locked_door", lines)
    assert "door_unlocked" in events
    assert outcome == "won"


def test_core_five_rooms_hidden_things():
    lines = ["go north", "take ring", "go west"] + ["search"] * 6 + ["take chalice", "inv"]
    _, events, game, text = play("core_five_rooms", lines, seed=0)
    assert "You notice the Tarnished Ring." in text  # passive Perception on entering the hall
    found = [e.method for turn in game.session.turns for e in turn.events
             if e.type == "hidden_found"]
    assert found == ["passive", "search"]
    assert game.session.state.party["hero"].inventory == ("tarnished_ring", "silver_chalice")


def test_the_key_must_be_taken_from_the_goblins_body():
    lines = ["go north", "go east"] + ["attack goblin"] * 8 + ["take key"]
    _, _, game, _ = play("core_five_rooms", lines, seed=0)
    assert "iron_key" not in game.session.state.party["hero"].inventory


def test_scenario_ability_check_fallback_wins_by_persuasion():
    lines = ["climb the cliff", "persuade the gatekeeper", "persuade the gatekeeper"]
    outcome, events, game, text = play("scenarios/ability_check", lines, seed=6)
    assert outcome == "won"
    assert all(turn.fallback for turn in game.session.turns)
    assert {"cliff_climbed", "passage_granted"} <= set(game.session.state.quest_flags)
    assert "You have won the adventure!" in text


def test_scenario_ability_check_fallback_can_fail_and_change_nothing():
    lines = ["persuade the gatekeeper"] * 3
    outcome, events, game, _ = play("scenarios/ability_check", lines, seed=0)
    assert outcome == "playing"
    assert set(events) == {"check_rolled"} and game.session.state.quest_flags == ()
