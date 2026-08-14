# Loading Animations for Async Operations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add spinner progress with per-step and total timing to every async wait in the `inspect` command, and record all operation levels to a dated log file that errors point the user to.

**Architecture:** A new `Logger` writes leveled, dated logs under `~/.sanityops/logs/`. A new `ProgressTracker` (with a `StepContext` context manager) wraps each async step: normal mode uses Rich `Status`; verbose mode uses Rich `Live` so agent detail lines expand during a step and collapse to a `✓ done (dur)` line when it finishes. `ProgressHook` mirrors its console output into the logger at DEBUG level. The `inspect` command wires both in, distinguishing user config errors (no log reference) from program errors (log path + issues URL).

**Tech Stack:** Python 3.11+, Typer, Rich (`Status`, `Live`, `Spinner`), stdlib `logging`, anyio (existing).

## Global Constraints

- Python `>=3.11`; dependencies unchanged (rich `>=13.0`, typer `>=0.12`).
- Ruff: `line-length = 100`; lint select `E, W, F, I, B, UP`; isort `known-first-party = ["sanityops_cli"]`.
- All user-facing progress and error text is **English**.
- Log file: `~/.sanityops/logs/sanityops-cli-{YYYY-MM-DD}.log`. Log dir default resolves `Path.home()` **at construction time** (so tests can `monkeypatch.setenv("HOME", ...)`).
- API keys/secrets must never reach the log file — `Logger.redact()` masks `sk-...` and `api_key=...` values.
- The three `inspect` steps, in order: `Loading configuration...`, `Analyzing artifacts...`, `Running defect check...`.
- Run tests with `python -m pytest <path>`; full suite baseline is 59 passing.

---

### Task 1: Logger Module

**Files:**
- Create: `src/sanityops_cli/logging/__init__.py`
- Create: `src/sanityops_cli/logging/logger.py`
- Create: `tests/unit/logging/__init__.py`
- Create: `tests/unit/logging/test_logger.py`

**Interfaces:**
- Produces (used by Tasks 2–5):
  - `Logger(log_dir: Path | None = None)`
  - `logger.debug(message: str) -> None`
  - `logger.info(message: str) -> None`
  - `logger.warning(message: str) -> None`
  - `logger.error(message: str) -> None`
  - `logger.step_started(step_name: str) -> None`
  - `logger.step_completed(step_name: str, duration: float) -> None`
  - `logger.step_failed(step_name: str, error: str) -> None`
  - `logger.get_log_path() -> Path`
  - `Logger.redact(message: str) -> str` (static)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/logging/test_logger.py`:

```python
"""Unit tests for the Logger class."""

from datetime import date
from pathlib import Path

from sanityops_cli.logging.logger import Logger


