from __future__ import annotations

from pathlib import Path

from beatsaver_sync.match_cache import MatchCache, build_match_cache_namespace
from beatsaver_sync.models import Artist, MatchResult, NeteaseSong


def test_match_cache_round_trips_result(tmp_path: Path) -> None:
    cache = MatchCache(tmp_path / "matches.json", namespace="v1")
    song = NeteaseSong(id=1, name="Song", artists=[Artist(name="Artist")])
    result = MatchResult(song=song, status="not_found", reason="No result")

    cache.set(result)
    loaded = MatchCache(tmp_path / "matches.json", namespace="v1")

    cached = loaded.get(song)
    assert cached is not None
    assert cached.status == "not_found"
    assert cached.reason == "No result"


def test_match_cache_key_keeps_covers_separate(tmp_path: Path) -> None:
    cache = MatchCache(tmp_path / "matches.json", namespace="v1")
    original = NeteaseSong(id=1, name="Song", artists=[Artist(name="Artist A")])
    cover = NeteaseSong(id=2, name="Song", artists=[Artist(name="Artist B")])

    assert cache.key_for(original) != cache.key_for(cover)


def test_match_cache_namespace_changes_with_matching_config() -> None:
    one = build_match_cache_namespace(
        min_confidence=0.72,
        search_with_artists=False,
        require_artist_match=True,
        min_artist_confidence=0.45,
        ollama_model="qwen3.6:27b",
        ollama_fallback_model=None,
    )
    two = build_match_cache_namespace(
        min_confidence=0.8,
        search_with_artists=False,
        require_artist_match=True,
        min_artist_confidence=0.45,
        ollama_model="qwen3.6:27b",
        ollama_fallback_model=None,
    )

    assert one != two
