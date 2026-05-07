from __future__ import annotations

import json

import pytest

from beatsaver_sync.netease import batched, extract_track_ids


def test_extract_track_ids_returns_all_playlist_ids() -> None:
    playlist = {"trackIds": [{"id": 1}, {"id": 2}, {"id": 3}]}

    assert extract_track_ids(playlist) == [1, 2, 3]


def test_extract_track_ids_ignores_missing_ids() -> None:
    playlist = {"trackIds": [{"id": 1}, {}, {"id": 3}]}

    assert extract_track_ids(playlist) == [1, 3]


def test_batched_splits_song_ids() -> None:
    assert batched([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


@pytest.mark.asyncio
async def test_get_song_audio_url_parses_player_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from beatsaver_sync.netease import NeteaseClient

    captured: dict = {}
    client = NeteaseClient(cookie="MUSIC_U=test")

    async def fake_get_json_with_params(http_client, url: str, params: dict) -> dict:
        captured["url"] = url
        captured["params"] = params
        return {"data": [{"url": "https://example.test/song.mp3"}]}

    monkeypatch.setattr(client, "_get_json_with_params", fake_get_json_with_params)

    assert await client.get_song_audio_url(123, bitrate=128000) == "https://example.test/song.mp3"
    assert captured["url"].endswith("/api/song/enhance/player/url")
    assert json.loads(captured["params"]["ids"]) == [123]
    assert captured["params"]["br"] == 128000


@pytest.mark.asyncio
async def test_get_song_audio_url_returns_none_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from beatsaver_sync.netease import NeteaseClient

    client = NeteaseClient(cookie="MUSIC_U=test")

    async def fake_get_json_with_params(http_client, url: str, params: dict) -> dict:
        return {"data": [{"url": None, "code": -110}]}

    monkeypatch.setattr(client, "_get_json_with_params", fake_get_json_with_params)

    assert await client.get_song_audio_url(123) is None
