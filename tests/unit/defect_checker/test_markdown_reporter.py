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

"""Unit tests for markdown_reporter."""

import pytest

from sanityops_cli.defect_checker.markdown_reporter import (
    _esc_md_cell,
    save_markdown_report,
)


def _response(**overrides):
    result = {
        "status": "completed",
        "results": [],
        "summary": {
            "total_defects": 0,
            "p0_count": 0, "p1_count": 0, "p2_count": 0,
            "gate_result": "PASS",
        },
        "errors": [],
        "metadata": {},
    }
    result.update(overrides)
    return result


def _defect(defect_id="d1", name="n", severity="P0", description="desc", location="loc", impact="imp", fix="fix"):
    return {
        "id": defect_id, "name": name, "severity": severity,
        "category": "cat", "description": description,
        "location": location, "impact": impact, "fix_suggestion": fix,
        "artifact_refs": ["/proj/skills/s.md"],
    }


class TestSave:
    def test_save_creates_file_in_output_dir(self, tmp_path):
        response = _response()
        path = save_markdown_report(response, tmp_path)
        assert path.exists()
        assert path.is_file()
        assert path.suffix == ".md"
        # Filename matches inspect-YYYYMMDD-HHMMSS-microseconds.md pattern
        import re
        assert re.match(r"inspect-\d{8}-\d{6}-\d{6}\.md", path.name)

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        response = _response()
        path = save_markdown_report(response, nested)
        assert path.exists()
        assert nested.exists()


class TestReportContent:
    def test_report_contains_summary_table(self, tmp_path):
        response = _response(
            summary={
                "total_defects": 5, "p0_count": 1, "p1_count": 2, "p2_count": 2,
                "gate_result": "FAIL",
            },
        )
        path = save_markdown_report(response, tmp_path, check_level="L2")
        content = path.read_text(encoding="utf-8")
        assert "## Summary" in content
        assert "| Total defects | 5 |" in content
        assert "| Severity | P0: 1 / P1: 2 / P2: 2 |" in content
        assert "| Gate | FAIL |" in content

    def test_report_contains_module_header_and_defect_table(self, tmp_path):
        response = _response(
            results=[
                {
                    "module": "QDS", "status": "completed", "defects": [_defect(defect_id="d1", severity="P0")],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "## Skills (QDS) — completed" in content
        assert "| ID | Name | Severity | Description | Location | Impact | Fix |" in content
        assert "| d1 | n | P0 | desc | loc | imp | fix |" in content

    def test_report_escapes_pipes_and_newlines(self, tmp_path):
        response = _response(
            results=[
                {
                    "module": "QDS", "status": "completed",
                    "defects": [_defect(
                        name="a|b", description="line1\nline2",
                    )],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "a\\|b" in content
        assert "line1<br>line2" in content

    def test_report_includes_meta_and_errors(self, tmp_path):
        response = _response(
            errors=[
                {"code": "E001", "message": "something broke", "retryable": True},
            ],
            metadata={"execution_time_seconds": 12.34},
        )
        path = save_markdown_report(response, tmp_path, project_id="proj-1", check_level="L3")
        content = path.read_text(encoding="utf-8")
        assert "# Inspect Report" in content
        assert "- **Check level**: L3" in content
        assert "- **Project ID**: proj-1" in content
        assert "- **Execution time**: 12.34s" in content
        assert "## Errors" in content
        assert "- **E001** (retryable=True): something broke" in content


class TestEscMdCell:
    def test_none_becomes_dash(self):
        assert _esc_md_cell(None) == "—"

    def test_pipe_escaped(self):
        assert _esc_md_cell("a|b") == "a\\|b"

    def test_newline_becomes_br(self):
        assert _esc_md_cell("a\nb") == "a<br>b"

    def test_html_escaped(self):
        assert _esc_md_cell("<x>&y") == "&lt;x&gt;&amp;y"


class TestExceptionHandling:
    def test_save_raises_on_permission_error(self, tmp_path):
        """Verify that save_markdown_report propagates IO errors."""
        from unittest.mock import patch

        response = _response()
        # Simulate an unwritable directory regardless of platform by mocking the
        # module's Path.write_text to raise PermissionError.
        with patch.object(
            save_markdown_report.__globals__["Path"],
            "write_text",
            side_effect=PermissionError,
        ):
            with pytest.raises(PermissionError):
                save_markdown_report(response, tmp_path)


class TestAggregateCrossDefects:
    def test_empty_input(self):
        """Returns empty list for empty input."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        assert _aggregate_cross_defects([]) == []

    def test_single_cross_result(self):
        """Aggregates defects from a single CROSS result."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PT-1", "severity": "P0", "category": "QD-PT"},
                ]
            }
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 1
        assert result[0] == {
            "defect_id": "QD-PT-1",
            "defect_level": "P0",
            "relation": "QD-PT",
        }

    def test_multiple_cross_results(self):
        """Aggregates defects from multiple CROSS results (PS/PT/ST)."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PS-1", "severity": "P1", "category": "QD-PS"},
                ]
            },
            {
                "defects": [
                    {"id": "QD-PT-2", "severity": "P0", "category": "QD-PT"},
                ]
            },
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 2
        assert result[0]["defect_id"] == "QD-PS-1"
        assert result[1]["defect_id"] == "QD-PT-2"

    def test_skips_non_dict_defects(self):
        """Skips defects that are not dicts."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PT-1", "severity": "P0", "category": "QD-PT"},
                    "invalid",
                    None,
                ]
            }
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 1


