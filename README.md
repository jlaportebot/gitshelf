# gitshelf 📚

A CLI tool for managing your local git repositories like a bookshelf. Track, organize, and get insights about all your cloned repos.

## Why?

Developers accumulate dozens of cloned repos. `gitshelf` helps you:

- **Discover** repos you forgot about (with `stale` detection)
- **Organize** repos with tags, categories, and notes
- **Audit** repo health (uncommitted changes, unpushed commits, diverged branches)
- **Clean up** repos you no longer need — find stale branches, disk hogs, and zombie repos
- **Sync** tracked repos to detect moved/deleted directories
- **Archive** repos you want to keep but de-prioritize
- **Export** data as JSON for scripting and automation

## Installation

```bash
pip install gitshelf
```

## Usage

### Scanning & Tracking

```bash
# Scan a directory for git repos
gitshelf scan ~/repos

# Scan two levels deep (e.g., ~/repos/org/repo)
gitshelf scan ~/repos --deep

# Remove a repo from tracking (doesn't delete files)
gitshelf untrack my-repo
```

### Listing & Searching

```bash
# List all tracked repos
gitshelf list

# List only dirty repos
gitshelf list --dirty

# List only archived repos
gitshelf list --archived

# Show archived repos in normal list
gitshelf list --all

# Filter by tag
gitshelf list --tag work

# Search repos by name, path, or tag
gitshelf search python
```

### Organization

```bash
# Tag repos for organization
gitshelf tag my-repo work
gitshelf tag my-repo python

# Remove tags
gitshelf untag my-repo work

# List all tags and their repos
gitshelf tags

# Add a note to a repo
gitshelf note my-repo "This is the main backend service"

# View a note
gitshelf note my-repo --show

# Delete a note
gitshelf note my-repo --delete

# Edit note in $EDITOR
gitshelf note my-repo

# List all repos with notes
gitshelf notes
```

### Ignore Patterns

```bash
# Add an ignore pattern (fnmatch-style) to skip repos during scan
gitshelf ignore "dotfiles"
gitshelf ignore "test-*"

# List all ignore patterns
gitshelf ignore --list

# Remove an ignore pattern
gitshelf ignore "test-*" --remove
```

### Health & Insights

```bash
# Quick health check
gitshelf health my-repo

# Detailed summary (commits, contributors, size, stale branches)
gitshelf summary my-repo

# Show recent commits
gitshelf log my-repo
gitshelf log my-repo -n 10

# Show repos with uncommitted changes
gitshelf dirty

# Show repos with no recent activity
gitshelf stale --days 30

# Find stale branches across all repos
gitshelf prune --days 90

# Show repos sorted by disk size (largest first)
gitshelf sizes

# Dashboard overview
gitshelf dashboard
```

### Sync & Reconcile

```bash
# Verify tracked repos still exist on disk
gitshelf sync

# Sync and attempt to fix broken paths
gitshelf sync --fix-paths

# Find untracked repos on disk and tracked repos missing from disk
gitshelf reconcile ~/repos
```

### Archive

```bash
# Archive a repo (hides from normal list)
gitshelf archive my-repo

# Unarchive a repo
gitshelf unarchive my-repo
```

### JSON Output

Every command supports `--json` output for scripting:

```bash
# JSON output via global flag
gitshelf --json list
gitshelf --json dashboard
gitshelf --json stale

# Or per-command flag
gitshelf list --json
gitshelf health my-repo --json
gitshelf sync --json
gitshelf reconcile ~/repos --json
```

## Configuration

`gitshelf` stores its database at `~/.gitshelf/db.json`. You can customize the path:

```bash
export GITSHELF_DB_PATH=~/.config/gitshelf/db.json
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `scan <dir>` | Scan directory for git repos |
| `list` | List tracked repos |
| `search <query>` | Search repos by name, path, or tag |
| `health <name>` | Health check for a repo |
| `summary <name>` | Detailed repo summary |
| `log <name>` | Show recent commits |
| `dirty` | Show repos with uncommitted changes |
| `stale` | Show inactive repos |
| `prune` | Find stale branches across repos |
| `sizes` | Show repos sorted by disk size |
| `dashboard` | Overview of all repos |
| `sync` | Verify tracked repos exist on disk |
| `reconcile <dir>` | Find untracked/missing repos |
| `tag <name> <tag...>` | Add tags to a repo |
| `untag <name> <tag...>` | Remove tags from a repo |
| `tags` | List all tags |
| `note <name> [text]` | Add/view/delete repo notes |
| `notes` | List all repos with notes |
| `ignore <pattern>` | Add/remove/list ignore patterns |
| `archive <name>` | Mark repo as archived |
| `unarchive <name>` | Unmark repo as archived |
| `untrack <name>` | Stop tracking a repo |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=gitshelf
```

## License

MIT
