"""Resolve model- and gateway-specific ``extra_body`` payloads from ``enable_thinking``."""

from __future__ import annotations

import urllib.parse
from typing import Any


def _extract_host(base_url: str | None) -> str:
    if not base_url:
        return ""
    parsed = urllib.parse.urlparse(base_url.strip())
    return (parsed.hostname or "").lower()


def _host_matches(host: str, *domains: str) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


def resolve_thinking_extra_body(
    *,
    provider: str,
    model_id: str,
    base_url: str | None = None,
    enable_thinking: bool | None = None,
) -> dict[str, Any] | None:
    """Map unified ``enable_thinking`` to gateway-specific ``extra_body`` parameters.

    Args:
        provider: Configured provider protocol (e.g., ``"anthropic"``, ``"openai"``).
        model_id: Target model identifier.
        base_url: Optional custom endpoint URL used to distinguish gateways.
        enable_thinking: Desired thinking mode, or ``None`` if unconfigured.

    Returns:
        A dict suitable for ``ProviderConfig.EXTRA_BODY``, or ``None`` when no extra
        request body parameters are needed.
    """
    if enable_thinking is None:
        return None

    prov = (provider or "").strip().lower()
    model = (model_id or "").strip().lower().rsplit("/", 1)[-1]
    host = _extract_host(base_url)
    return _map_thinking_param(prov, model, host, enable_thinking)


def _map_thinking_param(
    prov: str,
    model: str,
    host: str,
    enable_thinking: bool,
) -> dict[str, Any] | None:
    # Internal corporate gateway model (`code-assistant`) uses top-level `enable_thinking`
    # across both Anthropic and OpenAI compatible endpoints.
    if model == "code-assistant" or model.startswith("code-assistant-"):
        return {"enable_thinking": enable_thinking}

    # Aliyun DashScope / Bailian OpenAI-compatible gateways use top-level `enable_thinking`.
    if prov == "dashscope" or _host_matches(host, "aliyuncs.com"):
        return {"enable_thinking": enable_thinking}

    # Zhipu BigModel / Z.ai GLM family:
    # - GLM-5.3+ mandates thinking (`disabled` fails validation); tune effort when false.
    # - Older GLM-4.5..5.2 models accept `thinking: {"type": "enabled" | "disabled"}`.
    if model.startswith("glm-5.3"):
        if enable_thinking:
            return {"thinking": {"type": "enabled"}}
        return {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}

    if model.startswith("glm-") or _host_matches(host, "bigmodel.cn", "z.ai"):
        return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}

    # Self-hosted OpenAI-compatible servers (vLLM / SGLang) for Qwen3 / QwQ series.
    if model.startswith(("qwen3", "qwq")):
        return {"chat_template_kwargs": {"enable_thinking": enable_thinking}}

    # DeepSeek and Volcengine Ark (Doubao) use `thinking: {"type": "enabled" | "disabled"}`.
    if model.startswith(("deepseek", "doubao")) or _host_matches(
        host, "deepseek.com", "volces.com"
    ):
        return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}

    # OpenAI reasoning models and Google Gemini OpenAI-compatible endpoints.
    if not enable_thinking:
        if model.startswith(("o1", "o3", "o4")):
            return {"reasoning_effort": "low"}
        if model.startswith(("gpt-5.1", "gpt-5.2", "gpt-5.3", "gpt-5.4")):
            return {"reasoning_effort": "none"}
        if model.startswith("gpt-5"):
            return {"reasoning_effort": "minimal"}
        if model.startswith("gemini") or _host_matches(host, "generativelanguage.googleapis.com"):
            return {"reasoning_effort": "none"}

    # Anthropic Messages API / Claude models.
    if model.startswith("claude") or prov == "anthropic":
        if not enable_thinking:
            return {"thinking": {"type": "disabled"}}
        return None

    return None
