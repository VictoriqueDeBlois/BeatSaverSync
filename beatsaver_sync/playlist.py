from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

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
        "hash": playlist_hash_for_record(record),
        "songName": record.song_name,
        "songAuthorName": record.song_author,
        "levelAuthorName": "",
    }


def playlist_hash_for_record(record: DownloadRecord) -> str:
    file_path = Path(record.file_path)
    if not file_path.exists():
        return record.version_hash
    try:
        return compute_playlist_hash_from_zip(file_path)
    except (BadZipFile, KeyError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return record.version_hash


def compute_playlist_hash_from_zip(path: Path) -> str:
    with ZipFile(path) as archive:
        entries = {name.lower(): name for name in archive.namelist()}
        info_name = _find_entry(entries, "Info.dat", "_Info.dat")
        info_bytes = archive.read(info_name)
        info = json.loads(info_bytes.decode("utf-8-sig"))
        hasher = hashlib.sha1()
        hasher.update(info_bytes)
        for filename in _beatmap_hash_files(info):
            hasher.update(archive.read(_find_entry(entries, filename)))
        return hasher.hexdigest()


def _beatmap_hash_files(info: dict[str, Any]) -> list[str]:
    if isinstance(info.get("difficultyBeatmaps"), list):
        return _v4_beatmap_hash_files(info["difficultyBeatmaps"])
    return _legacy_beatmap_hash_files(info)


def _v4_beatmap_hash_files(difficulties: list[dict[str, Any]]) -> list[str]:
    files: list[str] = []
    for difficulty in difficulties:
        beatmap_filename = difficulty.get("beatmapDataFilename")
        lightshow_filename = difficulty.get("lightshowDataFilename")
        if beatmap_filename:
            files.append(str(beatmap_filename))
        if lightshow_filename:
            files.append(str(lightshow_filename))
    return files


def _legacy_beatmap_hash_files(info: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for beatmap_set in info.get("_difficultyBeatmapSets", []):
        for difficulty in beatmap_set.get("_difficultyBeatmaps", []):
            beatmap_filename = difficulty.get("_beatmapFilename")
            if beatmap_filename:
                files.append(str(beatmap_filename))
    return files


def _find_entry(entries: dict[str, str], *names: str) -> str:
    for name in names:
        entry = entries.get(name.lower())
        if entry:
            return entry
    raise KeyError(names[0])


def _include_record(record: DownloadRecord, existing_files_only: bool) -> bool:
    return not existing_files_only or Path(record.file_path).exists()
