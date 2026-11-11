"""QC-4.1 Snippet-Artifact Declaration Mismatch and QC-4.2 Snippet-Body Version/API Drift.

Both are hybrid pre-screens (design §7.2): deterministic hit collection with
Candidate output for model confirmation — never a Definitive verdict.

QC-4.1 compares the snippet's parameter names against the owning tool schema's
declared ``properties``/``required`` (v1 scope: tool artifacts, where the
declaration surface is a machine-readable schema).

QC-4.2 compares version pins and self-flagged API drift between the snippet
and the owning artifact's own prose.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Any

from ..models import DefectStatus, QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult

#: Names that may appear as keyword arguments without being schema properties.
_RESERVED_NAMES = frozenset(
    {
        "self",
        "cls",
        "return",
        "yield",
        "import",
        "from",
        "as",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "with",
        "try",
        "except",
        "finally",
        "lambda",
        "print",
        "len",
        "range",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "open",
        "type",
        "isinstance",
        "getattr",
        "setattr",
        "kwargs",
        "args",
    }
)

_KWARG_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=(?!=)")
_TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_VERSION_PIN_RE = re.compile(r"\b([A-Za-z0-9_.-]+)\s*(==|>=|<=|~=)\s*([0-9][A-Za-z0-9.*-]*)")
_DRIFT_HINT_RE = re.compile(
    r"(?:instead of|replaced by|deprecated|removed|use\s+|prefer)\s+" r"`?([A-Za-z_][\w.]*)\(`?",
    re.IGNORECASE,
)


def _add_candidate(
    artifact_result: QCArtifactResult,
    rule_id: QCRuleID,
    name: str,
    description: str,
    evidence: str,
    location: str,
    line_offset: int,
    language: str | None,
    model_prompt: str,
    fix_suggestion: str,
) -> None:
    artifact_result.defects.append(
        QCDefect(
            rule_id=rule_id,
            name=name,
            description=description,
            severity=Severity.P1 if rule_id == QCRuleID.QC_4_1 else Severity.P2,
            location=location,
            evidence=evidence[:200],
            fix_suggestion=fix_suggestion,
            line_number=line_offset + 1,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
            status=DefectStatus.CANDIDATE,
            model_prompt=model_prompt,
        )
    )


def extract_snippet_param_names(code: str, language: str) -> set[str]:
    """Parameter-like names used by the snippet.

    Combines keyword-argument assignment, ``{{template}}`` placeholders and —
    for Python — function signatures and call keywords from the AST.

    Args:
        code: The code snippet.
        language: The declared (normalized) language.

    Returns:
        Set of candidate parameter names.
    """
    names: set[str] = set()
    names.update(_TEMPLATE_VAR_RE.findall(code))
    names.update(_KWARG_RE.findall(code))

    if language.lower() in ("python", "py"):
        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    args = node.args
                    positional = [*args.posonlyargs, *args.args, *args.kwonlyargs]
                    names.update(arg.arg for arg in positional if arg.arg not in _RESERVED_NAMES)
                elif isinstance(node, ast.Call):
                    names.update(
                        kw.arg for kw in node.keywords if kw.arg and kw.arg not in _RESERVED_NAMES
                    )
    return {name for name in names if name and name not in _RESERVED_NAMES}


def check_qc_4_1_snippet_artifact_mismatch(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
    *,
    owner_context: dict[str, Any] | None = None,
) -> None:
    """QC-4.1 (hybrid pre-screen): snippet params vs owning artifact declarations.

    Fires when the snippet uses parameter names absent from the owner schema's
    ``properties``, or fails to provide ``required`` properties. Candidate only.

    Args:
        code: The code snippet to check.
        language: The declared (normalized) language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
        owner_context: ``{"properties": {name: schema}, "required": [name]}``
            from the owning tool schema; None skips the check.
    """
    if not owner_context:
        return

    properties = owner_context.get("properties") or {}
    if not isinstance(properties, dict) or not properties:
        return
    required = set(owner_context.get("required") or [])

    used = extract_snippet_param_names(code, language)
    if not used:
        return

    unknown = sorted(used - set(properties))
    if unknown:
        _add_candidate(
            artifact_result,
            QCRuleID.QC_4_1,
            "Snippet-Artifact Declaration Mismatch",
            f"Snippet uses parameter name(s) absent from the owning schema: {', '.join(unknown)}",
            f"unknown: {', '.join(unknown)}; declared: {', '.join(sorted(properties))}",
            location,
            line_offset,
            language,
            model_prompt=(
                f"The snippet at {location} uses parameter(s) {unknown} that the owning "
                f"tool schema does not declare (properties: {sorted(properties)}). "
                f"Confirm whether the snippet or the schema is wrong."
            ),
            fix_suggestion="Align snippet parameter names with the schema's properties",
        )

    missing_required = sorted(
        name for name in required if name not in used and not _has_default(properties.get(name))
    )
    if missing_required:
        _add_candidate(
            artifact_result,
            QCRuleID.QC_4_1,
            "Snippet-Artifact Declaration Mismatch",
            f"Snippet omits required property/ies: {', '.join(missing_required)}",
            f"required: {sorted(required)}; snippet used: {sorted(used)}",
            location,
            line_offset,
            language,
            model_prompt=(
                f"The schema marks {missing_required} as required, but the example snippet "
                f"at {location} does not supply them. Confirm whether the example is stale."
            ),
            fix_suggestion="Update the example to include required properties",
        )


def _has_default(prop_schema: Any) -> bool:
    return isinstance(prop_schema, dict) and "default" in prop_schema


def check_qc_4_2_snippet_body_drift(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
    *,
    artifact_body: str | None = None,
) -> None:
    """QC-4.2 (hybrid pre-screen): snippet vs owning artifact's stated versions/API.

    Deterministic signals (Candidate output only):
    - the artifact body pins ``pkg==1.2.3`` while the snippet pins a different
      version of the same package;
    - the artifact prose flags an API as replaced/deprecated ("instead of
      ``pkg.old(``") and the snippet still calls ``pkg.old(``.

    Args:
        code: The code snippet to check.
        language: The declared (normalized) language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
        artifact_body: The owning artifact's non-snippet text; None skips.
    """
    if not artifact_body:
        return

    body_pins = {
        name.lower(): (op, version) for name, op, version in _VERSION_PIN_RE.findall(artifact_body)
    }
    snippet_pins = {
        name.lower(): (op, version) for name, op, version in _VERSION_PIN_RE.findall(code)
    }
    for pkg, (op, version) in snippet_pins.items():
        body_op, body_version = body_pins.get(pkg, (None, None))
        if body_version and body_version != version:
            _add_candidate(
                artifact_result,
                QCRuleID.QC_4_2,
                "Snippet-Body Version/API Drift",
                (
                    f"Snippet pins {pkg}{op}{version} but the owning artifact declares "
                    f"{pkg}{body_op}{body_version}"
                ),
                f"{pkg}=={version} vs {pkg}{body_op}{body_version}",
                location,
                line_offset,
                language,
                model_prompt=(
                    f"Version conflict at {location}: the snippet requires {pkg}{op}{version} "
                    f"while the artifact body states {pkg}{body_op}{body_version}. Confirm "
                    f"which is authoritative."
                ),
                fix_suggestion="Align the snippet's pin with the artifact's declared version",
            )

    body_apis = {match.lower() for match in _DRIFT_HINT_RE.findall(artifact_body)}
    if body_apis:
        snippet_calls = {match.lower() for match in re.findall(r"\b([A-Za-z_][\w.]*)\(", code)}
        drifted = sorted(snippet_calls & body_apis)
        if drifted:
            _add_candidate(
                artifact_result,
                QCRuleID.QC_4_2,
                "Snippet-Body Version/API Drift",
                f"Snippet calls API(s) the artifact body flags for replacement: {', '.join(drifted)}",
                ", ".join(drifted),
                location,
                line_offset,
                language,
                model_prompt=(
                    f"The snippet at {location} calls {drifted}, which the artifact body "
                    f"describes as replaced/deprecated. Confirm the correct replacement."
                ),
                fix_suggestion="Migrate the snippet to the replacement API",
            )
