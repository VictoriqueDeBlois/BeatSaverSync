from __future__ import annotations

from pathlib import Path

import pytest

from beatsaver_sync.cli import run_pipeline
from beatsaver_sync.models import BeatSaverMap, BeatSaverVersion, DownloadResult, MatchResult, NeteaseSong, RunReport


class FakeMatcher:
    async def match_song(self, song: NeteaseSong) -> MatchResult:
        version = BeatSaverVersion(hash=f"hash-{song.id}", download_url="https://example.test/map.zip")
        selected = BeatSaverMap(
            id=f"map-{song.id}",
            name=song.name,
            song_name=song.name,
            song_author_name="Artist",
            versions=[version],
        )
        return MatchResult(
            song=song,
            status="matched",
            confidence=0.9,
            selected=selected,
            selected_version=version,
        )


class FakeDownloader:
    def __init__(self) -> None:
        self.downloaded: list[int] = []

    async def download(self, match: MatchResult, progress=None) -> DownloadResult:
        self.downloaded.append(match.song.id)
        return DownloadResult(match=match, status="downloaded", file_path=f"{match.song.id}.zip", size_bytes=10)


@pytest.mark.asyncio
async def test_pipeline_downloads_matches_as_they_are_found(tmp_path: Path) -> None:
    songs = [NeteaseSong(id=1, name="One"), NeteaseSong(id=2, name="Two")]
    report = RunReport(total_songs=len(songs), output_dir=str(tmp_path))
    downloader = FakeDownloader()

    await run_pipeline(
        songs=songs,
        matcher=FakeMatcher(),
        downloader=downloader,
        report=report,
        report_dir=tmp_path,
        search_concurrency=1,
        download_concurrency=1,
    )

    assert downloader.downloaded == [1, 2]
    assert report.matched == 2
    assert report.downloaded == 2
    assert (tmp_path / "report.json").exists()
