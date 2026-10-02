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

from dataclasses import field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


class FindingType(StrEnum):
    SKILL = "skill"
    TOOL = "tool"
    PROMPT = "prompt"


class Section(BaseModel):
    """A markdown section within a skill file."""
    title: str = Field(description="Section heading text")
    content: str = Field(description="Section body content")


class ToolSchema(BaseModel):
    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict,description="Tool parameters, JSON Schema (Draft-07) format")


class SkillContent(BaseModel):
    """Extracted content from a skill.md file."""

    name: str = Field(description="Skill name from frontmatter")
    description: str = Field(description="Skill description from frontmatter")
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw YAML frontmatter fields (preserved for QDS-0 gate)",
    )
    sections: list[Section] = Field(default_factory=list, description="Parsed markdown sections")

    #: Frontmatter fields that must be positive integers (QDS-0.4). LLM-based
    #: extraction can stringify numeric values, so coerce them back to int.
    _POSITIVE_INT_FIELDS: tuple[str, ...] = (
        "max_items", "max_chars", "timeout_seconds", "max_tool_calls", "max_retries",
    )

    @model_validator(mode="after")
    def _normalize_frontmatter_types(self) -> "SkillContent":
        # Create a normalized copy to avoid in-place mutation
        normalized = dict(self.frontmatter)
        for field_name in self._POSITIVE_INT_FIELDS:
            value = normalized.get(field_name)
            if isinstance(value, str) and value.strip().isdigit():
                normalized[field_name] = int(value.strip())
            elif isinstance(value, float) and not isinstance(value, bool):
                # YAML may parse integers as floats (e.g., "5" -> 5.0)
                normalized[field_name] = int(value)
            elif isinstance(value, bool):
                # bool is a subclass of int; reject explicit true/false for int fields
                normalized.pop(field_name, None)
            # int values are already correct, no conversion needed
        boolean_fields = ("partial_result_allowed",)
        for field_name in boolean_fields:
            value = normalized.get(field_name)
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("true", "false"):
                    normalized[field_name] = lowered == "true"
        self.frontmatter = normalized
        return self

    def to_markdown(self) -> str:
        """Reconstruct the full skill document: frontmatter plus sections.

        The frontmatter is re-serialized ahead of the body so downstream
        consumers (e.g. the QDS-0 gate) can re-parse the declared metadata.
        """
        parts: list[str] = []
        if self.frontmatter:
            # yaml is imported at module level; safe_dump preserves frontmatter.
            parts.append(
                "---\n"
                + yaml.safe_dump(self.frontmatter, sort_keys=False, allow_unicode=True)
                + "---\n"
            )
        if not self.sections:
            if not parts:
                return ""
        parts.append(
            "\n\n".join(
                f"## {section.title}\n\n{section.content}"
                for section in self.sections
            )
        )
        return "\n".join(parts)


class ToolContent(BaseModel):
    """Extracted content from a tool file."""
    name: str = Field(description="Tool name from definition")
    description: str = Field(description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema of parameters")


class PromptContent(BaseModel):
    content: str


class Finding(BaseModel):
    type: FindingType
    relative: str
    content: SkillContent | ToolContent | PromptContent | None = None

    @field_validator("relative")
    @classmethod
    def validate_relative(cls, v: str, info: ValidationInfo) -> str:
        ft = FindingType(info.data.get("type"))
        path = Path(v)

        if not path.is_absolute():
            raise ValueError(f"relative must be an absolute path: {v}")

        if not path.exists():
            raise ValueError(f"path does not exist: {v}")

        if ft == FindingType.TOOL:
            if not path.is_file():
                raise ValueError(f"Tool finding must be a file path: {v}")

        elif ft == FindingType.SKILL:
            # SKILL can be either a file (analyze_files mode) or directory (scan mode)
            if not path.is_file() and not path.is_dir():
                raise ValueError(f"Skill finding must be a file or directory path: {v}")

        return v

    @model_validator(mode="after")
    def validate_content_binding(self) -> "Finding":
        if self.type == FindingType.SKILL:
            if self.content is not None and not isinstance(self.content, SkillContent):
                raise ValueError("Skill finding content must be SkillContent or None")
        elif self.type == FindingType.TOOL:
            if self.content is not None and not isinstance(self.content, ToolContent):
                raise ValueError("Tool finding content must be ToolContent or None")
        elif self.type == FindingType.PROMPT:
            if self.content is not None and not isinstance(self.content, PromptContent):
                raise ValueError("Prompt finding content must be PromptContent or None")
        return self


class FindingsResult(BaseModel):
    directory: str
    skills: list[Finding] = field(default_factory=list)
    tools: list[Finding] = field(default_factory=list)
    prompts: list[Finding] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
