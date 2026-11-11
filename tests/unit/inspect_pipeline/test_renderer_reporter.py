"""Tests for the terminal renderer and report persistence (design §8)."""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

from sanityops_cli.inspect_pipeline.markdown_reporter import (
    assemble_report,
    save_inspection_report,
)
from sanityops_cli.inspect_pipeline.renderer import render_inspection_summary
from sanityops_cli.inspect_pipeline.report_parser import ParsedSummary


def summary(**overrides) -> ParsedSummary:
    base = dict(
        status="completed",
        counts={
            "inspect": {"p0": 1, "p1": 0, "p2": 1},
            "risk_explicit": {"p0": 1, "p1": 0, "p2": 0},
        },
        findings=[
            {
                "stage": "A",
                "module": "QD-P",
                "artifact": "system",
                "id": "QD-P-2.2.1",
                "severity": "P0",
                "description": "contradiction",
            },
            {
                "stage": "A",
                "module": "QD-P",
                "artifact": "system",
                "id": "QD-P-1.1",
                "severity": "P2",
                "description": "minor",
            },
            {
                "stage": "A",
                "module": "QD-T",
                "artifact": "search",
                "id": "QD-T-3.1",
                "severity": "P2",
                "description": "schema",
            },
            {
                "stage": "B",
                "module": "QD-PS",
                "artifact": ["system", "search"],
                "id": "QD-PS-2",
                "severity": "P1",
                "description": "mismatch",
            },
            {
                "stage": "E",
                "module": "EX",
                "artifact": "search",
                "id": "EX-NL-A",
                "severity": "P0",
                "description": "dangerous op",
            },
        ],
        stages={"A": "executed", "B": "executed"},
        warnings=["summary block missing; recomputing from sections"],
        source="sections",
    )
    base.update(overrides)
    return ParsedSummary(**base)


class TestRenderer:
    def test_renders_panels_and_counts(self):
        console = Console(record=True, width=120)
        render_inspection_summary(console, summary())
        text = console.export_text()
        assert "Inspect" in text and "P0: 1" in text
        assert "Stage A — QD-P" in text
        assert "QD-P-2.2.1" in text
        assert "Stage B — Cross" in text
        assert "Stage E — Explicit Risk" in text
        assert "not a defect verdict" in text

    def test_top3_truncation_is_deterministic(self):
        findings = [
            {
                "stage": "A",
                "module": "QD-P",
                "artifact": "a",
                "id": f"QD-P-{i}",
                "severity": "P1",
                "description": f"f{i}",
            }
            for i in range(5, 0, -1)
        ]
        console = Console(record=True, width=120)
        render_inspection_summary(console, summary(findings=findings))
        text = console.export_text()
        # sorted by id: QD-P-1..3 shown, 4-5 elided
        assert "QD-P-1" in text and "QD-P-3" in text
        assert "QD-P-4" not in text
        assert "+2 more" in text

    def test_explicit_p0_red_border(self):
        console = Console(record=True, width=120, force_terminal=True, color_system="truecolor")
        render_inspection_summary(console, summary())
        html = console.export_text(styles=True)
        # bold-red explicit-signal line and red panel borders in ANSI
        assert "\x1b[1;31m" in html

    def test_stage_f_only_verbose(self):
        console = Console(record=True, width=120)
        render_inspection_summary(console, summary())
        assert "Impact mapping" not in console.export_text()

        console2 = Console(record=True, width=120)
        render_inspection_summary(console2, summary(), verbose=True)
        assert "Impact mapping" in console2.export_text()

    def test_warnings_and_failed_status(self):
        console = Console(record=True, width=120)
        render_inspection_summary(console, summary(status="failed"))
        text = console.export_text()
        assert "⚠" in text
        assert "inspection incomplete" in text


class TestAssembleReport:
    def test_fixed_order_with_placeholders(self):
        text = assemble_report(
            section_parts={"A": ["stage A text"], "header": ["# R"]},
            missing_stages=["B", "C"],
            tail_block="<!-- inspect-summary -->{}<!-- /inspect-summary -->",
            meta={"model": "m", "date": "2026-11-06"},
        )
        assert text.index("# R") < text.index("stage A text")
        assert "NOT RECEIVED — agent did not emit this stage" in text
        assert text.rstrip().endswith("<!-- /inspect-summary -->")
        assert "- model: m" in text

    def test_nonstage_sections_not_placeholdered(self):
        text = assemble_report(section_parts={"A": ["a"]}, missing_stages=[], tail_block=None)
        # status_board/self_verification absent and NOT stage sections → no placeholder
        assert text.count("NOT RECEIVED") == 0

    def test_extra_sections_appended(self):
        text = assemble_report(
            section_parts={"A": ["## Stage A"], "appendix": ["## Appendix Notes"]},
            missing_stages=[],
            tail_block=None,
        )
        assert "## Stage A" in text
        assert "## Appendix Notes" in text
        assert text.index("## Stage A") < text.index("## Appendix Notes")


class TestSaveReport:
    def test_writes_timestamped_file(self, tmp_path: Path):
        path = save_inspection_report(
            {"A": ["a"]}, ["B"], "<!-- tail -->", tmp_path, meta={"model": "m"}
        )
        assert path.parent == tmp_path
        assert re.match(r"inspect-\d{8}-\d{6}\.md", path.name)
        content = path.read_text(encoding="utf-8")
        assert "stage a" in content.lower() or "a" in content

    def test_respects_explicit_timestamp(self, tmp_path: Path):
        path = save_inspection_report(
            {"A": ["a"]},
            [],
            None,
            tmp_path,
            timestamp="20261110-203500-2",
        )
        assert path == tmp_path / "inspect-20261110-203500-2.md"
