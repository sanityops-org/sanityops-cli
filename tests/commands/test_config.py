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

"""Tests for config command."""

from pathlib import Path

import yaml


class TestConfigCommandRead:
    """Test reading config values."""

    def test_read_global_base_url(self, monkeypatch, tmp_path: Path):
        """Should read server.base_url from global config."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        # Mock home directory
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create global config
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://example.com\n")

        result = runner.invoke(config_app, ["server.base_url"])
        assert result.exit_code == 0
        assert "https://example.com" in result.output

    def test_read_unset_key_shows_not_set(self, monkeypatch, tmp_path: Path):
        """Should show 'not set' message for missing key."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        result = runner.invoke(config_app, ["server.api_key"])
        assert "not set" in result.output.lower()


class TestConfigCommandSet:
    """Test setting config values."""

    def test_set_global_base_url(self, monkeypatch, tmp_path: Path):
        """Should set server.base_url in global config."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(config_app, ["server.base_url", "https://new.example.com"])

        assert result.exit_code == 0
        assert "Set server.base_url in global config" in result.output

        # Verify file was created
        global_config = home_dir / ".sanityops" / "config"
        assert global_config.exists()
        data = yaml.safe_load(global_config.read_text())
        assert data["server"]["base_url"] == "https://new.example.com"

    def test_set_api_key_global(self, monkeypatch, tmp_path: Path):
        """Should set server.api_key in global config."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(config_app, ["server.api_key", "my-secret-api-key"])

        assert result.exit_code == 0
        assert "Set server.api_key in global config" in result.output

        # Verify file was created with API key
        global_config = home_dir / ".sanityops" / "config"
        assert global_config.exists()
        data = yaml.safe_load(global_config.read_text())
        assert data["server"]["api_key"] == "my-secret-api-key"

    def test_set_local_creates_project_config(self, monkeypatch, tmp_path: Path):
        """Should set value in project config with --local flag."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        result = runner.invoke(config_app, ["server.base_url", "https://project.com", "--local"])

        assert result.exit_code == 0
        assert "project config" in result.output.lower()

        project_config = tmp_path / ".sanityops" / "inspect_config.yaml"
        assert project_config.exists()


class TestConfigCommandList:
    """Test listing config values."""

    def test_list_empty_shows_hint(self, monkeypatch, tmp_path: Path):
        """Should show setup hint when no config exists."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        assert "No configuration" in result.output or "Run:" in result.output

    def test_list_shows_values(self, monkeypatch, tmp_path: Path):
        """Should display config values in table."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create global config
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://example.com\n")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        assert "server.base_url" in result.output
        assert "https://example.com" in result.output

    def test_list_shows_empty_for_unset_in_one_column(self, monkeypatch, tmp_path: Path):
        """Keys set in global but not project show empty cell in Project column."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create global config with base_url
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://example.com\n")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        assert "server.base_url" in result.output
        assert "https://example.com" in result.output
        # The Project column shows empty string, not "(not set)"
        assert "(not set)" not in result.output

    def test_list_shows_env_vars(self, monkeypatch, tmp_path: Path):
        """Should display environment variables set for config keys."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SANITYOPS_BASE_URL", "https://env.example.com")

        # Need at least one config to avoid early "No configuration found" return
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        (global_config_dir / "config").write_text("server:\n  api_key: test-key\n")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        assert "SANITYOPS_BASE_URL" in result.output
        assert "https://env.example.com" in result.output


class TestConfigCommandUnset:
    """Test unsetting config values."""

    def test_unset_global_removes_key(self, monkeypatch, tmp_path: Path):
        """Should remove key from global config."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create global config with key
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://example.com\n  api_key: my-key\n")

        result = runner.invoke(config_app, ["--unset", "server.base_url"])

        assert result.exit_code == 0
        assert "Removed" in result.output

        data = yaml.safe_load(global_config.read_text())
        assert "base_url" not in data["server"]
        assert data["server"]["api_key"] == "my-key"

    def test_unset_with_both_flags_global_wins(self, monkeypatch, tmp_path: Path):
        """When both --global and --local are passed, --global should win."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create global config with key
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://global.example.com\n")

        # Create project config with same key
        project_config_dir = tmp_path / ".sanityops"
        project_config_dir.mkdir(parents=True)
        project_config = project_config_dir / "inspect_config.yaml"
        project_config.write_text("server:\n  base_url: https://project.example.com\n")

        # Unset with both flags --global should win
        result = runner.invoke(config_app, ["--unset", "server.base_url", "--global", "--local"])

        assert result.exit_code == 0
        assert "global config" in result.output.lower()

        # Global config should have key removed
        data = yaml.safe_load(global_config.read_text())
        assert "base_url" not in data.get("server", {})

        # Project config should be unchanged
        data = yaml.safe_load(project_config.read_text())
        assert data["server"]["base_url"] == "https://project.example.com"


class TestSensitiveValueMasking:
    """Test that sensitive values are masked on display."""

    def test_api_key_is_masked(self, monkeypatch, tmp_path: Path):
        """Should mask API key in output."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create config with API key
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  api_key: my-secret-api-key-12345\n")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        # Should contain masked version, not full key
        assert "my-***2345" in result.output
        assert "my-secret-api-key-12345" not in result.output

    def test_short_api_key_fully_masked(self, monkeypatch, tmp_path: Path):
        """Short API keys should be fully masked."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  api_key: short\n")

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        assert "short" not in result.output

    def test_read_sensitive_key_does_not_prompt_or_write(self, monkeypatch, tmp_path: Path):
        """Should READ (not prompt/write) when reading sensitive key without value."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create config with API key
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        original_content = "server:\n  api_key: my-secret-api-key-12345\n"
        global_config.write_text(original_content)

        # Read the API key (no value argument)
        result = runner.invoke(config_app, ["server.api_key"])

        assert result.exit_code == 0
        # Should contain masked version, not full key
        assert "my-***2345" in result.output
        assert "my-secret-api-key-12345" not in result.output

        # Config file should be unchanged
        assert global_config.read_text() == original_content

    def test_non_string_api_key_is_masked(self, monkeypatch, tmp_path: Path):
        """Non-string API key values from manually-edited YAML should be masked."""
        from typer.testing import CliRunner

        from sanityops_cli.commands.config import config_app

        runner = CliRunner()

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(tmp_path)

        # Create config with numeric API key (manually edited YAML)
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  api_key: 12345678\n")  # Integer in YAML

        result = runner.invoke(config_app, ["--list"])

        assert result.exit_code == 0
        # Should contain masked version of the stringified integer
        assert "123***5678" in result.output
