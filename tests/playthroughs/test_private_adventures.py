"""M7: books live in the private dnd-adventures repo, next to this one; the
game finds them through settings.yaml's extra_adventures, monsters and all."""

from solo_dm.composition_root import build_session
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from tests.test_cli import project_with_campaigns_in

RUNT = """stat_block_id: goblin_runt
name: Goblin Runt
armor_class: 14
hit_points: 2
initiative_bonus: 4
abilities: {STR: 5, DEX: 18, CON: 8, INT: 7, WIS: 12, CHA: 4}
attacks:
  - {name: Dagger, attack_bonus: 1, damage_dice: 1d4, damage_modifier: -1,
     damage_type: piercing}
"""
BOOK = """id: book
title: A Private Book
start_location: lair
win_condition: {flag: done}
locations:
  - id: lair
    name: Lair
    description: A lair.
    checks: [{ability: CHA, on_success: {set_flag: done}}]
entities:
  - {id: runt, srd_ref: goblin_runt, location: lair, attitude: indifferent}
"""


def test_a_book_from_the_private_folder_starts_with_its_own_monsters(tmp_path):
    (tmp_path / "game").mkdir()
    root = project_with_campaigns_in(tmp_path / "game")
    text = (root / "settings.yaml").read_text()
    assert "extra_adventures: [../dnd-adventures]" in text
    (root / "settings.yaml").write_text(text.replace(
        "[../dnd-adventures]", f"[{tmp_path / 'books'}]"))
    book = tmp_path / "books" / "book"
    (book / "creatures").mkdir(parents=True)
    (book / "adventure.yaml").write_text(BOOK)
    (book / "creatures" / "goblin_runt.yaml").write_text(RUNT)

    session = build_session("book", SeededDice(0), FakeLLM(), root)
    assert session.state.creatures["runt"].name == "Goblin Runt"
    assert session.state.creatures["runt"].hp == 2
