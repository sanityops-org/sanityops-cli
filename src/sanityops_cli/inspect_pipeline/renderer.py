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

"""Terminal rendering of the inspection summary (design §8).

Per-module panels: Stage A splits into QD-P/QD-S/QD-T/QC; Stage B is one
CROSS panel; Stage D QD-PM; Stage E EX with Explicit·P0 visually separated.
Each panel shows the top 3 findings by deterministic order (severity, then
rule id); truncation happens only here — findings[] stays complete.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sanityops_cli.inspect_pipeline.report_parser import SEVERITY_RANK, ParsedSummary

MAX_PER_PANEL = 3

STAGE_A_MODULES = ("QD-P", "QD-S", "QD-T", "QC")
CROSS_MODULES = ("QD-PS", "QD-PT", "QD-ST", "QD-SS", "QD-TT", "QD-CYC")
PM_MODULES = ("QD-PM",)
EX_MODULES = ("EX",)
IMPACT_MODULES = ("AS-FM",)  # Stage F — verbose only

_SEVERITY_STYLE = {"P0": "bold red", "P1": "yellow", "P2": "cyan"}


def _sort_key(finding: dict) -> tuple:
    return (
        SEVERITY_RANK.get(finding.get("severity", ""), 99),
        str(finding.get("id", "")),
    )


def _findings_for_modules(findings: list[dict], modules: tuple[str, ...]) -> list[dict]:
    return sorted((f for f in findings if f.get("module") in modules), key=_sort_key)


def _finding_line(finding: dict) -> Text:
    severity = finding.get("severity", "?")
    line = Text()
    line.append(f"[{severity}] ", style=_SEVERITY_STYLE.get(severity, "white"))
    line.append(str(finding.get("id") or finding.get("module", "?")))
    artifact = finding.get("artifact")
    if artifact:
        line.append(f" {artifact}", style="dim")
    line.append(f": {finding.get('description', '')}")
    return line


def _panel_for(title: str, findings: list[dict], *, border_style: str = "white") -> Panel:
    body = Text()
    if not findings:
        body.append("no findings", style="dim")
    else:
        for i, finding in enumerate(findings[:MAX_PER_PANEL]):
            if i:
                body.append("\n")
            body.append_text(_finding_line(finding))
        remaining = len(findings) - MAX_PER_PANEL
        if remaining > 0:
            body.append(f"\n… +{remaining} more", style="dim")
    return Panel(body, title=title, border_style=border_style, expand=False)


def render_inspection_summary(
    console: Console,
    summary: ParsedSummary,
    *,
    verbose: bool = False,
    warnings: list[str] | None = None,
) -> None:
    """Render the per-module panels + counts + warnings."""
    if warnings is None:
        warnings = summary.warnings
    counts = summary.counts
    inspect_counts = counts.get("inspect", {})
    explicit_counts = counts.get("risk_explicit", {})

    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold")
    header.add_column()
    header.add_row(
        "Inspect",
        f"P0: {inspect_counts.get('p0', 0)}  "
        f"P1: {inspect_counts.get('p1', 0)}  P2: {inspect_counts.get('p2', 0)}",
    )
    header.add_row(
        "Explicit",
        f"P0: {explicit_counts.get('p0', 0)}  "
        f"P1: {explicit_counts.get('p1', 0)}  P2: {explicit_counts.get('p2', 0)}",
    )
    console.print(header)

    findings = summary.findings
    for module in STAGE_A_MODULES:
        module_findings = _findings_for_modules(findings, (module,))
        if module_findings or verbose:
            console.print(_panel_for(f"Stage A — {module}", module_findings))

    console.print(_panel_for("Stage B — Cross", _findings_for_modules(findings, CROSS_MODULES)))

    pm_findings = _findings_for_modules(findings, PM_MODULES)
    if pm_findings or verbose:
        console.print(_panel_for("Stage D — QD-PM", pm_findings))

    ex_findings = _findings_for_modules(findings, EX_MODULES)
    has_explicit_p0 = explicit_counts.get("p0", 0) > 0
    console.print(
        _panel_for(
            "Stage E — Explicit Risk",
            ex_findings,
            border_style="red" if has_explicit_p0 else "white",
        )
    )
    if has_explicit_p0:
        console.print("[bold red]Explicit·P0 is a risk signal, not a defect verdict[/]")

    if verbose:
        console.print(
            _panel_for("Stage F — Impact mapping", _findings_for_modules(findings, IMPACT_MODULES))
        )

    if warnings:
        console.print()
        for warning in warnings:
            console.print(f"[yellow]⚠ {warning}[/]")

    if summary.status != "completed":
        console.print("[bold red]✗ inspection incomplete[/]")
