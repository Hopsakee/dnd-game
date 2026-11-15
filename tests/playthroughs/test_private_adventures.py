"""M7: books live in the private dnd-adventures repo, next to this one; the
game finds them through settings.yaml's extra_adventures, monsters and all."""

import pytest

from solo_dm.composition_root import PROJECT_ROOT, build_session
from solo_dm.core.state.apply import apply_events
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.resolve import resolve_intent
from solo_dm.infrastructure.adventures.yaml_adventure_source import YamlAdventureSource
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from tests.fakes import FixedDice
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
    checks: [{id: charm, goal: charm the runt, ability: CHA, on_success: {set_flag: done}}]
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


# The gold Revenge of Azzinax in dnd-adventures, next to this repo (after M7):
# the post-M7 wishes, checked on the real book. Skipped where it is not cloned.
GOLD = PROJECT_ROOT.parent / "dnd-adventures"
needs_gold = pytest.mark.skipif(not (GOLD / "revenge_of_azzinax").is_dir(),
                                reason="dnd-adventures is not cloned next to this repo")


def gold_at(location, faces=()):
    session = build_session("revenge_of_azzinax", SeededDice(0), FakeLLM())
    state = session.state.model_copy(update={"party_location": location})
    return session.adventure, state


def do(adventure, state, faces=(), **intent):
    resolution = resolve_intent(state, adventure, "hero", Intent(**intent), FixedDice(list(faces)))
    assert resolution.blocked is None, resolution.blocked
    return resolution, apply_events(state, resolution.events)


@needs_gold
def test_gold_azzinax_one_silver_in_the_fountain_opens_its_doors_and_leaves_seven():
    adventure, state = gold_at("village")
    _, state = do(adventure, state, action="take", target_id="silver_pieces")
    assert str(state.party["hero"].coins) == "18 gp, 8 sp"
    state = state.model_copy(update={"party_location": "room3"})
    resolution, state = do(adventure, state, action="use_item", item_id="coins")
    assert str(state.party["hero"].coins) == "18 gp, 7 sp"
    assert not {"3b", "3c", "3d"} & set(state.locked_exits)


@needs_gold
def test_gold_azzinax_the_cursed_warhammer_can_be_wielded_and_bites():
    adventure, state = gold_at("room5")
    _, state = do(adventure, state, action="take", target_id="cursed_warhammer")
    _, state = do(adventure, state, action="wield", item_id="cursed_warhammer")
    weapon = state.party["hero"].weapon_in_hand()
    assert (weapon.damage_dice, weapon.damage_penalty) == ("1d8", "1d4")


@needs_gold
def test_gold_azzinax_doors_match_the_map_and_every_place_has_its_cells():
    source = YamlAdventureSource(GOLD)
    adventure = source.load("revenge_of_azzinax")
    found = source.player_map("revenge_of_azzinax")
    assert found is not None and found.size == (1751, 2251)
    kinds = {o.id: o.kind for place in (*found.map.locations.values(),
                                        *found.map.off_map.values()) for o in place.openings}
    exits = {e.id: e.door for loc in adventure.locations for e in loc.exits}
    assert exits == {i: kinds[i] == "door" for i in exits}
    on_map = {loc.id for loc in adventure.locations} - set(found.map.off_map)
    assert on_map == set(found.map.locations)
    assert all(found.map.locations[i].cells for i in on_map)
