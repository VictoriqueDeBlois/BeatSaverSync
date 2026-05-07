from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from .models import NeteaseSong
from .netease import NeteaseClient


class SourceSong(BaseModel):
    source: str
    source_id: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str | None = None
    duration_ms: int | None = None
    audio_path: Path | None = None
    audio_url: str | None = None


class AudioReference(BaseModel):
    kind: Literal["url", "file", "bytes"]
    value: str | bytes
    source: str
    offset_seconds: float | None = None
    duration_seconds: float | None = None


class AudioSource(Protocol):
    async def get_audio_reference(self, song: SourceSong) -> AudioReference | None:
        ...


class NeteaseAudioSource:
    def __init__(self, client: NeteaseClient, bitrate: int = 320000) -> None:
        self.client = client
        self.bitrate = bitrate

    async def get_audio_reference(self, song: SourceSong) -> AudioReference | None:
        if song.source != "netease":
            return None
        url = await self.client.get_song_audio_url(int(song.source_id), bitrate=self.bitrate)
        if not url:
            return None
        return AudioReference(kind="url", value=url, source="netease", duration_seconds=_duration_seconds(song))


class LocalFileAudioSource:
    async def get_audio_reference(self, song: SourceSong) -> AudioReference | None:
        if not song.audio_path:
            return None
        return AudioReference(
            kind="file",
            value=str(song.audio_path),
            source=song.source,
            duration_seconds=_duration_seconds(song),
        )


def netease_song_to_source_song(song: NeteaseSong) -> SourceSong:
    return SourceSong(
        source="netease",
        source_id=str(song.id),
        title=song.name,
        artists=song.artist_names,
        album=song.album,
        duration_ms=song.duration_ms,
    )


def _duration_seconds(song: SourceSong) -> float | None:
    if song.duration_ms is None:
        return None
    return song.duration_ms / 1000
