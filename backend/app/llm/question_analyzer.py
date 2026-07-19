"""
Lightweight, model-free pre-checks on the raw question before spending an
LLM call. Catches empty/trivially-non-data questions early and gives the
workflow a heuristic signal for whether the question likely needs
aggregation (affects how much schema context / which few-shot examples to
include).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_AGGREGATE_HINTS = {
    "how many", "count", "total", "sum", "average", "avg", "max", "min",
    "top", "highest", "lowest", "most", "least", "group", "per",
}

_GREETING_ONLY = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay"}


@dataclass
class QuestionAnalysis:
    is_empty: bool
    is_greeting_only: bool
    likely_aggregate: bool
    word_count: int


class QuestionAnalyzer:
    @staticmethod
    def analyze(question: str) -> QuestionAnalysis:
        cleaned = question.strip().lower()
        words = re.findall(r"[a-zA-Z']+", cleaned)

        return QuestionAnalysis(
            is_empty=len(cleaned) == 0,
            is_greeting_only=cleaned.rstrip("!.? ") in _GREETING_ONLY,
            likely_aggregate=any(hint in cleaned for hint in _AGGREGATE_HINTS),
            word_count=len(words),
        )
