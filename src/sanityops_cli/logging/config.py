"""Log configuration for deeplogic-cli.

Handles loading and merging of logging configuration from:
1. inspect_config.yaml (file)
2. Environment variables (overrides)
3. CLI parameters (highest priority)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LogConfig:
    """Configuration for deeplogic-cli logging.

    Attributes:
        enabled: Whether logging is enabled globally.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        directory: Directory to store log files.
        retention_days: Days to retain logs (0 = permanent).
        redact_api_keys: Redact API keys in logs.
    """

    enabled: bool = True
    level: str = "INFO"
    directory: Path = field(default_factory=lambda: Path(".deeplogic/logs"))
    retention_days: int = 30
    redact_api_keys: bool = True

    # Runtime overrides (not persisted)
    _cli_level_override: str | None = field(default=None, repr=False, compare=False)
    _cli_dir_override: Path | None = field(default=None, repr=False, compare=False)
    _cli_enabled_override: bool | None = field(default=None, repr=False, compare=False)

    @property
    def effective_level(self) -> str:
        """Get effective log level (CLI override > config > default)."""
        if self._cli_level_override:
            return self._cli_level_override.upper()
        return self.level.upper()

    @property
    def effective_directory(self) -> Path:
        """Get effective log directory (CLI override > config > default)."""
        if self._cli_dir_override:
            return self._cli_dir_override
        return self.directory

    @property
    def effective_enabled(self) -> bool:
        """Get effective enabled state (CLI override > config > default)."""
        if self._cli_enabled_override is not None:
            return self._cli_enabled_override
        return self.enabled

    def apply_cli_overrides(
        self,
        enabled: bool | None = None,
        level: str | None = None,
        directory: Path | None = None,
    ) -> None:
        """Apply CLI parameter overrides.

        Args:
            enabled: Override enabled state (from --log/--no-log).
            level: Override log level (from --log-level).
            directory: Override log directory (from --log-dir).
        """
        if enabled is not None:
            self._cli_enabled_override = enabled
        if level is not None:
            self._cli_level_override = level.upper()
        if directory is not None:
            self._cli_dir_override = directory

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogConfig:
        """Create LogConfig from dictionary (e.g., from YAML).

        Args:
            data: Dictionary with logging configuration.

        Returns:
            LogConfig instance.
        """
        # Handle directory path conversion
        directory = data.get("directory")
        if isinstance(directory, str):
            directory = Path(directory)

        return cls(
            enabled=data.get("enabled", True),
            level=data.get("level", "INFO"),
            directory=directory if directory else Path(".deeplogic/logs"),
            retention_days=data.get("retention_days", 30),
            redact_api_keys=data.get("redact_api_keys", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation (excludes runtime overrides).
        """
        return {
            "enabled": self.enabled,
            "level": self.level,
            "directory": str(self.directory),
            "retention_days": self.retention_days,
            "redact_api_keys": self.redact_api_keys,
        }


def load_log_config(config_path: Path | None = None) -> LogConfig:
    """Load logging configuration from inspect_config.yaml.

    Args:
        config_path: Path to inspect_config.yaml. If None, uses default location.

    Returns:
        LogConfig instance with loaded or default values.
        The log directory is always resolved relative to the config file location.
    """
    if config_path is None:
        # Default location
        config_path = Path.cwd() / ".deeplogic" / "inspect_config.yaml"

    # Default log directory is always relative to config file
    default_log_dir = config_path.parent / "logs"

    if not config_path.exists():
        return LogConfig(directory=default_log_dir)

    try:
        content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
    except (OSError, yaml.YAMLError):
        # Return defaults on error
        return LogConfig(directory=default_log_dir)

    logging_config = data.get("logging")
    if not logging_config:
        return LogConfig(directory=default_log_dir)

    # Resolve directory relative to config file
    if isinstance(logging_config, dict):
        directory = logging_config.get("directory")
        if directory:
            # User specified a directory
            if not Path(directory).is_absolute():
                # Make relative to config file location
                logging_config["directory"] = config_path.parent / directory
        else:
            # No directory specified, use default relative to config file
            logging_config["directory"] = default_log_dir

    return LogConfig.from_dict(logging_config if isinstance(logging_config, dict) else {})
