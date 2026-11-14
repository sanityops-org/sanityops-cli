"""Main Code Contract inspector for Logic Artifacts.

Implements the 17-item checklist v2 (design §7): program rules emit
Definitive verdicts; the four hybrid items (QC-0.5/1.3/4.1/4.2) emit
Candidates awaiting model confirmation; context-gated items (QC-1.2/1.3)
declare Not Executed rather than guessing. A Definitive QC-0 verdict on a
snippet blocks the QC-1..4 tiers for that snippet (entry-gate semantics).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from .models import (
    DefectStatus,
    QCArtifactResult,
    QCInspectionResult,
    Severity,
)
from .rules import (
    check_qc_0_1_syntax_parsability,
    check_qc_0_3_structural_completeness,
    check_qc_0_4_fence_integrity,
    check_qc_0_5_language_content_mismatch,
    check_qc_1_1_undefined_name,
    check_qc_1_2_invalid_import,
    check_qc_1_3_deprecated_api,
    check_qc_1_4_type_mismatch,
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
    check_qc_4_1_snippet_artifact_mismatch,
    check_qc_4_2_snippet_body_drift,
    extract_code_blocks,
)

logger = logging.getLogger(__name__)

#: QC-0 Python checks — the entry gate (design §7.1). A Definitive verdict
#: here blocks QC-1..4 for the same snippet.
_QC0_PYTHON_CHECKS = (
    check_qc_0_1_syntax_parsability,
    check_qc_0_3_structural_completeness,
)

#: QC-1..3 Python checks — only run once the QC-0 gate passes.
_QC_PROGRAM_PYTHON_CHECKS = (
    check_qc_1_1_undefined_name,
    check_qc_1_4_type_mismatch,
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
)

#: Context-gated QC-1 additions (design §7.1: Not Executed over FAIL).
_QC_CONTEXT_GATED_PYTHON_CHECKS = (
    check_qc_1_2_invalid_import,
    check_qc_1_3_deprecated_api,
)


class CodeContractChecker:
    """Inspects Logic Artifacts for Code Contract violations.

    This checker runs WITHOUT LLM - it uses pure AST parsing and
    pattern matching to detect code defects in embedded code snippets.
    Hybrid items pre-screen deterministically and emit Candidates.
    """

    def __init__(
        self,
        verbose: bool = False,
        declared_dependencies: list[str] | None = None,
    ):
        """Initialize the checker.

        Args:
            verbose: Enable verbose output.
            declared_dependencies: Project dependency module names enabling
                QC-1.2 adjudication (``qc_lint.declared_dependencies`` config).
                None keeps QC-1.2 in Not Executed mode.
        """
        self.verbose = verbose
        self.declared_dependencies = declared_dependencies

    def check_from_paths(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ) -> QCInspectionResult:
        """Inspect artifacts from file paths.

        Args:
            prompts: List of prompt file paths.
            tools: List of tool schema file paths.
            skills: List of skill file paths.

        Returns:
            QCInspectionResult with all defects found.
        """
        start_time = perf_counter()
        result = QCInspectionResult()

        # Check prompts
        for path in prompts:
            artifact_result = self._check_prompt(path)
            result.prompts.append(artifact_result)

        # Check tools
        for path in tools:
            artifact_result = self._check_tool(path)
            result.tools.append(artifact_result)

        # Check skills
        for path in skills:
            artifact_result = self._check_skill(path)
            result.skills.append(artifact_result)

        result.inspection_time_seconds = perf_counter() - start_time
        return result

    def _read_artifact(self, path: str, artifact_result: QCArtifactResult) -> str | None:
        """Read an artifact file, returning None on read failure."""
        try:
            return Path(path).read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            if self.verbose:
                logger.warning("Could not read %s: %s", path, e)
            return None

    def _check_prompt(self, path: str) -> QCArtifactResult:
        """Check a prompt file for code contract violations.

        Args:
            path: Absolute path to the prompt file.

        Returns:
            QCArtifactResult with any defects found.
        """
        artifact_result = QCArtifactResult(
            artifact_type="prompt",
            artifact_path=path,
            artifact_name=Path(path).name,
            checked_at=datetime.now().isoformat(),
        )

        content = self._read_artifact(path, artifact_result)
        if content is None:
            return artifact_result

        check_qc_0_4_fence_integrity(content, artifact_result, "$.content")

        # Extract and check code blocks
        code_blocks = extract_code_blocks(content, artifact_result, location_prefix="$.content")

        for idx, block in enumerate(code_blocks):
            location = f"$.content.code_blocks[{idx}]"
            self._run_qc_checks(
                block.code,
                block.language,
                artifact_result,
                location,
                block.line_number,
                illustrative=block.illustrative,
                artifact_body=content,
            )

        return artifact_result

    def _check_tool(self, path: str) -> QCArtifactResult:
        """Check a tool schema file for code contract violations.

        Code snippets can appear in:
        - description field
        - parameters.properties.*.description
        - parameters.properties.*.default (for code-like values)
        - parameters.properties.*.examples

        For Python source files (.py), the entire file is checked directly.

        Args:
            path: Absolute path to the tool schema file.

        Returns:
            QCArtifactResult with any defects found.
        """
        artifact_result = QCArtifactResult(
            artifact_type="tool",
            artifact_path=path,
            artifact_name=Path(path).stem,
            checked_at=datetime.now().isoformat(),
        )

        content = self._read_artifact(path, artifact_result)
        if content is None:
            return artifact_result

        # Handle Python source files directly
        if Path(path).suffix.lower() == ".py":
            # For .py files, check the entire file as Python code
            self._run_qc_checks(content, "python", artifact_result, "$.content", line_offset=0)
            return artifact_result

        # Parse JSON or YAML
        try:
            if Path(path).suffix.lower() == ".json":
                data = json.loads(content)
            else:
                data = yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError):
            # Not valid JSON/YAML - try to extract code blocks from raw content
            check_qc_0_4_fence_integrity(content, artifact_result, "$.content")
            code_blocks = extract_code_blocks(content, artifact_result, location_prefix="$.content")
            self._check_code_blocks(code_blocks, artifact_result, artifact_body=content)
            return artifact_result

        if not isinstance(data, dict):
            return artifact_result

        owner_context = self._owner_context(data)

        # Check description field
        description = data.get("description", "")
        if description and isinstance(description, str):
            check_qc_0_4_fence_integrity(description, artifact_result, "$.description")
            code_blocks = extract_code_blocks(
                description, artifact_result, location_prefix="$.description"
            )
            self._check_code_blocks(
                code_blocks, artifact_result, owner_context=owner_context, artifact_body=description
            )

        # Check parameter descriptions and examples
        parameters = data.get("parameters", {})
        if isinstance(parameters, dict):
            self._check_tool_parameters(
                parameters,
                artifact_result,
                "$.parameters",
                owner_context=owner_context,
                artifact_body=description if isinstance(description, str) else "",
            )

        return artifact_result

    @staticmethod
    def _owner_context(data: dict[str, Any]) -> dict[str, Any] | None:
        """Build QC-4.1 owner context from a tool schema's parameters."""
        parameters = data.get("parameters")
        if not isinstance(parameters, dict):
            return None
        properties = parameters.get("properties")
        if not isinstance(properties, dict) or not properties:
            return None
        required = parameters.get("required")
        return {
            "properties": properties,
            "required": required if isinstance(required, list) else [],
        }

    def _run_qc_checks(
        self,
        code: str,
        language: str,
        artifact_result: QCArtifactResult,
        location: str,
        line_offset: int,
        *,
        illustrative: bool = False,
        owner_context: dict[str, Any] | None = None,
        artifact_body: str | None = None,
    ) -> None:
        """Apply the QC rule tiers to a single code snippet.

        Order (design §7.1): QC-0 entry gate → QC-1..3 program rules →
        context-gated QC-1 additions → QC-4 hybrid pre-screens. Illustrative
        (示意) snippets are exempt from QC-0.1/QC-0.3.

        Args:
            code: The code snippet to check.
            language: The declared language.
            artifact_result: The artifact result to add defects to.
            location: JSONPath-like location of the code.
            line_offset: Line number offset for the code.
            illustrative: True when the snippet is marked as an example/pseudo
                snippet (skips QC-0.1/QC-0.3).
            owner_context: Owning tool schema context for QC-4.1.
            artifact_body: Owning artifact prose for QC-4.2.
        """
        baseline = len(artifact_result.defects)

        # QC-0.5 applies to every language (hybrid pre-screen).
        check_qc_0_5_language_content_mismatch(
            code, language, artifact_result, location, line_offset
        )

        gate_blocked = False
        if language.lower() in ("python", "py") and not illustrative:
            for check in _QC0_PYTHON_CHECKS:
                check(code, language, artifact_result, location, line_offset)
            # Entry gate: any Definitive QC-0 verdict blocks QC-1..4.
            gate_blocked = any(
                d.status == DefectStatus.DEFINITIVE
                and d.severity in (Severity.P0, Severity.P1)
                and d.rule_id.value.startswith("QC-0")
                for d in artifact_result.defects[baseline:]
            )

        if gate_blocked:
            return

        if language.lower() in ("python", "py"):
            for check in _QC_PROGRAM_PYTHON_CHECKS:
                check(code, language, artifact_result, location, line_offset)
            for check in _QC_CONTEXT_GATED_PYTHON_CHECKS:
                if check is check_qc_1_2_invalid_import:
                    check(
                        code,
                        language,
                        artifact_result,
                        location,
                        line_offset,
                        declared_dependencies=self.declared_dependencies,
                    )
                else:
                    check(code, language, artifact_result, location, line_offset)

        # QC-4 hybrid pre-screens (owner-aware, any language).
        check_qc_4_1_snippet_artifact_mismatch(
            code,
            language,
            artifact_result,
            location,
            line_offset,
            owner_context=owner_context,
        )
        check_qc_4_2_snippet_body_drift(
            code,
            language,
            artifact_result,
            location,
            line_offset,
            artifact_body=artifact_body,
        )

    def _check_tool_parameters(
        self,
        parameters: dict[str, Any],
        artifact_result: QCArtifactResult,
        location_prefix: str,
        *,
        owner_context: dict[str, Any] | None = None,
        artifact_body: str = "",
        depth: int = 0,
        max_depth: int = 10,
    ) -> None:
        """Recursively check tool parameters for code snippets.

        Args:
            parameters: The parameters dict to check.
            artifact_result: The artifact result to add defects to.
            location_prefix: Location prefix for defects.
            owner_context: Top-level owner schema for QC-4.1.
            artifact_body: Owning artifact prose for QC-4.2.
            depth: Current recursion depth.
            max_depth: Maximum nesting depth before stopping (prevents stack overflow
                on malformed or adversarial deeply-nested schemas).
        """
        if depth >= max_depth:
            return

        properties = parameters.get("properties", {})
        if not isinstance(properties, dict):
            return

        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue

            prop_location = f"{location_prefix}.properties.{prop_name}"

            # Nested schemas take precedence as QC-4.1 owner context.
            nested_props = prop_def.get("properties")
            prop_owner_context = (
                {
                    "properties": nested_props,
                    "required": prop_def.get("required")
                    if isinstance(prop_def.get("required"), list)
                    else [],
                }
                if isinstance(nested_props, dict) and nested_props
                else owner_context
            )

            # Check description
            description = prop_def.get("description", "")
            if description and isinstance(description, str):
                check_qc_0_4_fence_integrity(
                    description, artifact_result, f"{prop_location}.description"
                )
                code_blocks = extract_code_blocks(
                    description, artifact_result, location_prefix=f"{prop_location}.description"
                )
                self._check_code_blocks(
                    code_blocks,
                    artifact_result,
                    owner_context=prop_owner_context,
                    artifact_body=artifact_body,
                )

            # Check default value if it looks like code
            default = prop_def.get("default")
            if isinstance(default, str) and "\n" in default:
                # Multi-line default might be code
                code_blocks = extract_code_blocks(
                    default, artifact_result, location_prefix=f"{prop_location}.default"
                )
                self._check_code_blocks(
                    code_blocks,
                    artifact_result,
                    owner_context=prop_owner_context,
                    artifact_body=artifact_body,
                )

            # Check examples
            examples = prop_def.get("examples", [])
            if isinstance(examples, list):
                for idx, example in enumerate(examples):
                    if isinstance(example, str) and "\n" in example:
                        code_blocks = extract_code_blocks(
                            example,
                            artifact_result,
                            location_prefix=f"{prop_location}.examples[{idx}]",
                        )
                        self._check_code_blocks(
                            code_blocks,
                            artifact_result,
                            owner_context=prop_owner_context,
                            artifact_body=artifact_body,
                        )

            # Check nested object properties
            if prop_def.get("type") == "object":
                nested_props = prop_def.get("properties", {})
                if isinstance(nested_props, dict):
                    self._check_tool_parameters(
                        prop_def,
                        artifact_result,
                        prop_location,
                        owner_context=prop_owner_context,
                        artifact_body=artifact_body,
                        depth=depth + 1,
                    )

            # Check items for array types
            items = prop_def.get("items", {})
            if isinstance(items, dict) and items.get("type") == "object":
                self._check_tool_parameters(
                    items,
                    artifact_result,
                    f"{prop_location}.items",
                    owner_context=prop_owner_context,
                    artifact_body=artifact_body,
                    depth=depth + 1,
                )

    def _check_skill(self, path: str) -> QCArtifactResult:
        """Check a skill file for code contract violations.

        Code snippets can appear in:
        - description field (frontmatter)
        - section content (markdown body)

        Args:
            path: Absolute path to the skill file.

        Returns:
            QCArtifactResult with any defects found.
        """
        artifact_result = QCArtifactResult(
            artifact_type="skill",
            artifact_path=path,
            artifact_name=Path(path).stem,
            checked_at=datetime.now().isoformat(),
        )

        content = self._read_artifact(path, artifact_result)
        if content is None:
            return artifact_result

        check_qc_0_4_fence_integrity(content, artifact_result, "$.content")

        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)

        # Check description in frontmatter
        description = frontmatter.get("description", "")
        if description and isinstance(description, str):
            code_blocks = extract_code_blocks(
                description, artifact_result, location_prefix="$.frontmatter.description"
            )
            self._check_code_blocks(code_blocks, artifact_result, artifact_body=body)

        # Check markdown body sections
        sections = self._parse_markdown_sections(body)
        for section_title, section_content in sections:
            safe_title = section_title.replace(".", "_").replace("[", "_")
            code_blocks = extract_code_blocks(
                section_content,
                artifact_result,
                location_prefix=f"$.sections.{safe_title}",
            )
            self._check_code_blocks(code_blocks, artifact_result, artifact_body=section_content)

        return artifact_result

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: The full file content.

        Returns:
            Tuple of (frontmatter_dict, body_content).
        """
        if not content.startswith("---"):
            return {}, content

        # Find the closing ---
        end_idx = content.find("\n---", 4)
        if end_idx == -1:
            return {}, content

        frontmatter_str = content[4:end_idx]
        body = content[end_idx + 5 :].lstrip()

        try:
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            frontmatter = {}

        return frontmatter, body

    def _parse_markdown_sections(self, content: str) -> list[tuple[str, str]]:
        """Parse markdown into sections by headings.

        Args:
            content: Markdown content.

        Returns:
            List of (section_title, section_content) tuples.
        """
        sections: list[tuple[str, str]] = []
        current_title = ""
        current_content: list[str] = []

        for line in content.split("\n"):
            if line.startswith("## "):
                # Save previous section
                if current_content:
                    sections.append((current_title, "\n".join(current_content)))
                current_title = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections.append((current_title, "\n".join(current_content)))

        return sections

    def _check_code_blocks(
        self,
        code_blocks: list,
        artifact_result: QCArtifactResult,
        *,
        owner_context: dict[str, Any] | None = None,
        artifact_body: str | None = None,
    ) -> None:
        """Apply all QC checks to a list of code blocks.

        Args:
            code_blocks: List of CodeBlock records.
            artifact_result: The artifact result to add defects to.
            owner_context: Owning tool schema context for QC-4.1.
            artifact_body: Owning artifact prose for QC-4.2.
        """
        for idx, block in enumerate(code_blocks):
            location = f"$.code_blocks[{idx}]"
            self._run_qc_checks(
                block.code,
                block.language,
                artifact_result,
                location,
                block.line_number,
                illustrative=block.illustrative,
                owner_context=owner_context,
                artifact_body=artifact_body,
            )
