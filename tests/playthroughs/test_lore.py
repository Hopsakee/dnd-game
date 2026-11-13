"""Lore (M5, plan 3.8): markdown files in lore/ with tags, indexed in SQLite FTS5.
Lore is context for the model only; it never changes what happens."""

import io

from rich.console import Console

from solo_dm.composition_root import build_terminal_game
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from tests.fakes import ScriptedLLM


def game_after(lines, adventure_id="core_five_rooms"):
    game = build_terminal_game(adventure_id, SeededDice(0), FakeLLM(),
                               Console(file=io.StringIO()))
    for line in lines:
        game.handle(line)
    return game


def lore_topics(game):
    return [snippet.topic for snippet in game.session.scene().lore]


def test_lore_for_the_tagged_location_and_creature_is_in_the_scene():
    assert lore_topics(game_after([])) == ["The Sunken Shrine"]
    guard_room = game_after(["go north", "go east"])
    assert lore_topics(guard_room) == ["Goblins of the Hill Country"]
    assert "goblin" in guard_room.session.scene().lore[0].text.lower()


def test_a_place_with_nothing_tagged_gets_no_lore():
    assert lore_topics(game_after(["go north", "go west"])) == []


def test_a_lore_query_from_the_interpreter_reaches_the_narrator_and_changes_nothing():
    llm = ScriptedLLM([{"action": "look", "lore_query": "what do I know of goblin bands?"}])
    game = build_terminal_game("core_five_rooms", SeededDice(0), llm, Console(file=io.StringIO()))
    before = game.session.state

    game.handle("what do I know of goblin bands?")
    outcome, narrator_scene = llm.narrated[0]
    assert [s.topic for s in narrator_scene.lore] == ["The Sunken Shrine",
                                                      "Goblins of the Hill Country"]
    assert outcome.events == [] and game.session.state == before


def test_items_carry_their_description_from_the_adventure_into_the_scene():
    # Play-test flag 12 (2026-11-13): with only a name, the narrator made the ring warm.
    game = game_after(["go north"])
    ring = next(i for i in game.session.scene().items if i.item_id == "tarnished_ring")
    assert "plain" in ring.description
    game.handle("take ring")
    carried = game.session.scene().party[0].inventory[0]
    assert carried.description == ring.description
