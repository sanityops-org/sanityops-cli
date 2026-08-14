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
