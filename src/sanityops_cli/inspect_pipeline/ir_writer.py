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

"""Two-layer IR rendering (design §2 step ③, §6.2).

One IR markdown per input document, written to
``.sanityops/results/ir/<run_id>/<basename>.ir.md`` as a pure audit artifact.
The same serialization feeds the InspectAgent injection payload (§6.2) —
rendering here is the single source for both.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from sanityops_cli.inspect_pipeline.models import (
    ExtractedArtifact,
    ExtractionResult,
)


def group_by_source(result: ExtractionResult) -> dict[str, list[ExtractedArtifact]]:
    """Group artifacts by their source document path (sorted for stability)."""
    grouped: dict[str, list[ExtractedArtifact]] = {}
    for artifact in result.artifacts:
        grouped.setdefault(artifact.source, []).append(artifact)
    return {source: grouped[source] for source in sorted(grouped)}


def _reference_routing(
    result: ExtractionResult,
) -> tuple[dict[str, list], list]:
    """Route references to the doc of the artifact they reference.

    ``referenced_by`` is an artifact name; a reference belongs to the IR of
    the document containing the artifact with that name. Unmatched names go
    to the second return value (they are themselves findings — dangling
    references must stay visible).
    """
    name_to_source: dict[str, str] = {}
    for artifact in result.artifacts:
        name_to_source.setdefault(artifact.name, artifact.source)

    routed: dict[str, list] = {}
    unmatched: list = []
    for reference in result.references:
        source = name_to_source.get(reference.referenced_by)
        if source is None:
            unmatched.append(reference)
        else:
            routed.setdefault(source, []).append(reference)
    return routed, unmatched


def _fence(content: str, language: str = "") -> str:
    """Wrap content in a code fence that survives embedded backticks."""
    longest = 0
    run = 0
    for char in content:
        if char == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{language}\n{content}\n{ticks}"


def render_document_ir(
    source: str,
    artifacts: list[ExtractedArtifact],
    references: list,
) -> str:
    """Render one document's IR markdown (object layer + reference layer)."""
    lines: list[str] = [
        f"# IR — {Path(source).name}",
        "",
        f"- source: `{source}`",
        f"- artifacts: {len(artifacts)}",
        "",
    ]

    lines.append("## Object layer")
    for artifact in artifacts:
        meta = f"{artifact.completeness}, {artifact.L}, {artifact.extraction_method}"
        lines.append(f"### [{artifact.type}] {artifact.name} ({meta})")
        lines.append("")
        if artifact.completeness == "not inspectable":
            lines.append(f"Not inspectable: {artifact.reason}")
            lines.append("")
            continue
        if artifact.type == "tool" and artifact.schema_object:
            lines.append(
                _fence(json.dumps(artifact.schema_object, ensure_ascii=False, indent=2), "json")
            )
            lines.append("")
        if artifact.content:
            lines.append(_fence(artifact.content))
            lines.append("")
        if artifact.field_evidence:
            lines.append("| field | source snippet |")
            lines.append("|---|---|")
            for fe in artifact.field_evidence:
                snippet = fe.snippet.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{fe.field}` | {snippet} |")
            lines.append("")
        if artifact.evidence:
            lines.append(f"Evidence: {artifact.evidence}")
            lines.append("")

    lines.append("## Reference layer")
    if references:
        lines.append("| referenced name | referenced by | relationship |")
        lines.append("|---|---|---|")
        for ref in references:
            lines.append(f"| {ref.name} | {ref.referenced_by} | {ref.relationship} |")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## ir-core")
    objects = []
    for artifact in artifacts:
        obj: dict = {
            "type": artifact.type,
            "name": artifact.name,
            "source": artifact.source,
            "completeness": artifact.completeness,
            "L": artifact.L,
            "extraction_method": artifact.extraction_method,
        }
        if artifact.content:
            obj["content"] = artifact.content
        if artifact.schema_object:
            obj["schema"] = artifact.schema_object
        if artifact.evidence:
            obj["evidence"] = artifact.evidence
        if artifact.field_evidence:
            obj["field_evidence"] = [fe.model_dump() for fe in artifact.field_evidence]
        if artifact.reason:
            obj["reason"] = artifact.reason
        objects.append(obj)
    ir_core = {
        "objects": objects,
        "references": [ref.model_dump() for ref in references],
    }
    lines.append(_fence(json.dumps(ir_core, ensure_ascii=False, indent=2), "json"))
    lines.append("")
    return "\n".join(lines)


def allocate_run_id(results_dir: Path, timestamp: str | None = None) -> str:
    """Allocate a collision-free batch ID shared by the IR folder and report.

    Normally returns ``YYYYMMDD-HHMMSS``; appends ``-2``, ``-3``, ... when a
    matching report file or IR batch directory already exists.
    """
    results_dir = Path(results_dir)
    ir_root = results_dir / "ir"
    base = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = 1
    while True:
        candidate = base if suffix == 1 else f"{base}-{suffix}"
        report_exists = (results_dir / f"inspect-{candidate}.md").exists()
        ir_exists = (ir_root / candidate).exists()
        if not report_exists and not ir_exists:
            return candidate
        suffix += 1


def _resolve_ir_filenames(sources: list[str], *, reserve_unmatched: bool) -> dict[str, str]:
    """Map each source path to a collision-free ``*.ir.md`` filename."""
    stems = {source: (Path(source).stem or "document") for source in sources}
    parents = {
        source: re.sub(r"[^A-Za-z0-9._-]+", "_", Path(source).parent.name).strip("_")
        for source in sources
    }
    stem_counts = Counter(stems.values())
    parent_stem_counts = Counter((parents[s], stems[s]) for s in sources)

    used: set[str] = {"_unmatched-references.ir.md"} if reserve_unmatched else set()
    mapping: dict[str, str] = {}
    for source in sources:
        stem = stems[source]
        parent = parents[source]
        if stem_counts[stem] == 1 and f"{stem}.ir.md" not in used:
            candidate = f"{stem}.ir.md"
        elif (
            parent
            and parent_stem_counts[(parent, stem)] == 1
            and f"{parent}__{stem}.ir.md" not in used
        ):
            candidate = f"{parent}__{stem}.ir.md"
        else:
            digest = hashlib.sha256(source.encode()).hexdigest()[:8]
            prefix = f"{parent}__{stem}" if parent else stem
            candidate = f"{prefix}_{digest}.ir.md"
            attempts = 0
            while candidate in used:
                attempts += 1
                if attempts > 1000:
                    raise RuntimeError(f"Could not allocate unique IR filename for {source}")
                digest = hashlib.sha256(f"{source}:{len(used)}:{attempts}".encode()).hexdigest()[:8]
                candidate = f"{prefix}_{digest}.ir.md"
        used.add(candidate)
        mapping[source] = candidate
    return mapping


def write_ir_files(
    result: ExtractionResult,
    ir_dir: Path,
    *,
    run_id: str | None = None,
) -> list[Path]:
    """Write one IR file per source document; returns the written paths.

    When ``run_id`` is provided, files are written under ``ir_dir / run_id`` so
    each inspection run gets an isolated batch directory.

    References whose ``referenced_by`` matches no extracted artifact are
    collected into ``_unmatched-references.ir.md`` — they are findings, not
    noise, and must not disappear.
    """
    grouped = group_by_source(result)
    routed, unmatched = _reference_routing(result)

    target_dir = Path(ir_dir) / run_id if run_id else Path(ir_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    filenames = _resolve_ir_filenames(list(grouped), reserve_unmatched=bool(unmatched))

    written: list[Path] = []
    for source, artifacts in grouped.items():
        path = target_dir / filenames[source]
        path.write_text(
            render_document_ir(source, artifacts, routed.get(source, [])),
            encoding="utf-8",
        )
        written.append(path)

    if unmatched:
        path = target_dir / "_unmatched-references.ir.md"
        path.write_text(
            render_document_ir("(unmatched references)", [], unmatched),
            encoding="utf-8",
        )
        written.append(path)
    return written


def render_injection_payload(result: ExtractionResult) -> str:
    """Build the InspectAgent injection payload (design §6.2).

    Contains everything the check must not lose: the extraction summary
    (counts, distributions, attribution), the per-document object layer with
    field evidence, the reference layer, and the not-inspectable list.
    """
    artifacts = result.artifacts
    type_counts = Counter(a.type for a in artifacts)
    completeness_counts = Counter(a.completeness for a in artifacts)
    level_counts = Counter(a.L for a in artifacts)
    not_inspectable = [a for a in artifacts if a.completeness == "not inspectable"]

    lines: list[str] = ["# Extraction IR payload", ""]

    lines.append("## Extraction summary")
    lines.append(
        f"- artifacts: {len(artifacts)} — "
        + ", ".join(f"{t}: {n}" for t, n in sorted(type_counts.items()))
    )
    lines.append(
        "- completeness: "
        + ", ".join(f"{label}: {n}" for label, n in sorted(completeness_counts.items()))
    )
    lines.append(
        "- L levels: " + ", ".join(f"{level}: {n}" for level, n in sorted(level_counts.items()))
    )
    if result.attribution:
        lines.append(
            f"- attribution: {result.attribution.status}"
            + (f" — {result.attribution.note}" if result.attribution.note else "")
        )
    else:
        lines.append("- attribution: not reported by the extraction agent")
    if result.meta.deterministic_candidates:
        lines.append(
            f"- deterministic candidates: {result.meta.deterministic_candidates} "
            "(records marked extraction_method=deterministic were never agent-reviewed; "
            "treat their L as unknown)"
        )
    lines.append("")

    if not_inspectable:
        lines.append("## Not inspectable (no L assigned)")
        for artifact in not_inspectable:
            lines.append(f"- [{artifact.type}] {artifact.name} — {artifact.reason}")
        lines.append("")

    grouped = group_by_source(result)
    routed, unmatched = _reference_routing(result)
    for source, doc_artifacts in grouped.items():
        lines.append(f"## Document: {source}")
        lines.append("")
        lines.append(render_document_ir(source, doc_artifacts, routed.get(source, [])))

    if unmatched:
        lines.append("## Unmatched references (referenced artifact not in the extracted set)")
        for ref in unmatched:
            lines.append(f"- {ref.referenced_by} -> {ref.name} ({ref.relationship})")
        lines.append("")

    return "\n".join(lines)
