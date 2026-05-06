from __future__ import annotations

from beatsaver_sync.matching import build_queries, score_candidate, split_title_queries
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

    assert queries[0] == "all alone with you"
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
