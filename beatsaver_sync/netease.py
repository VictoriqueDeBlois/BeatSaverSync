from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

import httpx

from .models import Artist, NeteaseSong

LOGGER = logging.getLogger(__name__)


class NeteaseError(RuntimeError):
    pass


class NeteaseClient:
    def __init__(self, cookie: str, timeout: float = 30.0) -> None:
        self.cookie = cookie.strip()
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
            "Cookie": self.cookie,
        }

    @classmethod
    def from_cookie_file(cls, path: Path) -> "NeteaseClient":
        if not path.exists():
            raise NeteaseError(
                f"Cookie file not found: {path}. Create it from a logged-in music.163.com browser request."
            )
        cookie = path.read_text(encoding="utf-8").strip()
        if not cookie:
            raise NeteaseError(f"Cookie file is empty: {path}")
        return cls(cookie)

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> dict:
        response = await client.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise NeteaseError(f"Unexpected NetEase response from {url}")
        return data

    async def get_account_profile(self) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            data = await self._get_json(client, "https://music.163.com/api/nuser/account/get")
        profile = data.get("profile")
        if not profile or not profile.get("userId"):
            raise NeteaseError("NetEase login cookie did not return a user profile. Refresh the cookie and try again.")
        return profile

    async def get_liked_playlist_id(self) -> int:
        profile = await self.get_account_profile()
        user_id = int(profile["userId"])
        url = f"https://music.163.com/api/user/playlist/?uid={user_id}&limit=1000&offset=0"
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            data = await self._get_json(client, url)
        playlists = data.get("playlist") or []
        for playlist in playlists:
            if playlist.get("specialType") == 5:
                return int(playlist["id"])
        for playlist in playlists:
            if "喜欢" in str(playlist.get("name", "")):
                return int(playlist["id"])
        raise NeteaseError("Could not find the liked music playlist in the logged-in NetEase account.")

    async def get_playlist_songs(self, playlist_id: int | None = None) -> list[NeteaseSong]:
        playlist_id = playlist_id or await self.get_liked_playlist_id()
        url = f"https://music.163.com/api/v6/playlist/detail?id={playlist_id}&n=100000&s=8"
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            data = await self._get_json(client, url)
            playlist = data.get("playlist") or {}
            tracks = playlist.get("tracks") or []
            track_ids = extract_track_ids(playlist)
            if not track_ids:
                if tracks:
                    LOGGER.info("NetEase playlist %s returned %s embedded tracks.", playlist_id, len(tracks))
                    return [self._parse_song(track) for track in tracks if track.get("id")]
                raise NeteaseError("NetEase playlist response did not contain tracks or trackIds.")
            if len(tracks) >= len(track_ids):
                LOGGER.info("NetEase playlist %s returned %s embedded tracks.", playlist_id, len(tracks))
                return [self._parse_song(track) for track in tracks if track.get("id")]
            LOGGER.info(
                "NetEase playlist %s returned %s embedded tracks and %s trackIds; fetching full song details.",
                playlist_id,
                len(tracks),
                len(track_ids),
            )
            return await self._get_song_details(client, track_ids)

    async def _get_song_details(self, client: httpx.AsyncClient, song_ids: list[int]) -> list[NeteaseSong]:
        songs: list[NeteaseSong] = []
        for start in range(0, len(song_ids), 500):
            batch = song_ids[start : start + 500]
            payload = quote(str([{"id": song_id} for song_id in batch]).replace("'", '"'))
            url = f"https://music.163.com/api/v3/song/detail?c={payload}"
            data = await self._get_json(client, url)
            songs.extend(self._parse_song(song) for song in data.get("songs", []) if song.get("id"))
        return songs

    def _parse_song(self, raw: dict) -> NeteaseSong:
        artists_raw = raw.get("ar") or raw.get("artists") or []
        artists = [Artist(id=artist.get("id"), name=artist.get("name", "")) for artist in artists_raw if artist.get("name")]
        album = raw.get("al") or raw.get("album") or {}
        return NeteaseSong(
            id=int(raw["id"]),
            name=raw.get("name", ""),
            artists=artists,
            album=album.get("name") if isinstance(album, dict) else None,
            duration_ms=raw.get("dt") or raw.get("duration"),
        )


def extract_track_ids(playlist: dict) -> list[int]:
    return [int(item["id"]) for item in playlist.get("trackIds", []) if item.get("id")]
