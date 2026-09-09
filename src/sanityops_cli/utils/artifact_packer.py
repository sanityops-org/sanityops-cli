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
#

"""Artifact packer — prepare artifacts for upload.

This module handles:
- Merging multiple prompt files into a single text
- Merging multiple tool schema files into a JSON array
- Packing skill directories/files into a ZIP archive
- Packing from ScannerAgent findings (extracted content)
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from sanityops_cli.agents.scanner_agent.models.finding import (
    Finding,
    PromptContent,
    SkillContent,
    ToolContent,
)


class ArtifactPacker:
    """Prepare artifacts for upload to the sanityops server.

    The server expects:
    - prompt_content: Single text string (merged from all prompt files)
    - tools_schema: JSON string of tool definitions array
    - skill_file: ZIP file containing skill directories/files
    """

    def __init__(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ):
        """Initialize the packer with artifact file paths.

        Args:
            prompts: List of absolute paths to prompt files.
            tools: List of absolute paths to tool schema files.
            skills: List of absolute paths to skill files or directories.
        """
        self.prompts = prompts
        self.tools = tools
        self.skills = skills

    def pack(self) -> dict[str, Any]:
        """Pack all artifacts into upload format.

        Returns:
            Dict with keys:
                - prompt_content: str or None
                - tools_schema: str (JSON) or None
                - skill_file: tuple(filename, bytes) or None

        Raises:
            OSError: If files cannot be read.
            ValueError: If tools schema is invalid JSON.
        """
        result: dict[str, Any] = {}

        # Pack prompts
        result["prompt_content"] = self._pack_prompts()

        # Pack tools
        result["tools_schema"] = self._pack_tools()

        # Pack skills
        result["skill_file"] = self._pack_skills()

        return result

    def _pack_prompts(self) -> str | None:
        """Merge all prompt files into a single text.

        Each file's content is separated by a marker comment.

        Returns:
            Merged prompt text, or None if no prompts.
        """
        if not self.prompts:
            return None

        parts: list[str] = []
        for path_str in self.prompts:
            path = Path(path_str)
            content = path.read_text(encoding="utf-8")

            # Add a header comment to identify the source file
            filename = path.name
            parts.append(f"<!-- BEGIN: {filename} -->")
            parts.append(content.strip())
            parts.append(f"<!-- END: {filename} -->")
            parts.append("")  # Empty line between files

        return "\n".join(parts).strip() if parts else None

    def _pack_tools(self) -> str | None:
        """Merge all tool schema files into a JSON array.

        Handles both:
        - Single tool definition objects
        - Arrays of tool definitions

        Tools are deduplicated by 'name' field.

        Returns:
            JSON string of tools array, or None if no tools.

        Raises:
            ValueError: If a tool file contains invalid JSON.
            ValueError: If tool definitions conflict on name.
        """
        if not self.tools:
            return None

        all_tools: dict[str, dict[str, Any]] = {}  # name -> definition

        for path_str in self.tools:
            path = Path(path_str)
            content = path.read_text(encoding="utf-8")

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in tool file {path}: {e}") from e

            # Handle both single object and array
            if isinstance(data, dict):
                tools_list = [data]
            elif isinstance(data, list):
                tools_list = data
            else:
                raise ValueError(f"Tool file {path} must contain an object or array")

            # Deduplicate by name
            for tool_def in tools_list:
                if not isinstance(tool_def, dict):
                    continue
                name = tool_def.get("name")
                if not name:
                    continue

                all_tools[name] = tool_def

        if not all_tools:
            return None

        return json.dumps(list(all_tools.values()), ensure_ascii=False)

    def _pack_skills(self) -> tuple[str, bytes] | None:
        """Pack skill directories/files into a ZIP archive.

        The ZIP preserves the directory structure relative to the skill root.
        If multiple skills are provided, they're all packed into one ZIP.

        Returns:
            Tuple of (filename, bytes) for the ZIP, or None if no skills.
        """
        if not self.skills:
            return None

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for skill_path_str in self.skills:
                skill_path = Path(skill_path_str)

                if skill_path.is_file():
                    # Single skill file
                    self._add_file_to_zip(zf, skill_path, skill_path.name)

                elif skill_path.is_dir():
                    # Skill directory - add all files recursively
                    for file_path in skill_path.rglob("*"):
                        if file_path.is_file():
                            # Skip hidden files and common exclusions
                            if any(part.startswith(".") for part in file_path.parts):
                                continue
                            if file_path.name in ("__pycache__", "node_modules", ".git"):
                                continue

                            # Preserve relative path from skill directory
                            rel_path = file_path.relative_to(skill_path)
                            self._add_file_to_zip(zf, file_path, str(rel_path))

        # Return ZIP with a descriptive name
        return ("skills.zip", buffer.getvalue())

    def _add_file_to_zip(self, zf: zipfile.ZipFile, file_path: Path, archive_name: str) -> None:
        """Add a file to the ZIP archive.

        Args:
            zf: ZipFile object.
            file_path: Path to the file on disk.
            archive_name: Name/path to use in the ZIP archive.
        """
        # Read file content
        try:
            content = file_path.read_bytes()
            zf.writestr(archive_name, content)
        except OSError:
            # Skip files that can't be read
            pass


def pack_from_findings(
    skills: list[Finding],
    tools: list[Finding],
    prompts: list[Finding],
) -> dict[str, Any]:
    """Pack artifacts from ScannerAgent findings (extracted content).

    This function uses the content already extracted by ScannerAgent,
    avoiding redundant file reads. It supports:
    - Prompts extracted from YAML/Python files (e.g., system_prompt field)
    - Tools extracted from code or schema files
    - Skills from directories or SKILL.md files

    Args:
        skills: List of skill findings from ScannerAgent.
        tools: List of tool findings from ScannerAgent.
        prompts: List of prompt findings from ScannerAgent.

    Returns:
        Dict with keys:
            - prompt_content: str or None
            - tools_schema: str (JSON) or None
            - skill_file: tuple(filename, bytes) or None
    """
    result: dict[str, Any] = {}

    # Pack prompts from findings
    result["prompt_content"] = _pack_prompts_from_findings(prompts)

    # Pack tools from findings
    result["tools_schema"] = _pack_tools_from_findings(tools)

    # Pack skills from findings
    result["skill_file"] = _pack_skills_from_findings(skills)

    return result


def _pack_prompts_from_findings(prompts: list[Finding]) -> str | None:
    """Merge prompt content from findings.

    Returns:
        Merged prompt text, or None if no prompts.
    """
    if not prompts:
        return None

    parts: list[str] = []
    for finding in prompts:
        if finding.content is None:
            continue
        if not isinstance(finding.content, PromptContent):
            continue

        content = finding.content.content
        if not content:
            continue

        # Add source identifier
        source = Path(finding.relative).name
        parts.append(f"<!-- BEGIN: {source} -->")
        parts.append(content.strip())
        parts.append(f"<!-- END: {source} -->")
        parts.append("")

    return "\n".join(parts).strip() if parts else None


def _pack_tools_from_findings(tools: list[Finding]) -> str | None:
    """Merge tool schemas from findings into OpenAI function calling format.

    Output format follows OpenAI function calling schema:
    [
      {
        "type": "function",
        "function": {
          "name": "...",
          "description": "...",
          "parameters": {...}
        }
      }
    ]

    Returns:
        JSON string of tools array, or None if no tools.
    """
    if not tools:
        return None

    all_tools: list[dict[str, Any]] = []
    for finding in tools:
        if finding.content is None:
            continue
        if not isinstance(finding.content, ToolContent):
            continue

        # Build OpenAI function calling format
        tool_def = {
            "type": "function",
            "function": {
                "name": finding.content.name,
                "description": finding.content.description,
                "parameters": finding.content.parameters,
            },
        }
        all_tools.append(tool_def)

    if not all_tools:
        return None

    return json.dumps(all_tools, ensure_ascii=False)


def _pack_skills_from_findings(skills: list[Finding]) -> tuple[str, bytes] | None:
    """Pack skills from findings.

    For skill findings with content (from analyze_files mode), creates a
    SKILL.md file in the ZIP. For directory findings (from scan mode),
    reads files from disk.

    Returns:
        Tuple of (filename, bytes) for the ZIP, or None if no skills.
    """
    if not skills:
        return None

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, finding in enumerate(skills):
            skill_path = Path(finding.relative)

            # Determine skill name
            if finding.content and isinstance(finding.content, SkillContent):
                skill_name = finding.content.name
            else:
                skill_name = skill_path.name if skill_path.is_dir() else f"skill_{i}"

            if skill_path.is_file():
                # Single skill file - read from disk
                try:
                    text_content = skill_path.read_text(encoding="utf-8")
                    zf.writestr(f"{skill_name}/SKILL.md", text_content)
                except OSError:
                    pass

            elif skill_path.is_dir():
                # Skill directory - add all files recursively
                for file_path in skill_path.rglob("*"):
                    if file_path.is_file():
                        # Skip hidden files and common exclusions
                        if any(part.startswith(".") for part in file_path.parts):
                            continue
                        if file_path.name in ("__pycache__", "node_modules", ".git"):
                            continue

                        rel_path = file_path.relative_to(skill_path)
                        try:
                            binary_content = file_path.read_bytes()
                            zf.writestr(f"{skill_name}/{rel_path}", binary_content)
                        except OSError:
                            pass

    return ("skills.zip", buffer.getvalue())
