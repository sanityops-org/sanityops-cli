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

import pytest

from sanityops_cli.agents.repair_agent.tools.store_repairs_tool import StoreRepairsTool


class TestStoreRepairsTool:
    """Tests for StoreRepairsTool."""

    def setup_method(self):
        """Clear repairs before each test."""
        StoreRepairsTool.clear()

    def test_tool_attributes(self):
        """Tool has correct name and description."""
        tool = StoreRepairsTool()
        assert tool.name == "store_repair"
        assert "repaired" in tool.description.lower()
        assert "artifact" in tool.description.lower()

    def test_add_repair_success(self):
        """Adding a valid repair succeeds."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="# Fixed prompt content",
            summary="Fixed ambiguous pronouns",
        )
        assert result.success is True
        assert "added" in result.content.lower()
        assert len(StoreRepairsTool.get_repairs()) == 1

    def test_add_repair_updates_existing(self):
        """Adding same artifact twice updates the entry."""
        tool = StoreRepairsTool()
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="version 1",
            summary="First fix",
        )
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="version 2",
            summary="Second fix",
        )
        repairs = StoreRepairsTool.get_repairs()
        assert len(repairs) == 1
        assert repairs[0]["repaired_content"] == "version 2"

    def test_add_repair_rejects_invalid_type(self):
        """Invalid artifact_type is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="invalid_type",
            artifact_path="/abs/path/to/file.md",
            repaired_content="content",
            summary="summary",
        )
        assert result.success is False
        assert "invalid" in result.error.lower()

    def test_add_repair_rejects_relative_path(self):
        """Relative path is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="relative/path.md",
            repaired_content="content",
            summary="summary",
        )
        assert result.success is False
        assert "absolute" in result.error.lower()

    def test_add_repair_rejects_empty_content(self):
        """Empty repaired_content is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/file.md",
            repaired_content="",
            summary="summary",
        )
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_clear_removes_all_repairs(self):
        """Clear removes all stored repairs."""
        tool = StoreRepairsTool()
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/1.md",
            repaired_content="content",
            summary="fix",
        )
        tool._add_repair(
            artifact_type="skill",
            artifact_path="/abs/path/2.md",
            repaired_content="content",
            summary="fix",
        )
        assert len(StoreRepairsTool.get_repairs()) == 2
        StoreRepairsTool.clear()
        assert len(StoreRepairsTool.get_repairs()) == 0

    @pytest.mark.anyio
    async def test_execute_add_operation(self):
        """Execute with add operation works."""
        tool = StoreRepairsTool()
        result = await tool.execute(
            artifact_type="skill",
            artifact_path="/abs/path/skill.md",
            repaired_content="# Skill content",
            summary="Fixed all defects",
        )
        assert result.success is True
        assert len(StoreRepairsTool.get_repairs()) == 1
