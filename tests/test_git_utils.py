"""Tests for gitshelf git utilities."""

import os
import subprocess

import pytest

from gitshelf.git_utils import (
    is_git_repo,
    get_current_branch,
    has_uncommitted_changes,
    has_unpushed_commits,
    get_last_commit_date,
    get_repo_name,
    get_health_report,
    get_summary,
    get_stash_count,
    get_branch_count,
    get_local_branches,
    get_stale_branches,
    get_commit_count,
    get_contributors,
    get_repo_size,
    scan_directory,
    get_worktree_status,
    get_recent_commits,
    get_remote_branches,
    has_diverged,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo for testing."""
    repo = tmp_path / "test-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    # Create an initial commit so HEAD is valid
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    return str(repo)


@pytest.fixture
def git_repo_multi_commit(tmp_path):
    """Create a git repo with multiple commits and branches."""
    repo = tmp_path / "multi-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    for i in range(3):
        (repo / f"file{i}.txt").write_text(f"content {i}")
        subprocess.run(
            ["git", "add", "."], cwd=str(repo), capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=str(repo),
            capture_output=True,
            check=True,
        )
    return str(repo)


def test_is_git_repo(git_repo, tmp_path):
    assert is_git_repo(git_repo) is True
    assert is_git_repo(str(tmp_path)) is False


def test_get_current_branch(git_repo):
    branch = get_current_branch(git_repo)
    assert branch in ("main", "master")


def test_get_current_branch_not_repo(tmp_path):
    assert get_current_branch(str(tmp_path)) is None


def test_has_uncommitted_changes_clean(git_repo):
    assert has_uncommitted_changes(git_repo) is False


def test_has_uncommitted_changes_dirty(git_repo):
    with open(os.path.join(git_repo, "newfile.txt"), "w") as f:
        f.write("dirty")
    assert has_uncommitted_changes(git_repo) is True


def test_get_last_commit_date(git_repo):
    date = get_last_commit_date(git_repo)
    assert date is not None


def test_get_repo_name(git_repo):
    name = get_repo_name(git_repo)
    assert name == "test-repo"


def test_get_repo_name_from_path(git_repo):
    name = get_repo_name(git_repo)
    assert "test-repo" in name


def test_get_stash_count_empty(git_repo):
    assert get_stash_count(git_repo) == 0


def test_get_branch_count(git_repo):
    assert get_branch_count(git_repo) >= 1


def test_get_health_report(git_repo):
    report = get_health_report(git_repo)
    assert report["path"] == git_repo
    assert report["branch"] in ("main", "master")
    assert report["dirty"] is False
    assert report["last_commit"] is not None


def test_get_summary(git_repo_multi_commit):
    s = get_summary(git_repo_multi_commit)
    assert s["commit_count"] == 3
    assert s["branch"] in ("main", "master")
    assert s["contributors"] is not None
    assert len(s["contributors"]) >= 1
    assert s["contributors"][0]["commits"] == 3
    assert s["size_bytes"] > 0
    assert s["stale_branches"] == []
    assert s["local_branches"] is not None


def test_get_local_branches(git_repo):
    branches = get_local_branches(git_repo)
    assert len(branches) >= 1
    assert any(b in ("main", "master") for b in branches)


def test_get_stale_branches_clean(git_repo):
    # Fresh repo, no stale branches
    stale = get_stale_branches(git_repo, days=90)
    assert stale == []


def test_get_commit_count(git_repo_multi_commit):
    assert get_commit_count(git_repo_multi_commit) == 3


def test_get_commit_count_single(git_repo):
    assert get_commit_count(git_repo) == 1


def test_get_contributors(git_repo_multi_commit):
    contribs = get_contributors(git_repo_multi_commit)
    assert len(contribs) >= 1
    assert contribs[0]["name"] == "Test User"
    assert contribs[0]["commits"] == 3


def test_get_repo_size(git_repo):
    size = get_repo_size(git_repo)
    assert size > 0


def test_has_unpushed_commits_no_remote(git_repo):
    # No remote set, so should return True
    result = has_unpushed_commits(git_repo)
    assert result is True


def test_scan_directory(tmp_path, git_repo):
    repos = scan_directory(str(tmp_path))
    assert len(repos) >= 1
    assert any(r["name"] == "test-repo" for r in repos)


def test_scan_directory_deep(tmp_path):
    # Create nested structure: tmp_path/org/repo
    org = tmp_path / "org"
    org.mkdir()
    repo = org / "nested-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    (repo / "README.md").write_text("# Nested")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )

    # Shallow scan should not find it
    shallow = scan_directory(str(tmp_path), deep=False)
    assert not any(r["name"] == "nested-repo" for r in shallow)

    # Deep scan should find it
    deep = scan_directory(str(tmp_path), deep=True)
    assert any(r["name"] == "nested-repo" for r in deep)


def test_scan_nonexistent_directory():
    repos = scan_directory("/nonexistent/path/12345")
    assert repos == []


# --- New v0.3.0 utility tests ---


def test_get_worktree_status(git_repo):
    result = get_worktree_status(git_repo)
    assert result is not None
    assert "worktrees" in result
    assert "count" in result
    assert result["count"] >= 1


def test_get_recent_commits(git_repo):
    commits = get_recent_commits(git_repo, count=5)
    assert len(commits) >= 1
    assert commits[0]["hash"]
    assert commits[0]["author"]
    assert commits[0]["subject"]


def test_get_recent_commits_multi(git_repo_multi_commit):
    commits = get_recent_commits(git_repo_multi_commit, count=3)
    assert len(commits) == 3
    # Most recent first
    assert "commit 2" in commits[0]["subject"]


def test_get_recent_commits_not_repo(tmp_path):
    commits = get_recent_commits(str(tmp_path), count=5)
    assert commits == []


def test_get_remote_branches_no_remote(git_repo):
    branches = get_remote_branches(git_repo)
    # No remotes set up, so should be empty
    assert branches == []


def test_has_diverged_no_remote(git_repo):
    # No upstream, so no divergence
    assert has_diverged(git_repo) is False


def test_has_diverged_not_repo(tmp_path):
    assert has_diverged(str(tmp_path)) is False
