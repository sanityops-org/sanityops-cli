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

"""Tests for config_resolver module."""

from pathlib import Path
from typing import Any

import yaml


class TestConfigResolverPaths:
    """Test path resolution functions."""

    def test_get_global_config_path(self, monkeypatch):
        """Global config path should be ~/.sanityops/config."""
        from sanityops_cli.utils.config_resolver import get_global_config_path

        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))
        path = get_global_config_path()
        assert path == Path("/fake/home/.sanityops/config")

    def test_get_project_config_path(self, monkeypatch, tmp_path: Path):
        """Project config path should be .sanityops/inspect_config.yaml."""
        from sanityops_cli.utils.config_resolver import get_project_config_path

        monkeypatch.chdir(tmp_path)
        path = get_project_config_path()
        assert path == tmp_path / ".sanityops" / "inspect_config.yaml"


class TestYamlFileOperations:
    """Test YAML file read/write operations."""

    def test_read_yaml_file_returns_dict(self, tmp_path: Path):
        """Should read YAML file and return dict."""
        from sanityops_cli.utils.config_resolver import _read_yaml_file

        config_file = tmp_path / "config.yaml"
        config_file.write_text("server:\n  base_url: https://example.com\n")

        result = _read_yaml_file(config_file)
        assert result == {"server": {"base_url": "https://example.com"}}

    def test_read_yaml_file_nonexistent_returns_empty(self, tmp_path: Path):
        """Should return empty dict for nonexistent file."""
        from sanityops_cli.utils.config_resolver import _read_yaml_file

        result = _read_yaml_file(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_read_yaml_file_invalid_yaml_returns_empty(self, tmp_path: Path):
        """Should return empty dict for invalid YAML."""
        from sanityops_cli.utils.config_resolver import _read_yaml_file

        bad_file = tmp_path / "bad.yaml"
        # Use truly invalid YAML (unclosed bracket)
        bad_file.write_text("key: [\nmissing bracket\n")

        result = _read_yaml_file(bad_file)
        assert result == {}

    def test_write_yaml_file_creates_file(self, tmp_path: Path):
        """Should write data to YAML file."""
        from sanityops_cli.utils.config_resolver import _write_yaml_file

        config_file = tmp_path / "config.yaml"
        data = {"server": {"base_url": "https://example.com"}}

        _write_yaml_file(config_file, data)

        assert config_file.exists()
        content = yaml.safe_load(config_file.read_text())
        assert content == data

    def test_write_yaml_file_creates_parent_dirs(self, tmp_path: Path):
        """Should create parent directories if needed."""
        from sanityops_cli.utils.config_resolver import _write_yaml_file

        config_file = tmp_path / "subdir" / "config.yaml"
        data = {"key": "value"}

        _write_yaml_file(config_file, data)

        assert config_file.exists()
        assert config_file.parent.is_dir()


class TestNestedKeyOperations:
    """Test nested key get/set/unset operations."""

    def test_get_nested_value_simple(self):
        """Should get top-level key."""
        from sanityops_cli.utils.config_resolver import _get_nested_value

        data = {"key": "value"}
        assert _get_nested_value(data, "key") == "value"

    def test_get_nested_value_dot_notation(self):
        """Should get nested value using dot notation."""
        from sanityops_cli.utils.config_resolver import _get_nested_value

        data = {"server": {"base_url": "https://example.com"}}
        assert _get_nested_value(data, "server.base_url") == "https://example.com"

    def test_get_nested_value_missing_key_returns_none(self):
        """Should return None for missing key."""
        from sanityops_cli.utils.config_resolver import _get_nested_value

        data = {"server": {}}
        assert _get_nested_value(data, "server.base_url") is None

    def test_set_nested_value_creates_nested_dict(self):
        """Should set value creating intermediate dicts."""
        from sanityops_cli.utils.config_resolver import _set_nested_value

        data: dict[str, Any] = {}
        _set_nested_value(data, "server.base_url", "https://example.com")
        assert data == {"server": {"base_url": "https://example.com"}}

    def test_set_nested_value_overwrites_existing(self):
        """Should overwrite existing value."""
        from sanityops_cli.utils.config_resolver import _set_nested_value

        data: dict[str, Any] = {"server": {"base_url": "old"}}
        _set_nested_value(data, "server.base_url", "new")
        assert data["server"]["base_url"] == "new"

    def test_unset_nested_value_removes_key(self):
        """Should remove nested key."""
        from sanityops_cli.utils.config_resolver import _unset_nested_value

        data: dict[str, Any] = {"server": {"base_url": "value", "api_key": "key"}}
        result = _unset_nested_value(data, "server.base_url")
        assert result is True
        assert "base_url" not in data["server"]
        assert data["server"]["api_key"] == "key"

    def test_unset_nested_value_missing_returns_false(self):
        """Should return False for missing key."""
        from sanityops_cli.utils.config_resolver import _unset_nested_value

        data: dict[str, Any] = {"server": {}}
        result = _unset_nested_value(data, "server.missing")
        assert result is False


class TestConfigResolverPrecedence:
    """Test precedence chain: project > global > env > default."""

    def test_resolve_returns_default_when_nothing_set(self, monkeypatch, tmp_path: Path):
        """Should return default when no config or env set."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)
        # Mock home to avoid touching real ~/.sanityops
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        resolver = ConfigResolver("server.base_url", env_var="SANITYOPS_BASE_URL", default="https://default.com")
        result = resolver.resolve()
        assert result == "https://default.com"

    def test_resolve_env_overrides_default(self, monkeypatch, tmp_path: Path):
        """Environment variable should override default."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setenv("SANITYOPS_BASE_URL", "https://env.example.com")

        resolver = ConfigResolver("server.base_url", env_var="SANITYOPS_BASE_URL", default="https://default.com")
        result = resolver.resolve()
        assert result == "https://env.example.com"

    def test_resolve_global_overrides_env(self, monkeypatch, tmp_path: Path):
        """Global config should override env and default."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setenv("SANITYOPS_BASE_URL", "https://env.example.com")

        # Create global config
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://global.example.com\n")

        resolver = ConfigResolver("server.base_url", env_var="SANITYOPS_BASE_URL", default="https://default.com")
        result = resolver.resolve()
        assert result == "https://global.example.com"

    def test_resolve_project_overrides_global(self, monkeypatch, tmp_path: Path):
        """Project config should override global, env, default."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)
        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.setenv("SANITYOPS_BASE_URL", "https://env.example.com")

        # Create global config
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://global.example.com\n")

        # Create project config
        project_config_dir = tmp_path / ".sanityops"
        project_config_dir.mkdir(parents=True)
        project_config = project_config_dir / "inspect_config.yaml"
        project_config.write_text("server:\n  base_url: https://project.example.com\n")

        resolver = ConfigResolver("server.base_url", env_var="SANITYOPS_BASE_URL", default="https://default.com")
        result = resolver.resolve()
        assert result == "https://project.example.com"


class TestConfigResolverSetUnset:
    """Test set/unset/list operations."""

    def test_set_global_creates_file(self, monkeypatch, tmp_path: Path):
        """Should create global config file."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        ConfigResolver.set_global("server.base_url", "https://example.com")

        global_config = home_dir / ".sanityops" / "config"
        assert global_config.exists()
        data = yaml.safe_load(global_config.read_text())
        assert data == {"server": {"base_url": "https://example.com"}}

    def test_set_global_merges_with_existing(self, monkeypatch, tmp_path: Path):
        """Should merge with existing global config."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        # Create existing config
        global_config_dir = home_dir / ".sanityops"
        global_config_dir.mkdir(parents=True)
        global_config = global_config_dir / "config"
        global_config.write_text("server:\n  base_url: https://old.com\n")

        ConfigResolver.set_global("server.api_key", "my-key")

        data = yaml.safe_load(global_config.read_text())
        assert data["server"]["base_url"] == "https://old.com"
        assert data["server"]["api_key"] == "my-key"

    def test_set_project_creates_file(self, tmp_path: Path, monkeypatch):
        """Should create project config file."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)

        ConfigResolver.set_project("server.base_url", "https://example.com")

        project_config = tmp_path / ".sanityops" / "inspect_config.yaml"
        assert project_config.exists()

    def test_unset_global_removes_key(self, monkeypatch, tmp_path: Path):
        """Should remove key from global config."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        # Create config with key
        ConfigResolver.set_global("server.base_url", "https://example.com")
        ConfigResolver.set_global("server.api_key", "my-key")

        result = ConfigResolver.unset_global("server.base_url")

        assert result is True
        data = yaml.safe_load((home_dir / ".sanityops" / "config").read_text())
        assert "base_url" not in data["server"]
        assert data["server"]["api_key"] == "my-key"

    def test_unset_global_missing_key_returns_false(self, monkeypatch, tmp_path: Path):
        """Should return False when key doesn't exist."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        result = ConfigResolver.unset_global("nonexistent.key")
        assert result is False

    def test_list_global_returns_dict(self, monkeypatch, tmp_path: Path):
        """Should return all global config values."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        home_dir = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home_dir)

        ConfigResolver.set_global("server.base_url", "https://example.com")
        ConfigResolver.set_global("server.api_key", "my-key")

        result = ConfigResolver.list_global()
        assert result["server"]["base_url"] == "https://example.com"
        assert result["server"]["api_key"] == "my-key"

    def test_list_project_returns_dict(self, tmp_path: Path, monkeypatch):
        """Should return all project config values."""
        from sanityops_cli.utils.config_resolver import ConfigResolver

        monkeypatch.chdir(tmp_path)

        ConfigResolver.set_project("server.base_url", "https://example.com")

        result = ConfigResolver.list_project()
        assert result["server"]["base_url"] == "https://example.com"
