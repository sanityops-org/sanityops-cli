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
"""Render defect-check results in the terminal, grouped by artifact type."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

#: URL advertised in the footer for the full experience.
FULL_EXPERIENCE_URL = "https://www.sanityops.org"

#: Map defect-check module names to display group labels.
_MODULE_LABELS: dict[str, str] = {
    "QDS": "Skills",
    "QDT": "Tools",
    "QDP": "Prompts",
}

#: Maximum number of defects rendered per group.
MAX_DEFECTS_PER_GROUP = 2


class DefectRenderer:
    """Renders a defect-check response dict for the terminal (English output)."""

    def __init__(self, console: Console):
        self.console = console

    def render(self, result: dict) -> None:
        """Render summary, per-group defects, and the footer."""
        self._render_summary(result.get("summary", {}))
        self._render_artifact_groups(result.get("results", []))
        self._render_footer()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _render_summary(self, summary: dict[str, Any]) -> None:
        total = summary.get("total_defects", 0)
        p0 = summary.get("p0_count", 0)
        p1 = summary.get("p1_count", 0)
        p2 = summary.get("p2_count", 0)
        gate = summary.get("gate_result", "PASS")

        table = Table(title="Defect Check Summary", border_style="blue")
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Total defects", str(total))
        table.add_row("Severity", f"P0: {p0}   P1: {p1}   P2: {p2}")
        gate_style = "red bold" if gate == "FAIL" else "green bold"
        table.add_row("Gate", f"[{gate_style}]{gate}[/]")
        self.console.print(table)
        self.console.print()

    # ------------------------------------------------------------------
    # Artifact groups
    # ------------------------------------------------------------------

    def _render_artifact_groups(self, results: list[dict[str, Any]]) -> None:
        for result in results:
            module = result.get("module")
            label = _MODULE_LABELS.get(module)
            if label is None:
                # CROSS and any unknown modules are not rendered.
                continue
            defects = result.get("defects", [])
            if not defects:
                continue
            self._render_group(label, defects)
            self.console.print()

    def _render_group(self, label: str, defects: list[dict[str, Any]]) -> None:
        lines: list[str] = []
        shown = defects[:MAX_DEFECTS_PER_GROUP]
        for defect in shown:
            lines.append(self._format_defect(defect))

        hidden = len(defects) - len(shown)
        if hidden > 0:
            lines.append(f"[dim]... {hidden} more defects not shown[/dim]")

        body = "\n".join(lines)
        self.console.print(Panel(body, title=label, border_style="cyan"))

    def _format_defect(self, defect: dict[str, Any]) -> str:
        severity = defect.get("severity", "NONE")
        defect_id = defect.get("id") or "defect"
        lines = [f"[bold red]✗ [{severity}] {defect_id}[/]"]
        if defect.get("location"):
            lines.append(f"  [dim]Location[/] : {defect['location']}")
        if defect.get("impact"):
            lines.append(f"  [dim]Impact[/]   : {defect['impact']}")
        if defect.get("fix_suggestion"):
            lines.append(f"  [dim]Fix[/]      : {defect['fix_suggestion']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _render_footer(self) -> None:
        self.console.print(
            Panel(
                f"For the full experience, visit\n{FULL_EXPERIENCE_URL}",
                border_style="green",
            )
        )
