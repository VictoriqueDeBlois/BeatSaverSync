from __future__ import annotations

from pathlib import Path

from beatsaver_sync.models import Artist, BeatSaverMap, BeatSaverVersion, MatchResult, NeteaseSong, RunReport
from beatsaver_sync.review import (
    build_low_confidence_review_rows,
    read_approved_review_rows,
    review_row_to_match,
    write_review_tsv,
)


def make_match(status: str = "low_confidence", reason: str = "title=0.60") -> MatchResult:
    version = BeatSaverVersion(hash="abc123", download_url="https://example.test/map.zip")
    selected = BeatSaverMap(
        id="map-id",
        name="Map Title",
        song_name="Song Title",
        song_author_name="Artist",
        versions=[version],
    )
    song = NeteaseSong(id=1, name="NetEase Song", artists=[Artist(name="Artist")])
    return MatchResult(
        song=song,
        status=status,
        confidence=0.68,
        selected=selected,
        selected_version=version,
        reason=reason,
    )


def test_build_review_rows_includes_downloadable_low_confidence() -> None:
    report = RunReport(matches=[make_match()])

    rows = build_low_confidence_review_rows(report, min_confidence=0.6)

    assert len(rows) == 1
    assert rows[0].download == "0"
    assert rows[0].version_hash == "abc123"


def test_review_tsv_round_trip_only_approved_rows(tmp_path: Path) -> None:
    path = tmp_path / "review.tsv"
    rows = build_low_confidence_review_rows(RunReport(matches=[make_match()]))
    rows[0] = rows[0].__class__(**{**rows[0].__dict__, "download": "1"})

    write_review_tsv(rows, path)
    approved = read_approved_review_rows(path)

    assert len(approved) == 1
    assert review_row_to_match(approved[0]).selected_version.download_url == "https://example.test/map.zip"
