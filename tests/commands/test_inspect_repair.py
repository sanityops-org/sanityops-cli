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

from pathlib import Path

from typer.testing import CliRunner

from sanityops_cli.commands.inspect import inspect_app

runner = CliRunner()


class TestFindLatestReport:
    """Tests for _find_latest_report helper."""

    def test_returns_none_when_dir_not_exists(self, tmp_path: Path):
        """Returns None when results directory does not exist."""
        from sanityops_cli.commands.inspect import _find_latest_report
        result = _find_latest_report(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_when_no_reports(self, tmp_path: Path):
        """Returns None when no inspect reports exist."""
        from sanityops_cli.commands.inspect import _find_latest_report
        (tmp_path / "results").mkdir()
        result = _find_latest_report(tmp_path / "results")
        assert result is None

    def test_returns_newest_report(self, tmp_path: Path):
        """Returns the most recently modified report."""
        import time

        from sanityops_cli.commands.inspect import _find_latest_report

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create two reports with different mtimes
        old_report = results_dir / "inspect-20260919-100000.md"
        new_report = results_dir / "inspect-20260920-100000.md"
        old_report.write_text("# Old Report")
        new_report.write_text("# New Report")

        # Ensure different mtimes
        time.sleep(0.1)
        new_report.touch()

        result = _find_latest_report(results_dir)
        assert result == new_report


class TestWriteRepairsMarkdown:
    """Tests for _write_repairs_markdown helper."""

    def test_creates_output_file(self, tmp_path: Path):
        """Creates output file with correct structure."""

        from sanityops_cli.commands.inspect import _write_repairs_markdown

        repairs = [
            {
                "artifact_type": "prompt",
                "artifact_path": "/abs/path/prompt.md",
                "repaired_content": "# Fixed content",
                "summary": "Fixed all issues",
            }
        ]

        output_dir = tmp_path / "repairs"
        report_path = tmp_path / "results" / "inspect-20260920.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Report")

        result = _write_repairs_markdown(
            repairs,
            output_dir,
            report_path=report_path,
            project_id="test-project",
        )

        assert result.exists()
        assert result.suffix == ".md"
        content = result.read_text()
        assert "# Repair Report" in content
        assert "test-project" in content
        assert "/abs/path/prompt.md" in content
        assert "Fixed all issues" in content
        assert "# Fixed content" in content

    def test_creates_output_directory(self, tmp_path: Path):
        """Creates output directory if it does not exist."""
        from sanityops_cli.commands.inspect import _write_repairs_markdown

        repairs = [
            {
                "artifact_type": "skill",
                "artifact_path": "/abs/path/skill.md",
                "repaired_content": "content",
                "summary": "summary",
            }
        ]

        output_dir = tmp_path / "new" / "repairs"
        report_path = tmp_path / "report.md"
        report_path.write_text("# Report")

        result = _write_repairs_markdown(
            repairs,
            output_dir,
            report_path=report_path,
            project_id=None,
        )

        assert output_dir.exists()
        assert result.exists()


class TestInspectRepairCommand:
    """Integration tests for inspect repair command."""

    def test_repair_command_shows_help(self):
        """Repair command shows help without error."""
        result = runner.invoke(inspect_app, ["repair", "--help"])
        assert result.exit_code == 0
        assert "repair" in result.output.lower()

    def test_repair_command_requires_config_or_report(self, tmp_path: Path, monkeypatch):
        """Repair command fails gracefully when no config exists."""
        # Change to temp directory with no config
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(inspect_app, ["repair"])
        # Should fail because no config exists
        assert result.exit_code != 0
