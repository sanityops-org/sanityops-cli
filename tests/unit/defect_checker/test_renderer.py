"""Unit tests for DefectRenderer."""
from rich.console import Console

from sanityops_cli.defect_checker.renderer import FULL_EXPERIENCE_URL, DefectRenderer


def _result(results, summary=None):
    return {
        "status": "completed",
        "results": results,
        "summary": summary or {
            "total_defects": 0, "p0_count": 0, "p1_count": 0, "p2_count": 0,
            "gate_result": "PASS",
        },
        "errors": [],
        "metadata": {},
    }


def _qds_defect(defect_id, severity, name="n", location="loc", impact="imp", fix="fix"):
    return {
        "id": defect_id, "name": name, "severity": severity,
        "category": "cat", "description": "desc",
        "location": location, "impact": impact, "fix_suggestion": fix,
        "artifact_refs": ["/proj/skills/s.md"],
    }


class TestRender:
    def test_footer_contains_server_url(self):
        console = Console(record=True, width=80)
        DefectRenderer(console).render(_result([]))
        out = console.export_text()
        assert FULL_EXPERIENCE_URL in out
        assert "For the full experience" in out

    def test_shows_summary_counts(self):
        console = Console(record=True, width=80)
        result = _result(
            [],
            summary={
                "total_defects": 5, "p0_count": 1, "p1_count": 2, "p2_count": 2,
                "gate_result": "FAIL",
            },
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Total defects" in out and "5" in out
        assert "Gate" in out and "FAIL" in out

    def test_group_labeled_by_module(self):
        console = Console(record=True, width=80)
        result = _result([
            {
                "module": "QDS", "status": "completed", "artifacts": [],
                "defects": [_qds_defect("d1", "P0")],
            }
        ])
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Skills" in out

    def test_only_two_defects_shown_with_notice(self):
        console = Console(record=True, width=80)
        result = _result([
            {
                "module": "QDS", "status": "completed", "artifacts": [],
                "defects": [
                    _qds_defect("d1", "P0"),
                    _qds_defect("d2", "P1"),
                    _qds_defect("d3", "P2"),
                ],
            }
        ])
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "d1" in out
        assert "d2" in out
        assert "d3" not in out
        assert "1 more defects not shown" in out

    def test_group_without_defects_not_rendered(self):
        console = Console(record=True, width=80)
        result = _result([
            {"module": "QDT", "status": "completed", "artifacts": [], "defects": []}
        ])
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Tools" not in out

    def test_cross_module_ignored(self):
        console = Console(record=True, width=80)
        result = _result([
            {"module": "CROSS", "status": "completed", "artifacts": [], "defects": [_qds_defect("c1", "P0")]}
        ])
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "c1" not in out
