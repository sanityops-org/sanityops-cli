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

"""Shared-memory store for repaired artifacts produced by the repair agent.

The agent calls `store_repair` once per defective artifact with the fully
rewritten content; the CLI flushes everything into a single markdown
report under `.sanityops/repairs/`.
"""

import json
from pathlib import Path
from typing import ClassVar

from sanityops_agent.tools.base import Tool, ToolResult


class StoreRepairsTool(Tool):
    """Shared-memory store for repaired artifacts produced by the repair agent.

    The agent calls `store_repair` once per defective artifact with the fully
    rewritten content; the CLI flushes everything into a single markdown
    report under `.sanityops/repairs/`.
    """

    name = "store_repair"
    description = "store the repaired content of one artifact"
    parameters = {
        "type": "object",
        "properties": {
            "artifact_type": {
                "type": "string",
                "enum": ["skill", "tool", "prompt"],
                "description": "which kind of artifact was repaired",
            },
            "artifact_path": {
                "type": "string",
                "description": "absolute path of the source artifact file that was repaired",
            },
            "repaired_content": {
                "type": "string",
                "description": "the complete repaired artifact content (full file, not a diff)",
            },
            "summary": {
                "type": "string",
                "description": "one-paragraph summary of the defects addressed",
            },
        },
        "required": ["artifact_type", "artifact_path", "repaired_content", "summary"],
    }
    tags = ["memory", "repair"]

    _repairs: ClassVar[list[dict]] = []

    async def execute(
        self,
        artifact_type: str,
        artifact_path: str,
        repaired_content: str,
        summary: str,
    ) -> ToolResult:
        """Execute the store_repair operation."""
        return self._add_repair(artifact_type, artifact_path, repaired_content, summary)

    def _add_repair(
        self,
        artifact_type: str,
        artifact_path: str,
        repaired_content: str,
        summary: str,
    ) -> ToolResult:
        """Add a repair entry to the shared store."""
        # Validate artifact_type
        if artifact_type not in ("skill", "tool", "prompt"):
            return ToolResult(
                content="",
                success=False,
                error=f"invalid artifact_type: {artifact_type}",
            )

        # Validate absolute path
        path = Path(artifact_path)
        if not path.is_absolute():
            return ToolResult(
                content="",
                success=False,
                error=f"artifact_path must be absolute: {artifact_path}",
            )

        # Validate non-empty content
        if not repaired_content or not repaired_content.strip():
            return ToolResult(
                content="",
                success=False,
                error="repaired_content is empty",
            )

        # Create entry
        entry = {
            "artifact_type": artifact_type,
            "artifact_path": str(path),
            "repaired_content": repaired_content,
            "summary": summary,
        }

        # Update existing entry for same artifact, or add new
        for index, existing in enumerate(self._repairs):
            if existing["artifact_path"] == entry["artifact_path"]:
                self._repairs[index] = entry
                action = "updated"
                break
        else:
            self._repairs.append(entry)
            action = "added"

        return ToolResult(
            content=json.dumps({
                "success": True,
                "message": f"{action} repair for {artifact_type}: {path.name}",
                "count": len(self._repairs),
            }),
            success=True,
        )

    @classmethod
    def get_repairs(cls) -> list[dict]:
        """Return all stored repairs."""
        return list(cls._repairs)

    @classmethod
    def clear(cls) -> None:
        """Clear all stored repairs."""
        cls._repairs.clear()
