from __future__ import annotations

from pathlib import Path

from beatsaver_sync.models import Artist, MatchResult, NeteaseSong, RunReport
from beatsaver_sync.reports import write_report


def test_write_report_outputs_markdown_and_json(tmp_path: Path) -> None:
    report = RunReport(total_songs=1, output_dir=str(tmp_path))
    report.matches = [
        MatchResult(
            song=NeteaseSong(id=1, name="Missing Song", artists=[Artist(name="Artist")]),
            status="not_found",
            reason="No BeatSaver search results.",
        )
    ]
    report.finish()

    md_path, json_path = write_report(report, tmp_path)

    assert md_path.exists()
    assert json_path.exists()
    assert "Missing Song" in md_path.read_text(encoding="utf-8")
