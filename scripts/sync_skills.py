#!/usr/bin/env python3
"""Sync vendor skills from the sanityops-inspect-lite repository into the CLI package.

Copies the ``sanityops-inspect-lite`` skill (SKILL.md + references/) and the
code-contract checklist into ``src/sanityops_cli/skills/`` and records the
source provenance (remote URL, commit SHA, content hashes) in ``VERSION.json``.

Both skill directories are vendored from upstream; ``--check`` verifies that
the vendored content has not drifted from the recorded state.

Usage:
    python scripts/sync_skills.py --source /path/to/sanityops-inspect-lite
    python scripts/sync_skills.py --source ... --check   # CI drift check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = REPO_ROOT / "src" / "sanityops_cli" / "skills"
VERSION_FILE = DEST_DIR / "VERSION.json"

# Path inside the source repo holding the skill packages.
SOURCE_SKILL_REL = "plugins/sanityops-inspect-lite/skills/sanityops-inspect-lite"
SOURCE_EXTRACT_SKILL_REL = "plugins/sanityops-inspect-lite/skills/pre-inspect-extract"
SOURCE_CHECKLIST_CANDIDATES = (
    "plugins/sanityops-inspect-lite/skills/sanityops-inspect-lite/references/"
    "code-contract-checklist.v2.md",
    "plugins/sanityops-inspect-lite/skills/sanityops-inspect-lite/references/"
    "code-contract-checklist.md",
)
# Vendored names inside src/sanityops_cli/skills/.
VENDORED_SKILL_DIR = "sanityops-inspect-lite"
VENDORED_EXTRACT_DIR = "pre-inspect-extract"
VENDORED_CHECKLIST_NAME = "code-contract-checklist.v2.md"

SYNCED_ITEMS = (VENDORED_SKILL_DIR, VENDORED_EXTRACT_DIR, VENDORED_CHECKLIST_NAME)


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean_url(url: str) -> str:
    """Strip authentication credentials (e.g. tokens/passwords) from URL."""
    parsed = urlsplit(url)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    return url


def _dir_hash(directory: Path) -> str:
    """Stable hash over all files in a directory (sorted relative paths)."""
    entries: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            entries.append(f"{path.relative_to(directory)}:{_sha256_of(path.read_bytes())}")
    return _sha256_of("\n".join(entries).encode())


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _frontmatter_version(skill_md: Path) -> str | None:
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip().strip('"')
        if stripped and not stripped.startswith("---") and ":" not in stripped:
            break  # frontmatter ended
    return None


def sync(source: Path, force: bool = False) -> bool:
    skill_src = source / SOURCE_SKILL_REL
    checklist_src = None
    for cand in SOURCE_CHECKLIST_CANDIDATES:
        p = source / cand
        if p.is_file():
            checklist_src = p
            break
    if not (skill_src / "SKILL.md").is_file():
        sys.exit(f"error: skill not found at {skill_src}")
    if checklist_src is None:
        sys.exit(f"error: checklist not found in candidates under {source}")

    upstream_commit = _git(["rev-parse", "HEAD"], source)
    if not force and VERSION_FILE.is_file():
        try:
            current_manifest = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            if current_manifest.get("source", {}).get("commit") == upstream_commit:
                print(f"already up-to-date at commit {upstream_commit[:12]}")
                return False
        except Exception:
            pass

    # Vendor the skill directory (clean replace).
    skill_dest = DEST_DIR / VENDORED_SKILL_DIR
    if skill_dest.exists():
        import shutil

        shutil.rmtree(skill_dest)
    skill_dest.mkdir(parents=True)
    for item in skill_src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(skill_src)
            target = skill_dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())

    # Vendor pre-inspect-extract skill directory (clean replace if present in source).
    extract_src = source / SOURCE_EXTRACT_SKILL_REL
    extract_dest = DEST_DIR / VENDORED_EXTRACT_DIR
    extract_version = "unknown"
    has_extract = False
    if extract_src.is_dir() and (extract_src / "SKILL.md").is_file():
        has_extract = True
        if extract_dest.exists():
            import shutil

            shutil.rmtree(extract_dest)
        extract_dest.mkdir(parents=True)
        for item in extract_src.rglob("*"):
            if item.is_file():
                rel = item.relative_to(extract_src)
                target = extract_dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(item.read_bytes())
        extract_version = _frontmatter_version(extract_dest / "SKILL.md") or "unknown"

    # Vendor the checklist under its v2 name.
    (DEST_DIR / VENDORED_CHECKLIST_NAME).write_bytes(checklist_src.read_bytes())

    version = _frontmatter_version(skill_dest / "SKILL.md") or "unknown"
    raw_url = _git(["remote", "get-url", "origin"], source)
    clean_url = _clean_url(raw_url)
    manifest_items = {
        VENDORED_SKILL_DIR: {
            "type": "synced",
            "version": version,
            "sha256": _dir_hash(skill_dest),
        },
        "code-contract-checklist.v2": {
            "type": "synced",
            "version": "v2",
            "sha256": _sha256_of(checklist_src.read_bytes()),
        },
    }
    if has_extract:
        manifest_items[VENDORED_EXTRACT_DIR] = {
            "type": "synced",
            "version": extract_version,
            "sha256": _dir_hash(extract_dest),
        }
    else:
        manifest_items[VENDORED_EXTRACT_DIR] = {"type": "local"}

    manifest = {
        "source": {
            "url": clean_url,
            "commit": upstream_commit,
            "synced_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "items": manifest_items,
    }
    VERSION_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"synced from {manifest['source']['commit'][:12]} ({manifest['source']['url']})")
    print(f"  skill:     {skill_dest} (version {version})")
    if has_extract:
        print(f"  extract:   {extract_dest} (version {extract_version})")
    print(f"  checklist: {DEST_DIR / VENDORED_CHECKLIST_NAME}")
    return True


def check(source: Path | None = None) -> int:
    if not VERSION_FILE.is_file():
        print(f"drift: {VERSION_FILE} missing — run sync_skills.py")
        return 1
    manifest = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    items = manifest.get("items", {})
    problems: list[str] = []

    recorded_skill = items.get(VENDORED_SKILL_DIR, {})
    current_skill_hash = _dir_hash(DEST_DIR / VENDORED_SKILL_DIR)
    if recorded_skill.get("sha256") != current_skill_hash:
        problems.append(f"{VENDORED_SKILL_DIR} content drift")

    recorded_extract = items.get(VENDORED_EXTRACT_DIR, {})
    if recorded_extract.get("type") == "synced":
        extract_path = DEST_DIR / VENDORED_EXTRACT_DIR
        if extract_path.is_dir():
            if recorded_extract.get("sha256") != _dir_hash(extract_path):
                problems.append(f"{VENDORED_EXTRACT_DIR} content drift")
        else:
            problems.append(f"{VENDORED_EXTRACT_DIR} missing")

    recorded_checklist = items.get("code-contract-checklist.v2", {})
    checklist_path = DEST_DIR / VENDORED_CHECKLIST_NAME
    if checklist_path.is_file():
        if recorded_checklist.get("sha256") != _sha256_of(checklist_path.read_bytes()):
            problems.append(f"{VENDORED_CHECKLIST_NAME} content drift")
    else:
        problems.append(f"{VENDORED_CHECKLIST_NAME} missing")

    if source is not None:
        if not source.is_dir():
            problems.append(f"source path is not a valid directory: {source}")
        else:
            upstream_commit = _git(["rev-parse", "HEAD"], source)
            if manifest.get("source", {}).get("commit") != upstream_commit:
                problems.append(
                    f"upstream moved: VERSION.json pinned at "
                    f"{manifest.get('source', {}).get('commit', '?')[:12]}, "
                    f"source repo at {upstream_commit[:12]}"
                )

    for problem in problems:
        print(f"drift: {problem}")
    if not problems:
        print("vendor state clean")
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the sanityops-inspect-lite repository checkout",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify vendored content matches VERSION.json instead of syncing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if source commit matches recorded commit",
    )
    args = parser.parse_args()

    source = args.source.resolve() if args.source else None
    if args.check:
        sys.exit(check(source if source and source.is_dir() else None))
    if not source.is_dir():
        sys.exit(f"error: source repo not found: {source}")
    synced = sync(source, force=args.force)
    sys.exit(0 if synced else 0)


if __name__ == "__main__":
    main()
