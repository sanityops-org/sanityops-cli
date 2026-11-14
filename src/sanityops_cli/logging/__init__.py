"""Logging module for sanityops-cli.

Provides structured logging for command execution.

Usage:
    from sanityops_cli.logging import LogManager, LogConfig

    config = LogConfig(enabled=True, level="INFO")
    manager = LogManager(config, command="inspect")
    manager.start_session()
    manager.info("agent", "ScannerAgent started")
    manager.end_session("success", {"duration": 30.5})
"""

from sanityops_cli.logging.config import LogConfig, load_log_config
from sanityops_cli.logging.manager import LogManager

__all__ = [
    "LogConfig",
    "LogManager",
    "load_log_config",
]
