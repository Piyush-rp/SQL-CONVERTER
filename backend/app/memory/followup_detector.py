"""
Lightweight, model-free heuristic for whether a question is likely a
follow-up to the previous turn ("and by region?", "now just last month",
"what about product B") versus a fresh, self-contained question. This
decides whether prior-turn context is worth spending prompt tokens on -
it's a cheap filter, not a hard gate: conversation memory is passed
whenever turns exist and the question is short enough that context
plausibly matters, but the LLM (via the prompt) always has the final say
on whether to use it.
"""
from __future__ import annotations

import re

_FOLLOWUP_STARTERS = (
    "and ", "what about", "how about", "now ", "instead", "also ",
    "just ", "only ", "same but", "same, but", "again but",
)

_PRONOUN_REFERENCE_RE = re.compile(
    r"\b(it|that|those|these|this|them)\b", re.IGNORECASE
)


def is_likely_followup(question: str, has_prior_turns: bool) -> bool:
    if not has_prior_turns:
        return False

    cleaned = question.strip().lower()
    if not cleaned:
        return False

    if any(cleaned.startswith(starter) for starter in _FOLLOWUP_STARTERS):
        return True

    if _PRONOUN_REFERENCE_RE.search(cleaned):
        return True

    # Short questions with no explicit subject are often follow-ups ("by
    # region?", "top 5 instead") - longer questions are more likely
    # self-contained even right after a prior turn.
    word_count = len(cleaned.split())
    if word_count <= 4:
        return True

    return False
