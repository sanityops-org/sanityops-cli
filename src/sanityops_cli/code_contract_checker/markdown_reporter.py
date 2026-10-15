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

"""Generate Markdown report for Code Contract inspection results."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import QCArtifactResult, QCInspectionResult

logger = logging.getLogger(__name__)


def save_qc_report(
    result: QCInspectionResult,
    output_dir: Path,
    *,
    project_id: str | None = None,
) -> Path | None:
    """Save QC inspection result to a markdown file.

    Args:
        result: The QC inspection result.
        output_dir: Directory to save the report.
        project_id: Optional project ID.

    Returns:
        Path to the saved report, or None if save failed.
    """
    try:
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"qc-inspect-{timestamp}.md"
        path = output_dir / filename

        content = _generate_markdown(result, project_id)
        path.write_text(content, encoding="utf-8")
        return path
    except OSError as e:
        logger.warning("Could not save QC report: %s", e)
        return None


def _generate_markdown(
    result: QCInspectionResult,
    project_id: str | None = None,
) -> str:
    """Generate markdown content for the report.

    Args:
        result: The QC inspection result.
        project_id: Optional project ID.

    Returns:
        Markdown string.
    """
    lines: list[str] = [
        "# Code Contract Inspection Report",
        "",
        f"> **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **Inspection time**: {result.inspection_time_seconds:.2f}s",
    ]

    if project_id:
        lines.append(f"> **Project ID**: {project_id}")

    lines.append("")

    # Summary
    lines.extend(
        [
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total artifacts | {result.total_artifacts} |",
            f"| Total defects | {result.total_defects} |",
            f"| P0 (blocking) | {result.p0_count} |",
            f"| P1 (warning) | {result.p1_count} |",
            f"| P2 (advisory) | {result.p2_count} |",
            f"| **QC Gate** | **{result.gate_result}** |",
            "",
        ]
    )

    # Artifacts section
    lines.extend(
        [
            "## Artifacts",
            "",
        ]
    )

    # Skills
    if result.skills:
        lines.append("### Skills")
        lines.append("")
        for artifact in result.skills:
            _render_artifact_section(lines, artifact)

    # Tools
    if result.tools:
        lines.append("### Tools")
        lines.append("")
        for artifact in result.tools:
            _render_artifact_section(lines, artifact)

    # Prompts
    if result.prompts:
        lines.append("### Prompts")
        lines.append("")
        for artifact in result.prompts:
            _render_artifact_section(lines, artifact)

    # Rule reference
    lines.extend(
        [
            "---",
            "",
            "## Rule Reference",
            "",
            "| Rule ID | Name | Severity | Description |",
            "|---------|------|----------|-------------|",
        ]
    )

    from .models import RULE_DEFINITIONS, QCRuleID

    for rule_id in QCRuleID:
        if rule_id in RULE_DEFINITIONS:
            info = RULE_DEFINITIONS[rule_id]
            lines.append(
                f"| {rule_id} | {info['name']} | {info['severity']} | {info['description']} |"
            )

    lines.append("")

    return "\n".join(lines)


def _render_artifact_section(lines: list[str], artifact: QCArtifactResult) -> None:
    """Render an artifact section.

    Args:
        lines: List to append lines to.
        artifact: The artifact to render.
    """
    lines.append(f"#### {artifact.artifact_name}")
    lines.append("")
    lines.append(f"- **Path**: `{artifact.artifact_path}`")
    lines.append(f"- **Defects**: {artifact.total_defects}")
    lines.append("")

    if artifact.defects:
        lines.append("| Rule | Severity | Location | Line | Description | Fix |")
        lines.append("|------|----------|----------|------|-------------|-----|")

        for defect in artifact.defects:
            fix = defect.fix_suggestion or "-"
            if defect.line_number:
                line = str(defect.line_number)
            else:
                line = "-"
            lines.append(
                f"| {defect.rule_id} | {defect.severity} | {defect.location} | "
                f"{line} | {defect.description} | {fix} |"
            )
        lines.append("")
    else:
        lines.append("_No defects found._")
        lines.append("")
