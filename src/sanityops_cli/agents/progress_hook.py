"""Progress hook with logging support.

Extends the original ProgressHook to also write to LogManager,
providing both console output and persistent log files.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.text import Text

from deeplogic_cli.inspect_pipeline.token_estimator import usage_breakdown

if TYPE_CHECKING:
    from deeplogic_cli.logging import LogManager

LLM_WAIT_UPDATE_SECONDS = 30


class LoggingProgressHook:
    """Hook to report agent progress to console and log manager."""

    def __init__(
        self,
        console: Console,
        log_manager: LogManager | None = None,
        verbose: bool = True,
        token_budget: int | None = None,
        stage: str | None = None,
    ):
        """Initialize the hook.

        Args:
            console: Rich console for terminal output.
            log_manager: Optional LogManager for file logging.
            verbose: Whether to output to console.
        """
        self.console = console
        self.log_manager = log_manager
        self.verbose = verbose
        self.stage = stage
        self._iteration = 0
        self._tool_calls = 0
        self._sub_agent_count = 0
        self.token_budget = token_budget
        self._tokens_used = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_tokens = 0
        self._started = False
        self._llm_started_at: float | None = None
        self._llm_wait_task: asyncio.Task[None] | None = None
        self._events = None

        self._active_tools: dict[str, tuple[float, dict[str, Any]]] = {}

    def _get_events(self):
        """Lazy import of HookEvent."""
        if self._events is None:
            from aidynamic_agent.hooks.base import HookEvent

            self._events = HookEvent
        return self._events

    @property
    def tokens_used(self) -> int:
        """Cumulative tokens (input + output) across all LLM calls so far."""
        return self._tokens_used

    @property
    def name(self) -> str:
        return "logging_progress"

    @property
    def description(self) -> str:
        return "Reports agent progress to console and log"

    @property
    def priority(self) -> int:
        return 5

    @property
    def events(self) -> list:
        """Return events this hook subscribes to."""
        events = self._get_events()
        return [
            events.BEFORE_LOOP,
            events.BEFORE_LLM_CALL,
            events.AFTER_LLM_CALL,
            events.BEFORE_TOOL_EXEC,
            events.AFTER_TOOL_EXEC,
            events.ON_TERMINATION,
        ]

    def can_handle(self, event) -> bool:
        """Whether this hook handles the given event."""
        return event in self.events

    async def handle(self, ctx):
        """Handle hook event and output progress."""
        event = ctx.event
        data = ctx.data

        events = self._get_events()

        if event == events.BEFORE_LOOP:
            self._iteration = data.get("iteration", 0)
            self._on_loop_start()

        elif event == events.BEFORE_LLM_CALL:
            iteration = data.get("iteration", self._iteration)
            self._iteration = iteration
            self._on_loop_start()
            self.stop_waiting()
            self._llm_started_at = perf_counter()
            self._log_llm_start(iteration)
            if self.verbose and self.stage:
                self._llm_wait_task = asyncio.create_task(self._show_llm_wait(iteration))

        elif event == events.AFTER_LLM_CALL:
            self.stop_waiting()
            response = data.get("response")
            if response and hasattr(response, "usage"):
                usage = response.usage
                if usage:
                    breakdown = self._usage_breakdown(usage)
                    self._input_tokens += breakdown["input"]
                    self._output_tokens += breakdown["output"]
                    self._cache_tokens += breakdown["cache"]
                    self._tokens_used += breakdown["total"]
                    elapsed = self._llm_elapsed()
                    self._log_llm_complete(breakdown, elapsed)

        elif event == events.BEFORE_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            tool_input = self._obj(data.get("tool_input"))
            self._tool_calls += 1
            call_id = data.get("tool_call_id") or tool_name
            self._active_tools[call_id] = (perf_counter(), tool_input)
            self._log_tool_start(tool_name, tool_input)

        elif event == events.AFTER_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            call_id = data.get("tool_call_id") or tool_name
            started_at, tool_input = self._active_tools.pop(call_id, (perf_counter(), {}))
            duration_ms = (perf_counter() - started_at) * 1000
            is_error = ctx.is_error or data.get("success") is False
            if self.log_manager:
                self.log_manager.log_tool_call(
                    tool_name,
                    {"detail": self._tool_detail(tool_name, tool_input)},
                    "rejected" if is_error else "accepted",
                    duration_ms,
                )
            self._log_tool_complete(
                tool_name, tool_input, data.get("result"), is_error, duration_ms
            )

        elif event == events.ON_TERMINATION:
            self.stop_waiting()
            reason = data.get("reason", "unknown")
            self._log_termination(reason)

        return ctx

    def _on_loop_start(self) -> None:
        """Ensure Agent start message is printed once."""
        if not self._started:
            if self.log_manager:
                self.log_manager.info("agent", "Agent started")
            if self.verbose:
                self.console.print("[bold cyan]▶ Agent started[/]")
            self._started = True

    def _log_llm_start(self, iteration: int) -> None:
        """Log LLM call start."""
        if self.log_manager:
            self.log_manager.debug("llm", "LLM call started", iteration=iteration + 1)
        if self.verbose:
            prefix = f"{self.stage} · " if self.stage else ""
            self.console.print(f"  [dim]⟳ {prefix}LLM call (iteration {iteration + 1})[/]")

    async def _show_llm_wait(self, iteration: int) -> None:
        while True:
            await asyncio.sleep(LLM_WAIT_UPDATE_SECONDS)
            self.console.print(
                f"  [dim]⟳ {self.stage} · iteration {iteration + 1} · "
                f"waiting for LLM ({self._llm_elapsed():.0f}s)[/]"
            )

    def stop_waiting(self) -> None:
        if self._llm_wait_task is not None:
            self._llm_wait_task.cancel()
            self._llm_wait_task = None

    def _log_llm_complete(self, usage: dict[str, int], elapsed: float) -> None:
        """Log one LLM response: per-call in/out/cache and the context size."""
        ctx = usage["input"] + usage["cache"]
        if self.log_manager:
            self.log_manager.debug(
                "llm",
                "LLM call completed",
                tokens=usage["total"],
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                cache_tokens=usage["cache"],
                context_tokens=ctx,
                duration_seconds=round(elapsed, 2),
            )
        if self.verbose:
            cache = f" · cache {usage['cache']:,}" if usage["cache"] else ""
            self.console.print(
                f"  [dim]↓ response  in {usage['input']:,} · out {usage['output']:,}"
                f"{cache}  ({elapsed:.1f}s)  ctx {self._compact(ctx)}[/]"
            )

    @staticmethod
    def _compact(value: int) -> str:
        return f"{value / 1000:.1f}k" if value >= 1000 else str(value)

    def _log_tool_start(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        """Log tool execution start."""
        if tool_name == "task":
            goal = tool_input.get("goal", "unknown")[:50]
            self._sub_agent_count += 1
            if self.log_manager:
                self.log_manager.info(
                    "agent",
                    "Sub-agent started",
                    goal=goal,
                    sub_agent_id=self._sub_agent_count,
                )
            if self.verbose:
                self.console.print(
                    f"  [bold yellow]◇ Starting sub Agent #{self._sub_agent_count}[/]: {goal}..."
                )
        elif self.verbose and tool_name != "write_report":
            detail = self._tool_detail(tool_name, tool_input)
            suffix = f": {detail}" if detail else ""
            self.console.print(Text.assemble(("  ⚡ " + tool_name, "green"), suffix))

    def _log_tool_complete(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: Any,
        is_error: bool,
        duration_ms: float,
    ) -> None:
        """Log tool execution completion."""
        if tool_name == "store_artifacts" and tool_input.get("operation") == "add_artifact":
            self._log_artifact_submission(tool_input, result, is_error, duration_ms)
            return
        if tool_name == "write_report":
            payload = self._obj(result)
            section = payload.get("section") or tool_input.get("section", "")
            label = f"Stage {section}" if section in tuple("ABCDEFG") else section
            if not is_error and isinstance(payload.get("part"), int):
                action = "replaced" if payload.get("action") == "replaced" else "recorded"
                message = f"{label} part {payload['part']} {action}"
                if payload.get("recovered") is True:
                    message += " after resubmission"
                if self.log_manager:
                    self.log_manager.info("report", message)
                if self.verbose:
                    self.console.print(Text(f"  ✓ {message}", style="green"))
                return
            if is_error and payload.get("error"):
                if self.log_manager:
                    self.log_manager.warning("report", f"{label} part rejected", detail=result)
                if self.verbose:
                    message = f"{label} part rejected · {payload['error']}"
                    self.console.print(Text(f"  ⚠ {message}", style="yellow"))
                return
        if tool_name == "task":
            if is_error:
                if self.log_manager:
                    self.log_manager.error("agent", "Sub-agent failed")
                if self.verbose:
                    self.console.print("  [red]✗ Sub Agent failed[/]")
            else:
                if self.log_manager:
                    self.log_manager.info("agent", "Sub-agent completed")
                if self.verbose:
                    self.console.print("  [green]✓ Sub Agent completed[/]")
        elif is_error:
            detail = f": {result}" if result else ""
            if self.log_manager:
                self.log_manager.error(
                    "tool", f"{tool_name} failed{detail}", duration=f"{duration_ms:.0f}ms"
                )
            if self.verbose:
                self.console.print(Text(f"  ✗ {tool_name} failed{detail}", style="red"))

    def _log_artifact_submission(
        self, tool_input: dict[str, Any], result: Any, is_error: bool, duration_ms: float
    ) -> None:
        artifact = self._obj(tool_input.get("artifact"))
        key = f"{artifact.get('type') or 'artifact'}/{artifact.get('name') or 'unknown'}"
        seq = artifact.get("seq", 0)
        payload = self._obj(result)
        if is_error:
            if self.log_manager:
                self.log_manager.warning(
                    "tool",
                    f"store_artifacts rejected {key} chunk {seq}",
                    duration=f"{duration_ms:.0f}ms",
                    detail=result,
                )
            if self.verbose:
                error = str(payload.get("error") or result or "validation failed")
                error = error.removeprefix(f"artifact {key}: ").removeprefix("Value error, ")
                error = " ".join(error.split())
                if len(error) > 220:
                    error = error[:219] + "…"
                self.console.print(
                    Text(f"  ⚠ {key} chunk {seq} rejected · {error}", style="yellow")
                )
        elif payload.get("recovered") is True:
            if self.log_manager:
                self.log_manager.info("tool", f"{key} recovered", seq=seq)
            if self.verbose:
                self.console.print(Text(f"  ✓ {key} recovered (chunk {seq})", style="green"))

    def _log_termination(self, reason: str) -> None:
        """Log agent termination."""
        if self.log_manager:
            self.log_manager.info(
                "agent",
                "Agent terminated",
                reason=reason,
                tool_calls=self._tool_calls,
                sub_agents=self._sub_agent_count,
                tokens=self._tokens_used,
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                cache_tokens=self._cache_tokens,
            )
        if self.verbose:
            self.console.print(f"[bold]⏹ Agent terminated[/]: {reason}")
            self.console.print(
                f"  [dim]Statistics: {self._tool_calls} tool calls, "
                f"{self._sub_agent_count} sub Agents, {self._token_summary()}[/]"
            )

    def _llm_elapsed(self) -> float:
        """Calculate current LLM call duration."""
        if self._llm_started_at is None:
            return 0.0
        return perf_counter() - self._llm_started_at

    _usage_breakdown = staticmethod(usage_breakdown)

    @classmethod
    def _total_tokens(cls, usage) -> int:
        return cls._usage_breakdown(usage)["total"]

    def _token_summary(self) -> str:
        """`in X · out Y · total Z · budget B (p%)` for the termination line."""
        parts = [f"in {self._input_tokens:,}", f"out {self._output_tokens:,}"]
        if self._cache_tokens:
            parts.append(f"cache {self._cache_tokens:,}")
        parts.append(f"total {self._tokens_used:,}")
        if self.token_budget:
            pct = self._tokens_used / self.token_budget * 100
            parts.append(f"budget {self.token_budget:,} ({pct:.0f}%)")
        return " · ".join(parts)

    @staticmethod
    def _obj(value) -> dict:
        """Tool args may arrive as a JSON string; never let display code crash."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except ValueError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _tool_detail(tool_name: str, tool_input: dict) -> str:
        """Extract safe, brief tool input summary."""
        if not isinstance(tool_input, dict):
            tool_input = LoggingProgressHook._obj(tool_input)
        if tool_name == "bash":
            cmd = str(tool_input.get("command", ""))[:80]
            return re.sub(
                r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+",
                r"\1=[REDACTED]",
                cmd,
            )
        if tool_name == "glob":
            return str(tool_input.get("pattern", ""))[:80]
        if tool_name == "grep":
            pattern = str(tool_input.get("pattern", ""))[:40]
            path = str(tool_input.get("path", ""))[:60]
            return f"'{pattern}' in {path}"
        if tool_name in {"read", "file_read", "file_ops", "list_files"}:
            path = tool_input.get("path") or tool_input.get("file_path") or ""
            operation = tool_input.get("operation")
            prefix = f"{operation} " if operation else ""
            return f"{prefix}{LoggingProgressHook._short_path(str(path))}".strip()
        if tool_name == "write_report":
            return str(tool_input.get("section", ""))
        if tool_name == "store_findings":
            finding = LoggingProgressHook._obj(tool_input.get("finding"))
            finding_type = finding.get("type", "artifact")
            finding_path = Path(str(finding.get("relative", ""))).name
            return f"{finding_type} {finding_path}".strip()
        if tool_name == "store_artifacts":
            operation = tool_input.get("operation", "")
            if operation == "add_artifact":
                artifact = LoggingProgressHook._obj(tool_input.get("artifact"))
                return f"add {artifact.get('type', 'artifact')} {artifact.get('name', '')} chunk {artifact.get('seq', 0)}".strip()
            if operation == "add_reference":
                reference = LoggingProgressHook._obj(tool_input.get("reference"))
                return f"ref {reference.get('referenced_by', '')} -> {reference.get('name', '')}".strip()
            if operation == "set_attribution":
                return f"attribution {LoggingProgressHook._obj(tool_input.get('attribution')).get('status', '')}".strip()
            return str(operation)
        if tool_name == "skill":
            operation = tool_input.get("operation", "")
            return f"{operation} {tool_input.get('name', '')}".strip()
        return ""

    @staticmethod
    def _short_path(value: str) -> str:
        if not value:
            return ""
        path = Path(value)
        cwd = Path.cwd()
        if path.is_relative_to(cwd):
            path = path.relative_to(cwd)
        limit = 66
        if len(str(path)) <= limit:
            return str(path)

        tail = path.name
        for parent in reversed(path.parent.parts):
            candidate = f"{parent}/{tail}"
            if len(candidate) + 2 > limit:
                break
            tail = candidate
        return f"…/{tail}"
