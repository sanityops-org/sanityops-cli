"""Root-scoped file reading for the ExtractAgent.

The inspected documents are untrusted input; the containment boundary lives
in the tool layer, not the prompt layer (design §5.1). Every path is
resolved with ``realpath()`` and must land inside one of the allowed roots —
symlink escapes therefore fail closed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from aidynamic_agent.tools.base import Tool, ToolResult

from deeplogic_cli.utils.config_loader import read_file_with_encoding_fallback

#: Refuse to read anything larger than this (artifacts are config-declared
#: documents; anything bigger is almost certainly a mistake or a binary).
DEFAULT_MAX_SIZE_BYTES = 2 * 1024 * 1024


class ScopedReadFileTool(Tool):
    """Read a text file, restricted to the configured allowed roots."""

    name = "read"
    description = (
        "Read a text file (markdown, YAML, JSON, source code) from the "
        "configured project roots. Absolute paths only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "minLength": 1,
                "description": "Absolute path of the file to read.",
            },
            "offset": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based line number to start from (default 1).",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "description": "Maximum number of lines to return.",
            },
        },
        "required": ["file_path"],
    }
    tags = ["extract", "reader"]

    def __init__(
        self,
        allowed_roots: list[Path],
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        *,
        content_transform: Callable[[Path, str], str] | None = None,
    ) -> None:
        super().__init__()
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        self.max_size_bytes = max_size_bytes
        self._content_transform = content_transform

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        file_path = kwargs.get("file_path")
        if not file_path:
            return self._error("file_path is required")

        resolved = Path(file_path).resolve()
        root = self._containing_root(resolved)
        if root is None:
            allowed = "\n".join(f"  - {r}" for r in self.allowed_roots)
            return self._error(
                f"path is outside the allowed roots: {resolved}\nallowed roots:\n{allowed}"
            )

        if not resolved.is_file():
            return self._error(f"file not found: {resolved}")
        if resolved.stat().st_size > self.max_size_bytes:
            return self._error(
                f"file exceeds the {self.max_size_bytes} byte read limit: {resolved}"
            )

        text = read_file_with_encoding_fallback(resolved)
        if text is None:
            return self._error(f"unreadable file (no supported encoding): {resolved}")
        if self._content_transform is not None:
            text = self._content_transform(resolved, text)

        lines = text.splitlines()
        total = len(lines)
        offset = int(kwargs.get("offset") or 1)
        limit = kwargs.get("limit")
        start = max(1, offset)
        end = total + 1 if limit is None else min(total + 1, start + int(limit))
        selected = lines[start - 1 : end - 1]

        body = "\n".join(selected)
        note = (
            ""
            if (start == 1 and end == total + 1)
            else (f"\n\n[showing lines {start}-{end - 1} of {total}]")
        )
        return ToolResult(content=body + note, success=True)

    def _containing_root(self, resolved: Path) -> Path | None:
        for root in self.allowed_roots:
            if resolved == root or root in resolved.parents:
                return root
        return None

    @staticmethod
    def _error(message: str) -> ToolResult:
        return ToolResult(content=f"Error: {message}", success=False, error=message)
