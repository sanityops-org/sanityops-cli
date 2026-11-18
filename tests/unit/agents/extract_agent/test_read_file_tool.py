"""Tests for the root-scoped read tool (design §5.1)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sanityops_cli.agents.extract_agent.tools.read_file_tool import ScopedReadFileTool


def run(tool: ScopedReadFileTool, **kwargs):
    return asyncio.run(tool.run(**kwargs))


@pytest.fixture()
def roots(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "docs").mkdir(parents=True)
    (project / "docs" / "prompt.md").write_text(
        "line-one\nline-two\nline-three\n", encoding="utf-8"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    return project, outside


class TestScoping:
    def test_read_inside_root(self, roots):
        project, _ = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(project / "docs" / "prompt.md"))
        assert result.success
        assert "line-two" in result.content

    def test_read_outside_root_denied(self, roots):
        project, outside = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(outside / "secret.txt"))
        assert not result.success
        assert "outside the allowed roots" in result.error
        # Error lists the allowed roots so the agent can self-correct.
        assert str(project) in result.content

    def test_relative_path_resolves_against_cwd_then_denied(self, roots, monkeypatch):
        project, outside = roots
        monkeypatch.chdir(outside)
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path="secret.txt")
        assert not result.success

    def test_symlink_escape_fails_closed(self, roots, tmp_path: Path):
        project, outside = roots
        link = project / "docs" / "escape.md"
        link.symlink_to(outside / "secret.txt")
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(link))
        assert not result.success
        assert "outside the allowed roots" in result.error

    def test_root_itself_is_readable(self, roots):
        project, _ = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(project))
        assert not result.success  # directory, not a file — but scoping passed
        assert "file not found" in result.error


class TestReading:
    def test_offset_and_limit(self, roots):
        project, _ = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(project / "docs" / "prompt.md"), offset=2, limit=1)
        assert result.success
        assert "line-two" in result.content
        assert "line-one" not in result.content
        assert "showing lines 2-2 of 3" in result.content

    def test_full_read_has_no_note(self, roots):
        project, _ = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(project / "docs" / "prompt.md"))
        assert "showing lines" not in result.content
        assert result.content == "line-one\nline-two\nline-three"

    def test_missing_file(self, roots):
        project, _ = roots
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(project / "docs" / "nope.md"))
        assert not result.success
        assert "file not found" in result.error

    def test_size_limit(self, roots):
        project, _ = roots
        big = project / "docs" / "big.md"
        big.write_text("x" * 4096, encoding="utf-8")
        tool = ScopedReadFileTool(allowed_roots=[project], max_size_bytes=1024)
        result = run(tool, file_path=str(big))
        assert not result.success
        assert "read limit" in result.error

    def test_gbk_fallback(self, roots):
        project, _ = roots
        gbk_file = project / "docs" / "gbk.md"
        gbk_file.write_text("中文提示词", encoding="gbk")
        tool = ScopedReadFileTool(allowed_roots=[project])
        result = run(tool, file_path=str(gbk_file))
        assert result.success
        assert "中文提示词" in result.content
