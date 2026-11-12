import pytest

from solo_dm.composition_root import main


def test_help_lists_the_commands(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    for command in ("play", "cost", "web"):
        assert command in out


def test_commands_not_built_yet_say_which_milestone_brings_them(capsys):
    assert main(["web"]) == 2
    assert "M6" in capsys.readouterr().err


def test_cost_prints_spend_per_day_and_per_campaign(tmp_path, capsys):
    from solo_dm.composition_root import PROJECT_ROOT
    from solo_dm.infrastructure.llm.cost_log import CostLog

    (tmp_path / "settings.yaml").write_text((PROJECT_ROOT / "settings.yaml").read_text())
    log = CostLog(tmp_path / "logs" / "llm_calls.jsonl")
    log.record("interpreter", "claude-haiku-5-5", 10_000, 500, campaign="core_five_rooms@x")
    log.record("narrator", "claude-haiku-5-5", 30_000, 1_500, campaign="core_five_rooms@x")
    assert main(["cost"], root=tmp_path) == 0
    out = capsys.readouterr().out
    assert "Per day" in out and "Per campaign" in out
    assert "core_five_rooms@x" in out and "$0.0050" in out
    assert "2 calls" in out


def test_cost_with_no_calls_yet_says_so(tmp_path, capsys):
    from solo_dm.composition_root import PROJECT_ROOT

    (tmp_path / "settings.yaml").write_text((PROJECT_ROOT / "settings.yaml").read_text())
    assert main(["cost"], root=tmp_path) == 0
    assert "No model calls logged yet" in capsys.readouterr().out
