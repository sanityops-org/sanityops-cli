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

"""QC-3 Code Pattern rules."""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from ..models import QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult

from .qc0_baseline import PYTHON_STDLIB

# Weak credential patterns
WEAK_CREDENTIAL_PATTERNS = [
    (re.compile(r'password\s*=\s*["\'](\d{4,6})["\']'), "short numeric password"),
    (re.compile(r'password\s*=\s*["\']123{2,}["\']'), "repeated digits"),
    (re.compile(r'password\s*=\s*["\'](password|passwd|pwd)["\']', re.I), "common password"),
    (re.compile(r'api_key\s*=\s*["\']xxx["\']'), "placeholder value"),
    (re.compile(r'api_key\s*=\s*["\']your[_-]?api[_-]?key["\']', re.I), "placeholder value"),
    (re.compile(r'(secret|token)\s*=\s*["\']xxx["\']'), "placeholder value"),
    (re.compile(r'(secret|token)\s*=\s*["\']changeme["\']', re.I), "placeholder value"),
]


def check_qc_3_1_unused_import(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-3.1: Check for unused imports.

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

    # Collect all imports
    imported: dict[str, tuple[str, int]] = {}  # name -> (module_or_alias, line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported[name.split(".")[0]] = (alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported[name] = (alias.name, node.lineno)

    # Find all used names
    used_names: set[str] = set()

    class NameCollector(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            # For module.attr, collect the module name
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)
            self.generic_visit(node)

    NameCollector().visit(tree)

    # Find unused imports
    for name, (module, line) in imported.items():
        if name not in used_names:
            defect = QCDefect(
                rule_id=QCRuleID.QC_3_1,
                name="Unused Import",
                description=f"Module '{module}' imported but never used",
                severity=Severity.P2,
                location=location,
                evidence=f"import {module}" if name == module else f"import {module} as {name}",
                fix_suggestion=f"Remove unused import: {module}",
                line_number=line_offset + line,
                artifact_path=artifact_result.artifact_path,
                artifact_type=artifact_result.artifact_type,
                language=language,
            )
            artifact_result.defects.append(defect)


def check_qc_3_2_missing_import(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-3.2: Check for missing imports.

    Detects usage of modules that are not imported.

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

    # Collect all imports
    imported_modules: set[str] = set()
    imported_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name)

    # Collect all locally defined names (function parameters, local variables, etc.)
    # to avoid false positives
    class LocalNamesCollector(ast.NodeVisitor):
        def __init__(self):
            self.local_names: set[str] = set()

        def _collect_assignment_targets(self, targets: list[ast.expr]) -> None:
            for target in targets:
                if isinstance(target, ast.Name):
                    self.local_names.add(target.id)
                elif isinstance(target, ast.Tuple | ast.List):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            self.local_names.add(elt.id)

        def _collect_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            """Record all parameter names of the function as local names."""
            for arg in node.args.args:
                self.local_names.add(arg.arg)
            for arg in node.args.posonlyargs:
                self.local_names.add(arg.arg)
            for arg in node.args.kwonlyargs:
                self.local_names.add(arg.arg)
            if node.args.vararg:
                self.local_names.add(node.args.vararg.arg)
            if node.args.kwarg:
                self.local_names.add(node.args.kwarg.arg)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._collect_function_signature(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            # Same handling as the sync visitor; the union-typed helper
            # makes the shared signature explicit.
            self._collect_function_signature(node)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            self._collect_assignment_targets(node.targets)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name):
                self.local_names.add(node.target.id)
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            if isinstance(node.target, ast.Name):
                self.local_names.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.local_names.add(elt.id)
            self.generic_visit(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            if isinstance(node.target, ast.Name):
                self.local_names.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.local_names.add(elt.id)
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                self.local_names.add(node.name)
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    self.local_names.add(item.optional_vars.id)
            self.generic_visit(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    self.local_names.add(item.optional_vars.id)
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            if isinstance(node.target, ast.Name):
                self.local_names.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.local_names.add(elt.id)
            self.generic_visit(node)

    local_collector = LocalNamesCollector()
    local_collector.visit(tree)

    # Find all attribute accesses that look like module usage
    class ModuleUsageCollector(ast.NodeVisitor):
        def __init__(self):
            self.potential_modules: dict[str, int] = {}  # name -> line

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if isinstance(node.value, ast.Name):
                name = node.value.id
                # Skip if it's imported, a local variable, or a known variable
                if (
                    name not in imported_modules
                    and name not in imported_names
                    and name not in local_collector.local_names
                ):
                    self.potential_modules[name] = node.lineno
            self.generic_visit(node)

    collector = ModuleUsageCollector()
    collector.visit(tree)

    for name, line in collector.potential_modules.items():
        # Check if this looks like a module usage
        if name in PYTHON_STDLIB:
            defect = QCDefect(
                rule_id=QCRuleID.QC_3_2,
                name="Missing Import",
                description=f"Module '{name}' is used but not imported",
                severity=Severity.P1,
                location=location,
                evidence=f"{name}.",
                fix_suggestion=f"Add: import {name}",
                line_number=line_offset + line,
                artifact_path=artifact_result.artifact_path,
                artifact_type=artifact_result.artifact_type,
                language=language,
            )
            artifact_result.defects.append(defect)


def check_qc_3_3_hardcoded_demo_value(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-3.3: Check for hardcoded demo/placeholder values.

    Detects weak credential patterns and placeholder values.

    Args:
        code: The code snippet to check.
        language: The declared language.
        artifact_result: The artifact result to add defects to.
        location: JSONPath-like location of the code block.
        line_offset: Line number offset for the code block.
    """
    if language.lower() not in ("python", "py"):
        return

    lines = code.split("\n")

    for i, line in enumerate(lines):
        # Skip comment-only lines to avoid flagging documentation examples
        # like "# password = 'password'".
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern, pattern_type in WEAK_CREDENTIAL_PATTERNS:
            match = pattern.search(line)
            if match:
                defect = QCDefect(
                    rule_id=QCRuleID.QC_3_3,
                    name="Hardcoded Demo Value",
                    description=f"Detected {pattern_type} in code",
                    severity=Severity.P2,
                    location=location,
                    evidence=line.strip()[:100],
                    fix_suggestion="Replace with secure value or environment variable",
                    line_number=line_offset + i + 1,
                    artifact_path=artifact_result.artifact_path,
                    artifact_type=artifact_result.artifact_type,
                    language=language,
                )
                artifact_result.defects.append(defect)
                break  # Only one defect per line
