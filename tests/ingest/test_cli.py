"""The adventure-ingest command the converter agent calls through the shell."""

import pytest

from adventure_ingest.cli import main

from .conftest import GOLD, TEST_BOOK


def test_verify_passes_the_gold_and_says_so(capsys):
    assert main(["verify", str(GOLD)]) == 0
    assert "verify: passed" in capsys.readouterr().out


def test_verify_lists_the_problems_and_fails(gold, capsys):
    gold.edit("adventure.yaml", lambda a: a["entities"][0].update(srd_ref="giant_rat"))
    assert main(["verify", str(gold.path)]) == 1
    assert "- 'goblin_1' has no stat block 'giant_rat'" in capsys.readouterr().out


def test_an_unknown_command_is_refused():
    with pytest.raises(SystemExit):
        main(["dance"])


def test_eval_writes_its_report_next_to_the_conversion(gold, capsys):
    gold.edit("adventure.yaml", lambda a: a["entities"][0].update(location="room1"))
    assert main(["eval", str(gold.path), str(GOLD)]) == 0
    report = (gold.path / "eval.md").read_text()
    assert "| monsters | 0.67 | 0.67 | 1 | 1 |" in report
    assert "- extra: goblin_warrior in room1" in report
    assert "monsters" in capsys.readouterr().out


def test_assemble_then_verify_the_gold_stages(stages, capsys):
    assert main(["assemble", str(stages.path)]) == 0
    assert main(["verify", str(stages.path)]) == 0


def test_check_one_stage(stages, capsys):
    assert main(["check", "map", str(stages.path)]) == 0
    assert "check map: passed" in capsys.readouterr().out


def test_schema_prints_a_stage_files_json_schema(capsys):
    assert main(["schema", "challenges"]) == 0
    assert '"ChallengesStage"' in capsys.readouterr().out


def test_extract_reports_the_picture_pages(tmp_path, capsys):
    assert main(["extract", str(TEST_BOOK / "book" / "book.pdf"), str(tmp_path)]) == 0
    assert "page 6: 1 word, 1 picture" in capsys.readouterr().out
