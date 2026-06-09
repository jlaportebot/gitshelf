"""Tests for gitshelf CLI."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from gitshelf.cli import main
from gitshelf.db import add_repo, _save, archive_repo, set_note


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
    (repo / "README.md").write_text("# My Project")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo),
        capture_output=True,
        check=True,
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
    assert "0.3.0" in result.output


def test_scan(runner, git_repo, db_path):
    parent = str(Path(git_repo).parent)
    result = runner.invoke(main, ["scan", parent], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "repos added" in result.output


def test_scan_json(runner, git_repo, db_path):
    parent = str(Path(git_repo).parent)
    result = runner.invoke(main, ["--json", "scan", parent], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["added"] >= 1


def test_scan_with_ignore(runner, git_repo, db_path):
    parent = str(Path(git_repo).parent)
    # Add ignore pattern for "myproject"
    from gitshelf.db import add_ignore_pattern

    add_ignore_pattern("myproject", db_path)
    result = runner.invoke(main, ["scan", parent], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "ignored" in result.output


def test_list_empty(runner, db_path):
    result = runner.invoke(main, ["list"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output


def test_list_json(runner, db_path):
    result = runner.invoke(main, ["--json", "list"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_list_with_repos(runner, db_path):
    data = {
        "repos": {
            "test-repo": {
                "path": "/tmp/test",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": [],
                "archived": False,
            }
        },
        "tags": {},
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _save(data, db_path)
    result = runner.invoke(main, ["list"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "test-repo" in result.output


def test_list_archived_only(runner, db_path):
    data = {
        "repos": {
            "active": {
                "path": "/tmp/active",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": [],
                "archived": False,
            },
            "old": {
                "path": "/tmp/old",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": [],
                "archived": True,
            },
        },
        "tags": {},
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _save(data, db_path)
    result = runner.invoke(main, ["list", "--archived"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "old" in result.output


def test_untrack(runner, db_path):
    data = {
        "repos": {
            "test": {
                "path": "/tmp/test",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": [],
                "archived": False,
            }
        },
        "tags": {},
    }
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


def test_dashboard_json(runner, db_path):
    result = runner.invoke(main, ["--json", "dashboard"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 0


def test_stale_json(runner, db_path):
    result = runner.invoke(main, ["--json", "stale"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_dirty_json(runner, db_path):
    result = runner.invoke(main, ["--json", "dirty"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_sizes_empty(runner, db_path):
    result = runner.invoke(main, ["sizes"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output


def test_prune_empty(runner, db_path):
    result = runner.invoke(main, ["prune"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output


def test_search_no_results(runner, db_path):
    result = runner.invoke(main, ["search", "xyz"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos matching" in result.output


def test_search_json(runner, db_path):
    data = {
        "repos": {
            "my-repo": {
                "path": "/tmp/my",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": ["python"],
                "archived": False,
            }
        },
        "tags": {"python": ["my-repo"]},
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _save(data, db_path)
    result = runner.invoke(main, ["--json", "search", "python"], env=_env_db(db_path))
    assert result.exit_code == 0
    results = json.loads(result.output)
    assert len(results) == 1
    assert results[0]["match_type"] == "tag"


def test_untag_command(runner, db_path):
    data = {
        "repos": {
            "r": {
                "path": "/tmp/r",
                "remote_url": None,
                "added_at": "2026-01-01",
                "last_accessed": "2026-01-01",
                "tags": ["work"],
                "archived": False,
            }
        },
        "tags": {"work": ["r"]},
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _save(data, db_path)
    result = runner.invoke(main, ["untag", "r", "work"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Removed tag" in result.output


# --- New v0.3.0 CLI tests ---


def test_sync_empty(runner, db_path):
    result = runner.invoke(main, ["sync"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No repos tracked" in result.output


def test_sync_json_empty(runner, db_path):
    result = runner.invoke(main, ["--json", "sync"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["checked"] == 0


def test_sync_with_repo(runner, git_repo, db_path):
    add_repo("myproject", git_repo, db_path=db_path)
    result = runner.invoke(main, ["sync"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Synced" in result.output


def test_sync_missing_repo(runner, db_path):
    add_repo("gone", "/nonexistent/path/12345", db_path=db_path)
    result = runner.invoke(main, ["--json", "sync"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "gone" in data["missing"]


def test_archive_command(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    result = runner.invoke(main, ["archive", "r"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Archived" in result.output


def test_archive_json(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    result = runner.invoke(main, ["--json", "archive", "r"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["archived"] is True


def test_archive_not_found(runner, db_path):
    result = runner.invoke(main, ["archive", "ghost"], env=_env_db(db_path))
    assert result.exit_code != 0


def test_unarchive_command(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    archive_repo("r", db_path)
    result = runner.invoke(main, ["unarchive", "r"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Unarchived" in result.output


def test_unarchive_json(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    archive_repo("r", db_path)
    result = runner.invoke(main, ["--json", "unarchive", "r"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["archived"] is False


def test_ignore_add(runner, db_path):
    result = runner.invoke(main, ["ignore", "test-*"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Added ignore pattern" in result.output


def test_ignore_list(runner, db_path):
    from gitshelf.db import add_ignore_pattern

    add_ignore_pattern("dotfiles", db_path)
    result = runner.invoke(main, ["ignore", "--list"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "dotfiles" in result.output


def test_ignore_list_empty(runner, db_path):
    result = runner.invoke(main, ["ignore", "--list"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No ignore patterns" in result.output


def test_ignore_remove(runner, db_path):
    from gitshelf.db import add_ignore_pattern

    add_ignore_pattern("temp", db_path)
    result = runner.invoke(main, ["ignore", "temp", "--remove"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Removed ignore pattern" in result.output


def test_note_set(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    result = runner.invoke(main, ["note", "r", "This is a note"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Note set" in result.output


def test_note_show(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    set_note("r", "hello world", db_path)
    result = runner.invoke(main, ["note", "r", "--show"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "hello world" in result.output


def test_note_show_empty(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    result = runner.invoke(main, ["note", "r", "--show"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No note" in result.output


def test_note_delete(runner, db_path):
    add_repo("r", "/tmp/r", db_path=db_path)
    set_note("r", "to delete", db_path)
    result = runner.invoke(main, ["note", "r", "--delete"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "Note removed" in result.output


def test_notes_list(runner, db_path):
    add_repo("a", "/tmp/a", db_path=db_path)
    add_repo("b", "/tmp/b", db_path=db_path)
    set_note("a", "note a", db_path)
    set_note("b", "note b", db_path)
    result = runner.invoke(main, ["notes"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "note a" in result.output


def test_notes_json(runner, db_path):
    add_repo("a", "/tmp/a", db_path=db_path)
    set_note("a", "my note", db_path)
    result = runner.invoke(main, ["--json", "notes"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["a"] == "my note"


def test_notes_empty(runner, db_path):
    result = runner.invoke(main, ["notes"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "No notes" in result.output


def test_reconcile_json(runner, git_repo, db_path):
    parent = str(Path(git_repo).parent)
    result = runner.invoke(main, ["--json", "reconcile", parent], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "untracked" in data
    assert "gone" in data


def test_reconcile_no_discrepancies(runner, git_repo, db_path):
    add_repo("myproject", git_repo, db_path=db_path)
    parent = str(Path(git_repo).parent)
    result = runner.invoke(main, ["reconcile", parent], env=_env_db(db_path))
    assert result.exit_code == 0


def test_log_command(runner, git_repo, db_path):
    add_repo("myproject", git_repo, db_path=db_path)
    result = runner.invoke(main, ["log", "myproject"], env=_env_db(db_path))
    assert result.exit_code == 0
    assert "init" in result.output


def test_log_json(runner, git_repo, db_path):
    add_repo("myproject", git_repo, db_path=db_path)
    result = runner.invoke(main, ["--json", "log", "myproject"], env=_env_db(db_path))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) >= 1
    assert data[0]["subject"]


def test_log_not_found(runner, db_path):
    result = runner.invoke(main, ["log", "ghost"], env=_env_db(db_path))
    assert result.exit_code != 0
