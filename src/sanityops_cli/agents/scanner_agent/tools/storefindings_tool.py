import json
from pathlib import Path
from typing import ClassVar

from sanityops_agent.tools.base import Tool, ToolResult

from ..models.finding import Finding, FindingType


class StoreFindingsTool(Tool):
    """
    maintain a shared memory list of findings (skills/tools/prompts) and export to JSON file.
    """

    name = "store_findings"
    description = "collect and store skills/tools/prompts"
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "flush", "clear", "count"],
                "description": "operation to perform: add (add a finding), flush (export to JSON), clear (clear memory), count (count findings)",
            },
            "finding": {
                "type": "object",
                "description": "the finding object to add (required for add operation)",
                "properties": {
                    "type": {"type": "string", "enum": ["skill", "tool", "prompt"]},
                    "relative": {"type": "string", "description": "absolute path"},
                    "content": {"type": "object", "description": "optional content object"},
                },
                "required": ["type", "relative"],
            },
            "output_path": {
                "type": "string",
                "description": "path to export JSON file (required for flush operation)",
            },
        },
        "required": ["operation"],
    }
    tags = ["memory"]

    _findings: ClassVar[list[Finding]] = []

    async def execute(
        self,
        operation: str,
        finding: Finding | None = None,
        output_path: str | None = None,
    ) -> ToolResult:
        if operation == "add":
            return self._add_finding(finding)
        elif operation == "flush":
            return self._flush(output_path)
        elif operation == "clear":
            return self._clear()
        elif operation == "count":
            return self._count()
        else:
            return ToolResult(
                content="",
                success=False,
                error=f"unknown operation: {operation}",
            )

    def _add_finding(self, finding_dict: Finding | None) -> ToolResult:
        if finding_dict is None:
            return ToolResult(
                content="",
                success=False,
                error="missing finding parameter",
            )

        try:
            finding = Finding.model_validate(finding_dict)
        except Exception as e:
            return ToolResult(
                content="",
                success=False,
                error=f"Finding validation failed: {e}",
            )

        self._findings.append(finding)
        return ToolResult(
            content=json.dumps({
                "success": True,
                "message": f"added {finding.type.value}: {finding.relative}",
                "count": len(self._findings),
            }),
            success=True,
        )

    def _flush(self, output_path: str | None) -> ToolResult:
        if not output_path:
            return ToolResult(
                content="",
                success=False,
                error="missing output_path parameter",
            )

        result = {
            "skills": [
                f.model_dump()
                for f in self._findings
                if f.type == FindingType.SKILL
            ],
            "tools": [
                f.model_dump()
                for f in self._findings
                if f.type == FindingType.TOOL
            ],
            "prompts": [
                f.model_dump()
                for f in self._findings
                if f.type == FindingType.PROMPT
            ],
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return ToolResult(
            content=json.dumps({
                "success": True,
                "message": f"exported {len(self._findings)} findings to {output_path}",
                "counts": {
                    "skills": len(result["skills"]),
                    "tools": len(result["tools"]),
                    "prompts": len(result["prompts"]),
                },
            }),
            success=True,
        )

    def _clear(self) -> ToolResult:
        count = len(self._findings)
        self._findings.clear()
        return ToolResult(
            content=json.dumps({
                "success": True,
                "message": f"cleared {count} findings",
            }),
            success=True,
        )

    def _count(self) -> ToolResult:
        return ToolResult(
            content=json.dumps({
                "success": True,
                "count": len(self._findings),
                "by_type": {
                    "skills": sum(1 for f in self._findings if f.type == FindingType.SKILL),
                    "tools": sum(1 for f in self._findings if f.type == FindingType.TOOL),
                    "prompts": sum(1 for f in self._findings if f.type == FindingType.PROMPT),
                },
            }),
            success=True,
        )
