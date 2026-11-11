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
- Packing from ExtractionResult records (skill-based pipeline)
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml

from sanityops_cli.inspect_pipeline.models import ExtractedArtifact, ExtractionResult

_EXCLUDED_DIR_NAMES = frozenset({"__pycache__", "node_modules", ".git"})
_SKILL_RESOURCE_DIRS = frozenset(
    {"references", "scripts", "assets", "resources", "templates", "examples", "tools"}
)
_SKILL_METADATA_FILES = ("skill.yaml", "skill.yml")
_TOOL_LIST_KEYS = ("tools", "tool_schema", "tool_schemas")


def _read_text_utf8_gbk(path: Path) -> str:
    """Read text file using UTF-8 (with BOM handling) and GBK fallback."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk")


def _extract_tool_parameters(schema: dict[str, Any]) -> Any:
    """Extract parameters supporting parameters, inputSchema, and input_schema."""
    for key in ("parameters", "inputSchema", "input_schema"):
        if key in schema and schema[key] is not None:
            return schema[key]
    return {}


def _normalize_tool_definition(
    tool_def: dict[str, Any],
    *,
    strict_neutral: bool = False,
    fallback_name: str | None = None,
) -> dict[str, Any] | None:
    """Normalize OpenAI / Anthropic / MCP / flat tool schemas to neutral form."""
    fn = tool_def.get("function")
    unwrapped = isinstance(fn, dict) and (
        "name" not in tool_def or tool_def.get("type") == "function"
    )
    payload: dict[str, Any] = fn if unwrapped and isinstance(fn, dict) else tool_def

    name = payload.get("name") or (fallback_name if strict_neutral else None)
    if not name:
        return None

    if strict_neutral or unwrapped:
        return {
            "name": name,
            "description": payload.get("description", ""),
            "parameters": _extract_tool_parameters(payload),
        }

    normalized = dict(payload)
    if normalized.get("type") == "function":
        normalized.pop("type", None)
    if "parameters" not in normalized and (
        "inputSchema" in normalized or "input_schema" in normalized
    ):
        normalized["parameters"] = _extract_tool_parameters(normalized)
    normalized.pop("inputSchema", None)
    normalized.pop("input_schema", None)
    return normalized


def _is_excluded_rel_path(rel_path: Path) -> bool:
    """Return True if any path segment inside a skill root is hidden or excluded."""
    return any(part.startswith(".") or part in _EXCLUDED_DIR_NAMES for part in rel_path.parts)


def _safe_skill_archive_prefix(name: str, fallback: str) -> str:
    """Sanitize skill archive directory name against path traversal."""
    cleaned = name.replace("\\", "/").strip("/")
    if not cleaned or cleaned in (".", "..") or ".." in Path(cleaned).parts:
        return fallback
    return cleaned.replace("/", "_")


def _pack_skill_dir_tree(
    zf: zipfile.ZipFile,
    skill_dir: Path,
    archive_prefix: str,
) -> int:
    """Pack all non-excluded files under a skill directory under archive_prefix."""
    added = 0
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(skill_dir)
        if _is_excluded_rel_path(rel_path):
            continue
        try:
            zf.writestr(f"{archive_prefix}/{rel_path.as_posix()}", file_path.read_bytes())
            added += 1
        except OSError:
            continue
    return added


def _pack_sibling_skill_resources(
    zf: zipfile.ZipFile,
    skill_dir: Path,
    archive_prefix: str,
) -> int:
    """Pack skill.yaml/yml metadata and standard resource subdirs adjacent to SKILL.md."""
    if (skill_dir / ".sanityops").exists():
        return 0
    added = 0
    for meta_name in _SKILL_METADATA_FILES:
        meta_path = skill_dir / meta_name
        if meta_path.is_file():
            try:
                zf.writestr(f"{archive_prefix}/{meta_name}", meta_path.read_bytes())
                added += 1
            except OSError:
                continue
    for subdir_name in sorted(_SKILL_RESOURCE_DIRS):
        subdir = skill_dir / subdir_name
        if subdir.is_dir():
            added += _pack_skill_dir_tree(zf, subdir, f"{archive_prefix}/{subdir_name}")
    return added


def pack_extracted(result: ExtractionResult) -> dict[str, Any]:
    """Pack an ExtractionResult (agent-store records) for upload.

    Same server contract as the path-based ``ArtifactPacker.pack``:
    ``prompt_content`` / ``tools_schema`` / ``skill_file``. Not-inspectable
    artifacts contribute nothing (they have no content by definition).
    """
    inspectable = [a for a in result.artifacts if a.completeness != "not inspectable"]

    prompt_parts = [a.content.strip() for a in inspectable if a.type == "prompt" and a.content]
    prompt_content = "\n\n".join(prompt_parts) or None

    tools_by_name: dict[str, dict[str, Any]] = {}
    for artifact in inspectable:
        if artifact.type != "tool" or not artifact.schema_object:
            continue
        normalized = _normalize_tool_definition(
            artifact.schema_object,
            strict_neutral=True,
            fallback_name=artifact.name,
        )
        if normalized is None:
            continue
        tools_by_name[normalized["name"]] = normalized
    tools_schema = (
        json.dumps(list(tools_by_name.values()), ensure_ascii=False) if tools_by_name else None
    )

    skill_file = _pack_skills_from_extracted([a for a in inspectable if a.type == "skill"])

    return {
        "prompt_content": prompt_content,
        "tools_schema": tools_schema,
        "skill_file": skill_file,
    }


def _pack_skills_from_extracted(
    skills: list[ExtractedArtifact],
) -> tuple[str, bytes] | None:
    """ZIP skill records: extracted SKILL.md content, or the source dir tree.

    When the skill's source is an existing directory the whole tree is
    packed (references/assets/scripts travel with it); otherwise the
    extracted verbatim content becomes ``<skill>/SKILL.md`` along with any
    adjacent skill metadata/resource subdirectories when source points to a
    standalone ``SKILL.md`` file.
    """
    if not skills:
        return None

    buffer = BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names: set[str] = set()
        for i, artifact in enumerate(skills):
            raw_name = artifact.name or f"skill_{i}"
            skill_name = _safe_skill_archive_prefix(raw_name, f"skill_{i}")
            base = skill_name
            suffix = 2
            while skill_name in used_names:
                skill_name = f"{base}_{suffix}"
                suffix += 1
            used_names.add(skill_name)

            source = Path(artifact.source) if artifact.source else None
            if source is not None and source.is_dir():
                added += _pack_skill_dir_tree(zf, source, skill_name)
                continue

            if artifact.content:
                zf.writestr(f"{skill_name}/SKILL.md", artifact.content.encode("utf-8"))
                added += 1
            elif source is not None and source.is_file() and source.name.lower() == "skill.md":
                try:
                    zf.writestr(f"{skill_name}/{source.name}", source.read_bytes())
                    added += 1
                except OSError:
                    continue

            if source is not None and source.is_file() and source.name.lower() == "skill.md":
                added += _pack_sibling_skill_resources(zf, source.parent, skill_name)

    if added == 0:
        return None
    return ("skills.zip", buffer.getvalue())


class ArtifactPacker:
    """Prepare artifacts for upload to the sanityops server.

    The server expects:
    - prompt_content: Single text string (merged from all prompt files)
    - tools_schema: JSON string of tool definitions array
    - skill_file: ZIP file containing skill directories/files

    Packs from configured file paths (``project push``); the inspect pipeline
    uses :func:`pack_extracted` instead.
    """

    def __init__(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ):
        """Initialize the packer with artifact file paths.

        Args:
            prompts: List of prompt file paths.
            tools: List of tool schema file paths.
            skills: List of skill directory/file paths.
        """
        self.prompts = prompts
        self.tools = tools
        self.skills = skills

    def pack(self) -> dict[str, Any]:
        """Pack artifacts from file paths.

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
        result["prompt_content"] = self._pack_prompts_from_paths()

        # Pack tools
        result["tools_schema"] = self._pack_tools_from_paths()

        # Pack skills
        result["skill_file"] = self._pack_skills_from_paths()

        return result

    # ========== File path-based methods ==========

    def _pack_prompts_from_paths(self) -> str | None:
        """Merge all prompt files into a single text.

        Each file's content is separated by a marker comment.

        Returns:
            Merged prompt text, or None if no prompts.
        """
        if not self.prompts:
            return None

        parts: list[str] = []
        for item in self.prompts:
            path = Path(item)
            content = _read_text_utf8_gbk(path)

            # Add a header comment to identify the source file
            filename = path.name
            parts.append(f"<!-- BEGIN: {filename} -->")
            parts.append(content.strip())
            parts.append(f"<!-- END: {filename} -->")
            parts.append("")  # Empty line between files

        return "\n".join(parts).strip() if parts else None

    def _pack_tools_from_paths(self) -> str | None:
        """Merge all tool schema files (JSON or YAML) into a JSON array.

        Handles:
        - Single tool definition objects
        - Arrays of tool definitions
        - Wrapped mappings ({tools / tool_schema / tool_schemas: [...]})
        - OpenAI function calling wrapper, Anthropic input_schema, MCP inputSchema

        Tools are deduplicated by 'name' field.

        Returns:
            JSON string of tools array, or None if no tools.

        Raises:
            ValueError: If a tool file contains invalid JSON/YAML.
        """
        if not self.tools:
            return None

        all_tools: dict[str, dict[str, Any]] = {}  # name -> definition

        for item in self.tools:
            path = Path(item)
            content = _read_text_utf8_gbk(path)

            if path.suffix.lower() in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in tool file {path}: {e}") from e
            else:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in tool file {path}: {e}") from e

            # Handle both single object, wrapper dicts, and array
            if isinstance(data, dict):
                tools_list = None
                for key in _TOOL_LIST_KEYS:
                    candidate = data.get(key)
                    if isinstance(candidate, list):
                        tools_list = candidate
                        break
                if tools_list is None:
                    tools_list = [data]
            elif isinstance(data, list):
                tools_list = data
            else:
                raise ValueError(f"Tool file {path} must contain an object or array")

            # Deduplicate by name
            for tool_def in tools_list:
                if not isinstance(tool_def, dict):
                    continue
                normalized = _normalize_tool_definition(tool_def, strict_neutral=False)
                if normalized is None:
                    continue
                all_tools[normalized["name"]] = normalized

        if not all_tools:
            return None

        return json.dumps(list(all_tools.values()), ensure_ascii=False)

    def _pack_skills_from_paths(self) -> tuple[str, bytes] | None:
        """Pack skill directories/files into a ZIP archive.

        The ZIP preserves the directory structure under the skill directory name.
        If multiple skills are provided, they're all packed into one ZIP.

        Returns:
            Tuple of (filename, bytes) for the ZIP, or None if no skills.
        """
        if not self.skills:
            return None

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in self.skills:
                skill_path = Path(item)

                if skill_path.is_file():
                    # Single skill file: prefix with the parent directory name to
                    # avoid duplicate archive names when several skill .md files
                    # (e.g. <skill-dir>/SKILL.md) are configured as individual files.
                    prefix = _safe_skill_archive_prefix(
                        skill_path.parent.name, skill_path.stem or "skill"
                    )
                    self._add_file_to_zip(zf, skill_path, f"{prefix}/{skill_path.name}")
                    if skill_path.name.lower() == "skill.md":
                        _pack_sibling_skill_resources(zf, skill_path.parent, prefix)

                elif skill_path.is_dir():
                    prefix = _safe_skill_archive_prefix(skill_path.name, "skill")
                    _pack_skill_dir_tree(zf, skill_path, prefix)

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
