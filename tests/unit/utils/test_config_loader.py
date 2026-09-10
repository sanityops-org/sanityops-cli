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


class TestSkillsSectionFilesOnly:
    """Skills entries must be existing files, not directories."""

    def _write_config(self, tmp_path: Path, skills_entries: list) -> Path:
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"
        config_content = {
            "project": {"id": "00000000-0000-0000-0000-0000000000aa"},
            "skills": skills_entries,
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)
        return config_file

    def test_skills_file_resolves_absolute_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        skill_file = tmp_path / "code_review.md"
        skill_file.write_text("# code review\n")
        config_file = self._write_config(tmp_path, [{"file": "code_review.md"}])
        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["skills"] == [str(skill_file.resolve())]

    def test_skills_bare_string_resolves_absolute_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        skill_file = tmp_path / "code_review.md"
        skill_file.write_text("# code review\n")
        config_file = self._write_config(tmp_path, ["code_review.md"])
        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["skills"] == [str(skill_file.resolve())]

    def test_skills_directory_raises_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "skills_dir").mkdir()
        config_file = self._write_config(tmp_path, [{"file": "skills_dir"}])
        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "not a file" in str(excinfo.value).lower()

    def test_skills_missing_file_raises_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = self._write_config(tmp_path, [{"file": "missing.md"}])
        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "not found" in str(excinfo.value).lower()


class TestConfigPathProperty:
    """Tests for the config_path property."""

    def test_config_path_returns_resolved_path(self, tmp_path: Path, monkeypatch):
        """config_path should return the resolved absolute path of the config file."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-0000000000bb"},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        assert loader.config_path == config_file.resolve()

    def test_config_path_with_explicit_path(self, tmp_path: Path, monkeypatch):
        """config_path should work when explicit path is provided."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / "custom_config"
        config_dir.mkdir()
        config_file = config_dir / "my_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-0000000000cc"},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        loader = InspectConfigLoader(str(config_file))
        assert loader.config_path == config_file.resolve()

    def test_config_path_with_default_location(self, tmp_path: Path, monkeypatch):
        """config_path should work when using default .sanityops location."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("---\nname: test\ndescription: test\n---\n")

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-0000000000dd"},
            "skills": [{"file": str(skill_file)}],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        # No explicit path - should find default location
        loader = InspectConfigLoader(None)
        assert loader.config_path == config_file.resolve()


class TestProjectPlaceholder:
    """Test handling of the placeholder project UUID and project.name."""

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
