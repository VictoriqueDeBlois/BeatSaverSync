from __future__ import annotations

import pytest

from beatsaver_sync.matching import (
    Matcher,
    build_queries,
    dedupe_queries,
    score_candidate,
    split_title_queries,
    title_needs_query_expansion,
    is_short_or_generic_title,
)
from beatsaver_sync.models import Artist, BeatSaverDifficulty, BeatSaverMap, BeatSaverVersion, NeteaseSong


def make_map(
    map_id: str,
    song_name: str,
    artist: str,
    difficulties: list[str],
    score: float = 0.9,
) -> BeatSaverMap:
    return BeatSaverMap(
        id=map_id,
        name=f"{song_name} - {artist}",
        song_name=song_name,
        song_author_name=artist,
        score=score,
        versions=[
            BeatSaverVersion(
                hash=f"hash-{map_id}",
                download_url=f"https://example.test/{map_id}.zip",
                diffs=[BeatSaverDifficulty(difficulty=difficulty) for difficulty in difficulties],
            )
        ],
    )


def test_build_queries_removes_common_noise() -> None:
    song = NeteaseSong(id=1, name="All Alone With You (TV Size) [Psycho-Pass ED2]", artists=[Artist(name="EGOIST")])

    queries = build_queries(song)

    assert queries[0] == "All Alone With You (TV Size) [Psycho-Pass ED2]"
    assert "all alone with you" in queries
    assert all("EGOIST" not in query for query in queries)


def test_build_queries_can_include_artists_when_enabled() -> None:
    song = NeteaseSong(id=1, name="All Alone With You", artists=[Artist(name="EGOIST")])

    queries = build_queries(song, include_artists=True)

    assert "all alone with you EGOIST" in queries


def test_split_title_queries_handles_multilingual_title() -> None:
    queries = split_title_queries("白夜洇润 unfurling night")

    assert "白夜洇润" in queries
    assert "unfurling night" in queries


def test_build_queries_dedupes_case_only_variants() -> None:
    song = NeteaseSong(id=1, name="PROVANT", artists=[Artist(name="SawanoHiroyuki[nZk]")])

    assert build_queries(song) == ["PROVANT"]


def test_dedupe_queries_is_case_insensitive() -> None:
    assert dedupe_queries(["A cup of coffee", "a cup of coffee", "  A  cup  of coffee  "]) == ["A cup of coffee"]


def test_score_prefers_correct_artist_over_more_playable_wrong_song() -> None:
    song = NeteaseSong(id=1, name="All Alone With You", artists=[Artist(name="EGOIST")])
    correct = make_map("a", "All Alone With You", "EGOIST", ["ExpertPlus"])
    wrong_but_easy = make_map("b", "Rock with you", "SEVENTEEN", ["Easy", "Normal", "Hard", "Expert"])

    assert score_candidate(song, correct).score > score_candidate(song, wrong_but_easy).score


def test_score_caps_low_artist_match_below_auto_download_threshold() -> None:
    song = NeteaseSong(id=1, name="A cup of coffee", artists=[Artist(name="ChiliChill乐团")])
    wrong_artist = make_map("a", "Last Cup Of Coffee", "LilyPitchu, Valkyrae, Natsumiii", ["Easy", "Normal", "Hard"])

    assert score_candidate(song, wrong_artist).score < 0.72


def test_score_rewards_low_difficulty_when_song_matches() -> None:
    song = NeteaseSong(id=1, name="All Alone With You", artists=[Artist(name="EGOIST")])
    expert_plus_only = make_map("a", "All Alone With You", "EGOIST", ["ExpertPlus"])
    many_difficulties = make_map("b", "All Alone With You", "EGOIST", ["Easy", "Normal", "Hard", "Expert"])

    assert score_candidate(song, many_difficulties).score > score_candidate(song, expert_plus_only).score


class FakeBeatSaver:
    def __init__(self, results: list[BeatSaverMap] | dict[str, list[BeatSaverMap]]) -> None:
        self.results = results
        self.queries: list[str] = []

    async def search(self, query: str) -> list[BeatSaverMap]:
        self.queries.append(query)
        if isinstance(self.results, dict):
            return self.results.get(query, [])
        return self.results


class FakeJudge:
    def __init__(
        self,
        selected_id: str,
        confidence: float = 0.95,
        reason: str = "test judgment",
        search_queries: list[str] | None = None,
    ) -> None:
        self.selected_id = selected_id
        self.confidence = confidence
        self.reason = reason
        self.search_queries = search_queries or []

    async def judge(self, song: NeteaseSong, candidates: list[BeatSaverMap]) -> tuple[str | None, float, str]:
        return self.selected_id, self.confidence, self.reason

    async def suggest_search_queries(self, song: NeteaseSong) -> list[str]:
        return self.search_queries


def test_title_needs_query_expansion_only_for_non_ascii() -> None:
    assert title_needs_query_expansion("恋愛裁判")
    assert not title_needs_query_expansion("Love Trial")


