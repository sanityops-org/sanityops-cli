"""Unit tests for analyzer prompt templates."""
from sanityops_cli.agents.scanner_agent.prompts import (
    ANALYZE_PARENT_PROMPT,
    PROMPT_ANALYZER_PROMPT,
    SKILL_ANALYZER_PROMPT,
    TOOL_ANALYZER_PROMPT,
)


class TestSkillAnalyzerPrompt:
    """Tests for SKILL_ANALYZER_PROMPT."""

    def test_format_with_files(self):
        """Test formatting with file list."""
        result = SKILL_ANALYZER_PROMPT.format(
            skill_files="- /path/to/skill1.md\n- /path/to/skill2.md"
        )
        assert "/path/to/skill1.md" in result
        assert "/path/to/skill2.md" in result
        assert "skill analyzer" in result.lower()

    def test_format_empty(self):
        """Test formatting with empty file list."""
        result = SKILL_ANALYZER_PROMPT.format(skill_files="(none)")
        assert "(none)" in result


class TestToolAnalyzerPrompt:
    """Tests for TOOL_ANALYZER_PROMPT."""

    def test_format_with_files(self):
        """Test formatting with file list."""
        result = TOOL_ANALYZER_PROMPT.format(
            tool_files="- /path/to/tool1.py\n- /path/to/tool2.py"
        )
        assert "/path/to/tool1.py" in result
        assert "/path/to/tool2.py" in result
        assert "tool analyzer" in result.lower()


class TestPromptAnalyzerPrompt:
    """Tests for PROMPT_ANALYZER_PROMPT."""

    def test_format_with_files(self):
        """Test formatting with file list."""
        result = PROMPT_ANALYZER_PROMPT.format(
            prompt_files="- /path/to/prompt1.md"
        )
        assert "/path/to/prompt1.md" in result
        assert "prompt analyzer" in result.lower()


class TestAnalyzeParentPrompt:
    """Tests for ANALYZE_PARENT_PROMPT."""

    def test_format_with_all_artifacts(self):
        """Test formatting with all artifact types."""
        result = ANALYZE_PARENT_PROMPT.format(
            skill_count=2,
            tool_count=3,
            prompt_count=1,
            SKILL_ANALYZER_PROMPT="skill analyzer content",
            TOOL_ANALYZER_PROMPT="tool analyzer content",
            PROMPT_ANALYZER_PROMPT="prompt analyzer content",
        )
        assert "Skills: 2 files" in result
        assert "Tools: 3 files" in result
        assert "Prompts: 1 files" in result
        assert "skill analyzer content" in result
        assert "tool analyzer content" in result
        assert "prompt analyzer content" in result

    def test_format_with_zero_counts(self):
        """Test formatting with zero artifact counts."""
        result = ANALYZE_PARENT_PROMPT.format(
            skill_count=0,
            tool_count=0,
            prompt_count=0,
            SKILL_ANALYZER_PROMPT="(none)",
            TOOL_ANALYZER_PROMPT="(none)",
            PROMPT_ANALYZER_PROMPT="(none)",
        )
        assert "Skills: 0 files" in result
        assert "Tools: 0 files" in result
        assert "Prompts: 0 files" in result
