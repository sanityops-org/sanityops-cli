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

"""Generate and persist a full Markdown report from a defect-check response dict."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

#: Map defect-check module names to display group labels (mirrors renderer).
_MODULE_LABELS: dict[str, str] = {
    "QDS": "Skills",
    "QDT": "Tools",
    "QDP": "Prompts",
}


def _esc_md_cell(text: str | None) -> str:
    """Escape markdown table cell content: pipes and newlines."""
    if text is None:
        return "—"
    text = html.escape(str(text))
    # Replace pipe to avoid breaking table columns
    text = text.replace("|", r"\|")
    # Replace newlines with <br> so multi-line content stays in one cell
    text = text.replace("\n", "<br>")
    # Strip leading/trailing whitespace to keep table compact
    return text.strip()


def _format_score(score: dict[str, Any] | None) -> str:
    """Format score/grade/gate for a section header, or empty string."""
    if score is None:
        return ""
    parts = []
    if "total_score" in score:
        max_score = score.get("max_score", 100.0)
        parts.append(f"score {score['total_score']}/{max_score}")
    if score.get("grade"):
        parts.append(f"grade {score['grade']}")
    if score.get("gate_result"):
        parts.append(f"gate {score['gate_result']}")
    return ", ".join(parts)


def _build_report(
    response: dict[str, Any],
    *,
    project_id: str | None,
    check_level: str,
    generated_at: datetime,
) -> str:
    """Render the full markdown report body."""
    summary = response.get("summary", {})
    results = response.get("results", [])
    errors = response.get("errors", [])
    metadata = response.get("metadata", {})
    status = response.get("status", "unknown")

    lines: list[str] = []
    lines.append("# Inspect Report")
    lines.append("")

    # Meta
    lines.append(f"- **Generated**: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Check level**: {check_level}")
    lines.append(f"- **Status**: {status}")
    if project_id:
        lines.append(f"- **Project ID**: {project_id}")
    exec_time = metadata.get("execution_time_seconds")
    if exec_time is not None:
        lines.append(f"- **Execution time**: {exec_time:.2f}s")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    total = summary.get("total_defects", 0)
    p0 = summary.get("p0_count", 0)
    p1 = summary.get("p1_count", 0)
    p2 = summary.get("p2_count", 0)
    gate = summary.get("gate_result", "PASS")
    lines.append(f"| Total defects | {total} |")
    lines.append(f"| Severity | P0: {p0} / P1: {p1} / P2: {p2} |")
    lines.append(f"| Gate | {gate} |")
    lines.append("")

    # Per-module results
    for result in results:
        module = result.get("module", "")
        label = _MODULE_LABELS.get(module, module)
        result_status = result.get("status", "unknown")
        score = result.get("score")
        defects = result.get("defects", [])

        score_str = _format_score(score)
        header = f"## {label} ({module}) — {result_status}"
        if score_str:
            header += f", {score_str}"
        lines.append(header)
        lines.append("")

        if not defects:
            lines.append("No defects found.")
            lines.append("")
            continue

        lines.append("| ID | Name | Severity | Description | Location | Impact | Fix |")
        lines.append("|---|---|---|---|---|---|---|")
        for defect in defects:
            defect_id = _esc_md_cell(defect.get("id"))
            name = _esc_md_cell(defect.get("name"))
            severity = _esc_md_cell(defect.get("severity"))
            description = _esc_md_cell(defect.get("description"))
            location = _esc_md_cell(defect.get("location"))
            impact = _esc_md_cell(defect.get("impact"))
            fix = _esc_md_cell(defect.get("fix_suggestion"))
            lines.append(
                f"| {defect_id} | {name} | {severity} | {description} |"
                f" {location} | {impact} | {fix} |"
            )
        lines.append("")

    # Errors section
    if errors:
        lines.append("## Errors")
        lines.append("")
        for err in errors:
            code = err.get("code", "unknown")
            message = err.get("message", "")
            retryable = err.get("retryable", False)
            lines.append(f"- **{code}** (retryable={retryable}): {message}")
        lines.append("")

    return "\n".join(lines)


def save_markdown_report(
    response: dict[str, Any],
    output_dir: Path,
    *,
    project_id: str | None = None,
    check_level: str = "L2",
) -> Path:
    """Persist a full markdown report and return the written file path.

    Args:
        response: Raw dict returned by defect_check.check().
        output_dir: Directory where the report will be written.
        project_id: Optional project identifier to include in the report.
        check_level: Inspection level (L1/L2/L3) to include in the report.

    Returns:
        Path to the written markdown file.
    """
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now()
    filename = f"inspect-{generated_at.strftime('%Y%m%d-%H%M%S')}.md"
    path = output_dir / filename

    body = _build_report(response, project_id=project_id, check_level=check_level, generated_at=generated_at)
    path.write_text(body, encoding="utf-8")

    return path
