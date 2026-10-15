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

"""Data models for Code Contract inspection results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class QCRuleID(StrEnum):
    """Code Contract rule IDs."""

    QC_0_1 = "QC-0.1"  # Syntax Parsability
    QC_0_2 = "QC-0.2"  # Language Declaration
    QC_0_3 = "QC-0.3"  # Structural Completeness
    QC_1_1 = "QC-1.1"  # Undefined Name Reference
    QC_1_4 = "QC-1.4"  # Type Mismatch
    QC_2_1 = "QC-2.1"  # Unclosed File Handle
    QC_2_2 = "QC-2.2"  # Unreleased Network Connection
    QC_2_3 = "QC-2.3"  # Missing Exception Handling
    QC_3_1 = "QC-3.1"  # Unused Import
    QC_3_2 = "QC-3.2"  # Missing Import
    QC_3_3 = "QC-3.3"  # Hardcoded Demo Value


class Severity(StrEnum):
    """Defect severity levels."""

    P0 = "P0"  # Blocking
    P1 = "P1"  # Warning
    P2 = "P2"  # Advisory


class GateResult(StrEnum):
    """Quality gate outcome for an inspection result."""

    PASS = "PASS"
    FAIL = "FAIL"


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


@dataclass
class QCArtifactResult:
    """Inspection result for a single artifact."""

    artifact_type: str  # "skill", "tool", "prompt"
    artifact_path: str
    artifact_name: str
    defects: list[QCDefect] = field(default_factory=list)
    checked_at: str = ""  # ISO timestamp

    @property
    def total_defects(self) -> int:
        return len(self.defects)

    @property
    def p0_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.P0)

    @property
    def p1_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.P1)

    @property
    def p2_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.P2)


@dataclass
class QCInspectionResult:
    """Complete Code Contract inspection result."""

    skills: list[QCArtifactResult] = field(default_factory=list)
    tools: list[QCArtifactResult] = field(default_factory=list)
    prompts: list[QCArtifactResult] = field(default_factory=list)
    inspection_time_seconds: float = 0.0

    @property
    def total_artifacts(self) -> int:
        return len(self.skills) + len(self.tools) + len(self.prompts)

    @property
    def total_defects(self) -> int:
        return sum(r.total_defects for r in self.skills + self.tools + self.prompts)

    @property
    def p0_count(self) -> int:
        return sum(r.p0_count for r in self.skills + self.tools + self.prompts)

    @property
    def p1_count(self) -> int:
        return sum(r.p1_count for r in self.skills + self.tools + self.prompts)

    @property
    def p2_count(self) -> int:
        return sum(r.p2_count for r in self.skills + self.tools + self.prompts)

    @property
    def gate_result(self) -> GateResult:
        """Gate result: FAIL if any P0 defects, otherwise PASS."""
        return GateResult.FAIL if self.p0_count > 0 else GateResult.PASS


# Rule metadata
RULE_DEFINITIONS: dict[QCRuleID, dict[str, Any]] = {
    QCRuleID.QC_0_1: {
        "name": "Syntax Parsability",
        "description": "Code snippet parses as valid syntax for its declared language",
        "severity": Severity.P0,
        "method": "AST parsing",
    },
    QCRuleID.QC_0_2: {
        "name": "Language Declaration",
        "description": "Code block has explicit language identifier",
        "severity": Severity.P1,
        "method": "Markdown code block detection",
    },
    QCRuleID.QC_0_3: {
        "name": "Structural Completeness",
        "description": "Code snippet is complete enough for standalone parsing",
        "severity": Severity.P1,
        "method": "AST parsing",
    },
    QCRuleID.QC_1_1: {
        "name": "Undefined Name Reference",
        "description": "Uses class/function/variable not defined in snippet or standard library",
        "severity": Severity.P1,
        "method": "AST parsing + name resolution",
    },
    QCRuleID.QC_1_4: {
        "name": "Type Mismatch",
        "description": "Function argument types clearly incompatible",
        "severity": Severity.P2,
        "method": "Type inference from literals",
    },
    QCRuleID.QC_2_1: {
        "name": "Unclosed File Handle",
        "description": "File opened without corresponding close or with statement",
        "severity": Severity.P1,
        "method": "Pattern match",
    },
    QCRuleID.QC_2_2: {
        "name": "Unreleased Network Connection",
        "description": "HTTP/socket connection opened without explicit close or context manager",
        "severity": Severity.P2,
        "method": "Pattern match",
    },
    QCRuleID.QC_2_3: {
        "name": "Missing Exception Handling",
        "description": "High-risk operation without try-catch",
        "severity": Severity.P2,
        "method": "Pattern match",
    },
    QCRuleID.QC_3_1: {
        "name": "Unused Import",
        "description": "Module imported but never referenced",
        "severity": Severity.P2,
        "method": "Automated",
    },
    QCRuleID.QC_3_2: {
        "name": "Missing Import",
        "description": "Module referenced but never imported",
        "severity": Severity.P1,
        "method": "Automated",
    },
    QCRuleID.QC_3_3: {
        "name": "Hardcoded Demo Value",
        "description": "Uses placeholder/demo values that may be mistaken for production",
        "severity": Severity.P2,
        "method": "Pattern match",
    },
}
