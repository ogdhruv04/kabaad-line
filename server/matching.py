"""Fuzzy-match what a collector *said* to a known location.

Speech-to-text may return English, Hinglish or Devanagari ("राजेंद्र भवन के पीछे"), so we match
against the name plus every alias and return close alternatives when unsure, so the voice agent can ask
"Rajendra Bhawan ya Rajiv Bhawan?".
"""
from rapidfuzz import fuzz, process

from .models import Location

MATCH_THRESHOLD = 70
STOP_WORDS = {"ke", "ka", "ki", "peeche", "piche", "wala", "wali", "bin", "dustbin", "paas", "saamne",
              "के", "का", "की", "पीछे", "वाला", "वाली", "पास", "सामने", "डस्टबिन"}


def _clean(text: str) -> str:
    return " ".join(w for w in text.lower().replace(",", " ").split() if w not in STOP_WORDS)


def match_location(spoken: str, locations: list[Location]) -> tuple[Location | None, list[str]]:
    if not spoken:
        return None, []
    choices: dict[str, Location] = {}
    for loc in locations:
        choices[loc.name.lower()] = loc
        for a in loc.aliases or []:
            choices[a.lower()] = loc
    query = _clean(spoken) or spoken.lower()
    results = process.extract(query, list(choices.keys()), scorer=fuzz.WRatio, limit=5)
    seen, alternatives = set(), []
    for key, score, _ in results:
        loc = choices[key]
        if loc.id not in seen:
            seen.add(loc.id)
            alternatives.append((loc, score))
    if not alternatives:
        return None, []
    best, best_score = alternatives[0]
    names = [l.name for l, _ in alternatives[:3]]
    # Confident only if above threshold and clearly ahead of the runner-up
    runner_up = alternatives[1][1] if len(alternatives) > 1 else 0
    if best_score >= MATCH_THRESHOLD and best_score - runner_up >= 5:
        return best, names
    return None, names
