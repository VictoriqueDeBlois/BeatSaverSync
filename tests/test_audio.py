from __future__ import annotations

from pathlib import Path

import pytest

from beatsaver_sync.audio import LocalFileAudioSource, NeteaseAudioSource, SourceSong, netease_song_to_source_song
from beatsaver_sync.models import Artist, NeteaseSong
from beatsaver_sync.netease import NeteaseClient


def test_netease_song_to_source_song_preserves_metadata() -> None:
    song = NeteaseSong(
        id=123,
        name="Song",
        artists=[Artist(name="Artist A"), Artist(name="Artist B")],
        album="Album",
        duration_ms=90000,
    )

    source_song = netease_song_to_source_song(song)

    assert source_song.source == "netease"
    assert source_song.source_id == "123"
    assert source_song.title == "Song"
    assert source_song.artists == ["Artist A", "Artist B"]
    assert source_song.duration_ms == 90000


@pytest.mark.asyncio
async def test_local_file_audio_source_returns_file_reference() -> None:
    source = LocalFileAudioSource()
    song = SourceSong(source="foobar2000", source_id="1", title="Song", audio_path=Path("C:/Music/song.flac"))

    reference = await source.get_audio_reference(song)

    assert reference is not None
    assert reference.kind == "file"
    assert reference.value == "C:\\Music\\song.flac"
    assert reference.source == "foobar2000"


@pytest.mark.asyncio
async def test_netease_audio_source_uses_client_audio_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = NeteaseClient(cookie="MUSIC_U=test")
    calls: list[tuple[int, int]] = []

    async def fake_get_song_audio_url(song_id: int, bitrate: int = 320000) -> str:
        calls.append((song_id, bitrate))
        return "https://example.test/audio.mp3"

    monkeypatch.setattr(client, "get_song_audio_url", fake_get_song_audio_url)
    source = NeteaseAudioSource(client, bitrate=128000)

    reference = await source.get_audio_reference(SourceSong(source="netease", source_id="123", title="Song"))

    assert reference is not None
    assert reference.kind == "url"
    assert reference.value == "https://example.test/audio.mp3"
    assert calls == [(123, 128000)]


@pytest.mark.asyncio
async def test_netease_audio_source_ignores_other_sources() -> None:
    source = NeteaseAudioSource(NeteaseClient(cookie="MUSIC_U=test"))

    assert await source.get_audio_reference(SourceSong(source="foobar2000", source_id="123", title="Song")) is None