class TestLogger:
    def test_creates_log_file_in_dir(self, tmp_path: Path):
        logger = Logger(tmp_path)
        assert logger.get_log_path().exists()
        assert logger.get_log_path().parent == tmp_path

    def test_filename_contains_today_date(self, tmp_path: Path):
        logger = Logger(tmp_path)
        assert logger.get_log_path().name == f"sanityops-cli-{date.today().isoformat()}.log"

    def test_creates_nested_log_dir(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "logs"
        Logger(nested)
        assert nested.is_dir()

    def test_leveled_messages_written(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.debug("debug line")
        logger.info("info line")
        logger.warning("warning line")
        logger.error("error line")
        content = logger.get_log_path().read_text()
        assert "[DEBUG] debug line" in content
        assert "[INFO] info line" in content
        assert "[WARNING] warning line" in content
        assert "[ERROR] error line" in content

    def test_step_helpers_write_expected_messages(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.step_started("Analyzing artifacts...")
        logger.step_completed("Analyzing artifacts...", 1.234)
        logger.step_failed("Analyzing artifacts...", "boom")
        content = logger.get_log_path().read_text()
        assert "[INFO] Step started: Analyzing artifacts..." in content
        assert "[INFO] Step completed: Analyzing artifacts... (1.23s)" in content
        assert "[ERROR] Step failed: Analyzing artifacts... - boom" in content

    def test_redact_masks_api_key_values(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.info("using api_key=sk-abc123DEF456 token")
        logger.info("auth: sk-proj-9f8e7d6c5b4a3a")
        content = logger.get_log_path().read_text()
        assert "sk-abc123DEF456" not in content
        assert "sk-proj-9f8e7d6c5b4a3a" not in content

    def test_redact_static(self):
        assert "sk-***" in Logger.redact("key=sk-abcdefghijklmn")
        assert Logger.redact("plain message") == "plain message"
```

Create empty `__init__.py` files for `src/sanityops_cli/logging/__init__.py` and `tests/unit/logging/__init__.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/logging/test_logger.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sanityops_cli.logging'`.

- [ ] **Step 3: Implement the Logger**

Create `src/sanityops_cli/logging/logger.py`:

```python
"""File-based logging for sanityops-cli operations."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

#: Patterns used to redact secrets before writing to disk.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(api[_-]?key\s*[:=]\s*)[^\s\"',}]+", re.IGNORECASE), r"\1***"),
]


class Logger:
    """Appends timestamped, leveled messages to a dated log file.

    Each instance owns its own stdlib logger and file handler so multiple
    instances (e.g. in tests) do not share handlers.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        if log_dir is not None:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path.home() / ".sanityops" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"sanityops-cli-{date.today().isoformat()}.log"
        self._logger = logging.getLogger(f"sanityops_cli.{id(self)}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self._logger.addHandler(handler)

    def debug(self, message: str) -> None:
        self._logger.debug(Logger.redact(message))

    def info(self, message: str) -> None:
        self._logger.info(Logger.redact(message))

    def warning(self, message: str) -> None:
        self._logger.warning(Logger.redact(message))

    def error(self, message: str) -> None:
        self._logger.error(Logger.redact(message))

    def step_started(self, step_name: str) -> None:
        self.info(f"Step started: {step_name}")

    def step_completed(self, step_name: str, duration: float) -> None:
        self.info(f"Step completed: {step_name} ({duration:.2f}s)")

    def step_failed(self, step_name: str, error: str) -> None:
        self.error(f"Step failed: {step_name} - {error}")

    def get_log_path(self) -> Path:
        return self.log_file

    @staticmethod
    def redact(message: str) -> str:
        """Mask API keys and secret-bearing substrings before logging."""
        for pattern, repl in _SECRET_PATTERNS:
            message = pattern.sub(repl, message)
        return message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/logging/test_logger.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/logging tests/unit/logging
git commit -m "feat(logging): add leveled file Logger with redaction"
```

---

### Task 2: ProgressTracker Module

**Files:**
- Create: `src/sanityops_cli/progress/__init__.py`
- Create: `src/sanityops_cli/progress/tracker.py`
- Create: `tests/unit/progress/__init__.py`
- Create: `tests/unit/progress/test_tracker.py`

**Interfaces:**
- Consumes: `Logger` from Task 1 (`logger.step_started`, `logger.step_completed`, `logger.step_failed`).
- Produces (used by Task 5):
  - `ProgressTracker(console: Console, logger: Logger, verbose: bool = False)`
  - `tracker.step(name: str) -> StepContext`
  - `tracker.summary() -> None` (prints divider + `Total time: {:.2f}s`)
  - `tracker.step_times: list[tuple[str, float]]`
  - `StepContext` is a context manager with a `console: Console` property (routes agent output into the Live display in verbose mode).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/progress/test_tracker.py`:

```python
"""Unit tests for ProgressTracker and StepContext."""

import io

import pytest
from rich.console import Console

from sanityops_cli.logging.logger import Logger
from sanityops_cli.progress.tracker import ProgressTracker


class TestProgressTracker:
    def _tracker(self, tmp_path, verbose=False):
        console = Console(record=True, file=io.StringIO())
        logger = Logger(tmp_path)
        return ProgressTracker(console, logger, verbose=verbose), console, logger

    def test_normal_mode_records_step_time_and_summary(self, tmp_path):
        tracker, console, _ = self._tracker(tmp_path)
        with tracker.step("Analyzing artifacts..."):
            pass
        tracker.summary()
        text = console.export_text()
        assert "Analyzing artifacts..." in text
        assert "Total time:" in text
        assert len(tracker.step_times) == 1
        name, duration = tracker.step_times[0]
        assert name == "Analyzing artifacts..."
        assert duration >= 0

    def test_success_logs_step_started_and_completed(self, tmp_path):
        tracker, _, logger = self._tracker(tmp_path)
        with tracker.step("Loading configuration..."):
            pass
        content = logger.get_log_path().read_text()
        assert "Step started: Loading configuration..." in content
        assert "Step completed: Loading configuration..." in content

    def test_failure_logs_step_failed_and_reraises(self, tmp_path):
        tracker, _, logger = self._tracker(tmp_path)
        with pytest.raises(RuntimeError, match="boom"):
            with tracker.step("Running defect check..."):
                raise RuntimeError("boom")
        content = logger.get_log_path().read_text()
        assert "Step failed: Running defect check... - boom" in content
        assert tracker.step_times == []

    def test_normal_mode_step_console_is_tracker_console(self, tmp_path):
        tracker, console, _ = self._tracker(tmp_path)
        step = tracker.step("Analyzing artifacts...")
        with step:
            assert step.console is tracker.console

    def test_verbose_mode_uses_live_console(self, tmp_path):
        tracker, console, _ = self._tracker(tmp_path, verbose=True)
        step = tracker.step("Analyzing artifacts...")
        with step:
            assert step.console is not tracker.console
        text = console.export_text()
        assert "Analyzing artifacts..." in text
```

Create empty `__init__.py` files for `src/sanityops_cli/progress/__init__.py` and `tests/unit/progress/__init__.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/progress/test_tracker.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sanityops_cli.progress'`.

- [ ] **Step 3: Implement ProgressTracker**

Create `src/sanityops_cli/progress/tracker.py`:

```python
"""Step-based progress display with spinner, elapsed timing, and logging."""

from __future__ import annotations

import time

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.status import Status
from rich.text import Text

from sanityops_cli.logging.logger import Logger

#: Refresh rate for spinner/live displays (Hz).
_REFRESH_PER_SECOND = 10


class ProgressTracker:
    """Tracks sequential steps: spinner progress, per-step timing, logging."""

    def __init__(self, console: Console, logger: Logger, verbose: bool = False) -> None:
        self.console = console
        self.logger = logger
        self.verbose = verbose
        self.step_times: list[tuple[str, float]] = []

    def step(self, name: str) -> "StepContext":
        """Start a new tracked step, returning its context manager."""
        return StepContext(self, name)

    def summary(self) -> None:
        """Print a divider and the total elapsed time across all steps."""
        total = sum(duration for _, duration in self.step_times)
        self.console.print(f"[dim]{'─' * 30}[/]")
        self.console.print(f"[bold]Total time:[/] {total:.2f}s")


class StepContext:
    """Context manager for a single tracked step."""

    def __init__(self, tracker: ProgressTracker, name: str) -> None:
        self.tracker = tracker
        self.name = name
        self._start: float = 0.0
        self._live: Live | None = None
        self._status: Status | None = None

    @property
    def console(self) -> Console:
        """Console to route agent progress output into (Live console in verbose mode)."""
        if self._live is not None:
            return self._live.console
        return self.tracker.console

    def __enter__(self) -> "StepContext":
        self._start = time.perf_counter()
        self.tracker.logger.step_started(self.name)
        if self.tracker.verbose:
            self._live = Live(
                console=self.tracker.console, refresh_per_second=_REFRESH_PER_SECOND
            )
            self._live.start()
            self._live.update(Spinner("dots", text=f"[bold cyan]{self.name}[/]"))
        else:
            self._status = self.tracker.console.status(f"[bold cyan]{self.name}[/]")
            self._status.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration = time.perf_counter() - self._start
        if exc_type is None:
            self.tracker.logger.step_completed(self.name, duration)
            self.tracker.step_times.append((self.name, duration))
            summary = Text.from_markup(f"[green]✓[/] {self.name} ({duration:.2f}s)")
            if self._live is not None:
                self._live.update(summary)
                self._live.stop()
                self._live = None
            else:
                self._status.stop()
                self._status = None
                self.tracker.console.print(summary)
        else:
            self.tracker.logger.step_failed(self.name, str(exc_val))
            if self._live is not None:
                self._live.stop()
                self._live = None
            else:
                self._status.stop()
                self._status = None
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/progress/test_tracker.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/progress tests/unit/progress
git commit -m "feat(progress): add ProgressTracker with Status/Live step display"
```

---

### Task 3: ProgressHook Logging Integration

**Files:**
- Modify: `src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py`
- Create: `tests/unit/agents/scanner_agent/test_progress_hook.py`

**Interfaces:**
- Consumes: `Logger` from Task 1.
- Produces (used by Task 4):
  - `ProgressHook(console: Console, verbose: bool = True, logger: Logger | None = None)`
  - New private helper `_emit(message: str) -> None`: prints to console and mirrors plain text to `logger.debug`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/scanner_agent/test_progress_hook.py`:

```python
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
    return hook


def _ctx(event, data=None, is_error=False):
    return SimpleNamespace(event=event, data=data or {}, is_error=is_error)


class TestProgressHookLogging:
    @pytest.mark.anyio
    async def test_before_llm_call_logs_debug(self):
        logger = _FakeLogger()
        hook = _make_hook(logger)
        await hook.handle(_ctx("before_llm_call", {"iteration": 0}))
        assert any("LLM call" in m for m in logger.debug_calls)

    @pytest.mark.anyio
    async def test_task_completion_logs_plain_text(self):
        logger = _FakeLogger()
        hook = _make_hook(logger)
        await hook.handle(
            _ctx("before_tool_exec", {"tool_name": "task", "tool_input": {"goal": "g"}})
        )
        await hook.handle(_ctx("after_tool_exec", {"tool_name": "task"}, is_error=False))
        assert any(m == "✓ Sub Agent completed" for m in logger.debug_calls)

    @pytest.mark.anyio
    async def test_task_failure_logs_error(self):
        logger = _FakeLogger()
        hook = _make_hook(logger)
        await hook.handle(_ctx("after_tool_exec", {"tool_name": "task"}, is_error=True))
        assert any("Sub Agent failed" in m for m in logger.error_calls)

    @pytest.mark.anyio
    async def test_no_logger_does_not_crash(self):
        hook = _make_hook(None)
        await hook.handle(_ctx("before_llm_call", {"iteration": 0}))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/scanner_agent/test_progress_hook.py -q`
Expected: FAIL with `TypeError: ProgressHook.__init__() got an unexpected keyword argument 'logger'`.

- [ ] **Step 3: Implement the ProgressHook changes**

Modify `src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py`:

Add the import at the top:

```python
from rich.console import Console
from rich.text import Text

from sanityops_cli.logging.logger import Logger
```

Change the constructor:

```python
    def __init__(
        self,
        console: Console,
        verbose: bool = True,
        logger: Logger | None = None,
    ):
        self.console = console
        self.verbose = verbose
        self.logger = logger
        self._iteration = 0
        self._tool_calls = 0
        self._sub_agent_count = 0
        # Will be set after lazy import
        self._events = None
```

Add the `_emit` helper (place it right before `async def handle`):

```python
    def _emit(self, message: str) -> None:
        """Print a progress line to console and mirror it to the logger at DEBUG."""
        self.console.print(message)
        if self.logger is not None:
            self.logger.debug(Text.from_markup(message).plain)
```

Replace every `self.console.print(...)` call inside `handle()` with `self._emit(...)` **except** the `AFTER_TOOL_EXEC` task-failure branch, which becomes:

```python
        elif event == events.AFTER_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            is_error = ctx.is_error

            if tool_name == "task":
                if is_error:
                    self.console.print("  [red]✗ Sub Agent failed[/]")
                    if self.logger is not None:
                        self.logger.error("Sub Agent failed")
                else:
                    self._emit("  [green]✓ Sub Agent completed[/]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/scanner_agent/test_progress_hook.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py tests/unit/agents/scanner_agent/test_progress_hook.py
git commit -m "feat(progress-hook): mirror agent progress to file logger at DEBUG level"
```

---

### Task 4: ScannerAgent Logger Passthrough

**Files:**
- Modify: `src/sanityops_cli/agents/scanner_agent/agent.py`
- Create: `tests/unit/agents/scanner_agent/test_agent.py`

**Interfaces:**
- Consumes: `ProgressHook(console, verbose, logger)` from Task 3.
- Produces (used by Task 5):
  - `ScannerAgent(provider, max_loops=30, timeout=120, verbose=False, console=None, logger=None)`
  - The logger is forwarded to `ProgressHook` in both `scan()` and `analyze_files()`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/agents/scanner_agent/test_agent.py`:

```python
"""Unit tests for ScannerAgent construction and logger passthrough."""

from rich.console import Console

from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.logging.logger import Logger


class TestScannerAgent:
    def test_accepts_logger_and_console(self, tmp_path):
        console = Console(record=True)
        logger = Logger(tmp_path)
        agent = ScannerAgent(provider=object(), verbose=True, console=console, logger=logger)
        assert agent.logger is logger
        assert agent.console is console
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/agents/scanner_agent/test_agent.py -q`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'logger'`.

- [ ] **Step 3: Implement the ScannerAgent changes**

Modify `src/sanityops_cli/agents/scanner_agent/agent.py`.

Change the constructor:

```python
    def __init__(
        self,
        provider,
        max_loops: int = 30,
        timeout: int = 120,
        verbose: bool = False,
        console: Console | None = None,
        logger=None,
    ):
        self.provider = provider
        self.max_loops = max_loops
        self.timeout = timeout
        self.verbose = verbose
        self.console = console or Console()
        self.logger = logger
```

In **both** `scan()` and `analyze_files()`, replace the `ProgressHook` registration line:

```python
            hook_executor.register(ProgressHook(self.console, verbose=self.verbose))
```

with:

```python
            hook_executor.register(
                ProgressHook(self.console, verbose=self.verbose, logger=self.logger)
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/scanner_agent/test_agent.py tests/unit/agents/scanner_agent/test_progress_hook.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/agents/scanner_agent/agent.py tests/unit/agents/scanner_agent/test_agent.py
git commit -m "feat(scanner-agent): pass logger through to ProgressHook"
```

---

### Task 5: Wire Progress + Logging Into the inspect Command

**Files:**
- Modify: `src/sanityops_cli/commands/inspect.py`
- Modify: `tests/unit/commands/test_inspect.py`

**Interfaces:**
- Consumes: `Logger` (Task 1), `ProgressTracker` (Task 2), `ScannerAgent(logger=...)` (Task 4).
- Produces: modified `inspect` command behavior per spec: three tracked steps, per-step + total timing, user-error vs program-error handling.

- [ ] **Step 1: Update the existing inspect test**

Modify `tests/unit/commands/test_inspect.py`:
1. Add `import io` to the imports.
2. Add `from rich.console import Console` to the imports.
3. Add `from sanityops_cli.constants.exit_codes import EXIT_FAILURE` to the imports.
4. Add `monkeypatch.setenv("HOME", str(tmp_path))` as the first line of the existing `test_inspect_skips_defect_check_when_flag_set` so the Logger writes into `tmp_path` instead of the real home.

- [ ] **Step 2: Write the new failing inspect tests**

Append to `tests/unit/commands/test_inspect.py`:

```python
def test_inspect_writes_dated_log_file(monkeypatch, tmp_path):
    """Inspect should create a dated log file under ~/.sanityops/logs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n")
    cfg = tmp_path / "inspect_config.yaml"
    cfg.write_text(
        "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
        f"skills:\n  - file: {skill_file}\n"
    )

    class FakeAgent:
        def analyze_files_sync(self, prompts, tools, skills):
            return _findings()

    monkeypatch.setattr(
        "sanityops_cli.commands.inspect.ScannerAgent",
        lambda *a, **k: FakeAgent(),
    )

    result = runner.invoke(app, ["inspect", "--config", str(cfg), "--skip-defect-check"])
    assert result.exit_code == 0

    logs = list((tmp_path / ".sanityops" / "logs").glob("sanityops-cli-*.log"))
    assert len(logs) == 1
    content = logs[0].read_text()
    assert "Step started: Loading configuration" in content
    assert "Step completed: Analyzing artifacts" in content
    assert "Step failed" not in content


def test_inspect_program_error_points_to_log_file(monkeypatch, tmp_path):
    """A program error should print the log path and issue URL."""
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n")
    cfg = tmp_path / "inspect_config.yaml"
    cfg.write_text(
        "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
        f"skills:\n  - file: {skill_file}\n"
    )

    class FailingAgent:
        def analyze_files_sync(self, prompts, tools, skills):
            raise RuntimeError("LLM API timeout")

    monkeypatch.setattr(
        "sanityops_cli.commands.inspect.ScannerAgent",
        lambda *a, **k: FailingAgent(),
    )

    output = io.StringIO()
    test_console = Console(file=output, record=True)
    monkeypatch.setattr("sanityops_cli.commands.inspect.console", test_console)

    result = runner.invoke(app, ["inspect", "--config", str(cfg), "--skip-defect-check"])
    assert result.exit_code == EXIT_FAILURE
    text = output.getvalue()
    assert "Error in step" in text
    assert "LLM API timeout" in text
    assert "See log for details" in text
    assert "github.com/sanityops-org/sanityops-cli/issues" in text


def test_inspect_config_error_shows_guidance_without_log_hint(monkeypatch, tmp_path):
    """A missing config is a user error: guidance shown, no log reference."""
    monkeypatch.setenv("HOME", str(tmp_path))
    output = io.StringIO()
    test_console = Console(file=output, record=True)
    monkeypatch.setattr("sanityops_cli.commands.inspect.console", test_console)

    result = runner.invoke(app, ["inspect", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == EXIT_FAILURE
    text = output.getvalue()
    assert "Config error" in text
    assert "Config file not found" in text
    assert "See log for details" not in text
```

- [ ] **Step 3: Run tests to verify the new ones fail**

Run: `python -m pytest tests/unit/commands/test_inspect.py -q`
Expected: the three new tests FAIL (import errors or assertions), existing test may still pass.

- [ ] **Step 4: Implement the inspect command changes**

Rewrite `src/sanityops_cli/commands/inspect.py` in full:

```python
"""inspect command — Sanityops CLI Tool"""

import anyio
import typer
from rich.console import Console
from rich.table import Table

from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.defect_checker.checker import DefectChecker
from sanityops_cli.defect_checker.llm_config import resolve_llm_config
from sanityops_cli.defect_checker.renderer import DefectRenderer
from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.logging.logger import Logger
from sanityops_cli.progress.tracker import ProgressTracker
from sanityops_cli.utils.config_loader import InspectConfigLoader

console = Console()
inspect_app = typer.Typer()

#: URL users attach log files to when reporting issues.
ISSUE_URL = "https://github.com/sanityops-org/sanityops-cli/issues"


def _report_program_error(logger: Logger, step_name: str, error: Exception) -> None:
    """Print a concise program-error summary and point to the log file."""
    console.print(f"[red]✗ Error in step \"{step_name}\"[/]")
    console.print(f"  Message: {error}")
    console.print(f"\nSee log for details: {logger.get_log_path()}")
    console.print("To report this issue, attach the log file to:")
    console.print(ISSUE_URL)


@inspect_app.callback(invoke_without_command=True)
def inspect(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .sanityops/inspect_config.yaml in cwd.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    check_level: str = typer.Option(
        "L2",
        "--check-level",
        help="Defect check level: L1 (fast), L2 (standard), L3 (deep).",
    ),
    skip_defect_check: bool = typer.Option(
        False,
        "--skip-defect-check",
        help="Skip the defect check step and only run artifact analysis.",
    ),
):
    """Inspect and defect-check the configured artifacts."""
    if check_level not in {"L1", "L2", "L3"}:
        console.print(f"[red]✗ Invalid check level: {check_level} (must be L1/L2/L3)[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    logger = Logger()
    tracker = ProgressTracker(console, logger, verbose=verbose)

    # Step 1: Load and validate config
    try:
        with tracker.step("Loading configuration..."):
            loader = InspectConfigLoader(config)
            artifacts = loader.load()
    except ValidationError as e:
        console.print(f"[red]✗ Config error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except Exception as e:
        _report_program_error(logger, "Loading configuration...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = artifacts["project_id"]
    prompt_files = artifacts["prompts"]
    tool_files = artifacts["tools"]
    skill_files = artifacts["skills"]

    # Step 2: Display resolved artifacts
    table = Table(title="[bold]Inspect Artifacts[/]", border_style="blue")
    table.add_column("Type", style="bold cyan", no_wrap=True)
    table.add_column("Absolute Path", style="white")
    for f in prompt_files:
        table.add_row("Prompt", f)
    for f in tool_files:
        table.add_row("Tool", f)
    for f in skill_files:
        table.add_row("Skill", f)
    console.print(table)
    console.print(f"[dim]Project ID: {project_id}[/dim]")
    console.print(
        f"[dim]Total: {len(prompt_files)} prompts, "
        f"{len(tool_files)} tools, {len(skill_files)} skills[/dim]\n"
    )

    # Step 3: Run ScannerAgent analysis
    try:
        with tracker.step("Analyzing artifacts...") as step:
            # Resolve LLM config (config file model section or env vars)
            llm_config = resolve_llm_config(config)

            from sanityops_agent.config import ProviderConfig
            from sanityops_agent.llm.factory import ProviderFactory

            provider_config = ProviderConfig(
                LLM_PROVIDER=llm_config["llm_provider"],
                API_KEY=llm_config["llm_api_key"],
                MODEL_ID=llm_config["llm_model_id"],
                BASE_URL=llm_config["llm_base_url"] or None,
            )
            provider = ProviderFactory.create(provider_config)
            agent = ScannerAgent(
                provider=provider,
                verbose=verbose,
                console=step.console,
                logger=logger,
            )
            result = agent.analyze_files_sync(
                prompts=prompt_files,
                tools=tool_files,
                skills=skill_files,
            )
    except Exception as e:
        _report_program_error(logger, "Analyzing artifacts...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not result.skills and not result.tools and not result.prompts:
        console.print("[yellow]No artifacts found to check.[/yellow]")
        tracker.summary()
        raise typer.Exit()

    # Step 4: Run defect check and render (unless skipped)
    if skip_defect_check:
        console.print("[dim]Defect check skipped (--skip-defect-check).[/dim]")
        tracker.summary()
        raise typer.Exit()

    async def run_check():
        checker = DefectChecker(llm_config)
        return await checker.check(result, check_level=check_level)

    try:
        with tracker.step("Running defect check..."):
            response = anyio.run(run_check)
    except Exception as e:
        _report_program_error(logger, "Running defect check...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    tracker.summary()
    DefectRenderer(console).render(response)
```

- [ ] **Step 5: Run the full inspect test file**

Run: `python -m pytest tests/unit/commands/test_inspect.py -q`
Expected: 4 passed.

- [ ] **Step 6: Run the full suite + lint**

```bash
python -m pytest -q
ruff check src tests
```

Expected: all tests pass (59 existing + new); ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/sanityops_cli/commands/inspect.py tests/unit/commands/test_inspect.py
git commit -m "feat(inspect): add step progress, timing, and file logging with error handling"
```

---

## Self-Review

- **Spec coverage:**
  - Progress spinner per async step → Task 2 + Task 5 (`Status` normal / `Live` verbose).
  - Per-step + total timing → Task 2 (`step_times`, `summary()`), wired in Task 5.
  - All-English display text → Global Constraints + step names in Task 5.
  - Logging system with all levels → Task 1 (DEBUG/INFO/WARNING/ERROR), wired in Task 5.
  - Log path shown on program error → Task 5 `_report_program_error`.
  - User config errors show guidance without log reference → Task 5 `ValidationError` branch (asserted by `test_inspect_config_error_shows_guidance_without_log_hint`).
  - Verbose expand/collapse of agent details → Task 2 (`Live` + `StepContext.console` routing) + Task 3/4 (hook → logger, agent console routing).
- **Placeholder scan:** no TBD/TODO; every step has concrete code and expected output.
- **Type consistency:** `Logger.step_started/step_completed/step_failed` signatures match between Task 1 (definition) and Tasks 2/5 (usage). `ProgressHook(console, verbose, logger)` matches Task 3 (definition) and Task 4 (call). `ScannerAgent(..., logger=...)` matches Task 4 (definition) and Task 5 (call). `StepContext.console` matches Task 2 (definition) and Task 5 (usage as `step.console`).
