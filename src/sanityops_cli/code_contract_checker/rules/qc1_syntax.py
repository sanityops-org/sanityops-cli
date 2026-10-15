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

"""QC-1 Syntax Validation rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..models import QCDefect, QCRuleID, Severity

if TYPE_CHECKING:
    from ..models import QCArtifactResult

from .qc0_baseline import PYTHON_BUILTINS, PYTHON_KEYWORDS, PYTHON_STDLIB


def check_qc_1_1_undefined_name(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-1.1: Check for undefined name references.

    Uses AST to find name references that are:
    - Not defined in the snippet
    - Not in Python builtins
    - Not in standard library (common ones)
    - Not imported

    For complete Python files, this correctly handles:
    - Function/method parameters
    - Loop variables (for, list comprehension, generator)
    - Exception variables (except)
    - With statement context variables
    - Class attributes accessed via self/cls

    Known limitation: definitions are collected into a single flat set
    without nesting scopes, so a name defined inside one function is
    treated as defined everywhere in the snippet (e.g. a variable set in
    ``foo()`` will not be flagged when referenced in ``bar()``). This is
    an intentional trade-off: false negatives are preferred over the
    false positives a heuristic scope stack would produce on fragments.

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
        # QC-0.1 will catch syntax errors
        return

    # Collect all definitions with their scopes
    # For complete files, we need to track scope properly

    # Names that are always defined
    defined_names: set[str] = set(PYTHON_BUILTINS) | set(PYTHON_KEYWORDS)
    imported_modules: set[str] = set()
    imported_names: set[str] = set()

    # Collect imports first (module level)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name.split(".")[0])
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name)

    # Add imported names to defined names
    defined_names.update(imported_names)
    defined_names.update(imported_modules)

    # Collect all function, class, and top-level definitions
    for node in ast.walk(tree):
        # Function definitions (including async)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            defined_names.add(node.name)
        # Class definitions
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)

    # Use a scope-aware visitor to collect all defined names
    class ScopeCollector(ast.NodeVisitor):
        def __init__(self):
            self.defined: set[str] = set()

        def _collect_assignment_targets(self, targets: list[ast.expr]) -> None:
            """Collect all names from assignment targets."""
            for target in targets:
                if isinstance(target, ast.Name):
                    self.defined.add(target.id)
                elif isinstance(target, ast.Tuple | ast.List):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            self.defined.add(elt.id)
                elif isinstance(target, ast.Attribute):
                    # self.x = ... - don't add x, only check the base
                    pass

        def _collect_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            """Record the function name and all parameter names as defined."""
            self.defined.add(node.name)
            for arg in node.args.args:
                self.defined.add(arg.arg)
            for arg in node.args.posonlyargs:
                self.defined.add(arg.arg)
            for arg in node.args.kwonlyargs:
                self.defined.add(arg.arg)
            if node.args.vararg:
                self.defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                self.defined.add(node.args.kwarg.arg)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._collect_function_signature(node)
            # Visit function body
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            # Same handling as the sync visitor; the union-typed helper
            # makes the shared signature explicit.
            self._collect_function_signature(node)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.defined.add(node.name)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            # Collect all assignment targets (x = ..., x, y = ...)
            self._collect_assignment_targets(node.targets)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            # Annotated assignment: x: int = ...
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            self.generic_visit(node)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            # Augmented assignment: x += 1
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            # Loop variable is defined
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.defined.add(elt.id)
            self.generic_visit(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            # Same as For
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.defined.add(elt.id)
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            # Exception variable is defined
            if node.name:
                self.defined.add(node.name)
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            # Comprehension iteration variable is defined
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        self.defined.add(elt.id)
            self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            # Lambda parameters
            for arg in node.args.args:
                self.defined.add(arg.arg)
            for arg in node.args.posonlyargs:
                self.defined.add(arg.arg)
            for arg in node.args.kwonlyargs:
                self.defined.add(arg.arg)
            if node.args.vararg:
                self.defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                self.defined.add(node.args.kwarg.arg)
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:
            # With statement context variable
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    self.defined.add(item.optional_vars.id)
            self.generic_visit(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            # Same as With
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    self.defined.add(item.optional_vars.id)
            self.generic_visit(node)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            # Walrus operator: (x := value)
            if isinstance(node.target, ast.Name):
                self.defined.add(node.target.id)
            self.generic_visit(node)

    collector = ScopeCollector()
    collector.visit(tree)
    defined_names.update(collector.defined)

    # Find all name references (names that are used, not defined)
    class NameReferenceVisitor(ast.NodeVisitor):
        def __init__(self):
            self.undefined: list[tuple[str, int]] = []

        def visit_Name(self, node: ast.Name) -> None:
            # Only check names that are being used (loaded), not stored or deleted
            if not isinstance(node.ctx, ast.Load):
                return

            name = node.id

            # Skip if name is defined, imported, or known
            if (
                name in defined_names
                or name in imported_names
                or name in imported_modules
                or name in PYTHON_STDLIB
            ):
                return

            # Skip common patterns that are context-dependent
            # - Private names (start with _), including __dunder__ names
            # - self, cls (used in methods)
            if name.startswith("_"):
                return
            if name in ("self", "cls"):
                return

            self.undefined.append((name, node.lineno))
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            # For attribute access like self.x or cls.x, don't flag x
            # But do check the base object
            self.generic_visit(node)

    visitor = NameReferenceVisitor()
    visitor.visit(tree)

    # Report unique undefined names
    seen: set[str] = set()
    for name, lineno in visitor.undefined:
        if name in seen:
            continue
        seen.add(name)

        defect = QCDefect(
            rule_id=QCRuleID.QC_1_1,
            name="Undefined Name Reference",
            description=f"Name '{name}' is not defined in snippet, standard library, or imports",
            severity=Severity.P1,
            location=location,
            evidence=f"{name}",
            fix_suggestion=f"Define '{name}' or add import statement",
            line_number=line_offset + lineno,
            artifact_path=artifact_result.artifact_path,
            artifact_type=artifact_result.artifact_type,
            language=language,
        )
        artifact_result.defects.append(defect)


def check_qc_1_4_type_mismatch(
    code: str,
    language: str,
    artifact_result: QCArtifactResult,
    location: str,
    line_offset: int = 0,
) -> None:
    """QC-1.4: Check for obvious type mismatches.

    Detects:
    - String passed to function expecting int (e.g., range("5"))
    - Wrong number of arguments to builtins

    Intentionally narrow scope: only the small table of common builtins
    below is inspected. This is a heuristic signal, not a type checker —
    full signature analysis is out of scope for a lightweight lint pass.

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

    # Known function signatures: function -> expected types for positional args
    type_patterns = {
        "range": [{"int"}, {"int"}],  # range(stop) or range(start, stop[, step])
        "len": [{"object"}],  # len() accepts any object
        "int": [{"int", "float", "str"}],  # int() accepts these types
        "float": [{"int", "float", "str"}],
        "str": [{"object"}],
        "abs": [{"int", "float"}],
        "pow": [{"int", "float"}],
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Get function name
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if not func_name or func_name not in type_patterns:
            continue

        # Check argument types
        for arg in node.args:
            arg_type = None
            if isinstance(arg, ast.Constant):
                if isinstance(arg.value, int):
                    arg_type = "int"
                elif isinstance(arg.value, float):
                    arg_type = "float"
                elif isinstance(arg.value, str):
                    arg_type = "str"
                elif arg.value is None:
                    arg_type = "None"
                elif isinstance(arg.value, bool):
                    arg_type = "bool"
                elif isinstance(arg.value, list):
                    arg_type = "list"
                elif isinstance(arg.value, dict):
                    arg_type = "dict"

            if arg_type == "str" and func_name == "range":
                defect = QCDefect(
                    rule_id=QCRuleID.QC_1_4,
                    name="Type Mismatch",
                    description="range() expects integer arguments, got string literal",
                    severity=Severity.P2,
                    location=location,
                    evidence=f"range({ast.unparse(arg)})",
                    fix_suggestion="Convert string to int: range(int(...))",
                    line_number=line_offset + node.lineno,
                    artifact_path=artifact_result.artifact_path,
                    artifact_type=artifact_result.artifact_type,
                    language=language,
                )
                artifact_result.defects.append(defect)
