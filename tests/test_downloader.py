from __future__ import annotations

from pathlib import Path

import pytest

from beatsaver_sync.downloader import DownloadManager
from beatsaver_sync.models import BeatSaverMap, BeatSaverVersion, MatchResult, NeteaseSong


def make_match(version_hash: str = "abc123") -> MatchResult:
    version = BeatSaverVersion(hash=version_hash, download_url="https://example.test/map.zip")
    selected = BeatSaverMap(
        id="map1",
        name="Song - Artist",
        song_name="Song",
        song_author_name="Artist",
        versions=[version],
    )
    return MatchResult(
        song=NeteaseSong(id=1, name="Song"),
        status="matched",
        confidence=0.9,
        selected=selected,
        selected_version=version,
    )


@pytest.mark.asyncio
async def test_download_writes_index_and_skips_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DownloadManager(tmp_path / "downloads", tmp_path / "downloads" / "index.json")
    match = make_match()

    async def fake_stream(url, target, progress_key, progress):
        target.write_bytes(b"zip-data")
        return 8

    monkeypatch.setattr(manager, "_stream_download", fake_stream)
    first = await manager.download(match)
    second = await manager.download(match)

    assert first.status == "downloaded"
    assert second.status == "skipped_existing"
    assert manager.index.records["abc123"].size_bytes == 8
    assert Path(manager.index.records["abc123"].file_path).exists()


@pytest.mark.asyncio
async def test_download_cleans_part_file_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DownloadManager(tmp_path / "downloads", tmp_path / "downloads" / "index.json", retries=1)
    match = make_match("failed")

    async def failing_stream(url, target, progress_key, progress):
        target.write_bytes(b"partial")
        raise RuntimeError("network broke")

    monkeypatch.setattr(manager, "_stream_download", failing_stream)
    result = await manager.download(match)

    assert result.status == "failed"
    assert not list((tmp_path / "downloads").glob("*.part"))


def test_index_prunes_missing_files(tmp_path: Path) -> None:
    index_path = tmp_path / "downloads" / "index.json"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        """
        {
          "records": {
            "gone": {
              "version_hash": "gone",
              "beatsaver_id": "map",
              "song_name": "Song",
              "song_author": "Artist",
              "download_url": "https://example.test/map.zip",
              "file_path": "C:/definitely/missing/file.zip",
              "downloaded_at": "2026-01-01T00:00:00+00:00",
              "size_bytes": 10
            }
          }
        }
        """,
        encoding="utf-8",
    )

    manager = DownloadManager(tmp_path / "downloads", index_path)

    assert manager.index.records == {}
