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
from rich.markup import escape
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

#: Map module names to singular type labels for panel titles.
_MODULE_TYPE_LABELS: dict[str, str] = {
    "QDS": "Skill",
    "QDT": "Tool",
    "QDP": "Prompt",
}

def _resolve_artifact_names(result: dict[str, Any]) -> str | None:
    """Resolve artifact names from defect's artifact_refs.

    1. Collects artifact_refs from all defects
    2. Maps refs to artifact names via artifacts[].id -> artifacts[].name
    3. Returns comma-separated names or None
    """
    artifacts = [a for a in result.get("artifacts") or [] if isinstance(a, dict)]
    by_id = {a.get("id"): a for a in artifacts if isinstance(a.get("id"), str)}

    names: list[str] = []
    refs: list[str] = []
    for defect in result.get("defects") or []:
        for ref in defect.get("artifact_refs") or []:
            if isinstance(ref, str) and ref not in refs:
                refs.append(ref)

    seen: set[str] = set()
    for ref in refs:
        artifact = by_id.get(ref)
        name = artifact.get("name") if artifact else None
        if isinstance(name, str) and name and name not in seen:
            names.append(name)
            seen.add(name)

    if names:
        return ", ".join(names)
    if len(artifacts) == 1:
        return artifacts[0].get("name")
    return None


#: Maximum number of defects rendered per group.
MAX_DEFECTS_PER_GROUP = 2


class DefectRenderer:
    """Renders a defect-check response dict for the terminal (English output)."""

    def __init__(self, console: Console):
        self.console = console

    def render(self, result: dict, *, report_path: str | None = None) -> None:
        """Render summary, per-group defects, and the footer."""
        self._render_summary(result.get("summary", {}))
        self._render_artifact_groups(result.get("results", []))
        self._render_footer(report_path)

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

    def _render_footer(self, report_path: str | None = None) -> None:
        lines: list[str] = []
        if report_path:
            lines.append(f"Report saved to [magenta]{escape(report_path)}[/magenta]")
        lines.extend([
            "For the full experience, visit",
            FULL_EXPERIENCE_URL,
        ])
        self.console.print(
            Panel(
                "\n".join(lines),
                border_style="green",
            )
        )
