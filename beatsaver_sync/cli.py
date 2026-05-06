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
from .config import apply_overrides, load_config
from .downloader import DownloadManager
from .llm import OllamaJudge
from .matching import Matcher
from .models import DownloadResult, MatchResult, RunReport, ensure_directory
from .netease import NeteaseClient
from .reports import write_report

app = typer.Typer(no_args_is_help=True, help="Download BeatSaver maps that match your NetEase Cloud Music liked playlist.")
console = Console()


def setup_logging(log_path: Path, console_logging: bool) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if console_logging:
        handlers.append(RichHandler(console=console, show_path=False, rich_tracebacks=True))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command("sync")
def sync_command(
    config_file: Annotated[Path, typer.Option("--config", help="JSON config file path.")] = Path("config.json"),
    netease_liked: Annotated[
        bool | None, typer.Option("--netease-liked/--no-netease-liked", help="Read the logged-in user's liked playlist.")
    ] = None,
    cookie_file: Annotated[Path | None, typer.Option("--cookie-file", help="NetEase cookie file path.")] = None,
    output: Annotated[Path | None, typer.Option("--output", help="Output directory.")] = None,
    search_with_artists: Annotated[bool | None, typer.Option("--search-with-artists/--title-only-search")] = None,
    search_concurrency: Annotated[int | None, typer.Option("--search-concurrency", min=1)] = None,
    search_retries: Annotated[int | None, typer.Option("--search-retries", min=1)] = None,
    download_concurrency: Annotated[int | None, typer.Option("--download-concurrency", min=1)] = None,
    ollama_concurrency: Annotated[int | None, typer.Option("--ollama-concurrency", min=1)] = None,
    ollama_model: Annotated[str | None, typer.Option("--ollama-model")] = None,
    ollama_fallback_model: Annotated[str | None, typer.Option("--ollama-fallback-model")] = None,
    min_confidence: Annotated[float | None, typer.Option("--min-confidence", min=0.0, max=1.0)] = None,
    console_logging: Annotated[bool | None, typer.Option("--console-log/--no-console-log")] = None,
    force_refresh_search: Annotated[bool | None, typer.Option("--force-refresh-search/--use-search-cache")] = None,
    redownload: Annotated[bool | None, typer.Option("--redownload/--skip-downloaded")] = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Limit songs for smoke testing.")] = None,
) -> None:
    config = apply_overrides(
        load_config(config_file),
        {
            "netease_liked": netease_liked,
            "cookie_file": cookie_file,
            "output": output,
            "search_with_artists": search_with_artists,
            "search_concurrency": search_concurrency,
            "search_retries": search_retries,
            "download_concurrency": download_concurrency,
            "ollama_concurrency": ollama_concurrency,
            "ollama_model": ollama_model,
            "ollama_fallback_model": ollama_fallback_model,
            "min_confidence": min_confidence,
            "console_logging": console_logging,
            "force_refresh_search": force_refresh_search,
            "redownload": redownload,
            "limit": limit,
        },
    )
    if not config.netease_liked:
        raise typer.BadParameter("Only --netease-liked is supported in the first version.")
    asyncio.run(
        run_sync(
            cookie_file=config.cookie_file,
            output=config.output,
            search_with_artists=config.search_with_artists,
            search_concurrency=config.search_concurrency,
            search_retries=config.search_retries,
            download_concurrency=config.download_concurrency,
            ollama_concurrency=config.ollama_concurrency,
            ollama_model=config.ollama_model,
            ollama_fallback_model=config.ollama_fallback_model,
            min_confidence=config.min_confidence,
            console_logging=config.console_logging,
            force_refresh_search=config.force_refresh_search,
            redownload=config.redownload,
            limit=config.limit,
        )
    )


