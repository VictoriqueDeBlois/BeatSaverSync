# BeatSaver Sync

Download BeatSaver maps that best match your NetEase Cloud Music liked playlist.

## Setup

Install dependencies with `uv`:

```powershell
uv sync
```

If you want the default LLM-assisted matching model, pull it once:

```powershell
ollama pull qwen3.6:27b
```

The tool falls back to `qwen3.5:35b` if the default model is unavailable.

## NetEase Cookie

The liked playlist usually needs a logged-in cookie.

1. Log in at `https://music.163.com`.
2. Open browser developer tools and inspect any `music.163.com` network request.
3. Copy the full `Cookie` request header.
4. Save it to `.secrets/netease.cookie`.

`.secrets/` is ignored by git. The cookie is only sent to NetEase and is not written to reports or logs.

## Run

```powershell
uv run beatsaver-sync --netease-liked --cookie-file .secrets/netease.cookie
```

Useful options:

```powershell
uv run beatsaver-sync `
  --output output `
  --search-concurrency 5 `
  --download-concurrency 3 `
  --ollama-concurrency 1 `
  --ollama-model qwen3.6:27b `
  --ollama-fallback-model qwen3.5:35b `
  --min-confidence 0.72
```

For a smoke test:

```powershell
uv run beatsaver-sync --cookie-file .secrets/netease.cookie --limit 10
```

## Output

- `output/downloads/*.zip`: downloaded BeatSaver maps.
- `output/downloads/index.json`: downloaded version-hash index used to skip duplicates.
- `output/cache/beatsaver_searches.json`: BeatSaver search cache.
- `output/logs/beatsaver-sync.log`: run log.
- `output/reports/report.md`: human-readable report.
- `output/reports/report.json`: structured report.

Downloads are deduplicated by BeatSaver version hash. A record is considered downloaded only when the index entry exists and the zip file still exists on disk.
