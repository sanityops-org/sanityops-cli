"""Full report persistence (design §8).

Assembles the final markdown from the report tool's section parts in fixed
order, inserts "NOT RECEIVED" placeholders for stages the agent never
emitted, and appends the tail JSON block for audit. Best-effort: a failure
to write never fails the command (same semantics as the previous pipeline).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from deeplogic_cli.agents.inspect_agent.tools.write_report_tool import (
    SECTION_ORDER,
    STAGE_SECTIONS,
)
from deeplogic_cli.inspect_pipeline.report_parser import (
    ParsedSummary,
    format_counts,
)


def assemble_report(
    section_parts: dict[str, list[str]],
    missing_stages: list[str],
    tail_block: str | None,
    meta: dict[str, str] | None = None,
    *,
    summary: ParsedSummary | None = None,
) -> str:
    """Fixed-order assembly + NOT RECEIVED placeholders + tail JSON."""
    chunks: list[str] = []

    if meta:
        meta_lines = "\n".join(f"- {key}: {value}" for key, value in meta.items())
        chunks.append(f"---\n{meta_lines}\n---\n")

    for section in SECTION_ORDER:
        parts = section_parts.get(section)
        if parts:
            chunks.append("\n\n".join(parts))
        elif section in STAGE_SECTIONS and section in missing_stages:
            # Only stages the report tool actually reported missing; the CLI
            # must not invent placeholders the agent may have delivered.
            chunks.append(f"## Stage {section}\n\nNOT RECEIVED — agent did not emit this stage")

    # Append any extra sections that are not part of standard SECTION_ORDER
    for section, parts in sorted(section_parts.items()):
        if section not in SECTION_ORDER and parts:
            chunks.append("\n\n".join(parts))

    if summary is not None:
        chunks.append(_render_summary(summary, tail_block))
    elif tail_block:
        chunks.append(tail_block)

    return "\n\n".join(chunks) + "\n"


def _render_summary(summary: ParsedSummary, tail_block: str | None) -> str:
    count_label = "Recorded findings" if summary.counts_partial else "Finding counts"
    lines = [
        "## CLI inspection summary",
        "",
        f"- Status: {summary.status}",
        f"- {count_label}: {format_counts(summary.counts)}",
        *(f"- Stage {stage}: {summary.stage_status(stage)}" for stage in STAGE_SECTIONS),
        *(f"- Warning: {warning}" for warning in summary.warnings),
    ]
    if tail_block:
        lines.extend(["", "### Agent summary (raw)", "", "```json", tail_block, "```"])
    return "\n".join(lines)


def save_inspection_report(
    section_parts: dict[str, list[str]],
    missing_stages: list[str],
    tail_block: str | None,
    output_dir: Path,
    *,
    meta: dict[str, str] | None = None,
    summary: ParsedSummary | None = None,
    timestamp: str | None = None,
) -> Path:
    """Write ``inspect-<ts>.md``; returns the path (best-effort)."""
    output_dir = Path(output_dir)
    ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"inspect-{ts}.md"
    path = output_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        assemble_report(section_parts, missing_stages, tail_block, meta, summary=summary),
        encoding="utf-8",
    )
    return path
