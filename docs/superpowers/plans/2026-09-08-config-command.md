# Config Subcommand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the `config` subcommand from deeplogic-cli to sanityops-cli, providing CLI-based configuration management for server URL and API key.

**Architecture:** Create three new files (`constants/config_defaults.py`, `utils/config_resolver.py`, `commands/config.py`) and modify `main.py` to register the config subcommand. ConfigResolver handles the precedence chain (project > global > env > default) with YAML read/write. The config command provides get/set/list/unset operations via Typer CLI.

**Tech Stack:** Python 3.11+, Typer, Rich, PyYAML

## Global Constraints

- Config keys: `server.base_url`, `server.api_key` only
- Environment variables: `SANITYOPS_BASE_URL`, `SANITYOPS_API_KEY`
- Default server URL: `https://www.sanityops.org/demo`
- Project config path: `.sanityops/inspect_config.yaml`
- Global config path: `~/.sanityops/config`
- Copyright header required on all new files
- Tests use `tmp_path` and `monkeypatch` fixtures, never touch real `~/.sanityops/`

---

## Task 1: Create config_defaults.py

**Files:**
- Create: `src/sanityops_cli/constants/config_defaults.py`

**Interfaces:**
- Produces: `DEFAULT_SERVER_BASE_URL` constant

- [ ] **Step 1: Create the constants file**

```python
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

"""Default values for sanityops configuration.

Central place for config key defaults so they can be adjusted in one spot.
"""

# Default sanityops SaaS backend base URL (server.base_url)
DEFAULT_SERVER_BASE_URL = "https://www.sanityops.org/demo"
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from sanityops_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL; print(DEFAULT_SERVER_BASE_URL)"`
Expected: `https://www.sanityops.org/demo`

- [ ] **Step 3: Commit**

```bash
git add src/sanityops_cli/constants/config_defaults.py
git commit -m "feat(constants): add DEFAULT_SERVER_BASE_URL for config command"
```

---

## Task 2: Create config_resolver.py

**Files:**
- Create: `src/sanityops_cli/utils/config_resolver.py`
- Test: `tests/utils/test_config_resolver.py`

**Interfaces:**
- Produces: `ConfigResolver` class with:
  - `__init__(config_key: str, env_var: str | None, default: str | None)`
  - `resolve() -> str | None`
  - `resolve_all_sources() -> dict[str, str | None]`
  - `set_global(key: str, value: str) -> None` (static)
  - `set_project(key: str, value: str) -> None` (static)
  - `unset_global(key: str) -> bool` (static)
  - `unset_project(key: str) -> bool` (static)
  - `list_global() -> dict[str, Any]` (static)
  - `list_project() -> dict[str, Any]` (static)
- Consumes: `read_file_with_encoding_fallback` from `config_loader.py`

### Task 2.1: Write helper functions and ConfigResolver basic tests

- [ ] **Step 1: Create the test file with first failing test**

```python
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

import os
from pathlib import Path

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/utils/test_config_resolver.py -v`
Expected: FAIL with module import error

- [ ] **Step 3: Create config_resolver.py with path functions**

```python
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

"""Generic config resolver with precedence chain: project > global > env > default."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from sanityops_cli.utils.config_loader import read_file_with_encoding_fallback

# Default config file locations
DEFAULT_PROJECT_CONFIG_DIR = ".sanityops"
DEFAULT_PROJECT_CONFIG_FILE = "inspect_config.yaml"
GLOBAL_CONFIG_DIR = ".sanityops"
GLOBAL_CONFIG_FILE = "config"


def get_global_config_path() -> Path:
    """Return the global config file path, cross-platform.

    Uses Path.home() which correctly resolves:
    - macOS/Linux: $HOME
    - Windows: %USERPROFILE%
    """
    return Path.home() / GLOBAL_CONFIG_DIR / GLOBAL_CONFIG_FILE


def get_project_config_path() -> Path:
    """Return the project-level config file path in current working directory."""
    return Path.cwd() / DEFAULT_PROJECT_CONFIG_DIR / DEFAULT_PROJECT_CONFIG_FILE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/utils/test_config_resolver.py::TestConfigResolverPaths -v`
Expected: PASS

### Task 2.2: Add YAML read/write helpers

- [ ] **Step 1: Add test for _read_yaml_file**

```python
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
        bad_file.write_text(":::invalid:::\n")

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/utils/test_config_resolver.py::TestYamlFileOperations -v`
Expected: FAIL with function not found

