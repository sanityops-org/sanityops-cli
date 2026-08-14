"""Step-based progress display with spinner, elapsed timing, and logging."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.markup import escape
from rich.spinner import Spinner
from rich.status import Status
from rich.text import Text

from sanityops_cli.logging.logger import Logger

#: Refresh rate for spinner/live displays (Hz).
_REFRESH_PER_SECOND = 10

__all__ = ["ProgressTracker", "StepContext"]


class ProgressTracker:
    """Tracks sequential steps: spinner progress, per-step timing, logging."""

    def __init__(self, console: Console, logger: Logger, verbose: bool = False) -> None:
        self.console = console
        self.logger = logger
        self.verbose = verbose
        self.step_times: list[tuple[str, float]] = []

    def step(self, name: str) -> StepContext:
        """Start a new tracked step, returning its context manager."""
        return StepContext(self, name)

    def summary(self) -> None:
        """Print a divider and the total elapsed time across all steps."""
        total = sum(duration for _, duration in self.step_times)
        self.console.print(f"[dim]{'─' * 30}[/]")
        self.console.print(f"[bold]Total time:[/] {total:.2f}s")


class _LiveConsole:
    """Console-like sink that appends printed lines into a step's Live display.

    Duck-types ``Console.print`` so an agent's ProgressHook can stream detail
    lines into the step's Live renderable (expand). The accumulated lines
    collapse away when the Live stops, replaced by the step summary.
    """

    def __init__(self, live: Live, step_name: str) -> None:
        self._live = live
        self._step_name = step_name
        self._lines: list[RenderableType] = []

    def print(self, *objects: Any, **kwargs: Any) -> None:
        """Duck-type ``Console.print``: render objects into the Live display.

        Multiple objects are joined with spaces (rich's default); a ``style``
        kwarg is honored. Other rich keyword options are ignored — each print
        is rendered as its own row in the Live display.
        """
        message = " ".join(str(obj) for obj in objects) if objects else ""
        line = Text.from_markup(message, style=kwargs.get("style"))
        self._lines.append(line)
        self._live.update(
            Group(
                Spinner("dots", text=f"[bold cyan]{escape(self._step_name)}[/]"),
                *self._lines,
            )
        )


class StepContext:
    """Context manager for a single tracked step."""

    def __init__(self, tracker: ProgressTracker, name: str) -> None:
        self.tracker = tracker
        self.name = name
        self._start: float = 0.0
        self._live: Live | None = None
        self._status: Status | None = None
        self._live_console: _LiveConsole | None = None

    @property
    def console(self) -> Console | _LiveConsole:
        """Console to route agent progress output into (Live sink in verbose mode)."""
        if self._live_console is not None:
            return self._live_console
        return self.tracker.console

    def __enter__(self) -> StepContext:
        self._start = time.perf_counter()
        self.tracker.logger.step_started(self.name)
        if self.tracker.verbose:
            self._live = Live(
                console=self.tracker.console, refresh_per_second=_REFRESH_PER_SECOND
            )
            self._live.start()
            self._live.update(Spinner("dots", text=f"[bold cyan]{escape(self.name)}[/]"))
            self._live_console = _LiveConsole(self._live, self.name)
        else:
            self._status = self.tracker.console.status(f"[bold cyan]{escape(self.name)}[/]")
            self._status.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration = time.perf_counter() - self._start
        if exc_type is None:
            self.tracker.logger.step_completed(self.name, duration)
            self.tracker.step_times.append((self.name, duration))
            summary = Text.from_markup(f"[green]✓[/] {escape(self.name)} ({duration:.2f}s)")
            if self._live is not None:
                self._live.update(summary)
                self._live.stop()
                self._live = None
                self._live_console = None
            else:
                self._status.stop()
                self._status = None
                self.tracker.console.print(summary)
        else:
            self.tracker.logger.step_failed(self.name, str(exc_val))
            if self._live is not None:
                self._live.update(Text.from_markup(f"[red]✗[/] {escape(self.name)} ({duration:.2f}s)"))
                self._live.stop()
                self._live = None
                self._live_console = None
            else:
                self._status.stop()
                self._status = None
        return False
