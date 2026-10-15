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

"""QC-0 Baseline Compliance rules - entry gate checks."""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from ..models import QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult


# Language identifier patterns for Markdown code blocks
# Trailing newline is optional so code blocks at end of file are still matched.
CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\s*\n(.*?)```(?:\n|$)", re.DOTALL)

# Language aliases mapping
LANGUAGE_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "sh": "bash",
    "shell": "bash",
    "yml": "yaml",
    "json": "json",
}

# Python keywords and builtins treated as always-defined names.
PYTHON_KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)

PYTHON_BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "complex",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "exec",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "help",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
        # Common exceptions
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "RuntimeError",
        "StopIteration",
        "NotImplementedError",
        "FileNotFoundError",
        "IOError",
        "OSError",
        "ImportError",
        "ModuleNotFoundError",
        "BaseException",
        "ArithmeticError",
        "LookupError",
    }
)

# Common standard library modules
PYTHON_STDLIB = frozenset(
    {
        "abc",
        "argparse",
        "asyncio",
        "base64",
        "binascii",
        "code",
        "codeop",
        "collections",
        "concurrent",
        "configparser",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "email",
        "enum",
        "filecmp",
        "fnmatch",
        "fractions",
        "functools",
        "getopt",
        "glob",
        "hashlib",
        "hmac",
        "html",
        "http",
        "imaplib",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "multiprocessing",
        "optparse",
        "os",
        "pathlib",
        "pdb",
        "pickle",
        "poplib",
        "pprint",
        "random",
        "re",
        "secrets",
        "shelve",
        "shutil",
        "smtplib",
        "socket",
        "sqlite3",
        "statistics",
        "string",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "threading",
        "time",
        "traceback",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "xml",
        "xmlrpc",
        "yaml",
    }
)


def check_qc_0_1_syntax_parsability(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-0.1: Check if code snippet parses as valid syntax.

    Args:
        code: The code snippet to check.
        language: The declared language (e.g., "python").
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        # Only Python is supported for AST parsing currently
        return

    try:
        ast.parse(code)
    except SyntaxError as e:
        defect = QCDefect(
            rule_id=QCRuleID.QC_0_1,
            name="Syntax Parsability",
            description=f"Code snippet has syntax error: {e.msg}",
            severity=Severity.P0,
            location=location,
            evidence=code[:200] if len(code) > 200 else code,
            fix_suggestion=f"Fix syntax error at line {e.lineno}: {e.msg}",
            line_number=(line_offset + (e.lineno or 1)) if e.lineno else line_offset + 1,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)


def check_qc_0_2_language_declaration(
    code_block_lang: str | None,
    artifact_result: QCArtifactResult,
    location: str,
    line_number: int,
) -> None:
    """QC-0.2: Check if code block has explicit language identifier.

    Args:
        code_block_lang: The language identifier from the code block fence.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_number: Line number of the code block.
    """
    if not code_block_lang or not code_block_lang.strip():
        defect = QCDefect(
            rule_id=QCRuleID.QC_0_2,
            name="Language Declaration",
            description="Code block has no explicit language identifier",
            severity=Severity.P1,
            location=location,
            evidence="```",  # Empty language identifier
            fix_suggestion="Add language identifier after opening backticks (e.g., ```python)",
            line_number=line_number,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
        )
        artifact_result.defects.append(defect)


