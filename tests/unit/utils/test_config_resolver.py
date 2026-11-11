"""Tests for ConfigResolver utility class."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sanityops_cli.utils.config_resolver import (
    ConfigResolver,
    _get_nested_value,
    _read_yaml_file,
    _set_nested_value,
    _unset_nested_value,
    get_global_config_path,
    get_project_config_path,
)


class TestPathResolvers:
    """Test cross-platform path resolution."""

    def test_global_config_path_is_under_home(self):
        """Global config should live under ~/.sanityops/config."""
        path = get_global_config_path()
        assert path.name == "config"
        assert path.parent.name == ".sanityops"
        # Path.home() should be the ancestor
        parts = list(path.parents)
        home = Path.home()
        assert home in parts

    def test_project_config_path_is_under_cwd(self, tmp_path: Path, monkeypatch):
        """Project config should be .sanityops/inspect_config.yaml in cwd."""
        monkeypatch.chdir(tmp_path)
        path = get_project_config_path()
        assert path.name == "inspect_config.yaml"
        assert path.parent.name == ".sanityops"


class TestYamlFileOperations:
    """Test YAML file read/write helpers."""

    def test_read_yaml_file_returns_empty_for_nonexistent(self, tmp_path: Path):
        """Reading a nonexistent file should return empty dict, not raise."""
        result = _read_yaml_file(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_read_yaml_file_parses_valid_yaml(self, tmp_path: Path):
        """Should correctly parse a valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("server:\n  base_url: http://example.com\n")

        result = _read_yaml_file(config_file)
        assert result == {"server": {"base_url": "http://example.com"}}

    def test_read_yaml_file_handles_empty_file(self, tmp_path: Path):
        """Empty YAML file should return empty dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        result = _read_yaml_file(config_file)
        assert result == {}

    def test_read_yaml_file_handles_non_dict_root(self, tmp_path: Path):
        """YAML with non-dict root (e.g., list) should return empty dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2\n")

        result = _read_yaml_file(config_file)
        assert result == {}

    def test_read_yaml_file_handles_gbk_encoding(self, tmp_path: Path):
        """Should fall back to GBK when UTF-8 fails (Windows compatibility)."""
        config_file = tmp_path / "config.yaml"
        # GBK-encoded Chinese comment
        content = "# 注释\nserver:\n  base_url: http://example.com\n"
        config_file.write_bytes(content.encode("gbk"))

        result = _read_yaml_file(config_file)
        assert "server" in result


class TestNestedValueOperations:
    """Test nested dict helpers for dot-notation keys."""

    def test_get_nested_value_top_level(self):
        """Getting a top-level key should work directly."""
        data = {"server": {"base_url": "x"}}
        assert _get_nested_value(data, "server") == {"base_url": "x"}

    def test_get_nested_value_deep(self):
        """Getting a deeply nested key should traverse correctly."""
        data = {"server": {"config": {"base_url": "http://example.com"}}}
        assert _get_nested_value(data, "server.config.base_url") == "http://example.com"

    def test_get_nested_value_missing_key(self):
        """Missing intermediate keys should return None, not raise."""
        data = {"server": {}}
        assert _get_nested_value(data, "server.missing.key") is None

    def test_get_nested_value_non_dict_intermediate(self):
        """If an intermediate value is not a dict, return None."""
        data = {"server": "not-a-dict"}
        assert _get_nested_value(data, "server.base_url") is None

    def test_set_nested_value_creates_intermediates(self):
        """Setting a deep key should create intermediate dicts."""
        data: dict[str, Any] = {}
        _set_nested_value(data, "server.base_url", "http://example.com")
        assert data == {"server": {"base_url": "http://example.com"}}

    def test_set_nested_value_overwrites_leaf(self):
        """Setting an existing key should overwrite the value."""
        data: dict[str, Any] = {"server": {"base_url": "old"}}
        _set_nested_value(data, "server.base_url", "new")
        assert data["server"]["base_url"] == "new"

    def test_unset_nested_value_removes_key(self):
        """Unsetting a key should remove it from the dict."""
        data: dict[str, Any] = {"server": {"base_url": "x"}}
        result = _unset_nested_value(data, "server.base_url")
        assert result is True
        assert "server" not in data  # empty parent dicts are cleaned up

    def test_unset_nested_value_returns_false_for_missing(self):
        """Unsetting a missing key should return False."""
        data: dict[str, Any] = {"server": {}}
        result = _unset_nested_value(data, "server.missing")
        assert result is False


