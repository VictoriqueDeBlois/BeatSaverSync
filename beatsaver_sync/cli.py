from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .beatsaver import BeatSaverClient
from .downloader import DownloadManager
from .llm import OllamaJudge
from .matching import Matcher
from .models import DownloadResult, MatchResult, RunReport, ensure_directory
from .netease import NeteaseClient
from .reports import write_report

app = typer.Typer(no_args_is_help=True, help="Download BeatSaver maps that match your NetEase Cloud Music liked playlist.")
console = Console()


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            RichHandler(console=console, show_path=False, rich_tracebacks=True),
        ],
        force=True,
    )


@app.command("sync")
def sync_command(
    netease_liked: Annotated[bool, typer.Option("--netease-liked", help="Read the logged-in user's liked playlist.")] = True,
    cookie_file: Annotated[Path, typer.Option("--cookie-file", help="NetEase cookie file path.")] = Path(
        ".secrets/netease.cookie"
    ),
    output: Annotated[Path, typer.Option("--output", help="Output directory.")] = Path("output"),
    search_concurrency: Annotated[int, typer.Option("--search-concurrency", min=1)] = 5,
    download_concurrency: Annotated[int, typer.Option("--download-concurrency", min=1)] = 3,
    ollama_concurrency: Annotated[int, typer.Option("--ollama-concurrency", min=1)] = 1,
    ollama_model: Annotated[str, typer.Option("--ollama-model")] = "qwen3.6:27b",
    ollama_fallback_model: Annotated[str, typer.Option("--ollama-fallback-model")] = "qwen3.5:35b",
    min_confidence: Annotated[float, typer.Option("--min-confidence", min=0.0, max=1.0)] = 0.72,
    force_refresh_search: Annotated[bool, typer.Option("--force-refresh-search")] = False,
    redownload: Annotated[bool, typer.Option("--redownload")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Limit songs for smoke testing.")] = None,
) -> None:
    if not netease_liked:
        raise typer.BadParameter("Only --netease-liked is supported in the first version.")
    asyncio.run(
        run_sync(
            cookie_file=cookie_file,
            output=output,
            search_concurrency=search_concurrency,
            download_concurrency=download_concurrency,
            ollama_concurrency=ollama_concurrency,
            ollama_model=ollama_model,
            ollama_fallback_model=ollama_fallback_model,
            min_confidence=min_confidence,
            force_refresh_search=force_refresh_search,
            redownload=redownload,
            limit=limit,
        )
    )


async def run_sync(
    cookie_file: Path,
    output: Path,
    search_concurrency: int,
    download_concurrency: int,
    ollama_concurrency: int,
    ollama_model: str,
    ollama_fallback_model: str,
    min_confidence: float,
    force_refresh_search: bool,
    redownload: bool,
    limit: int | None,
) -> None:
    output = output.resolve()
    cache_dir = ensure_directory(output / "cache")
    downloads_dir = ensure_directory(output / "downloads")
    reports_dir = ensure_directory(output / "reports")
    setup_logging(output / "logs" / "beatsaver-sync.log")
    report = RunReport(output_dir=str(output))
    logging.info("Starting BeatSaver sync.")

    netease = NeteaseClient.from_cookie_file(cookie_file)
    songs = await netease.get_playlist_songs()
    if limit:
        songs = songs[:limit]
    report.total_songs = len(songs)
    console.print(f"[bold]Loaded {len(songs)} NetEase songs.[/bold]")

    beatsaver = BeatSaverClient(cache_path=cache_dir / "beatsaver_searches.json", force_refresh=force_refresh_search)
    judge = OllamaJudge(model=ollama_model, fallback_model=ollama_fallback_model)
    matcher = Matcher(
        beatsaver=beatsaver,
        judge=judge,
        min_confidence=min_confidence,
        ollama_concurrency=ollama_concurrency,
    )

    matches = await match_all(songs, matcher, search_concurrency)
    report.matches = matches
    report.matched = sum(1 for item in matches if item.status == "matched")
    report.low_confidence = sum(1 for item in matches if item.status == "low_confidence")
    report.not_found = sum(1 for item in matches if item.status == "not_found")
    report.errors = sum(1 for item in matches if item.status == "error")

    downloader = DownloadManager(
        downloads_dir=downloads_dir,
        index_path=downloads_dir / "index.json",
        redownload=redownload,
    )
    downloads = await download_all([item for item in matches if item.status == "matched"], downloader, download_concurrency)
    report.downloads = downloads
    report.downloaded = sum(1 for item in downloads if item.status == "downloaded")
    report.skipped_existing = sum(1 for item in downloads if item.status == "skipped_existing")
    report.download_failed = sum(1 for item in downloads if item.status == "failed")
    report.finish()
    md_path, json_path = write_report(report, reports_dir)
    console.print(f"[green]Done.[/green] Report: {md_path}")
    console.print(f"[dim]JSON report: {json_path}[/dim]")


async def match_all(songs, matcher: Matcher, concurrency: int) -> list[MatchResult]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[MatchResult | None] = [None] * len(songs)

    async def worker(index: int, song) -> None:
        async with semaphore:
            results[index] = await matcher.match_song(song)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Searching and matching", total=len(songs))

        async def tracked(index: int, song) -> None:
            progress.update(task, description=f"Searching: {song.name[:42]}")
            await worker(index, song)
            result = results[index]
            suffix = result.status if result else "unknown"
            progress.update(task, advance=1, description=f"Matched: {song.name[:32]} ({suffix})")

        await asyncio.gather(*(tracked(index, song) for index, song in enumerate(songs)))
    return [item for item in results if item is not None]


async def download_all(matches: list[MatchResult], downloader: DownloadManager, concurrency: int) -> list[DownloadResult]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[DownloadResult | None] = [None] * len(matches)
    task_by_hash: dict[str, TaskID] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        total_task = progress.add_task("Downloading maps", total=len(matches))

        def update_download(version_hash: str, completed: int, total: int | None) -> None:
            task_id = task_by_hash.get(version_hash)
            if task_id is None:
                task_id = progress.add_task(version_hash[:10], total=total)
                task_by_hash[version_hash] = task_id
            if total and progress.tasks[task_id].total != total:
                progress.update(task_id, total=total)
            progress.update(task_id, completed=completed)

        async def worker(index: int, match: MatchResult) -> None:
            async with semaphore:
                result = await downloader.download(match, update_download)
                results[index] = result
                version = match.selected_version
                if version and version.hash in task_by_hash:
                    progress.remove_task(task_by_hash[version.hash])
                progress.update(total_task, advance=1)

        await asyncio.gather(*(worker(index, match) for index, match in enumerate(matches)))
    return [item for item in results if item is not None]


if __name__ == "__main__":
    app()
