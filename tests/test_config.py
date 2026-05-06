from __future__ import annotations

from pathlib import Path

from beatsaver_sync.config import apply_overrides, load_config


def test_load_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.json")

    assert config.cookie_file == Path(".secrets/netease.cookie")
    assert config.search_with_artists is False
    assert config.search_concurrency == 5
    assert config.search_retries == 3
    assert config.console_logging is False
    assert config.ollama_fallback_model is None
    assert config.limit is None


def test_load_config_from_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        """
        {
          "cookie_file": ".secrets/custom.cookie",
          "output": "custom-output",
          "search_with_artists": true,
          "search_concurrency": 9,
          "search_retries": 4,
          "console_logging": true,
          "ollama_fallback_model": "qwen3.5:35b",
          "limit": 20
        }
        """,
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.cookie_file == Path(".secrets/custom.cookie")
    assert config.output == Path("custom-output")
    assert config.search_with_artists is True
    assert config.search_concurrency == 9
    assert config.search_retries == 4
    assert config.console_logging is True
    assert config.ollama_fallback_model == "qwen3.5:35b"
    assert config.limit == 20


def test_apply_overrides_ignores_none_values() -> None:
    config = apply_overrides(
        load_config(Path("does-not-exist.json")),
        {"search_concurrency": 7, "download_concurrency": None, "console_logging": True, "limit": 3},
    )

    assert config.search_concurrency == 7
    assert config.download_concurrency == 3
    assert config.console_logging is True
    assert config.limit == 3
