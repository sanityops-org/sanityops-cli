#!/usr/bin/env python3
"""Update the vendored inspect skills and open a pull request on GitHub.

Invoked by the downstream GitHub Actions workflow:
1. Clones the upstream skill repository (public, no credentials required).
2. Compares upstream HEAD with the local ``skills/VERSION.json``.
3. Copies the skill content into ``src/sanityops_cli/skills/``.
4. Runs the quality gates (``ruff check`` and ``pytest``).
5. Creates a bot branch and opens a pull request targeting ``main``.

Usage:
    python scripts/ci_sync_skills.py [--dry-run] [--force] [--skip-tests]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = REPO_ROOT / "src" / "sanityops_cli" / "skills"
VERSION_FILE = DEST_DIR / "VERSION.json"

DEFAULT_UPSTREAM_URL = "https://github.com/sanityops-org/sanityops-inspect-lite.git"
DEFAULT_BRANCH = "main"


def _redact_secrets(text: str, *tokens: str) -> str:
    """Scrub raw tokens and authenticated URLs from log output."""
    if not text:
        return ""
    for token in tokens:
        if token:
            text = text.replace(token, "[REDACTED]")
            text = text.replace(quote(token, safe=""), "[REDACTED]")
    text = re.sub(r"https?://[^@\s]+@", "https://[REDACTED]@", text)
    return text


def _run(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute a shell command with captured output."""
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _log(msg: str) -> None:
    print(f"[Skill Update] {msg}", flush=True)


def _git_config_if_missing() -> None:
    """Ensure a git identity exists for the bot commit."""
    for key, value in (("user.name", "sanityops-bot"), ("user.email", "bot@sanityops.org")):
        try:
            _run(["git", "config", key])
        except subprocess.CalledProcessError:
            _run(["git", "config", key, value])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream-url",
        default=os.environ.get("UPSTREAM_SKILL_URL", DEFAULT_UPSTREAM_URL),
        help=f"Git URL of the upstream skill repository (default: {DEFAULT_UPSTREAM_URL})",
    )
    parser.add_argument(
        "--upstream-branch",
        default=os.environ.get("UPSTREAM_BRANCH", DEFAULT_BRANCH),
        help="Upstream branch to track (default: main)",
    )
    parser.add_argument(
        "--target-branch",
        default=os.environ.get("TARGET_BRANCH", DEFAULT_BRANCH),
        help="Base branch for the pull request (default: main)",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="Target GitHub repository (owner/name). Defaults to $GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub token used to open the pull request. Defaults to $GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Clone, update, and test without creating a branch or pull request.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update even when the upstream commit matches VERSION.json.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip ruff and pytest quality gates (use with caution).",
    )
    return parser.parse_args()


def run_quality_gates() -> None:
    """Run lint and the full test suite before creating a branch."""
    _log("Running quality gates: ruff check...")
    res = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format=concise", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        _log("ruff check failed:")
        print(res.stdout)
        print(res.stderr)
        sys.exit(1)

    _log("Running quality gates: pytest...")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        _log("pytest failed:")
        print(res.stdout)
        print(res.stderr)
        sys.exit(1)

    _log("Quality gates passed (ruff + pytest green).")


def _open_pull_request(repo: str, token: str, head: str, base: str, title: str, body: str) -> str:
    """Create a pull request through the GitHub REST API; return its URL."""
    payload = json.dumps({"title": title, "head": head, "base": base, "body": body}).encode()
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "sanityops-cli-skill-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode())
            return str(data.get("html_url", ""))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 422 and "A pull request already exists" in detail:
            _log(f"A pull request already exists for branch '{head}'.")
            return ""
        raise RuntimeError(f"GitHub API error ({exc.code}): {detail}") from exc


