"""Git introspection utilities for gitshelf."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _run_git(args: list[str], repo_path: str) -> str | None:
    """Run a git command in a repo directory, return stdout or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def is_git_repo(path: str) -> bool:
    """Check if a directory is a git repository."""
    return _run_git(["rev-parse", "--git-dir"], path) is not None


def get_current_branch(repo_path: str) -> str | None:
    """Get the current branch name."""
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)


def get_remote_url(repo_path: str) -> str | None:
    """Get the origin remote URL."""
    return _run_git(["remote", "get-url", "origin"], repo_path)


def has_uncommitted_changes(repo_path: str) -> bool:
    """Check if there are uncommitted changes (staged or unstaged)."""
    status = _run_git(["status", "--porcelain"], repo_path)
    return status is not None and len(status) > 0


def has_unpushed_commits(repo_path: str) -> bool:
    """Check if there are commits not pushed to the remote."""
    branch = get_current_branch(repo_path)
    if not branch or branch == "HEAD":
        return False
    # Check if upstream tracking branch exists
    upstream = _run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], repo_path)
    if upstream is None:
        # No upstream set — assume unpushed
        return True
    unpushed = _run_git(["log", "@{upstream}..HEAD", "--oneline"], repo_path)
    return unpushed is not None and len(unpushed) > 0


def get_last_commit_date(repo_path: str) -> datetime | None:
    """Get the date of the most recent commit."""
    date_str = _run_git(["log", "-1", "--format=%cI"], repo_path)
    if date_str:
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass
    return None


def get_stash_count(repo_path: str) -> int:
    """Get the number of stashed changes."""
    result = _run_git(["stash", "list"], repo_path)
    if result is None or result == "":
        return 0
    return len(result.splitlines())


def get_branch_count(repo_path: str) -> int:
    """Get the total number of branches."""
    result = _run_git(["branch", "-a"], repo_path)
    if result is None:
        return 0
    return len(result.splitlines())


def get_repo_name(repo_path: str) -> str:
    """Extract repo name from path or remote URL."""
    # Try remote URL first
    remote = get_remote_url(repo_path)
    if remote:
        # Handle both HTTPS and SSH URLs
        name = remote.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name
    # Fall back to directory name
    return os.path.basename(os.path.abspath(repo_path))


def scan_directory(directory: str) -> list[dict[str, Any]]:
    """Scan a directory for git repositories (one level deep)."""
    repos: list[dict[str, Any]] = []
    base = Path(directory).expanduser().resolve()

    if not base.is_dir():
        return repos

    for entry in base.iterdir():
        if entry.is_dir() and is_git_repo(str(entry)):
            path = str(entry)
            name = get_repo_name(path)
            repos.append({
                "name": name,
                "path": path,
                "remote_url": get_remote_url(path),
                "branch": get_current_branch(path),
                "dirty": has_uncommitted_changes(path),
                "last_commit": get_last_commit_date(path),
            })

    return repos


def get_health_report(repo_path: str) -> dict[str, Any]:
    """Generate a health report for a repository."""
    return {
        "path": repo_path,
        "branch": get_current_branch(repo_path),
        "dirty": has_uncommitted_changes(repo_path),
        "unpushed": has_unpushed_commits(repo_path),
        "stashes": get_stash_count(repo_path),
        "branches": get_branch_count(repo_path),
        "last_commit": get_last_commit_date(repo_path),
    }