def check_qc_0_3_structural_completeness(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-0.3: Check if code snippet is structurally complete.

    Detects:
    - Truncated function bodies with `...`
    - Missing closing brackets/parentheses
    - Incomplete statements

    Args:
        code: The code snippet to check.
        language: The declared language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    # Check for truncation indicators
    truncation_patterns = [
        (r"def\s+\w+\([^)]*\):\s*\.\.\.", "Function body truncated with '...'"),
        (r"^\s*\.\.\.\s*$", "Code block contains only '...'"),
        (r"#\s*\.\.\.", "Code contains '# ...' truncation comment"),
    ]

    for pattern, message in truncation_patterns:
        if re.search(pattern, code, re.MULTILINE):
            defect = QCDefect(
                rule_id=QCRuleID.QC_0_3,
                name="Structural Completeness",
                description=message,
                severity=Severity.P1,
                location=location,
                evidence=code[:200] if len(code) > 200 else code,
                fix_suggestion="Provide complete code snippet or mark as pseudo-code",
                line_number=line_offset + 1,
                artifact_path=artifact_result.artifact_path,
                artifact_type=artifact_result.artifact_type,
                language=language,
            )
            artifact_result.defects.append(defect)
            return  # Only report one truncation defect per block

    # Check for unbalanced brackets, ignoring brackets inside strings and comments.
    # Use Python's tokenize to skip string/comment tokens.
    brackets = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []

    import io
    import tokenize

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Code already fails to tokenize - QC-0.1 will catch the syntax error.
        tokens = []

    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        for char in tok.string:
            if char in brackets:
                stack.append(char)
            elif char in brackets.values():
                if not stack:
                    defect = QCDefect(
                        rule_id=QCRuleID.QC_0_3,
                        name="Structural Completeness",
                        description="Unbalanced closing bracket without matching opening bracket",
                        severity=Severity.P1,
                        location=location,
                        evidence=code[:200] if len(code) > 200 else code,
                        fix_suggestion="Add matching opening bracket",
                        line_number=line_offset + 1,
                        artifact_path=artifact_result.artifact_path,
                        artifact_type=artifact_result.artifact_type,
                        language=language,
                    )
                    artifact_result.defects.append(defect)
                    return
                opener = stack.pop()
                if brackets[opener] != char:
                    defect = QCDefect(
                        rule_id=QCRuleID.QC_0_3,
                        name="Structural Completeness",
                        description=f"Mismatched brackets: expected '{brackets[opener]}', got '{char}'",
                        severity=Severity.P1,
                        location=location,
                        evidence=code[:200] if len(code) > 200 else code,
                        fix_suggestion="Fix bracket mismatch",
                        line_number=line_offset + 1,
                        artifact_path=artifact_result.artifact_path,
                        artifact_type=artifact_result.artifact_type,
                        language=language,
                    )
                    artifact_result.defects.append(defect)
                    return

    if stack:
        defect = QCDefect(
            rule_id=QCRuleID.QC_0_3,
            name="Structural Completeness",
            description=f"Unclosed bracket(s): {', '.join(stack)}",
            severity=Severity.P1,
            location=location,
            evidence=code[:200] if len(code) > 200 else code,
            fix_suggestion="Add closing brackets",
            line_number=line_offset + 1,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)


def extract_code_blocks(
    content: str,
    artifact_result: QCArtifactResult,
    location_prefix: str = "$",
) -> list[tuple[str, str, int]]:
    """Extract all code blocks from content with their locations.

    Args:
        content: The markdown content to extract from.
        artifact_result: Artifact result for QC-0.2 checks.
        location_prefix: Prefix for location paths.

    Returns:
        List of (code, language, line_number) tuples.
    """
    blocks: list[tuple[str, str, int]] = []

    for match in CODE_BLOCK_PATTERN.finditer(content):
        lang = match.group(1).strip() if match.group(1) else ""
        code = match.group(2)

        # Find the line number of the opening fence
        # Count newlines before the match position
        line_number = content[: match.start()].count("\n") + 1

        # Normalize language
        normalized_lang = LANGUAGE_ALIASES.get(lang.lower(), lang.lower())

        # QC-0.2: Check language declaration
        check_qc_0_2_language_declaration(
            lang or None,
            artifact_result,
            f"{location_prefix}.code_blocks[{len(blocks)}]",
            line_number,
        )

        if normalized_lang:
            blocks.append((code, normalized_lang, line_number))

    return blocks
