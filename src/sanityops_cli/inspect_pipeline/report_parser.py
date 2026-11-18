"""Resolve the CLI summary from report findings, with legacy fallbacks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

TAIL_START = "<!-- inspect-summary -->"
TAIL_END = "<!-- /inspect-summary -->"
STAGE_SECTIONS = tuple("ABCDEFG")

#: Severity → sort rank.
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}

#: module → stage mapping (used to guess the stage when recomputing).
MODULE_STAGE = {
    "QD-P": "A",
    "QD-S": "A",
    "QD-T": "A",
    "QC": "A",
    "QD-PS": "B",
    "QD-PT": "B",
    "QD-ST": "B",
    "QD-SS": "B",
    "QD-TT": "B",
    "QD-CYC": "B",
    "QD-PM": "D",
    "EX": "E",
    "AS-FM": "F",
}

#: Module vocabulary from the contract appendix.
KNOWN_MODULES = set(MODULE_STAGE)

_MAX_DESCRIPTION = 120

#: Best-effort line pattern when the tail JSON is missing: a severity next to
#: a module/rule id in a report section line.
_MODULE_PATTERN = "|".join(re.escape(module) for module in sorted(KNOWN_MODULES))
_SECTION_FINDING_RE = re.compile(rf"\b(P0|P1|P2)\b[^:\n]*?\b(?P<module>{_MODULE_PATTERN})(?![A-Z])")
_SKIPPED_STAGE_RE = re.compile(
    r"^(?:Stage [A-G]\s*[:—-]\s*)?(?:not executed\b|skipped\b|未执行)", re.IGNORECASE
)


@dataclass
class ParsedSummary:
    """Fail-closed summary of one inspection run."""

    status: str  # "completed" | "partial" | "failed"
    counts: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    stages: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: str = "none"  # "parts" | "tail" | "sections" | "none"
    #: Stages the report tool recorded as never emitted (CLI-recorded reality,
    #: §6.3) — drives the strict stage-completeness gate (design §9).
    missing_stages: list[str] = field(default_factory=list)
    counts_partial: bool = False
    unstructured_stages: list[str] = field(default_factory=list)

    @property
    def inspect_p0(self) -> int:
        return int(self.counts.get("inspect", {}).get("p0", 0))

    def stage_status(self, stage: str) -> str:
        if stage in self.missing_stages:
            return "not received"
        status = self.stages.get(stage, "status unavailable")
        if stage in self.unstructured_stages:
            return f"{status} (findings incomplete)"
        return status


def extract_tail_block(tail_text: str) -> str | None:
    """Return the raw tail JSON block, or None when absent/malformed."""
    if not tail_text:
        return None
    start = tail_text.find(TAIL_START)
    if start == -1:
        return None
    end = tail_text.find(TAIL_END, start)
    if end == -1:
        return None
    return tail_text[start + len(TAIL_START) : end].strip()


def parse_summary(
    tail_text: str,
    section_parts: dict[str, list[str]],
    missing_stages: list[str] | None = None,
    *,
    part_findings: list[dict] | None = None,
    unstructured_stages: list[str] | None = None,
) -> ParsedSummary:
    """Count structured report parts, legacy tail findings, or scanned Markdown."""
    missing_stages = missing_stages or []
    unstructured_stages = unstructured_stages or []
    warnings: list[str] = []
    tail_raw = extract_tail_block(tail_text)
    tail: dict = {}
    if tail_raw is not None:
        try:
            decoded = json.loads(tail_raw)
            if not isinstance(decoded, dict):
                raise ValueError("expected a JSON object")
            tail = decoded
        except ValueError as exc:
            warnings.append(f"summary block malformed ({exc})")
    else:
        warnings.append("summary block missing")

    legacy_findings = tail.get("findings")
    warning_count = len(warnings)
    if part_findings is not None:
        source = "parts"
        findings = _normalize_findings(part_findings, warnings)
    elif isinstance(legacy_findings, list):
        source = "tail"
        findings = _normalize_findings(legacy_findings, warnings)
    elif section_parts:
        source = "sections"
        warnings.append("structured findings unavailable; counts estimated from report sections")
        findings = _findings_from_sections(section_parts)
    else:
        source = "none"
        findings = []

    counts = counts_from_findings(findings)
    counts_partial = bool(
        missing_stages
        or unstructured_stages
        or source in {"sections", "none"}
        or len(warnings) > warning_count
    )
    counts_partial |= tail.get("counts_partial") is True
    declared = tail.get("counts")
    if isinstance(declared, dict) and declared and declared != counts:
        warnings.append(
            f"counts inconsistent: agent declared {format_counts(declared)} · "
            f"recorded findings {format_counts(counts)}"
        )
        counts_partial |= source != "parts"
    if unstructured_stages:
        warnings.append(
            f"structured findings missing from report parts in stages {', '.join(unstructured_stages)}"
        )

    claimed_status = tail.get("status", "completed")
    status = "completed"
    if source == "none" or claimed_status == "failed":
        status = "failed"
    elif missing_stages or unstructured_stages or claimed_status != "completed":
        status = "partial"
    if claimed_status not in ("completed", "partial"):
        warnings.append(f"agent reported status={claimed_status}")

    stages = _stage_statuses(section_parts, tail.get("stages"), missing_stages)
    return ParsedSummary(
        status=status,
        counts=counts,
        findings=findings,
        stages=stages,
        warnings=warnings,
        source=source,
        missing_stages=missing_stages,
        counts_partial=counts_partial,
        unstructured_stages=unstructured_stages,
    )


def _stage_statuses(
    section_parts: dict[str, list[str]], claimed: object, missing_stages: list[str]
) -> dict[str, str]:
    stages = {
        stage: str(claimed[stage])
        for stage in STAGE_SECTIONS
        if isinstance(claimed, dict) and isinstance(claimed.get(stage), str)
    }
    for stage in STAGE_SECTIONS:
        if stage in missing_stages:
            stages[stage] = "NOT RECEIVED — agent did not emit this stage"
        elif stage not in stages and (parts := section_parts.get(stage)):
            lines = [line.strip(" #*\t") for line in parts[0].splitlines() if line.strip()]
            skipped = next((line for line in lines[:2] if _SKIPPED_STAGE_RE.match(line)), "")
            stages[stage] = skipped or "received (status unavailable)"
    return stages


def format_severities(bucket: object) -> str:
    values = bucket if isinstance(bucket, dict) else {}
    return "  ".join(
        f"{severity}: {values.get(severity.lower(), '?')}" for severity in SEVERITY_RANK
    )


def format_counts(counts: dict) -> str:
    return (
        f"Inspect {format_severities(counts.get('inspect'))} / "
        f"Explicit {format_severities(counts.get('risk_explicit'))}"
    )


def _empty_counts() -> dict:
    return {
        "inspect": {"p0": 0, "p1": 0, "p2": 0},
        "risk_explicit": {"p0": 0, "p1": 0, "p2": 0},
    }


def counts_from_findings(findings: list[dict]) -> dict:
    counts = _empty_counts()
    for finding in findings:
        severity = str(finding.get("severity", "")).upper()
        if severity not in SEVERITY_RANK:
            continue
        module = str(finding.get("module", ""))
        bucket = "risk_explicit" if module == "EX" else "inspect"
        key = severity.lower()
        counts[bucket][key] = counts[bucket].get(key, 0) + 1
    return counts


def _normalize_findings(findings: list, warnings: list[str]) -> list[dict]:
    normalized: list[dict] = []
    for item in findings:
        if not isinstance(item, dict):
            warnings.append("dropping non-object tail finding")
            continue
        entry = {
            "stage": str(item.get("stage", "")),
            "module": str(item.get("module", "")),
            "artifact": item.get("artifact", ""),
            "id": str(item.get("id", "")),
            "severity": str(item.get("severity", "")).upper(),
            "description": str(item.get("description", ""))[:_MAX_DESCRIPTION],
        }
        if entry["severity"] not in SEVERITY_RANK:
            warnings.append(f"dropping finding with unknown severity: {entry['severity']!r}")
            continue
        normalized.append(entry)
    return normalized


def _findings_from_sections(section_parts: dict[str, list[str]]) -> list[dict]:
    """Best-effort severity/module scan over the section markdown."""
    findings: list[dict] = []
    for section in sorted(section_parts):
        for part in section_parts[section]:
            for line in part.splitlines():
                match = _SECTION_FINDING_RE.search(line)
                if not match:
                    continue
                module = match.group("module")
                severity = match.group(1)
                line = line.strip()
                findings.append(
                    {
                        "stage": MODULE_STAGE.get(module, section),
                        "module": module,
                        "artifact": "",
                        "id": _extract_id(line, module),
                        "severity": severity,
                        "description": re.sub(r"[*_`|]", "", line)[:_MAX_DESCRIPTION],
                    }
                )
    return findings


def _extract_id(line: str, module: str) -> str:
    match = re.search(rf"{re.escape(module)}[-\s]?\d+(?:\.\d+)*", line)
    if match:
        return match.group(0).replace(" ", "-")
    return module
