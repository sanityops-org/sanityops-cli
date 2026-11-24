"""Tests for the vendored-skill runtime (materialize + SkillManager assembly)."""

from __future__ import annotations

import logging
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from sanityops_agent.tools.registry import ToolRegistry

from sanityops_cli.inspect_pipeline import skill_runtime

SRC = Path(__file__).resolve().parents[3] / "src" / "sanityops_cli" / "skills"
LOGGER = "sanityops_cli.inspect_pipeline.skill_runtime"


class TestMaterialize:
    def test_materializes_both_skills(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert (target / "sanityops-inspect-only" / "SKILL.md").is_file()
        assert (target / "sanityops-extract-only" / "SKILL.md").is_file()
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
        (mutated / "sanityops-extract-only" / "SKILL.md").write_text(
            (mutated / "sanityops-extract-only" / "SKILL.md").read_text(encoding="utf-8")
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

    @pytest.mark.skipif(
        sys.version_info < (3, 12),
        reason="resources.as_file() extracts directories only from Python 3.12",
    )
    def test_materialize_from_zip_keeps_as_file_temp_dir_until_copied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import zipfile
        from contextlib import contextmanager
        from importlib import resources

        zip_path = tmp_path / "pkg.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for item in sorted(SRC.rglob("*")):
                if item.is_file():
                    arcname = Path("sanityops_cli") / "skills" / item.relative_to(SRC)
                    zf.write(item, arcname=arcname.as_posix())

        extracted_paths: list[Path] = []
        real_as_file = resources.as_file

        @contextmanager
        def tracking_as_file(traversable):
            with real_as_file(traversable) as extracted:
                extracted_paths.append(extracted)
                yield extracted

        # Disable the repo fallback path so only the zipped resource can succeed.
        monkeypatch.setattr(
            skill_runtime,
            "__file__",
            str(tmp_path / "missing" / "inspect_pipeline" / "skill_runtime.py"),
        )
        monkeypatch.setattr(skill_runtime.resources, "as_file", tracking_as_file)

        with zipfile.ZipFile(zip_path, "r") as zf:
            pkg_root = zipfile.Path(zf, "sanityops_cli/")
            monkeypatch.setattr(skill_runtime.resources, "files", lambda _pkg: pkg_root)

            target = skill_runtime.materialize_skills(cache_root=tmp_path / "cache")

        assert len(extracted_paths) == 1
        assert not extracted_paths[0].exists()
        assert (target / "VERSION.json").is_file()
        assert (target / "sanityops-inspect-only" / "SKILL.md").is_file()
        assert (target / "sanityops-extract-only" / "SKILL.md").is_file()
        assert (target / "code-contract-checklist.v2.md").is_file()

    def test_packaged_skills_context_falls_back_when_directory_extraction_is_unsupported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        @contextmanager
        def unsupported(traversable):
            raise IsADirectoryError(traversable)
            yield  # pragma: no cover

        monkeypatch.setattr(skill_runtime.resources, "as_file", unsupported)
        monkeypatch.setattr(skill_runtime.resources, "files", lambda _pkg: SRC.parent)

        with skill_runtime._packaged_skills_context() as path:
            assert path.is_dir()
            assert (path / "VERSION.json").is_file()

    def test_packaged_skills_context_falls_back_to_source_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def missing(_package: str):
            raise FileNotFoundError("package resources unavailable")

        monkeypatch.setattr(skill_runtime.resources, "files", missing)

        with skill_runtime._packaged_skills_context() as path:
            assert path.is_dir()
            assert (path / "VERSION.json").is_file()

    def test_packaged_skills_context_does_not_swallow_caller_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            skill_runtime.resources,
            "files",
            lambda _pkg: SRC.parent,
        )
        with pytest.raises(FileNotFoundError, match="boom"):
            with skill_runtime._packaged_skills_context():
                raise FileNotFoundError("boom")

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

    def test_vendored_skill_names_match_directories(self) -> None:
        for name in skill_runtime.EXPECTED_SKILLS:
            text = (SRC / name / "SKILL.md").read_text(encoding="utf-8")
            assert re.search(rf"^name:\s*{re.escape(name)}\s*$", text, re.MULTILINE)


class TestValidateVendor:
    def test_clean_vendor_has_no_warnings(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        assert skill_runtime.validate_vendor(target) == []

    def test_warns_on_frontmatter_version_mismatch(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        skill_md = target / "sanityops-inspect-only" / "SKILL.md"
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
        shutil.rmtree(partial / "sanityops-extract-only")
        warnings = skill_runtime.validate_vendor(partial)
        assert any("'sanityops-extract-only' missing" in w for w in warnings)


class TestAttachSkillTools:
    def test_registry_gets_skill_manager_and_tool(self, tmp_path: Path) -> None:
        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        registry = ToolRegistry()
        manager = skill_runtime.attach_skill_tools(registry, target)
        assert registry.context.skill_manager is manager
        assert registry.get("skill") is not None
        names = {s["name"] for s in manager.describe_available()}
        assert names == {"sanityops-inspect-only", "sanityops-extract-only"}


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
        assert "sanityops-inspect-only" in result.content
        assert "sanityops-extract-only" in result.content

    def test_load_rewrites_bash_hints(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="sanityops-inspect-only"))
        assert result.success
        assert "`cat " not in result.content
        assert "`rg " not in result.content
        assert "use the read tool on" in result.content
        assert "(read tool)" not in result.content
        # Skill body itself is intact: the vendored H1 comes through verbatim.
        # Read the title from the file rather than pinning a title string, so a
        # skill content update does not fail this runtime test.
        skill_md = SRC / "sanityops-inspect-only" / "SKILL.md"
        h1 = next(
            line for line in skill_md.read_text(encoding="utf-8").splitlines() if line.startswith("# ")
        )
        assert h1 in result.content

    def test_load_inspect_skill_applies_cli_rewrites(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="sanityops-inspect-only"))
        assert result.success
        text = result.content
        # Standalone-skill framing is replaced by the CLI contract.
        assert "The official `sanityops-cli`" not in text
        assert "no CLI, no scripts, no network calls" not in text
        assert "## 10. Further reading & upgrade" not in text
        assert "upgrade pointer" not in text
        assert "CLI-provided report header data" in text
        assert "SanityOps Framework v1.1" in text
        assert "## CLI runtime override (sanityops-cli)" in text
        assert "run sanityops-inspector (extract + inspect)" not in text
        assert "run the CLI extraction stage first" in text
        assert "single-model self-audit rather than an official engine conclusion" not in text
        assert "unofficial-result disclaimer or a host-model label" in text
        assert "the CLI Contract Appendix" in text
        assert "8. **Self-verification statement**" in text
        assert "six provenance facts" not in text
        assert "CLI provenance facts" in text
        assert "Impact Cards" not in text
        assert "impact-outlook mappings" in text

    def test_load_extract_only_skill(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="sanityops-extract-only"))
        assert result.success
        assert "sanityops-extract-only" in result.content

    def test_load_unknown_skill_errors(self, tool_and_manager) -> None:
        import asyncio

        tool, _ = tool_and_manager
        result = asyncio.run(tool.run(operation="load", name="nope"))
        assert not result.success