class TestConfigResolverResolve:
    """Test the resolve() method's precedence chain."""

    def test_resolve_returns_default_when_nothing_set(self, tmp_path: Path, monkeypatch):
        """With no config files and no env var, should return default."""
        monkeypatch.chdir(tmp_path)

        # Mock global config path to avoid reading user's real ~/.sanityops/config
        global_path = tmp_path / ".sanityops" / "config"
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        resolver = ConfigResolver(
            config_key="server.base_url",
            env_var="SANITYOPS_BASE_URL",
            default="http://112.94.11.111:16666",
        )
        result = resolver.resolve()
        assert result == "http://112.94.11.111:16666"

    def test_resolve_uses_global_config(self, tmp_path: Path, monkeypatch):
        """Global config should be used when set."""
        monkeypatch.chdir(tmp_path)

        # Write global config
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  base_url: http://global.example.com\n")

        # Patch get_global_config_path to use tmp_path
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        resolver = ConfigResolver(
            config_key="server.base_url",
            env_var="SANITYOPS_BASE_URL",
            default="http://112.94.11.111:16666",
        )
        result = resolver.resolve()
        assert result == "http://global.example.com"

    def test_resolve_project_overrides_global(self, tmp_path: Path, monkeypatch):
        """Project-level config should take precedence over global."""
        monkeypatch.chdir(tmp_path)

        # Write global config
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  base_url: http://global.example.com\n")

        # Write project config
        project_path = tmp_path / ".sanityops" / "inspect_config.yaml"
        project_path.write_text("server:\n  base_url: http://project.example.com\n")

        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        resolver = ConfigResolver(
            config_key="server.base_url",
            env_var="SANITYOPS_BASE_URL",
            default="http://112.94.11.111:16666",
        )
        result = resolver.resolve()
        assert result == "http://project.example.com"

    def test_resolve_env_var_wins_over_project(self, tmp_path: Path, monkeypatch):
        """Environment variables override project config (CI/CD precedence)."""
        monkeypatch.chdir(tmp_path)

        # Set env var
        monkeypatch.setenv("SANITYOPS_BASE_URL", "http://env.example.com")

        # Write project config
        project_path = tmp_path / ".sanityops" / "inspect_config.yaml"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("server:\n  base_url: http://project.example.com\n")

        resolver = ConfigResolver(
            config_key="server.base_url",
            env_var="SANITYOPS_BASE_URL",
            default="http://112.94.11.111:16666",
        )
        result = resolver.resolve()
        assert result == "http://env.example.com"

    def test_resolve_env_var_used_when_no_config(self, tmp_path: Path, monkeypatch):
        """Env var should be used when no config files exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SANITYOPS_API_KEY", "sk-test-key")
        # Mock global config path to avoid reading user's real ~/.sanityops/config
        global_path = tmp_path / ".sanityops" / "config"
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        resolver = ConfigResolver(
            config_key="server.api_key",
            env_var="SANITYOPS_API_KEY",
        )
        result = resolver.resolve()
        assert result == "sk-test-key"

    def test_resolve_blank_project_value_falls_back_to_global(self, tmp_path: Path, monkeypatch):
        """Empty or whitespace-only project value must not shadow global config."""
        monkeypatch.chdir(tmp_path)

        global_path = tmp_path / "home" / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  api_key: sk-global-key\n")
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        project_path = tmp_path / ".sanityops" / "inspect_config.yaml"
        project_path.parent.mkdir(parents=True)
        project_path.write_text('server:\n  api_key: ""\n')

        resolver = ConfigResolver("server.api_key", "SANITYOPS_API_KEY")
        assert resolver.resolve() == "sk-global-key"
        assert resolver.resolve_all_sources()["project"] is None

    def test_resolve_explicit_project_config_path(self, tmp_path: Path, monkeypatch):
        """Explicit project_config_path resolves project overrides regardless of cwd."""
        other_cwd = tmp_path / "elsewhere"
        other_cwd.mkdir()
        monkeypatch.chdir(other_cwd)

        global_path = tmp_path / "home" / ".sanityops" / "config"
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        target_cfg = tmp_path / "target" / ".sanityops" / "inspect_config.yaml"
        target_cfg.parent.mkdir(parents=True)
        target_cfg.write_text("server:\n  base_url: http://target.example.com\n")

        resolver = ConfigResolver(
            "server.base_url",
            project_config_path=target_cfg,
        )
        assert resolver.resolve() == "http://target.example.com"


class TestConfigResolverSetUnset:
    """Test the set_global/set_project and unset methods."""

    def test_set_global_creates_file(self, tmp_path: Path, monkeypatch):
        """set_global should create the global config file if missing."""
        global_path = tmp_path / ".sanityops" / "config"
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        ConfigResolver.set_global("server.base_url", "http://example.com")

        assert global_path.exists()
        data = yaml.safe_load(global_path.read_text())
        assert data["server"]["base_url"] == "http://example.com"

    def test_set_global_merges_with_existing(self, tmp_path: Path, monkeypatch):
        """set_global should merge with existing config, not overwrite."""
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  base_url: http://old.com\n")

        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        ConfigResolver.set_global("server.api_key", "sk-new-key")

        data = yaml.safe_load(global_path.read_text())
        assert data["server"]["base_url"] == "http://old.com"
        assert data["server"]["api_key"] == "sk-new-key"

    def test_set_project_merges_with_existing(self, tmp_path: Path, monkeypatch):
        """set_project should merge with existing inspect_config.yaml."""
        monkeypatch.chdir(tmp_path)

        project_path = tmp_path / ".sanityops" / "inspect_config.yaml"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("project:\n  id: test-uuid\n")

        ConfigResolver.set_project("server.base_url", "http://project.com")

        data = yaml.safe_load(project_path.read_text())
        assert data["project"]["id"] == "test-uuid"
        assert data["server"]["base_url"] == "http://project.com"

    def test_unset_global_removes_key(self, tmp_path: Path, monkeypatch):
        """unset_global should remove the key and return True."""
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  base_url: http://example.com\n")

        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        result = ConfigResolver.unset_global("server.base_url")
        assert result is True

        # The implementation removes the file once no keys remain.
        assert not global_path.exists()

    def test_unset_global_returns_false_for_missing(self, tmp_path: Path, monkeypatch):
        """unset_global should return False if key doesn't exist."""
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server: {}\n")

        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        result = ConfigResolver.unset_global("server.base_url")
        assert result is False


