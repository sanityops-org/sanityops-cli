"""Unit tests for ProgressHook logging integration."""

import io
from types import SimpleNamespace

import pytest
from rich.console import Console

from sanityops_cli.agents.scanner_agent.hooks.progress_hook import ProgressHook


class _FakeEvents:
    BEFORE_LOOP = "before_loop"
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"
    BEFORE_TOOL_EXEC = "before_tool_exec"
    AFTER_TOOL_EXEC = "after_tool_exec"
    ON_TERMINATION = "on_termination"


class _FakeLogger:
    def __init__(self):
        self.debug_calls: list[str] = []
        self.error_calls: list[str] = []

    def debug(self, message: str) -> None:
        self.debug_calls.append(message)

    def error(self, message: str) -> None:
        self.error_calls.append(message)


def _make_hook(logger):
    console = Console(record=True, file=io.StringIO())
    hook = ProgressHook(console=console, verbose=False, logger=logger)
    hook._get_events = lambda: _FakeEvents()  # type: ignore[method-assign]
    return hook, console


def _ctx(event, data=None, is_error=False):
    return SimpleNamespace(event=event, data=data or {}, is_error=is_error)


class TestProgressHookLogging:
    @pytest.mark.anyio
    async def test_before_llm_call_logs_debug(self):
        logger = _FakeLogger()
        hook, _ = _make_hook(logger)
        await hook.handle(_ctx("before_llm_call", {"iteration": 0}))
        assert any("LLM call" in m for m in logger.debug_calls)

    @pytest.mark.anyio
    async def test_task_completion_logs_plain_text(self):
        logger = _FakeLogger()
        hook, _ = _make_hook(logger)
        await hook.handle(
            _ctx("before_tool_exec", {"tool_name": "task", "tool_input": {"goal": "g"}})
        )
        await hook.handle(_ctx("after_tool_exec", {"tool_name": "task"}, is_error=False))
        assert any(m == "✓ Sub Agent completed" for m in logger.debug_calls)

    @pytest.mark.anyio
    async def test_task_failure_logs_error(self):
        logger = _FakeLogger()
        hook, _ = _make_hook(logger)
        await hook.handle(_ctx("after_tool_exec", {"tool_name": "task"}, is_error=True))
        assert any("Sub Agent failed" in m for m in logger.error_calls)

    @pytest.mark.anyio
    async def test_no_logger_does_not_crash(self):
        hook, console = _make_hook(None)
        await hook.handle(_ctx("before_llm_call", {"iteration": 0}))
        await hook.handle(_ctx("after_tool_exec", {"tool_name": "task"}, is_error=True))
        # console output still appears without a logger
        assert "LLM call" in console.export_text()
