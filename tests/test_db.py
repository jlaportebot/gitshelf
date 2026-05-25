"""Tests for gitshelf database operations."""

import json
import tempfile
from pathlib import Path

import pytest

from gitshelf.db import (
    add_repo,
    remove_repo,
    get_repo,
    list_repos,
    tag_repo,
    untag_repo,
    get_repos_by_tag,
    list_tags,
    search_repos,
    _load,
    _save,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_db.json"


def test_add_repo(db_path):
    add_repo("my-repo", "/home/user/my-repo", "https://github.com/user/my-repo.git", db_path)
    repo = get_repo("my-repo", db_path)
    assert repo is not None
    assert repo["path"] == "/home/user/my-repo"
    assert repo["remote_url"] == "https://github.com/user/my-repo.git"


def test_add_repo_no_remote(db_path):
    add_repo("local-repo", "/tmp/local", db_path=db_path)
    repo = get_repo("local-repo", db_path)
    assert repo["remote_url"] is None


def test_remove_repo(db_path):
    add_repo("to-remove", "/path", db_path=db_path)
    assert remove_repo("to-remove", db_path) is True
    assert get_repo("to-remove", db_path) is None


def test_remove_repo_not_found(db_path):
    assert remove_repo("nonexistent", db_path) is False


def test_get_repo_not_found(db_path):
    assert get_repo("nope", db_path) is None


def test_list_repos(db_path):
    add_repo("a", "/a", db_path=db_path)
    add_repo("b", "/b", db_path=db_path)
    repos = list_repos(db_path)
    assert len(repos) == 2
    assert "a" in repos
    assert "b" in repos


def test_tag_repo(db_path):
    add_repo("tagged", "/tagged", db_path=db_path)
    tag_repo("tagged", "work", db_path)
    tags = list_tags(db_path)
    assert "work" in tags
    assert "tagged" in tags["work"]
    repo = get_repo("tagged", db_path)
    assert "work" in repo["tags"]


def test_tag_nonexistent_repo(db_path):
    with pytest.raises(ValueError, match="not found"):
        tag_repo("ghost", "work", db_path)


def test_untag_repo(db_path):
    add_repo("r", "/r", db_path=db_path)
    tag_repo("r", "work", db_path)
    untag_repo("r", "work", db_path)
    assert "work" not in get_repo("r", db_path)["tags"]


def test_untag_cleans_empty_tags(db_path):
    add_repo("r", "/r", db_path=db_path)
    tag_repo("r", "work", db_path)
    untag_repo("r", "work", db_path)
    tags = list_tags(db_path)
    assert "work" not in tags


def test_get_repos_by_tag(db_path):
    add_repo("r1", "/r1", db_path=db_path)
    add_repo("r2", "/r2", db_path=db_path)
    tag_repo("r1", "python", db_path)
    tag_repo("r2", "python", db_path)
    tag_repo("r1", "work", db_path)
    python_repos = get_repos_by_tag("python", db_path)
    assert sorted(python_repos) == ["r1", "r2"]
    work_repos = get_repos_by_tag("work", db_path)
    assert work_repos == ["r1"]


def test_remove_repo_cleans_tags(db_path):
    add_repo("r", "/r", db_path=db_path)
    tag_repo("r", "work", db_path)
    remove_repo("r", db_path)
    assert "r" not in list_tags(db_path).get("work", [])


def test_duplicate_tag_is_idempotent(db_path):
    add_repo("r", "/r", db_path=db_path)
    tag_repo("r", "t", db_path)
    tag_repo("r", "t", db_path)
    assert get_repos_by_tag("t", db_path) == ["r"]


def test_empty_db(db_path):
    assert list_repos(db_path) == {}
    assert list_tags(db_path) == {}


def test_search_by_name(db_path):
    add_repo("torchmetrics", "/tm", db_path=db_path)
    add_repo("harper", "/hp", db_path=db_path)
    results = search_repos("torch", db_path)
    assert len(results) == 1
    assert results[0]["name"] == "torchmetrics"
    assert results[0]["match_type"] == "name"


def test_search_by_path(db_path):
    add_repo("repo1", "/home/user/projects/python", db_path=db_path)
    results = search_repos("python", db_path)
    assert len(results) == 1
    assert results[0]["match_type"] == "path"


def test_search_by_tag(db_path):
    add_repo("r1", "/r1", db_path=db_path)
    tag_repo("r1", "machine-learning", db_path)
    results = search_repos("machine", db_path)
    assert len(results) == 1
    assert results[0]["match_type"] == "tag"


def test_search_no_results(db_path):
    add_repo("repo1", "/path", db_path=db_path)
    results = search_repos("xyz123", db_path)
    assert results == []


def test_search_case_insensitive(db_path):
    add_repo("MyRepo", "/mr", db_path=db_path)
    results = search_repos("myrepo", db_path)
    assert len(results) == 1


def test_remove_repo_cleans_empty_tags(db_path):
    add_repo("only", "/only", db_path=db_path)
    tag_repo("only", "solo", db_path)
    remove_repo("only", db_path)
    tags = list_tags(db_path)
    assert "solo" not in tags