def main() -> None:
    args = parse_args()

    _log("Starting vendored skill update...")
    _log(f"Upstream: {args.upstream_url} (branch: {args.upstream_branch})")
    _log(f"Target branch: {args.target_branch}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        _log("Cloning upstream skill repository...")
        clone_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            args.upstream_branch,
            args.upstream_url,
            str(temp_path),
        ]
        res = subprocess.run(clone_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            _log(f"Failed to clone upstream repository: {_redact_secrets(res.stderr, args.token)}")
            sys.exit(1)

        upstream_commit = _run(["git", "rev-parse", "HEAD"], cwd=temp_path).stdout.strip()
        _log(f"Upstream HEAD commit: {upstream_commit}")

        if not args.force and VERSION_FILE.is_file():
            try:
                manifest = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
                current_commit = manifest.get("source", {}).get("commit", "")
                if current_commit == upstream_commit:
                    _log(f"Vendored skills are already at {upstream_commit[:8]}. Nothing to do.")
                    sys.exit(0)
            except Exception as exc:
                _log(f"Could not read existing VERSION.json ({exc}); continuing.")

        _log("Updating vendored skills...")
        sync_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "sync_skills.py"),
            "--source",
            str(temp_path),
        ]
        if args.force:
            sync_cmd.append("--force")
        res = subprocess.run(sync_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            _log(f"scripts/sync_skills.py failed:\n{res.stderr}")
            sys.exit(1)
        print(res.stdout.strip())

    diff_check = _run(["git", "diff", "--quiet", "src/sanityops_cli/skills/"], check=False)
    status_check = _run(["git", "status", "--porcelain", "src/sanityops_cli/skills/"])
    if diff_check.returncode == 0 and not status_check.stdout.strip():
        _log("No file changes detected. Already up-to-date.")
        sys.exit(0)

    if not VERSION_FILE.is_file():
        _log("VERSION.json was not generated.")
        sys.exit(1)

    manifest = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    skill_version = (
        manifest.get("items", {}).get("sanityops-inspect-lite", {}).get("version", "unknown")
    )
    short_sha = upstream_commit[:8]
    branch_name = f"bot/sync-inspect-skills-v{skill_version}-{short_sha}"

    _log(f"Skill version: {skill_version} (commit {short_sha})")
    _log(f"Target branch name: {branch_name}")

    existing = _run(["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch_name}"], check=False)
    if existing.stdout.strip():
        _log(f"Remote branch '{branch_name}' already exists; skipping.")
        sys.exit(0)

    if not args.skip_tests:
        run_quality_gates()
    else:
        _log("Skipping quality gates (--skip-tests).")

    _git_config_if_missing()

    if args.dry_run:
        _log("DRY-RUN mode:")
        _log(f"  Would create branch: {branch_name}")
        _log("  Would commit changes under src/sanityops_cli/skills/")
        _log(f"  Would open a pull request targeting {args.target_branch}")
        sys.exit(0)

    _log(f"Creating branch {branch_name}...")
    _run(["git", "checkout", "-b", branch_name])
    _run(["git", "add", "src/sanityops_cli/skills/"])

    title = f"chore(skills): update vendored inspect skills to v{skill_version}"
    body_lines = [
        f"Vendored inspect skill content updated to version {skill_version}.",
        "",
        f"- Content commit: `{upstream_commit}`",
        "- Quality gates: `ruff check` and `pytest` passed",
    ]
    _run(["git", "commit", "-m", title, "-m", "\n".join(body_lines)])

    _log(f"Pushing branch {branch_name}...")
    push = _run(["git", "push", "origin", branch_name], check=False)
    if push.returncode != 0:
        _log(f"git push failed:\n{_redact_secrets(push.stderr, args.token)}")
        sys.exit(1)

    if not args.repo:
        _log("GITHUB_REPOSITORY is not set; branch pushed without a pull request.")
        sys.exit(0)

    if not args.token:
        _log("GITHUB_TOKEN is not set; branch pushed without a pull request.")
        sys.exit(0)

    pr_body = "\n".join(
        [
            f"Updates the vendored inspect skills to version **{skill_version}**.",
            "",
            f"- Content commit: `{upstream_commit}`",
            "- `ruff check` and `pytest` passed before the branch was created.",
            "",
            "Review the skill diff and merge when ready.",
        ]
    )
    try:
        pr_url = _open_pull_request(
            args.repo, args.token, branch_name, args.target_branch, title, pr_body
        )
    except Exception as exc:
        _log(f"Could not open a pull request: {_redact_secrets(str(exc), args.token)}")
        sys.exit(1)

    if pr_url:
        _log(f"Pull request: {pr_url}")


if __name__ == "__main__":
    main()
