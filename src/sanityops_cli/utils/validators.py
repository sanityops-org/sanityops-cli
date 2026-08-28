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
"""local validators for sanityops-cli"""

import json
import os
from pathlib import Path

from sanityops_cli.exceptions.base_exceptions import ValidationError

# Exclude directories
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

def validate_inspect_directory(directory: str) -> None:
    """validate inspect directory"""
    import os
    from pathlib import Path

    path = Path(directory)

    # folder exists
    if not path.exists():
        raise ValidationError(f"Folder does not exist: {directory}")

    # is a directory
    if not path.is_dir():
        raise ValidationError(f"Path is not a directory: {directory}")

    # folder is readable
    if not os.access(path, os.R_OK | os.X_OK):
        raise ValidationError(f"Folder is not readable: {directory}")

    # folder is not empty
    try:
        items = list(path.iterdir())
        # Exclude certain directories from the list of items
        items = [i for i in items if i.name not in EXCLUDED_DIRS]
        if not items:
            raise ValidationError(f"Folder is empty: {directory}")
    except PermissionError:
        raise ValidationError(f"Folder is not readable: {directory}") from None


def validate_artifact_inputs(
    skills: list[str],
    tools: list[str],
    prompts: list[str],
    level: str,
) -> None:
    """validate artifact inputs for inspect command"""
    if not skills and not tools and not prompts:
        raise ValidationError("at least one of (--skill / --tools / --prompt) must be provided")

    for label, paths in [("Skill", skills), ("Tools Schema", tools), ("System Prompt", prompts)]:
        for path_str in paths:
            p = Path(path_str)
            if not p.exists():
                raise ValidationError(f"Path does not exist: {path_str}")

            if label == "Skill":
                if p.is_file():
                    if not os.access(p, os.R_OK):
                        raise ValidationError(f"File is not readable: {path_str}")
                    if p.stat().st_size == 0:
                        raise ValidationError(f"File is empty: {path_str}")
                elif p.is_dir():
                    if not os.access(p, os.R_OK):
                        raise ValidationError(f"Directory is not readable: {path_str}")
                else:
                    raise ValidationError(f"Skill path must be a file or directory: {path_str}")
            else:
                if not p.is_file():
                    raise ValidationError(f"Path is not a file: {path_str}")
                if not os.access(p, os.R_OK):
                    raise ValidationError(f"File is not readable: {path_str}")
                if p.stat().st_size == 0:
                    raise ValidationError(f"File is empty: {path_str}")

    for path_str in tools:
        try:
            content = Path(path_str).read_text(encoding="utf-8")
        except Exception:
            raise ValidationError(f"File is not readable: {path_str}") from None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            raise ValidationError(f"Tools Schema is not valid JSON: {path_str}") from None
        if not isinstance(parsed, (dict, list)):
            raise ValidationError(f"Tools Schema must be a JSON object or array: {path_str}")

    if level.upper() not in ("L1", "L2", "L3"):
        raise ValidationError(f"Level must be one of L1/L2/L3, current value: {level}")


