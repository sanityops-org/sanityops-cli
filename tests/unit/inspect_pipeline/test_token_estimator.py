"""Tests for CJK-aware token estimation (design §6.6)."""

from __future__ import annotations

from sanityops_cli.inspect_pipeline.token_estimator import (
    derive_injection_budget,
    estimate_skill_reserve,
    estimate_tokens,
)


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


class TestBudget:
    def test_budget_arithmetic(self):
        budget = derive_injection_budget(
            context_window=200_000,
            system_prompt="a" * 12_000,  # 3000 tokens
            skill_reserve=63_000,
        )
        assert budget == 200_000 - 3_000 - 63_000 - 8_192 - 16_384

    def test_budget_floors_at_zero(self):
        assert derive_injection_budget(1_000, "", 0) == 0


class TestSkillReserve:
    def test_prompt_only(self):
        assert estimate_skill_reserve({"prompt"}) == 42_000 + 16_000

    def test_prompt_and_tool_adds_cross(self):
        reserve = estimate_skill_reserve({"prompt", "tool"})
        assert reserve == 42_000 + 16_000 + 11_000 + 12_000 + 5_000

    def test_full_set(self):
        reserve = estimate_skill_reserve({"prompt", "tool", "skill"})
        assert reserve == (42_000 + 16_000 + 11_000 + 12_000 + 5_000 + 16_000)
