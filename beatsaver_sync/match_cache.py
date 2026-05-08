from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .fs import read_json, write_json
from .models import MatchResult, NeteaseSong


class MatchCacheEntry(BaseModel):
    key: str
    song_id: int
    song_name: str
    artists: list[str] = Field(default_factory=list)
    result: MatchResult
    cached_at: str


class MatchCache:
    def __init__(self, path: Path, namespace: str) -> None:
        self.path = path
        self.namespace = namespace
        raw = read_json(path, {"entries": {}})
        self.entries: dict[str, MatchCacheEntry] = {
            key: MatchCacheEntry.model_validate(value) for key, value in raw.get("entries", {}).items()
        }

    def get(self, song: NeteaseSong) -> MatchResult | None:
        entry = self.entries.get(self.key_for(song))
        if not entry:
            return None
        return entry.result

    def set(self, result: MatchResult) -> None:
        key = self.key_for(result.song)
        self.entries[key] = MatchCacheEntry(
            key=key,
            song_id=result.song.id,
            song_name=result.song.name,
            artists=result.song.artist_names,
            result=result,
            cached_at=datetime.now(timezone.utc).isoformat(),
        )
        self.save()

    def save(self) -> None:
        write_json(self.path, {"entries": {key: entry.model_dump(mode="json") for key, entry in self.entries.items()}})

    def key_for(self, song: NeteaseSong) -> str:
        payload: dict[str, Any] = {
            "namespace": self.namespace,
            "song_id": song.id,
            "song_name": song.name,
            "artists": song.artist_names,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_match_cache_namespace(
    *,
    min_confidence: float,
    search_with_artists: bool,
    expand_search_with_llm: bool,
    download_all_matching_maps: bool,
    artist_match_mode: str,
    ollama_model: str,
    ollama_fallback_model: str | None,
) -> str:
    payload = {
        "version": 5,
        "min_confidence": min_confidence,
        "search_with_artists": search_with_artists,
        "expand_search_with_llm": expand_search_with_llm,
        "download_all_matching_maps": download_all_matching_maps,
        "artist_match_mode": artist_match_mode,
        "ollama_model": ollama_model,
        "ollama_fallback_model": ollama_fallback_model,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
