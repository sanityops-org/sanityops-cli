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
import re
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
        return ToolResult(content=_rewrite_skill_for_cli(name, text))


_CLI_HEADER_SECTION = """7. **报告头（每份报告和每份阶段报告均强制）**——恰好包含以下溯源事实：
   - CLI 提供的报告头数据（见系统契约附录中的 `header_data`，如 `cli`、`framework`、`model`、`date`、`project`）；
   - 复核说明：`Extraction and inspection were performed in separate agent contexts without an independent human or second-engine verifier.`（跳过提取时省略提取部分）；
   - 规范基线：`DeepLogic Framework v1.1 (2026-10 release)`；
   - 每个工件集的保真度层级：`full` / `incomplete` / `summary`（逐对象）——为 `incomplete` 或 `summary` 时说明未执行的规则族。

   不得为节省 token 省略报告头。"""


def _rewrite_skill_for_cli(name: str, text: str) -> str:
    """Adapt skill load text for the CLI runtime without mutating vendored files."""
    rewritten = _rewrite_hint_for_cli(text)
    if name == "sanityops-inspect-lite":
        rewritten = _rewrite_inspect_skill_for_cli(rewritten)
    return rewritten


def _rewrite_inspect_skill_for_cli(text: str) -> str:
    """Strip standalone-skill disclaimers, lite tags, and CLI upgrade prompts."""
    text = re.sub(
        r"由宿主模型执行，并使用 `references/` 中的浓缩检查清单。零依赖：无 CLI、无脚本、无网络调用。",
        "由 `sanityops-cli` 静态检查流水线执行，使用 `references/` 中的检查清单。",
        text,
    )
    text = re.sub(
        r"^- 官方 `sanityops-cli` 或任何 SaaS：[^\n]*\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"，并将每个判定标记为\s*\*\*“provisional \(lite\)”\*\*",
        "",
        text,
    )
    text = text.replace("保持零依赖姿态（无脚本、无额外工具）。", "")
    text = text.replace("宿主模型", "检查模型")
    text = text.replace(
        "本 Skill 没有程序引擎，因此仅形式化自检（ID 存在、P 合法、证据非空、格式正确）",
        "形式化自检（ID 存在、P 合法、证据非空、格式正确）",
    )
    text = re.sub(
        r"以及升级指引（通过 `sanityops-cli` 执行完整检查——见 https?://[^\s）]+）",
        "",
        text,
    )
    text = re.sub(
        r"^6\. \*\*无分数\*\*——[^\n]*",
        "6. **无分数**——本检查不计算数值分数，也不将发现映射到 AI 应用等级。输出仅为“检查项 → 严重度（P）→ 证据”。",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"7\. \*\*报告头（每份报告和每份阶段报告均强制）\*\*[\s\S]*?不得为节省 token 省略报告头[^\n]*",
        _CLI_HEADER_SECTION,
        text,
    )
    text = re.sub(
        r"——本 Skill 不要求实现 CLI（`sanityops-org/sanityops-cli`，Apache 2\.0）",
        "",
        text,
    )
    text = re.sub(
        r"\n## 10\. 延伸阅读与升级\n[\s\S]*?(?=\n## 附录 A)",
        "",
        text,
    )
    return text


def rewrite_reference_for_cli(path: Path, text: str) -> str:
    """Strip lite-only output markers when reading vendored reference checklists."""
    if path.name != "relevance-map.v2.md":
        return text
    text = text.replace('并标 "provisional (lite)"', "")
    text = text.replace(' "provisional (lite)"', "")
    text = text.replace('"provisional (lite)"', "")
    text = text.replace(
        "**Recommended Validation — NOT run by this lite inspector**",
        "**Recommended Validation — Not Executed in Static Inspect**",
    )
    text = text.replace("lite 从不运行 Quality 子集", "静态检查不运行运行时 Quality 子集")
    text = text.replace("**lite inspector v1 出范围**", "**当前静态检查范围外**")
    text = text.replace("出 lite 范围", "范围说明")
    return text


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
