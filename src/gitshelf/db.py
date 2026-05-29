"""Database layer for gitshelf — stores repo metadata in a JSON file."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _default_db_path() -> Path:
    """Get the default db path, checking env var at call time."""
    return Path(os.environ.get("GITSHELF_DB_PATH", "~/.gitshelf/db.json")).expanduser()


def _now() -> str:
    return datetime.now().isoformat()


def _load(db_path: Path | None = None) -> dict[str, Any]:
    if db_path is None:
        db_path = _default_db_path()
    if not db_path.exists():
        return {"repos": {}, "tags": {}, "ignore_patterns": [], "notes": {}}
    with open(db_path) as f:
        data = json.load(f)
    # Ensure backward compatibility with old DB format
    data.setdefault("ignore_patterns", [])
    data.setdefault("notes", {})
    return data


def _save(data: dict[str, Any], db_path: Path | None = None) -> None:
    if db_path is None:
        db_path = _default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w") as f:
        json.dump(data, f, indent=2)


def add_repo(
    name: str,
    path: str,
    remote_url: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Add a repo to the database."""
    data = _load(db_path)
    data["repos"][name] = {
        "path": path,
        "remote_url": remote_url,
        "added_at": _now(),
        "last_accessed": _now(),
        "tags": [],
        "archived": False,
    }
    _save(data, db_path)


def remove_repo(name: str, db_path: Path | None = None) -> bool:
    """Remove a repo from tracking. Returns True if found."""
    data = _load(db_path)
    if name not in data["repos"]:
        return False
    del data["repos"][name]
    # Clean up tag references
    for tag_repos in data.get("tags", {}).values():
        if name in tag_repos:
            tag_repos.remove(name)
    # Clean up empty tag entries
    data["tags"] = {k: v for k, v in data.get("tags", {}).items() if v}
    # Clean up notes
    data.get("notes", {}).pop(name, None)
    _save(data, db_path)
    return True


def get_repo(name: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Get repo metadata by name."""
    data = _load(db_path)
    return data["repos"].get(name)


def list_repos(
    db_path: Path | None = None,
    include_archived: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return all tracked repos."""
    data = _load(db_path)
    repos = data.get("repos", {})
    if not include_archived:
        repos = {k: v for k, v in repos.items() if not v.get("archived", False)}
    return repos


def tag_repo(name: str, tag: str, db_path: Path | None = None) -> None:
    """Add a tag to a repo."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    if tag not in data.get("tags", {}):
        data.setdefault("tags", {})[tag] = []
    if name not in data["tags"][tag]:
        data["tags"][tag].append(name)
    if tag not in data["repos"][name].get("tags", []):
        data["repos"][name].setdefault("tags", []).append(tag)
    _save(data, db_path)


def untag_repo(name: str, tag: str, db_path: Path | None = None) -> None:
    """Remove a tag from a repo."""
    data = _load(db_path)
    if tag in data.get("tags", {}) and name in data["tags"][tag]:
        data["tags"][tag].remove(name)
    repo = data["repos"].get(name, {})
    if tag in repo.get("tags", []):
        repo["tags"].remove(tag)
    # Clean up empty tag entries
    data["tags"] = {k: v for k, v in data.get("tags", {}).items() if v}
    _save(data, db_path)


def get_repos_by_tag(tag: str, db_path: Path | None = None) -> list[str]:
    """Get all repo names with a given tag."""
    data = _load(db_path)
    return data.get("tags", {}).get(tag, [])


def update_last_accessed(name: str, db_path: Path | None = None) -> None:
    """Update the last_accessed timestamp for a repo."""
    data = _load(db_path)
    if name in data["repos"]:
        data["repos"][name]["last_accessed"] = _now()
        _save(data, db_path)


def list_tags(db_path: Path | None = None) -> dict[str, list[str]]:
    """Return all tags and their repos."""
    data = _load(db_path)
    return data.get("tags", {})


def search_repos(query: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Search repos by name, path, or tag. Returns list of matches with match_type."""
    data = _load(db_path)
    query_lower = query.lower()
    results = []

    for name, info in data.get("repos", {}).items():
        if query_lower in name.lower():
            results.append({**info, "name": name, "match_type": "name"})
        elif query_lower in info.get("path", "").lower():
            results.append({**info, "name": name, "match_type": "path"})
        elif any(query_lower in t.lower() for t in info.get("tags", [])):
            results.append({**info, "name": name, "match_type": "tag"})

    return results


# --- Ignore patterns ---

def add_ignore_pattern(pattern: str, db_path: Path | None = None) -> None:
    """Add a name pattern to the ignore list (glob-style)."""
    data = _load(db_path)
    patterns = data.setdefault("ignore_patterns", [])
    if pattern not in patterns:
        patterns.append(pattern)
        _save(data, db_path)


def remove_ignore_pattern(pattern: str, db_path: Path | None = None) -> bool:
    """Remove a name pattern from the ignore list. Returns True if found."""
    data = _load(db_path)
    patterns = data.get("ignore_patterns", [])
    if pattern in patterns:
        patterns.remove(pattern)
        _save(data, db_path)
        return True
    return False


def list_ignore_patterns(db_path: Path | None = None) -> list[str]:
    """Return all ignore patterns."""
    data = _load(db_path)
    return data.get("ignore_patterns", [])


def is_ignored(name: str, db_path: Path | None = None) -> bool:
    """Check if a repo name matches any ignore pattern (fnmatch)."""
    import fnmatch
    patterns = list_ignore_patterns(db_path)
    return any(fnmatch.fnmatch(name, p) for p in patterns)


# --- Notes ---

def set_note(name: str, note: str, db_path: Path | None = None) -> None:
    """Set a note for a repo."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    data.setdefault("notes", {})[name] = note
    _save(data, db_path)


def get_note(name: str, db_path: Path | None = None) -> str | None:
    """Get the note for a repo, or None."""
    data = _load(db_path)
    return data.get("notes", {}).get(name)


def remove_note(name: str, db_path: Path | None = None) -> bool:
    """Remove a note for a repo. Returns True if found."""
    data = _load(db_path)
    notes = data.get("notes", {})
    if name in notes:
        del notes[name]
        _save(data, db_path)
        return True
    return False


def list_notes(db_path: Path | None = None) -> dict[str, str]:
    """Return all repo notes."""
    data = _load(db_path)
    return data.get("notes", {})


# --- Archive ---

def archive_repo(name: str, db_path: Path | None = None) -> None:
    """Mark a repo as archived."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    data["repos"][name]["archived"] = True
    _save(data, db_path)


def unarchive_repo(name: str, db_path: Path | None = None) -> None:
    """Unmark a repo as archived."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    data["repos"][name]["archived"] = False
    _save(data, db_path)


# --- Sync / Reconcile helpers ---

def update_repo_path(name: str, new_path: str, db_path: Path | None = None) -> None:
    """Update the path for a tracked repo."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    data["repos"][name]["path"] = new_path
    _save(data, db_path)


def update_repo_remote(name: str, remote_url: str | None, db_path: Path | None = None) -> None:
    """Update the remote URL for a tracked repo."""
    data = _load(db_path)
    if name not in data["repos"]:
        raise ValueError(f"Repo '{name}' not found")
    data["repos"][name]["remote_url"] = remote_url
    _save(data, db_path)
