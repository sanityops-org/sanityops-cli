# Loading Animations for Async Operations - Design Spec

## Overview

Add progress indicators with timing information to the `inspect` command for all async operations. Implement a logging system that records all operations and provides users with log file location when errors occur.

## Goals

1. Display step-by-step progress with spinner animation during async operations
2. Show duration for each step and total elapsed time
3. Log all operations (normal and error) to dated log files
4. Provide log file path on error for user-initiated issue reporting

## Non-Goals

- The `init` command requires no changes (no async operations)
- No in-terminal error reporting mechanism (users manually attach logs to GitHub issues)

---

## Progress Display

### Steps

The `inspect` command displays the following steps in order:

| Step | Description |
|------|-------------|
| `Loading configuration...` | Load and validate inspect_config.yaml |
| `Analyzing artifacts...` | ScannerAgent analyzes all prompt, tool, and skill files |
| `Running defect check...` | DefectChecker executes defect detection |

**Note:** The ScannerAgent processes all artifact types in a single execution. Verbose mode shows the internal agent activity (LLM calls, tool executions) which may span multiple artifact types within the same step.

### Display Format - Normal Mode

```
 ✓ Loading configuration... (0.12s)
 ✓ Analyzing artifacts... (7.64s)
 ✓ Running defect check... (5.63s)
────────────────────────────────────
 Total: 13.39s
```

### Display Format - Verbose Mode

Verbose mode expands each step to show agent execution details:

```
 ⠋ Analyzing artifacts...
   ⟳ LLM call (iteration 1)
   ↓ received response (tokens: 1234)
   ⚡ file_read: /path/to/prompt.md
   ⚡ grep: 'pattern' in /path
   ⟳ LLM call (iteration 2)
   ⚡ file_read: /path/to/tool.json
 ✓ done (7.64s)

 ⠋ Running defect check...
   ⟳ LLM call (iteration 1)
   ↓ received response (tokens: 2456)
 ✓ done (5.63s)
```

### Implementation

Use Rich `Status` for normal mode spinner display. Use Rich `Live` for verbose mode to allow real-time updates while displaying agent details.

---

## Logging System

### Log File Location

```
~/.sanityops/logs/sanityops-cli-{YYYY-MM-DD}.log
```

Example: `~/.sanityops/logs/sanityops-cli-2026-08-14.log`

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Verbose execution details (LLM calls, tool executions) |
| `INFO` | Normal operation steps |
| `WARNING` | Non-fatal issues |
| `ERROR` | Error conditions |

### Log Format

```
{timestamp} [{level}] {message}
```

Example:
```
2026-08-14 10:23:45,123 [INFO] Step started: Loading configuration
2026-08-14 10:23:45,235 [INFO] Step completed: Loading configuration (0.12s)
2026-08-14 10:23:45,236 [INFO] Step started: Analyzing prompts
2026-08-14 10:23:47,586 [DEBUG] LLM call iteration 1
2026-08-14 10:23:47,587 [DEBUG] Tool: file_read /path/to/prompt.md
2026-08-14 10:23:47,812 [ERROR] Step failed: Analyzing prompts - Agent execution timeout
```

---

## Error Display

### Error Output Format

```
✗ Error in step "Analyzing prompts"
  Message: Agent execution timeout after 120s

See log for details: ~/.sanityops/logs/sanityops-cli-2026-08-14.log

To report this issue, attach the log file to:
https://github.com/sanityops-org/sanityops-cli/issues
```

### Error Categories

**User configuration errors (no log reference needed):**

| Error Type | Display |
|------------|---------|
| Config file not found | Show expected path and suggest `inspect init` |
| YAML parse error | Show parse error location |
| Validation error | Show which field is invalid and why |
| Artifact file not found | Show the missing file path |
| Invalid check level | Show valid options (L1/L2/L3) |

**Program errors (show log reference):**

| Error Type | Display |
|------------|---------|
| LLM API error | Network timeout, rate limit, auth failure |
| Agent execution error | Agent timeout, unexpected termination |
| Defect check error | Check execution failure |
| Unexpected exception | Any other unhandled errors |

---

## File Structure

