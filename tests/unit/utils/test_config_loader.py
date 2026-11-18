"""Tests for model section validation in InspectConfigLoader."""

from pathlib import Path

import pytest
import yaml

from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.utils.config_loader import PROJECT_ID_PLACEHOLDER, InspectConfigLoader


class TestModelSectionValidation:
    """Test cases for model section validation in config loader."""

    def test_model_section_absent_is_valid(self, tmp_path: Path, monkeypatch):
        """Config without model section should be valid."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000001"},
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        # Should not raise
        result = loader.load()
        assert result["project_id"] == "00000000-0000-0000-0000-000000000001"

    def test_model_section_complete_is_valid(self, tmp_path: Path, monkeypatch):
        """Config with complete model section should be valid."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000002"},
            "model": {
                "provider": "anthropic",
                "api_key": "sk-test-key",
                "model_id": "claude-sonnet-4-20250514",
                "base_url": "https://api.anthropic.com",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        # Should not raise
        result = loader.load()
        assert result["project_id"] == "00000000-0000-0000-0000-000000000002"

    def test_model_section_without_base_url_is_valid(self, tmp_path: Path, monkeypatch):
        """Config with model section missing optional base_url should be valid."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000003"},
            "model": {
                "provider": "anthropic",
                "api_key": "sk-test-key",
                "model_id": "claude-sonnet-4-20250514",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        # Should not raise
        result = loader.load()
        assert result["project_id"] == "00000000-0000-0000-0000-000000000003"

    def test_model_section_missing_provider_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with model section missing provider should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000004"},
            "model": {
                "api_key": "sk-test-key",
                "model_id": "claude-sonnet-4-20250514",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "provider" in str(excinfo.value).lower()

    def test_model_section_missing_api_key_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with model section missing api_key should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000005"},
            "model": {
                "provider": "anthropic",
                "model_id": "claude-sonnet-4-20250514",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "api_key" in str(excinfo.value).lower()

    def test_model_section_missing_model_id_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with model section missing model_id should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000006"},
            "model": {
                "provider": "anthropic",
                "api_key": "sk-test-key",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "model_id" in str(excinfo.value).lower()

    def test_model_section_empty_provider_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with empty provider string should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000007"},
            "model": {
                "provider": "",
                "api_key": "sk-test-key",
                "model_id": "claude-sonnet-4-20250514",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "provider" in str(excinfo.value).lower()

    def test_model_section_empty_api_key_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with empty api_key string should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000008"},
            "model": {
                "provider": "anthropic",
                "api_key": "",
                "model_id": "claude-sonnet-4-20250514",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "api_key" in str(excinfo.value).lower()

    def test_model_section_empty_model_id_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with empty model_id string should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000009"},
            "model": {
                "provider": "anthropic",
                "api_key": "sk-test-key",
                "model_id": "",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "model_id" in str(excinfo.value).lower()

    def test_model_section_not_a_dict_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with model section as non-dict should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000010"},
            "model": "not a dict",
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "model" in str(excinfo.value).lower()


class TestGbkEncodedConfig:
    """Windows users often save config files as GBK (Notepad ANSI default).

    The loader should accept GBK-encoded files via encoding fallback.
    """

    def test_gbk_encoded_config_is_loaded(self, tmp_path: Path, monkeypatch):
        """GBK-encoded config file should be loaded without UnicodeDecodeError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        # Create a valid skill file
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000011"},
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w", encoding="gbk") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["project_id"] == "00000000-0000-0000-0000-000000000011"
        assert result["skills"] == [str(skill_file.resolve())]

    def test_gbk_config_with_chinese_comments_is_loaded(self, tmp_path: Path, monkeypatch):
        """GBK config with Chinese comments should be loaded correctly."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        content = (
            "# 检查配置文件\n"
            "project:\n"
            '  id: "00000000-0000-0000-0000-000000000012"\n'
            "prompts: []\n"
            "tools: []\n"
            "skills:\n"
            f"  - file: {skill_file}\n"
        )
        with open(config_file, "w", encoding="gbk") as f:
            f.write(content)

        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["project_id"] == "00000000-0000-0000-0000-000000000012"

    def test_model_section_unsupported_provider_raises_error(self, tmp_path: Path, monkeypatch):
        """Config with unsupported provider should raise ValidationError."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000009"},
            "model": {
                "provider": "unsupported_llm",
                "api_key": "sk-test-key",
                "model_id": "model-1",
            },
            "prompts": [],
            "tools": [],
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "unsupported 'model.provider'" in str(excinfo.value).lower()

    def test_cross_directory_config_resolves_project_relative_paths(
        self, tmp_path: Path, monkeypatch
    ):
        """Passing --config from a different cwd must resolve paths against config project root."""
        project_dir = tmp_path / "remote_project"
        (project_dir / ".sanityops").mkdir(parents=True)
        (project_dir / "prompts").mkdir()
        (project_dir / "tools").mkdir()
        (project_dir / "skills" / "my-skill").mkdir(parents=True)

        prompt_file = project_dir / "prompts" / "system.md"
        prompt_file.write_text("System prompt", encoding="utf-8")
        tool_file = project_dir / "tools" / "tools.json"
        tool_file.write_text('[{"name": "t1"}]', encoding="utf-8")
        skill_file = project_dir / "skills" / "my-skill" / "SKILL.md"
        skill_file.write_text(
            "---\nname: my-skill\ndescription: d\n---\n# Body\n", encoding="utf-8"
        )

        config_file = project_dir / ".sanityops" / "inspect_config.yaml"
        config_file.write_text(
            "project:\n"
            "  id: 00000000-0000-0000-0000-000000000000\n"
            "prompts:\n"
            "  - file: prompts/system.md\n"
            "tools:\n"
            "  - file: tools/tools.json\n"
            "skills:\n"
            "  - file: skills/\n",
            encoding="utf-8",
        )

        unrelated_cwd = tmp_path / "other_dir"
        unrelated_cwd.mkdir()
        monkeypatch.chdir(unrelated_cwd)

        loader = InspectConfigLoader(str(config_file), require_project_id=False)
        loaded = loader.load()

        assert loaded["prompts"] == [str(prompt_file.resolve())]
        assert loaded["tools"] == [str(tool_file.resolve())]
        assert loaded["skills"] == [str(skill_file.resolve())]


class TestProjectIdResolution:
    """Target-specific project id resolution behavior."""

    def test_placeholder_uuid_resolves_to_none(self, tmp_path: Path, monkeypatch):
        """Placeholder project.id should resolve to None (project not bound)."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": PROJECT_ID_PLACEHOLDER},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["project_id"] is None

    def test_real_uuid_is_returned_as_is(self, tmp_path: Path, monkeypatch):
        """A real (non-placeholder) project.id should be returned unchanged."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        real_id = "11111111-2222-3333-4444-555555555555"
        config_content = {
            "project": {"id": real_id},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["project_id"] == real_id

    def test_project_name_field_is_ignored_by_loader(self, tmp_path: Path, monkeypatch):
        """An extra project.name field should not affect loading."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": PROJECT_ID_PLACEHOLDER, "name": ""},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["project_id"] is None
        assert str(skill_file.resolve()) in result["skills"]
