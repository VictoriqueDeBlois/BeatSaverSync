from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from urllib.parse import quote

import httpx

from .fs import read_json, write_json
from .models import BeatSaverDifficulty, BeatSaverMap, BeatSaverVersion

LOGGER = logging.getLogger(__name__)


class BeatSaverClient:
    def __init__(self, cache_path: Path, timeout: float = 30.0, force_refresh: bool = False, retries: int = 3) -> None:
        self.cache_path = cache_path
        self.timeout = timeout
        self.force_refresh = force_refresh
        self.retries = retries
        self.cache: dict[str, list[dict]] = read_json(cache_path, {})
        self.headers = {"User-Agent": "beatsaver-sync/0.1 (+https://beatsaver.com)"}

    async def search(self, query: str, page: int = 0) -> list[BeatSaverMap]:
        key = f"{page}:{query}"
        if not self.force_refresh and key in self.cache:
            return [parse_map(item) for item in self.cache[key]]
        url = f"https://beatsaver.com/api/search/text/{page}?q={quote(query)}"
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                LOGGER.warning("BeatSaver search attempt %s/%s failed for %r: %s", attempt, self.retries, query, exc)
                if attempt < self.retries:
                    await asyncio.sleep(1.5 * attempt)
        else:
            assert last_error is not None
            raise last_error
        docs = data.get("docs") or []
        self.cache[key] = docs
        write_json(self.cache_path, self.cache)
        return [parse_map(item) for item in docs]


def parse_map(raw: dict) -> BeatSaverMap:
    metadata = raw.get("metadata") or {}
    stats = raw.get("stats") or {}
    versions = [
        BeatSaverVersion(
            hash=version.get("hash", ""),
            download_url=version.get("downloadURL", ""),
            cover_url=version.get("coverURL"),
            preview_url=version.get("previewURL"),
            diffs=[
                BeatSaverDifficulty(
                    characteristic=diff.get("characteristic", ""),
                    difficulty=diff.get("difficulty", ""),
                    seconds=diff.get("seconds"),
                )
                for diff in version.get("diffs", [])
            ],
        )
        for version in raw.get("versions", [])
        if version.get("hash") and version.get("downloadURL")
    ]
    return BeatSaverMap(
        id=str(raw.get("id", "")),
        name=raw.get("name", ""),
        song_name=metadata.get("songName", ""),
        song_author_name=metadata.get("songAuthorName", ""),
        level_author_name=metadata.get("levelAuthorName", ""),
        duration=metadata.get("duration"),
        score=float(stats.get("score") or 0.0),
        upvotes=int(stats.get("upvotes") or 0),
        downvotes=int(stats.get("downvotes") or 0),
        versions=versions,
        raw=raw,
    )