```
src/sanityops_cli/
├── commands/
│   └── inspect.py              # Modified: use ProgressTracker
├── progress/
│   ├── __init__.py
│   └── tracker.py              # New: ProgressTracker class
├── logging/
│   ├── __init__.py
│   └── logger.py               # New: Logger class
└── constants/
    └── exit_codes.py           # Existing
```

---

## Components

### Logger Class

Location: `src/sanityops_cli/logging/logger.py`

```python
class Logger:
    """Manages file-based logging for CLI operations."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or Path.home() / ".sanityops" / "logs"
        self._ensure_log_dir()
        self._current_log_file = self._get_log_file_path()

    def info(self, message: str) -> None: ...
    def debug(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...

    def step_started(self, step_name: str) -> None:
        self.info(f"Step started: {step_name}")

    def step_completed(self, step_name: str, duration: float) -> None:
        self.info(f"Step completed: {step_name} ({duration:.2f}s)")

    def step_failed(self, step_name: str, error: str) -> None:
        self.error(f"Step failed: {step_name} - {error}")

    def get_log_path(self) -> Path:
        return self._current_log_file
```

### ProgressTracker Class

Location: `src/sanityops_cli/progress/tracker.py`

```python
class ProgressTracker:
    """Displays step progress with spinner and timing."""

    def __init__(self, console: Console, logger: Logger, verbose: bool = False):
        self.console = console
        self.logger = logger
        self.verbose = verbose
        self._step_times: list[tuple[str, float]] = []
        self._total_start: float = 0

    def step(self, name: str) -> StepContext:
        """Context manager for a single step."""
        return StepContext(self, name)

    def _display_total(self) -> None:
        total = sum(t for _, t in self._step_times)
        self.console.print(f"[dim]{'─' * 30}[/]")
        self.console.print(f"[bold]Total:[/] {total:.2f}s")
```

### StepContext Class

```python
class StepContext:
    """Context manager for tracking a single step."""

    def __init__(self, tracker: ProgressTracker, name: str):
        self.tracker = tracker
        self.name = name
        self._start_time: float = 0

    def __enter__(self) -> StepContext:
        self._start_time = time.perf_counter()
        self.tracker.logger.step_started(self.name)
        # Display spinner based on verbose mode
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration = time.perf_counter() - self._start_time
        if exc_type is None:
            self.tracker.logger.step_completed(self.name, duration)
            # Display success with duration
        else:
            self.tracker.logger.step_failed(self.name, str(exc_val))
            # Display error
        return False  # Don't suppress exceptions
```

---

## Data Flow

```
inspect command starts
    │
    ├─► Logger.initialize()
    │       └─► Create log directory if needed
    │       └─► Open today's log file
    │
    ├─► ProgressTracker.initialize(console, logger, verbose)
    │
    ├─► with tracker.step("Loading configuration..."):
    │       ├─► Logger: "Step started: Loading configuration"
    │       ├─► Execute config loading
    │       └─► Logger: "Step completed: Loading configuration (0.12s)"
    │
    ├─► with tracker.step("Analyzing artifacts..."):
    │       ├─► Logger: "Step started: Analyzing artifacts"
    │       ├─► ScannerAgent.run()
    │       │       └─► ProgressHook logs to DEBUG level
    │       └─► Logger: "Step completed: Analyzing artifacts (7.64s)"
    │
    ├─► with tracker.step("Running defect check..."):
    │       ├─► Logger: "Step started: Running defect check"
    │       ├─► DefectChecker.run()
    │       └─► Logger: "Step completed: Running defect check (5.63s)"
    │
    └─► ProgressTracker.display_total()
```

---

## Testing Considerations

- Unit tests for Logger with mocked file system
- Unit tests for ProgressTracker timing calculations
- Integration tests for verbose mode output capture
- Test log file creation in non-existent directory
- Test concurrent writes to same log file (multiple CLI instances)

---

## Implementation Notes

1. **Rich Status vs Live**: Use `Status` for normal mode (simpler), `Live` for verbose mode (allows dynamic content updates)

2. **ProgressHook integration**: Modify existing `ProgressHook` to log to DEBUG level instead of direct console output when used with ProgressTracker

3. **Error handling**: Wrap each step in try-except within the context manager to ensure proper logging of failures

4. **Log rotation**: Consider implementing log rotation if file size exceeds threshold (future enhancement)

5. **Sensitive data**: Ensure API keys and secrets are not logged (mask in Logger methods)