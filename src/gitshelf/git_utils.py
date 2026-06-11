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


def _parse_git_date(date_str: str | None) -> datetime | None:
    """Parse git ISO 8601 date string, handling Python 3.10's limited fromisoformat."""
    if not date_str:
        return None
    # Python 3.10's fromisoformat doesn't support timezone with colon (+00:00)
    # Normalize timezone to +0000 format for compatibility
    normalized = date_str
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if "+" in normalized and normalized.count(":") == 3:
        # Has timezone with colon, e.g., 2026-06-11T10:30:00+00:00
        # Remove colon from timezone for Python 3.10 compatibility
        normalized = normalized[:-3] + normalized[-2:]
    try:
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        # Final fallback: parse without timezone
        try:
            return datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            pass
    return None


def get_last_commit_date(repo_path: str) -> datetime | None:
    """Get the date of the most recent commit."""
    date_str = _run_git(["log", "-1", "--format=%cI"], repo_path)
    return _parse_git_date(date_str)


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


def get_local_branches(repo_path: str) -> list[str]:
    """Get list of local branch names."""
    result = _run_git(["branch", "--format=%(refname:short)"], repo_path)
    if result is None:
        return []
    return [b.strip() for b in result.splitlines() if b.strip()]


def get_stale_branches(repo_path: str, days: int = 90) -> list[dict[str, Any]]:
    """Get branches with no activity in the last N days."""
    branches = get_local_branches(repo_path)
    stale = []
    for branch in branches:
        date_str = _run_git(["log", "-1", "--format=%cI", branch], repo_path)
        last_date = _parse_git_date(date_str)
        if last_date:
            days_idle = (datetime.now(last_date.tzinfo) - last_date).days
            if days_idle > days:
                stale.append({"branch": branch, "days_idle": days_idle})
    return stale


def get_repo_size(repo_path: str) -> int:
    """Get the total size of the repo directory in bytes."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(repo_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def get_commit_count(repo_path: str) -> int:
    """Get the total number of commits on the current branch."""
    result = _run_git(["rev-list", "--count", "HEAD"], repo_path)
    if result:
        try:
            return int(result)
        except ValueError:
            pass
    return 0


def get_contributors(repo_path: str) -> list[dict[str, Any]]:
    """Get top contributors by commit count."""
    result = _run_git(["shortlog", "-sn", "HEAD"], repo_path)
    if result is None:
        return []
    contributors = []
    for line in result.splitlines():
        parts = line.strip().split("\t", 1)
        if len(parts) == 2:
            contributors.append(
                {
                    "name": parts[1],
                    "commits": int(parts[0]),
                }
            )
    return contributors


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


def scan_directory(directory: str, deep: bool = False) -> list[dict[str, Any]]:
    """Scan a directory for git repositories.

    Args:
        directory: Path to scan.
        deep: If True, scan two levels deep instead of one.
    """
    repos: list[dict[str, Any]] = []
    base = Path(directory).expanduser().resolve()

    if not base.is_dir():
        return repos

    def _check_dir(entry: Path) -> dict[str, Any] | None:
        if entry.is_dir() and is_git_repo(str(entry)):
            path = str(entry)
            name = get_repo_name(path)
            return {
                "name": name,
                "path": path,
                "remote_url": get_remote_url(path),
                "branch": get_current_branch(path),
                "dirty": has_uncommitted_changes(path),
                "last_commit": get_last_commit_date(path),
            }
        return None

    for entry in base.iterdir():
        repo_info = _check_dir(entry)
        if repo_info:
            repos.append(repo_info)
            continue
        # If deep, also check subdirectories
        if deep and entry.is_dir() and not entry.name.startswith("."):
            for sub in entry.iterdir():
                repo_info = _check_dir(sub)
                if repo_info:
                    repos.append(repo_info)

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


def get_summary(repo_path: str) -> dict[str, Any]:
    """Generate a detailed summary for a repository."""
    return {
        "path": repo_path,
        "branch": get_current_branch(repo_path),
        "remote_url": get_remote_url(repo_path),
        "dirty": has_uncommitted_changes(repo_path),
        "unpushed": has_unpushed_commits(repo_path),
        "stashes": get_stash_count(repo_path),
        "branches": get_branch_count(repo_path),
        "local_branches": get_local_branches(repo_path),
        "stale_branches": get_stale_branches(repo_path),
        "last_commit": get_last_commit_date(repo_path),
        "commit_count": get_commit_count(repo_path),
        "contributors": get_contributors(repo_path),
        "size_bytes": get_repo_size(repo_path),
    }


def get_worktree_status(repo_path: str) -> dict[str, Any] | None:
    """Get worktree status: list of worktrees for a repo.

    Returns list of dicts with 'path' and 'branch' keys, or None on error.
    """
    result = _run_git(["worktree", "list", "--porcelain"], repo_path)
    if result is None:
        return None
    worktrees = []
    current: dict[str, str] = {}
    for line in result.splitlines():
        if " " in line:
            key, value = line.split(" ", 1)
            if key == "worktree":
                current["path"] = value
            elif key == "branch":
                current["branch"] = value
        elif line == "" and current:
            worktrees.append(current)
            current = {}
    if current:
        worktrees.append(current)
    return {"worktrees": worktrees, "count": len(worktrees)}


def get_recent_commits(repo_path: str, count: int = 5) -> list[dict[str, str]]:
    """Get recent commits with hash, author, date, and subject."""
    fmt = "%H|%an|%aI|%s"
    result = _run_git(["log", f"-{count}", f"--format={fmt}"], repo_path)
    if result is None:
        return []
    commits = []
    for line in result.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append(
                {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "subject": parts[3],
                }
            )
    return commits


def get_remote_branches(repo_path: str) -> list[str]:
    """Get list of remote branch names (without remote prefix)."""
    result = _run_git(["branch", "-r", "--format=%(refname:short)"], repo_path)
    if result is None:
        return []
    return [b.strip() for b in result.splitlines() if b.strip() and "HEAD" not in b]


def has_diverged(repo_path: str) -> bool:
    """Check if local branch has diverged from its upstream."""
    branch = get_current_branch(repo_path)
    if not branch or branch == "HEAD":
        return False
    upstream = _run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], repo_path)
    if upstream is None:
        return False
    # Check for both ahead and behind
    ahead = _run_git(["rev-list", "--count", "@{upstream}..HEAD"], repo_path)
    behind = _run_git(["rev-list", "--count", "HEAD..@{upstream}"], repo_path)
    try:
        return int(ahead or "0") > 0 and int(behind or "0") > 0
    except ValueError:
        return False
