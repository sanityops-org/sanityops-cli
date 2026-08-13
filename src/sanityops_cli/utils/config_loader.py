"""Inspect config loader - load and validate inspect_config.yaml"""

import re
from pathlib import Path
from typing import Any

import yaml

from sanityops_cli.exceptions.base_exceptions import ValidationError

# Reuse excluded directories from validators
from sanityops_cli.utils.validators import EXCLUDED_DIRS

# Default config file location
DEFAULT_CONFIG_DIR = ".sanityops"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"

# Regex pattern for skill.md frontmatter (YAML frontmatter with name & description)
_SKILL_FRONTMATTER_RE = re.compile(
    r"^---\s*\n"
    r"(?:.*\n)*?"
    r"name\s*:\s*.+\n"
    r"(?:.*\n)*?"
    r"description\s*:\s*.+\n"
    r"(?:.*\n)*?"
    r"^---\s*$",
    re.MULTILINE,
)


class InspectConfigLoader:
    """Load and validate inspect_config.yaml, resolve all artifact paths to absolute."""

    def __init__(self, config_path: str | None = None):
        self._config_path = self._resolve_config_path(config_path)
        self._config = self._load_yaml()
        self._root_dir = Path.cwd()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load config, validate, and return resolved absolute paths.

        Returns:
            {
                "project_id": str,
                "prompts": List[str],   # absolute paths
                "tools": List[str],     # absolute paths
                "skills": List[str],    # absolute paths
            }
        """
        self._validate_structure()

        prompts = self._process_prompts()
        tools = self._process_tools()
        skills = self._process_skills()

        if not prompts and not tools and not skills:
            raise ValidationError(
                "At least one of (prompts / tools / skills) must be provided in config"
            )

        return {
            "project_id": self._config["project"]["id"],
            "prompts": prompts,
            "tools": tools,
            "skills": skills,
        }

    # ------------------------------------------------------------------
    # Config path resolution
    # ------------------------------------------------------------------

    def _resolve_config_path(self, config_path: str | None) -> Path:
        """Resolve config file path: explicit -> .sanityops/inspect_config.yaml -> error."""
        if config_path:
            p = Path(config_path).expanduser()
            if not p.exists():
                raise ValidationError(f"Config file not found: {config_path}")
            if not p.is_file():
                raise ValidationError(f"Config path is not a file: {config_path}")
            return p.resolve()

        # Fall back to default location in cwd
        default_path = Path.cwd() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
        if default_path.exists() and default_path.is_file():
            return default_path.resolve()

        raise ValidationError(
            f"Config file not found. Provide --config <path>, "
            f"or create one at .sanityops/{DEFAULT_CONFIG_FILE}"
        )

    # ------------------------------------------------------------------
    # YAML loading & structure validation
    # ------------------------------------------------------------------

    def _load_yaml(self) -> dict:
        try:
            with open(self._config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML in config file: {e}") from e
        except OSError as e:
            raise ValidationError(f"Cannot read config file: {e}") from e

        if not isinstance(data, dict):
            raise ValidationError("Config file must contain a YAML object at top level")

        return data

    def _validate_structure(self) -> None:
        # project.id is required
        project = self._config.get("project")
        if not isinstance(project, dict):
            raise ValidationError("Config must contain 'project' section")
        project_id = project.get("id")
        if not project_id:
            raise ValidationError("'project.id' is required (UUID)")
        # validate UUID format
        uuid_re = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        if not uuid_re.match(str(project_id)):
            raise ValidationError(f"'project.id' is not a valid UUID: {project_id}")

        # Validate model section if present
        self._validate_model_section()

    def _validate_model_section(self) -> None:
        """Validate model section if present.

        Rules:
        - If 'model' key absent: OK (no validation)
        - If 'model' present but not a dict: ValidationError
        - Required fields: provider, api_key, model_id (non-empty strings)
        - Optional: base_url (string, may be empty)
        """
        model = self._config.get("model")
        if model is None:
            return  # model section is optional

        if not isinstance(model, dict):
            raise ValidationError("'model' section must be a mapping (dict)")

        # Required fields - must be non-empty strings
        required_fields = ["provider", "api_key", "model_id"]
        for field in required_fields:
            value = model.get(field)
            if value is None:
                raise ValidationError(f"'model.{field}' is required when model section is present")
            if not isinstance(value, str):
                raise ValidationError(f"'model.{field}' must be a string")
            if value.strip() == "":
                raise ValidationError(f"'model.{field}' cannot be empty")

        # Optional field - just check it's a string if present
        base_url = model.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise ValidationError("'model.base_url' must be a string")

    # ------------------------------------------------------------------
    # Path resolution helper
    # ------------------------------------------------------------------

    def _resolve_file_path(self, file_str: str) -> Path:
        """Resolve a file path to absolute, handling relative paths against root dir."""
        p = Path(file_str).expanduser()
        if not p.is_absolute():
            p = self._root_dir / p
        return p.resolve()

    # ------------------------------------------------------------------
    # Prompts processing
    # ------------------------------------------------------------------

    def _process_prompts(self) -> list[str]:
        """Validate prompt files and return absolute paths."""
        entries = self._config.get("prompts", [])
        if entries is None:
            entries = []
        return self._process_file_entries(entries, "prompts")

    # ------------------------------------------------------------------
    # Tools processing
    # ------------------------------------------------------------------

    def _process_tools(self) -> list[str]:
        """Validate tool files and return absolute paths."""
        entries = self._config.get("tools", [])
        if entries is None:
            entries = []
        return self._process_file_entries(entries, "tools")

    def _process_file_entries(self, entries: list, label: str) -> list[str]:
        """Common logic for prompts and tools: each entry must be a readable file."""
        result: list[str] = []
        for i, entry in enumerate(entries):
            file_str = self._extract_file_value(entry, label, i)
            abs_path = self._resolve_file_path(file_str)
            if not abs_path.exists():
                raise ValidationError(
                    f"[{label}] file not found: {file_str} (resolved: {abs_path})"
                )
            if not abs_path.is_file():
                raise ValidationError(
                    f"[{label}] path is not a file: {file_str} (resolved: {abs_path})"
                )
            result.append(str(abs_path))
        return result

    # ------------------------------------------------------------------
    # Skills processing
    # ------------------------------------------------------------------

    def _process_skills(self) -> list[str]:
        """Validate skill files/directories and return absolute file paths.

        For directories, recursively find files matching skill.md format.
        """
        entries = self._config.get("skills", [])
        if entries is None:
            entries = []

        result: list[str] = []
        for i, entry in enumerate(entries):
            file_str = self._extract_file_value(entry, "skills", i)
            abs_path = self._resolve_file_path(file_str)

            if not abs_path.exists():
                raise ValidationError(
                    f"[skills] path not found: {file_str} (resolved: {abs_path})"
                )

            if abs_path.is_file():
                result.append(str(abs_path))
            elif abs_path.is_dir():
                result.extend(self._find_skill_files_in_dir(abs_path))
            else:
                raise ValidationError(
                    f"[skills] path is neither file nor directory: {file_str}"
                )

        return result

    def _find_skill_files_in_dir(self, dir_path: Path) -> list[str]:
        """Recursively find skill.md format files in a directory."""
        found: list[str] = []
        for item in sorted(dir_path.rglob("*")):
            # skip excluded directories
            if any(part in EXCLUDED_DIRS for part in item.parts):
                continue
            if not item.is_file():
                continue
            if self._is_skill_file(item):
                found.append(str(item.resolve()))
        return found

    def _is_skill_file(self, file_path: Path) -> bool:
        """Check if a file matches skill.md standard format.

        A skill.md file should:
        - Have .md extension
        - Contain YAML frontmatter with 'name' and 'description' fields
          OR be named 'skill.md'
        """
        # Must be a markdown file
        if file_path.suffix.lower() != ".md":
            return False

        # File named skill.md is always considered a skill file
        if file_path.name.lower() == "skill.md":
            return True

        # Otherwise check for valid frontmatter
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False

        return bool(_SKILL_FRONTMATTER_RE.search(content))

    # ------------------------------------------------------------------
    # Entry parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_file_value(entry, label: str, index: int) -> str:
        """Extract 'file' value from a YAML list entry."""
        if isinstance(entry, dict):
            file_val = entry.get("file")
            if not file_val:
                raise ValidationError(
                    f"[{label}] entry #{index} missing 'file' key"
                )
            return str(file_val)
        elif isinstance(entry, str):
            return entry
        else:
            raise ValidationError(
                f"[{label}] entry #{index} must be a string or object with 'file' key"
            )
