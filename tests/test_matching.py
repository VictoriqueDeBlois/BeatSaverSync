from __future__ import annotations

from beatsaver_sync.matching import build_queries, score_candidate
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

    assert queries[0] == "all alone with you EGOIST"
    assert "all alone with you" in queries


def test_score_prefers_correct_artist_over_more_playable_wrong_song() -> None:
    song = NeteaseSong(id=1, name="All Alone With You", artists=[Artist(name="EGOIST")])
    correct = make_map("a", "All Alone With You", "EGOIST", ["ExpertPlus"])
    wrong_but_easy = make_map("b", "Rock with you", "SEVENTEEN", ["Easy", "Normal", "Hard", "Expert"])

    assert score_candidate(song, correct).score > score_candidate(song, wrong_but_easy).score


def test_score_rewards_low_difficulty_when_song_matches() -> None:
    song = NeteaseSong(id=1, name="All Alone With You", artists=[Artist(name="EGOIST")])
    expert_plus_only = make_map("a", "All Alone With You", "EGOIST", ["ExpertPlus"])
    many_difficulties = make_map("b", "All Alone With You", "EGOIST", ["Easy", "Normal", "Hard", "Expert"])

    assert score_candidate(song, many_difficulties).score > score_candidate(song, expert_plus_only).score
