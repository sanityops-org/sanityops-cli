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
    "CROSS": "Cross",
    "QD-PM": "Permissions",
}

#: Map module names to singular type labels for panel titles.
_MODULE_TYPE_LABELS: dict[str, str] = {
    "QDS": "Skill",
    "QDT": "Tool",
    "QDP": "Prompt",
    "QD-PM": "Permission",
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
        if not isinstance(defect, dict):
            continue
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
        name = artifacts[0].get("name")
        if isinstance(name, str) and name:
            return name
    return None


def resolve_artifact_title(result: dict[str, Any]) -> str | None:
    """Generate panel title for QDS/QDT/QDP/CROSS results.

    Returns:
        - "Skill morning-report" (type + name) if artifacts resolvable
        - "Skills" (plural label) if not resolvable
        - "Cross" for CROSS module
        - None for unknown modules
    """
    module = result.get("module")

    if module == "CROSS":
        return "Cross"

    fallback_label = _MODULE_LABELS.get(module)
    if fallback_label is None:
        return None

    artifact_names = _resolve_artifact_names(result)
    type_label = _MODULE_TYPE_LABELS.get(module)
    if type_label and artifact_names:
        return f"{type_label} {artifact_names}"
    return fallback_label


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
            module = result.get("module", "")
            title = resolve_artifact_title(result)
            if title is None:
                continue
            defects = result.get("defects", [])
            if not defects:
                continue
            self._render_group(title, defects, module=module)
            self.console.print()

    def _render_group(
        self, label: str, defects: list[dict[str, Any]], *, module: str = ""
    ) -> None:
        lines: list[str] = []
        shown = defects[:MAX_DEFECTS_PER_GROUP]
        for defect in shown:
            lines.append(self._format_defect(defect, module=module))

        hidden = len(defects) - len(shown)
        if hidden > 0:
            lines.append(f"[dim]... {hidden} more defects not shown[/dim]")

        body = "\n".join(lines)
        self.console.print(Panel(body, title=label, border_style="cyan"))

    def _format_defect(self, defect: dict[str, Any], *, module: str = "") -> str:
        """Format a defect for terminal display.

        Dispatches to specialized formatter for permission defects.

        Detection priority: module == "QD-PM" > category == "permission" > ID prefix.
        This is more permissive than markdown_reporter's module-only detection.
        Rationale: terminal output is per-defect and can adapt based on defect
        content, while markdown uses module-level table structure. The primary
        path (module == "QD-PM") is shared; fallbacks handle edge cases where
        defect metadata is inconsistent. This is intentional design.
        """
        # Detect permission defects via module, category, or ID prefix
        category = defect.get("category") or ""
        raw_defect_id = defect.get("id") or ""
        if module == "QD-PM" or category == "permission" or raw_defect_id.startswith("QD-PM"):
            return self._format_permission_defect(defect)

        # Default formatting for other defect types
        severity = defect.get("severity") or "NONE"
        defect_id = raw_defect_id or "defect"
        lines = [f"[bold red]✗ [{severity}] {defect_id}[/]"]
        if defect.get("location"):
            lines.append(f"  [dim]Location[/] : {defect['location']}")
        if defect.get("impact"):
            lines.append(f"  [dim]Impact[/]   : {defect['impact']}")
        if defect.get("fix_suggestion"):
            lines.append(f"  [dim]Fix[/]      : {defect['fix_suggestion']}")
        return "\n".join(lines)

    def _format_permission_defect(self, defect: dict[str, Any]) -> str:
        """Format a QD-PM permission defect with permission-specific fields.

        Shows: name, description, action, permission_side, duty_side from details dict.

        Note: Missing fields are silently omitted (unlike markdown which uses em dash).
        This is intentional for terminal output compactness.
        """
        severity = defect.get("severity") or "NONE"
        defect_id = defect.get("id") or "unknown-permission-defect"
        lines = [f"[bold red]✗ [{severity}] {defect_id}[/]"]

        # Name field (for consistency with markdown table)
        if defect.get("name"):
            lines.append(f"  [dim]Name[/]     : {defect['name']}")

        # Description field (standard field)
        if defect.get("description"):
            lines.append(f"  [dim]Desc[/]     : {defect['description']}")

        # Standard fields
        if defect.get("location"):
            lines.append(f"  [dim]Location[/] : {defect['location']}")
        if defect.get("impact"):
            lines.append(f"  [dim]Impact[/]   : {defect['impact']}")

        # Permission-specific fields from details dict
        details = defect.get("details", {})
        if isinstance(details, dict):
            action = details.get("action")
            if action:
                lines.append(f"  [dim]Action[/]   : {action}")
            permission_side = details.get("permission_side")
            if permission_side:
                lines.append(f"  [dim]Permission[/]: {permission_side}")
            duty_side = details.get("duty_side")
            if duty_side:
                lines.append(f"  [dim]Duty[/]     : {duty_side}")

        # Fix suggestion
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
        lines.extend(
            [
                "For the full experience, visit",
                FULL_EXPERIENCE_URL,
            ]
        )
        self.console.print(
            Panel(
                "\n".join(lines),
                border_style="green",
            )
        )
