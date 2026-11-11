"""QC-1.2 Invalid Import (program, context-gated) and QC-1.3 Deprecated API Usage (hybrid).

Both rules operate with incomplete dependency context (design §7.1):
- QC-1.2 compares imports against the stdlib table plus an optional
  ``declared_dependencies`` list. When that list is unavailable the rule is
  recorded as Not Executed — never FAIL (a unknown module may simply be a
  third-party package).
- QC-1.3 pre-screens a built-in top-N table of deprecated/removed API calls;
  hits become Candidates and the rule declares Not Executed for full
  version-context coverage.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from ..models import DefectStatus, QCDefect, QCRuleID, Severity
from .qc0_baseline import PYTHON_STDLIB

if TYPE_CHECKING:
    from ..models import QCArtifactResult


def _imported_roots(code: str) -> list[str]:
    """Top-level module names imported by the snippet."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.append(node.module.split(".")[0])
    return roots


def check_qc_1_2_invalid_import(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
    *,
    declared_dependencies: list[str] | None = None,
) -> None:
    """QC-1.2: imports must resolve against stdlib or declared dependencies.

    Design §7.1: with no dependency context the rule records Not Executed
    instead of FAIL; only with a provided ``declared_dependencies`` list can
    an unknown import be adjudicated as a Definitive defect.

    Args:
        code: The code snippet to check.
        language: The declared (normalized) language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
        declared_dependencies: Project dependency module names, or None when
            the qc_lint config does not provide them.
    """
    if language.lower() not in ("python", "py"):
        return

    roots = _imported_roots(code)
    if not roots:
        return

    known = PYTHON_STDLIB | {name.lower() for name in (declared_dependencies or [])}
    unknown = sorted({root for root in roots if root.lower() not in known})

    if not unknown:
        return

    if declared_dependencies is None:
        # Dependency context missing → Not Executed, never FAIL (§7.1).
        artifact_result.defects.append(
            QCDefect(
                rule_id=QCRuleID.QC_1_2,
                name="Invalid Import",
                description=(
                    "QC-1.2 not executed — dependency list unavailable; "
                    f"{len(unknown)} import target(s) not in stdlib table"
                ),
                severity=Severity.P2,
                location=location,
                evidence=", ".join(unknown),
                fix_suggestion="Declare project dependencies in qc_lint config to enable QC-1.2",
                line_number=line_offset + 1,
                artifact_path=artifact_result.artifact_path,
                artifact_type=artifact_result.artifact_type,
                language=language,
                status=DefectStatus.NOT_EXECUTED,
            )
        )
        artifact_result.not_executed_rules.setdefault(
            str(QCRuleID.QC_1_2), "dependency list unavailable"
        )
        return

    artifact_result.defects.append(
        QCDefect(
            rule_id=QCRuleID.QC_1_2,
            name="Invalid Import",
            description=f"Import target(s) not in stdlib or declared dependencies: {', '.join(unknown)}",
            severity=Severity.P2,
            location=location,
            evidence=", ".join(unknown),
            fix_suggestion="Fix the module name or declare the dependency",
            line_number=line_offset + 1,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
    )


# Top-N deprecated/removed API patterns (design §7.2). Each entry is
# (regex, platform, note). Hits become Candidates for model confirmation;
# the rule always declares Not Executed for full version-context coverage.
DEPRECATED_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\bimp\.reload\b", "Python 3.12", "imp module removed; use importlib.reload"),
    (r"\bimport\s+imp\b", "Python 3.12", "imp module removed; use importlib"),
    (r"\bdistutils\.", "Python 3.12", "distutils removed; use setuptools/shutil"),
    (r"\.ix\[", "pandas 2.0", "DataFrame.ix removed; use .loc/.iloc"),
    (r"\b(?:df|dataframe)\.append\(", "pandas 2.0", "DataFrame.append removed; use pd.concat"),
    (
        r"\bcollections\.(?:Mapping|Sequence|Iterable|Callable|MutableMapping)\b",
        "Python 3.10",
        "ABCs moved to collections.abc",
    ),
    (r"\btime\.clock\(", "Python 3.8", "time.clock removed; use time.perf_counter"),
    (r"\bgetargspec\(", "Python 3.11", "inspect.getargspec removed; use getfullargspec"),
    (r"@asyncio\.coroutine", "Python 3.11", "decorator removed; use async def"),
    (
        r"\basyncio\.get_event_loop\(\)",
        "Python 3.12",
        "deprecated in async contexts; use async runners",
    ),
    (r"\bunittest\.makeSuite\b", "Python 3.13", "makeSuite removed; use load_tests"),
    (r"\bos\.spawn[lv]?\(", "Python 3.x", "deprecated process API; use subprocess"),
)


def check_qc_1_3_deprecated_api(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-1.3 (hybrid pre-screen): deprecated/removed API calls.

    v1 ships a built-in top-N table (design §7.2) — hits are Candidates, and
    full version-context adjudication is declared Not Executed.

    Args:
        code: The code snippet to check.
        language: The declared (normalized) language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    for pattern, platform, note in DEPRECATED_PATTERNS:
        match = re.search(pattern, code)
        if not match:
            continue
        artifact_result.defects.append(
            QCDefect(
                rule_id=QCRuleID.QC_1_3,
                name="Deprecated API Usage",
                description=f"Possible deprecated API ({platform}): {note}",
                severity=Severity.P2,
                location=location,
                evidence=code[max(0, match.start() - 40) : match.end() + 40],
                fix_suggestion=note,
                line_number=line_offset + 1,
                artifact_path=artifact_result.artifact_path,
                artifact_type=artifact_result.artifact_type,
                language=language,
                status=DefectStatus.CANDIDATE,
                model_prompt=(
                    f"The snippet at {location} uses ``{match.group(0)}``, which matches a "
                    f"known deprecated/removed API ({platform}). Confirm the targeted "
                    f"runtime version and whether a replacement is required."
                ),
            )
        )

    # Partial coverage: v1 has no API version library — declare it (§7.1).
    artifact_result.not_executed_rules.setdefault(
        str(QCRuleID.QC_1_3), "API version library unavailable; top-N pre-screen only"
    )
