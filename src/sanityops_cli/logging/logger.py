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
"""File-based logging for sanityops-cli operations."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

#: Patterns used to redact secrets before writing to disk.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-***"),
    (re.compile(r"(api[_-]?key\s*[:=]\s*)[^\s\"',}]+", re.IGNORECASE), r"\1***"),
]

__all__ = ["Logger"]


class Logger:
    """Appends timestamped, leveled messages to a dated log file.

    Each instance owns its own stdlib logger and file handler so multiple
    instances (e.g. in tests) do not share handlers.

    Process-scoped usage (the CLI) intentionally relies on interpreter exit to
    flush and close the handler; ``close()`` is provided for long-lived callers
    and tests to release the handle explicitly.
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

    def close(self) -> None:
        """Close and remove the file handler, releasing the open handle.

        Safe to call more than once; after closing, further log calls are
        dropped (no handler remains to write them).
        """
        for handler in self._logger.handlers[:]:
            handler.close()
            self._logger.removeHandler(handler)

    @staticmethod
    def redact(message: str) -> str:
        """Mask API keys and secret-bearing substrings before logging.

        Coverage is intentionally limited to OpenAI-style ``sk-...`` keys and
        ``api_key=`` / ``api-key:`` assignments; other credential formats
        (e.g. AWS, Azure) are not matched and should not be logged.
        """
        for pattern, repl in _SECRET_PATTERNS:
            message = pattern.sub(repl, message)
        return message
