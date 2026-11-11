"""Tests for the vendored-skill runtime (materialize + SkillManager assembly)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sanityops_agent.tools.registry import ToolRegistry

from sanityops_cli.inspect_pipeline import skill_runtime

SRC = Path(__file__).resolve().parents[3] / "src" / "sanityops_cli" / "skills"


class TestMaterialize:
    def test_materializes_both_skills(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert (target / "sanityops-inspect-lite" / "SKILL.md").is_file()
        assert (target / "pre-inspect-extract" / "SKILL.md").is_file()
        assert (target / "code-contract-checklist.v2.md").is_file()

    def test_idempotent_same_content(self, tmp_path: Path) -> None:
        first = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        second = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert first == second

    def test_new_key_when_content_changes(self, tmp_path: Path) -> None:
        first = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        mutated = tmp_path / "src-copy"
        import shutil

        shutil.copytree(SRC, mutated)
        (mutated / "pre-inspect-extract" / "SKILL.md").write_text(
            (mutated / "pre-inspect-extract" / "SKILL.md").read_text(encoding="utf-8")
            + "\n<!-- mutated -->",
            encoding="utf-8",
        )
        second = skill_runtime.materialize_skills(source=mutated, cache_root=tmp_path)
        assert first != second

    def test_reuses_cache_entry_unchanged(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        marker = target / "VERSION.json"
        before = marker.read_bytes()
        # Corrupt a file, then re-materialize: hash mismatch → rebuilt from src.
        marker.write_bytes(b"corrupted")
        skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert marker.read_bytes() == before


class TestPackagedDir:
    def test_packaged_skills_dir_resolves(self) -> None:
        path = skill_runtime.packaged_skills_dir()
        assert path.is_dir()
        assert (path / "VERSION.json").is_file()

    def test_vendored_checklist_matches_17_rule_index(self) -> None:
        checklist = (SRC / "code-contract-checklist.v2.md").read_text(encoding="utf-8")
        ids = set(_QC_IDS(checklist))
        expected = {
            "QC-0.1",
            "QC-0.2",
            "QC-0.3",
            "QC-0.4",
            "QC-0.5",
            "QC-1.1",
            "QC-1.2",
            "QC-1.3",
            "QC-1.4",
            "QC-2.1",
            "QC-2.2",
            "QC-2.3",
            "QC-3.1",
            "QC-3.2",
            "QC-3.3",
            "QC-4.1",
            "QC-4.2",
        }
        assert ids == expected


class TestValidateVendor:
    def test_clean_vendor_has_no_warnings(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert skill_runtime.validate_vendor(target) == []

    def test_warns_on_frontmatter_version_mismatch(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        skill_md = target / "sanityops-inspect-lite" / "SKILL.md"
        current_version = skill_runtime._frontmatter_version(skill_md)
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8").replace(
                f"version: {current_version}", "version: 9.9.9", 1
            ),
            encoding="utf-8",
        )
        warnings = skill_runtime.validate_vendor(target)
        assert any("frontmatter version" in w for w in warnings)

    def test_warns_when_skill_missing(self, tmp_path: Path) -> None:
        import shutil

        partial = tmp_path / "partial"
        shutil.copytree(SRC, partial)
        shutil.rmtree(partial / "pre-inspect-extract")
        warnings = skill_runtime.validate_vendor(partial)
        assert any("'pre-inspect-extract' missing" in w for w in warnings)


class TestAttachSkillTools:
    def test_registry_gets_skill_manager_and_tool(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        registry = ToolRegistry()
        manager = skill_runtime.attach_skill_tools(registry, target)
        assert registry.context.skill_manager is manager
        assert registry.get("skill") is not None
        names = {s["name"] for s in manager.describe_available()}
        assert names == {"sanityops-inspect-lite", "pre-inspect-extract"}


class TestCliSkillTool:
    @pytest.fixture()
    def tool_and_manager(self, tmp_path: Path):
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        registry = ToolRegistry()
        manager = skill_runtime.attach_skill_tools(registry, target)
        return registry.get("skill"), manager

    def test_list_shows_both_skills(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="list"))
        assert result.success
        assert "sanityops-inspect-lite" in result.content
        assert "pre-inspect-extract" in result.content

    def test_load_rewrites_bash_hints(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="sanityops-inspect-lite"))
        assert result.success
        assert "`cat " not in result.content
        assert "`rg " not in result.content
        assert "use the read tool" in result.content
        # Skill body itself is intact.
        assert "# SanityOps Inspect Lite" in result.content

    def test_load_pre_inspect_extract(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="pre-inspect-extract"))
        assert result.success
        assert "pre-inspect-extract" in result.content

    def test_load_unknown_skill_errors(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="nope"))
        assert not result.success


def _QC_IDS(text: str) -> list[str]:
    import re

    return re.findall(r"QC-\d+\.\d+", text)
