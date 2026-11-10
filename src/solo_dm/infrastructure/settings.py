"""Loads settings.yaml and the optional API key from .env.solo_dm."""

from pathlib import Path

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

ENV_FILE = ".env.solo_dm"


class LlmSettings(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    max_tokens: int
    temperature: float


class PathSettings(BaseModel):
    adventures: Path
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


def load_settings(root: Path) -> Settings:
    raw = yaml.safe_load((root / "settings.yaml").read_text())
    raw["paths"] = {name: root / value for name, value in raw["paths"].items()}
    key = dotenv_values(root / ENV_FILE).get("ANTHROPIC_API_KEY")
    return Settings(**raw, api_key=key or None)
