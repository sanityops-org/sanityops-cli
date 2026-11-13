"""Two-layer IR rendering (design §2 step ③, §6.2).

One IR markdown per input document, written to
``.deeplogic/results/ir/<run-id>/<document>.ir.md`` as a pure audit artifact. The same
serialization feeds the InspectAgent injection payload (§6.2) — rendering
here is the single source for both.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from unicodedata import normalize

from deeplogic_cli.inspect_pipeline.models import (
    ExtractedArtifact,
    ExtractionResult,
)

_UNMATCHED_FILENAME = "_unmatched-references.ir.md"


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


def allocate_run_id(
    results_dir: Path, timestamp: str | None = None, *, reserve: bool = False
) -> str:
    """Allocate a collision-free batch ID shared by the IR folder and report.

    Normally returns ``YYYYMMDD-HHMMSS``; appends ``-2``, ``-3``, ... when a
    matching report file or IR batch directory already exists. With
    ``reserve=True``, create the IR directory atomically to claim the ID.
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
            if reserve:
                try:
                    (ir_root / candidate).mkdir(parents=True)
                except FileExistsError:
                    suffix += 1
                    continue
            return candidate
        suffix += 1


def _filename_key(name: str) -> str:
    """Detect collisions on case-insensitive and Unicode-normalizing filesystems."""
    return normalize("NFD", name).casefold()


def _document_filenames(sources: list[str]) -> dict[str, str]:
    paths = {source: Path(source) for source in sources}
    base_names = {source: f"{path.stem or 'document'}.ir.md" for source, path in paths.items()}
    base_counts = Counter(_filename_key(name) for name in base_names.values())
    parents = {
        source: re.sub(r"[^A-Za-z0-9._-]+", "_", path.parent.name).strip("_") or "document"
        for source, path in paths.items()
    }
    qualified_names = {source: f"{parents[source]}__{base}" for source, base in base_names.items()}
    qualified_counts = Counter(_filename_key(name) for name in qualified_names.values())
    reserved = _filename_key(_UNMATCHED_FILENAME)
    used = set(base_counts) | {reserved}
    names: dict[str, str] = {}
    for source, path in paths.items():
        base = base_names[source]
        key = _filename_key(base)
        if key != reserved and base_counts[key] == 1 and len(os.fsencode(base)) <= 255:
            names[source] = base
            continue

        name = qualified_names[source]
        qualified_key = _filename_key(name)
        if (
            qualified_key in used
            or qualified_counts[qualified_key] > 1
            or len(os.fsencode(name)) > 255
        ):
            digest = sha256(os.fsencode(source)).hexdigest()[:12]
            stem = (path.stem or "document")[:40]
            prefix = f"{parents[source][:40]}__{stem}"
            name = f"{prefix}_{digest}.ir.md"
            index = 2
            while _filename_key(name) in used:
                name = f"{prefix}_{digest}-{index}.ir.md"
                index += 1
        names[source] = name
        used.add(_filename_key(name))
    return names


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
    filenames = _document_filenames(list(grouped))

    target_dir = Path(ir_dir) / run_id if run_id else Path(ir_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for source, artifacts in grouped.items():
        path = target_dir / filenames[source]
        path.write_text(
            render_document_ir(source, artifacts, routed.get(source, [])),
            encoding="utf-8",
        )
        written.append(path)

    if unmatched:
        path = target_dir / _UNMATCHED_FILENAME
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
