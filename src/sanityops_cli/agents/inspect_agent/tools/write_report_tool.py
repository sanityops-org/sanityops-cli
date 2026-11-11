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
#

"""The InspectAgent's sole output channel (design §6.3).

A real seven-stage report is 66–77KB — far beyond a single response, so the
report arrives incrementally: one ``write_report`` call per section part.
The tool enforces the section vocabulary, the fixed serialization order, and
the per-call size cap; stage completeness (A–G each ≥ 1 part) is checked by
``missing_stages`` and remediated CLI-side.
"""

from __future__ import annotations

import json

from sanityops_agent.tools.base import Tool, ToolResult

#: Fixed serialization order, independent of arrival order.
SECTION_ORDER = (
    "header",
    "exec_summary",
    "glossary",
    "input_notes",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "status_board",
    "self_verification",
)

#: The seven inspection stages that must each have at least one part.
STAGE_SECTIONS = ("A", "B", "C", "D", "E", "F", "G")

#: Provider output ceiling safety margin (same rationale as store_artifacts).
MAX_SECTION_CHARS = 6000


class WriteReportTool(Tool):
    """Incremental report assembly for the InspectAgent.

    One instance per agent run; the CLI renders the final markdown from the
    same instance it registered.
    """

    name = "write_report"
    description = (
        "Write one part of the inspection report. Call repeatedly per section "
        "(stages may need several parts). Sections assemble in a fixed order "
        "regardless of call order. Every stage A-G needs at least one part — "
        "use a part explaining 'Not Executed' when a stage does not run."
    )
    parameters = {
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": list(SECTION_ORDER),
                "description": (
                    "Which report section this part belongs to. Stages A-G map "
                    "to the skill's seven stages; the rest are report scaffolding."
                ),
            },
            "content": {
                "type": "string",
                "minLength": 1,
                "description": "Markdown content of this part (under ~6000 chars).",
            },
            "replace_part": {
                "type": "boolean",
                "description": (
                    "Rewrite the most recent part of this section instead of "
                    "appending (self-correction; never duplicates)."
                ),
            },
        },
        "required": ["section", "content"],
    }
    tags = ["inspect", "report"]

    def __init__(self) -> None:
        super().__init__()
        self._sections: dict[str, list[str]] = {}

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        section = kwargs.get("section")
        content = kwargs.get("content")
        if section not in SECTION_ORDER:
            return self._error(f"section must be one of {SECTION_ORDER}, got {section!r}")
        if not content or not isinstance(content, str):
            return self._error("content must be a non-empty string")
        if len(content) > MAX_SECTION_CHARS:
            return self._error(
                f"content is {len(content)} chars; split into parts of at most "
                f"{MAX_SECTION_CHARS} chars"
            )

        parts = self._sections.setdefault(section, [])
        if kwargs.get("replace_part") and parts:
            parts[-1] = content
            action = "replaced"
        else:
            parts.append(content)
            action = "appended"
        return self._ok(f"{action} part in section '{section}' ({len(parts)} part(s))")

    # ------------------------------------------------------------------
    # CLI-side assembly
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Assemble the full report in fixed section order."""
        chunks: list[str] = []
        for section in SECTION_ORDER:
            parts = self._sections.get(section)
            if not parts:
                continue
            chunks.append("\n\n".join(parts))
        return "\n\n".join(chunks)

    def missing_stages(self) -> list[str]:
        """Stage sections (A-G) that received no part at all."""
        return [stage for stage in STAGE_SECTIONS if not self._sections.get(stage)]

    def section_parts(self) -> dict[str, list[str]]:
        """Read-only view of the stored parts (for the fail-closed ladder)."""
        return {section: list(parts) for section, parts in self._sections.items()}

    @staticmethod
    def _ok(message: str) -> ToolResult:
        return ToolResult(content=json.dumps({"success": True, "message": message}), success=True)

    @staticmethod
    def _error(message: str) -> ToolResult:
        return ToolResult(
            content=json.dumps({"success": False, "error": message}, ensure_ascii=False),
            success=False,
            error=message,
        )
