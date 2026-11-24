"""Unit tests for the skill update workflow and sync scripts."""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts.ci_sync_skills import (
    DEFAULT_UPSTREAM_URL,
    _find_open_pull_request,
    _redact_secrets,
    parse_args,
)
from scripts.sync_skills import (
    CANONICAL_UPSTREAM_URL,
    _canonical_source_url,
    _clean_url,
    _is_git_checkout,
    check,
    sync,
)


def test_redact_secrets() -> None:
    token = "ghp_secret_123456"
    text = f"fatal: unable to access 'https://x-access-token:{token}@github.com/org/repo.git'"
    redacted = _redact_secrets(text, token)
    assert token not in redacted
    assert "[REDACTED]" in redacted


def test_clean_url_strips_credentials() -> None:
    url = "https://x-access-token:secret@github.com/sanityops-org/sanityops-inspector.git"
    assert (
        _clean_url(url)
        == "https://github.com/sanityops-org/sanityops-inspector.git"
    )

    plain = "https://github.com/sanityops-org/sanityops-inspector.git"
    assert _clean_url(plain) == plain


def test_canonical_source_url_maps_retired_repo() -> None:
    retired = "https://github.com/sanityops-org/sanityops-inspect-lite.git"
    assert _canonical_source_url(retired) == CANONICAL_UPSTREAM_URL
    retired_no_suffix = "https://github.com/sanityops-org/sanityops-inspect-lite"
    assert _canonical_source_url(retired_no_suffix) == CANONICAL_UPSTREAM_URL
    assert _canonical_source_url(CANONICAL_UPSTREAM_URL) == CANONICAL_UPSTREAM_URL
    other = "https://github.com/example/other.git"
    assert _canonical_source_url(other) == other


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
        / "sanityops-inspector"
        / "skills"
        / "sanityops-inspect-only"
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
    """sanityops-extract-only is vendored from upstream as a synced item."""
    dummy_source = tmp_path / "upstream"
    skill_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspector"
        / "skills"
        / "sanityops-inspect-only"
    )
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nversion: 2.0.2\n---\n")
    (ref_dir / "code-contract-checklist.v2.md").write_text("# Checklist")

    extract_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspector"
        / "skills"
        / "sanityops-extract-only"
    )
    extract_dir.mkdir(parents=True)
    (extract_dir / "SKILL.md").write_text("---\nversion: 2.0.0\n---\n# Extract")

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
            assert manifest["items"]["sanityops-inspect-only"]["version"] == "2.0.2"
            extract_item = manifest["items"]["sanityops-extract-only"]
            assert extract_item["type"] == "synced"
            assert extract_item["version"] == "2.0.0"
            assert (dummy_dest / "sanityops-extract-only" / "SKILL.md").is_file()


def test_check_hash_only_on_vendored_tree() -> None:
    """The committed vendored tree matches VERSION.json without a source checkout."""
    assert check(None) == 0


def test_check_reports_invalid_source(tmp_path: Path, capsys) -> None:
    assert check(tmp_path / "missing") == 1
    assert "source path is not a valid directory" in capsys.readouterr().out


def test_check_reports_non_git_source(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()
    assert check(source) == 1
    assert "source path is not a git checkout" in capsys.readouterr().out


def test_is_git_checkout_true_for_repo_root() -> None:
    assert _is_git_checkout(Path.cwd()) is True


def test_is_git_checkout_false_for_plain_directory(tmp_path: Path) -> None:
    assert _is_git_checkout(tmp_path) is False


def test_check_reports_missing_version_json(tmp_path: Path) -> None:
    with patch("scripts.sync_skills.VERSION_FILE", tmp_path / "missing.json"):
        assert check(None) == 1


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:  # noqa: ANN002
        return False

    def read(self) -> bytes:
        return self._payload


def test_find_open_pull_request_returns_url() -> None:
    payload = json.dumps([{"html_url": "https://example.test/pull/1"}]).encode()
    with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
        assert (
            _find_open_pull_request("owner/repo", "token", "bot/x")
            == "https://example.test/pull/1"
        )


def test_find_open_pull_request_returns_empty_when_none() -> None:
    with patch("urllib.request.urlopen", return_value=_FakeResponse(b"[]")):
        assert _find_open_pull_request("owner/repo", "token", "bot/x") == ""


def test_find_open_pull_request_swallows_api_error() -> None:
    error = urllib.error.HTTPError("https://api.test", 500, "server error", {}, None)
    with patch("urllib.request.urlopen", side_effect=error):
        assert _find_open_pull_request("owner/repo", "token", "bot/x") == ""


def test_sync_revendors_when_vendored_content_drifted(tmp_path: Path) -> None:
    dummy_source = tmp_path / "upstream"
    skill_dir = (
        dummy_source
        / "plugins"
        / "sanityops-inspector"
        / "skills"
        / "sanityops-inspect-only"
    )
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nversion: 2.0.2\n---\n# Inspect")
    (skill_dir / "references" / "code-contract-checklist.v2.md").write_text("# Checklist")

    dummy_dest = tmp_path / "dest_skills"
    dummy_dest.mkdir()
    version_file = dummy_dest / "VERSION.json"

    with patch("scripts.sync_skills._git") as mock_git:
        mock_git.side_effect = (
            lambda args, cwd: "same_sha" if "rev-parse" in args else "http://dummy/url"
        )
        with (
            patch("scripts.sync_skills.DEST_DIR", dummy_dest),
            patch("scripts.sync_skills.VERSION_FILE", version_file),
        ):
            assert sync(dummy_source, force=True) is True
            assert sync(dummy_source) is False  # commit and hashes match

            (dummy_dest / "sanityops-inspect-only" / "SKILL.md").write_text("tampered")
            assert sync(dummy_source) is True  # same commit, drifted content
            restored = (dummy_dest / "sanityops-inspect-only" / "SKILL.md").read_text()
            assert restored.startswith("---\nversion: 2.0.2")
