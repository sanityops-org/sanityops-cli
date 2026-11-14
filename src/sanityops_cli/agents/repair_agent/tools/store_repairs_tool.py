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
            "artifact_name": {
                "type": "string",
                "description": "optional name of the specific tool, skill, or sub-artifact within the file",
            },
        },
        "required": ["artifact_type", "artifact_path", "repaired_content", "summary"],
    }
    tags = ["memory"]

    _repairs: ClassVar[list[dict]] = []

    async def execute(
        self,
        artifact_type: str,
        artifact_path: str,
        repaired_content: str,
        summary: str,
        artifact_name: str | None = None,
    ) -> ToolResult:
        if artifact_type not in ("skill", "tool", "prompt"):
            return ToolResult(
                content="", success=False, error=f"invalid artifact_type: {artifact_type}"
            )
        path = Path(artifact_path)
        if not path.is_absolute():
            return ToolResult(
                content="", success=False, error=f"artifact_path must be absolute: {artifact_path}"
            )
        if not repaired_content or not repaired_content.strip():
            return ToolResult(content="", success=False, error="repaired_content is empty")

        # 同一工件重复提交时保留最后一次（若有 artifact_name 则精细区分子工件）
        entry: dict = {
            "artifact_type": artifact_type,
            "artifact_path": str(path),
            "repaired_content": repaired_content,
            "summary": summary,
        }
        if artifact_name:
            entry["artifact_name"] = artifact_name

        def _is_same(a: dict, b: dict) -> bool:
            if a["artifact_path"] != b["artifact_path"]:
                return False
            a_name = a.get("artifact_name")
            b_name = b.get("artifact_name")
            if a_name and b_name:
                return a_name == b_name
            return True

        for index, existing in enumerate(self._repairs):
            if _is_same(existing, entry):
                self._repairs[index] = entry
                action = "updated"
                break
        else:
            self._repairs.append(entry)
            action = "added"

        display_name = f"{path.name} ({artifact_name})" if artifact_name else path.name
        return ToolResult(
            content=json.dumps(
                {
                    "success": True,
                    "message": f"{action} repair for {artifact_type}: {display_name}",
                    "count": len(self._repairs),
                }
            ),
            success=True,
        )

    @classmethod
    def get_repairs(cls) -> list[dict]:
        """Return all stored repairs (artifact_type, artifact_path, repaired_content, summary)."""
        return list(cls._repairs)

    @classmethod
    def clear(cls) -> None:
        cls._repairs.clear()
