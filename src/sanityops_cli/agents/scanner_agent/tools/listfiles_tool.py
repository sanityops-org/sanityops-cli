
from pathlib import Path

from sanityops_agent.tools.base import Tool, ToolResult


class ListFilesTool(Tool):
    """List files in a directory with structure."""

    name = "list_files"
    description = "List all files and directories with their structure. Shows file types and sizes."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list"
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth to traverse (default 3)",
                "default": 3
            }
        },
        "required": ["path"]
    }
    tags = ["scanner"]

    async def execute(self, path: str, max_depth: int = 3, **kwargs) -> ToolResult:
        """List directory structure."""
        try:
            base_path = Path(path)
            if not base_path.exists():
                return ToolResult(
                    content=f"Path not found: {path}",
                    success=False,
                    error="Path not found"
                )

            result_lines = []
            file_count = 0
            dir_count = 0

            for item in base_path.rglob("*"):
                rel_path = item.relative_to(base_path)
                depth = len(rel_path.parts)

                if depth > max_depth:
                    continue

                if item.is_dir():
                    dir_count += 1
                    result_lines.append(f"[DIR] {rel_path}/")
                else:
                    file_count += 1
                    size = item.stat().st_size
                    ext = item.suffix.lower()
                    result_lines.append(f"[FILE] {rel_path} ({size} bytes, {ext})")

            summary = f"\n---\nTotal: {dir_count} directories, {file_count} files"
            return ToolResult(
                content="\n".join(result_lines) + summary,
                success=True,
                metadata={"file_count": file_count, "dir_count": dir_count}
            )

        except Exception as e:
            return ToolResult(
                content=f"Error listing files: {e}",
                success=False,
                error=str(e)
            )


