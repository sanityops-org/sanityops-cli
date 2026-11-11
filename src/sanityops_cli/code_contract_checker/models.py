"""Data models for Code Contract inspection results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class QCRuleID(StrEnum):
    """Code Contract rule IDs (17-item checklist v2)."""

    QC_0_1 = "QC-0.1"  # Syntax Parsability
    QC_0_2 = "QC-0.2"  # Language Declaration
    QC_0_3 = "QC-0.3"  # Structural Completeness
    QC_0_4 = "QC-0.4"  # Fence Integrity
    QC_0_5 = "QC-0.5"  # Language-Content Mismatch
    QC_1_1 = "QC-1.1"  # Undefined Name Reference
    QC_1_2 = "QC-1.2"  # Invalid Import
    QC_1_3 = "QC-1.3"  # Deprecated API Usage
    QC_1_4 = "QC-1.4"  # Type Mismatch
    QC_2_1 = "QC-2.1"  # Unclosed File Handle
    QC_2_2 = "QC-2.2"  # Unreleased Network Connection
    QC_2_3 = "QC-2.3"  # Missing Exception Handling
    QC_3_1 = "QC-3.1"  # Unused Import
    QC_3_2 = "QC-3.2"  # Missing Import
    QC_3_3 = "QC-3.3"  # Hardcoded Demo Value
    QC_4_1 = "QC-4.1"  # Snippet-Artifact Declaration Mismatch
    QC_4_2 = "QC-4.2"  # Snippet-Body Version/API Drift


class Severity(StrEnum):
    """Defect severity levels."""

    P0 = "P0"  # Blocking
    P1 = "P1"  # Warning
    P2 = "P2"  # Advisory


class GateResult(StrEnum):
    """Quality gate outcome for an inspection result."""

    PASS = "PASS"
    FAIL = "FAIL"


class DefectStatus(StrEnum):
    """Adjudication status of a QC defect (design §7.3).

    - DEFINITIVE: program rule verdict; counts toward the gate.
    - CANDIDATE: hybrid pre-screen hit awaiting model confirmation;
      never triggers FAIL by itself.
    - NOT_EXECUTED: rule could not adjudicate for lack of context
      (dependency list / API version library); never triggers FAIL.
    """

    DEFINITIVE = "Definitive"
    CANDIDATE = "Candidate"
    NOT_EXECUTED = "Not Executed"


@dataclass
class QCDefect:
    """A single Code Contract defect."""

    rule_id: QCRuleID
    name: str
    description: str
    severity: Severity
    location: str  # JSONPath-like location, e.g., "$.steps[0].code"
    evidence: str  # The problematic code snippet or text
    fix_suggestion: str | None = None
    line_number: int | None = None
    artifact_path: str | None = None  # Source file path
    artifact_type: str | None = None  # "skill", "tool", "prompt"
    language: str | None = None  # Code language, e.g., "python"
    status: DefectStatus = DefectStatus.DEFINITIVE
    model_prompt: str | None = None  # Confirmation question for hybrid candidates


@dataclass
class QCArtifactResult:
    """Inspection result for a single artifact."""

    artifact_type: str  # "skill", "tool", "prompt"
    artifact_path: str
    artifact_name: str
    defects: list[QCDefect] = field(default_factory=list)
    checked_at: str = ""  # ISO timestamp
    #: rule_id -> reason the rule could not fully adjudicate (design §7.2)
    not_executed_rules: dict[str, str] = field(default_factory=dict)

    @property
    def total_defects(self) -> int:
        return len(self.defects)

    @property
    def definitive_defects(self) -> list[QCDefect]:
        return [d for d in self.defects if d.status == DefectStatus.DEFINITIVE]

    @property
    def p0_count(self) -> int:
        return sum(
            1
            for d in self.defects
            if d.severity == Severity.P0 and d.status == DefectStatus.DEFINITIVE
        )

    @property
    def p1_count(self) -> int:
        return sum(
            1
            for d in self.defects
            if d.severity == Severity.P1 and d.status == DefectStatus.DEFINITIVE
        )

    @property
    def p2_count(self) -> int:
        return sum(
            1
            for d in self.defects
            if d.severity == Severity.P2 and d.status == DefectStatus.DEFINITIVE
        )

    @property
    def candidate_count(self) -> int:
        return sum(1 for d in self.defects if d.status == DefectStatus.CANDIDATE)

    @property
    def not_executed_count(self) -> int:
        return sum(1 for d in self.defects if d.status == DefectStatus.NOT_EXECUTED)


@dataclass
class QCInspectionResult:
    """Complete Code Contract inspection result."""

    skills: list[QCArtifactResult] = field(default_factory=list)
    tools: list[QCArtifactResult] = field(default_factory=list)
    prompts: list[QCArtifactResult] = field(default_factory=list)
    inspection_time_seconds: float = 0.0

    @property
    def all_artifacts(self) -> list[QCArtifactResult]:
        return self.skills + self.tools + self.prompts

    @property
    def total_artifacts(self) -> int:
        return len(self.all_artifacts)

    @property
    def total_defects(self) -> int:
        return sum(r.total_defects for r in self.all_artifacts)

    @property
    def p0_count(self) -> int:
        return sum(r.p0_count for r in self.all_artifacts)

    @property
    def p1_count(self) -> int:
        return sum(r.p1_count for r in self.all_artifacts)

    @property
    def p2_count(self) -> int:
        return sum(r.p2_count for r in self.all_artifacts)

    @property
    def candidate_count(self) -> int:
        return sum(r.candidate_count for r in self.all_artifacts)

    @property
    def not_executed_count(self) -> int:
        return sum(r.not_executed_count for r in self.all_artifacts)

    @property
    def not_executed_rule_ids(self) -> list[str]:
        """Distinct rule IDs that could not fully adjudicate, sorted."""
        return sorted({rid for r in self.all_artifacts for rid in r.not_executed_rules})

    @property
    def gate_result(self) -> GateResult:
        """Gate result: FAIL only on Definitive P0 defects (design §7.3).

        Hybrid candidates and not-executed markers never block the gate.
        """
        return GateResult.FAIL if self.p0_count > 0 else GateResult.PASS


# Rule metadata — 17-item checklist v2 (vendored at
# skills/code-contract-checklist.v2.md §2). ``name``/``severity`` are verbatim
# from the checklist index; ``engine`` mirrors the checklist's engine column
# (Automated / Semi-automated / Pattern match; QC-0.x has no engine column in
# the checklist and follows design §7.1's program/hybrid split).
# ``hybrid`` marks the four pre-screen→model-confirm items.
RULE_DEFINITIONS: dict[QCRuleID, dict[str, Any]] = {
    QCRuleID.QC_0_1: {
        "name": "Syntax Parsability",
        "description": "Code snippet parses as valid syntax for its declared language",
        "severity": Severity.P0,
        "method": "AST parsing",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_0_2: {
        "name": "Language Declaration",
        "description": "Code block has explicit language identifier",
        "severity": Severity.P1,
        "method": "Markdown code block detection",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_0_3: {
        "name": "Structural Completeness",
        "description": "Code snippet is complete enough for standalone parsing",
        "severity": Severity.P1,
        "method": "AST parsing",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_0_4: {
        "name": "Fence Integrity",
        "description": "Markdown fences open/close with matching backtick runs; no unclosed fence",
        "severity": Severity.P1,
        "method": "Fence state machine",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_0_5: {
        "name": "Language-Content Mismatch",
        "description": "Declared fence language conflicts with the snippet's content profile",
        "severity": Severity.P2,
        "method": "Keyword-profile pre-screen",
        "engine": "Semi-automated",
        "hybrid": True,
    },
    QCRuleID.QC_1_1: {
        "name": "Undefined Name Reference",
        "description": "Uses class/function/variable not defined in snippet or standard library",
        "severity": Severity.P1,
        "method": "AST parsing + name resolution",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_1_2: {
        "name": "Invalid Import",
        "description": "Imports a module unknown to stdlib table and declared dependencies",
        "severity": Severity.P2,
        "method": "Import table cross-check",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_1_3: {
        "name": "Deprecated API Usage",
        "description": "Calls an API deprecated/removed in the referenced major platform",
        "severity": Severity.P2,
        "method": "Top-N deprecated pattern pre-screen",
        "engine": "Semi-automated",
        "hybrid": True,
    },
    QCRuleID.QC_1_4: {
        "name": "Type Mismatch",
        "description": "Function argument types clearly incompatible",
        "severity": Severity.P2,
        "method": "Type inference from literals",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_2_1: {
        "name": "Unclosed File Handle",
        "description": "File opened without corresponding close or with statement",
        "severity": Severity.P1,
        "method": "Pattern match",
        "engine": "Pattern match",
        "hybrid": False,
    },
    QCRuleID.QC_2_2: {
        "name": "Unreleased Network Connection",
        "description": "HTTP/socket connection opened without explicit close or context manager",
        "severity": Severity.P2,
        "method": "Pattern match",
        "engine": "Pattern match",
        "hybrid": False,
    },
    QCRuleID.QC_2_3: {
        "name": "Missing Exception Handling",
        "description": "High-risk operation without try-catch",
        "severity": Severity.P2,
        "method": "Pattern match",
        "engine": "Pattern match",
        "hybrid": False,
    },
    QCRuleID.QC_3_1: {
        "name": "Unused Import",
        "description": "Module imported but never referenced",
        "severity": Severity.P2,
        "method": "AST import/usage cross-check",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_3_2: {
        "name": "Missing Import",
        "description": "Module referenced but never imported",
        "severity": Severity.P1,
        "method": "AST import/usage cross-check",
        "engine": "Automated",
        "hybrid": False,
    },
    QCRuleID.QC_3_3: {
        "name": "Hardcoded Demo Value",
        "description": "Uses placeholder/demo values that may be mistaken for production",
        "severity": Severity.P2,
        "method": "Pattern match",
        "engine": "Pattern match",
        "hybrid": False,
    },
    QCRuleID.QC_4_1: {
        "name": "Snippet-Artifact Declaration Mismatch",
        "description": "Snippet parameter names conflict with the owning artifact's declared schema",
        "severity": Severity.P1,
        "method": "Owner-schema cross-check pre-screen",
        "engine": "Semi-automated",
        "hybrid": True,
    },
    QCRuleID.QC_4_2: {
        "name": "Snippet-Body Version/API Drift",
        "description": "Snippet contradicts the owning artifact's stated version/API",
        "severity": Severity.P2,
        "method": "Version-pin/API drift pre-screen",
        "engine": "Semi-automated",
        "hybrid": True,
    },
}

#: Hybrid rules require model confirmation; program rules never emit Candidates.
HYBRID_RULE_IDS: frozenset[QCRuleID] = frozenset(
    rid for rid, meta in RULE_DEFINITIONS.items() if meta["hybrid"]
)
