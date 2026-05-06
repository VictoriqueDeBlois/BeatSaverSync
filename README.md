# BeatSaver Sync

根据你的网易云“我喜欢的音乐”列表，自动搜索并下载最匹配的 BeatSaver 谱面。

## 安装

使用 `uv` 安装依赖：

```powershell
uv sync
```

如果要使用默认的本地大模型辅助匹配，先拉取一次模型：

```powershell
ollama pull qwen3.6:27b
```

如果默认模型不可用，工具会回退到 `qwen3.5:35b`。

## 网易云 Cookie

红心歌单通常需要登录态 cookie 才能完整读取。

1. 在浏览器登录 `https://music.163.com`。
2. 打开浏览器开发者工具，查看任意 `music.163.com` 的网络请求。
3. 复制请求头里的完整 `Cookie`。
4. 保存到 `.secrets/netease.cookie`。

`.secrets/` 已被 git 忽略。cookie 只会发送给网易云，不会写入报告或日志。

## 运行

默认参数都在 `config.json` 里，日常直接运行：

```powershell
uv run beatsaver-sync
```

如果要使用其他配置文件：

```powershell
uv run beatsaver-sync --config config.json
```

`config.json` 示例：

```json
{
  "netease_liked": true,
  "cookie_file": ".secrets/netease.cookie",
  "output": "output",
  "search_concurrency": 5,
  "download_concurrency": 3,
  "ollama_concurrency": 1,
  "ollama_model": "qwen3.6:27b",
  "ollama_fallback_model": "qwen3.5:35b",
  "min_confidence": 0.72,
  "force_refresh_search": false,
  "redownload": false,
  "limit": null
}
```

命令行参数仍然可以临时覆盖配置：

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

如果想先小范围试跑：

```powershell
uv run beatsaver-sync --limit 10
```

## 配置参数

`netease_liked`

是否读取网易云“我喜欢的音乐”歌单。当前版本只支持这个来源，所以保持 `true` 即可。

`cookie_file`

网易云登录态 cookie 文件路径。默认是 `.secrets/netease.cookie`。如果你把 cookie 放在别的位置，就改成对应路径。不要把 cookie 直接写进 `config.json`。

`output`

输出目录。默认是 `output`，下载的 zip、缓存、日志和报告都会放在这里。如果你想把结果放到其他盘或单独目录，可以改成绝对路径或相对路径。

`search_concurrency`

BeatSaver 搜索和匹配阶段的并发数。默认 `5` 比较温和。调大可以更快，但也更容易遇到网络波动或接口限流；如果搜索经常失败，可以调低到 `2` 或 `3`。

`download_concurrency`

同时下载 zip 的数量。默认 `3`。网速很快时可以调到 `5`，但太高会让进度条更乱，也可能触发下载失败。

`ollama_concurrency`

同时调用 Ollama 做疑难判断的数量。默认 `1`。本地大模型比较吃显存，4090 上也建议先保持 `1`；如果确认模型运行很稳，再考虑调到 `2`。

`ollama_model`

疑难匹配时优先使用的 Ollama 模型。默认 `qwen3.6:27b`，适合中英日混合歌名、翻译名和歌手别名判断。第一次使用前需要执行 `ollama pull qwen3.6:27b`。

`ollama_fallback_model`

主模型不可用或调用失败时使用的备用模型。默认 `qwen3.5:35b`，因为你本地已经有这个模型。备用模型也失败时，工具会退回规则打分结果或把结果标为低置信。

`min_confidence`

自动下载的最低置信度阈值，范围是 `0.0` 到 `1.0`，默认 `0.72`。调高会减少误下载，但跳过更多歌曲；调低会下载更多候选，但错配风险更高。

`force_refresh_search`

是否忽略 BeatSaver 搜索缓存并重新请求接口。默认 `false`。如果你觉得缓存结果过旧，或调整了搜索逻辑后想重新搜索，可以改成 `true` 或临时加 `--force-refresh-search`。

`redownload`

是否无视已下载索引，强制重新下载。默认 `false`。平时不要打开；只有当 zip 损坏、想重新拉一遍文件时再改成 `true` 或临时加 `--redownload`。

`limit`

限制本次最多处理多少首歌。默认 `null`，表示处理完整红心歌单。调试时建议设成 `10` 或使用 `--limit 10`，确认 cookie、搜索、匹配和下载都正常后再跑全量。

## 输出

- `output/downloads/*.zip`：下载好的 BeatSaver 谱面 zip。
- `output/downloads/index.json`：已下载版本 hash 索引，用来跳过重复谱面。
- `output/cache/beatsaver_searches.json`：BeatSaver 搜索缓存。
- `output/logs/beatsaver-sync.log`：运行日志。
- `output/reports/report.md`：方便人工查看的报告。
- `output/reports/report.json`：结构化报告。

下载按 BeatSaver 版本 hash 去重。只有索引记录存在，并且对应 zip 文件仍然存在时，才会认为该谱面已经下载过。
