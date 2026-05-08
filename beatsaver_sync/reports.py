from __future__ import annotations

from pathlib import Path

from .fs import write_json
from .models import RunReport


def write_report(report: RunReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "report.json"
    md_path = report_dir / "report.md"
    write_json(json_path, report.model_dump(mode="json"))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, json_path


def render_markdown(report: RunReport) -> str:
    lines = [
        "# BeatSaver Sync Report",
        "",
        f"- Started: {report.started_at}",
        f"- Finished: {report.finished_at or ''}",
        f"- Total songs: {report.total_songs}",
        f"- Matched: {report.matched}",
        f"- Download candidates: {sum(max(1, len(match.accepted)) for match in report.matches if match.status == 'matched')}",
        f"- Low confidence skipped: {report.low_confidence}",
        f"- Not found: {report.not_found}",
        f"- Search/match errors: {report.errors}",
        f"- Downloaded: {report.downloaded}",
        f"- Already downloaded: {report.skipped_existing}",
        f"- Download failed: {report.download_failed}",
        "",
        "## Downloads",
        "",
    ]
    if report.downloads:
        lines.append("| Status | NetEase Song | BeatSaver Map | Confidence | File | Error |")
        lines.append("|---|---|---|---:|---|---|")
        for result in report.downloads:
            match = result.match
            song = f"{match.song.name} - {', '.join(match.song.artist_names)}"
            selected = match.selected.name if match.selected else ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        result.status,
                        _cell(song),
                        _cell(selected),
                        f"{match.confidence:.2f}",
                        _cell(result.file_path or ""),
                        _cell(result.error or ""),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No downloads were attempted.")
    lines.extend(["", "## Skipped Or Unmatched", ""])
    skipped = [match for match in report.matches if match.status != "matched"]
    if skipped:
        lines.append("| Status | Song | Confidence | Reason | Top Candidate |")
        lines.append("|---|---|---:|---|---|")
        for match in skipped:
            song = f"{match.song.name} - {', '.join(match.song.artist_names)}"
            top = match.candidates[0].name if match.candidates else ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        match.status,
                        _cell(song),
                        f"{match.confidence:.2f}",
                        _cell(match.reason or match.error or ""),
                        _cell(top),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No low-confidence or unmatched songs.")
    lines.append("")
    return "\n".join(lines)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
