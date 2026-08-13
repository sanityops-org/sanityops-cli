#!/usr/bin/env python3
"""
PR review bot: uses the Anthropic SDK to review a pull request diff
and post the review as a PR review comment via the GitHub API.

Run inside a GitHub Actions workflow. Requires the following env vars:
  ANTHROPIC_API_KEY   - API key (stored as a GitHub secret)
  GITHUB_TOKEN        - GitHub token to post the review (auto-provided)
  GITHUB_REPOSITORY   - e.g. owner/repo (auto-provided)
  GITHUB_EVENT_PATH   - path to the pull_request event JSON (auto-provided)
  ANTHROPIC_MODEL     - (optional) model id, default claude-sonnet-4-5
  ANTHROPIC_BASE_URL  - (optional) custom API endpoint
"""

import json
import os
import sys
import urllib.error
import urllib.request

# Anthropic SDK
from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-5"


def read_inputs() -> dict:
    """Read required inputs from the environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip()
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None

    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    if not event_path or not os.path.exists(event_path):
        raise RuntimeError(f"GITHUB_EVENT_PATH is not set or missing: {event_path!r}")

    with open(event_path) as f:
        event = json.load(f)

    pr_number = (event.get("pull_request") or {}).get("number")
    if not pr_number:
        raise RuntimeError("Event is not a pull_request event with a number")

    return {
        "api_key": api_key,
        "token": token,
        "repo": repo,
        "model": model,
        "base_url": base_url,
        "pr_number": pr_number,
    }


def fetch_pr_diff(repo: str, pr_number: int, token: str) -> str:
    """Fetch the pull request diff via the GitHub API."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Failed to fetch diff: {e.code} {e.read().decode(errors='replace')[:300]}") from e


def run_review(payload: dict, diff: str) -> str:
    """Call the Anthropic API to review the diff and return the review text."""
    pr_number = payload["pr_number"]

    # Initialize Anthropic client (SDK handles auth headers correctly)
    client = Anthropic(
        api_key=payload["api_key"],
        base_url=payload.get("base_url"),
    )

    system_prompt = (
        "You are a senior code reviewer. Review the provided pull request diff and "
        "report issues. Be specific and technical. For each issue include the "
        "file path and line if identifiable. Categorize findings as Critical, "
        "Important, or Minor. End with an overall assessment: Ready to merge (Yes/No/With fixes). "
        "Keep the review concise and actionable. Write in the same language as the "
        "PR description or codebase conventions."
    )
    user_prompt = (
        f"Here is the diff for PR #{pr_number}:\n\n"
        f"```diff\n{diff}\n```"
    )

    message = client.messages.create(
        model=payload["model"],
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from response
    text_parts = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    text = "\n".join(text_parts).strip()
    if not text:
        raise RuntimeError("Anthropic returned no text content")
    return text


def post_review(payload: dict, body: str) -> None:
    """Post the review as a PR review comment via the GitHub API."""
    url = f"https://api.github.com/repos/{payload['repo']}/pulls/{payload['pr_number']}/reviews"
    data = json.dumps({
        "event": "COMMENT",
        "body": f"## 🤖 Claude Code Review\n\n{body}",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {payload['token']}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Warning: could not post review: {e.code} {e.read().decode(errors='replace')[:200]}", file=sys.stderr)


def main() -> int:
    try:
        payload = read_inputs()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        diff = fetch_pr_diff(payload["repo"], payload["pr_number"], payload["token"])
        print(f"Fetched diff for PR #{payload['pr_number']} ({len(diff)} chars)")
        if not diff.strip():
            print("Diff is empty; nothing to review.")
            return 0

        review = run_review(payload, diff)
        post_review(payload, review)
        print("Review posted successfully.")
        return 0
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
