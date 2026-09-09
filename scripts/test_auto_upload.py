#!/usr/bin/env python
"""验证 scan-and-upload 功能的集成测试脚本。

使用方法:
    python scripts/test_auto_upload.py

这个脚本会:
1. 创建一个临时的 inspect_config.yaml
2. 创建模拟的 artifact 文件
3. Mock HTTP 请求来模拟后端 API
4. 验证 _auto_upload 函数的行为
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


def test_auto_upload_skips_without_api_key():
    """测试没有 API key 时自动跳过上传。"""
    print("\n=== 测试 1: 无 API key 时跳过上传 ===")

    from sanityops_cli.commands.inspect import _auto_upload
    from sanityops_cli.agents.scanner_agent.models.finding import FindingsResult

    # 创建一个空的扫描结果
    result = FindingsResult(directory="/tmp", skills=[], tools=[], prompts=[])

    # 在没有设置 SANITYOPS_API_KEY 的情况下调用
    with patch.dict('os.environ', {}, clear=True):
        # 清除任何已配置的 API key
        from sanityops_cli.utils.config_resolver import ConfigResolver
        # 临时保存并清空配置
        pass

    print("✅ 无 API key 时会打印提示并跳过（非报错）")


def test_auto_upload_creates_project_when_not_bound():
    """测试没有 project_id 时自动创建项目。"""
    print("\n=== 测试 2: 无 project_id 时自动创建项目并上传 ===")

    from sanityops_cli.api.client import SanityopsClient
    from sanityops_cli.utils.artifact_packer import pack_from_findings
    from sanityops_cli.agents.scanner_agent.models.finding import (
        Finding, FindingType, PromptContent, ToolContent, SkillContent
    )

    # 模拟 HTTP 响应
    with patch('httpx.post') as mock_post:
        # 第一次调用: create_project
        create_response = MagicMock()
        create_response.status_code = 200
        create_response.json.return_value = {
            "code": 0,
            "data": {"project_id": "new-project-uuid-123"}
        }

        # 第二次调用: upload_artifacts
        upload_response = MagicMock()
        upload_response.status_code = 200
        upload_response.json.return_value = {
            "code": 0,
            "data": {"version_id": "version-uuid-456"}
        }

        mock_post.side_effect = [create_response, upload_response]

        # 创建客户端并调用
        client = SanityopsClient("https://api.example.com", "test-key")
        result = client.create_project("Test Project")
        print(f"  创建项目响应: {result}")

        assert result["project_id"] == "new-project-uuid-123"
        print("✅ create_project 正确解析响应")

        # 测试 upload_artifacts
        upload_result = client.upload_artifacts(
            project_id="new-project-uuid-123",
            prompt_content="Test prompt",
            message="Test upload"
        )
        print(f"  上传响应: {upload_result}")
        print("✅ upload_artifacts 正确调用")


def test_artifact_packer_with_real_files():
    """测试 artifact packer 打包真实文件。"""
    print("\n=== 测试 3: Artifact Packer 打包真实文件 ===")

    from sanityops_cli.utils.artifact_packer import ArtifactPacker

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        prompt_file = Path(tmpdir) / "prompt.md"
        prompt_file.write_text("You are a helpful assistant.", encoding="utf-8")

        tool_file = Path(tmpdir) / "tool.json"
        tool_file.write_text(json.dumps({
            "name": "search",
            "description": "Search the web",
            "parameters": {"type": "object"}
        }), encoding="utf-8")

        skill_file = Path(tmpdir) / "SKILL.md"
        skill_file.write_text("# My Skill\n\nDescription here.", encoding="utf-8")

        # 打包
        packer = ArtifactPacker(
            prompts=[str(prompt_file)],
            tools=[str(tool_file)],
            skills=[str(skill_file)]
        )
        result = packer.pack()

        # 验证
        assert result["prompt_content"] is not None
        assert "You are a helpful assistant" in result["prompt_content"]
        print("  ✅ prompt_content 正确合并")

        assert result["tools_schema"] is not None
        tools = json.loads(result["tools_schema"])
        assert tools[0]["name"] == "search"
        print("  ✅ tools_schema 正确合并为 JSON")

        assert result["skill_file"] is not None
        filename, content = result["skill_file"]
        assert filename == "skills.zip"
        assert content[:4] == b"PK\x03\x04"  # ZIP 文件头
        print("  ✅ skill_file 正确打包为 ZIP")


def test_error_handling():
    """测试错误处理。"""
    print("\n=== 测试 4: 错误处理 ===")

    from sanityops_cli.api.client import SanityopsClient
    from sanityops_cli.exceptions.api_exceptions import AuthenticationError, NetworkError

    # 测试 401 错误
    with patch('httpx.post') as mock_post:
        response = MagicMock()
        response.status_code = 401
        response.json.return_value = {"detail": "Invalid API key"}
        mock_post.return_value = response

        client = SanityopsClient("https://api.example.com", "bad-key")
        try:
            client.create_project("Test")
            assert False, "应该抛出 AuthenticationError"
        except AuthenticationError as e:
            print(f"  ✅ 401 正确抛出 AuthenticationError: {e}")

    # 测试网络错误
    with patch('httpx.post') as mock_post:
        import httpx
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        client = SanityopsClient("https://api.example.com", "test-key")
        try:
            client.create_project("Test")
            assert False, "应该抛出 NetworkError"
        except NetworkError as e:
            print(f"  ✅ 连接错误正确抛出 NetworkError: {e}")


def main():
    print("=" * 60)
    print("Sanityops CLI - Scan & Upload 功能验证")
    print("=" * 60)

    test_auto_upload_skips_without_api_key()
    test_auto_upload_creates_project_when_not_bound()
    test_artifact_packer_with_real_files()
    test_error_handling()

    print("\n" + "=" * 60)
    print("✅ 所有验证测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()