from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from .fs import read_json, safe_filename, write_json
from .models import DownloadIndex, DownloadRecord, DownloadResult, MatchResult

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[str, int, int | None], None]


class DownloadManager:
    def __init__(
        self,
        downloads_dir: Path,
        index_path: Path,
        redownload: bool = False,
        retries: int = 3,
        timeout: float = 60.0,
    ) -> None:
        self.downloads_dir = downloads_dir
        self.index_path = index_path
        self.redownload = redownload
        self.retries = retries
        self.timeout = timeout
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.index = DownloadIndex.model_validate(read_json(index_path, {"records": {}}))
        self._prune_missing_files()

    def _prune_missing_files(self) -> None:
        missing = [
            version_hash
            for version_hash, record in self.index.records.items()
            if not Path(record.file_path).exists()
        ]
        for version_hash in missing:
            self.index.records.pop(version_hash, None)
        if missing:
            self.save_index()

    def save_index(self) -> None:
        write_json(self.index_path, self.index.model_dump(mode="json"))

    def is_downloaded(self, version_hash: str) -> bool:
        if self.redownload:
            return False
        record = self.index.records.get(version_hash)
        return bool(record and Path(record.file_path).exists())

    def target_path(self, match: MatchResult) -> Path:
        assert match.selected and match.selected_version
        name = safe_filename(f"{match.selected.song_author_name} - {match.selected.song_name} [{match.selected.id}]")
        return self.downloads_dir / f"{name}.zip"

    async def download(self, match: MatchResult, progress: ProgressCallback | None = None) -> DownloadResult:
        version = match.selected_version
        selected = match.selected
        if not version or not selected:
            return DownloadResult(match=match, status="skipped_no_version", error="No BeatSaver version selected.")
        if self.is_downloaded(version.hash):
            return DownloadResult(
                match=match,
                status="skipped_existing",
                file_path=self.index.records[version.hash].file_path,
                size_bytes=self.index.records[version.hash].size_bytes,
            )
        target = self.target_path(match)
        part = target.with_suffix(target.suffix + ".part")
        last_error: str | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if part.exists():
                    part.unlink()
                size = await self._stream_download(version.download_url, part, version.hash, progress)
                os.replace(part, target)
                record = DownloadRecord(
                    version_hash=version.hash,
                    beatsaver_id=selected.id,
                    song_name=selected.song_name,
                    song_author=selected.song_author_name,
                    download_url=version.download_url,
                    file_path=str(target),
                    downloaded_at=datetime.now(timezone.utc).isoformat(),
                    size_bytes=size,
                )
                self.index.records[version.hash] = record
                self.save_index()
                return DownloadResult(match=match, status="downloaded", file_path=str(target), size_bytes=size)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                LOGGER.warning("Download attempt %s/%s failed for %s: %s", attempt, self.retries, version.hash, exc)
                if part.exists():
                    part.unlink()
                if attempt < self.retries:
                    await asyncio.sleep(1.5 * attempt)
        return DownloadResult(match=match, status="failed", file_path=str(target), error=last_error)

    async def _stream_download(
        self,
        url: str,
        target: Path,
        progress_key: str,
        progress: ProgressCallback | None,
    ) -> int:
        bytes_written = 0
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", "0")) or None
                with target.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            continue
                        handle.write(chunk)
                        bytes_written += len(chunk)
                        if progress:
                            progress(progress_key, bytes_written, total)
        return bytes_written
