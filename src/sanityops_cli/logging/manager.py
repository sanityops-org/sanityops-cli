"""Log Manager - unified logging interface for deeplogic-cli.

Manages log sessions and provides a simple API for logging throughout the CLI.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from deeplogic_cli.logging.config import LogConfig


class LogManager:
    """Unified log manager for deeplogic-cli commands.

    Provides a single interface for logging operations.

    Usage:
        config = LogConfig()
        manager = LogManager(config, command="inspect")
        manager.start_session()
        manager.info("agent", "ScannerAgent started")
        manager.end_session("success", {"duration": 30.5})
    """

    # Log level mapping
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(
        self,
        config: LogConfig,
        command: str,
        console_sink: Any | None = None,
    ):
        """Initialize the log manager.

        Args:
            config: LogConfig instance with logging settings.
            command: Command name (e.g., "inspect", "project.push").
            console_sink: Optional callable for console output (for verbose mode).
        """
        self.config = config
        self.command = command
        self.console_sink = console_sink

        # Session state
        self._session_id: str | None = None
        self._session_start: datetime | None = None
        self._log_dir: Path | None = None
        self._log_file: Path | None = None
        self._file_handler: logging.FileHandler | None = None
        self._logger: logging.Logger | None = None

        # Counters for summary
        self._tool_calls = 0
        self._errors: list[str] = []

    @property
    def is_enabled(self) -> bool:
        """Check if logging is enabled."""
        return self.config.effective_enabled

    @property
    def session_id(self) -> str | None:
        """Get current session ID (timestamp-based)."""
        return self._session_id

    @property
    def log_file(self) -> Path | None:
        """Get current log file path."""
        return self._log_file

    def start_session(self) -> Path | None:
        """Start a new logging session.

        Creates log directory and file, initializes handlers.

        Returns:
            Path to the log file, or None if logging is disabled.
        """
        if not self.is_enabled:
            return None

        # Generate session ID (timestamp)
        self._session_start = datetime.now()
        self._session_id = self._session_start.strftime("%H%M%S")

        # Create log directory structure
        date_dir = self._session_start.strftime("%Y-%m-%d")
        self._log_dir = self.config.effective_directory / self.command / date_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Create execution log file
        self._log_file = self._log_dir / f"{self.command}-{self._session_id}.log"

        # Setup Python logger
        self._setup_logger()

        # Log session start
        self.log("session", "INFO", f"Command started: {self.command}")

        return self._log_file

    def _setup_logger(self) -> None:
        """Setup Python logging infrastructure."""
        if self._log_file is None:
            return

        # Create logger
        self._logger = logging.getLogger(f"deeplogic_cli.{self.command}.{self._session_id}")
        self._logger.setLevel(self.LEVEL_MAP.get(self.config.effective_level, logging.INFO))

        # Remove existing handlers
        self._logger.handlers.clear()

        # Create file handler
        self._file_handler = logging.FileHandler(self._log_file, encoding="utf-8")
        self._file_handler.setLevel(self._logger.level)

        # Set format with custom formatter for category support
        self._file_handler.setFormatter(_CategoryFormatter())
        self._logger.addHandler(self._file_handler)

        # Prevent propagation to root logger
        self._logger.propagate = False

    def log(
        self,
        category: str,
        level: str,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Log a message.

        Args:
            category: Log category (e.g., "agent", "tool", "config").
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: Log message.
            **kwargs: Additional context to include.
        """
        if not self.is_enabled or self._logger is None:
            return

        # Get log level
        log_level = self.LEVEL_MAP.get(level.upper(), logging.INFO)

        # Skip if below configured level
        if log_level < self._logger.level:
            return

        # Format extra context
        extra = {"category": category}
        if kwargs:
            context_str = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} | {context_str}"

        # Log to file
        self._logger.log(log_level, message, extra=extra)

        # Also output to console if sink is provided and verbose
        if self.console_sink and level.upper() in ("DEBUG", "INFO"):
            self.console_sink(f"[{category}] {message}")

    def debug(self, category: str, message: str, **kwargs: Any) -> None:
        """Log a DEBUG message."""
        self.log(category, "DEBUG", message, **kwargs)

    def info(self, category: str, message: str, **kwargs: Any) -> None:
        """Log an INFO message."""
        self.log(category, "INFO", message, **kwargs)

    def warning(self, category: str, message: str, **kwargs: Any) -> None:
        """Log a WARNING message."""
        self.log(category, "WARNING", message, **kwargs)

    def error(self, category: str, message: str, **kwargs: Any) -> None:
        """Log an ERROR message."""
        self.log(category, "ERROR", message, **kwargs)
        self._errors.append(message)

    def exception(
        self, category: str, message: str, exc: Exception | None = None, **kwargs: Any
    ) -> None:
        """Log an ERROR message with full traceback.

        This method should be called inside an except block.
        If exc is not provided, it uses sys.exc_info() to get the current exception.

        Args:
            category: Log category (e.g., "agent", "defect", "config").
            message: Error description.
            exc: Optional exception instance. If None, uses current exception.
            **kwargs: Additional context to include.
        """
        import sys
        import traceback

        # Get exception info
        if exc is None:
            exc_type, exc_value, exc_tb = sys.exc_info()
        else:
            exc_type = type(exc)
            exc_value = exc
            exc_tb = exc.__traceback__

        # Format traceback
        if exc_type is None:
            tb_text = "No active exception"
        elif exc_tb is not None:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            tb_text = "".join(tb_lines)
        else:
            # No traceback available (e.g., manually constructed exception)
            tb_text = f"{exc_type.__name__}: {exc_value}"

        # Log main error message
        self.error(category, message, **kwargs)

        # Log traceback with multi-line support
        if self._logger:
            # Split traceback into lines for structured logging
            for line in tb_text.strip().split("\n"):
                self._logger.log(
                    logging.ERROR,
                    f"  {line}",
                    extra={"category": f"{category}_traceback"},
                )

    def log_tool_call(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        output_summary: str | None,
        duration_ms: float,
    ) -> None:
        """Log a tool execution.

        Args:
            tool_name: Name of the tool.
            input_data: Tool input parameters.
            output_summary: Brief summary of output.
            duration_ms: Execution duration in milliseconds.
        """
        self._tool_calls += 1

        # Redact sensitive data if configured
        safe_input = self._redact_if_needed(input_data)

        self.debug(
            "tool",
            f"Executed: {tool_name}",
            input=_truncate(str(safe_input), 100),
            duration=f"{duration_ms:.0f}ms",
            output=output_summary,
        )

    def end_session(
        self,
        status: str,
        summary: dict[str, Any] | None = None,
    ) -> None:
        """End the current logging session.

        Args:
            status: Session end status (success, failed, partial).
            summary: Optional summary metrics.
        """
        if not self.is_enabled or self._logger is None:
            return

        # Calculate duration
        duration = 0.0
        if self._session_start:
            duration = (datetime.now() - self._session_start).total_seconds()

        # Build summary
        final_summary = {
            "duration": f"{duration:.1f}s",
            "tool_calls": self._tool_calls,
            "errors": len(self._errors),
        }
        if summary:
            final_summary.update(summary)

        # Log session end
        self.log(
            "session",
            "INFO" if status == "success" else "WARNING",
            f"Command completed: {self.command}",
            status=status,
            **final_summary,
        )

        # Cleanup
        self._cleanup()

    def _cleanup(self) -> None:
        """Cleanup logging resources."""
        # Cleanup file handler
        if self._file_handler:
            self._file_handler.close()
            if self._logger:
                self._logger.removeHandler(self._file_handler)
            self._file_handler = None

    def _redact_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive information if configured.

        Args:
            data: Data dictionary to redact.

        Returns:
            Redacted copy of data.
        """
        if not self.config.redact_api_keys:
            return data

        # Keys to redact (case-insensitive matching)
        sensitive_keys = {
            "api_key",
            "apikey",
            "token",
            "secret",
            "password",
            "credential",
        }

        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                if isinstance(value, str) and len(value) > 8:
                    # Show first 4 and last 4 characters
                    result[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    result[key] = "[REDACTED]"
            else:
                result[key] = value

        return result


class _CategoryFormatter(logging.Formatter):
    """Custom formatter that supports 'category' field."""

    def __init__(self):
        """Initialize with the standard format."""
        super().__init__(
            fmt="%(asctime)s.%(msecs)03d [%(levelname)s] [%(category)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with category support."""
        # Get category from extra, default to 'general'
        category = getattr(record, "category", "general")
        record.category = category
        return super().format(record)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len with ellipsis.

    Args:
        text: Text to truncate.
        max_len: Maximum length.

    Returns:
        Truncated text.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