class TestConfigResolverList:
    """Test the list_global and list_project methods."""

    def test_list_global_returns_config_dict(self, tmp_path: Path, monkeypatch):
        """list_global should return the parsed global config."""
        global_path = tmp_path / ".sanityops" / "config"
        global_path.parent.mkdir(parents=True)
        global_path.write_text("server:\n  base_url: http://example.com\n")

        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        result = ConfigResolver.list_global()
        assert result == {"server": {"base_url": "http://example.com"}}

    def test_list_global_returns_empty_for_nonexistent(self, tmp_path: Path, monkeypatch):
        """list_global should return empty dict if file doesn't exist."""
        global_path = tmp_path / ".sanityops" / "config"
        monkeypatch.setattr(
            "sanityops_cli.utils.config_resolver.get_global_config_path",
            lambda: global_path,
        )

        result = ConfigResolver.list_global()
        assert result == {}

    def test_list_project_returns_config_dict(self, tmp_path: Path, monkeypatch):
        """list_project should return the parsed project config."""
        monkeypatch.chdir(tmp_path)

        project_path = tmp_path / ".sanityops" / "inspect_config.yaml"
        project_path.parent.mkdir(parents=True)
        project_path.write_text("project:\n  id: test-uuid\n")

        result = ConfigResolver.list_project()
        assert result == {"project": {"id": "test-uuid"}}
