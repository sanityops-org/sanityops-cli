"""Runtime for the vendored inspect skills.

Vendored skills live inside the wheel (``src/sanityops_cli/skills/``). They must
be materialized to a real filesystem directory before ``SkillManager`` can scan
them (PyInstaller/zipimport have no scannable paths), then wired into a
``ToolRegistry`` via ``SkillTool`` for on-demand lazy loading by the agents.

**Coupling warning.** ``_rewrite_inspect_skill_for_cli`` adapts the standalone
``sanityops-inspect-only`` skill to the CLI pipeline with exact-string and
regex replacements, so it is coupled to the vendored skill's wording. When
``scripts/sync_skills.py`` refreshes the vendored content, run the tests:
``_replace_expected`` / ``_sub_expected`` log a warning for any pattern that
no longer matches, and
``tests/unit/inspect_pipeline/test_skill_runtime.py::TestRewriteDriftDetection``
fails when the current skill stops matching every guarded pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from importlib import resources
from pathlib import Path

from sanityops_agent.managers.skill import SkillManager
from sanityops_agent.tools.base import ToolResult
from sanityops_agent.tools.builtins.skill import SkillTool
from sanityops_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

EXPECTED_SKILLS = ("sanityops-inspect-only", "sanityops-extract-only")
CHECKLIST_NAME = "code-contract-checklist.v2.md"


def default_cache_root() -> Path:
    """Root of the content-keyed skill cache.

    Entries are keyed by content hash, so a skill update writes a new
    directory and the old one is never reused. Old entries are harmless and
    can be deleted at any time (``rm -rf ~/.cache/sanityops-cli/skills``);
    materialization recreates the current entry on the next run.
    """
    override = os.environ.get("SANITYOPS_SKILL_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "sanityops-cli" / "skills"


@contextmanager
def _packaged_skills_context() -> Iterator[Path]:
    """Yield the packaged ``skills/`` directory, keeping temp extraction alive.

    The yielded path is valid only inside the ``with`` block: for zipped or
    PyInstaller installs it points into a temporary extraction that is removed
    when the context exits, so copy whatever you need before leaving it.
    """
    with ExitStack() as stack:
        path: Path | None = None
        try:
            traversable = resources.files("sanityops_cli").joinpath("skills")
            if traversable.is_dir():
                path = stack.enter_context(resources.as_file(traversable))
        except (
            ModuleNotFoundError,
            FileNotFoundError,
            NotADirectoryError,
            IsADirectoryError,
        ):
            # NotADirectoryError is a defensive catch for filesystem importers.
            # IsADirectoryError is raised by resources.as_file(): Python < 3.12
            # cannot extract a directory traversable. Fall back to the source
            # tree when it exists.
            path = None

        if path is None:
            fallback = Path(__file__).resolve().parent.parent / "skills"
            if not fallback.is_dir():
                raise FileNotFoundError("vendored skills directory not found in package")
            path = fallback

        yield path


def packaged_skills_dir() -> Path:
    """Filesystem path of the packaged ``skills/`` directory when already on disk.

    Zipped/PyInstaller installs have no stable on-disk path here; use
    ``materialize_skills()``, which keeps the resource extraction alive while
    copying.
    """
    try:
        ref = resources.files("sanityops_cli").joinpath("skills")
        if isinstance(ref, Path) and ref.is_dir():
            return ref
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    fallback = Path(__file__).resolve().parent.parent / "skills"
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError(
        "vendored skills directory not found in package; "
        "use materialize_skills() for zipped installs"
    )


def dir_hash(directory: Path) -> str:
    """Stable content hash over all files in a directory (sorted relative paths)."""
    entries: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{path.relative_to(directory)}:{digest}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def _materialize_from_dir(src: Path, cache_root: Path | None = None) -> Path:
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


def materialize_skills(source: Path | None = None, cache_root: Path | None = None) -> Path:
    """Copy the packaged skills to a content-keyed cache directory and return it.

    Keyed by content hash so upgrades invalidate automatically; identical
    content reuses the existing directory (idempotent, safe across runs).
    """
    if source is not None:
        return _materialize_from_dir(source, cache_root=cache_root)
    with _packaged_skills_context() as src:
        return _materialize_from_dir(src, cache_root=cache_root)


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


_CLI_HEADER_SECTION = """7. **Report header (mandatory on every report and every stage-only report)** — exactly these provenance facts:
   - CLI-provided report header data (see the `header` section of the CLI Contract Appendix: `cli`, `framework`, `model`, `date`, `project`);
   - Review note: `Extraction and inspection were performed in separate agent contexts without an independent human or second-engine verifier.` (omit the extraction clause when extraction was skipped);
   - Specification baseline: `SanityOps Framework v1.1 (2026-10 release)`;
   - Fidelity tier per artifact set: `full` / `incomplete` / `summary` (per-object) — when `incomplete` or `summary`, state which rule families were not run.

   Never omit the report header to save tokens. Do not emit host-model labels, unofficial-result disclaimers, or upgrade prompts: this is the CLI's own inspection run."""


_CLI_OVERRIDE_NOTE = """

---

## CLI runtime override (sanityops-cli)

This skill is loaded inside the `sanityops-cli` inspect pipeline. Where the
standalone-skill framing above conflicts with the CLI contract appendix, the
appendix wins: the report header uses the CLI-provided provenance fields (no
host-model self-declaration, unofficial-result disclaimer, or upgrade prompt),
and every report section is delivered through the CLI's `write_report` tool.
"""


