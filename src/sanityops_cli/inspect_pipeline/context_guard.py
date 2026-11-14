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


class ContextLimitedProvider(LLMProvider):
    """Guard SDK requests and supply the total used by its cumulative budget."""

    def __init__(self, provider: LLMProvider, context: ArtifactAwareContext) -> None:
        super().__init__(api_key=provider.api_key, base_url=provider.base_url, model=provider.model)
        self._provider = provider
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

    def _can_fallback_from_disable_thinking(self, exc: LLMError) -> bool:
        return type(exc) is LLMError and getattr(self._provider, "enable_thinking", True) is False

    async def create(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs
    ) -> LLMResponse:
        await self._check_input(messages, tools)
        try:
            response = await self._provider.create(messages, tools=tools, **kwargs)
        except LLMError as exc:
            if not self._can_fallback_from_disable_thinking(exc):
                raise
            logger.warning(
                "Provider rejected disable-thinking request (%s); retrying with default thinking.",
                exc,
            )
            provider: Any = self._provider
            provider.enable_thinking = True
            try:
                response = await self._provider.create(messages, tools=tools, **kwargs)
            except Exception:
                provider.enable_thinking = False
                raise
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
        async for chunk in self._provider.stream(messages, tools=tools, **kwargs):
            yield chunk

    async def close(self) -> None:
        await self._provider.close()
