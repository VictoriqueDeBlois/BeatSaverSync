from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .fs import read_json


class SyncConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    netease_liked: bool = True
    cookie_file: Path = Path(".secrets/netease.cookie")
    output: Path = Path("output")
    search_concurrency: int = Field(default=5, ge=1)
    download_concurrency: int = Field(default=3, ge=1)
    ollama_concurrency: int = Field(default=1, ge=1)
    ollama_model: str = "qwen3.6:27b"
    ollama_fallback_model: str = "qwen3.5:35b"
    min_confidence: float = Field(default=0.72, ge=0.0, le=1.0)
    force_refresh_search: bool = False
    redownload: bool = False
    limit: int | None = Field(default=None, ge=1)

    @field_validator("cookie_file", "output", mode="before")
    @classmethod
    def expand_path(cls, value: Any) -> Path:
        return Path(value).expanduser()


def load_config(path: Path) -> SyncConfig:
    if not path.exists():
        return SyncConfig()
    data = read_json(path, {})
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    return SyncConfig.model_validate(data)


def apply_overrides(config: SyncConfig, overrides: dict[str, Any]) -> SyncConfig:
    data = config.model_dump()
    data.update({key: value for key, value in overrides.items() if value is not None})
    return SyncConfig.model_validate(data)
