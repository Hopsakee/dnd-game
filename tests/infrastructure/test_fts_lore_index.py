import pytest

from solo_dm.infrastructure.lore.fts_lore_index import FtsLoreIndex, InvalidLoreFile


def lore_dir(tmp_path, **files):
    for name, text in files.items():
        (tmp_path / f"{name}.md").write_text(text)
    return tmp_path


GOBLINS = "---\ntitle: Goblins\ntags: [goblin]\n---\nThey keep a fire going against the damp.\n"
SHRINE = "---\ntitle: Shrine\ntags: [shrine, water]\n---\nThe dawn shrine filled with water.\n"


def test_lore_is_found_by_tag_and_by_words(tmp_path):
    index = FtsLoreIndex(lore_dir(tmp_path, goblins=GOBLINS, shrine=SHRINE))
    assert [s.topic for s in index.search(tags=["water"])] == ["Shrine"]
    assert [s.topic for s in index.search("why the fire?")] == ["Goblins"]
    assert index.search(tags=["dragon"]) == []


def test_a_query_full_of_punctuation_is_words_not_fts_syntax(tmp_path):
    index = FtsLoreIndex(lore_dir(tmp_path, goblins=GOBLINS))
    assert [s.topic for s in index.search('goblins" AND (fire* OR -NEAR')] == ["Goblins"]
    assert index.search("?!") == []


def test_a_lore_file_without_tags_fails_loudly(tmp_path):
    with pytest.raises(InvalidLoreFile, match="tags"):
        FtsLoreIndex(lore_dir(tmp_path, bad="---\ntitle: Bad\n---\nNo tags.\n"))


def test_a_query_matches_other_forms_of_a_word(tmp_path):
    index = FtsLoreIndex(lore_dir(tmp_path, goblins=GOBLINS, shrine=SHRINE))
    assert [s.topic for s in index.search("burning fires")] == ["Goblins"]
