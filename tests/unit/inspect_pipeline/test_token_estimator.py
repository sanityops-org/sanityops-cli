"""Tests for CJK-aware token estimation (design §6.6)."""

from __future__ import annotations

from sanityops_cli.inspect_pipeline.token_estimator import (
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
