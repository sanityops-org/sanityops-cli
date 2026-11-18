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

# Placeholder project ID (project not yet bound)
PROJECT_ID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"

# UUID validation regex (compiled once at module load for efficiency)
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}" r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _has_valid_frontmatter(content: str) -> bool:
    """Check if content has valid skill.md frontmatter.

    Simple and safe check: looks for --- delimited block containing
    both 'name:' and 'description:' fields. Avoids regex backtracking.
    """
    # Must start with ---
    if not content.startswith("---"):
        return False

    # Find closing ---
    # Limit search to first 4KB to avoid DoS
    end_marker = content.find("\n---", 4)
    if end_marker == -1:
        return False

    # Extract frontmatter block
    frontmatter = content[4:end_marker]

    # Check for required fields (simple string search, no regex)
    has_name = "\nname:" in frontmatter or frontmatter.startswith("name:")
    has_desc = "\ndescription:" in frontmatter or frontmatter.startswith("description:")

    return has_name and has_desc


def read_file_with_encoding_fallback(path: Path) -> str | None:
    """Read file content with UTF-8 to GBK encoding fallback.

    Windows users often save config files as GBK (ANSI in Notepad).
    This function tries UTF-8 first, then falls back to GBK.

    Args:
        path: Path to the file to read.

    Returns:
        File content as string, or None if both encodings fail.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="gbk")
        except UnicodeDecodeError:
            return None
    except OSError:
        return None


class InspectConfigLoader:
    """Load and validate inspect_config.yaml, resolve all artifact paths to absolute."""

    def __init__(self, config_path: str | None = None, require_project_id: bool = True):
        """Initialize the config loader.

        Args:
            config_path: Optional path to config file. If None, uses default location.
            require_project_id: If True, validate that project.id is a valid non-placeholder UUID.
                Set to False when loading config for commands that don't need project binding.
        """
        self._config_path = self._resolve_config_path(config_path)
        self._config = self._load_yaml()
        self._root_dir = self._derive_root_dir(self._config_path)
        self._require_project_id = require_project_id

    @staticmethod
    def _derive_root_dir(config_file: Path) -> Path:
        """Derive project root from inspect_config.yaml location."""
        if config_file.parent.name == DEFAULT_CONFIG_DIR:
            return config_file.parent.parent
        return config_file.parent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def config_path(self) -> Path:
        """返回本次实际加载的配置文件绝对路径。"""
        return self._config_path

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

        # project_id may be None/placeholder if not bound
        project_id = self._config.get("project", {}).get("id")
        if project_id == "00000000-0000-0000-0000-000000000000":
            project_id = None

        return {
            "project_id": project_id,
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
        """Load YAML config file with encoding auto-detection.

        On Windows, config files are often saved with GBK encoding (ANSI in Notepad).
        We try UTF-8 first (standard), then fall back to GBK for compatibility.
        """
        content = read_file_with_encoding_fallback(self._config_path)
        if content is None:
            raise ValidationError(
                f"Cannot read config file: {self._config_path}. Expected UTF-8 or GBK encoding."
            )

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML in config file: {e}") from e

        if not isinstance(data, dict):
            raise ValidationError("Config file must contain a YAML object at top level")

        return data

    def _validate_structure(self) -> None:
        # project section is required
        project = self._config.get("project")
        if not isinstance(project, dict):
            raise ValidationError("Config must contain 'project' section")

        if self._require_project_id:
            # When strict validation is enabled, project.id must be a valid non-placeholder UUID
            project_id = project.get("id")
            if not project_id:
                raise ValidationError("'project.id' is required (UUID)")
            # validate UUID format
            if not _UUID_RE.match(str(project_id)):
                raise ValidationError(f"'project.id' is not a valid UUID: {project_id}")
            # Check it's not the placeholder UUID
            if str(project_id) == "00000000-0000-0000-0000-000000000000":
                raise ValidationError(
                    "'project.id' is still a placeholder. "
                    "Run 'sanityops-cli project create <name>' or 'sanityops-cli project bind <id>'"
                )
        else:
            # When not requiring project_id, just check the format if it's set
            project_id = project.get("id")
            if project_id and str(project_id) != "00000000-0000-0000-0000-000000000000":
                if not _UUID_RE.match(str(project_id)):
                    raise ValidationError(f"'project.id' is not a valid UUID: {project_id}")

        # Validate model section if present
        self._validate_model_section()

    def _validate_model_section(self) -> None:
        """Validate model section if present.

        Rules:
        - If 'model' key absent: OK (no validation)
        - If 'model' present but not a dict: ValidationError
        - Optional: context_window (positive integer when non-null)
        - Optional: enable_thinking (boolean when non-null)
        - Credential fields (provider, api_key, model_id, base_url):
          If any credential key is present in 'model', provider/api_key/model_id
          must all be non-empty strings. If only non-credential fields such as
          'context_window' or 'enable_thinking' are specified, credentials fall
          back to env vars.
        """
        model = self._config.get("model")
        if model is None:
            return  # model section is optional

        if not isinstance(model, dict):
            raise ValidationError("'model' section must be a mapping (dict)")

        if "context_window" in model and model.get("context_window") is not None:
            cw = model.get("context_window")
            if isinstance(cw, bool) or not isinstance(cw, int) or cw <= 0:
                raise ValidationError("'model.context_window' must be a positive integer")

        if "enable_thinking" in model and model.get("enable_thinking") is not None:
            if not isinstance(model.get("enable_thinking"), bool):
                raise ValidationError("'model.enable_thinking' must be a boolean")

        credential_fields = ("provider", "api_key", "model_id", "base_url")
        if not any(field in model for field in credential_fields):
            return

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

        provider_val = str(model.get("provider", "")).strip().lower()
        supported_providers = {"openai", "anthropic", "dashscope"}
        if provider_val not in supported_providers:
            raise ValidationError(
                f"Unsupported 'model.provider': '{model.get('provider')}'. "
                f"Supported providers: {', '.join(sorted(supported_providers))}"
            )

        # Optional field - just check it's a string if present
        base_url = model.get("base_url")
        if base_url is not None:
            if not isinstance(base_url, str):
                raise ValidationError("'model.base_url' must be a string")
            # Validate URL format if non-empty
            if base_url.strip():
                import urllib.parse

                try:
                    parsed = urllib.parse.urlparse(base_url)
                    if parsed.scheme not in ("http", "https"):
                        raise ValidationError(
                            f"'model.base_url' must use http:// or https:// scheme: {base_url}"
                        )
                    if not parsed.netloc:
                        raise ValidationError(
                            f"'model.base_url' must have a valid host: {base_url}"
                        )
                except Exception as e:
                    raise ValidationError(f"'model.base_url' is not a valid URL: {e}") from e

    # ------------------------------------------------------------------
    # Path resolution helper
    # ------------------------------------------------------------------

    def _resolve_file_path(self, file_str: str) -> Path:
        """Resolve a file path to absolute, handling relative paths against root dir.

        Note: Symlinks are resolved to their target paths. If you use symlinks
        pointing outside the project directory, ensure those paths are intended
        and accessible. The CLI does not restrict symlink targets.
        """
        p = Path(file_str).expanduser()
        if not p.is_absolute():
            candidate = (self._root_dir / p).resolve()
            if candidate.exists() or self._root_dir == Path.cwd():
                return candidate
            cwd_candidate = (Path.cwd() / p).resolve()
            if cwd_candidate.exists():
                return cwd_candidate
            return candidate
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
                raise ValidationError(f"[skills] path not found: {file_str} (resolved: {abs_path})")

            if abs_path.is_file():
                result.append(str(abs_path))
            elif abs_path.is_dir():
                result.extend(self._find_skill_files_in_dir(abs_path))
            else:
                raise ValidationError(f"[skills] path is neither file nor directory: {file_str}")

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
        # Read only the first chunk - frontmatter always sits at the top of the file
        try:
            content = file_path.read_bytes()[:4096].decode("utf-8", errors="ignore")
        except OSError:
            # File unreadable (permissions, disk error, etc.) - skip it
            # Note: We intentionally return False without logging to avoid noise
            # during skill scanning. Permission issues should be caught elsewhere
            # when the file is actually used, not during discovery.
            return False

        return _has_valid_frontmatter(content)

    # ------------------------------------------------------------------
    # Entry parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_file_value(entry, label: str, index: int) -> str:
        """Extract 'file' value from a YAML list entry."""
        if isinstance(entry, dict):
            file_val = entry.get("file")
            if not file_val:
                raise ValidationError(f"[{label}] entry #{index} missing 'file' key")
            return str(file_val)
        elif isinstance(entry, str):
            return entry
        else:
            raise ValidationError(
                f"[{label}] entry #{index} must be a string or object with 'file' key"
            )
