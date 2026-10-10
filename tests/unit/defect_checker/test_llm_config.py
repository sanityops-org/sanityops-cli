"""Unit tests for LLM config resolution."""
from pathlib import Path

import yaml

from sanityops_cli.defect_checker.llm_config import resolve_llm_config

LLM_ENV_NAMES = (
    "LLM_PROVIDER",
    "LLM_LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "LLM_BASE_URL",
)


def _set_llm_env(monkeypatch, tmp_path: Path, **values: str) -> None:
    """Point the LLM_* environment variables at `values`, clearing the rest.

    Also chdirs into tmp_path so ProviderConfig's `.env` lookup (env_file)
    cannot leak values from the repository into the test.
    """
    monkeypatch.chdir(tmp_path)
    for name in LLM_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


class TestResolveLlmConfigFromEnvironment:
    """The env fallback must read the documented LLM_* variable names.

    Regression: resolve_llm_config read ``ProviderConfig.LLM_PROVIDER``, the
    deprecated constructor alias, instead of ``ProviderConfig.PROVIDER``. The
    settings model sets ``env_prefix="LLM_"``, so that alias listens on
    ``LLM_LLM_PROVIDER``; the documented ``LLM_PROVIDER`` never reached the
    defect-check SDK, which refused the run with LLM_CONFIGURATION_MISSING and
    left the report at zero defects with a PASS gate.
    """

    def test_returns_four_expected_keys(self, tmp_path: Path, monkeypatch):
        _set_llm_env(monkeypatch, tmp_path)
        cfg = resolve_llm_config()
        assert set(cfg.keys()) == {"llm_provider", "llm_api_key", "llm_model_id", "llm_base_url"}

    def test_reads_documented_env_var_names(self, tmp_path: Path, monkeypatch):
        """LLM_PROVIDER and friends resolve into the provider the SDK receives."""
        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_PROVIDER="anthropic",
            LLM_API_KEY="sk-test",
            LLM_MODEL_ID="claude-sonnet-4-20250514",
            LLM_BASE_URL="https://api.example.com",
        )
        assert resolve_llm_config() == {
            "llm_provider": "anthropic",
            "llm_api_key": "sk-test",
            "llm_model_id": "claude-sonnet-4-20250514",
            "llm_base_url": "https://api.example.com",
        }

    def test_deprecated_double_prefixed_provider_name_still_resolves(self, tmp_path: Path, monkeypatch):
        """LLM_LLM_PROVIDER is the deprecated alias' own env name; keep it working."""
        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_LLM_PROVIDER="openai",
            LLM_API_KEY="sk-test",
            LLM_MODEL_ID="gpt-4o",
        )
        assert resolve_llm_config()["llm_provider"] == "openai"

    def test_unset_base_url_becomes_empty_string(self, tmp_path: Path, monkeypatch):
        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_PROVIDER="openai",
            LLM_API_KEY="k",
            LLM_MODEL_ID="gpt-4o",
        )
        assert resolve_llm_config()["llm_base_url"] == ""


class TestResolveLlmConfigFromConfigFile:
    """Tests for reading model config from config file."""

    def test_reads_complete_model_section(self, tmp_path: Path, monkeypatch):
        """Should read all four values from model section."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000001"},
            "model": {
                "provider": "anthropic",
                "api_key": "sk-config-key",
                "model_id": "claude-opus-4-20250514",
                "base_url": "https://custom.api.com",
            },
            "prompts": [],
            "tools": [],
            "skills": [],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        cfg = resolve_llm_config(str(config_file))
        assert cfg == {
            "llm_provider": "anthropic",
            "llm_api_key": "sk-config-key",
            "llm_model_id": "claude-opus-4-20250514",
            "llm_base_url": "https://custom.api.com",
        }

    def test_model_section_without_base_url_returns_empty_string(self, tmp_path: Path, monkeypatch):
        """Should return empty string for base_url when not specified."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000002"},
            "model": {
                "provider": "openai",
                "api_key": "sk-openai-key",
                "model_id": "gpt-4o",
            },
            "prompts": [],
            "tools": [],
            "skills": [],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        cfg = resolve_llm_config(str(config_file))
        assert cfg["llm_base_url"] == ""

    def test_model_section_absent_falls_back_to_env_vars(self, tmp_path: Path, monkeypatch):
        """Should fall back to ProviderConfig when model section absent."""
        _set_llm_env(monkeypatch, tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000003"},
            "prompts": [],
            "tools": [],
            "skills": [],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_PROVIDER="env-provider",
            LLM_API_KEY="env-key",
            LLM_MODEL_ID="env-model",
            LLM_BASE_URL="https://env.url",
        )
        assert resolve_llm_config(str(config_file)) == {
            "llm_provider": "env-provider",
            "llm_api_key": "env-key",
            "llm_model_id": "env-model",
            "llm_base_url": "https://env.url",
        }

    def test_config_file_missing_falls_back_to_env_vars(self, tmp_path: Path, monkeypatch):
        """Should fall back to ProviderConfig when config file doesn't exist."""
        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_PROVIDER="fallback-provider",
            LLM_API_KEY="fallback-key",
            LLM_MODEL_ID="fallback-model",
        )
        assert resolve_llm_config("/nonexistent/config.yaml") == {
            "llm_provider": "fallback-provider",
            "llm_api_key": "fallback-key",
            "llm_model_id": "fallback-model",
            "llm_base_url": "",
        }

    def test_default_path_reads_dot_sanityops(self, tmp_path: Path, monkeypatch):
        """Should read from .sanityops/inspect_config.yaml when no path given."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000004"},
            "model": {
                "provider": "default-path-provider",
                "api_key": "default-path-key",
                "model_id": "default-path-model",
                "base_url": "",
            },
            "prompts": [],
            "tools": [],
            "skills": [],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        cfg = resolve_llm_config()  # No config_path argument
        assert cfg == {
            "llm_provider": "default-path-provider",
            "llm_api_key": "default-path-key",
            "llm_model_id": "default-path-model",
            "llm_base_url": "",
        }

    def test_config_file_takes_precedence_over_env_vars(self, tmp_path: Path, monkeypatch):
        """Config file values should override env var values."""
        monkeypatch.chdir(tmp_path)
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"

        config_content = {
            "project": {"id": "00000000-0000-0000-0000-000000000005"},
            "model": {
                "provider": "config-provider",
                "api_key": "config-key",
                "model_id": "config-model",
            },
            "prompts": [],
            "tools": [],
            "skills": [],
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        # Env vars that must be ignored in favour of the config file's model: section
        _set_llm_env(
            monkeypatch,
            tmp_path,
            LLM_PROVIDER="env-provider-should-be-ignored",
            LLM_API_KEY="env-key-should-be-ignored",
            LLM_MODEL_ID="env-model-should-be-ignored",
            LLM_BASE_URL="https://env.url.ignored",
        )

        cfg = resolve_llm_config(str(config_file))

        # Config values win
        assert cfg == {
            "llm_provider": "config-provider",
            "llm_api_key": "config-key",
            "llm_model_id": "config-model",
            "llm_base_url": "",
        }