async def run_sync(
    cookie_file: Path,
    output: Path,
    search_with_artists: bool,
    search_concurrency: int,
    search_retries: int,
    download_concurrency: int,
    ollama_concurrency: int,
    ollama_model: str,
    ollama_fallback_model: str,
    min_confidence: float,
    console_logging: bool,
    force_refresh_search: bool,
    redownload: bool,
    limit: int | None,
) -> None:
    output = output.resolve()
    cache_dir = ensure_directory(output / "cache")
    downloads_dir = ensure_directory(output / "downloads")
    reports_dir = ensure_directory(output / "reports")
    setup_logging(output / "logs" / "beatsaver-sync.log", console_logging=console_logging)
    report = RunReport(output_dir=str(output))
    logging.info("Starting BeatSaver sync.")

    netease = NeteaseClient.from_cookie_file(cookie_file)
    songs = await netease.get_playlist_songs()
    if limit:
        songs = songs[:limit]
    report.total_songs = len(songs)
    console.print(f"[bold]Loaded {len(songs)} NetEase songs.[/bold]")

    beatsaver = BeatSaverClient(
        cache_path=cache_dir / "beatsaver_searches.json",
        force_refresh=force_refresh_search,
        retries=search_retries,
    )
    judge = OllamaJudge(model=ollama_model, fallback_model=ollama_fallback_model)
    matcher = Matcher(
        beatsaver=beatsaver,
        judge=judge,
        min_confidence=min_confidence,
        search_with_artists=search_with_artists,
        ollama_concurrency=ollama_concurrency,
    )

    downloader = DownloadManager(
        downloads_dir=downloads_dir,
        index_path=downloads_dir / "index.json",
        redownload=redownload,
    )
    md_path = reports_dir / "report.md"
    json_path = reports_dir / "report.json"
    try:
        await run_pipeline(
            songs=songs,
            matcher=matcher,
            downloader=downloader,
            report=report,
            report_dir=reports_dir,
            search_concurrency=search_concurrency,
            download_concurrency=download_concurrency,
        )
    finally:
        report.finish()
        md_path, json_path = write_report(report, reports_dir)
    console.print(f"[green]Done.[/green] Report: {md_path}")
    console.print(f"[dim]JSON report: {json_path}[/dim]")


async def run_pipeline(
    songs,
    matcher: Matcher,
    downloader: DownloadManager,
    report: RunReport,
    report_dir: Path,
    search_concurrency: int,
    download_concurrency: int,
) -> None:
    song_queue: asyncio.Queue = asyncio.Queue()
    download_queue: asyncio.Queue[MatchResult | None] = asyncio.Queue()
    task_by_hash: dict[str, TaskID] = {}
    report_lock = asyncio.Lock()
    for song in songs:
        song_queue.put_nowait(song)

    async def record_match(match: MatchResult) -> None:
        async with report_lock:
            report.matches.append(match)
            if match.status == "matched":
                report.matched += 1
            elif match.status == "low_confidence":
                report.low_confidence += 1
            elif match.status == "not_found":
                report.not_found += 1
            elif match.status == "error":
                report.errors += 1
            write_report(report, report_dir)

    async def record_download(result: DownloadResult) -> None:
        async with report_lock:
            report.downloads.append(result)
            if result.status == "downloaded":
                report.downloaded += 1
            elif result.status == "skipped_existing":
                report.skipped_existing += 1
            elif result.status == "failed":
                report.download_failed += 1
            write_report(report, report_dir)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        match_task = progress.add_task("Matching songs", total=len(songs))
        download_task = progress.add_task("Downloads: 0 queued", total=None)

        def update_download(version_hash: str, completed: int, total: int | None) -> None:
            task_id = task_by_hash.get(version_hash)
            if task_id is None:
                task_id = progress.add_task(f"Downloading {version_hash[:10]}", total=total)
                task_by_hash[version_hash] = task_id
            if total:
                progress.update(task_id, total=total)
            progress.update(task_id, completed=completed)

        async def match_worker(worker_id: int) -> None:
            while True:
                try:
                    song = song_queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                progress.update(match_task, description=f"Matching: {song.name[:42]}")
                try:
                    match = await matcher.match_song(song)
                    await record_match(match)
                    if match.status == "matched":
                        await download_queue.put(match)
                        progress.update(download_task, description=f"Downloads: {download_queue.qsize()} queued")
                    progress.update(match_task, advance=1, description=f"Matched: {song.name[:32]} ({match.status})")
                finally:
                    song_queue.task_done()

        async def download_worker(worker_id: int) -> None:
            while True:
                match = await download_queue.get()
                if match is None:
                    download_queue.task_done()
                    return
                try:
                    result = await downloader.download(match, update_download)
                    await record_download(result)
                    version = match.selected_version
                    if version and version.hash in task_by_hash:
                        progress.remove_task(task_by_hash[version.hash])
                        task_by_hash.pop(version.hash, None)
                    progress.update(
                        download_task,
                        advance=1,
                        description=(
                            f"Downloads: {download_queue.qsize()} queued, "
                            f"{report.downloaded} downloaded, {report.skipped_existing} existing, {report.download_failed} failed"
                        ),
                    )
                finally:
                    download_queue.task_done()

        download_workers = [asyncio.create_task(download_worker(index)) for index in range(download_concurrency)]
        match_workers = [asyncio.create_task(match_worker(index)) for index in range(search_concurrency)]
        await asyncio.gather(*match_workers)
        for _ in download_workers:
            await download_queue.put(None)
        await download_queue.join()
        await asyncio.gather(*download_workers)


if __name__ == "__main__":
    app()
