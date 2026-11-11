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
