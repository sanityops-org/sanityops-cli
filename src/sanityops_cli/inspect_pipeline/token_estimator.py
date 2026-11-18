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


def derive_injection_budget(
    context_window: int,
    system_prompt: str,
    skill_reserve: int,
    output_reserve: int = 8192,
    work_margin: int = 16384,
) -> int:
    """Tokens available for the injected payload (task message).

    skill_reserve: expected lazy skill loads for this run (design §6.6 table);
    the caller estimates it from the artifact-type combination.
    """
    return max(
        0,
        context_window
        - estimate_tokens(system_prompt)
        - skill_reserve
        - output_reserve
        - work_margin,
    )


def estimate_skill_reserve(artifact_types: set[str]) -> int:
    """Expected lazy-load reserve per the §6.6 table (approximate, CJK-aware).

    Only the SKILL.md (~42k) plus the domain checklists the artifact
    combination requires. Values measured on the vendored skill.
    """
    reserve = 42_000  # SKILL.md
    if "prompt" in artifact_types:
        reserve += 16_000  # prompt-checklist
    if "tool" in artifact_types:
        reserve += 11_000  # tool-checklist
    if len(artifact_types & {"prompt", "skill", "tool"}) >= 2:
        reserve += 12_000  # cross-checklist
        reserve += 5_000  # _meta guidance
    if "skill" in artifact_types:
        reserve += 16_000  # skill-checklist
    return reserve


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
