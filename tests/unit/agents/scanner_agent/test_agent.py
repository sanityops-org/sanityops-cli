"""Unit tests for ScannerAgent construction and logger passthrough."""

from types import SimpleNamespace

import pytest
from rich.console import Console

from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.agents.scanner_agent.hooks.progress_hook import ProgressHook
from sanityops_cli.agents.scanner_agent.models.finding import FindingType
from sanityops_cli.logging.logger import Logger


class _SpyProgressHook:
    """Records the logger passed at construction, then delegates to the real hook.

    The real ``ProgressHook`` is captured at import time (before the test
    monkeypatches the module attribute), so delegation doesn't recurse.
    """

    constructed_loggers: list = []

    def __init__(self, console, verbose=True, logger=None):
        _SpyProgressHook.constructed_loggers.append(logger)
        self._delegate = ProgressHook(console, verbose=verbose, logger=logger)

    def __getattr__(self, name):
        return getattr(self._delegate, name)


class _FakeParentAgent:
    def __init__(self):
        from sanityops_agent.core.agent import TerminationReason

        self.result = SimpleNamespace(
            termination_reason=TerminationReason.END_TURN,
            error=None,
            error_detail=None,
            time_elapsed=0.0,
            loops_used=0,
            tokens_used=0,
        )

    async def run(self, prompt):
        return self.result


class _FakeAgentFactory:
    """Builds the real registry but returns a fake parent agent."""

    def __init__(self, **kwargs):
        pass

    def create_parent_agent(self, system_prompt="", **kwargs):
        return _FakeParentAgent()


class TestScannerAgent:
    def test_accepts_logger_and_console(self, tmp_path):
        console = Console(record=True)
        logger = Logger(tmp_path)
        agent = ScannerAgent(provider=object(), verbose=True, console=console, logger=logger)
        assert agent.logger is logger
        assert agent.console is console

    def _agent(self, tmp_path, logger):
        return ScannerAgent(
            provider=object(), verbose=True, console=Console(), logger=logger
        )

    @pytest.mark.anyio
    async def test_scan_forwards_logger_to_progress_hook(self, tmp_path, monkeypatch):
        _SpyProgressHook.constructed_loggers = []
        monkeypatch.setattr(
            "sanityops_cli.agents.scanner_agent.hooks.progress_hook.ProgressHook",
            _SpyProgressHook,
        )
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        logger = Logger(tmp_path)
        result = await self._agent(tmp_path, logger).scan(str(tmp_path))
        assert _SpyProgressHook.constructed_loggers == [logger]
        assert result.skills == []

    @pytest.mark.anyio
    async def test_analyze_files_forwards_logger_to_progress_hook(
        self, tmp_path, monkeypatch
    ):
        _SpyProgressHook.constructed_loggers = []
        monkeypatch.setattr(
            "sanityops_cli.agents.scanner_agent.hooks.progress_hook.ProgressHook",
            _SpyProgressHook,
        )
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n")
        logger = Logger(tmp_path)
        result = await self._agent(tmp_path, logger).analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )
        assert _SpyProgressHook.constructed_loggers == [logger]
        # Deterministic capture: skill file is read from disk and populated
        assert len(result.skills) == 1
        assert result.skills[0].type == FindingType.SKILL
        assert result.skills[0].relative == str(skill_file)
        skill_content = result.skills[0].content
        assert skill_content is not None
        assert skill_content.name == "s"
        assert skill_content.description == "d"
