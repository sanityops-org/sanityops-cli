"""Tests for inspect init command."""

import uuid
from pathlib import Path

import yaml


class TestInitConfig:
    """Test cases for init_config function."""

    def test_creates_config_file_when_none_exists(self, tmp_path: Path, monkeypatch):
        """Should create .sanityops/inspect_config.yaml with valid UUID."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        assert config_file.exists()
        assert config_file.is_file()

        # Verify content structure
        content = yaml.safe_load(config_file.read_text())
        assert "project" in content
        assert "id" in content["project"]

        # Verify UUID is valid format
        project_id = content["project"]["id"]
        uuid.UUID(project_id)  # raises ValueError if invalid

    def test_preserves_existing_when_user_declines(self, tmp_path: Path, monkeypatch):
        """Should preserve existing config when user declines overwrite."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        # Create existing config with known content
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"
        original_content = {"project": {"id": "original-uuid-12345"}}
        with open(config_file, "w") as f:
            yaml.dump(original_content, f)

        # Mock user declining
        monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: False)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert - original file unchanged
        content = yaml.safe_load(config_file.read_text())
        assert content["project"]["id"] == "original-uuid-12345"

        # No backup file created (only the original file should exist)
        assert list(config_dir.iterdir()) == [config_file]

    def test_backs_up_and_creates_new_when_user_accepts(self, tmp_path: Path, monkeypatch):
        """Should backup existing config and create new when user accepts."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"
        original_content = {"project": {"id": "original-uuid-12345"}}
        with open(config_file, "w") as f:
            yaml.dump(original_content, f)

        # Mock user accepting
        monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: True)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert - new file created with new UUID
        new_content = yaml.safe_load(config_file.read_text())
        assert new_content["project"]["id"] != "original-uuid-12345"
        uuid.UUID(new_content["project"]["id"])  # verify valid UUID

        # Backup file exists with original content
        backup_files = list(config_dir.glob("inspect_config.yaml.bak.*"))
        assert len(backup_files) == 1
        backup_content = yaml.safe_load(backup_files[0].read_text())
        assert backup_content["project"]["id"] == "original-uuid-12345"

    def test_creates_sanityops_directory_if_missing(self, tmp_path: Path, monkeypatch):
        """Should create .sanityops directory if it doesn't exist."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / ".sanityops").exists()

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        assert (tmp_path / ".sanityops").is_dir()
        assert (tmp_path / ".sanityops" / "inspect_config.yaml").exists()

    def test_works_when_sanityops_directory_exists(self, tmp_path: Path, monkeypatch):
        """Should work when .sanityops directory already exists."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        assert (config_dir / "inspect_config.yaml").exists()

    def test_init_is_registered_as_top_level_command(self):
        """Verify 'init' is registered on the top-level app, not just under 'inspect'."""
        from sanityops_cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "init" in command_names, "'init' should be a top-level command"

    def test_init_is_registered_under_inspect_for_backward_compat(self):
        """Verify 'init' is still registered under 'inspect' for backward compatibility."""
        from sanityops_cli.commands.inspect import inspect_app

        command_names = [cmd.name for cmd in inspect_app.registered_commands]
        assert "init" in command_names, "'init' should remain under 'inspect' for backward compat"


class TestInitConfigPreservesComments:
    """Test that init preserves YAML comments in template."""

    def test_generated_config_contains_model_comment(self, tmp_path: Path, monkeypatch):
        """Should preserve '# Model configuration' comment in output."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "# Model configuration" in content, "Model configuration header comment should be preserved"

    def test_generated_config_contains_provider_comment(self, tmp_path: Path, monkeypatch):
        """Should preserve provider field comment with examples."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "# provider:" in content or "provider:" in content, "Provider field comment should be preserved"

    def test_generated_config_contains_required_optional_labels(self, tmp_path: Path, monkeypatch):
        """Should preserve Required/Optional labels in comments."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "Required:" in content or "# Required" in content, "Required labels should be in comments"

    def test_generated_config_has_valid_uuid_not_placeholder(self, tmp_path: Path, monkeypatch):
        """Should replace placeholder UUID with real UUID."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "00000000-0000-0000-0000-000000000000" not in content, "Placeholder UUID should be replaced"

        # Verify the actual UUID is valid
        data = yaml.safe_load(content)
        uuid.UUID(data["project"]["id"])  # raises if invalid
