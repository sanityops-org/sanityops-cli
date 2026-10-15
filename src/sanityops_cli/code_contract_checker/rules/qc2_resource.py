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

"""QC-2 Resource Management rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..models import QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult


#: Call names that open files and should be closed or used as context manager.
FILE_OPEN_CALLS = frozenset({"open", "io.open", "builtins.open", "pdfplumber.open"})

#: Call names that create network connections needing close/context manager.
NETWORK_CONN_CALLS = frozenset(
    {
        "http.client.HTTPSConnection",
        "http.client.HTTPConnection",
        "socket.socket",
        "urllib.request.urlopen",
        "aiohttp.ClientSession",
    }
)

#: High-risk operation call names that should be wrapped in try/except.
HIGH_RISK_CALLS = frozenset(
    {
        "open",
        "requests.get",
        "requests.post",
        "urllib.request.urlopen",
        "connect",
        "cursor",
        "execute",
    }
)


def _call_name(node: ast.Call) -> str | None:
    """Return the dotted name of a call target, or None."""
    func = node.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Return a {id(child): parent} map without mutating the AST.

    Avoids modifying nodes in place, which could break AST caching or
    reuse when the same tree is analyzed more than once.
    """
    parent_map: dict[int, ast.AST] = {}
    for child in ast.walk(tree):
        for _, value in ast.iter_fields(child):
            if isinstance(value, ast.AST):
                parent_map[id(value)] = child
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        parent_map[id(item)] = child
    return parent_map


def _is_with_context(node: ast.Call, parent_map: dict[int, ast.AST]) -> bool:
    """Check whether a call is directly used as a `with` context manager."""
    parent = parent_map.get(id(node))
    return isinstance(parent, ast.withitem)


def check_qc_2_1_unclosed_file_handle(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-2.1: Check for unclosed file handles.

    Uses AST to find `open()` calls that are neither used as a `with`
    context manager nor followed by a matching `close()` call.

    Args:
        code: The code snippet to check.
        language: The declared language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    parent_map = _build_parent_map(tree)

    # Collect all names assigned to `close()` calls within the module/function scope.
    closed_vars: set[str] = set()

    class CloseCollector(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr == "close":
                if isinstance(node.func.value, ast.Name):
                    closed_vars.add(node.func.value.id)
            self.generic_visit(node)

    CloseCollector().visit(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in FILE_OPEN_CALLS:
            continue

        # Skip calls used directly as a with context manager.
        if _is_with_context(node, parent_map):
            continue

        # Skip calls that are closed in a finally/other block via close().
        var_name: str | None = None
        parent = parent_map.get(id(node))
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1:
            target = parent.targets[0]
            if isinstance(target, ast.Name):
                var_name = target.id

        if var_name is not None and var_name in closed_vars:
            continue

        defect = QCDefect(
            rule_id=QCRuleID.QC_2_1,
            name="Unclosed File Handle",
            description=(
                f"File opened via '{name}' without 'with' statement or close() call"
                if var_name is None
                else f"File opened as '{var_name}' without 'with' statement or close() call"
            ),
            severity=Severity.P1,
            location=location,
            evidence=ast.get_source_segment(code, node) or node.__class__.__name__,
            fix_suggestion=(
                "Use 'with open(...) as f:' or call f.close()"
                if var_name is None
                else f"Use 'with open(...) as {var_name}:' or call {var_name}.close()"
            ),
            line_number=line_offset + node.lineno,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)


def check_qc_2_2_unreleased_network(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-2.2: Check for unreleased network connections.

    Uses AST to find network connection calls that are neither used as a
    `with` context manager nor followed by a matching `close()` call.

    Args:
        code: The code snippet to check.
        language: The declared language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    parent_map = _build_parent_map(tree)

    closed_vars: set[str] = set()

    class CloseCollector(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr == "close":
                if isinstance(node.func.value, ast.Name):
                    closed_vars.add(node.func.value.id)
            self.generic_visit(node)

    CloseCollector().visit(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in NETWORK_CONN_CALLS:
            continue

        if _is_with_context(node, parent_map):
            continue

        var_name: str | None = None
        parent = parent_map.get(id(node))
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1:
            target = parent.targets[0]
            if isinstance(target, ast.Name):
                var_name = target.id

        if var_name is not None and var_name in closed_vars:
            continue

        defect = QCDefect(
            rule_id=QCRuleID.QC_2_2,
            name="Unreleased Network Connection",
            description=(
                f"Network connection opened via '{name}' without context manager or close()"
                if var_name is None
                else f"Network connection '{var_name}' opened without context manager or close()"
            ),
            severity=Severity.P2,
            location=location,
            evidence=ast.get_source_segment(code, node) or node.__class__.__name__,
            fix_suggestion=(
                "Use 'with ... as conn:' or call conn.close()"
                if var_name is None
                else f"Use 'with ... as {var_name}:' or call {var_name}.close()"
            ),
            line_number=line_offset + node.lineno,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)


def check_qc_2_3_missing_exception_handling(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-2.3: Check for missing exception handling on high-risk operations.

    Uses AST to find high-risk calls (file/network/DB) that are not wrapped
    in a try-except block.

    Args:
        code: The code snippet to check.
        language: The declared language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return

    # Collect line ranges covered by try bodies.
    try_lines: set[int] = set()

    class TryCollector(ast.NodeVisitor):
        def visit_Try(self, node: ast.Try) -> None:
            for stmt in node.body:
                for child in ast.walk(stmt):
                    lineno = getattr(child, "lineno", None)
                    if isinstance(lineno, int):
                        try_lines.add(lineno)
            self.generic_visit(node)

        # Python 3.11+ adds ast.TryStar for `try*` / `except*` syntax.
        # The hasattr guard keeps this file importable on older interpreters,
        # which is why the parameter is annotated as ast.AST: ast.TryStar
        # cannot be referenced in annotations evaluated on Python < 3.11.
        # The method only runs on 3.11+ where the argument is always a
        # real ast.TryStar node.
        if hasattr(ast, "TryStar"):

            def visit_TryStar(self, node: ast.AST) -> None:
                # Runtime-guaranteed ast.TryStar on 3.11+; the ast.AST
                # annotation is a compatibility concession, hence the
                # ignore below.
                for stmt in node.body:  # type: ignore[union-attr]
                    for child in ast.walk(stmt):
                        lineno = getattr(child, "lineno", None)
                        if isinstance(lineno, int):
                            try_lines.add(lineno)
                self.generic_visit(node)

    TryCollector().visit(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in HIGH_RISK_CALLS:
            continue
        if node.lineno in try_lines:
            continue

        defect = QCDefect(
            rule_id=QCRuleID.QC_2_3,
            name="Missing Exception Handling",
            description=f"High-risk operation '{name}' without try-except block",
            severity=Severity.P2,
            location=location,
            evidence=ast.get_source_segment(code, node) or node.__class__.__name__,
            fix_suggestion="Wrap in try-except block to handle potential exceptions",
            line_number=line_offset + node.lineno,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)
