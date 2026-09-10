"""Tests for inspect init command."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from sanityops_cli.main import app
from sanityops_cli.utils.config_loader import PROJECT_ID_PLACEHOLDER as PLACEHOLDER_UUID


def test_init_prints_file_created_message(tmp_path: Path, monkeypatch):
    """Should confirm the config file was created."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Created .sanityops/inspect_config.yaml" in result.output


def test_init_prints_artifact_and_model_guidance(tmp_path: Path, monkeypatch):
    """Should guide users to edit artifacts and model configuration."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Before running inspect, you need:" in result.output
    assert "- Edit this file to add your prompts, tools, and skills." in result.output
    assert "- Edit this file to add your provider, api_key, model_id and base_url" in result.output
    assert "optional." in result.output
    assert "If omitted, the CLI uses LLM_* environment variables)." in result.output


def test_init_prints_server_config_guidance(tmp_path: Path, monkeypatch):
    """Should guide users to configure the server URL and API key."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert (
        "- To connect to the Sanityops service, configure the server URL and API key:"
        in result.output
    )
    assert 'sanityops-cli config server.base_url "<your-server-url>"' in result.output
    assert 'sanityops-cli config server.api_key "<your-api-key>"' in result.output


class TestInitConfig:
    """Test cases for init_config function."""

    def test_creates_config_file_when_none_exists(self, tmp_path: Path, monkeypatch):
        """Should create .sanityops/inspect_config.yaml with placeholder UUID."""
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
        assert "name" in content["project"]

        # Verify placeholder UUID is kept (project not yet bound)
        project_id = content["project"]["id"]
        assert project_id == PLACEHOLDER_UUID
        assert content["project"]["name"] == ""

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

        # Assert - new file created with placeholder UUID (not the old one)
        new_content = yaml.safe_load(config_file.read_text())
        assert new_content["project"]["id"] == PLACEHOLDER_UUID

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
        assert "provider: anthropic" in content, "Provider field comment should be preserved"

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

    def test_generated_config_keeps_placeholder_uuid(self, tmp_path: Path, monkeypatch):
        """Should keep placeholder UUID so the project can be auto-created later."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert PLACEHOLDER_UUID in content, "Placeholder UUID should be preserved for unbound project"

        # Placeholder is a valid UUID format but signals "not yet bound"
        data = yaml.safe_load(content)
        assert data["project"]["id"] == PLACEHOLDER_UUID
