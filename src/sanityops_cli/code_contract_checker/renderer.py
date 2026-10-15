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

"""Render Code Contract inspection results to terminal."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .models import (
    GateResult,
    QCArtifactResult,
    QCDefect,
    QCInspectionResult,
)


class QCRenderer:
    """Renders QC inspection results for the terminal."""

    def __init__(self, console: Console | None = None):
        """Initialize the renderer.

        Args:
            console: Rich console to use. If None, creates a new one.
        """
        self.console = console or Console()

    def render(self, result: QCInspectionResult) -> None:
        """Render the complete inspection result.

        Args:
            result: The QC inspection result to render.
        """
        self._render_summary(result)
        self._render_artifact_groups(result)
        self._render_footer(result)

    def _render_summary(self, result: QCInspectionResult) -> None:
        """Render the summary table.

        Args:
            result: The QC inspection result.
        """
        table = Table(title="Code Contract Inspection Summary", border_style="blue")
        table.add_column("Metric", style="bold")
        table.add_column("Value")

        table.add_row("Total artifacts", str(result.total_artifacts))
        table.add_row("Total defects", str(result.total_defects))

        severity_str = f"P0: {result.p0_count}   P1: {result.p1_count}   P2: {result.p2_count}"
        table.add_row("Severity", severity_str)

        gate_style = "red bold" if result.gate_result == GateResult.FAIL else "green bold"
        table.add_row("QC Gate", f"[{gate_style}]{result.gate_result}[/]")

        table.add_row("Inspection time", f"{result.inspection_time_seconds:.2f}s")

        self.console.print(table)
        self.console.print()

    def _render_artifact_groups(self, result: QCInspectionResult) -> None:
        """Render defects grouped by artifact.

        Args:
            result: The QC inspection result.
        """
        # Skills
        for artifact in result.skills:
            if artifact.defects:
                self._render_artifact_panel(artifact, "Skill")

        # Tools
        for artifact in result.tools:
            if artifact.defects:
                self._render_artifact_panel(artifact, "Tool")

        # Prompts
        for artifact in result.prompts:
            if artifact.defects:
                self._render_artifact_panel(artifact, "Prompt")

    def _render_artifact_panel(self, artifact: QCArtifactResult, type_label: str) -> None:
        """Render a single artifact's defects in a panel.

        Args:
            artifact: The artifact result.
            type_label: The type label ("Skill", "Tool", "Prompt").
        """
        lines: list[str] = []

        for defect in artifact.defects:
            lines.append(self._format_defect(defect))

        title = f"{type_label} {artifact.artifact_name}"
        self.console.print(
            Panel(
                "\n".join(lines),
                title=escape(title),
                border_style="cyan",
            )
        )
        self.console.print()

    def _format_defect(self, defect: QCDefect) -> str:
        """Format a single defect for display.

        Args:
            defect: The defect to format.

        Returns:
            Formatted string.
        """
        severity_color = {
            "P0": "red bold",
            "P1": "yellow bold",
            "P2": "dim",
        }

        color = severity_color.get(defect.severity.value, "white")

        # Use ASCII-safe X instead of Unicode checkmark for Windows compatibility
        title = f"[{color}]X [{defect.severity.value}] {defect.rule_id}[/] - {escape(defect.name)}"

        lines = [title]

        if defect.description:
            lines.append(f"  [dim]Desc[/]     : {escape(defect.description)}")

        if defect.location:
            lines.append(f"  [dim]Location[/] : {defect.location}")

        if defect.evidence:
            evidence_display = defect.evidence[:100]
            if len(defect.evidence) > 100:
                evidence_display += "..."
            lines.append(f"  [dim]Evidence[/] : {escape(evidence_display)}")

        if defect.line_number:
            lines.append(f"  [dim]Line[/]     : {defect.line_number}")

        if defect.fix_suggestion:
            lines.append(f"  [dim]Fix[/]      : {defect.fix_suggestion}")

        return "\n".join(lines)

    def _render_footer(self, result: QCInspectionResult) -> None:
        """Render the footer with gate result.

        Args:
            result: The QC inspection result.
        """
        if result.gate_result == GateResult.FAIL:
            self.console.print(
                Panel(
                    "[red bold]QC Gate: FAIL[/]\n\n"
                    "P0 defects found. Consider fixing them to improve artifact quality.",
                    border_style="red",
                )
            )
        else:
            self.console.print(
                Panel(
                    "[green bold]QC Gate: PASS[/]\n\n"
                    "No blocking defects found. Proceeding to LLM analysis.",
                    border_style="green",
                )
            )
