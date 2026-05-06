from __future__ import annotations

import json
from pathlib import Path

from beatsaver_sync.beatsaver import parse_map


def test_parse_har_json_first_result() -> None:
    data = _load_sample_response()
    parsed = parse_map(data["docs"][0])

    assert parsed.id == "28d08"
    assert parsed.song_name == "All Alone With You (TV Size)"
    assert parsed.song_author_name == "EGOIST"
    assert parsed.latest_version is not None
    assert parsed.latest_version.hash == "aa5cafdd2c48812a46aead0dd48dc85cebe62118"
    assert parsed.latest_version.download_url.endswith(".zip")
    assert {diff.difficulty for diff in parsed.latest_version.diffs} == {"Expert", "ExpertPlus"}


def _load_sample_response() -> dict:
    har_path = Path("har.json")
    if har_path.exists():
        return json.loads(har_path.read_text(encoding="utf-8"))
    return {
        "docs": [
            {
                "id": "28d08",
                "name": "All Alone With You (TV Size) [Psycho-Pass Ending 2] - EGOIST",
                "metadata": {
                    "duration": 91,
                    "songName": "All Alone With You (TV Size)",
                    "songAuthorName": "EGOIST",
                    "levelAuthorName": "Joetastic",
                },
                "stats": {"score": 0.9387, "upvotes": 189, "downvotes": 7},
                "versions": [
                    {
                        "hash": "aa5cafdd2c48812a46aead0dd48dc85cebe62118",
                        "downloadURL": "https://r2cdn.beatsaver.com/aa5cafdd2c48812a46aead0dd48dc85cebe62118.zip",
                        "diffs": [{"difficulty": "Expert"}, {"difficulty": "ExpertPlus"}],
                    }
                ],
            }
        ]
    }