class TestReferenceRewrite:
    def test_relevance_map_labels_validation_as_static(self) -> None:
        path = SRC / "sanityops-inspect-only" / "references" / "relevance-map.v2.md"
        text = path.read_text(encoding="utf-8")
        rewritten = skill_runtime.rewrite_reference_for_cli(path, text)
        assert "NOT run by this inspector" not in rewritten
        assert "not run in this CLI static inspection" in rewritten

    def test_other_references_pass_through(self) -> None:
        path = SRC / "sanityops-inspect-only" / "references" / "_meta.md"
        text = path.read_text(encoding="utf-8")
        assert skill_runtime.rewrite_reference_for_cli(path, text) == text


class TestRewriteDriftDetection:
    def test_missing_pattern_logs_warning(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            result = skill_runtime._rewrite_inspect_skill_for_cli("standalone text")
        assert result == "standalone text"
        assert "Skill rewrite pattern not found" in caplog.text
        assert "pattern=" in caplog.text

    def test_current_skill_matches_every_rewrite_pattern(self, tmp_path, caplog) -> None:
        import asyncio

        target = skill_runtime.materialize_skills(source=SRC, cache_root=tmp_path)
        registry = ToolRegistry()
        skill_runtime.attach_skill_tools(registry, target)
        tool = registry.get("skill")
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            result = asyncio.run(tool.run(operation="load", name="sanityops-inspect-only"))
        assert result.success
        assert "Skill rewrite pattern not found" not in caplog.text

    def test_reference_rewrite_warns_on_missing_pattern(self, tmp_path, caplog) -> None:
        path = tmp_path / "relevance-map.v2.md"
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            assert skill_runtime.rewrite_reference_for_cli(path, "changed text") == "changed text"
        assert "relevance-map validation label" in caplog.text


def _QC_IDS(text: str) -> list[str]:
    import re

    return re.findall(r"QC-\d+\.\d+", text)