class TestCalculateCrossScore:
    def test_empty_input(self):
        """Returns None for empty input."""
        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score
        assert _calculate_cross_score([], "L2") is None

    def test_valid_defects(self):
        """Returns score dict for valid defects.

        This test exercises the real defect-check SDK (a required dependency)
        rather than mocking, to verify the integration works end-to-end.
        """
        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score
        defects = [
            {"defect_id": "QD-PT-1", "defect_level": "P1", "relation": "QD-PT"},
        ]
        result = _calculate_cross_score(defects, "L2")
        # Should return a dict with total_score and gate_result
        assert isinstance(result, dict)
        assert "total_score" in result
        assert "gate_result" in result

    def test_sdk_exception_returns_none(self, caplog):
        """Returns None gracefully when SDK raises exception, logs warning."""
        from unittest.mock import patch

        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score

        defects = [{"defect_id": "x", "defect_level": "P0", "relation": "QD-PT"}]

        # Patch CrossScoringCalculator to raise an exception
        with patch(
            "defect_check.cross.scoring.CrossScoringCalculator.calculate_score",
            side_effect=RuntimeError("SDK error"),
        ):
            result = _calculate_cross_score(defects, "L2")
            assert result is None
            # Verify the warning was logged
            assert "Cross scoring calculation failed" in caplog.text
            assert "SDK error" in caplog.text


class TestCrossArtifactReport:
    def test_cross_module_merged_in_report(self, tmp_path):
        """CROSS sub-results are merged into single section."""
        response = _response(
            results=[
                {
                    "module": "QDS",
                    "status": "completed",
                    "defects": [_defect(defect_id="QDS-1", severity="P1")],
                },
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PT-1", "name": "cross1", "severity": "P0",
                         "description": "d", "location": "l", "impact": "i",
                         "fix_suggestion": "f", "category": "QD-PT"},
                    ],
                },
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Should contain CROSS section with merged results
        assert "## Cross (CROSS)" in content
        assert "QD-PT-1" in content

    def test_multiple_cross_subresults_merged(self, tmp_path):
        """Multiple CROSS sub-results (PS/PT/ST) are merged."""
        response = _response(
            results=[
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PS-1", "name": "ps1", "severity": "P1",
                         "description": "d", "location": "l", "impact": "i",
                         "fix_suggestion": "f", "category": "QD-PS"},
                    ],
                },
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PT-1", "name": "pt1", "severity": "P0",
                         "description": "d", "location": "l", "impact": "i",
                         "fix_suggestion": "f", "category": "QD-PT"},
                    ],
                },
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Should contain only one CROSS section
        assert content.count("## Cross (CROSS)") == 1
        assert "QD-PS-1" in content
        assert "QD-PT-1" in content