def _rewrite_skill_for_cli(name: str, text: str) -> str:
    """Adapt skill load text for the CLI runtime without mutating vendored files."""
    rewritten = _rewrite_hint_for_cli(text)
    if name == "sanityops-inspect-only":
        rewritten = _rewrite_inspect_skill_for_cli(rewritten) + _CLI_OVERRIDE_NOTE
    return rewritten


def _warn_missing_pattern(label: str, pattern: str) -> None:
    """Log a missing rewrite pattern with a bounded snippet for debugging."""
    snippet = pattern if len(pattern) <= 120 else pattern[:117] + "..."
    logger.warning(
        "Skill rewrite pattern not found (%s; pattern=%r); the vendored skill may have changed",
        label,
        snippet,
    )


def _replace_expected(text: str, old: str, new: str, label: str) -> str:
    """Replace an expected standalone phrase.

    The runtime logs a warning and keeps the original text when the pattern is
    missing, so a wording change does not crash an installed CLI. CI enforces
    the hard failure through ``TestRewriteDriftDetection``.
    """
    if old not in text:
        _warn_missing_pattern(label, old)
        return text
    return text.replace(old, new)


def _sub_expected(text: str, pattern: str, repl: str, label: str) -> str:
    """Regex variant of ``_replace_expected`` (same warn-and-continue contract)."""
    rewritten, count = re.subn(pattern, repl, text)
    if count == 0:
        _warn_missing_pattern(label, pattern)
    return rewritten


def _rewrite_inspect_skill_for_cli(text: str) -> str:
    """Adapt the standalone inspect-only skill to the CLI inspection pipeline.

    The vendored skill is written for a host model running it standalone.
    Inside the CLI it is executed by the inspection agent, so the standalone
    disclaimers, the host-model report header, and the upgrade pointers are
    replaced with the CLI contract.
    """
    text = _replace_expected(
        text,
        "— executed by you, the host model, applying the condensed checklists in "
        "`references/`. Zero dependencies: no CLI, no scripts, no network calls.",
        "— executed by the CLI's inspection agent, applying the condensed "
        "checklists in `references/`. The CLI provides the execution "
        "environment; the skill itself remains prompt-only.",
        "standalone introduction",
    )
    text = _replace_expected(
        text,
        "- The official `sanityops-cli` or any SaaS — condensed minimal rule sets, "
        "with the Permission stage as the exception (it runs the full 43-item set); "
        "still not the full specification.\n",
        "",
        "official-cli bullet",
    )
    text = _sub_expected(
        text,
        r", and an upgrade pointer \(full inspection via `sanityops-cli`[^)]*\)",
        "",
        "executive-summary upgrade pointer",
    )
    # Item 7 spans from its heading to the next numbered item; anchoring there
    # keeps the rewrite stable if the closing sentence is reworded.
    text = _sub_expected(
        text,
        r"7\. \*\*Report header \(mandatory on every report and every stage-only report\)\*\*"
        r"[\s\S]*?(?=\n\n8\. \*\*Self-verification statement\*\*)",
        _CLI_HEADER_SECTION,
        "report header",
    )
    text = _replace_expected(
        text,
        "the report header carries all six provenance facts (§6.7)",
        "the report header carries the CLI provenance facts (§6.7)",
        "Stage G header count",
    )
    text = _replace_expected(
        text,
        "the per-rule verdicts and Impact Cards are the detail behind it.",
        "the per-rule verdicts and impact-outlook mappings are the detail behind it.",
        "Impact Cards wording",
    )
    text = _replace_expected(
        text,
        "for raw or mixed documents run sanityops-inspector (extract + inspect) instead.",
        "for raw or mixed documents run the CLI extraction stage first.",
        "wrapper reference",
    )
    text = _replace_expected(
        text,
        "the report ends with a verdict-tally appendix",
        "the verdict-tally appendix is delivered in the CLI's `self_verification` section",
        "verdict-tally appendix",
    )
    text = _replace_expected(
        text,
        "that PASS and N/A lines are folded and the ledger is available on request, "
        "and that the result is a single-model self-audit rather than an official engine conclusion.",
        "that PASS and N/A lines are folded and the ledger is available on request. "
        "Do not add an unofficial-result disclaimer or a host-model label: this is the "
        "CLI's own inspection run.",
        "reader lead-in disclaimer",
    )
    text = _replace_expected(
        text,
        "scoring is out of scope for this inspector (full scoring lives in "
        "`sanityops-cli` / platform, which read the checklist's `score_weight`)",
        "scoring is out of scope for this inspector (the SanityOps Platform "
        "computes scores from the checklist's `score_weight`)",
        "scoring note",
    )
    text = _replace_expected(
        text,
        "Specification source: `sanityops-org/sanityops-framework` — the implementing "
        "CLI (`sanityops-org/sanityops-cli`, Apache 2.0) is NOT required by this skill.",
        "Specification source: `sanityops-org/sanityops-framework` — this skill is "
        "executed by the implementing CLI (`sanityops-org/sanityops-cli`, Apache 2.0).",
        "implementing-CLI note",
    )
    text = _sub_expected(
        text,
        r"\n## 10\. Further reading & upgrade\n[\s\S]*?(?=\n## Appendix A)",
        "",
        "further reading section",
    )
    return text


def rewrite_reference_for_cli(path: Path, text: str) -> str:
    """Adapt vendored reference checklists for the CLI static inspection."""
    if path.name != "relevance-map.v2.md":
        return text
    return _replace_expected(
        text,
        "**Recommended Validation — NOT run by this inspector**",
        "**Recommended Validation — not run in this CLI static inspection**",
        "relevance-map validation label",
    )


def _rewrite_hint_for_cli(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("- Read files: `cat "):
            out.append(
                line.replace("- Read files: `cat ", "- Read files: use the read tool on `")
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
