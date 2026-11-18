"""Estimate input size locally and normalize the provider's reported usage."""

from __future__ import annotations

import unicodedata

DEFAULT_CONTEXT_WINDOW = 200_000


def _is_cjk(char: str) -> bool:
    return unicodedata.east_asian_width(char) in ("F", "W")


def estimate_tokens(text: str) -> int:
    """CJK chars ≈ 1 token; everything else ≈ chars/4."""
    if not text:
        return 0
    cjk = sum(1 for char in text if _is_cjk(char))
    other = len(text) - cjk
    return cjk + other // 4


def usage_breakdown(usage) -> dict[str, int]:
    """Use the provider's total when available, deriving it for Anthropic."""

    def value(key: str) -> int:
        raw = usage.get(key, 0) if isinstance(usage, dict) else getattr(usage, key, 0)
        return int(raw or 0)

    inp = value("input_tokens") or value("prompt_tokens")
    out = value("output_tokens") or value("completion_tokens")
    cache = value("cache_read_input_tokens") + value("cache_creation_input_tokens")
    total = value("total_tokens") or (inp + out + cache)
    return {"input": inp, "output": out, "cache": cache, "total": total}