def test_short_or_generic_title_detection() -> None:
    assert is_short_or_generic_title("Q")
    assert is_short_or_generic_title("Baby")
    assert not is_short_or_generic_title("恋愛裁判")


@pytest.mark.asyncio
async def test_llm_selection_must_pass_artist_gate() -> None:
    song = NeteaseSong(id=1, name="白夜洇润 Unfurling Night", artists=[Artist(name="HOYO-MiX")])
    wrong = make_map("wrong", "Byakuya gentou", "Nekomata Master", ["Easy", "Normal", "Expert"])
    matcher = Matcher(FakeBeatSaver([wrong]), FakeJudge("wrong"), min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "low_confidence"
    assert result.selected is None
    assert "failed the local artist/title gate" in result.reason


@pytest.mark.asyncio
async def test_llm_selection_accepts_artist_alias_case() -> None:
    song = NeteaseSong(id=1, name="どうかしてる", artists=[Artist(name="WurtS")])
    correct = make_map("correct", "Doukashiteru (どうかしてる)", "Wurts", ["Expert"])
    matcher = Matcher(FakeBeatSaver([correct]), FakeJudge("correct"), min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "matched"
    assert result.selected == correct


@pytest.mark.asyncio
async def test_llm_selection_accepts_translation_when_reason_confirms_artist() -> None:
    song = NeteaseSong(id=1, name="恋愛裁判", artists=[Artist(name="40mP"), Artist(name="初音ミク")])
    correct = make_map("correct", "Love Trial", "40mP", ["Expert"])
    judge = FakeJudge(
        "correct",
        confidence=0.95,
        reason="The title is a direct English translation of 恋愛裁判 and the artist matches exactly: 40mP.",
    )
    matcher = Matcher(FakeBeatSaver([correct]), judge, min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "matched"
    assert result.selected == correct


@pytest.mark.asyncio
async def test_cover_aware_mode_accepts_high_confidence_cover_relation() -> None:
    song = NeteaseSong(id=1, name="Rolling Girl", artists=[Artist(name="acane_madder")])
    original_map = make_map("correct", "Rolling Girl", "wowaka", ["Expert"])
    judge = FakeJudge(
        "correct",
        confidence=0.95,
        reason="This is the same song and an original/cover relationship; title matches Rolling Girl.",
    )
    matcher = Matcher(FakeBeatSaver([original_map]), judge, min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "matched"


@pytest.mark.asyncio
async def test_strict_mode_rejects_cover_artist_mismatch() -> None:
    song = NeteaseSong(id=1, name="Rolling Girl", artists=[Artist(name="acane_madder")])
    original_map = make_map("correct", "Rolling Girl", "wowaka", ["Expert"])
    judge = FakeJudge(
        "correct",
        confidence=0.95,
        reason="This is the same song and an original/cover relationship; title matches Rolling Girl.",
    )
    matcher = Matcher(
        FakeBeatSaver([original_map]),
        judge,
        min_confidence=0.72,
        llm_threshold=1.0,
        artist_match_mode="strict",
    )

    result = await matcher.match_song(song)

    assert result.status == "low_confidence"
    assert result.selected is None


@pytest.mark.asyncio
async def test_cover_aware_mode_rejects_short_title_without_artist_confirmation() -> None:
    song = NeteaseSong(id=1, name="Q", artists=[Artist(name="Rega")])
    wrong = make_map("wrong", "Q", "Axiom Gr33ne", ["Expert"])
    judge = FakeJudge("wrong", confidence=0.95, reason="This is the same song with the same title.")
    matcher = Matcher(FakeBeatSaver([wrong]), judge, min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "low_confidence"


@pytest.mark.asyncio
async def test_llm_selection_still_rejects_title_only_coincidence() -> None:
    song = NeteaseSong(id=1, name="白夜洇润 Unfurling Night", artists=[Artist(name="HOYO-MiX")])
    wrong = make_map("wrong", "Byakuya gentou", "Nekomata Master", ["Expert"])
    judge = FakeJudge(
        "wrong",
        confidence=0.95,
        reason="Title contains Byakuya and artist name matches Nekomata Master.",
    )
    matcher = Matcher(FakeBeatSaver([wrong]), judge, min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "low_confidence"
    assert result.selected is None


@pytest.mark.asyncio
async def test_matcher_uses_llm_search_expansion_after_empty_search() -> None:
    song = NeteaseSong(id=1, name="恋愛裁判", artists=[Artist(name="40mP")])
    correct = make_map("correct", "Love Trial", "40mP", ["Expert"])
    beatsaver = FakeBeatSaver({"恋愛裁判": [], "Love Trial": [correct]})
    judge = FakeJudge(
        "correct",
        reason="The title is a direct English translation and the artist matches exactly: 40mP.",
        search_queries=["Love Trial"],
    )
    matcher = Matcher(beatsaver, judge, min_confidence=0.72, llm_threshold=1.0)

    result = await matcher.match_song(song)

    assert result.status == "matched"
    assert "Love Trial" in result.queries
    assert beatsaver.queries == ["恋愛裁判", "Love Trial"]
