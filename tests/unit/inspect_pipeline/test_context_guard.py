"""Tests for the request-side context guard and the extra_body fallback retry."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from sanityops_agent.core.message import (
    ContentType,
    FinishReason,
    Message,
    Role,
    StreamChunk,
    TextBlock,
)
from sanityops_agent.llm.base import LLMProvider, LLMResponse
from sanityops_agent.llm.exceptions import AuthenticationError, LLMError

from sanityops_cli.inspect_pipeline.context_guard import (
    ArtifactAwareContext,
    ContextLimitedProvider,
    ExtraBodyFallbackProvider,
)


class RejectExtraBodyProvider(LLMProvider):
    """Reject requests that carry ``extra_body``, mimicking a picky gateway."""

    def __init__(self, *, extra_body: dict | None = None, always_fail: bool = False):
        # LLMProvider is an ABC without its own __init__, so set attributes directly
        self.api_key = "k"
        self.base_url = None
        self.model = "m"
        self.extra_body = extra_body
        self.always_fail = always_fail
        self.calls: list[dict | None] = []

    async def create(self, messages, tools=None, **kwargs):
        self.calls.append(self.extra_body)
        if self.always_fail or self.extra_body:
            raise LLMError("extra_body parameter is not supported")
        return LLMResponse(
            content=[TextBlock(text="ok")],
            stop_reason=FinishReason.END_TURN,
            model=self.model,
            provider="test",
        )

    async def stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError

    async def close(self):
        return None


class StreamRejectProvider(LLMProvider):
    """Reject the first stream attempt when ``extra_body`` is set."""

    def __init__(self, *, extra_body: dict | None = None):
        self.api_key = "k"
        self.base_url = None
        self.model = "m"
        self.extra_body = extra_body
        self.stream_calls: list[dict | None] = []

    async def create(self, messages, tools=None, **kwargs):
        raise NotImplementedError

    async def stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        self.stream_calls.append(self.extra_body)
        if self.extra_body:
            raise LLMError("extra_body parameter is not supported")
        yield StreamChunk(type=ContentType.TEXT, delta="ok")

    async def close(self):
        return None


INITIAL_EXTRA = {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}


async def _two_creates(guarded) -> tuple[LLMResponse, LLMResponse]:
    msgs = [Message.from_text(Role.USER, "hello")]
    return await guarded.create(msgs), await guarded.create(msgs)


def test_fallback_provider_drops_extra_body_then_reuses_the_plain_provider():
    inner = RejectExtraBodyProvider(extra_body=dict(INITIAL_EXTRA))
    wrapped = ContextLimitedProvider(ExtraBodyFallbackProvider(inner), ArtifactAwareContext(10_000))

    res1, res2 = asyncio.run(_two_creates(wrapped))

    assert res1.content[0].text == "ok"
    assert res2.content[0].text == "ok"
    assert inner.calls == [INITIAL_EXTRA, None, None]
    assert inner.extra_body is None


def test_context_limited_provider_also_falls_back_when_wrapping_directly():
    inner = RejectExtraBodyProvider(extra_body=dict(INITIAL_EXTRA))
    direct = ContextLimitedProvider(inner, ArtifactAwareContext(10_000))

    res1, res2 = asyncio.run(_two_creates(direct))

    assert res1.content[0].text == "ok"
    assert res2.content[0].text == "ok"
    assert inner.calls == [INITIAL_EXTRA, None, None]
    assert inner.extra_body is None


def test_persistent_failure_restores_extra_body():
    failing = RejectExtraBodyProvider(extra_body=dict(INITIAL_EXTRA), always_fail=True)
    guarded = ExtraBodyFallbackProvider(failing)

    with pytest.raises(LLMError, match="not supported"):
        asyncio.run(guarded.create([Message.from_text(Role.USER, "hello")]))

    assert failing.calls == [INITIAL_EXTRA, None]
    assert failing.extra_body == INITIAL_EXTRA


def test_authentication_error_is_never_retried_as_extra_body_fallback():
    class AuthFailProvider(RejectExtraBodyProvider):
        async def create(self, messages, tools=None, **kwargs):
            self.calls.append(self.extra_body)
            raise AuthenticationError("invalid key")

    auth_fail = AuthFailProvider(extra_body=dict(INITIAL_EXTRA))
    guarded = ContextLimitedProvider(
        ExtraBodyFallbackProvider(auth_fail), ArtifactAwareContext(10_000)
    )

    with pytest.raises(AuthenticationError):
        asyncio.run(guarded.create([Message.from_text(Role.USER, "hello")]))

    assert auth_fail.calls == [INITIAL_EXTRA]


def test_stream_fallback_drops_extra_body_before_the_first_chunk():
    inner = StreamRejectProvider(extra_body=dict(INITIAL_EXTRA))
    wrapper = ExtraBodyFallbackProvider(inner)

    async def _collect() -> list[StreamChunk]:
        return [chunk async for chunk in wrapper.stream([Message.from_text(Role.USER, "hello")])]

    chunks = asyncio.run(_collect())

    assert [c.delta for c in chunks] == ["ok"]
    assert inner.stream_calls == [INITIAL_EXTRA, None]
    assert inner.extra_body is None