- [ ] **Step 3: Add YAML helper functions**

Add to `config_resolver.py` after the path functions:

```python


def _read_yaml_file(path: Path) -> dict[str, Any]:
    """Read a YAML file with encoding fallback (UTF-8 -> GBK for Windows).

    Returns empty dict if file doesn't exist or is unreadable.
    """
    if not path.exists() or not path.is_file():
        return {}

    content = read_file_with_encoding_fallback(path)
    if content is None:
        return {}

    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return {}
        return data
    except yaml.YAMLError:
        return {}


def _write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file with atomic replacement.

    Creates parent directories if needed.
    Uses temp file + rename to prevent corruption on interruption.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        tmp_path.replace(path)  # Atomic on POSIX, near-atomic on Windows
    except Exception:
        # Clean up temp file on failure
        if tmp_path.exists():
            tmp_path.unlink()
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/utils/test_config_resolver.py::TestYamlFileOperations -v`
Expected: PASS

### Task 2.3: Add nested key helpers

- [ ] **Step 1: Add tests for nested key operations**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/utils/test_config_resolver.py::TestNestedKeyOperations -v`
Expected: FAIL with function not found

- [ ] **Step 3: Add nested key helper functions**

Add to `config_resolver.py` after `_write_yaml_file`:

```python


def _get_nested_value(data: dict[str, Any], key: str) -> Any:
    """Get a nested value from a dict using dot-separated key.

    Example: _get_nested_value({"server": {"base_url": "x"}}, "server.base_url")
    Returns None if any intermediate key is missing or not a dict.
    """
    parts = key.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _set_nested_value(data: dict[str, Any], key: str, value: Any) -> None:
    """Set a nested value in a dict using dot-separated key.

    Creates intermediate dicts as needed.
    Example: _set_nested_value(data, "server.base_url", "x")
    """
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _unset_nested_value(data: dict[str, Any], key: str) -> bool:
    """Remove a nested key from a dict using dot-separated key.

    Returns True if key was present and removed, False otherwise.
    Does not remove empty intermediate dicts.
    """
    parts = key.split(".")
    current = data

    # Navigate to parent
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]

    if not isinstance(current, dict):
        return False

    final_key = parts[-1]
    if final_key in current:
        del current[final_key]
        return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/utils/test_config_resolver.py::TestNestedKeyOperations -v`
Expected: PASS

### Task 2.4: Add ConfigResolver class

- [ ] **Step 1: Add tests for ConfigResolver.resolve()**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/utils/test_config_resolver.py::TestConfigResolverPrecedence -v`
Expected: FAIL with ConfigResolver not found

- [ ] **Step 3: Add ConfigResolver class**

Add to `config_resolver.py` after `_unset_nested_value`:

