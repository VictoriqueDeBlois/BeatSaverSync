from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .fs import read_json
from .matching import score_candidate
from .models import BeatSaverMap, BeatSaverVersion, MatchResult, NeteaseSong, RunReport

REVIEW_FIELDS = [
    "download",
    "source",
    "confidence",
    "netease_song",
    "netease_artists",
    "beatsaver_id",
    "version_hash",
    "download_url",
    "map_title",
    "map_song_name",
    "map_song_author",
    "reason",
]


@dataclass(frozen=True)
class ReviewRow:
    download: str
    source: str
    confidence: float
    netease_song: str
    netease_artists: str
    beatsaver_id: str
    version_hash: str
    download_url: str
    map_title: str
    map_song_name: str
    map_song_author: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "download": self.download,
            "source": self.source,
            "confidence": f"{self.confidence:.4f}",
            "netease_song": self.netease_song,
            "netease_artists": self.netease_artists,
            "beatsaver_id": self.beatsaver_id,
            "version_hash": self.version_hash,
            "download_url": self.download_url,
            "map_title": self.map_title,
            "map_song_name": self.map_song_name,
            "map_song_author": self.map_song_author,
            "reason": self.reason.replace("\r", " ").replace("\n", " "),
        }


def load_run_report(path: Path) -> RunReport:
    return RunReport.model_validate(read_json(path, {}))


def build_low_confidence_review_rows(
    report: RunReport,
    *,
    min_confidence: float = 0.0,
    include_gate_candidates: bool = True,
) -> list[ReviewRow]:
    rows: list[ReviewRow] = []
    seen: set[tuple[int, str]] = set()
    for match in report.matches:
        if match.status != "low_confidence" or match.confidence < min_confidence:
            continue
        if match.selected and match.selected_version:
            rows.append(_row_from_match(match, match.selected, match.selected_version, "selected"))
            seen.add((match.song.id, match.selected_version.hash))
        if include_gate_candidates and "failed the local artist/title gate" in match.reason:
            for candidate in _best_gate_candidates(match):
                version = candidate.latest_version
                if not version or (match.song.id, version.hash) in seen:
                    continue
                rows.append(_row_from_match(match, candidate, version, "gate_candidate"))
                seen.add((match.song.id, version.hash))
    rows.sort(key=lambda row: (row.source != "gate_candidate", -row.confidence, row.netease_song.casefold()))
    return rows


def _best_gate_candidates(match: MatchResult) -> list[BeatSaverMap]:
    scored = sorted(
        ((score_candidate(match.song, candidate).score, candidate) for candidate in match.candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    if not scored:
        return []
    best_score = scored[0][0]
    return [candidate for score, candidate in scored if score >= best_score - 0.001]


def write_review_tsv(rows: list[ReviewRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS, dialect="excel-tab")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
    return path


def read_approved_review_rows(path: Path, *, download_all: bool = False) -> list[ReviewRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, dialect="excel-tab")
        rows = [_row_from_dict(row) for row in reader]
    if download_all:
        return rows
    return [row for row in rows if row.download.strip().casefold() in {"1", "true", "yes", "y"}]


def review_row_to_match(row: ReviewRow) -> MatchResult:
    version = BeatSaverVersion(hash=row.version_hash, download_url=row.download_url)
    selected = BeatSaverMap(
        id=row.beatsaver_id,
        name=row.map_title,
        song_name=row.map_song_name,
        song_author_name=row.map_song_author,
        versions=[version],
    )
    song = NeteaseSong(id=0, name=row.netease_song)
    return MatchResult(
        song=song,
        status="matched",
        confidence=row.confidence,
        selected=selected,
        selected_version=version,
        reason=f"Approved from review TSV: {row.reason}",
    )


def _row_from_match(match: MatchResult, item: BeatSaverMap, version: BeatSaverVersion, source: str) -> ReviewRow:
    return ReviewRow(
        download="0",
        source=source,
        confidence=match.confidence,
        netease_song=match.song.name,
        netease_artists=", ".join(match.song.artist_names),
        beatsaver_id=item.id,
        version_hash=version.hash,
        download_url=version.download_url,
        map_title=item.name,
        map_song_name=item.song_name,
        map_song_author=item.song_author_name,
        reason=match.reason,
    )


def _row_from_dict(row: dict[str, str]) -> ReviewRow:
    return ReviewRow(
        download=row.get("download", ""),
        source=row.get("source", ""),
        confidence=float(row.get("confidence") or 0.0),
        netease_song=row.get("netease_song", ""),
        netease_artists=row.get("netease_artists", ""),
        beatsaver_id=row.get("beatsaver_id", ""),
        version_hash=row.get("version_hash", ""),
        download_url=row.get("download_url", ""),
        map_title=row.get("map_title", ""),
        map_song_name=row.get("map_song_name", ""),
        map_song_author=row.get("map_song_author", ""),
        reason=row.get("reason", ""),
    )
