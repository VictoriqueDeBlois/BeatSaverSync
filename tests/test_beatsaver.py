from __future__ import annotations

import json
from pathlib import Path

from beatsaver_sync.beatsaver import parse_map


def test_parse_har_json_first_result() -> None:
    data = json.loads(Path("har.json").read_text(encoding="utf-8"))
    parsed = parse_map(data["docs"][0])

    assert parsed.id == "28d08"
    assert parsed.song_name == "All Alone With You (TV Size)"
    assert parsed.song_author_name == "EGOIST"
    assert parsed.latest_version is not None
    assert parsed.latest_version.hash == "aa5cafdd2c48812a46aead0dd48dc85cebe62118"
    assert parsed.latest_version.download_url.endswith(".zip")
    assert {diff.difficulty for diff in parsed.latest_version.diffs} == {"Expert", "ExpertPlus"}
