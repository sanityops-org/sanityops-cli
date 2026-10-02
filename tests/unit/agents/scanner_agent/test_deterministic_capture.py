"""Unit tests for deterministic artifact capture in analyze_files."""

from types import SimpleNamespace

import pytest

from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.agents.scanner_agent.models.finding import FindingType


class _FakeParentAgent:
    """Fake agent that returns minimal valid result."""

    def __init__(self):
        from sanityops_agent.core.agent import TerminationReason

        self.result = SimpleNamespace(
            termination_reason=TerminationReason.END_TURN,
            error=None,
            error_detail=None,
            time_elapsed=0.0,
            loops_used=0,
            tokens_used=0,
        )

    async def run(self, prompt):
        return self.result


class _FakeAgentFactory:
    """Builds the real registry but returns a fake parent agent."""

    def __init__(self, **kwargs):
        pass

    def create_parent_agent(self, system_prompt="", **kwargs):
        return _FakeParentAgent()


class TestDeterministicPromptCapture:
    """Tests for deterministic prompt file capture."""

    @pytest.mark.anyio
    async def test_captures_prompt_content_verbatim(self, tmp_path, monkeypatch):
        """Prompt content should be read verbatim from disk."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        prompt_file = tmp_path / "system.txt"
        prompt_content = "You are a helpful assistant.\n\n## Instructions\nBe precise."
        prompt_file.write_text(prompt_content)

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[str(prompt_file)], tools=[], skills=[]
        )

        assert len(result.prompts) == 1
        assert result.prompts[0].type == FindingType.PROMPT
        assert result.prompts[0].relative == str(prompt_file)
        assert result.prompts[0].content is not None
        assert result.prompts[0].content.content == prompt_content

    @pytest.mark.anyio
    async def test_handles_multiline_prompt(self, tmp_path, monkeypatch):
        """Should handle prompts with many lines."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        lines = [f"Line {i}" for i in range(100)]
        prompt_file = tmp_path / "long.txt"
        prompt_file.write_text("\n".join(lines))

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[str(prompt_file)], tools=[], skills=[]
        )

        expected = "\n".join(lines)
        assert result.prompts[0].content.content == expected


class TestDeterministicSkillCapture:
    """Tests for deterministic skill file capture."""

    @pytest.mark.anyio
    async def test_captures_skill_with_frontmatter(self, tmp_path, monkeypatch):
        """Skill with frontmatter should parse name, description, and sections."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("""---
name: code-review
description: Review code for quality issues
---

## Usage

Use this skill to review code.

## Rules

1. Check for bugs
2. Check for style
""")

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )

        assert len(result.skills) == 1
        skill = result.skills[0]
        assert skill.type == FindingType.SKILL
        assert skill.relative == str(skill_file)
        assert skill.content is not None
        assert skill.content.name == "code-review"
        assert skill.content.description == "Review code for quality issues"
        assert len(skill.content.sections) == 2
        assert skill.content.sections[0].title == "Usage"
        assert "review code" in skill.content.sections[0].content
        assert skill.content.sections[1].title == "Rules"

    @pytest.mark.anyio
    async def test_handles_skill_without_frontmatter(self, tmp_path, monkeypatch):
        """Skill without frontmatter should still be captured."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("""## Overview

A simple skill.

## Steps

1. Do something
""")

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )

        assert len(result.skills) == 1
        skill = result.skills[0]
        assert skill.content is not None
        assert skill.content.name == ""
        assert skill.content.description == ""
        assert len(skill.content.sections) == 2

    @pytest.mark.anyio
    async def test_handles_frontmatter_without_trailing_newline(self, tmp_path, monkeypatch):
        """Frontmatter ending at EOF (no trailing newline) should still be parsed."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        # No trailing newline after the closing ---
        skill_file.write_text("---\nname: test-skill\ndescription: Test\n---\n## Body\nContent")

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )

        assert len(result.skills) == 1
        skill = result.skills[0]
        assert skill.content is not None
        assert skill.content.name == "test-skill"
        assert skill.content.description == "Test"

    @pytest.mark.anyio
    async def test_handles_malformed_yaml_frontmatter(self, tmp_path, monkeypatch):
        """Malformed YAML should be gracefully handled with empty frontmatter."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("""---
name: [invalid yaml
description: missing bracket
---

## Usage

Some content.
""")

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )

        # Should still capture the skill, but with empty frontmatter
        assert len(result.skills) == 1
        skill = result.skills[0]
        assert skill.content is not None
        # Name and description will be empty because YAML parsing failed
        assert skill.content.name == ""
        assert skill.content.description == ""

    @pytest.mark.anyio
    async def test_preserves_all_frontmatter_fields(self, tmp_path, monkeypatch):
        """All frontmatter fields should be preserved in the frontmatter dict."""
        monkeypatch.setattr(
            "sanityops_agent.agents.AgentFactory",
            _FakeAgentFactory,
        )
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("""---
name: test
description: desc
max_items: 5
timeout_seconds: 60
custom_field: value
---

## Usage

Content.
""")

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        result = await agent.analyze_files(
            prompts=[], tools=[], skills=[str(skill_file)]
        )

        skill = result.skills[0]
        assert skill.content is not None
        assert skill.content.frontmatter.get("max_items") == 5
        assert skill.content.frontmatter.get("timeout_seconds") == 60
        assert skill.content.frontmatter.get("custom_field") == "value"


class TestErrorHandling:
    """Tests for error handling in deterministic capture."""

    @pytest.mark.anyio
    async def test_raises_on_missing_prompt_file(self, tmp_path):
        """Should raise ValidationError if prompt file doesn't exist."""
        from sanityops_cli.exceptions.base_exceptions import ValidationError

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        with pytest.raises(ValidationError, match="path does not exist"):
            await agent.analyze_files(
                prompts=[str(tmp_path / "nonexistent.txt")], tools=[], skills=[]
            )

    @pytest.mark.anyio
    async def test_raises_on_missing_skill_file(self, tmp_path):
        """Should raise ValidationError if skill file doesn't exist."""
        from sanityops_cli.exceptions.base_exceptions import ValidationError

        from rich.console import Console

        agent = ScannerAgent(provider=object(), verbose=False, console=Console())
        with pytest.raises(ValidationError, match="path does not exist"):
            await agent.analyze_files(
                prompts=[], tools=[], skills=[str(tmp_path / "nonexistent.md")]
            )