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
async def test_call_uses_response_field(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = OllamaJudge(model="primary")
    captured_payload = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"selected_id":"abc","confidence":0.8,"reason":"ok"}'}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url: str, json: dict):
            captured_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr("beatsaver_sync.llm.httpx.AsyncClient", FakeClient)

    result = await judge._call("primary", "prompt")

    assert result.startswith("{")
    assert captured_payload["think"] is False
    assert captured_payload["options"]["num_predict"] == 160
    assert captured_payload["options"]["num_ctx"] == 2048


@pytest.mark.asyncio
async def test_call_falls_back_to_thinking_field(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = OllamaJudge(model="primary")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": "", "thinking": '{"selected_id":"abc","confidence":0.8,"reason":"ok"}'}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url: str, json: dict):
            return FakeResponse()

    monkeypatch.setattr("beatsaver_sync.llm.httpx.AsyncClient", FakeClient)

    assert await judge._call("primary", "prompt") == '{"selected_id":"abc","confidence":0.8,"reason":"ok"}'


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
