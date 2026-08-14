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
