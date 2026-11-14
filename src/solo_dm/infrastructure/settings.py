"""Loads settings.yaml and the optional API key from .env.solo_dm, and works out
where model calls go (plan 3.9): the credential broker in the box, the Anthropic
API with a key elsewhere. One adapter, two settings; no code path differs."""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

ENV_FILE = ".env.solo_dm"
BROKER_AUTH_HEADER = "X-Hoggle-Broker-Auth"
# The broker swaps in the real key; the SDK only needs a non-empty one.
KEY_PLACEHOLDER_FOR_BROKER = "added-by-the-broker"

Role = Literal["interpreter", "narrator"]


class MissingApiKey(RuntimeError):
    pass


class RoleSettings(BaseModel):
    model: str | None = None  # None: llm.model
    max_tokens: int
    effort: Literal["low", "medium", "high"]


class LlmSettings(BaseModel):
    provider: Literal["anthropic", "fake"]
    model: str
    base_url: str | None = None
    base_url_env: str = "ANTHROPIC_API_BASE"
    broker_auth_file: Path | None = None
    interpreter: RoleSettings
    narrator: RoleSettings

    def role(self, role: Role) -> RoleSettings:
        return getattr(self, role)

    def model_for(self, role: Role) -> str:
        return self.role(role).model or self.model


class PathSettings(BaseModel):
    adventures: Path
    # More adventure folders, searched after `adventures` (M7: the private
    # dnd-adventures repo cloned next to this one). Missing folders are skipped.
    extra_adventures: list[Path] = []
    srd: Path
    lore: Path
    campaigns: Path
    llm_call_log: Path


class CostSettings(BaseModel):
    daily_cap_usd: float | None = None


class Settings(BaseModel):
    llm: LlmSettings
    paths: PathSettings
    cost: CostSettings
    api_key: SecretStr | None = None


class AnthropicConnection(BaseModel):
    base_url: str | None
    api_key: SecretStr
    headers: dict[str, str]


def load_settings(root: Path) -> Settings:
    raw = yaml.safe_load((root / "settings.yaml").read_text())
    raw["paths"] = {name: [root / v for v in value] if isinstance(value, list) else root / value
                    for name, value in raw["paths"].items()}
    key = dotenv_values(root / ENV_FILE).get("ANTHROPIC_API_KEY")
    return Settings(**raw, api_key=key or None)


def anthropic_connection(settings: Settings, environ: Mapping[str, str]) -> AnthropicConnection:
    llm = settings.llm
    base_url = llm.base_url or environ.get(llm.base_url_env) or None
    headers = {}
    if llm.broker_auth_file is not None and llm.broker_auth_file.exists():
        headers[BROKER_AUTH_HEADER] = llm.broker_auth_file.read_text().strip()
    if settings.api_key is not None:
        key = settings.api_key.get_secret_value()
    elif base_url is not None:
        key = KEY_PLACEHOLDER_FOR_BROKER
    else:
        raise MissingApiKey(
            f"No API key: put ANTHROPIC_API_KEY in {ENV_FILE}, or set "
            f"{llm.base_url_env} to a credential broker."
        )
    return AnthropicConnection(base_url=base_url, api_key=key, headers=headers)
