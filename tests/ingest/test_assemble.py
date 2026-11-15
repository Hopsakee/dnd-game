"""assemble: the stage files into one adventure.yaml, validated by the engine's
schema (BUILD_PLAN M8). Exits come from map.yaml: an exit is an opening."""

from adventure_ingest.assemble import assemble

from .conftest import GOLD, load_adventure


def test_the_gold_stages_assemble_into_the_gold_adventure(stages):
    assert assemble(stages.path) == []
    assert load_adventure(stages.path / "adventure.yaml") == load_adventure(
        GOLD / "adventure.yaml")


def test_a_broken_reference_is_reported_not_written(stages):
    stages.edit("items.yaml", lambda s: s["locks"][0].update(key="brass_key"))
    assert assemble(stages.path) == ["adventure.yaml: lock key 'brass_key' is not an item"]
    assert not (stages.path / "adventure.yaml").exists()
