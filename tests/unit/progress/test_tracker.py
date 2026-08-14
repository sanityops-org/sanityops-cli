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
            step.console.print("  [dim]detail line[/]")
            assert step._live_console._lines[0].plain == "  detail line"
        text = console.export_text()
        assert "Analyzing artifacts..." in text
        # detail lines collapse on completion; only the summary remains
        assert "detail line" not in text

    def test_verbose_live_console_merges_multiple_objects(self, tmp_path):
        tracker, console, _ = self._tracker(tmp_path, verbose=True)
        step = tracker.step("Analyzing artifacts...")
        with step:
            step.console.print("a", "b")
            assert step._live_console._lines[-1].plain == "a b"
