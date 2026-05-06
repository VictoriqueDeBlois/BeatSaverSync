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

```powershell
uv run beatsaver-sync --netease-liked --cookie-file .secrets/netease.cookie
```

常用参数：

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
uv run beatsaver-sync --cookie-file .secrets/netease.cookie --limit 10
```

## 输出

- `output/downloads/*.zip`：下载好的 BeatSaver 谱面 zip。
- `output/downloads/index.json`：已下载版本 hash 索引，用来跳过重复谱面。
- `output/cache/beatsaver_searches.json`：BeatSaver 搜索缓存。
- `output/logs/beatsaver-sync.log`：运行日志。
- `output/reports/report.md`：方便人工查看的报告。
- `output/reports/report.json`：结构化报告。

下载按 BeatSaver 版本 hash 去重。只有索引记录存在，并且对应 zip 文件仍然存在时，才会认为该谱面已经下载过。
