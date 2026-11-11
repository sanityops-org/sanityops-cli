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

"""Runtime for the vendored inspect skills.

Vendored skills live inside the wheel (``src/sanityops_cli/skills/``). They must
be materialized to a real filesystem directory before ``SkillManager`` can scan
them (PyInstaller/zipimport have no scannable paths), then wired into a
``ToolRegistry`` via ``SkillTool`` for on-demand lazy loading by the agents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from importlib import resources
from pathlib import Path

from sanityops_agent.managers.skill import SkillManager
from sanityops_agent.tools.base import ToolResult
from sanityops_agent.tools.builtins.skill import SkillTool
from sanityops_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

EXPECTED_SKILLS = ("sanityops-inspect-lite", "pre-inspect-extract")
CHECKLIST_NAME = "code-contract-checklist.v2.md"


def default_cache_root() -> Path:
    override = os.environ.get("SANITYOPS_SKILL_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "sanityops-cli" / "skills"


def packaged_skills_dir() -> Path:
    """Filesystem path of the packaged ``skills/`` directory."""
    try:
        traverse = resources.as_file(resources.files("sanityops_cli").joinpath("skills"))
        path = traverse.__enter__()
        traverse.__exit__(None, None, None)  # copy out below; path needn't outlive
        if path.is_dir():
            return path
    except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError):
        pass
    fallback = Path(__file__).resolve().parent.parent / "skills"
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError("vendored skills directory not found in package")


def dir_hash(directory: Path) -> str:
    """Stable content hash over all files in a directory (sorted relative paths)."""
    entries: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{path.relative_to(directory)}:{digest}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def materialize_skills(source: Path | None = None, cache_root: Path | None = None) -> Path:
    """Copy the packaged skills to a content-keyed cache directory and return it.

    Keyed by content hash so upgrades invalidate automatically; identical
    content reuses the existing directory (idempotent, safe across runs).
    """
    src = source if source is not None else packaged_skills_dir()
    root = cache_root if cache_root is not None else default_cache_root()
    key = dir_hash(src)[:12]
    target = root / key

    if (target / "VERSION.json").is_file() and dir_hash(target) == dir_hash(src):
        return target

    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".skills-{key}-", dir=root))
    try:
        shutil.copytree(src, staging / "content")
        final = root / f".skills-{key}-final"
        if final.exists():
            shutil.rmtree(final)
        (staging / "content").rename(final)
        staging.rmdir()
        if target.exists():
            shutil.rmtree(target)
        final.rename(target)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def validate_vendor(skills_dir: Path) -> list[str]:
    """Cross-check vendored skills against VERSION.json; returns warnings."""
    warnings: list[str] = []
    version_file = skills_dir / "VERSION.json"
    if not version_file.is_file():
        return [f"VERSION.json missing under {skills_dir}"]

    try:
        manifest = json.loads(version_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"VERSION.json unreadable: {exc}"]

    items = manifest.get("items", {})

    for skill_name in EXPECTED_SKILLS:
        skill_md = skills_dir / skill_name / "SKILL.md"
        if not skill_md.is_file():
            warnings.append(f"skill '{skill_name}' missing")
            continue
        recorded = items.get(skill_name, {})
        recorded_version = recorded.get("version")
        if recorded_version and recorded.get("type") == "synced":
            frontmatter_version = _frontmatter_version(skill_md)
            if frontmatter_version and frontmatter_version != recorded_version:
                warnings.append(
                    f"skill '{skill_name}' frontmatter version {frontmatter_version} "
                    f"!= VERSION.json {recorded_version}"
                )

    if not (skills_dir / CHECKLIST_NAME).is_file():
        warnings.append(f"{CHECKLIST_NAME} missing")
    return warnings


def _frontmatter_version(skill_md: Path) -> str | None:
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip('"')
        if stripped and not stripped.startswith("---") and ":" not in stripped:
            break  # frontmatter ended
    return None


class CliSkillTool(SkillTool):
    """SkillTool whose load hint points at ``read`` instead of bash.

    The framework hint suggests ``cat``/``rg``/``python``/``find``; the CLI
    registers none of those, so loaded skills would point the agent at tools
    it does not have. Only the hint is rewritten — the skill body follows it.
    """

    name = "skill"
    description = (
        "Navigate skills: list available skills and load skill documents "
        "(use the read tool with absolute paths to read reference files)"
    )

    async def _load(self, manager, kwargs: dict):  # noqa: ANN001 - matches parent
        name = kwargs.get("name")
        if not name:
            return ToolResult(
                content="Error: name is required for load operation",
                success=False,
                error="name is required for load operation",
            )
        text = manager.load_full_text_with_path_hint(name)
        if text is None:
            return ToolResult(
                content=f"Error: skill '{name}' not found",
                success=False,
                error=f"Skill not found: {name}",
            )
        return ToolResult(content=_rewrite_hint_for_cli(text))


def _rewrite_hint_for_cli(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("- Read files: `cat "):
            out.append(
                line.replace("- Read files: `cat ", "- Read files: use the read tool on `")
                .replace("/references/xxx.md`", "/references/xxx.md` (read tool)")
                .rstrip("\n")
                + "\n"
            )
        elif line.startswith("- Search content: `rg "):
            out.append(
                "- Search content: read the relevant file under the skill's"
                " `references/` with the read tool\n"
            )
        elif line.startswith("- Execute scripts: `python "):
            out.append("- Scripts: this CLI does not execute skill scripts\n")
        elif line.startswith("- List structure: `find "):
            out.append(
                "- List structure: every file under the skill directory can be"
                " read directly with the read tool using its absolute path\n"
            )
        else:
            out.append(line)
    return "".join(out)


def attach_skill_tools(registry: ToolRegistry, skills_dir: Path) -> SkillManager:
    """Scan ``skills_dir`` and wire SkillManager + SkillTool into ``registry``."""
    manager = SkillManager(skills_dir=str(skills_dir))
    found = {s["name"] for s in manager.describe_available()}
    missing = [name for name in EXPECTED_SKILLS if name not in found]
    if missing:
        logger.warning("skills not found after materialization: %s", missing)
    registry.context.set("skill_manager", manager)
    registry.register(CliSkillTool())
    return manager
