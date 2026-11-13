"""The InspectAgent's sole output channel (design §6.3).

A real seven-stage report is 66–77KB — far beyond a single response, so the
report arrives incrementally: one ``write_report`` call per section part.
The tool enforces the section vocabulary, the fixed serialization order, and
the per-call size cap; stage completeness (A–G each ≥ 1 part) is checked by
``missing_stages`` and remediated CLI-side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from aidynamic_agent.tools.base import Tool, ToolResult

from deeplogic_cli.inspect_pipeline.report_parser import MODULE_STAGE, SEVERITY_RANK, STAGE_SECTIONS

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

_FINDING_SECTIONS = frozenset(MODULE_STAGE.values())

#: Provider output ceiling safety margin (same rationale as store_artifacts).
MAX_SECTION_CHARS = 6000


@dataclass
class _ReportPart:
    content: str
    findings: list[dict] | None


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
            "findings": {
                "type": "array",
                "description": (
                    "Every structured finding described in this part of stage A, B, D, E or F. "
                    "Pass [] for parts without findings. Each finding belongs to one part."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string", "enum": list(MODULE_STAGE)},
                        "artifact": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                        },
                        "id": {"type": "string"},
                        "severity": {"type": "string", "enum": list(SEVERITY_RANK)},
                        "description": {"type": "string", "maxLength": 120},
                    },
                    "required": ["module", "artifact", "id", "severity", "description"],
                },
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

    def __init__(self, *, require_findings: bool = False) -> None:
        super().__init__()
        self._require_findings = require_findings
        self._rejected_parts: dict[str, set[str]] = {}
        self._sections: dict[str, list[_ReportPart]] = {}
        if require_findings:
            self.parameters = {**self.parameters, "required": ["section", "content", "findings"]}

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

        findings = kwargs.get("findings")
        if findings is None:
            error = (
                "findings is required (use [] when there are no findings)"
                if self._require_findings and section in _FINDING_SECTIONS
                else None
            )
        else:
            error = self._validate_findings(section, findings)
        if error:
            self._rejected_parts.setdefault(section, set()).add(content.strip())
            return self._error(
                f"{error}. Correct findings and resend the same content in {section}."
            )
        if findings is not None:
            findings = [dict(finding, stage=section) for finding in findings]

        part = _ReportPart(content, findings)
        parts = self._sections.setdefault(section, [])
        if kwargs.get("replace_part") and parts:
            parts[-1] = part
            action = "replaced"
        else:
            parts.append(part)
            action = "appended"
        pending = self._rejected_parts.get(section)
        recovered = pending is not None and content.strip() in pending and findings is not None
        if recovered and pending is not None:
            pending.discard(content.strip())
        return self._ok(
            f"{action} part in section '{section}' ({len(parts)} part(s))",
            section=section,
            part=len(parts),
            action=action,
            recovered=recovered,
        )

    @staticmethod
    def _validate_findings(section: str, findings: object) -> str | None:
        if not isinstance(findings, list):
            return "findings must be an array of objects"
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                return f"findings[{index}] must be an object"
            module = finding.get("module")
            if not isinstance(module, str) or MODULE_STAGE.get(module) != section:
                return f"findings[{index}].module must belong to section {section}"
            severity = finding.get("severity")
            if not isinstance(severity, str) or severity not in SEVERITY_RANK:
                return f"findings[{index}].severity must be P0, P1 or P2"
            for field in ("id", "description"):
                value = finding.get(field)
                if not isinstance(value, str) or not value.strip():
                    return f"findings[{index}].{field} must be a non-empty string"
            artifact = finding.get("artifact")
            if not isinstance(artifact, str) and not (
                isinstance(artifact, list) and all(isinstance(name, str) for name in artifact)
            ):
                return f"findings[{index}].artifact must be a name or a list of names"
        return None

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
            chunks.append("\n\n".join(part.content for part in parts))
        return "\n\n".join(chunks)

    def missing_stages(self) -> list[str]:
        """Stage sections (A-G) that received no part at all."""
        return [stage for stage in STAGE_SECTIONS if not self._sections.get(stage)]

    def section_parts(self) -> dict[str, list[str]]:
        """Read-only view of the stored parts (for the fail-closed ladder)."""
        return {
            section: [part.content for part in parts] for section, parts in self._sections.items()
        }

    def findings(self) -> list[dict] | None:
        """Return all supplied findings. None indicates a legacy Markdown-only run."""
        batches = [
            part.findings
            for section in STAGE_SECTIONS
            if section in _FINDING_SECTIONS
            for part in self._sections.get(section, [])
            if part.findings is not None
        ]
        return [finding for batch in batches for finding in batch] if batches else None

    def unstructured_stages(self) -> list[str]:
        """Identify received stages with parts missing a structured findings array."""
        return [
            section
            for section in STAGE_SECTIONS
            if section in _FINDING_SECTIONS
            and (
                self._rejected_parts.get(section)
                or any(part.findings is None for part in self._sections.get(section, []))
            )
        ]

    @staticmethod
    def _ok(message: str, **details) -> ToolResult:
        payload = {"success": True, "message": message, **details}
        return ToolResult(content=json.dumps(payload), success=True)

    @staticmethod
    def _error(message: str) -> ToolResult:
        return ToolResult(
            content=json.dumps({"success": False, "error": message}, ensure_ascii=False),
            success=False,
            error=message,
        )
