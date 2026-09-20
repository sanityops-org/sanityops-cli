"""Tests for the Getting Started and Advanced Usage help panels."""

import subprocess
import sys
from pathlib import Path

from rich.panel import Panel

from sanityops_cli.help_panel import (
    ADVANCED_USAGE_TEXT,
    GETTING_STARTED_TEXT,
    get_advanced_usage_panel,
    get_getting_started_panel,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_getting_started_text_content():
    """Verify the Getting Started text contains all 5 steps."""
    assert "deeplogic-cli init" in GETTING_STARTED_TEXT
    assert "inspect_config.yaml" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect repair" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect cover" in GETTING_STARTED_TEXT
    assert "(optional)" in GETTING_STARTED_TEXT


def test_getting_started_panel_returns_panel():
    """Verify the function returns a Rich Panel."""
    panel = get_getting_started_panel()
    assert isinstance(panel, Panel)


def test_getting_started_panel_has_correct_title():
    """Verify the panel has the correct title."""
    panel = get_getting_started_panel()
    assert panel.title is not None
    assert "Getting Started" in str(panel.title)


def test_advanced_usage_text_content():
    """Verify the Advanced Usage text contains CI/CD integration."""
    assert "CI/CD" in ADVANCED_USAGE_TEXT
    assert "inspect_config.yaml" in ADVANCED_USAGE_TEXT
    assert "environment variables" in ADVANCED_USAGE_TEXT
    assert "deeplogic-cli config --help" in ADVANCED_USAGE_TEXT


def test_advanced_usage_panel_returns_panel():
    """Verify the function returns a Rich Panel."""
    panel = get_advanced_usage_panel()
    assert isinstance(panel, Panel)


def test_advanced_usage_panel_has_correct_title():
    """Verify the panel has the correct title."""
    panel = get_advanced_usage_panel()
    assert panel.title is not None
    assert "Advanced Usage" in str(panel.title)


def test_entry_point_shows_getting_started_on_help():
    """Verify the PyInstaller entry point (entry.py) shows the Getting Started panel.

    Regression test: entry.py used to call app() directly, bypassing the
    Getting Started panel logic in main(), so the packaged binary's --help
    output was missing the panel while pip-installed runs showed it.
    """
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" in result.stdout


def test_entry_point_shows_advanced_usage_on_help():
    """Verify the entry point shows the Advanced Usage panel."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Advanced Usage" in result.stdout


def test_entry_point_shows_getting_started_with_no_args():
    """Verify the PyInstaller entry point shows the panel with no arguments."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py")],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" in result.stdout
    assert "Advanced Usage" in result.stdout


def test_entry_point_does_not_show_panels_for_unsupported_h_flag():
    """Verify -h (unsupported by Typer at root) shows an error without panels."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "-h"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 2
    assert "No such option: -h" in result.stderr + result.stdout
    assert "Getting Started" not in result.stdout
    assert "Advanced Usage" not in result.stdout


def test_entry_point_does_not_show_panels_for_invalid_flag_with_help():
    """Verify --help mixed with an invalid flag shows an error without panels."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--help", "--bogus"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 2
    assert "No such option: --bogus" in result.stderr + result.stdout
    assert "Getting Started" not in result.stdout
    assert "Advanced Usage" not in result.stdout


def test_entry_point_does_not_show_panels_for_subcommand_help():
    """Verify subcommand help does not show the top-level panels."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "inspect", "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" not in result.stdout
    assert "Advanced Usage" not in result.stdout


def test_entry_point_does_not_show_panels_for_version():
    """Verify --version does not show the top-level panels."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--version"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" not in result.stdout
    assert "Advanced Usage" not in result.stdout
