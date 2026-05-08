from __future__ import annotations

from pathlib import Path

import pytest

from beatsaver_sync.cli import expand_download_matches, run_pipeline
from beatsaver_sync.match_cache import MatchCache
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
        assert match.selected is not None
        self.downloaded.append(match.selected.id)
        return DownloadResult(match=match, status="downloaded", file_path=f"{match.selected.id}.zip", size_bytes=10)


@pytest.mark.asyncio
async def test_pipeline_downloads_matches_as_they_are_found(tmp_path: Path) -> None:
    songs = [NeteaseSong(id=1, name="One"), NeteaseSong(id=2, name="Two")]
    report = RunReport(total_songs=len(songs), output_dir=str(tmp_path))
    downloader = FakeDownloader()

    await run_pipeline(
        songs=songs,
        matcher=FakeMatcher(),
        match_cache=MatchCache(tmp_path / "matches.json", namespace="test"),
        downloader=downloader,
        report=report,
        report_dir=tmp_path,
        search_concurrency=1,
        download_concurrency=1,
    )

    assert downloader.downloaded == ["map-1", "map-2"]
    assert report.matched == 2
    assert report.downloaded == 2
    assert (tmp_path / "report.json").exists()


@pytest.mark.asyncio
async def test_pipeline_uses_cached_match(tmp_path: Path) -> None:
    song = NeteaseSong(id=1, name="Cached")
    cache = MatchCache(tmp_path / "matches.json", namespace="test")
    version = BeatSaverVersion(hash="hash-cached", download_url="https://example.test/map.zip")
    selected = BeatSaverMap(
        id="map-cached",
        name="Cached",
        song_name="Cached",
        song_author_name="Artist",
        versions=[version],
    )
    cache.set(
        MatchResult(
            song=song,
            status="matched",
            confidence=0.9,
            selected=selected,
            selected_version=version,
        )
    )
    report = RunReport(total_songs=1, output_dir=str(tmp_path))
    downloader = FakeDownloader()

    await run_pipeline(
        songs=[song],
        matcher=FakeMatcher(),
        match_cache=cache,
        downloader=downloader,
        report=report,
        report_dir=tmp_path,
        search_concurrency=1,
        download_concurrency=1,
    )

    assert downloader.downloaded == ["map-cached"]
    assert report.matched == 1


@pytest.mark.asyncio
async def test_pipeline_downloads_all_accepted_maps(tmp_path: Path) -> None:
    song = NeteaseSong(id=1, name="Multi")
    version_a = BeatSaverVersion(hash="hash-a", download_url="https://example.test/a.zip")
    version_b = BeatSaverVersion(hash="hash-b", download_url="https://example.test/b.zip")
    map_a = BeatSaverMap(id="map-a", name="Multi A", song_name="Multi", song_author_name="Artist", versions=[version_a])
    map_b = BeatSaverMap(id="map-b", name="Multi B", song_name="Multi", song_author_name="Artist", versions=[version_b])

    class MultiMatcher:
        async def match_song(self, song: NeteaseSong) -> MatchResult:
            return MatchResult(
                song=song,
                status="matched",
                confidence=0.9,
                selected=map_a,
                selected_version=version_a,
                accepted=[map_a, map_b],
            )

    report = RunReport(total_songs=1, output_dir=str(tmp_path))
    downloader = FakeDownloader()

    await run_pipeline(
        songs=[song],
        matcher=MultiMatcher(),
        match_cache=MatchCache(tmp_path / "matches.json", namespace="test"),
        downloader=downloader,
        report=report,
        report_dir=tmp_path,
        search_concurrency=1,
        download_concurrency=1,
    )

    assert downloader.downloaded == ["map-a", "map-b"]
    assert report.matched == 1
    assert report.downloaded == 2


def test_expand_download_matches_preserves_one_task_per_hash() -> None:
    song = NeteaseSong(id=1, name="Multi")
    version = BeatSaverVersion(hash="same-hash", download_url="https://example.test/a.zip")
    map_a = BeatSaverMap(id="map-a", name="Multi A", song_name="Multi", song_author_name="Artist", versions=[version])
    map_b = BeatSaverMap(id="map-b", name="Multi B", song_name="Multi", song_author_name="Artist", versions=[version])
    match = MatchResult(song=song, status="matched", selected=map_a, selected_version=version, accepted=[map_a, map_b])

    expanded = expand_download_matches(match)

    assert len(expanded) == 1
    assert expanded[0].selected == map_a
