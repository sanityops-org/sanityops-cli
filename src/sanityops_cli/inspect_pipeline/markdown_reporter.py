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

"""Full report persistence (design §8).

Assembles the final markdown from the report tool's section parts in fixed
order, inserts "NOT RECEIVED" placeholders for stages the agent never
emitted, and appends the tail JSON block for audit. Best-effort: a failure
to write never fails the command (same semantics as the previous pipeline).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sanityops_cli.agents.inspect_agent.tools.write_report_tool import (
    SECTION_ORDER,
    STAGE_SECTIONS,
)


def assemble_report(
    section_parts: dict[str, list[str]],
    missing_stages: list[str],
    tail_block: str | None,
    meta: dict[str, str] | None = None,
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

    if tail_block:
        chunks.append(tail_block)

    return "\n\n".join(chunks) + "\n"


def save_inspection_report(
    section_parts: dict[str, list[str]],
    missing_stages: list[str],
    tail_block: str | None,
    output_dir: Path,
    *,
    meta: dict[str, str] | None = None,
    timestamp: str | None = None,
) -> Path:
    """Write ``inspect-<ts>.md``; returns the path (best-effort)."""
    output_dir = Path(output_dir)
    ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"inspect-{ts}.md"
    path = output_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        assemble_report(section_parts, missing_stages, tail_block, meta),
        encoding="utf-8",
    )
    return path
