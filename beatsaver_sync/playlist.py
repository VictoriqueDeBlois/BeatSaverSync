from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fs import read_json
from .models import DownloadIndex, DownloadRecord


def load_download_index(path: Path) -> DownloadIndex:
    return DownloadIndex.model_validate(read_json(path, {"records": {}}))


def build_bplist(
    index: DownloadIndex,
    *,
    title: str,
    author: str,
    description: str = "",
    image: str = "",
    existing_files_only: bool = True,
) -> dict[str, Any]:
    records = sorted(index.records.values(), key=lambda record: (record.song_author.casefold(), record.song_name.casefold()))
    songs = [record_to_bplist_song(record) for record in records if _include_record(record, existing_files_only)]
    return {
        "playlistTitle": title,
        "playlistAuthor": author,
        "playlistDescription": description,
        "image": image,
        "songs": songs,
    }


def write_bplist(playlist: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(playlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def record_to_bplist_song(record: DownloadRecord) -> dict[str, str]:
    return {
        "key": record.beatsaver_id,
        "hash": record.version_hash,
        "songName": record.song_name,
        "songAuthorName": record.song_author,
        "levelAuthorName": "",
    }


def _include_record(record: DownloadRecord, existing_files_only: bool) -> bool:
    return not existing_files_only or Path(record.file_path).exists()
