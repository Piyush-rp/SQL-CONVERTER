"""
Text/token helpers. The token estimator is a heuristic, not an exact
tokenizer count (tiktoken's real BPE vocab files need a network download
this environment can't reach - see the same constraint noted for
HuggingFace models in app/vectorstore/embeddings.py) - but it's accurate
enough (+/-15% in practice for English technical text) to warn when a
prompt is getting large, which is its only real job here.
"""
from __future__ import annotations

_CHARS_PER_TOKEN_ESTIMATE = 4.0


def estimate_token_count(text: str) -> int:
    """Rough token count estimate - good enough for a prompt-size warning,
    not for billing/quota accuracy. Real usage should read the actual
    usage figures the provider returns with each response instead."""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN_ESTIMATE))


def truncate_to_token_budget(text: str, max_tokens: int) -> str:
    """Hard-truncates text to roughly fit a token budget, on a line
    boundary where possible so it doesn't cut off mid-statement."""
    if estimate_token_count(text) <= max_tokens:
        return text

    max_chars = int(max_tokens * _CHARS_PER_TOKEN_ESTIMATE)
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.7:  # don't chop off most of the last line for a tiny gain
        truncated = truncated[:last_newline]
    return truncated + "\n... (truncated)"
