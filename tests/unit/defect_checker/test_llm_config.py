"""Unit tests for LLM config resolution."""
from pathlib import Path
from unittest import mock

import yaml

from sanityops_cli.defect_checker.llm_config import resolve_llm_config


class TestResolveLlmConfig:
    def test_returns_four_expected_keys(self):
        cfg = resolve_llm_config()
        assert set(cfg.keys()) == {"llm_provider", "llm_api_key", "llm_model_id", "llm_base_url"}

    def test_maps_provider_config_fields(self):
        fake = mock.Mock()
        fake.LLM_PROVIDER = "anthropic"
        fake.API_KEY = "sk-test"
        fake.MODEL_ID = "claude-sonnet-4-20250514"
        fake.BASE_URL = "https://api.example.com"
        with mock.patch(
            "sanityops_cli.defect_checker.llm_config.ProviderConfig",
            return_value=fake,
        ):
            cfg = resolve_llm_config()
        assert cfg == {
            "llm_provider": "anthropic",
            "llm_api_key": "sk-test",
            "llm_model_id": "claude-sonnet-4-20250514",
            "llm_base_url": "https://api.example.com",
        }

    def test_none_base_url_becomes_empty_string(self):
        fake = mock.Mock()
        fake.LLM_PROVIDER = "openai"
        fake.API_KEY = "k"
        fake.MODEL_ID = "gpt-4o"
        fake.BASE_URL = None
        with mock.patch(
            "sanityops_cli.defect_checker.llm_config.ProviderConfig",
            return_value=fake,
        ):
            cfg = resolve_llm_config()
        assert cfg["llm_base_url"] == ""


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
        monkeypatch.chdir(tmp_path)
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

        fake = mock.Mock()
        fake.LLM_PROVIDER = "env-provider"
        fake.API_KEY = "env-key"
        fake.MODEL_ID = "env-model"
        fake.BASE_URL = "https://env.url"
        with mock.patch(
            "sanityops_cli.defect_checker.llm_config.ProviderConfig",
            return_value=fake,
        ):
            cfg = resolve_llm_config(str(config_file))
        assert cfg == {
            "llm_provider": "env-provider",
            "llm_api_key": "env-key",
            "llm_model_id": "env-model",
            "llm_base_url": "https://env.url",
        }

    def test_config_file_missing_falls_back_to_env_vars(self, tmp_path: Path, monkeypatch):
        """Should fall back to ProviderConfig when config file doesn't exist."""
        monkeypatch.chdir(tmp_path)

        fake = mock.Mock()
        fake.LLM_PROVIDER = "fallback-provider"
        fake.API_KEY = "fallback-key"
        fake.MODEL_ID = "fallback-model"
        fake.BASE_URL = None
        with mock.patch(
            "sanityops_cli.defect_checker.llm_config.ProviderConfig",
            return_value=fake,
        ):
            cfg = resolve_llm_config("/nonexistent/config.yaml")
        assert cfg == {
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

        # Set up env vars that should be ignored
        fake = mock.Mock()
        fake.LLM_PROVIDER = "env-provider-should-be-ignored"
        fake.API_KEY = "env-key-should-be-ignored"
        fake.MODEL_ID = "env-model-should-be-ignored"
        fake.BASE_URL = "https://env.url.ignored"
        with mock.patch(
            "sanityops_cli.defect_checker.llm_config.ProviderConfig",
            return_value=fake,
        ):
            cfg = resolve_llm_config(str(config_file))

        # Config values win
        assert cfg["llm_provider"] == "config-provider"
        assert cfg["llm_api_key"] == "config-key"
        assert cfg["llm_model_id"] == "config-model"
        assert cfg["llm_base_url"] == ""