class TestPermissionReport:
    """Tests for QD-PM permission defect markdown reporting."""

    def _permission_defect(
        self,
        defect_id="QD-PM-1.1",
        severity="P0",
        name="Permission overflow",
        action="read",
        permission_side="skill -> tool -> params",
        duty_side="skill -> para.3",
        fix="Narrow scope",
    ):
        """Create a permission defect dict for testing."""
        return {
            "id": defect_id,
            "name": name,
            "severity": severity,
            "category": "permission",
            "description": "Permission exceeds duty boundary",
            "fix_suggestion": fix,
            "details": {
                "action": action,
                "permission_side": permission_side,
                "duty_side": duty_side,
            },
        }

    def test_permission_module_uses_extended_table(self, tmp_path):
        """QD-PM defects use extended table with permission columns."""
        response = _response(
            results=[
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "defects": [self._permission_defect()],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "## Permission (QD-PM)" in content
        # Extended table header
        assert "| ID | Name | Severity | Action | Permission Side | Duty Side | Fix |" in content
        # Data row with permission fields
        assert "QD-PM-1.1" in content
        assert "read" in content
        # Note: `->` is HTML-escaped to `-&gt;` by _esc_md_cell
        assert "skill -&gt; tool -&gt; params" in content

    def test_permission_defect_without_details(self, tmp_path):
        """Permission defects without details field render with dashes."""
        response = _response(
            results=[
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "defects": [
                        {
                            "id": "QD-PM-2.1",
                            "name": "Permission issue",
                            "severity": "P1",
                            "category": "permission",
                            "fix_suggestion": "Fix it",
                            # No details dict
                        }
                    ],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "QD-PM-2.1" in content
        # Should still have extended table header
        assert "| Action | Permission Side | Duty Side |" in content
        # Missing fields should show dashes
        assert "—" in content

    def test_permission_defect_with_empty_details(self, tmp_path):
        """Permission defects with empty details dict render gracefully."""
        response = _response(
            results=[
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "defects": [
                        {
                            "id": "QD-PM-3.1",
                            "name": "Permission issue",
                            "severity": "P1",
                            "category": "permission",
                            "fix_suggestion": "Fix it",
                            "details": {},  # Empty dict
                        }
                    ],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "QD-PM-3.1" in content
        # Missing fields should show dashes
        assert "—" in content

    def test_permission_table_multiple_defects(self, tmp_path):
        """Permission table handles multiple defects correctly."""
        response = _response(
            results=[
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "defects": [
                        self._permission_defect(
                            defect_id="QD-PM-1.1",
                            action="read",
                            permission_side="skill -> tool -> params.read",
                        ),
                        self._permission_defect(
                            defect_id="QD-PM-1.2",
                            action="write",
                            permission_side="skill -> tool -> params.write",
                        ),
                    ],
                }
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "QD-PM-1.1" in content
        assert "QD-PM-1.2" in content
        assert "read" in content
        assert "write" in content

    def test_permission_alongside_other_modules(self, tmp_path):
        """Permission module coexists with other modules in report."""
        response = _response(
            results=[
                {
                    "module": "QDS",
                    "status": "completed",
                    "defects": [_defect(defect_id="QDS-1", severity="P1")],
                },
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "defects": [self._permission_defect()],
                },
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Both modules should appear
        assert "## Skills (QDS)" in content
        assert "## Permission (QD-PM)" in content
        # QDS should use standard table
        assert "| Description | Location | Impact |" in content
        # QD-PM should use extended table
        assert "| Action | Permission Side | Duty Side |" in content


class TestFormatPermissionTable:
    """Tests for _format_permission_table helper function."""

    def test_formats_single_defect(self):
        """Formats a single permission defect correctly."""
        from sanityops_cli.defect_checker.markdown_reporter import _format_permission_table

        defects = [
            {
                "id": "QD-PM-1.1",
                "name": "Permission overflow",
                "severity": "P0",
                "fix_suggestion": "Narrow scope",
                "details": {
                    "action": "read",
                    "permission_side": "skill -> tool -> params",
                    "duty_side": "skill -> para.3",
                },
            }
        ]
        lines = _format_permission_table(defects)
        assert len(lines) == 3  # Header + separator + 1 data row
        assert "QD-PM-1.1" in lines[2]
        assert "read" in lines[2]

    def test_formats_multiple_defects(self):
        """Formats multiple permission defects correctly."""
        from sanityops_cli.defect_checker.markdown_reporter import _format_permission_table

        defects = [
            {
                "id": "QD-PM-1.1",
                "name": "First",
                "severity": "P0",
                "details": {"action": "read"},
            },
            {
                "id": "QD-PM-1.2",
                "name": "Second",
                "severity": "P1",
                "details": {"action": "write"},
            },
        ]
        lines = _format_permission_table(defects)
        assert len(lines) == 4  # Header + separator + 2 data rows
        assert "read" in lines[2]
        assert "write" in lines[3]

    def test_handles_missing_details(self):
        """Handles defects without details dict."""
        from sanityops_cli.defect_checker.markdown_reporter import _format_permission_table

        defects = [
            {
                "id": "QD-PM-1.1",
                "name": "No details",
                "severity": "P1",
                "fix_suggestion": "Fix it",
                # No details
            }
        ]
        lines = _format_permission_table(defects)
        assert len(lines) == 3
        assert "—" in lines[2]  # Missing fields show dash
