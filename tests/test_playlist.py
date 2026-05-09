from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from beatsaver_sync.models import DownloadIndex, DownloadRecord
from beatsaver_sync.playlist import build_bplist, record_to_bplist_song, write_bplist


def make_record(tmp_path: Path, version_hash: str = "hash-a") -> DownloadRecord:
    file_path = tmp_path / f"{version_hash}.zip"
    file_path.write_bytes(b"zip")
    return DownloadRecord(
        version_hash=version_hash,
        beatsaver_id="abc12",
        song_name="Song",
        song_author="Artist",
        download_url="https://example.test/map.zip",
        file_path=str(file_path),
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        size_bytes=3,
    )


def test_record_to_bplist_song_uses_beatsaver_key_and_hash(tmp_path: Path) -> None:
    record = make_record(tmp_path)

    assert record_to_bplist_song(record) == {
        "key": "abc12",
        "hash": "hash-a",
        "songName": "Song",
        "songAuthorName": "Artist",
        "levelAuthorName": "",
    }


def test_build_bplist_skips_missing_files_by_default(tmp_path: Path) -> None:
    existing = make_record(tmp_path, "hash-a")
    missing = make_record(tmp_path, "hash-b")
    Path(missing.file_path).unlink()
    index = DownloadIndex(records={"hash-a": existing, "hash-b": missing})

    playlist = build_bplist(index, title="Title", author="Author")

    assert playlist["playlistTitle"] == "Title"
    assert playlist["playlistAuthor"] == "Author"
    assert [song["hash"] for song in playlist["songs"]] == ["hash-a"]


def test_write_bplist_writes_json_file(tmp_path: Path) -> None:
    path = tmp_path / "playlist.bplist"
    playlist = {"playlistTitle": "Title", "playlistAuthor": "Author", "songs": []}

    write_bplist(playlist, path)

    assert json.loads(path.read_text(encoding="utf-8"))["playlistTitle"] == "Title"
