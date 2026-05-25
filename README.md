# gitshelf 📚

A CLI tool for managing your local git repositories like a bookshelf. Track, organize, and get insights about all your cloned repos.

## Why?

Developers accumulate dozens of cloned repos. `gitshelf` helps you:
- **Discover** repos you forgot about (with `stale` detection)
- **Organize** repos with tags and categories
- **Audit** repo health (uncommitted changes, unpushed commits, outdated branches)
- **Clean up** repos you no longer need

## Installation

```bash
pip install gitshelf
```

## Usage

```bash
# Scan a directory for git repos
gitshelf scan ~/repos

# List all tracked repos
gitshelf list

# Show repos with uncommitted changes
gitshelf dirty

# Show repos that haven't been touched in 30+ days
gitshelf stale --days 30

# Tag repos for organization
gitshelf tag my-repo work
gitshelf tag my-repo python

# List repos by tag
gitshelf list --tag work

# Get a health report for a repo
gitshelf health my-repo

# Remove tracking for a repo (doesn't delete files)
gitshelf untrack my-repo

# Get a summary dashboard
gitshelf dashboard
```

## Configuration

`gitshelf` stores its database at `~/.gitshelf/db.json`. You can customize the path:

```bash
export GITSHelf_DB_PATH=~/.config/gitshelf/db.json
```

## License

MIT
