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


def test_each_role_has_its_own_budget_and_may_override_the_model():
    llm = load_settings(ROOT).llm
    assert llm.model_for("interpreter") == "claude-haiku-5-5"
    assert llm.interpreter.effort == "low" and llm.narrator.max_tokens >= 1024


def _llm(tmp_path, **changes):
    import yaml

    raw = yaml.safe_load((ROOT / "settings.yaml").read_text())
    raw["llm"].update(changes)
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(raw))
    return load_settings(tmp_path)


def test_in_the_box_calls_go_to_the_broker_with_its_caller_token(tmp_path):
    from solo_dm.infrastructure.settings import anthropic_connection

    caller = tmp_path / "caller"
    caller.write_text("tok-abc\n")
    settings = _llm(tmp_path, broker_auth_file=str(caller))
    conn = anthropic_connection(settings, {"ANTHROPIC_API_BASE": "http://broker:8080/anthropic"})
    assert conn.base_url == "http://broker:8080/anthropic"
    assert conn.headers == {"X-Hoggle-Broker-Auth": "tok-abc"}
    assert conn.api_key  # a placeholder: the broker replaces it with the real key


def test_outside_the_box_calls_go_direct_with_the_key_from_the_env_file(tmp_path):
    from solo_dm.infrastructure.settings import anthropic_connection

    _llm(tmp_path, broker_auth_file=str(tmp_path / "absent"))
    (tmp_path / ".env.solo_dm").write_text("ANTHROPIC_API_KEY=sk-test-123\n")
    conn = anthropic_connection(load_settings(tmp_path), {})
    assert (conn.base_url, conn.api_key.get_secret_value(), conn.headers) == (
        None, "sk-test-123", {})


def test_no_broker_and_no_key_is_a_clear_error(tmp_path):
    import pytest

    from solo_dm.infrastructure.settings import MissingApiKey, anthropic_connection

    settings = _llm(tmp_path, broker_auth_file=str(tmp_path / "absent"))
    with pytest.raises(MissingApiKey, match=".env.solo_dm"):
        anthropic_connection(settings, {})


def test_a_base_url_in_settings_wins_over_the_environment(tmp_path):
    from solo_dm.infrastructure.settings import anthropic_connection

    settings = _llm(tmp_path, base_url="http://elsewhere", broker_auth_file=None)
    conn = anthropic_connection(settings, {"ANTHROPIC_API_BASE": "http://broker"})
    assert conn.base_url == "http://elsewhere"
