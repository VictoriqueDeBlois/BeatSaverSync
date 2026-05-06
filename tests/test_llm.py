from __future__ import annotations

import pytest

from beatsaver_sync.llm import OllamaJudge


def test_parse_ollama_json_with_thinking_text() -> None:
    judge = OllamaJudge()

    selected_id, confidence, reason = judge._parse(
        '<think>checking candidates</think>\n{"selected_id":"abc","confidence":0.83,"reason":"same song"}'
    )

    assert selected_id == "abc"
    assert confidence == 0.83
    assert reason == "same song"


@pytest.mark.asyncio
async def test_invalid_primary_response_does_not_call_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = OllamaJudge(model="primary", fallback_model="fallback")
    calls: list[str] = []

    async def fake_call(model: str, prompt: str) -> str:
        calls.append(model)
        return "not json"

    monkeypatch.setattr(judge, "_call", fake_call)
    selected_id, confidence, reason = await judge.judge(song=_song(), candidates=[])

    assert selected_id is None
    assert confidence == 0.0
    assert calls == []


@pytest.mark.asyncio
async def test_invalid_primary_response_with_candidates_does_not_call_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = OllamaJudge(model="primary", fallback_model="fallback")
    calls: list[str] = []

    async def fake_call(model: str, prompt: str) -> str:
        calls.append(model)
        return "not json"

    monkeypatch.setattr(judge, "_call", fake_call)
    selected_id, confidence, reason = await judge.judge(song=_song(), candidates=[_candidate()])

    assert selected_id is None
    assert confidence == 0.0
    assert "invalid JSON" in reason
    assert calls == ["primary"]


def _song():
    from beatsaver_sync.models import NeteaseSong

    return NeteaseSong(id=1, name="Song")


def _candidate():
    from beatsaver_sync.models import BeatSaverMap

    return BeatSaverMap(id="abc", name="Song", song_name="Song", song_author_name="Artist")
