"""Tests for gitshelf CLI."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from gitshelf.cli import main
from gitshelf.db import add_repo, _load, _save


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "cli_test_db.json"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo for CLI testing."""
    import subprocess
    repo = tmp_path / "myproject"
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
    (repo / "README.md").write_text("# My Project")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo), capture_output=True, check=True,
    )
    return str(repo)


def _env_db(db_path):
    """Return env dict with GITSHELF_DB_PATH set."""
    env = os.environ.copy()
    env["GITSHELF_DB_PATH"] = str(db_path)
    return env


def test_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_scan(runner, git_repo, db_path):
    parent = str(Path(git_repo).parent)
    result = runner.invoke(main, ["scan", parent], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "repos added" in result.output


def test_list_empty(runner, db_path):
    result = runner.invoke(main, ["list"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output


def test_untrack(runner, db_path):
    # Manually create a db entry
    data = {"repos": {"test": {"path": "/tmp/test", "remote_url": None, "added_at": "2026-01-01", "last_accessed": "2026-01-01", "tags": []}}, "tags": {}}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _save(data, db_path)
    result = runner.invoke(main, ["untrack", "test"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Untracked" in result.output


def test_tags_empty(runner, db_path):
    result = runner.invoke(main, ["tags"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No tags" in result.output


def test_dashboard_empty(runner, db_path):
    result = runner.invoke(main, ["dashboard"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output
