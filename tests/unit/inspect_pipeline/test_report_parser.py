"""Tests for the fail-closed tail-JSON ladder (design §6.4)."""

from __future__ import annotations

import json

from sanityops_cli.inspect_pipeline.report_parser import parse_summary

TAIL_OK = (
    "preceding prose\n<!-- inspect-summary -->\n"
    + json.dumps(
        {
            "status": "completed",
            "stages": {"A": "executed", "B": "not executed — collection mode"},
            "counts": {
                "inspect": {"p0": 1, "p1": 0, "p2": 1},
                "risk_explicit": {"p0": 0, "p1": 1, "p2": 0},
            },
            "findings": [
                {
                    "stage": "A",
                    "module": "QD-P",
                    "artifact": "system",
                    "id": "QD-P-2.2.1",
                    "severity": "P0",
                    "description": "x" * 200,
                },
                {
                    "stage": "A",
                    "module": "QC",
                    "artifact": "system",
                    "id": "QC-3.3",
                    "severity": "P2",
                    "description": "weak demo value",
                },
                {
                    "stage": "E",
                    "module": "EX",
                    "artifact": "system",
                    "id": "EX-NL-A",
                    "severity": "P1",
                    "description": "explicit risk",
                },
            ],
        }
    )
    + "\n<!-- /inspect-summary -->\ntrailing"
)

SECTIONS = {
    "header": ["# Report"],
    "A": ["## Stage A\n[P0] QD-P-2.2.1 system: contradiction"],
    "B": ["Stage B: Not Executed — collection mode"],
}


class TestTailParsing:
    def test_valid_tail_parsed(self):
        parsed = parse_summary(TAIL_OK, SECTIONS)
        assert parsed.source == "tail"
        assert parsed.status == "completed"
        assert parsed.counts["inspect"]["p0"] == 1
        assert parsed.counts["risk_explicit"]["p1"] == 1
        assert len(parsed.findings) == 3
        assert parsed.findings[0]["description"] == "x" * 120  # clamped
        assert parsed.stages["B"] == "not executed — collection mode"
        assert parsed.warnings == []

    def test_counts_cross_validated_findings_win(self):
        tail = TAIL_OK.replace('"p0": 1, "p1": 0, "p2": 1', '"p0": 9, "p1": 0, "p2": 1')
        parsed = parse_summary(tail, SECTIONS)
        assert parsed.counts["inspect"]["p0"] == 1  # findings-derived
        assert any("inconsistent" in w for w in parsed.warnings)

    def test_missing_stage_overrides_stages(self):
        parsed = parse_summary(TAIL_OK, SECTIONS, missing_stages=["C"])
        assert parsed.stages["C"] == "NOT RECEIVED — agent did not emit this stage"

    def test_unknown_severity_dropped_with_warning(self):
        tail = TAIL_OK.replace('"severity": "P0"', '"severity": "P9"')
        parsed = parse_summary(tail, SECTIONS)
        assert all(f["severity"] != "P9" for f in parsed.findings)
        assert any("unknown severity" in w for w in parsed.warnings)


class TestFailClosedLadder:
    def test_malformed_tail_recomputes_from_sections(self):
        tail = TAIL_OK.replace(
            '"status": "completed"', '"status": completed'
        )  # invalid JSON, markers intact
        parsed = parse_summary(tail, SECTIONS)
        assert parsed.source == "sections"
        assert parsed.status == "completed"
        assert parsed.counts["inspect"]["p0"] == 1
        assert any("malformed" in w for w in parsed.warnings)

    def test_missing_tail_with_sections_recomputes(self):
        parsed = parse_summary("no tail here", SECTIONS)
        assert parsed.source == "sections"
        assert parsed.status == "completed"
        assert parsed.counts["inspect"]["p0"] == 1
        assert any("missing" in w for w in parsed.warnings)

    def test_no_tail_no_sections_is_failed(self):
        parsed = parse_summary("", {})
        assert parsed.source == "none"
        assert parsed.status == "failed"

    def test_empty_findings_ok(self):
        tail = (
            "<!-- inspect-summary -->\n"
            + json.dumps({"status": "completed", "stages": {}, "counts": {}, "findings": []})
            + "\n<!-- /inspect-summary -->"
        )
        parsed = parse_summary(tail, SECTIONS)
        assert parsed.status == "completed"
        assert parsed.counts["inspect"]["p0"] == 0


class TestSectionScan:
    def test_severity_and_module_extracted(self):
        parts = {"A": ["- **P0** QD-S-1.2 missing sidecar — description here"]}
        parsed = parse_summary("", parts)
        assert parsed.findings[0]["module"] == "QD-S"
        assert parsed.findings[0]["severity"] == "P0"
        assert parsed.findings[0]["stage"] == "A"

    def test_scan_capped_at_20(self):
        lines = [f"- P0 QD-P-{i} finding {i}" for i in range(30)]
        parsed = parse_summary("", {"A": ["\n".join(lines)]})
        assert len(parsed.findings) == 20
