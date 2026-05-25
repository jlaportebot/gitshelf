# gitshelf 📚

A CLI tool for managing your local git repositories like a bookshelf. Track, organize, and get insights about all your cloned repos.

## Why?

Developers accumulate dozens of cloned repos. `gitshelf` helps you:

- **Discover** repos you forgot about (with `stale` detection)
- **Organize** repos with tags and categories
- **Audit** repo health (uncommitted changes, unpushed commits, outdated branches)
- **Clean up** repos you no longer need — find stale branches, disk hogs, and zombie repos
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
```

### Health & Insights

```bash
# Quick health check
gitshelf health my-repo

# Detailed summary (commits, contributors, size, stale branches)
gitshelf summary my-repo

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
| `dirty` | Show repos with uncommitted changes |
| `stale` | Show inactive repos |
| `prune` | Find stale branches across repos |
| `sizes` | Show repos sorted by disk size |
| `dashboard` | Overview of all repos |
| `tag <name> <tag...>` | Add tags to a repo |
| `untag <name> <tag...>` | Remove tags from a repo |
| `tags` | List all tags |
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
