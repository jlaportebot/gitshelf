"""Tests for gitshelf git utilities."""

import subprocess

import pytest

from gitshelf.git_utils import (
    is_git_repo,
    get_current_branch,
    get_remote_url,
    has_uncommitted_changes,
    get_last_commit_date,
    get_repo_name,
    get_health_report,
    get_stash_count,
    get_branch_count,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo for testing."""
    repo = tmp_path / "test-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), capture_output=True, check=True,
    )
    # Create an initial commit so HEAD is valid
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo), capture_output=True, check=True,
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
    import os
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
    # Remove remote so it falls back to directory name
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
