"""Tests for CJK-aware token estimation (design §6.6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sanityops_cli.inspect_pipeline.token_estimator import (
    estimate_skill_reserve,
    estimate_tokens,
)

SKILLS = Path(__file__).resolve().parents[3] / "src" / "sanityops_cli" / "skills"
INSPECT = SKILLS / "sanityops-inspect-only"
_ALWAYS = (
    "SKILL.md",
    "references/_meta.md",
    "references/permission-checklist.v2.md",
    "references/explicit-checklist.v2.md",
    "references/relevance-map.v2.md",
    "references/code-contract-checklist.v2.md",
)
_BY_TYPE = {
    "prompt": "references/prompt-checklist.v2.md",
    "tool": "references/tool-checklist.v2.md",
    "skill": "references/skill-checklist.v2.md",
}


class TestEstimateTokens:
    def test_ascii_chars_per_4(self):
        assert estimate_tokens("a" * 40) == 10

    def test_cjk_char_is_one_token(self):
        assert estimate_tokens("测" * 10) == 10

    def test_mixed(self):
        # 20 CJK + 40 ASCII → 20 + 10 = 30 (chars/4 alone would say 15)
        text = "测" * 20 + "a" * 40
        assert estimate_tokens(text) == 30

    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_cjk_not_underestimated_like_framework(self):
        text = "这是一个中文系统提示词，包含很多汉字。" * 10
        assert estimate_tokens(text) > len(text) // 4


def _measured_load(types: set[str]) -> int:
    paths = list(_ALWAYS) + [_BY_TYPE[t] for t in sorted(types) if t in _BY_TYPE]
    if len(types & {"prompt", "tool", "skill"}) >= 2:
        paths.append("references/cross-checklist.v2.md")
    return sum(estimate_tokens((INSPECT / p).read_text(encoding="utf-8")) for p in paths)


@pytest.mark.parametrize(
    "types",
    [set(), {"prompt"}, {"tool"}, {"skill"}, {"prompt", "tool"}, {"prompt", "skill", "tool"}],
)
def test_reserve_covers_measured_reference_loads(types):
    """When the vendored files change, update ``estimate_skill_reserve`` too."""
    assert estimate_skill_reserve(types) >= _measured_load(types)
