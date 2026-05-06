from __future__ import annotations

from beatsaver_sync.llm import OllamaJudge


def test_parse_ollama_json_with_thinking_text() -> None:
    judge = OllamaJudge()

    selected_id, confidence, reason = judge._parse(
        '<think>checking candidates</think>\n{"selected_id":"abc","confidence":0.83,"reason":"same song"}'
    )

    assert selected_id == "abc"
    assert confidence == 0.83
    assert reason == "same song"
