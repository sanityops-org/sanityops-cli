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

"""Auto-detect LLM configuration for the defect-check SDK."""

from __future__ import annotations

from pathlib import Path

import yaml

# Workaround: sanityops-agent 0.0.2 installs modules flat in site-packages root
# instead of under sanityops_agent/. Import from flat location.
try:
    from sanityops_agent.config import ProviderConfig
except ModuleNotFoundError:
    from config import ProviderConfig  # type: ignore[import-untyped]

# Default config file location
DEFAULT_CONFIG_DIR = ".sanityops"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"


def _read_model_section(config_path: str | None) -> dict[str, str]:
    """Read model section from config file if present.

    Args:
        config_path: Path to config file, or None to use default location.

    Returns:
        Dict with keys llm_provider, llm_api_key, llm_model_id, llm_base_url
        if model section is present and valid. Empty dict {} if model section
        absent or file missing/unreadable.
    """
    # Resolve config file path
    if config_path:
        p = Path(config_path).expanduser()
    else:
        p = Path.cwd() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE

    # If file doesn't exist, return empty (fall back to env vars)
    if not p.exists() or not p.is_file():
        return {}

    # Try to read and parse YAML
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    model = data.get("model")
    if not isinstance(model, dict):
        return {}

    # Check for required fields - if any missing, fall back to env vars
    provider = model.get("provider")
    api_key = model.get("api_key")
    model_id = model.get("model_id")

    if not provider or not api_key or not model_id:
        return {}

    # All required fields present and non-empty
    return {
        "llm_provider": str(provider),
        "llm_api_key": str(api_key),
        "llm_model_id": str(model_id),
        "llm_base_url": str(model.get("base_url", "")),
    }


def resolve_llm_config(config_path: str | None = None) -> dict[str, str]:
    """Resolve the four LLM params accepted by defect_check.check().

    Precedence: config file `model:` section -> ProviderConfig (env vars).

    Args:
        config_path: Optional path to config file. If None, looks for
            .sanityops/inspect_config.yaml in current working directory.

    Returns:
        dict with keys: llm_provider, llm_api_key, llm_model_id, llm_base_url
    """
    # Try config file first
    config_values = _read_model_section(config_path)
    if config_values:
        return config_values

    # Fall back to ProviderConfig (env vars)
    config = ProviderConfig()
    return {
        "llm_provider": config.LLM_PROVIDER,
        "llm_api_key": config.API_KEY,
        "llm_model_id": config.MODEL_ID,
        "llm_base_url": config.BASE_URL or "",
    }
