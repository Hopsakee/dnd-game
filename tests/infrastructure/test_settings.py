import subprocess
from pathlib import Path

from solo_dm.infrastructure.settings import load_settings

ROOT = Path(__file__).parent.parent.parent


def test_repo_settings_use_haiku_and_hold_no_key():
    settings = load_settings(ROOT)
    assert (settings.llm.provider, settings.llm.model) == ("anthropic", "claude-haiku-5-5")
    assert settings.paths.srd == ROOT / "srd"
    assert settings.api_key is None


def test_api_key_comes_from_the_env_file_and_is_never_printed(tmp_path):
    (tmp_path / "settings.yaml").write_text((ROOT / "settings.yaml").read_text())
    (tmp_path / ".env.solo_dm").write_text("ANTHROPIC_API_KEY=sk-test-123\n")
    settings = load_settings(tmp_path)
    assert settings.api_key.get_secret_value() == "sk-test-123"
    assert "sk-test-123" not in repr(settings)


def test_no_env_file_is_tracked_by_git():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert [f for f in tracked if Path(f).name.startswith(".env")] == []
