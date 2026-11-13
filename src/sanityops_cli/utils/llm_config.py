"""Auto-detect LLM configuration for the local inspection agents."""

from __future__ import annotations

from pathlib import Path

import yaml

from deeplogic_cli.utils.config_loader import read_file_with_encoding_fallback

# Import ProviderConfig with safe fallback for deeplogic-agent packaging quirks.
try:
    from aidynamic_agent.config import ProviderConfig
except ModuleNotFoundError:
    import importlib

    try:
        _cfg_mod = importlib.import_module("config")
        if hasattr(_cfg_mod, "ProviderConfig"):
            ProviderConfig = _cfg_mod.ProviderConfig
        else:
            raise ModuleNotFoundError(
                "Module 'config' does not provide ProviderConfig. "
                "Ensure aidynamic-agent is installed properly."
            )
    except Exception as _e:
        raise ModuleNotFoundError(
            f"Failed to import ProviderConfig from aidynamic_agent.config: {_e}"
        ) from _e

# Default config file location
DEFAULT_CONFIG_DIR = ".deeplogic"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"


def _is_non_empty_string(value: object) -> bool:
    """Return True if value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def _read_model_section(config_path: str | None) -> dict[str, str]:
    """Read model section from config file if present.

    Args:
        config_path: Path to config file, or None to use default location.

    Returns:
        Dict with keys llm_provider, llm_api_key, llm_model_id, llm_base_url
        if model section is present and valid. Empty dict {} if model section
        absent or file missing/unreadable.

    Note:
        This function intentionally returns {} on errors (silent fallback to
        env vars), unlike InspectConfigLoader which raises ValidationError.
    """
    # Resolve config file path
    if config_path:
        p = Path(config_path).expanduser()
    else:
        p = Path.cwd() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE

    # If file doesn't exist, return empty (fall back to env vars)
    if not p.exists() or not p.is_file():
        return {}

    # Read file with encoding fallback (UTF-8 -> GBK for Windows compatibility)
    content = read_file_with_encoding_fallback(p)
    if content is None:
        return {}

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict):
        return {}

    model = data.get("model")
    if not isinstance(model, dict):
        return {}

    # Check for required fields - if any missing, fall back to env vars
    # Validation mirrors config_loader's rules: all three must be non-empty strings.
    # Unlike config_loader (which raises on invalid config), this module intentionally
    # falls back to env vars when the model section is missing/invalid.
    provider = model.get("provider")
    api_key = model.get("api_key")
    model_id = model.get("model_id")

    if (
        not _is_non_empty_string(provider)
        or not _is_non_empty_string(api_key)
        or not _is_non_empty_string(model_id)
    ):
        return {}

    # All required fields present and non-empty strings
    # Use str() to satisfy mypy - we've validated they're non-empty strings above
    provider_str = str(provider)
    api_key_str = str(api_key)
    model_id_str = str(model_id)

    # Handle base_url: null -> empty string (not "None" string)
    # Note: API keys are returned as plain strings by design. The CLI passes
    # these directly to the agent constructors, which expect string values.
    # While SecretStr could prevent accidental logging, it would add
    # complexity without practical security benefit in this CLI context
    # where config values are never logged or exposed in error messages.
    base_url = model.get("base_url")
    return {
        "llm_provider": provider_str,
        "llm_api_key": api_key_str,
        "llm_model_id": model_id_str,
        "llm_base_url": str(base_url) if base_url is not None else "",
    }


def resolve_llm_config(config_path: str | None = None) -> dict[str, str]:
    """Resolve the four LLM params consumed by the local inspection agents.

    Precedence: config file `model:` section -> ProviderConfig (env vars).

    Args:
        config_path: Optional path to config file. If None, looks for
            .deeplogic/inspect_config.yaml in current working directory.

    Returns:
        dict with keys: llm_provider, llm_api_key, llm_model_id, llm_base_url
    """
    # Try config file first
    config_values = _read_model_section(config_path)
    if config_values:
        return config_values

    # Fall back to ProviderConfig (env vars)
    #
    # NOTE: aidynamic-agent >= 0.3.3 renames ProviderConfig's provider field from
    # `LLM_PROVIDER` to `PROVIDER` (env_prefix="LLM_" keeps the env var name).
    # Use getattr to stay compatible across versions. str() coerces the value to a
    # string so mypy sees a str, not Any | None.
    config = ProviderConfig()
    return {
        "llm_provider": str(
            getattr(config, "PROVIDER", None) or getattr(config, "LLM_PROVIDER", "") or ""
        ),
        "llm_api_key": str(getattr(config, "API_KEY", "")),
        "llm_model_id": str(getattr(config, "MODEL_ID", "")),
        "llm_base_url": getattr(config, "BASE_URL", "") or "",
    }
