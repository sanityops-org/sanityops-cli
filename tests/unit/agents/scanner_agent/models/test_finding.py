"""Unit tests for finding models."""
from sanityops_cli.agents.scanner_agent.models.finding import (
    PromptContent,
    Section,
    SkillContent,
    ToolContent,
)


class TestSection:
    """Tests for Section model."""

    def test_section_creation(self):
        """Test creating a Section instance."""
        section = Section(title="Overview", content="This is the overview.")
        assert section.title == "Overview"
        assert section.content == "This is the overview."

    def test_section_defaults(self):
        """Test Section with minimal fields."""
        section = Section(title="Test", content="")
        assert section.title == "Test"
        assert section.content == ""


class TestSkillContent:
    """Tests for SkillContent model."""

    def test_skill_content_creation(self):
        """Test creating a SkillContent instance."""
        sections = [
            Section(title="Overview", content="Overview content"),
            Section(title="Usage", content="Usage content"),
        ]
        skill = SkillContent(
            name="code-review",
            description="Review code for issues",
            sections=sections,
        )
        assert skill.name == "code-review"
        assert skill.description == "Review code for issues"
        assert len(skill.sections) == 2

    def test_skill_content_to_markdown(self):
        """Test to_markdown() reconstructs sections."""
        sections = [
            Section(title="Overview", content="Overview content"),
            Section(title="Usage", content="Usage content"),
        ]
        skill = SkillContent(
            name="test-skill",
            description="A test skill",
            sections=sections,
        )
        result = skill.to_markdown()
        assert "## Overview" in result
        assert "## Usage" in result
        assert "Overview content" in result
        assert "Usage content" in result

    def test_skill_content_to_markdown_empty(self):
        """Test to_markdown() with no sections."""
        skill = SkillContent(name="test", description="desc", sections=[])
        assert skill.to_markdown() == ""

    def test_skill_content_default_sections(self):
        """Test sections defaults to empty list."""
        skill = SkillContent(name="test", description="desc")
        assert skill.sections == []

    def test_skill_content_frontmatter_type_coercion(self):
        """Test frontmatter type coercion for integer fields."""
        # String to int conversion
        skill = SkillContent(
            name="test",
            description="desc",
            frontmatter={"max_items": "5", "timeout_seconds": "30"},
        )
        assert skill.frontmatter["max_items"] == 5
        assert skill.frontmatter["timeout_seconds"] == 30

    def test_skill_content_float_to_int_coercion(self):
        """Test float to int conversion (YAML may parse ints as floats)."""
        skill = SkillContent(
            name="test",
            description="desc",
            frontmatter={"max_items": 5.0, "timeout_seconds": 30.0},
        )
        assert skill.frontmatter["max_items"] == 5
        assert skill.frontmatter["timeout_seconds"] == 30
        assert isinstance(skill.frontmatter["max_items"], int)

    def test_skill_content_boolean_field_coercion(self):
        """Test boolean field string-to-bool conversion."""
        skill = SkillContent(
            name="test",
            description="desc",
            frontmatter={"partial_result_allowed": "true"},
        )
        assert skill.frontmatter["partial_result_allowed"] is True

        skill2 = SkillContent(
            name="test",
            description="desc",
            frontmatter={"partial_result_allowed": "false"},
        )
        assert skill2.frontmatter["partial_result_allowed"] is False


class TestToolContent:
    """Tests for ToolContent model."""

    def test_tool_content_creation(self):
        """Test creating a ToolContent instance."""
        tool = ToolContent(
            name="search",
            description="Search for files",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        assert tool.name == "search"
        assert tool.description == "Search for files"
        assert tool.parameters["type"] == "object"

    def test_tool_content_default_parameters(self):
        """Test parameters defaults to empty dict."""
        tool = ToolContent(name="test", description="A test tool")
        assert tool.parameters == {}


class TestPromptContent:
    """Tests for PromptContent model."""

    def test_prompt_content_creation(self):
        """Test creating a PromptContent instance."""
        prompt = PromptContent(content="You are a helpful assistant.")
        assert prompt.content == "You are a helpful assistant."

    def test_prompt_content_empty(self):
        """Test PromptContent with empty string."""
        prompt = PromptContent(content="")
        assert prompt.content == ""


class TestFinding:
    """Placeholder tests for Finding model."""
    pass
