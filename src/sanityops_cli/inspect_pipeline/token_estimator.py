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

    Always loaded for any artifact set: the inspect SKILL.md, ``_meta``, and
    the permission / explicit / relevance-map / code-contract checklists. The
    per-type checklists and the cross checklist follow the set composition.
    Values are measured on the vendored v2 skill plus a safety margin;
    ``test_reserve_covers_measured_reference_loads`` keeps them above the
    measured file sizes. Update the constants whenever the vendored references
    change: the guard only proves coverage of the files present at test time.
    """
    # An empty artifact set still loads the always-required references below.
    reserve = 18_000  # inspect SKILL.md
    reserve += 3_000  # _meta (shared definitions)
    reserve += 11_000  # permission-checklist (Stage D)
    reserve += 5_000  # explicit-checklist (Stage E)
    reserve += 9_000  # relevance-map (Stage F)
    reserve += 3_000  # code-contract-checklist (Stage A QC)
    if "prompt" in artifact_types:
        reserve += 5_500  # prompt-checklist
    if "tool" in artifact_types:
        reserve += 4_000  # tool-checklist
    if "skill" in artifact_types:
        reserve += 4_500  # skill-checklist
    if len(artifact_types & {"prompt", "skill", "tool"}) >= 2:
        reserve += 4_500  # cross-checklist
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
