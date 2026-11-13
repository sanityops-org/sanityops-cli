"""Terminal rendering of the inspection summary (design §8).

Each section shows all P0 findings and fills up to three rows with other
severities. Findings are ordered by severity and rule ID.
"""

from __future__ import annotations

from itertools import groupby

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sanityops_cli.inspect_pipeline.report_parser import (
    KNOWN_MODULES,
    SEVERITY_RANK,
    STAGE_SECTIONS,
    ParsedSummary,
)

MAX_PER_SECTION = 3
MAX_PANEL_WIDTH = 112

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


def _finding_body(finding: dict) -> Text:
    body = Text(str(finding.get("id") or finding.get("module", "?")), style="bold", overflow="fold")
    artifact = finding.get("artifact")
    if isinstance(artifact, list):
        artifact = ", ".join(map(str, artifact))
    if artifact:
        body.append(f"  ·  {artifact}", style="dim")
    description = finding.get("description")
    if description:
        body.append(f"\n{description}", style="not bold")
    return body


def _section_for(
    title: str,
    findings: list[dict],
    *,
    empty: str = "no findings",
    title_style: str = "bold cyan",
) -> RenderableType:
    heading = Text().append(title, style=title_style)
    if not findings:
        return heading.append(f"  ·  {empty}", style="dim")

    rows = Table.grid(padding=(0, 2), expand=True)
    rows.add_column(width=4, no_wrap=True)
    rows.add_column(ratio=1)
    limit = max(MAX_PER_SECTION, sum(finding.get("severity") == "P0" for finding in findings))
    for finding in findings[:limit]:
        severity = finding.get("severity", "?")
        rows.add_row(
            Text(f"[{severity}]", style=_SEVERITY_STYLE.get(severity, "white")),
            _finding_body(finding),
        )
    if len(findings) > limit:
        rows.add_row("", Text(f"… +{len(findings) - limit} more", style="dim"))
    return Group(heading, rows)


def _empty_stage(summary: ParsedSummary, stage: str) -> str:
    status = summary.stage_status(stage)
    if status.lower() in {"executed", "completed", "passed"}:
        return "no recorded findings" if summary.counts_partial else "no findings"
    return status


def _stage_overview(summary: ParsedSummary) -> Text:
    overview = Text().append("Stages  ", style="bold")
    for i, (status, stages) in enumerate(groupby(STAGE_SECTIONS, key=summary.stage_status)):
        ids = list(stages)
        label = ids[0] if len(ids) == 1 else f"{ids[0]}–{ids[-1]}"
        if i:
            overview.append("  ·  ", style="dim")
        style = "yellow" if any(stage in summary.missing_stages for stage in ids) else ""
        overview.append(f"{label}: {status}", style=style)
    return overview


def render_inspection_summary(
    console: Console,
    summary: ParsedSummary,
    *,
    verbose: bool = False,
    warnings: list[str] | None = None,
    duration: float | None = None,
) -> None:
    """Render counts, stage coverage, and grouped findings in the terminal."""
    if warnings is None:
        warnings = summary.warnings
    if duration is not None:
        if summary.status == "completed":
            console.print(f"[green]✓[/] Inspection completed in {duration:.1f}s")
        elif summary.status == "failed":
            console.print(f"[red]✗[/] Inspection failed after {duration:.1f}s")
        else:
            console.print(f"[yellow]⚠[/] Inspection incomplete after {duration:.1f}s")
    counts = summary.counts
    inspect_counts = counts.get("inspect", {})
    explicit_counts = counts.get("risk_explicit", {})

    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold")
    for _ in SEVERITY_RANK:
        header.add_column(justify="right", no_wrap=True)
    label = " (recorded)" if summary.counts_partial else ""
    for name, bucket in (("Inspect", inspect_counts), ("Explicit", explicit_counts)):
        values = bucket if isinstance(bucket, dict) else {}
        header.add_row(
            f"{name}{label}",
            *(f"{severity}: {values.get(severity.lower(), '?')}" for severity in SEVERITY_RANK),
        )
    console.print(header)
    console.print(_stage_overview(summary))

    sections: list[RenderableType] = []
    findings = summary.findings
    groups = (
        *(("A", module, (module,)) for module in STAGE_A_MODULES),
        ("B", "Cross", CROSS_MODULES),
        ("D", "QD-PM", PM_MODULES),
        ("E", "Explicit Risk", EX_MODULES),
        ("F", "Impact mapping", IMPACT_MODULES),
    )
    previous_has_findings = False
    for stage, title, modules in groups:
        rows = _findings_for_modules(findings, modules)
        if not verbose and stage not in {"B", "E"}:
            if not rows or (stage == "F" and all(f.get("severity") != "P0" for f in rows)):
                continue
        if sections and (rows or previous_has_findings):
            sections.append(Text())
        explicit_p0 = stage == "E" and explicit_counts.get("p0", 0) > 0
        sections.append(
            _section_for(
                f"Stage {stage} — {title}",
                rows,
                empty=_empty_stage(summary, stage),
                title_style="bold red" if explicit_p0 else "bold cyan",
            )
        )
        if explicit_p0:
            sections.append(Text("Explicit·P0 is a risk signal, not a defect verdict", "bold red"))
        previous_has_findings = bool(rows) or explicit_p0

    other_findings = sorted(
        (f for f in findings if f.get("module") not in KNOWN_MODULES), key=_sort_key
    )
    if other_findings:
        sections.extend((Text(), _section_for("Other findings", other_findings)))

    console.print(
        Panel(
            Group(*sections),
            title="Findings",
            title_align="left",
            border_style="dim cyan",
            width=min(console.width, MAX_PANEL_WIDTH),
        )
    )

    if warnings:
        console.print()
        for warning in warnings:
            console.print(Text(f"⚠ {warning}", style="yellow"))

    if duration is None and summary.status != "completed":
        console.print("[bold red]✗ inspection incomplete[/]")
