from __future__ import annotations

import json
import logging

import httpx

from .models import BeatSaverMap, NeteaseSong

LOGGER = logging.getLogger(__name__)


class OllamaJudge:
    def __init__(
        self,
        model: str = "qwen3.6:27b",
        fallback_model: str = "qwen3.5:35b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def judge(self, song: NeteaseSong, candidates: list[BeatSaverMap]) -> tuple[str | None, float, str]:
        if not candidates:
            return None, 0.0, "No candidates."
        prompt = self._prompt(song, candidates[:8])
        for model in [self.model, self.fallback_model]:
            try:
                result = await self._call(model, prompt)
                return self._parse(result)
            except Exception as exc:  # noqa: BLE001 - keep the sync run resilient.
                LOGGER.warning("Ollama judge failed with %s: %s", model, exc)
        return None, 0.0, "Ollama unavailable or returned invalid JSON."

    async def _call(self, model: str, prompt: str) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data.get("response", ""))

    def _parse(self, response: str) -> tuple[str | None, float, str]:
        data = json.loads(response)
        selected_id = data.get("selected_id")
        if selected_id in ("", "none", "null"):
            selected_id = None
        confidence = float(data.get("confidence", 0.0))
        reason = str(data.get("reason", ""))
        return selected_id, max(0.0, min(confidence, 1.0)), reason

    def _prompt(self, song: NeteaseSong, candidates: list[BeatSaverMap]) -> str:
        candidate_lines = [
            {
                "id": item.id,
                "title": item.name,
                "songName": item.song_name,
                "artist": item.song_author_name,
                "difficulties": sorted({diff.difficulty for version in item.versions for diff in version.diffs}),
            }
            for item in candidates
        ]
        return (
            "You select the BeatSaver map that best matches a NetEase Cloud Music song. "
            "Consider multilingual title variants, translations, romanization, artist aliases, TV size/remix/live markers, "
            "and reject unrelated songs. Prefer correct song and artist over popularity or difficulty. "
            "Return JSON only with keys selected_id, confidence, reason. "
            f"NetEase song: {json.dumps({'title': song.name, 'artists': song.artist_names}, ensure_ascii=False)}\n"
            f"BeatSaver candidates: {json.dumps(candidate_lines, ensure_ascii=False)}"
        )
