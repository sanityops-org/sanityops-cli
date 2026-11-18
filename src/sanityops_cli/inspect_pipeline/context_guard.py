"""Limit each model request independently of the Agent's cumulative usage."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from sanityops_agent.core.context import AgentContext, CompactConfig
from sanityops_agent.core.message import Message, StreamChunk, ToolDefinition, ToolUseBlock
from sanityops_agent.llm.base import LLMProvider, LLMResponse
from sanityops_agent.llm.exceptions import ContextWindowExceededError, LLMError

from sanityops_cli.inspect_pipeline.token_estimator import (
    DEFAULT_CONTEXT_WINDOW,
    estimate_tokens,
    usage_breakdown,
)

logger = logging.getLogger(__name__)


class ArtifactAwareContext(AgentContext):
    """Estimate request size for the SDK compaction trigger and input limit."""

    def __init__(self, context_window: int = DEFAULT_CONTEXT_WINDOW) -> None:
        super().__init__(
            compact_config=CompactConfig(trigger_token_threshold=max(1, context_window * 4 // 5))
        )
        self.context_window = context_window
        self.tool_schema_tokens = 0
        self._tool_input_sizes: dict[tuple[str, int], int] = {}

    def estimate_tokens(self) -> int:
        return self.estimate_request(self.messages)

    def estimate_request(self, messages: list[Message]) -> int:
        tokens = self.tool_schema_tokens
        for message in messages:
            tokens += 4  # approximate message framing
            for block in message.content:
                tokens += 4  # approximate content block framing
                for field in (
                    "text",
                    "thinking",
                    "tool_result_content",
                    "tool_call_id",
                    "tool_name",
                ):
                    tokens += estimate_tokens(getattr(block, field, "") or "")
                if isinstance(block, ToolUseBlock):
                    key = (block.tool_call_id, id(block.tool_input))
                    size = self._tool_input_sizes.get(key)
                    if size is None:
                        size = _estimate_json(block.tool_input)
                        self._tool_input_sizes[key] = size
                    tokens += size
        return tokens


def _estimate_json(value: object) -> int:
    return estimate_tokens(json.dumps(value, ensure_ascii=False, default=str))


def _can_fallback_from_extra_body(provider: Any, exc: LLMError, kwargs: dict[str, Any]) -> bool:
    return type(exc) is LLMError and bool(
        getattr(provider, "extra_body", None) or kwargs.get("extra_body")
    )


async def _create_with_extra_body_fallback(
    provider: Any,
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    **kwargs: Any,
) -> LLMResponse:
    try:
        return await provider.create(messages, tools=tools, **kwargs)
    except LLMError as exc:
        if not _can_fallback_from_extra_body(provider, exc, kwargs):
            raise
        logger.warning(
            "Provider rejected extra_body (%s); dropping extra_body and retrying.",
            exc,
        )
        has_attr = hasattr(provider, "extra_body")
        original_extra_body = getattr(provider, "extra_body", None)
        if has_attr:
            provider.extra_body = None
        retry_kwargs = dict(kwargs)
        retry_kwargs.pop("extra_body", None)
        try:
            return await provider.create(messages, tools=tools, **retry_kwargs)
        except Exception:
            if has_attr:
                provider.extra_body = original_extra_body
            raise


async def _stream_with_extra_body_fallback(
    provider: Any,
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    **kwargs: Any,
) -> AsyncIterator[StreamChunk]:
    yielded = False
    try:
        async for chunk in provider.stream(messages, tools=tools, **kwargs):
            yielded = True
            yield chunk
        return
    except LLMError as exc:
        if yielded or not _can_fallback_from_extra_body(provider, exc, kwargs):
            raise
        logger.warning(
            "Provider rejected extra_body (%s); dropping extra_body and retrying stream.",
            exc,
        )
        has_attr = hasattr(provider, "extra_body")
        original_extra_body = getattr(provider, "extra_body", None)
        if has_attr:
            provider.extra_body = None
        retry_kwargs = dict(kwargs)
        retry_kwargs.pop("extra_body", None)
        retry_yielded = False
        try:
            async for chunk in provider.stream(messages, tools=tools, **retry_kwargs):
                retry_yielded = True
                yield chunk
        except Exception:
            if has_attr and not retry_yielded:
                provider.extra_body = original_extra_body
            raise


class _DelegatingLLMProvider(LLMProvider):
    """Base wrapper delegating connection metadata and ``extra_body`` to an inner provider."""

    def __init__(self, provider: LLMProvider) -> None:
        # LLMProvider is an ABC without its own __init__ and does not declare
        # connection metadata, so delegate it only when the wrapped provider
        # exposes it (test doubles legitimately do not).
        self.api_key = getattr(provider, "api_key", None)
        self.base_url = getattr(provider, "base_url", None)
        self.model = getattr(provider, "model", None)
        self._provider = provider

    @property
    def extra_body(self) -> Any:
        return getattr(self._provider, "extra_body", None)

    @extra_body.setter
    def extra_body(self, value: Any) -> None:
        inner: Any = self._provider
        inner.extra_body = value

    async def close(self) -> None:
        await self._provider.close()


class ExtraBodyFallbackProvider(_DelegatingLLMProvider):
    """Retry once without ``extra_body`` if the endpoint rejects it with ``LLMError``."""

    async def create(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs
    ) -> LLMResponse:
        return await _create_with_extra_body_fallback(
            self._provider, messages, tools=tools, **kwargs
        )

    async def stream(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        async for chunk in _stream_with_extra_body_fallback(
            self._provider, messages, tools=tools, **kwargs
        ):
            yield chunk


class ContextLimitedProvider(_DelegatingLLMProvider):
    """Guard SDK requests and supply the total used by its cumulative budget."""

    def __init__(self, provider: LLMProvider, context: ArtifactAwareContext) -> None:
        super().__init__(provider)
        self._context = context

    async def _check_input(
        self, messages: list[Message], tools: list[ToolDefinition] | None
    ) -> None:
        context = self._context
        context.tool_schema_tokens = (
            _estimate_json([asdict(tool) for tool in tools]) if tools else 0
        )
        estimated = context.estimate_request(messages)
        if estimated <= context.context_window:
            return
        # The SDK also compacts after executing tools. Check again here so
        # the initial request and turns without tools are covered as well.
        if messages is context.messages:
            await context.compact_if_needed()
            estimated = context.estimate_tokens()
        if estimated > context.context_window:
            raise ContextWindowExceededError(
                f"Estimated model input of {estimated:,} tokens exceeds "
                f"context_window={context.context_window:,} after SDK compaction."
            )

    async def create(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs
    ) -> LLMResponse:
        await self._check_input(messages, tools)
        if isinstance(self._provider, ExtraBodyFallbackProvider):
            response = await self._provider.create(messages, tools=tools, **kwargs)
        else:
            response = await _create_with_extra_body_fallback(
                self._provider, messages, tools=tools, **kwargs
            )
        if response.usage and not response.usage.get("total_tokens"):
            response.usage = {
                **response.usage,
                "total_tokens": usage_breakdown(response.usage)["total"],
            }
        return response

    async def stream(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        await self._check_input(messages, tools)
        if isinstance(self._provider, ExtraBodyFallbackProvider):
            async for chunk in self._provider.stream(messages, tools=tools, **kwargs):
                yield chunk
        else:
            async for chunk in _stream_with_extra_body_fallback(
                self._provider, messages, tools=tools, **kwargs
            ):
                yield chunk
