"""Tests for pack_extracted (ExtractionResult -> upload payload)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from sanityops_cli.inspect_pipeline.models import (
    ExtractedArtifact,
    ExtractionResult,
)
from sanityops_cli.utils.artifact_packer import pack_extracted


def artifact(**overrides):
    base = {
        "type": "prompt",
        "name": "system",
        "content": "You are a helpful assistant.",
        "completeness": "full original",
        "L": "AC-L1",
        "source": "/proj/prompts/system.md",
    }
    base.update(overrides)
    return ExtractedArtifact(**base)


class TestPackExtracted:
    def test_prompt_content_merged(self):
        res = ExtractionResult(
            artifacts=[
                artifact(name="a", content="first"),
                artifact(name="b", content="second", source="/p/b.md"),
            ]
        )
        packed = pack_extracted(res)
        assert packed["prompt_content"] == "first\n\nsecond"

    def test_tools_schema_provider_neutral(self):
        res = ExtractionResult(
            artifacts=[
                artifact(
                    type="tool",
                    name="search",
                    schema={
                        "name": "search",
                        "description": "d",
                        "parameters": {"type": "object"},
                        "extra": "kept-out",
                    },
                ),
            ]
        )
        packed = pack_extracted(res)
        tools = json.loads(packed["tools_schema"])
        assert tools == [{"name": "search", "description": "d", "parameters": {"type": "object"}}]

    def test_tool_name_falls_back_to_record_name(self):
        res = ExtractionResult(
            artifacts=[
                artifact(type="tool", name="fallback", schema={"parameters": {}}),
            ]
        )
        tools = json.loads(pack_extracted(res)["tools_schema"])
        assert tools[0]["name"] == "fallback"

    def test_tools_deduped_by_name(self):
        res = ExtractionResult(
            artifacts=[
                artifact(
                    type="tool",
                    name="t",
                    schema={"name": "t", "description": "one", "parameters": {}},
                ),
                artifact(
                    type="tool",
                    name="t",
                    schema={"name": "t", "description": "two", "parameters": {}},
                    source="/other.py",
                ),
            ]
        )
        tools = json.loads(pack_extracted(res)["tools_schema"])
        assert len(tools) == 1
        assert tools[0]["description"] == "two"

    def test_skill_file_from_content(self):
        res = ExtractionResult(
            artifacts=[
                artifact(type="skill", name="review", content="---\nname: review\n---\nbody"),
            ]
        )
        packed = pack_extracted(res)
        filename, blob = packed["skill_file"]
        assert filename == "skills.zip"
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            assert zf.read("review/SKILL.md").decode("utf-8").endswith("body")

    def test_skill_file_from_source_directory(self, tmp_path: Path):
        skill_dir = tmp_path / "review"
        (skill_dir / "references").mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("frontmatter", encoding="utf-8")
        (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
        (skill_dir / ".hidden").write_text("no", encoding="utf-8")

        res = ExtractionResult(
            artifacts=[
                artifact(type="skill", name="review", content="verbatim", source=str(skill_dir)),
            ]
        )
        with zipfile.ZipFile(io.BytesIO(pack_extracted(res)["skill_file"][1])) as zf:
            names = set(zf.namelist())
        assert names == {"review/SKILL.md", "review/references/guide.md"}

    def test_not_inspectable_excluded(self):
        res = ExtractionResult(
            artifacts=[
                artifact(
                    completeness="not inspectable", reason="binary", content="", L="undetermined"
                ),
            ]
        )
        packed = pack_extracted(res)
        assert packed["prompt_content"] is None
        assert packed["tools_schema"] is None
        assert packed["skill_file"] is None

    def test_empty_result(self):
        packed = pack_extracted(ExtractionResult())
        assert packed == {"prompt_content": None, "tools_schema": None, "skill_file": None}

    def test_tools_schema_unwraps_openai_and_input_schema(self):
        res = ExtractionResult(
            artifacts=[
                artifact(
                    type="tool",
                    name="collector",
                    schema={
                        "type": "function",
                        "function": {
                            "name": "device_data_collector",
                            "description": "Collect telemetry",
                            "parameters": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                            },
                        },
                    },
                ),
                artifact(
                    type="tool",
                    name="inspector",
                    schema={
                        "name": "mcp_inspector",
                        "description": "Inspect",
                        "inputSchema": {"type": "object"},
                    },
                ),
            ]
        )
        tools = json.loads(pack_extracted(res)["tools_schema"])
        assert tools == [
            {
                "name": "device_data_collector",
                "description": "Collect telemetry",
                "parameters": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
            {
                "name": "mcp_inspector",
                "description": "Inspect",
                "parameters": {"type": "object"},
            },
        ]

    def test_skill_dir_under_hidden_ancestor_and_skill_md_resources(self, tmp_path: Path):
        hidden_dir = tmp_path / ".worktree" / "review"
        (hidden_dir / "references").mkdir(parents=True)
        skill_md = hidden_dir / "SKILL.md"
        skill_md.write_text("frontmatter", encoding="utf-8")
        (hidden_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
        (hidden_dir / ".env").write_text("secret", encoding="utf-8")

        res = ExtractionResult(
            artifacts=[
                artifact(type="skill", name="review", content="frontmatter", source=str(skill_md)),
            ]
        )
        with zipfile.ZipFile(io.BytesIO(pack_extracted(res)["skill_file"][1])) as zf:
            names = set(zf.namelist())
        assert names == {"review/SKILL.md", "review/references/guide.md"}