```python


class ConfigResolver:
    """Generic config resolver with precedence chain.

    Precedence: project-level > global > environment variable > default.

    Attributes:
        config_key: Dot-separated config key (e.g., "server.base_url").
        env_var: Environment variable name (e.g., "SANITYOPS_BASE_URL").
        default: Default value if none of the above provide a value.
    """

    def __init__(
        self,
        config_key: str,
        env_var: str | None = None,
        default: str | None = None,
    ):
        self.config_key = config_key
        self.env_var = env_var
        self.default = default

    def resolve(self) -> str | None:
        """Resolve config value following precedence chain.

        Returns:
            The resolved value, or None if not found and no default.
        """
        # 1. Project-level config
        project_config = _read_yaml_file(get_project_config_path())
        value = _get_nested_value(project_config, self.config_key)
        if value is not None:
            return str(value) if not isinstance(value, str) else value

        # 2. Global config
        global_config = _read_yaml_file(get_global_config_path())
        value = _get_nested_value(global_config, self.config_key)
        if value is not None:
            return str(value) if not isinstance(value, str) else value

        # 3. Environment variable
        if self.env_var:
            env_value = os.environ.get(self.env_var)
            if env_value is not None:
                return env_value

        # 4. Default
        return self.default

    def resolve_all_sources(self) -> dict[str, str | None]:
        """Resolve value from each source for display purposes.

        Returns dict with keys: 'project', 'global', 'env', 'default'.
        Useful for --list output showing where each value comes from.
        """
        result: dict[str, str | None] = {}

        # Project-level
        project_config = _read_yaml_file(get_project_config_path())
        project_value = _get_nested_value(project_config, self.config_key)
        result["project"] = str(project_value) if project_value is not None else None

        # Global
        global_config = _read_yaml_file(get_global_config_path())
        global_value = _get_nested_value(global_config, self.config_key)
        result["global"] = str(global_value) if global_value is not None else None

        # Env
        result["env"] = os.environ.get(self.env_var) if self.env_var else None

        # Default
        result["default"] = self.default

        return result

    @staticmethod
    def set_global(key: str, value: str) -> None:
        """Set a value in the global config file.

        Creates the file if it doesn't exist. Merges with existing content.
        """
        path = get_global_config_path()
        data = _read_yaml_file(path)
        _set_nested_value(data, key, value)
        _write_yaml_file(path, data)

    @staticmethod
    def set_project(key: str, value: str) -> None:
        """Set a value in the project-level config file.

        Creates the file if it doesn't exist. Merges with existing content.
        """
        path = get_project_config_path()
        data = _read_yaml_file(path)
        _set_nested_value(data, key, value)
        _write_yaml_file(path, data)

    @staticmethod
    def unset_global(key: str) -> bool:
        """Remove a key from the global config file.

        Returns True if key was present and removed, False otherwise.
        """
        path = get_global_config_path()
        data = _read_yaml_file(path)
        if not data:
            return False
        removed = _unset_nested_value(data, key)
        if removed:
            _write_yaml_file(path, data)
        return removed

    @staticmethod
    def unset_project(key: str) -> bool:
        """Remove a key from the project-level config file.

        Returns True if key was present and removed, False otherwise.
        """
        path = get_project_config_path()
        data = _read_yaml_file(path)
        if not data:
            return False
        removed = _unset_nested_value(data, key)
        if removed:
            _write_yaml_file(path, data)
        return removed

    @staticmethod
    def list_global() -> dict[str, Any]:
        """List all config values from global config file."""
        return _read_yaml_file(get_global_config_path())

    @staticmethod
    def list_project() -> dict[str, Any]:
        """List all config values from project-level config file."""
        return _read_yaml_file(get_project_config_path())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/utils/test_config_resolver.py::TestConfigResolverPrecedence -v`
Expected: PASS

### Task 2.5: Add tests for set/unset/list methods

- [ ] **Step 1: Add tests for set_global, set_project, unset, list**

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/utils/test_config_resolver.py::TestConfigResolverSetUnset -v`
Expected: PASS (all methods already implemented)

### Task 2.6: Commit config_resolver

- [ ] **Step 1: Run all config_resolver tests**

Run: `pytest tests/utils/test_config_resolver.py -v`
Expected: All PASS

- [ ] **Step 2: Commit**

```bash
git add src/sanityops_cli/utils/config_resolver.py tests/utils/test_config_resolver.py
git commit -m "feat(utils): add ConfigResolver for config management with precedence chain"
```

---

## Task 3: Create commands/config.py

**Files:**
- Create: `src/sanityops_cli/commands/config.py`
- Test: `tests/commands/test_config.py`

**Interfaces:**
- Consumes: `ConfigResolver` from Task 2, `DEFAULT_SERVER_BASE_URL` from Task 1, `EXIT_FAILURE` from `constants/exit_codes.py`
- Produces: `config_app` (Typer app) for registration in main.py

### Task 3.1: Write config command tests

- [ ] **Step 1: Create test file with first failing test**

```python
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
        assert "my-s***2345" in result.output or "***" in result.output
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_config.py -v`
Expected: FAIL with module import error

### Task 3.2: Implement config command

- [ ] **Step 1: Create commands/config.py**

```python
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

"""config command — Get and set sanityops configuration.

Config keys use dot notation, e.g. ``server.base_url``. They correspond to
the sanityops SaaS backend (NOT the LLM model config, which lives under
``model.*``). Precedence: project-level > global > env var > default.
"""

from __future__ import annotations

import getpass
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from sanityops_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.utils.config_resolver import ConfigResolver

console = Console()

# Create a Typer app for config subcommand
config_app = typer.Typer(
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
    no_args_is_help=True,
)

# Registry of known config keys: metadata for reading defaults / masking.
# New config keys can be added here without touching resolve logic.
CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "server.base_url": {
        "env": "SANITYOPS_BASE_URL",
        "default": DEFAULT_SERVER_BASE_URL,
        "sensitive": False,
    },
    "server.api_key": {
        "env": "SANITYOPS_API_KEY",
        "default": None,
        "sensitive": True,
    },
}


