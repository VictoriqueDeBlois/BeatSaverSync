from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Artist(BaseModel):
    id: int | None = None
    name: str


class NeteaseSong(BaseModel):
    id: int
    name: str
    artists: list[Artist] = Field(default_factory=list)
    album: str | None = None
    duration_ms: int | None = None

    @property
    def artist_names(self) -> list[str]:
        return [artist.name for artist in self.artists if artist.name]

    @property
    def primary_artist(self) -> str:
        return self.artist_names[0] if self.artist_names else ""


class BeatSaverDifficulty(BaseModel):
    characteristic: str = ""
    difficulty: str = ""
    seconds: float | None = None


class BeatSaverVersion(BaseModel):
    hash: str
    download_url: str
    cover_url: str | None = None
    preview_url: str | None = None
    diffs: list[BeatSaverDifficulty] = Field(default_factory=list)


class BeatSaverMap(BaseModel):
    id: str
    name: str
    song_name: str
    song_author_name: str
    level_author_name: str = ""
    duration: int | None = None
    score: float = 0.0
    upvotes: int = 0
    downvotes: int = 0
    versions: list[BeatSaverVersion] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def latest_version(self) -> BeatSaverVersion | None:
        return self.versions[0] if self.versions else None


class SearchQuery(BaseModel):
    query: str
    reason: str


class MatchResult(BaseModel):
    song: NeteaseSong
    status: Literal["matched", "low_confidence", "not_found", "error"]
    confidence: float = 0.0
    selected: BeatSaverMap | None = None
    selected_version: BeatSaverVersion | None = None
    accepted: list[BeatSaverMap] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    reason: str = ""
    candidates: list[BeatSaverMap] = Field(default_factory=list)
    error: str | None = None
    llm_used: bool = False


class DownloadRecord(BaseModel):
    version_hash: str
    beatsaver_id: str
    song_name: str
    song_author: str
    download_url: str
    file_path: str
    downloaded_at: str
    size_bytes: int


class DownloadIndex(BaseModel):
    records: dict[str, DownloadRecord] = Field(default_factory=dict)


class DownloadResult(BaseModel):
    match: MatchResult
    status: Literal["downloaded", "skipped_existing", "failed", "skipped_no_version"]
    file_path: str | None = None
    size_bytes: int | None = None
    error: str | None = None


class RunReport(BaseModel):
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    total_songs: int = 0
    matched: int = 0
    low_confidence: int = 0
    not_found: int = 0
    errors: int = 0
    downloaded: int = 0
    skipped_existing: int = 0
    download_failed: int = 0
    output_dir: str = ""
    matches: list[MatchResult] = Field(default_factory=list)
    downloads: list[DownloadResult] = Field(default_factory=list)

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
