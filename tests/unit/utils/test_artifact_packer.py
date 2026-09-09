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

"""Tests for sanityops_cli.utils.artifact_packer module."""

import json
import zipfile
from io import BytesIO

import pytest

from sanityops_cli.agents.scanner_agent.models.finding import (
    Finding,
    FindingType,
    PromptContent,
    SkillContent,
    ToolContent,
)
from sanityops_cli.utils.artifact_packer import pack_from_findings


@pytest.fixture
def prompt_file(tmp_path) -> str:
    p = tmp_path / "prompt.md"
    p.write_text("Hello world", encoding="utf-8")
    return str(p)


@pytest.fixture
def tool_file(tmp_path) -> str:
    p = tmp_path / "tool.json"
    p.write_text('{"name": "search", "description": "Search tool"}', encoding="utf-8")
    return str(p)


@pytest.fixture
def skill_file(tmp_path) -> str:
    p = tmp_path / "SKILL.md"
    p.write_text("# Test Skill\n\nContent here", encoding="utf-8")
    return str(p)


def _make_prompt_finding(path: str, content: str = "Hello world") -> Finding:
    return Finding(type=FindingType.PROMPT, relative=path, content=PromptContent(content=content))


def _make_tool_finding(
    path: str,
    name: str = "search",
    description: str = "Search tool",
    parameters: dict | None = None,
) -> Finding:
    return Finding(
        type=FindingType.TOOL,
        relative=path,
        content=ToolContent(name=name, description=description, parameters=parameters or {}),
    )


def _make_skill_finding(path: str, name: str = "my-skill") -> Finding:
    return Finding(
        type=FindingType.SKILL,
        relative=path,
        content=SkillContent(
            name=name,
            description="A test skill",
            sections=[],
        ),
    )


class TestPackFromFindings:
    """Test pack_from_findings function."""

    def test_returns_empty_dicts_for_no_findings(self) -> None:
        result = pack_from_findings([], [], [])
        assert result["prompt_content"] is None
        assert result["tools_schema"] is None
        assert result["skill_file"] is None

    def test_packs_prompts_into_single_text(self, prompt_file, tmp_path) -> None:
        second = tmp_path / "b.md"
        second.write_text("Second prompt", encoding="utf-8")

        prompts = [
            _make_prompt_finding(prompt_file, "First prompt"),
            _make_prompt_finding(str(second), "Second prompt"),
        ]
        result = pack_from_findings([], [], prompts)

        assert result["prompt_content"] is not None
        assert "First prompt" in result["prompt_content"]
        assert "Second prompt" in result["prompt_content"]
        assert "<!-- BEGIN: prompt.md -->" in result["prompt_content"]
        assert "<!-- BEGIN: b.md -->" in result["prompt_content"]

    def test_packs_tools_into_openai_format(self, tool_file) -> None:
        tools = [
            _make_tool_finding(
                tool_file,
                name="search",
                description="Search the web",
                parameters={"type": "object", "properties": {}},
            ),
        ]
        result = pack_from_findings([], tools, [])

        assert result["tools_schema"] is not None
        parsed = json.loads(result["tools_schema"])
        assert isinstance(parsed, list)
        assert parsed[0]["type"] == "function"
        assert parsed[0]["function"]["name"] == "search"
        assert parsed[0]["function"]["description"] == "Search the web"

    def test_ignores_findings_with_no_content(self, prompt_file) -> None:
        prompts = [Finding(type=FindingType.PROMPT, relative=prompt_file)]  # content is None
        result = pack_from_findings([], [], prompts)
        assert result["prompt_content"] is None

    def test_packs_skills_into_zip(self, skill_file) -> None:
        finding = _make_skill_finding(skill_file, name="test-skill")

        result = pack_from_findings([finding], [], [])

        assert result["skill_file"] is not None
        filename, content = result["skill_file"]
        assert filename == "skills.zip"

        # Verify the ZIP contains the skill
        with zipfile.ZipFile(BytesIO(content)) as zf:
            assert "test-skill/SKILL.md" in zf.namelist()


class TestIgnoreNonMatchingContent:
    """Test that findings with wrong content types are skipped."""

    def test_skill_content_in_prompt_findings_is_skipped(self, prompt_file) -> None:
        from sanityops_cli.utils.artifact_packer import _pack_prompts_from_findings

        # A prompt finding with SkillContent should be ignored by prompt packing
        finding = Finding(
            type=FindingType.PROMPT,
            relative=prompt_file,
            content=PromptContent(content="actual prompt"),
        )
        finding.content = SkillContent(name="skill", description="desc")  # wrong type
        # The defensive isinstance check should skip it and return None
        result = _pack_prompts_from_findings([finding])
        assert result is None

    def test_prompt_content_in_tool_findings_is_skipped(self, tool_file) -> None:
        from sanityops_cli.utils.artifact_packer import _pack_tools_from_findings

        finding = Finding(
            type=FindingType.TOOL,
            relative=tool_file,
            content=ToolContent(name="search", description="Search"),
        )
        finding.content = PromptContent(content="not a tool")  # wrong type
        # The defensive isinstance check should skip it and return None
        result = _pack_tools_from_findings([finding])
        assert result is None