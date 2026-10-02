"""Unit tests for DefectChecker conversion and invocation."""
import pytest

from sanityops_cli.agents.scanner_agent.models.finding import (
    Finding,
    FindingsResult,
    FindingType,
    PromptContent,
    Section,
    SkillContent,
    ToolContent,
)
from sanityops_cli.defect_checker.checker import DefectChecker


class TestConverters:
    def _findings(self, tmp_path):
        # Create temporary files/directories to satisfy path validation
        skill_dir = tmp_path / "skills" / "code_review.md"
        skill_dir.mkdir(parents=True)

        tool_file = tmp_path / "tools" / "search.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text("# tool")

        prompt_file = tmp_path / "prompts" / "system.md"
        prompt_file.parent.mkdir(parents=True)
        prompt_file.write_text("# prompt")

        skill = Finding(
            type=FindingType.SKILL,
            relative=str(skill_dir),
            content=SkillContent(
                name="code-review",
                description="Review code",
                sections=[Section(title="Usage", content="Use it.")],
            ),
        )
        tool = Finding(
            type=FindingType.TOOL,
            relative=str(tool_file),
            content=ToolContent(
                name="search",
                description="Search files",
                parameters={"type": "object"},
            ),
        )
        prompt = Finding(
            type=FindingType.PROMPT,
            relative=str(prompt_file),
            content=PromptContent(content="You are a helper."),
        )
        return skill, tool, prompt

    def test_convert_skills(self, tmp_path):
        skill, _, _ = self._findings(tmp_path)
        checker = DefectChecker(llm_config={})
        out = checker._convert_skills([skill])
        assert out == [{
            "id": skill.relative,
            "name": "code-review",
            "content": "## Usage\n\nUse it.",
        }]

    def test_convert_tools(self, tmp_path):
        _, tool, _ = self._findings(tmp_path)
        checker = DefectChecker(llm_config={})
        out = checker._convert_tools([tool])
        assert out == [{
            "name": "search",
            "description": "Search files",
            "inputSchema": {"type": "object"},
            "parameters": {"type": "object"},  # Deprecated alias for inputSchema
        }]

    def test_convert_prompts(self, tmp_path):
        _, _, prompt = self._findings(tmp_path)
        checker = DefectChecker(llm_config={})
        out = checker._convert_prompts([prompt])
        assert out == [{"content": "You are a helper."}]

    def test_skips_none_content(self, tmp_path):
        tool_file = tmp_path / "t.py"
        tool_file.write_text("# tool")
        empty = Finding(type=FindingType.TOOL, relative=str(tool_file), content=None)
        checker = DefectChecker(llm_config={})
        assert checker._convert_tools([empty]) == []

    def test_ignore_wrong_type_in_group(self, tmp_path):
        skill, _, _ = self._findings(tmp_path)
        checker = DefectChecker(llm_config={})
        # A skill finding should not appear in the tools group
        assert checker._convert_tools([skill]) == []


class TestCheck:
    @pytest.mark.anyio
    async def test_check_invokes_sdk_with_converted_inputs(self, monkeypatch, tmp_path):
        import defect_check

        skill_dir = tmp_path / "skills" / "s.md"
        skill_dir.mkdir(parents=True)

        skill = Finding(
            type=FindingType.SKILL,
            relative=str(skill_dir),
            content=SkillContent(name="s", description="d", sections=[]),
        )
        result = FindingsResult(
            directory=str(tmp_path),
            skills=[skill],
            tools=[],
            prompts=[],
        )

        captured = {}

        async def fake_check(tools, prompts, skills, **kwargs):
            captured["tools"] = tools
            captured["prompts"] = prompts
            captured["skills"] = skills
            captured["kwargs"] = kwargs
            return {"status": "completed", "summary": {}, "results": []}

        monkeypatch.setattr(defect_check, "check", fake_check)

        checker = DefectChecker(
            llm_config={
                "llm_provider": "anthropic",
                "llm_api_key": "k",
                "llm_model_id": "m",
                "llm_base_url": "",
            }
        )
        await checker.check(result, check_level="L2")

        assert captured["skills"] == [{"id": str(skill_dir), "name": "s", "content": ""}]
        assert captured["tools"] == []
        assert captured["prompts"] == []
        assert captured["kwargs"]["check_level"] == "L2"
        assert captured["kwargs"]["llm_provider"] == "anthropic"
        assert captured["kwargs"]["llm_api_key"] == "k"
        assert captured["kwargs"]["llm_model_id"] == "m"
