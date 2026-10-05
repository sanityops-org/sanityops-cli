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
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sanityops_cli.defect_checker.renderer import _MODULE_LABELS

_log = logging.getLogger(__name__)


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


def _aggregate_cross_defects(cross_results: list[dict]) -> list[dict]:
    """Aggregate defects from all CROSS sub-results (PS/PT/ST) into one list.

    Maps SDK DefectItem format to CrossScoringCalculator format:
        id -> defect_id
        severity -> defect_level
        category -> relation (QD-PS, QD-PT, QD-ST)
    """
    defects = []
    for result in cross_results:
        for d in result.get("defects") or []:
            if not isinstance(d, dict):
                continue
            defects.append({
                "defect_id": d.get("id"),
                "defect_level": d.get("severity"),
                "relation": d.get("category"),
            })
    return defects


def _format_permission_table(defects: list[dict]) -> list[str]:
    """Generate extended markdown table for QD-PM permission defects.

    Columns: ID | Name | Severity | Action | Permission Side | Duty Side | Fix
    """
    lines = []
    lines.append("| ID | Name | Severity | Action | Permission Side | Duty Side | Fix |")
    lines.append("|---|---|---|---|---|---|---|")

    for defect in defects:
        details = defect.get("details", {})
        if not isinstance(details, dict):
            details = {}

        defect_id = _esc_md_cell(defect.get("id") or "defect")
        name = _esc_md_cell(defect.get("name"))
        severity = _esc_md_cell(defect.get("severity"))
        action = _esc_md_cell(details.get("action"))
        permission_side = _esc_md_cell(details.get("permission_side"))
        duty_side = _esc_md_cell(details.get("duty_side"))
        fix = _esc_md_cell(defect.get("fix_suggestion"))

        lines.append(
            f"| {defect_id} | {name} | {severity} | {action} | "
            f"{permission_side} | {duty_side} | {fix} |"
        )

    return lines


def _calculate_cross_score(
    defects: list[dict],
    check_level: str,
) -> dict | None:
    """Compute merged CROSS score using SDK's CrossScoringCalculator.

    The SDK uses weighted deductions per PS/PT/ST group:
        P0:P1:P2 = 5:3:1 deduction weights
        Gate FAIL when any group has P0 defect

    Returns None on any failure so the report degrades gracefully instead of
    crashing. This is intentional: the SDK import or calculation may fail in
    unexpected ways, and we prefer an unscored CROSS section over no report.
    """
    if not defects:
        return None
    try:
        from defect_check.cross.scoring import CrossScoringCalculator
        scoring = CrossScoringCalculator().calculate_score(defects, check_level, mode=None)
    except Exception as e:
        # Intentional broad catch: SDK import, configuration, or calculation
        # failures should not prevent report generation.
        _log.warning("Cross scoring calculation failed: %s", e)
        return None
    return {
        "total_score": scoring.get("total_score"),
        "gate_result": scoring.get("gate_result", "PASS"),
    }


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

    # Separate CROSS from other modules and merge
    module_results = [r for r in results if r.get("module") != "CROSS"]
    cross_results = [r for r in results if r.get("module") == "CROSS"]

    if cross_results:
        # Merge all CROSS sub-results into single section
        cross_defects = [d for r in cross_results for d in (r.get("defects") or [])]
        mapped_defects = _aggregate_cross_defects(cross_results)
        cross_score = _calculate_cross_score(mapped_defects, check_level)

        module_results.append({
            "module": "CROSS",
            "status": "completed",
            "defects": cross_defects,
            "score": cross_score,
        })

    # Per-module results
    for result in module_results:
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

        # Use permission-specific table for QD-PM module.
        # Note: Detection is by module, which differs from renderer's per-defect
        # detection. This is intentional: markdown uses module-level table structure,
        # while terminal formatting is per-defect. Both produce consistent output.
        if module == "QD-PM":
            lines.extend(_format_permission_table(defects))
            lines.append("")
            continue

        # Standard defect table for other modules
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
    filename = f"inspect-{generated_at.strftime('%Y%m%d-%H%M%S-%f')}.md"
    path = output_dir / filename

    body = _build_report(response, project_id=project_id, check_level=check_level, generated_at=generated_at)
    path.write_text(body, encoding="utf-8")

    return path
