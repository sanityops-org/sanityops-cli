"""Tests for the write_report incremental assembly tool (design §6.3)."""

from __future__ import annotations

import asyncio

from sanityops_cli.agents.inspect_agent.tools.write_report_tool import (
    MAX_SECTION_CHARS,
    WriteReportTool,
)


def run(tool: WriteReportTool, **kwargs):
    return asyncio.run(tool.run(**kwargs))


class TestAssembly:
    def test_fixed_order_regardless_of_arrival(self):
        tool = WriteReportTool()
        run(tool, section="G", content="stage-g")
        run(tool, section="header", content="the-header")
        run(tool, section="A", content="stage-a")
        rendered = tool.render()
        assert rendered.index("the-header") < rendered.index("stage-a") < rendered.index("stage-g")

    def test_parts_appended_in_order(self):
        tool = WriteReportTool()
        run(tool, section="A", content="part-1")
        run(tool, section="A", content="part-2")
        rendered = tool.render()
        assert "part-1\n\npart-2" in rendered

    def test_replace_part_rewrites_last(self):
        tool = WriteReportTool()
        run(tool, section="G", content="draft")
        run(tool, section="G", content="reconciled", replace_part=True)
        rendered = tool.render()
        assert "reconciled" in rendered
        assert "draft" not in rendered
        assert tool.section_parts()["G"] == ["reconciled"]

    def test_replace_part_on_empty_section_appends(self):
        tool = WriteReportTool()
        run(tool, section="B", content="fresh", replace_part=True)
        assert tool.section_parts()["B"] == ["fresh"]


class TestValidation:
    def test_unknown_section_rejected(self):
        tool = WriteReportTool()
        result = run(tool, section="H", content="x")
        assert not result.success
        assert "section must be one of" in result.error

    def test_empty_content_rejected(self):
        tool = WriteReportTool()
        result = run(tool, section="A", content="")
        assert not result.success

    def test_oversized_content_rejected(self):
        tool = WriteReportTool()
        result = run(tool, section="A", content="x" * (MAX_SECTION_CHARS + 1))
        assert not result.success
        assert "split into parts" in result.error


class TestStageCompleteness:
    def test_missing_stages_reported(self):
        tool = WriteReportTool()
        run(tool, section="header", content="h")
        run(tool, section="A", content="a")
        run(tool, section="C", content="c")
        assert tool.missing_stages() == ["B", "D", "E", "F", "G"]

    def test_all_stages_present(self):
        tool = WriteReportTool()
        for stage in "ABCDEFG":
            run(tool, section=stage, content=f"stage-{stage}")
        assert tool.missing_stages() == []

    def test_not_executed_part_counts(self):
        tool = WriteReportTool()
        run(tool, section="B", content="Stage B: Not Executed — collection mode")
        # A "Not Executed" part satisfies the stage gate; only B was written.
        assert tool.missing_stages() == ["A", "C", "D", "E", "F", "G"]
