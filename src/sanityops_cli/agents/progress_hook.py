# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Progress hook with logging support.

Extends the framework progress hook with console output and persistent
file logging through the CLI ``Logger``."""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter
from typing import Any

from rich.console import Console

from sanityops_cli.logging.logger import Logger


class LoggingProgressHook:
    """Report agent progress to the console and the log file."""

    def __init__(
        self,
        console: Console,
        logger: Logger | None = None,
        verbose: bool = True,
    ):
        """Initialize the hook.

        Args:
            console: Rich console for terminal output.
            logger: Optional file logger.
            verbose: Whether to output to console.
        """
        self.console = console
        self.logger = logger
        self.verbose = verbose
        self._iteration = 0
        self._tool_calls = 0
        self._sub_agent_count = 0
        self._tokens_used = 0
        self._started = False
        self._llm_started_at: float | None = None
        self._events = None

        # Track tool call start times
        self._tool_start_times: dict[str, float] = {}

    def _get_events(self):
        """Lazy import of HookEvent."""
        if self._events is None:
            from sanityops_agent.hooks.base import HookEvent

            self._events = HookEvent
        return self._events

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
            self._llm_started_at = perf_counter()
            self._log_llm_start(iteration)

        elif event == events.AFTER_LLM_CALL:
            response = data.get("response")
            if response and hasattr(response, "usage"):
                usage = response.usage
                if usage:
                    tokens = self._usage_value(usage, "total_tokens")
                    self._tokens_used += tokens
                    elapsed = self._llm_elapsed()
                    self._log_llm_complete(tokens, elapsed)

        elif event == events.BEFORE_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", {})
            self._tool_calls += 1
            self._tool_start_times[tool_name] = perf_counter()
            self._log_tool_start(tool_name, tool_input)

        elif event == events.AFTER_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            is_error = ctx.is_error
            result_str = str(data.get("result") or "")
            duration_ms = 0.0
            if tool_name in self._tool_start_times:
                duration_ms = (perf_counter() - self._tool_start_times[tool_name]) * 1000
                del self._tool_start_times[tool_name]

            self._log_tool_complete(
                tool_name, is_error, duration_ms, error_detail=result_str if is_error else ""
            )

        elif event == events.ON_TERMINATION:
            reason = data.get("reason", "unknown")
            self._log_termination(reason)

        return ctx

    def _on_loop_start(self) -> None:
        """Ensure Agent start message is printed once."""
        if not self._started:
            if self.logger:
                self.logger.info("Agent started")
            if self.verbose:
                self.console.print("[bold cyan]▶ Agent started[/]")
            self._started = True

    def _log_llm_start(self, iteration: int) -> None:
        """Log LLM call start."""
        if self.logger:
            self.logger.debug(f"LLM call started (iteration {iteration + 1})")
        if self.verbose:
            self.console.print(f"  [dim]⟳ LLM call (iteration {iteration + 1})[/]")

    def _log_llm_complete(self, tokens: int, elapsed: float) -> None:
        """Log LLM call completion."""
        if self.logger:
            self.logger.debug(
                f"LLM call completed (tokens: {tokens}, duration: {elapsed:.1f}s)"
            )
        if self.verbose:
            self.console.print(f"  [dim]↓ received response (tokens: {tokens}, {elapsed:.1f}s)[/]")

    def _log_tool_start(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        """Log tool execution start."""
        if tool_name == "task":
            goal = tool_input.get("goal", "unknown")[:50]
            self._sub_agent_count += 1
            if self.logger:
                self.logger.info(
                    f"Sub-agent started (id: {self._sub_agent_count}, goal: {goal})"
                )
            if self.verbose:
                self.console.print(
                    f"  [bold yellow]◇ Starting sub Agent #{self._sub_agent_count}[/]: {goal}..."
                )
        else:
            if self.verbose:
                detail = self._tool_detail(tool_name, tool_input)
                suffix = f": {detail}" if detail else ""
                self.console.print(f"  [green]⚡ {tool_name}[/]{suffix}")

    def _log_tool_complete(
        self,
        tool_name: str,
        is_error: bool,
        duration_ms: float,
        error_detail: str = "",
    ) -> None:
        """Log tool execution completion."""
        if tool_name == "task":
            if is_error:
                if self.logger:
                    self.logger.error("Sub-agent failed")
                if self.verbose:
                    self.console.print("  [red]✗ Sub Agent failed[/]")
            else:
                if self.logger:
                    self.logger.info("Sub-agent completed")
                if self.verbose:
                    self.console.print("  [green]✓ Sub Agent completed[/]")
        elif is_error:
            detail = f": {error_detail}" if error_detail else ""
            if self.logger:
                self.logger.error(f"{tool_name} failed{detail} ({duration_ms:.0f}ms)")
            if self.verbose:
                self.console.print(f"  [red]✗ {tool_name} failed{detail}[/]")

    def _log_termination(self, reason: str) -> None:
        """Log agent termination."""
        if self.logger:
            self.logger.info(
                "Agent terminated "
                f"(reason: {reason}, tool calls: {self._tool_calls}, "
                f"sub-agents: {self._sub_agent_count}, tokens: {self._tokens_used})"
            )
        if self.verbose:
            self.console.print(f"[bold]⏹ Agent terminated[/]: {reason}")
            self.console.print(
                f"  [dim]Statistics: {self._tool_calls} tool calls, "
                f"{self._sub_agent_count} sub Agents, {self._tokens_used} tokens[/]"
            )

    def _llm_elapsed(self) -> float:
        """Calculate current LLM call duration."""
        if self._llm_started_at is None:
            return 0.0
        return perf_counter() - self._llm_started_at

    @staticmethod
    def _usage_value(usage, key: str) -> int:
        """Handle both dict and object usage formats."""
        if isinstance(usage, dict):
            return int(usage.get(key, 0) or 0)
        return int(getattr(usage, key, 0) or 0)

    @staticmethod
    def _tool_detail(tool_name: str, tool_input: dict) -> str:
        """Extract safe, brief tool input summary."""
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
            return f"{prefix}{str(path)[:100]}".strip()
        if tool_name == "store_findings":
            finding = tool_input.get("finding") or {}
            finding_type = finding.get("type", "artifact")
            finding_path = Path(str(finding.get("relative", ""))).name
            return f"{finding_type} {finding_path}".strip()
        if tool_name == "store_artifacts":
            operation = tool_input.get("operation", "")
            if operation == "add_artifact":
                artifact = tool_input.get("artifact") or {}
                return f"add {artifact.get('type', 'artifact')} {artifact.get('name', '')} chunk {artifact.get('seq', 0)}".strip()
            if operation == "add_reference":
                reference = tool_input.get("reference") or {}
                return f"ref {reference.get('referenced_by', '')} -> {reference.get('name', '')}".strip()
            if operation == "set_attribution":
                return (
                    f"attribution {(tool_input.get('attribution') or {}).get('status', '')}".strip()
                )
            return str(operation)
        if tool_name == "skill":
            operation = tool_input.get("operation", "")
            return f"{operation} {tool_input.get('name', '')}".strip()
        return ""
