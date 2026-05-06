from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .beatsaver import BeatSaverClient
from .llm import OllamaJudge
from .models import BeatSaverMap, MatchResult, NeteaseSong

LOGGER = logging.getLogger(__name__)

NOISE_PATTERNS = [
    r"\b(tv|anime|op|ed)\s*(size|ver\.?|version)?\b",
    r"\b(full|short|game|movie)\s*(ver\.?|version)?\b",
    r"\b(inst|instrumental|karaoke|off vocal)\b",
    r"\b(remaster(ed)?|radio edit)\b",
    r"\b\d{4}\s*(remaster|mix)\b",
]

LOW_DIFFICULTIES = {"Easy", "Normal", "Hard"}


@dataclass(frozen=True)
class CandidateScore:
    map: BeatSaverMap
    score: float
    reason: str


def normalize_text(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[【】「」『』《》（）()\[\]{}]", " ", value)
    value = re.sub(r"[-_/|:：,，.。!！?？~〜]", " ", value)
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(feat|ft|featuring)\b.*$", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_parenthetical(value: str) -> str:
    return re.sub(r"[\[(（【].*?[\])）】]", " ", value).strip()


def build_queries(song: NeteaseSong) -> list[str]:
    title = song.name.strip()
    clean_title = normalize_text(strip_parenthetical(title)) or normalize_text(title)
    artists = song.artist_names[:3]
    queries: list[str] = []
    for artist in artists[:2]:
        queries.append(f"{clean_title} {artist}".strip())
    queries.append(clean_title)
    if title and title != clean_title:
        queries.append(title)
    return list(dict.fromkeys(query for query in queries if query))


def difficulty_bonus(item: BeatSaverMap) -> float:
    difficulties = {diff.difficulty for version in item.versions for diff in version.diffs if diff.difficulty}
    low_count = len(difficulties & LOW_DIFFICULTIES)
    coverage = min(len(difficulties), 5) / 5
    expert_plus_only_penalty = -0.08 if difficulties == {"ExpertPlus"} else 0.0
    return (low_count * 0.035) + (coverage * 0.05) + expert_plus_only_penalty


def score_candidate(song: NeteaseSong, item: BeatSaverMap) -> CandidateScore:
    title = normalize_text(song.name)
    title_clean = normalize_text(strip_parenthetical(song.name))
    bs_title = normalize_text(item.song_name or item.name)
    bs_full = normalize_text(f"{item.name} {item.song_name}")
    title_score = max(fuzz.token_set_ratio(title, bs_title), fuzz.token_set_ratio(title_clean, bs_title)) / 100
    full_title_score = fuzz.token_set_ratio(title_clean or title, bs_full) / 100
    artist_scores = [
        fuzz.token_set_ratio(normalize_text(artist), normalize_text(item.song_author_name)) / 100
        for artist in song.artist_names
    ]
    artist_score = max(artist_scores) if artist_scores else 0.0
    popularity = min(max(item.score, 0.0), 1.0) * 0.08
    score = (title_score * 0.48) + (full_title_score * 0.2) + (artist_score * 0.22) + popularity + difficulty_bonus(item)
    if artist_score < 0.45 and title_score < 0.92:
        score -= 0.18
    if song.artist_names and artist_score < 0.45:
        score = min(score, 0.68)
    score = max(0.0, min(score, 1.0))
    reason = f"title={title_score:.2f}, full_title={full_title_score:.2f}, artist={artist_score:.2f}"
    return CandidateScore(item, score, reason)


class Matcher:
    def __init__(
        self,
        beatsaver: BeatSaverClient,
        judge: OllamaJudge,
        min_confidence: float = 0.72,
        llm_margin: float = 0.08,
        llm_threshold: float = 0.82,
        ollama_concurrency: int = 1,
    ) -> None:
        self.beatsaver = beatsaver
        self.judge = judge
        self.min_confidence = min_confidence
        self.llm_margin = llm_margin
        self.llm_threshold = llm_threshold
        self.ollama_sem = asyncio.Semaphore(max(1, ollama_concurrency))

    async def match_song(self, song: NeteaseSong) -> MatchResult:
        queries = build_queries(song)
        seen: dict[str, BeatSaverMap] = {}
        search_errors: list[str] = []
        for query in queries:
            try:
                for item in await self.beatsaver.search(query):
                    seen.setdefault(item.id, item)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("BeatSaver search failed for %s with query %r: %s", song.name, query, exc)
                search_errors.append(f"{query}: {exc}")
        candidates = list(seen.values())
        if not candidates:
            if search_errors:
                return MatchResult(
                    song=song,
                    status="error",
                    queries=queries,
                    error="; ".join(search_errors),
                    reason="All BeatSaver search queries failed.",
                )
            return MatchResult(song=song, status="not_found", queries=queries, reason="No BeatSaver search results.")
        scored = sorted((score_candidate(song, item) for item in candidates), key=lambda item: item.score, reverse=True)
        best = scored[0]
        use_llm = self._needs_llm(scored)
        if use_llm:
            async with self.ollama_sem:
                selected_id, confidence, reason = await self.judge.judge(song, [item.map for item in scored[:8]])
            if selected_id and selected_id in seen:
                selected = seen[selected_id]
                version = selected.latest_version
                status = "matched" if confidence >= self.min_confidence else "low_confidence"
                return MatchResult(
                    song=song,
                    status=status,
                    confidence=confidence,
                    selected=selected,
                    selected_version=version,
                    queries=queries,
                    reason=f"Ollama: {reason}",
                    candidates=[item.map for item in scored[:8]],
                    llm_used=True,
                )
            if confidence > 0:
                return MatchResult(
                    song=song,
                    status="low_confidence",
                    confidence=confidence,
                    queries=queries,
                    reason=f"Ollama rejected candidates: {reason}",
                    candidates=[item.map for item in scored[:8]],
                    llm_used=True,
                )
        status = "matched" if best.score >= self.min_confidence else "low_confidence"
        return MatchResult(
            song=song,
            status=status,
            confidence=best.score,
            selected=best.map,
            selected_version=best.map.latest_version,
            queries=queries,
            reason=best.reason,
            candidates=[item.map for item in scored[:8]],
            llm_used=False,
        )

    def _needs_llm(self, scored: list[CandidateScore]) -> bool:
        if not scored:
            return False
        if scored[0].score < self.llm_threshold:
            return True
        if len(scored) > 1 and scored[0].score - scored[1].score < self.llm_margin:
            return True
        return False
