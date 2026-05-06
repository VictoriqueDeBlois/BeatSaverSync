from __future__ import annotations

from beatsaver_sync.netease import batched, extract_track_ids


def test_extract_track_ids_returns_all_playlist_ids() -> None:
    playlist = {"trackIds": [{"id": 1}, {"id": 2}, {"id": 3}]}

    assert extract_track_ids(playlist) == [1, 2, 3]


def test_extract_track_ids_ignores_missing_ids() -> None:
    playlist = {"trackIds": [{"id": 1}, {}, {"id": 3}]}

    assert extract_track_ids(playlist) == [1, 3]


def test_batched_splits_song_ids() -> None:
    assert batched([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