def _is_sensitive_key(key: str) -> bool:
    """Check if a key holds a sensitive value (masked on display)."""
    return bool(CONFIG_SCHEMA.get(key, {}).get("sensitive"))


def _mask_sensitive_value(value: str | None) -> str:
    """Mask a sensitive value for display: first 3 + '***' + last 4 chars.

    Short values (< 8 chars) are fully masked. None -> '(not set)'.
    """
    if value is None:
        return "(not set)"
    if len(value) <= 7:
        return "***"
    return f"{value[:3]}***{value[-4:]}"


def _display_value(key: str, value: str | None) -> str:
    """Return the value as it should be shown, masking sensitive keys."""
    if value is None:
        return ""
    if _is_sensitive_key(key):
        return _mask_sensitive_value(value)
    return str(value)


def _flatten_config(data: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested config dict into (dot.key, value) tuples."""
    result: list[tuple[str, Any]] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten_config(value, full_key))
        else:
            result.append((full_key, value))
    return result


@config_app.callback(invoke_without_command=True)
def config_callback(
    ctx: typer.Context,
    key: str = typer.Argument(None, help="Config key, e.g. server.base_url"),
    value: str = typer.Argument(None, help="Config value (omit to read)"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all config values"),
    unset: str = typer.Option(None, "--unset", help="Remove a config key"),
    global_config: bool = typer.Option(
        False,
        "--global",
        help="Operate on global config (default behavior)",
    ),
    local_config: bool = typer.Option(
        False,
        "--local",
        help="Operate on project-level config",
    ),
) -> None:
    """Get, set, or list sanityops configuration values.

    Precedence: project-level > global > environment variables > default.

    Examples:
        sanityops-cli config server.base_url               # Read value
        sanityops-cli config server.base_url http://...    # Set (global, default)
        sanityops-cli config server.base_url http://... --local   # Set project-level
        sanityops-cli config server.api_key                # Prompt (masked input)
        sanityops-cli config --list                         # List all values
        sanityops-cli config --unset server.base_url        # Remove key
    """
    # Hide the unused --global flag from linters while keeping it documented.
    del global_config

    if list_all:
        _list_config()
        return

    if unset:
        _unset_config(unset, local=local_config)
        return

    if not key:
        console.print(ctx.get_help())
        return

    use_local = local_config  # --local overrides; default is global

    if value is None:
        # Interactive masked input for sensitive keys on a TTY.
        if _is_sensitive_key(key) and sys.stdin.isatty():
            entered = getpass.getpass(f"Enter {key}: ")
            _write_config(key, entered, local=use_local)
        else:
            _read_config(key)
    else:
        _write_config(key, value, local=use_local)


def _read_config(key: str) -> None:
    """Read and display a config value."""
    schema = CONFIG_SCHEMA.get(key, {})
    resolver = ConfigResolver(
        config_key=key,
        env_var=schema.get("env"),
        default=schema.get("default"),
    )
    resolved = resolver.resolve()

    if resolved is None:
        console.print(f"[yellow]{key} is not set[/yellow]")
        raise typer.Exit()

    console.print(_display_value(key, resolved))


def _write_config(key: str, value: str, local: bool = False) -> None:
    """Write a config value to the global or project config file."""
    try:
        if local:
            ConfigResolver.set_project(key, value)
            console.print(f"[green]✓[/green] Set {key} in project config")
        else:
            ConfigResolver.set_global(key, value)
            console.print(f"[green]✓[/green] Set {key} in global config")
    except Exception as e:
        console.print(f"[red]✗ Failed to write config: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None


def _unset_config(key: str, local: bool = False) -> None:
    """Remove a config key from the global or project config file."""
    try:
        removed = ConfigResolver.unset_project(key) if local else ConfigResolver.unset_global(key)
        if removed:
            location = "project config" if local else "global config"
            console.print(f"[green]✓[/green] Removed {key} from {location}")
        else:
            console.print(f"[yellow]{key} was not set[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Failed to unset config: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None


def _list_config() -> None:
    """List all config values from global and project configs."""
    global_config = ConfigResolver.list_global()
    project_config = ConfigResolver.list_project()

    if not global_config and not project_config:
        console.print("[yellow]No configuration found[/yellow]")
        console.print("\n  Run: sanityops-cli config server.base_url <url>")
        console.print("  Run: sanityops-cli config server.api_key <key>")
        return

    table = Table(title="[bold]Sanityops Configuration[/]", border_style="blue")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Global", style="white")
    table.add_column("Project", style="green")

    # Merge keys from both configs.
    items: dict[str, tuple[Any, Any]] = {}
    for k, v in _flatten_config(global_config):
        items.setdefault(k, (None, None))
        items[k] = (v, items[k][1])
    for k, v in _flatten_config(project_config):
        items.setdefault(k, (None, None))
        items[k] = (items[k][0], v)

    for key in sorted(items):
        global_val, project_val = items[key]
        table.add_row(
            key,
            _display_value(key, str(global_val) if global_val is not None else None),
            _display_value(key, str(project_val) if project_val is not None else None),
        )

    console.print(table)

    # Report which known env vars are set.
    env_set = [
        (env_name, _display_value(key, os_val))
        for key, env_name, os_val in (
            (
                k,
                v["env"],
                __import__("os").environ.get(v["env"]),
            )
            for k, v in CONFIG_SCHEMA.items()
            if v.get("env")
        )
        if os_val
    ]
    if env_set:
        console.print("\n[dim]Environment variables set:[/dim]")
        for env_name, val in env_set:
            console.print(f"  [dim]{env_name}={val}[/dim]")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/commands/test_config.py -v`
Expected: All PASS

### Task 3.3: Commit config command

- [ ] **Step 1: Run all config tests**

Run: `pytest tests/commands/test_config.py -v`
Expected: All PASS

- [ ] **Step 2: Commit**

```bash
git add src/sanityops_cli/commands/config.py tests/commands/test_config.py
git commit -m "feat(commands): add config subcommand for managing server URL and API key"
```

---

## Task 4: Register config_app in main.py

**Files:**
- Modify: `src/sanityops_cli/main.py`

### Task 4.1: Add config_app to main.py

- [ ] **Step 1: Add import and registration**

Modify `src/sanityops_cli/main.py`:

```python
# Add import after existing imports (around line 8)
from sanityops_cli.commands.config import config_app

# Add registration after inspect_app registration (around line 55)
app.add_typer(
    config_app,
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
)
```

The full modified file should look like:

```python
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

"""Sanityops CLI Entrance — Typer Application"""

import sys

import typer

from sanityops_cli import __version__
from sanityops_cli.commands.config import config_app
from sanityops_cli.commands.init import init_config
from sanityops_cli.commands.inspect import inspect_app
from sanityops_cli.exceptions.base_exceptions import ValidationError

app = typer.Typer(
    name="Sanityops-cli",
    help="Sanityops CLI Tool — A cli tool for sanityops",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sanityops-cli v{__version__}")
        typer.echo("Copyright (C) 2026 zipsonken / Sanity AI Labs")
        typer.echo("License: Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0)")
        raise typer.Exit()


@app.callback()
def callback(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        is_eager=True,
        callback=version_callback,
    ),
):
    """Sanityops CLI callback."""

app.add_typer(inspect_app, name="inspect", help="Static defect inspection of logical artifacts (System Prompts, Skills, Tool Schemas), suitable for local development or CI/CD integration")
app.add_typer(
    config_app,
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
)
app.command("init")(init_config)


def main():
    """Entrance function for the Sanityops CLI application."""
    try:
        app()
    except ValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unknown Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify config command is available**

Run: `python -c "from sanityops_cli.main import app; print([cmd.name for cmd in app.registered_groups])"`
Expected: `['inspect', 'config']`

- [ ] **Step 3: Test CLI help shows config**

Run: `python -m sanityops_cli.main --help`
Expected: Help text includes `config` command

- [ ] **Step 4: Commit**

```bash
git add src/sanityops_cli/main.py
git commit -m "feat(main): register config subcommand in CLI"
```

---

## Task 5: Final Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run ruff linting**

Run: `ruff check src/sanityops_cli/`
Expected: No errors

- [ ] **Step 3: Manual smoke test**

```bash
# Test help
python -m sanityops_cli.main config --help

# Test list (empty)
python -m sanityops_cli.main config --list

# Test set
python -m sanityops_cli.main config server.base_url https://test.example.com

# Test read
python -m sanityops_cli.main config server.base_url

# Test list (with values)
python -m sanityops_cli.main config --list

# Test unset
python -m sanityops_cli.main config --unset server.base_url
```

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address any remaining issues"
```