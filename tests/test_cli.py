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


def test_an_unknown_adventure_names_the_ones_that_exist(tmp_path, capsys):
    # Play-test flag 1 (2026-11-13): a typo crashed with a FileNotFoundError traceback.
    root = project_with_campaigns_in(tmp_path)
    assert main(["play", "--fake", "--adventure", "scenarios/ability_chec"], root=root) == 2
    err = capsys.readouterr().err
    assert "No adventure 'scenarios/ability_chec'" in err
    assert "core_five_rooms" in err and "scenarios/ability_check" in err


def project_with_campaigns_in(tmp_path):
    """Settings that read the real adventures and SRD but keep campaigns in tmp_path."""
    from solo_dm.composition_root import PROJECT_ROOT

    text = (PROJECT_ROOT / "settings.yaml").read_text()
    for name in ("adventures", "srd", "lore"):
        text = text.replace(f"  {name}: {name}", f"  {name}: {PROJECT_ROOT / name}")
    (tmp_path / "settings.yaml").write_text(text)
    return tmp_path


def typing(monkeypatch, *lines):
    remaining = iter(lines)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(remaining))


def test_play_stores_a_campaign_that_can_be_listed_rewound_and_resumed(
    tmp_path, monkeypatch, capsys
):
    root = project_with_campaigns_in(tmp_path)
    typing(monkeypatch, "go north", "take ring", "quit")
    assert main(["play", "--fake", "--seed", "0"], root=root) == 0
    assert "Campaign 1" in capsys.readouterr().out

    assert main(["campaigns"], root=root) == 0
    listing = capsys.readouterr().out
    assert "1" in listing and "The Amulet of the Sunken Shrine" in listing
    assert "2 turns" in listing and "playing" in listing

    assert main(["rewind", "1", "1"], root=root) == 0
    assert "turn 1" in capsys.readouterr().out

    typing(monkeypatch, "inv", "quit")
    assert main(["play", "--fake", "--campaign", "1"], root=root) == 0
    out = capsys.readouterr().out
    assert "Resuming campaign 1 after turn 1" in out
    assert "Pillared Hall" in out and "pack: empty" in out

    assert main(["turns", "1"], root=root) == 0
    out = capsys.readouterr().out
    assert "go north" in out and "take ring" in out and "superseded" in out


def test_resuming_an_unknown_campaign_says_how_to_list_them(tmp_path, capsys):
    root = project_with_campaigns_in(tmp_path)
    assert main(["play", "--fake", "--campaign", "7"], root=root) == 2
    assert "No campaign 7" in capsys.readouterr().err
