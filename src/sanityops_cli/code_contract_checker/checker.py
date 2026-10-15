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

"""Main Code Contract inspector for Logic Artifacts."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from .models import (
    QCArtifactResult,
    QCInspectionResult,
)
from .rules import (
    check_qc_0_1_syntax_parsability,
    check_qc_0_3_structural_completeness,
    check_qc_1_1_undefined_name,
    check_qc_1_4_type_mismatch,
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
    extract_code_blocks,
)

logger = logging.getLogger(__name__)

#: Maximum nesting depth when recursing into nested tool parameter schemas.
#: Prevents stack overflow on malformed or adversarial deeply-nested schemas.
MAX_TOOL_SCHEMA_DEPTH = 10

#: All QC checks applied to every Python code snippet, in order.
#: Adding a new rule here automatically applies it to both embedded
#: code blocks and whole Python source files.
#: Note: QC-0.2 (language declaration) is intentionally absent here - it
#: operates on the fence marker rather than the code body, so it is run
#: inside extract_code_blocks during block discovery instead.
_QC_PYTHON_CHECKS = (
    check_qc_0_1_syntax_parsability,
    check_qc_0_3_structural_completeness,
    check_qc_1_1_undefined_name,
    check_qc_1_4_type_mismatch,
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
)


class CodeContractChecker:
    """Inspects Logic Artifacts for Code Contract violations.

    This checker runs WITHOUT LLM - it uses pure AST parsing and
    pattern matching to detect code defects in embedded code snippets.
    """

    def __init__(self, verbose: bool = False):
        """Initialize the checker.

        Args:
            verbose: Enable verbose output.
        """
        self.verbose = verbose

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

    def _read_artifact(self, path: str) -> str | None:
        """Read an artifact file, returning None on read failure."""
        try:
            return Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # OSError covers FileNotFoundError, PermissionError,
            # IsADirectoryError and other path-related failures;
            # UnicodeDecodeError (a ValueError) covers binary files.
            logger.debug("Could not read %s: %s", path, e)
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

        content = self._read_artifact(path)
        if content is None:
            return artifact_result

        # Extract and check code blocks
        code_blocks = extract_code_blocks(content, artifact_result, location_prefix="$.content")

        for idx, (code, language, line_number) in enumerate(code_blocks):
            location = f"$.content.code_blocks[{idx}]"
            self._run_qc_checks(code, language, artifact_result, location, line_number)

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

        content = self._read_artifact(path)
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
            code_blocks = extract_code_blocks(content, artifact_result, location_prefix="$.content")
            self._check_code_blocks(code_blocks, artifact_result, location_prefix="$.content")
            return artifact_result

        # Check description field
        description = data.get("description", "")
        if description and isinstance(description, str):
            code_blocks = extract_code_blocks(
                description, artifact_result, location_prefix="$.description"
            )
            self._check_code_blocks(code_blocks, artifact_result, location_prefix="$.description")

        # Check parameter descriptions and examples
        parameters = data.get("parameters", {})
        if isinstance(parameters, dict):
            self._check_tool_parameters(parameters, artifact_result, "$.parameters")

        return artifact_result

    def _run_qc_checks(
        self,
        code: str,
        language: str,
        artifact_result: QCArtifactResult,
        location: str,
        line_offset: int,
    ) -> None:
        """Apply every QC check to a single Python code snippet.

        Shared by embedded code blocks and whole Python source files.

        Args:
            code: The code snippet to check.
            language: The declared language.
            artifact_result: The artifact result to add defects to.
            location: JSONPath-like location of the code.
            line_offset: Line number offset for the code.
        """
        for check in _QC_PYTHON_CHECKS:
            check(code, language, artifact_result, location, line_offset)

    def _check_tool_parameters(
        self,
        parameters: dict[str, Any],
        artifact_result: QCArtifactResult,
        location_prefix: str,
        *,
        depth: int = 0,
        max_depth: int = MAX_TOOL_SCHEMA_DEPTH,
    ) -> None:
        """Recursively check tool parameters for code snippets.

        Args:
            parameters: The parameters dict to check.
            artifact_result: The artifact result to add defects to.
            location_prefix: Location prefix for defects.
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

            # Check description
            description = prop_def.get("description", "")
            if description and isinstance(description, str):
                code_blocks = extract_code_blocks(
                    description, artifact_result, location_prefix=f"{prop_location}.description"
                )
                self._check_code_blocks(
                    code_blocks, artifact_result, location_prefix=f"{prop_location}.description"
                )

            # Check default value if it looks like code
            default = prop_def.get("default")
            if isinstance(default, str) and "\n" in default:
                # Multi-line default might be code
                code_blocks = extract_code_blocks(
                    default, artifact_result, location_prefix=f"{prop_location}.default"
                )
                self._check_code_blocks(
                    code_blocks, artifact_result, location_prefix=f"{prop_location}.default"
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
                            location_prefix=f"{prop_location}.examples[{idx}]",
                        )

            # Check nested object properties
            if prop_def.get("type") == "object":
                nested_props = prop_def.get("properties", {})
                if isinstance(nested_props, dict):
                    self._check_tool_parameters(
                        prop_def, artifact_result, prop_location, depth=depth + 1
                    )

            # Check items for array types
            items = prop_def.get("items", {})
            if isinstance(items, dict) and items.get("type") == "object":
                self._check_tool_parameters(
                    items, artifact_result, f"{prop_location}.items", depth=depth + 1
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

        content = self._read_artifact(path)
        if content is None:
            return artifact_result

        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)

        # Check description in frontmatter
        description = frontmatter.get("description", "")
        if description and isinstance(description, str):
            code_blocks = extract_code_blocks(
                description, artifact_result, location_prefix="$.frontmatter.description"
            )
            self._check_code_blocks(
                code_blocks, artifact_result, location_prefix="$.frontmatter.description"
            )

        # Check markdown body sections
        sections = self._parse_markdown_sections(body)
        for section_title, section_content in sections:
            safe_title = section_title.replace(".", "_").replace("[", "_")
            code_blocks = extract_code_blocks(
                section_content,
                artifact_result,
                location_prefix=f"$.sections.{safe_title}",
            )
            self._check_code_blocks(
                code_blocks, artifact_result, location_prefix=f"$.sections.{safe_title}"
            )

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
        code_blocks: list[tuple[str, str, int]],
        artifact_result: QCArtifactResult,
        location_prefix: str = "$",
    ) -> None:
        """Apply all QC checks to a list of code blocks.

        Args:
            code_blocks: List of (code, language, line_number) tuples.
            artifact_result: The artifact result to add defects to.
            location_prefix: Prefix for defect locations.
        """
        for idx, (code, language, line_number) in enumerate(code_blocks):
            location = f"{location_prefix}.code_blocks[{idx}]"
            self._run_qc_checks(code, language, artifact_result, location, line_number)
