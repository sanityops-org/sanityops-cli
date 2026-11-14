"""Unit tests for the skill update workflow and sync scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts.ci_sync_skills import (
    DEFAULT_UPSTREAM_URL,
    _redact_secrets,
    parse_args,
)
from scripts.sync_skills import _clean_url, sync


def test_redact_secrets() -> None:
    token = "ghp_secret_123456"
    text = f"fatal: unable to access 'https://x-access-token:{token}@github.com/org/repo.git'"
    redacted = _redact_secrets(text, token)
    assert token not in redacted
    assert "[REDACTED]" in redacted


def test_clean_url_strips_credentials() -> None:
    url = "https://x-access-token:secret@github.com/sanityops-org/sanityops-inspect-lite.git"
    assert (
        _clean_url(url)
        == "https://github.com/sanityops-org/sanityops-inspect-lite.git"
    )

    plain = "https://github.com/sanityops-org/sanityops-inspect-lite.git"
    assert _clean_url(plain) == plain


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ci_sync_skills.py"])
    monkeypatch.delenv("UPSTREAM_SKILL_URL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    args = parse_args()
    assert args.upstream_url == DEFAULT_UPSTREAM_URL
    assert args.upstream_branch == "main"
    assert args.target_branch == "main"
    assert args.token == ""
    assert args.repo == ""
    assert args.dry_run is False


def test_parse_args_env(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ci_sync_skills.py", "--dry-run", "--force"])
    monkeypatch.setenv("GITHUB_TOKEN", "token-123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "sanityops-org/sanityops-cli")
    args = parse_args()
    assert args.token == "token-123"
    assert args.repo == "sanityops-org/sanityops-cli"
    assert args.dry_run is True
    assert args.force is True


def test_sync_skills_idempotency(tmp_path: Path) -> None:
    """When the source commit is already recorded, sync() is a no-op."""
    dummy_source = tmp_path / "upstream"
    skill_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspect-lite"
        / "skills"
        / "sanityops-inspect-lite"
    )
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nversion: 1.0.0\n---\n")
    (ref_dir / "code-contract-checklist.v2.md").write_text("# Checklist")

    dummy_dest = tmp_path / "dest_skills"
    dummy_dest.mkdir()
    version_file = dummy_dest / "VERSION.json"

    with patch("scripts.sync_skills._git") as mock_git:
        mock_git.side_effect = (
            lambda args, cwd: "dummy_sha_123" if "rev-parse" in args else "http://dummy/url"
        )
        with (
            patch("scripts.sync_skills.DEST_DIR", dummy_dest),
            patch("scripts.sync_skills.VERSION_FILE", version_file),
        ):
            assert sync(dummy_source, force=False) is True
            assert version_file.is_file()
            assert sync(dummy_source, force=False) is False
            assert sync(dummy_source, force=True) is True


def test_sync_skills_with_extract_skill(tmp_path: Path) -> None:
    """pre-inspect-extract is vendored from upstream as a synced item."""
    dummy_source = tmp_path / "upstream"
    skill_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspect-lite"
        / "skills"
        / "sanityops-inspect-lite"
    )
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nversion: 1.3.1\n---\n")
    (ref_dir / "code-contract-checklist.v2.md").write_text("# Checklist")

    extract_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspect-lite"
        / "skills"
        / "pre-inspect-extract"
    )
    extract_dir.mkdir(parents=True)
    (extract_dir / "SKILL.md").write_text("---\nversion: 1.3.1\n---\n# Extract")

    dummy_dest = tmp_path / "dest_skills"
    dummy_dest.mkdir()
    version_file = dummy_dest / "VERSION.json"

    with patch("scripts.sync_skills._git") as mock_git:
        mock_git.side_effect = (
            lambda args, cwd: "dummy_sha_456" if "rev-parse" in args else "http://dummy/url"
        )
        with (
            patch("scripts.sync_skills.DEST_DIR", dummy_dest),
            patch("scripts.sync_skills.VERSION_FILE", version_file),
        ):
            assert sync(dummy_source, force=True) is True
            manifest = json.loads(version_file.read_text(encoding="utf-8"))
            extract_item = manifest["items"]["pre-inspect-extract"]
            assert extract_item["type"] == "synced"
            assert extract_item["version"] == "1.3.1"
            assert (dummy_dest / "pre-inspect-extract" / "SKILL.md").is_file()
