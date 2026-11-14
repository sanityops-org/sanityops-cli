"""QC-0.4 Fence Integrity (program) and QC-0.5 Language-Content Mismatch (hybrid).

QC-0.4 runs a fence state machine over raw markdown (checklist v2 §2):
opening/closing backtick runs must match, and no fence may remain open at EOF.
QC-0.5 is a keyword-profile pre-screen whose hits are Candidates awaiting model
confirmation (design §7.3) — it never emits a Definitive verdict.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..models import DefectStatus, QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult

# A fence line: 3+ backticks optionally followed by an info string.
FENCE_LINE_RE = re.compile(r"^(\s*)(`{3,})(.*)$")


def _add_defect(
    artifact_result: QCArtifactResult,
    location: str,
    description: str,
    evidence: str,
    line_number: int,
) -> None:
    artifact_result.defects.append(
        QCDefect(
            rule_id=QCRuleID.QC_0_4,
            name="Fence Integrity",
            description=description,
            severity=Severity.P1,
            location=location,
            evidence=evidence,
            fix_suggestion="Balance the opening and closing ``` runs of the fence",
            line_number=line_number,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
        )
    )


def check_qc_0_4_fence_integrity(
    content: str,
    artifact_result: QCArtifactResult,
    location_prefix: str,
) -> None:
    """QC-0.4: verify every fenced region opens and closes coherently.

    CommonMark semantics: a closing fence must be a line of backticks at least
    as long as the opening run. Detected violations:
    - unclosed fence at EOF
    - a closing fence shorter than the opening run when the opener is the
      common ```` ``` ```` form (the block silently swallows the markdown that
      follows). Shorter backtick-only lines inside a 4+ backtick opener are
      treated as nested fence content, not errors.

    Args:
        content: Raw markdown content to scan.
        artifact_result: The artifact result to add defects to.
        location_prefix: Location prefix, e.g. "$.content".
    """
    fence_index = 0
    open_run = 0
    open_line = 0

    for offset, line in enumerate(content.split("\n"), start=1):
        match = FENCE_LINE_RE.match(line)
        if not match:
            continue

        backticks = len(match.group(2))
        if open_run == 0:
            open_run = backticks
            open_line = offset
        elif backticks >= open_run and not match.group(3).strip("`"):
            # Proper closing fence (>= opener length, backticks only).
            open_run = 0
        elif open_run == 3 and backticks < open_run and not match.group(3).strip("`"):
            # Backtick-only line, but too short: an intended closing fence
            # that CommonMark treats as content — report and close the region
            # at the author's evident intent so the prose after it is not
            # flagged as absorbed.
            fence_index += 1
            _add_defect(
                artifact_result,
                f"{location_prefix}.fences[{fence_index}]",
                "Closing fence has fewer backticks than the opening fence; "
                "the code region is not properly terminated",
                line.strip(),
                offset,
            )
            open_run = 0

    if open_run:
        fence_index += 1
        _add_defect(
            artifact_result,
            f"{location_prefix}.fences[{fence_index}]",
            "Fence opened but never closed before end of file",
            f"``` (opened at line {open_line})",
            open_line,
        )


# Keyword profiles: a snippet "looks like" language L when every marker group
# has at least one hit. QC-0.5 fires when the content matches a profile other
# than the declared language's profile (design §7.2).
_LANGUAGE_PROFILES: dict[str, tuple[tuple[str, ...], ...]] = {
    "python": (
        (r"^\s*def\s+\w+\(", r"^\s*import\s", r"^\s*from\s+\w+\s+import\s"),
        (r"^\s+\w+\s*=\s", r"self\.", r"print\(", r":\s*$"),
    ),
    "bash": (
        (r"\becho\b", r"\bprintf\b"),
        (r"\b(?:apt(?:-get)?|brew|pip3?|npm|curl|wget|mkdir|chmod|sudo)\b", r"\$\(", r"^\s*cd\s"),
    ),
    "javascript": (
        (r"\b(?:const|let|var)\s", r"\bfunction\s", r"=>"),
        (r"\brequire\(", r"\bconsole\.log", r"\bmodule\.exports", r"\bdocument\."),
    ),
    "json": (
        (r'"\w+"\s*:',),
        (r"^\s*\{", r"^\s*\["),
    ),
    "yaml": (
        (r"^\s*[\w.-]+:\s",),
        (r"^\s*-\s", r"^\s{2,}[\w.-]+:\s"),
    ),
    "sql": (
        (r"\bSELECT\b", r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b"),
        (r"\bFROM\b", r"\bWHERE\b", r"\bJOIN\b", r"\bINTO\b"),
    ),
}

_LANGUAGE_ALIASES = {
    "python": "python",
    "py": "python",
    "sh": "bash",
    "shell": "bash",
    "bash": "bash",
    "zsh": "bash",
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "typescript": "javascript",  # TS shares the JS profile markers
    "ts": "javascript",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "sql": "sql",
}


def check_qc_0_5_language_content_mismatch(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-0.5 (hybrid pre-screen): declared language conflicts with content.

    Emits a Candidate only — model confirmation decides (design §7.3).
    Conservative: both the declared language and the mismatched profile must
    have complete keyword-profile hits.

    Args:
        code: The code snippet to check.
        language: The declared (normalized) language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    declared = _LANGUAGE_ALIASES.get(language.lower())
    if declared is None:
        return  # no profile for the declared language → no conflict assertion

    def _matches(profile: str) -> bool:
        return all(
            any(re.search(pattern, code, re.MULTILINE | re.IGNORECASE) for pattern in group)
            for group in _LANGUAGE_PROFILES[profile]
        )

    for profile in _LANGUAGE_PROFILES:
        if profile == declared:
            continue
        # Content strongly matches another language AND does not match the
        # declared language's own profile.
        if _matches(profile) and not _matches(declared):
            artifact_result.defects.append(
                QCDefect(
                    rule_id=QCRuleID.QC_0_5,
                    name="Language-Content Mismatch",
                    description=(f"Block declared as {language} but content matches {profile}"),
                    severity=Severity.P2,
                    location=location,
                    evidence=code[:200],
                    fix_suggestion="Align the fence language tag with the snippet content",
                    line_number=line_offset + 1,
                    artifact_path=artifact_result.artifact_path,
                    artifact_type=artifact_result.artifact_type,
                    language=language,
                    status=DefectStatus.CANDIDATE,
                    model_prompt=(
                        f"The code block at {location} is declared ```{language} but its "
                        f"content profile matches {profile}. Confirm whether the "
                        f"language tag is wrong (and which language the snippet actually is)."
                    ),
                )
            )
            return  # one candidate per block is enough
