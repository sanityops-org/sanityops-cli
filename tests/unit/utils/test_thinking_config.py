"""Unit tests for enable_thinking -> extra_body mapping."""

from sanityops_cli.utils.thinking_config import resolve_thinking_extra_body


def test_none_enable_thinking_and_no_override_returns_none():
    assert (
        resolve_thinking_extra_body(
            provider="anthropic",
            model_id="claude-sonnet-4-20250514",
            base_url=None,
            enable_thinking=None,
        )
        is None
    )


def test_anthropic_claude_mapping():
    assert resolve_thinking_extra_body(
        provider="anthropic",
        model_id="claude-sonnet-4-20250514",
        base_url=None,
        enable_thinking=False,
    ) == {"thinking": {"type": "disabled"}}
    assert (
        resolve_thinking_extra_body(
            provider="anthropic",
            model_id="claude-sonnet-4-20250514",
            base_url=None,
            enable_thinking=True,
        )
        is None
    )


def test_bigmodel_glm53_flash_mapping():
    assert resolve_thinking_extra_body(
        provider="anthropic",
        model_id="glm-5.3-flash",
        base_url="https://open.bigmodel.cn/api/anthropic",
        enable_thinking=False,
    ) == {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}
    assert resolve_thinking_extra_body(
        provider="anthropic",
        model_id="glm-5.3-flash",
        base_url="https://open.bigmodel.cn/api/anthropic",
        enable_thinking=True,
    ) == {"thinking": {"type": "enabled"}}


def test_bigmodel_older_glm_mapping():
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="glm-4.7",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        enable_thinking=False,
    ) == {"thinking": {"type": "disabled"}}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="glm-4.7",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        enable_thinking=True,
    ) == {"thinking": {"type": "enabled"}}


def test_dashscope_and_bailian_mapping():
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="qwen3-235b-a22b",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        enable_thinking=False,
    ) == {"enable_thinking": False}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="glm-5.3",
        base_url="https://ws-x46wy9lys1i5w6rm.us-east-1.maas.aliyuncs.com/compatible-mode/v1",
        enable_thinking=True,
    ) == {"enable_thinking": True}
    assert resolve_thinking_extra_body(
        provider="dashscope",
        model_id="qwen-plus",
        base_url=None,
        enable_thinking=False,
    ) == {"enable_thinking": False}


def test_self_hosted_qwen3_vllm_mapping():
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="Qwen/Qwen3-32B",
        base_url="http://localhost:8000/v1",
        enable_thinking=False,
    ) == {"chat_template_kwargs": {"enable_thinking": False}}


def test_deepseek_and_volces_mapping():
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        enable_thinking=False,
    ) == {"thinking": {"type": "disabled"}}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="doubao-seed-1-6",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        enable_thinking=True,
    ) == {"thinking": {"type": "enabled"}}


def test_openai_models_and_gemini_mapping():
    assert (
        resolve_thinking_extra_body(
            provider="openai",
            model_id="gpt-4o",
            base_url=None,
            enable_thinking=False,
        )
        is None
    )
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="o3-mini",
        base_url=None,
        enable_thinking=False,
    ) == {"reasoning_effort": "low"}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="gpt-5.2",
        base_url=None,
        enable_thinking=False,
    ) == {"reasoning_effort": "none"}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="gpt-5",
        base_url=None,
        enable_thinking=False,
    ) == {"reasoning_effort": "minimal"}
    assert resolve_thinking_extra_body(
        provider="openai",
        model_id="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        enable_thinking=False,
    ) == {"reasoning_effort": "none"}


def test_code_assistant_mapping():
    for proto, url in [
        ("anthropic", "http://192.168.1.189:4000"),
        ("openai", "http://192.168.1.189:4000/v1"),
    ]:
        assert resolve_thinking_extra_body(
            provider=proto,
            model_id="code-assistant",
            base_url=url,
            enable_thinking=False,
        ) == {"enable_thinking": False}
        assert resolve_thinking_extra_body(
            provider=proto,
            model_id="code-assistant",
            base_url=url,
            enable_thinking=True,
        ) == {"enable_thinking": True}
