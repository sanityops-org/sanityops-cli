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

"""Tail-JSON parsing with the fail-closed ladder (design §6.4).

Never fail open: whatever the agent emitted, the CLI ends up with a
``ParsedSummary`` whose counts are either the (cross-validated) tail JSON
values, a CLI recomputation from the report sections, or a hard ``failed``
status that maps to exit 2.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

TAIL_START = "<!-- inspect-summary -->"
TAIL_END = "<!-- /inspect-summary -->"

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

_MAX_FINDINGS = 20
_MAX_DESCRIPTION = 120

#: Best-effort line pattern when the tail JSON is missing: a severity next to
#: a module/rule id in a report section line.
_SECTION_FINDING_RE = re.compile(
    r"\b(P0|P1|P2)\b[^|:\n]*?\b(?P<module>QD-[A-Z]{1,2}|QC|EX|AS-FM)\b" r"(?P<rest>[^\n]*)"
)


@dataclass
class ParsedSummary:
    """Fail-closed summary of one inspection run."""

    status: str  # "completed" | "failed"
    counts: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    stages: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: str = "none"  # "tail" | "sections" | "none"
    #: Stages the report tool recorded as never emitted (CLI-recorded reality,
    #: §6.3) — drives the strict stage-completeness gate (design §9).
    missing_stages: list[str] = field(default_factory=list)

    @property
    def inspect_p0(self) -> int:
        return int(self.counts.get("inspect", {}).get("p0", 0))


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
) -> ParsedSummary:
    """Apply the fail-closed ladder and return the summary."""
    missing_stages = missing_stages or []
    tail_raw = extract_tail_block(tail_text)

    if tail_raw is not None:
        warnings: list[str] = []
        try:
            tail = json.loads(tail_raw)
        except json.JSONDecodeError as exc:
            tail = None
            warnings.append(f"summary block malformed ({exc}); recomputing from sections")
        if tail is not None:
            return _from_tail(tail, section_parts, missing_stages)
        return _from_sections(section_parts, missing_stages, warnings)

    return _from_sections(
        section_parts,
        missing_stages,
        ["summary block missing; recomputing from sections"],
    )


def _empty_counts() -> dict:
    return {
        "inspect": {"p0": 0, "p1": 0, "p2": 0},
        "risk_explicit": {"p0": 0, "p1": 0, "p2": 0},
    }


def _counts_from_findings(findings: list[dict]) -> dict:
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
    if len(normalized) > _MAX_FINDINGS:
        warnings.append(
            f"tail findings exceed {_MAX_FINDINGS}; keeping the first "
            f"{_MAX_FINDINGS} (severity order not guaranteed)"
        )
        normalized = normalized[:_MAX_FINDINGS]
    return normalized


def _from_tail(
    tail: dict, section_parts: dict[str, list[str]], missing_stages: list[str]
) -> ParsedSummary:
    warnings: list[str] = []
    findings = _normalize_findings(tail.get("findings") or [], warnings)

    recomputed = _counts_from_findings(findings)
    declared = tail.get("counts") or {}
    counts = recomputed
    if declared and declared != recomputed:
        warnings.append("tail counts inconsistent with findings[]; using findings-derived counts")

    status = str(tail.get("status", "completed"))
    stages = dict(tail.get("stages") or {})
    # CLI-recorded stage reality overrides the agent's claims (§6.3).
    for stage in missing_stages:
        stages[stage] = "NOT RECEIVED — agent did not emit this stage"

    if status != "completed":
        warnings.append(f"agent reported status={status}")

    return ParsedSummary(
        status=status,
        counts=counts,
        findings=findings,
        stages=stages,
        warnings=warnings,
        source="tail",
        missing_stages=missing_stages,
    )


def _from_sections(
    section_parts: dict[str, list[str]],
    missing_stages: list[str],
    warnings: list[str],
) -> ParsedSummary:
    findings = _findings_from_sections(section_parts, warnings)
    counts = _counts_from_findings(findings)
    stages = {
        stage: "executed"
        for stage in ("A", "B", "C", "D", "E", "F", "G")
        if stage not in missing_stages
    }
    for stage in missing_stages:
        stages[stage] = "NOT RECEIVED — agent did not emit this stage"

    has_sections = bool(section_parts)
    return ParsedSummary(
        status="completed" if has_sections else "failed",
        counts=counts,
        findings=findings,
        stages=stages,
        warnings=warnings,
        source="sections" if has_sections else "none",
        missing_stages=missing_stages,
    )


def _findings_from_sections(section_parts: dict[str, list[str]], warnings: list[str]) -> list[dict]:
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
                if len(findings) >= _MAX_FINDINGS:
                    warnings.append("section scan capped at 20 findings")
                    return findings
    return findings


def _extract_id(line: str, module: str) -> str:
    match = re.search(rf"{re.escape(module)}[-\s]?\d+(?:\.\d+)*", line)
    if match:
        return match.group(0).replace(" ", "-")
    return module
