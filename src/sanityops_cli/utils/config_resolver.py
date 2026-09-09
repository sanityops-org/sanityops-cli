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
import tempfile
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


def _is_global_config_path(path: Path) -> bool:
    """Check if the path is the global config file path."""
    return path == get_global_config_path()


def _ensure_restricted_permissions(path: Path, is_file: bool = True) -> None:
    """Ensure restricted permissions for global config paths.

    For directories: 0o700 (owner-only access)
    For files: 0o600 (owner-only read/write)

    No-op for non-global paths. Best-effort on non-POSIX filesystems.
    """
    try:
        if is_file:
            path.chmod(0o600)
        else:
            path.chmod(0o700)
    except OSError:
        pass  # Non-POSIX filesystem (e.g., Windows)


def _write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file with atomic replacement.

    Creates parent directories if needed.
    Uses an unpredictable temp file + rename to prevent corruption on
    interruption and symlink attacks. The temp file is created with
    owner-only permissions (0o600) from the start (via O_EXCL), so sensitive
    values are never written to a world-readable file.
    """
    is_global = _is_global_config_path(path)

    # Create parent directory
    path.parent.mkdir(parents=True, exist_ok=True)

    # For global config, restrict directory permissions first
    if is_global:
        _ensure_restricted_permissions(path.parent, is_file=False)

    # Create an unpredictable temp file in the same directory with restrictive
    # permissions. O_EXCL + O_CREAT + 0o600 means the file is owner-only from
    # the instant it exists, and a pre-existing file never gets clobbered.
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.tmp-",
        # Drop S_IRWXG/S_IRWXO from the default 0o666 so the file is 0o600.
        # umask may further restrict, never loosen.
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        # Atomic on POSIX, near-atomic on Windows
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


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
