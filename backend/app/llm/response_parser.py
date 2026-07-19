"""Extracts SQL (and the CANNOT_ANSWER escape hatch) from raw LLM text."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ANY_FENCE_RE = re.compile(r"```\s*(.*?)```", re.DOTALL)
_CANNOT_ANSWER_RE = re.compile(r"CANNOT_ANSWER:\s*(.+)", re.IGNORECASE)


@dataclass
class ParsedLLMResponse:
    sql: Optional[str]
    cannot_answer_reason: Optional[str]
    raw_text: str


class ResponseParser:
    @staticmethod
    def parse(raw_text: str) -> ParsedLLMResponse:
        cannot_match = _CANNOT_ANSWER_RE.search(raw_text)
        if cannot_match and not _SQL_FENCE_RE.search(raw_text):
            return ParsedLLMResponse(sql=None, cannot_answer_reason=cannot_match.group(1).strip(), raw_text=raw_text)

        fence_match = _SQL_FENCE_RE.search(raw_text) or _ANY_FENCE_RE.search(raw_text)
        if fence_match:
            sql = fence_match.group(1).strip()
            return ParsedLLMResponse(sql=sql, cannot_answer_reason=None, raw_text=raw_text)

        # No fence at all - treat the whole trimmed response as SQL if it looks
        # like one (starts with SELECT/WITH), otherwise surface as unanswerable.
        stripped = raw_text.strip()
        if re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
            return ParsedLLMResponse(sql=stripped, cannot_answer_reason=None, raw_text=raw_text)

        return ParsedLLMResponse(sql=None, cannot_answer_reason="Model did not return a recognizable SQL query", raw_text=raw_text)
