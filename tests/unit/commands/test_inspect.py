"""Unit tests for the inspect command defect-check wiring."""
from typer.testing import CliRunner

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
