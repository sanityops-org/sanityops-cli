"""Unit tests for the inspect command defect-check wiring."""
import io

from rich.console import Console
from typer.testing import CliRunner

from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.main import app

runner = CliRunner()


def _findings():
    import tempfile

    from sanityops_cli.agents.scanner_agent.models.finding import (
        Finding,
        FindingsResult,
        FindingType,
        SkillContent,
    )
    # SKILL findings require `relative` to be an absolute directory path,
    # so use mkdtemp rather than a file.
    path = tempfile.mkdtemp()
    skill = Finding(
        type=FindingType.SKILL,
        relative=path,
        content=SkillContent(name="s", description="d", sections=[]),
    )
    return FindingsResult(directory=".", skills=[skill], tools=[], prompts=[])


def test_inspect_skips_defect_check_when_flag_set(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Create a real skill file and a minimal config pointing at it
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n")
    cfg = tmp_path / "inspect_config.yaml"
    cfg.write_text(
        "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
        f"skills:\n  - file: {skill_file}\n"
    )

    called = {"analyze": False, "check": False}

    class FakeAgent:
        def analyze_files_sync(self, prompts, tools, skills):
            called["analyze"] = True
            return _findings()

    monkeypatch.setattr(
        "sanityops_cli.commands.inspect.ScannerAgent",
        lambda *a, **k: FakeAgent(),
    )

    result = runner.invoke(app, ["inspect", "--config", str(cfg), "--skip-defect-check"])
    assert result.exit_code == 0
    assert called["analyze"] is True


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
            # brackets in the message would be eaten as Rich markup if unescaped
            raise RuntimeError("LLM API timeout [a-z]")

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
    assert "LLM API timeout [a-z]" in text
    assert "See log for details" in text
    assert "github.com/sanityops-org/sanityops-cli/issues" in text

    logs = list((tmp_path / ".sanityops" / "logs").glob("sanityops-cli-*.log"))
    assert len(logs) == 1
    assert "Step failed: Analyzing artifacts..." in logs[0].read_text()


def test_inspect_program_error_verbose_shows_single_error_output(monkeypatch, tmp_path):
    """Verbose mode: the failing step collapses to ✗ without a duplicate error report."""
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

    result = runner.invoke(
        app, ["inspect", "--config", str(cfg), "--skip-defect-check", "--verbose"]
    )
    assert result.exit_code == EXIT_FAILURE
    text = output.getvalue()
    # the failing step collapses to a ✗ line inside the Live display
    assert "✗ Analyzing artifacts..." in text
    assert "LLM API timeout" in text
    assert "See log for details" in text
    assert "github.com/sanityops-org/sanityops-cli/issues" in text
    # no duplicate headline: the step collapse already reported the failure
    assert "Error in step" not in text


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


def test_banner_line_contains_version_python_and_platform():
    import platform

    from sanityops_cli import __version__
    from sanityops_cli.commands.inspect import _banner_line

    line = _banner_line()
    assert f"sanityops-cli v{__version__}" in line
    assert platform.python_version() in line
    assert "|" in line


def test_inspect_prints_banner_before_project_id(monkeypatch, tmp_path):
    """The run banner should appear directly before the Project ID line."""
    from sanityops_cli import __version__

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

    output = io.StringIO()
    test_console = Console(file=output, record=True)
    monkeypatch.setattr("sanityops_cli.commands.inspect.console", test_console)

    result = runner.invoke(app, ["inspect", "--config", str(cfg), "--skip-defect-check"])
    assert result.exit_code == 0
    text = output.getvalue()
    assert f"sanityops-cli v{__version__}" in text
    assert "Project ID: 00000000-0000-0000-0000-000000000000" in text
    # the Project ID line must immediately follow the banner line (no intervening output)
    lines = text.splitlines()
    banner_line_idx = next(
        i for i, line in enumerate(lines) if f"sanityops-cli v{__version__}" in line
    )
    assert (
        "Project ID: 00000000-0000-0000-0000-000000000000"
        in lines[banner_line_idx + 1]
    )
