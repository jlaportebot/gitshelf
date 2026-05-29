"""CLI interface for gitshelf."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from gitshelf import __version__
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
    add_ignore_pattern,
    remove_ignore_pattern,
    list_ignore_patterns,
    is_ignored,
    set_note,
    get_note,
    remove_note,
    list_notes,
    archive_repo,
    unarchive_repo,
    update_repo_path,
    update_repo_remote,
)
from gitshelf.git_utils import (
    is_git_repo,
    scan_directory,
    get_health_report,
    get_summary,
    has_uncommitted_changes,
    get_last_commit_date,
    get_repo_size,
    get_current_branch,
    get_remote_url,
    get_worktree_status,
    get_recent_commits,
    has_diverged,
)

console = Console()


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


@click.group()
@click.version_option(__version__)
@click.option("--json-output", "--json", "json_output", is_flag=True, help="Output as JSON.")
@click.pass_context
def main(ctx: click.Context, json_output: bool) -> None:
    """gitshelf 📚 — Manage your local git repos like a bookshelf."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


@main.command()
@click.argument("directory")
@click.option("--deep", is_flag=True, help="Scan two levels deep instead of one.")
@click.pass_context
def scan(ctx: click.Context, directory: str, deep: bool) -> None:
    """Scan a directory for git repos and add them to the shelf."""
    repos = scan_directory(directory, deep=deep)
    if not repos:
        if ctx.obj["json"]:
            click.echo(json.dumps({"added": 0, "skipped": 0, "ignored": 0, "repos": []}))
        else:
            console.print(f"[yellow]No git repos found in {directory}[/yellow]")
        return

    added = 0
    skipped = 0
    ignored = 0
    added_repos = []
    for repo in repos:
        existing = get_repo(repo["name"])
        if existing:
            skipped += 1
            continue
        if is_ignored(repo["name"]):
            ignored += 1
            continue
        add_repo(repo["name"], repo["path"], repo.get("remote_url"))
        added_repos.append({"name": repo["name"], "path": repo["path"]})
        added += 1

    if ctx.obj["json"]:
        click.echo(json.dumps({"added": added, "skipped": skipped, "ignored": ignored, "repos": added_repos}))
    else:
        parts = [f"{added} repos added"]
        if skipped:
            parts.append(f"{skipped} already tracked")
        if ignored:
            parts.append(f"{ignored} ignored")
        console.print(f"[green]✓ Scanned {directory}: {', '.join(parts)}[/green]")


@main.command("list")
@click.option("--tag", "-t", help="Filter by tag.")
@click.option("--dirty", is_flag=True, help="Show only repos with uncommitted changes.")
@click.option("--archived", is_flag=True, help="Show only archived repos.")
@click.option("--all", "show_all", is_flag=True, help="Show archived repos too.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def list_cmd(ctx: click.Context, tag: str | None, dirty: bool, archived: bool, show_all: bool, json_flag: bool) -> None:
    """List all tracked repos."""
    use_json = ctx.obj.get("json") or json_flag
    include_archived = show_all or archived
    repos = list_repos(include_archived=include_archived)
    if not repos:
        if use_json:
            click.echo(json.dumps([]))
        else:
            console.print("[yellow]No repos tracked. Use 'gitshelf scan' to add some.[/yellow]")
        return

    if tag:
        names = get_repos_by_tag(tag)
        repos = {n: repos[n] for n in names if n in repos}

    result = []
    for name, info in sorted(repos.items()):
        is_archived = info.get("archived", False)
        if archived and not is_archived:
            continue
        repo_path = info["path"]
        is_dirty = has_uncommitted_changes(repo_path) if is_git_repo(repo_path) else False
        if dirty and not is_dirty:
            continue
        result.append({
            "name": name,
            "path": repo_path,
            "tags": info.get("tags", []),
            "dirty": is_dirty,
            "archived": is_archived,
            "added_at": info.get("added_at", ""),
        })

    if use_json:
        click.echo(json.dumps(result, indent=2, default=str))
        return

    table = Table(title="📚 Git Shelf", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Path", style="dim")
    table.add_column("Tags", style="magenta")
    table.add_column("Added", style="dim")

    for r in result:
        dirty_mark = " [red]●[/red]" if r["dirty"] else ""
        archived_mark = " [dim](archived)[/dim]" if r["archived"] else ""
        tags_str = ", ".join(r["tags"])
        added = r["added_at"][:10] if r["added_at"] else ""
        table.add_row(f"{r['name']}{dirty_mark}{archived_mark}", r["path"], tags_str, added)

    console.print(table)


@main.command()
@click.argument("name")
@click.argument("tags", nargs=-1, required=True)
def tag(name: str, tags: tuple[str, ...]) -> None:
    """Add one or more tags to a repo."""
    for t in tags:
        try:
            tag_repo(name, t)
            console.print(f"[green]✓ Tagged '{name}' with '{t}'[/green]")
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")


@main.command()
@click.argument("name")
@click.argument("tags", nargs=-1, required=True)
def untag(name: str, tags: tuple[str, ...]) -> None:
    """Remove one or more tags from a repo."""
    for t in tags:
        untag_repo(name, t)
        console.print(f"[green]✓ Removed tag '{t}' from '{name}'[/green]")


@main.command()
@click.argument("name")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def health(ctx: click.Context, name: str, json_flag: bool) -> None:
    """Show a health report for a repo."""
    use_json = ctx.obj.get("json") or json_flag
    repo = get_repo(name)
    if not repo:
        console.print(f"[red]Repo '{name}' not found on shelf[/red]")
        sys.exit(1)

    report = get_health_report(repo["path"])

    if use_json:
        click.echo(json.dumps(report, indent=2, default=str))
        return

    panel_content = []
    panel_content.append(f"[cyan]Path:[/cyan] {report['path']}")
    panel_content.append(f"[cyan]Branch:[/cyan] {report['branch'] or 'detached'}")
    panel_content.append(f"[cyan]Dirty:[/cyan] {'[red]Yes[/red]' if report['dirty'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Unpushed:[/cyan] {'[yellow]Yes[/yellow]' if report['unpushed'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Stashes:[/cyan] {report['stashes']}")
    panel_content.append(f"[cyan]Branches:[/cyan] {report['branches']}")
    lc = report["last_commit"]
    panel_content.append(f"[cyan]Last commit:[/cyan] {lc.strftime('%Y-%m-%d %H:%M') if lc else 'N/A'}")

    # Diverged status
    try:
        if has_diverged(repo["path"]):
            panel_content.append("[yellow]Diverged:[/yellow] Yes (ahead and behind upstream)")
    except Exception:
        pass

    console.print(Panel("\n".join(panel_content), title=f"🏥 {name}", border_style="blue"))


@main.command()
@click.argument("name")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def summary(ctx: click.Context, name: str, json_flag: bool) -> None:
    """Show a detailed summary for a repo."""
    use_json = ctx.obj.get("json") or json_flag
    repo = get_repo(name)
    if not repo:
        console.print(f"[red]Repo '{name}' not found on shelf[/red]")
        sys.exit(1)

    data = get_summary(repo["path"])
    note_text = get_note(name)

    if use_json:
        data["note"] = note_text
        data["archived"] = repo.get("archived", False)
        click.echo(json.dumps(data, indent=2, default=str))
        return

    panel_content = []
    panel_content.append(f"[cyan]Path:[/cyan] {data['path']}")
    panel_content.append(f"[cyan]Branch:[/cyan] {data['branch'] or 'detached'}")
    panel_content.append(f"[cyan]Remote:[/cyan] {data['remote_url'] or 'none'}")
    panel_content.append(f"[cyan]Commits:[/cyan] {data['commit_count']}")
    panel_content.append(f"[cyan]Dirty:[/cyan] {'[red]Yes[/red]' if data['dirty'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Unpushed:[/cyan] {'[yellow]Yes[/yellow]' if data['unpushed'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Stashes:[/cyan] {data['stashes']}")
    panel_content.append(f"[cyan]Branches:[/cyan] {data['branches']} local")
    panel_content.append(f"[cyan]Size:[/cyan] {_format_size(data['size_bytes'])}")
    if repo.get("archived"):
        panel_content.append("[dim]Archived: Yes[/dim]")
    lc = data["last_commit"]
    panel_content.append(f"[cyan]Last commit:[/cyan] {lc.strftime('%Y-%m-%d %H:%M') if lc else 'N/A'}")

    if note_text:
        panel_content.append(f"[cyan]Note:[/cyan] {note_text}")

    if data["stale_branches"]:
        stale_names = ", ".join(b["branch"] for b in data["stale_branches"])
        panel_content.append(f"[yellow]Stale branches:[/yellow] {stale_names}")

    if data["contributors"]:
        top = data["contributors"][:5]
        contrib_str = ", ".join(f"{c['name']} ({c['commits']})" for c in top)
        panel_content.append(f"[cyan]Top contributors:[/cyan] {contrib_str}")

    console.print(Panel("\n".join(panel_content), title=f"📊 {name}", border_style="blue"))


@main.command()
@click.option("--days", default=30, help="Number of days to consider stale.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def stale(ctx: click.Context, days: int, json_flag: bool) -> None:
    """Show repos with no recent activity."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps([]))
        else:
            console.print("[yellow]No repos tracked.[/yellow]")
        return

    threshold = datetime.now() - timedelta(days=days)
    stale_repos = []

    for name, info in sorted(repos.items()):
        lc = get_last_commit_date(info["path"])
        if lc:
            lc_naive = lc.replace(tzinfo=None) if lc.tzinfo else lc
            if lc_naive < threshold:
                delta = (datetime.now() - lc_naive).days
                stale_repos.append({"name": name, "last_commit": lc_naive.isoformat(), "days_idle": delta})
        elif not lc:
            stale_repos.append({"name": name, "last_commit": None, "days_idle": None})

    if use_json:
        click.echo(json.dumps(stale_repos, indent=2, default=str))
        return

    if stale_repos:
        table = Table(title=f"🕸️ Stale Repos (>{days}d)", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Last Commit", style="yellow")
        table.add_column("Days Idle", style="red")
        for r in stale_repos:
            lc_str = r["last_commit"][:10] if r["last_commit"] else "unknown"
            idle_str = str(r["days_idle"]) if r["days_idle"] is not None else "—"
            table.add_row(r["name"], lc_str, idle_str)
        console.print(table)
    else:
        console.print("[green]All repos are active! No stale repos found.[/green]")


@main.command()
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def dirty(ctx: click.Context, json_flag: bool) -> None:
    """Show repos with uncommitted changes."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps([]))
        else:
            console.print("[yellow]No repos tracked.[/yellow]")
        return

    dirty_repos = []
    for name, info in sorted(repos.items()):
        if is_git_repo(info["path"]) and has_uncommitted_changes(info["path"]):
            dirty_repos.append({"name": name, "path": info["path"]})

    if use_json:
        click.echo(json.dumps(dirty_repos, indent=2))
        return

    if dirty_repos:
        table = Table(title="🔴 Dirty Repos", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="dim")
        for r in dirty_repos:
            table.add_row(r["name"], r["path"])
        console.print(table)
    else:
        console.print("[green]All repos are clean! 🧹[/green]")


@main.command()
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def dashboard(ctx: click.Context, json_flag: bool) -> None:
    """Show a summary dashboard of all repos."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps({"total": 0}))
        else:
            console.print("[yellow]No repos tracked. Use 'gitshelf scan' to add some.[/yellow]")
        return

    total = len(repos)
    dirty_count = 0
    stale_count = 0
    unpushed_count = 0
    diverged_count = 0
    archived_count = 0
    total_size = 0
    threshold = datetime.now() - timedelta(days=30)

    for name, info in repos.items():
        path = info["path"]
        if info.get("archived", False):
            archived_count += 1
        if is_git_repo(path):
            if has_uncommitted_changes(path):
                dirty_count += 1
            lc = get_last_commit_date(path)
            if lc:
                lc_naive = lc.replace(tzinfo=None) if lc.tzinfo else lc
                if lc_naive < threshold:
                    stale_count += 1
            from gitshelf.git_utils import has_unpushed_commits
            if has_unpushed_commits(path):
                unpushed_count += 1
            try:
                if has_diverged(path):
                    diverged_count += 1
            except Exception:
                pass
            total_size += get_repo_size(path)

    tags = list_tags()
    tag_count = len(tags)
    notes = list_notes()
    note_count = len(notes)

    result = {
        "total": total,
        "dirty": dirty_count,
        "unpushed": unpushed_count,
        "diverged": diverged_count,
        "stale": stale_count,
        "archived": archived_count,
        "tags": tag_count,
        "notes": note_count,
        "total_size": total_size,
        "total_size_human": _format_size(total_size),
    }

    if use_json:
        click.echo(json.dumps(result, indent=2))
        return

    panel = Panel(
        f"[cyan]Total repos:[/cyan] {total}\n"
        f"[red]Dirty:[/red] {dirty_count}\n"
        f"[yellow]Unpushed:[/yellow] {unpushed_count}\n"
        f"[magenta]Diverged:[/magenta] {diverged_count}\n"
        f"[dim]Stale (>30d):[/dim] {stale_count}\n"
        f"[dim]Archived:[/dim] {archived_count}\n"
        f"[magenta]Tags:[/magenta] {tag_count}\n"
        f"[blue]Notes:[/blue] {note_count}\n"
        f"[blue]Total size:[/blue] {_format_size(total_size)}",
        title="📚 Git Shelf Dashboard",
        border_style="blue",
    )
    console.print(panel)


@main.command()
@click.argument("name")
def untrack(name: str) -> None:
    """Remove a repo from the shelf (doesn't delete files)."""
    if remove_repo(name):
        console.print(f"[green]✓ Untracked '{name}'[/green]")
    else:
        console.print(f"[red]Repo '{name}' not found on shelf[/red]")
        sys.exit(1)


@main.command()
def tags() -> None:
    """List all tags and their repos."""
    all_tags = list_tags()
    if not all_tags:
        console.print("[yellow]No tags created yet. Use 'gitshelf tag' to add some.[/yellow]")
        return

    table = Table(title="🏷️ Tags", box=box.ROUNDED)
    table.add_column("Tag", style="magenta")
    table.add_column("Repos", style="cyan")
    table.add_column("Count", style="dim")

    for tag, repo_names in sorted(all_tags.items()):
        table.add_row(tag, ", ".join(repo_names), str(len(repo_names)))

    console.print(table)


@main.command()
@click.argument("query")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def search(ctx: click.Context, query: str, json_flag: bool) -> None:
    """Search repos by name, tag, or path."""
    use_json = ctx.obj.get("json") or json_flag
    results = search_repos(query)

    if use_json:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    if not results:
        console.print(f"[yellow]No repos matching '{query}'[/yellow]")
        return

    table = Table(title=f"🔍 Search: {query}", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Tags", style="magenta")
    table.add_column("Match", style="green")

    for r in results:
        tags_str = ", ".join(r.get("tags", []))
        table.add_row(r["name"], r["path"], tags_str, r["match_type"])

    console.print(table)


@main.command()
@click.option("--days", default=90, help="Days of inactivity to consider a branch stale.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def prune(ctx: click.Context, days: int, json_flag: bool) -> None:
    """Show repos with stale branches that could be cleaned up."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps([]))
        else:
            console.print("[yellow]No repos tracked.[/yellow]")
        return

    from gitshelf.git_utils import get_stale_branches

    prune_repos = []
    for name, info in sorted(repos.items()):
        if not is_git_repo(info["path"]):
            continue
        stale_branches = get_stale_branches(info["path"], days=days)
        if stale_branches:
            prune_repos.append({
                "name": name,
                "path": info["path"],
                "stale_branches": stale_branches,
            })

    if use_json:
        click.echo(json.dumps(prune_repos, indent=2, default=str))
        return

    if not prune_repos:
        console.print(f"[green]No repos with stale branches (>{days}d). 🧹[/green]")
        return

    for r in prune_repos:
        table = Table(title=f"🌿 {r['name']} — Stale Branches", box=box.ROUNDED)
        table.add_column("Branch", style="yellow")
        table.add_column("Days Idle", style="red")
        for b in r["stale_branches"]:
            table.add_row(b["branch"], str(b["days_idle"]))
        console.print(table)


@main.command()
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def sizes(ctx: click.Context, json_flag: bool) -> None:
    """Show repos sorted by disk size (largest first)."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps([]))
        else:
            console.print("[yellow]No repos tracked.[/yellow]")
        return

    repo_sizes = []
    for name, info in repos.items():
        if is_git_repo(info["path"]):
            size = get_repo_size(info["path"])
            repo_sizes.append({"name": name, "size_bytes": size, "size_human": _format_size(size)})

    repo_sizes.sort(key=lambda x: x["size_bytes"], reverse=True)

    if use_json:
        click.echo(json.dumps(repo_sizes, indent=2))
        return

    table = Table(title="📦 Repos by Size", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="yellow", justify="right")
    for r in repo_sizes:
        table.add_row(r["name"], r["size_human"])

    console.print(table)


# --- New v0.3.0 commands ---


@main.command()
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--fix-paths", is_flag=True, help="Attempt to fix broken paths by re-scanning parent dirs.")
@click.pass_context
def sync(ctx: click.Context, json_flag: bool, fix_paths: bool) -> None:
    """Verify tracked repos still exist on disk and update metadata."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
    if not repos:
        if use_json:
            click.echo(json.dumps({"checked": 0, "ok": 0, "missing": 0, "updated": []}))
        else:
            console.print("[yellow]No repos tracked.[/yellow]")
        return

    ok_count = 0
    missing = []
    updated = []

    for name, info in sorted(repos.items()):
        path = info["path"]
        if is_git_repo(path):
            ok_count += 1
            # Update remote URL if changed
            new_remote = get_remote_url(path)
            old_remote = info.get("remote_url")
            if new_remote != old_remote:
                update_repo_remote(name, new_remote)
                updated.append({"name": name, "field": "remote_url", "old": old_remote, "new": new_remote})
        else:
            missing.append({"name": name, "path": path})

    if fix_paths and missing:
        for m in missing:
            parent = str(Path(m["path"]).parent)
            if Path(parent).is_dir():
                found = scan_directory(parent, deep=False)
                for r in found:
                    if r["name"] == m["name"]:
                        update_repo_path(m["name"], r["path"])
                        new_remote = get_remote_url(r["path"])
                        if new_remote != get_repo(m["name"]).get("remote_url"):
                            update_repo_remote(m["name"], new_remote)
                        updated.append({"name": m["name"], "field": "path", "old": m["path"], "new": r["path"]})
                        missing = [x for x in missing if x["name"] != m["name"]]
                        ok_count += 1
                        break

    result = {
        "checked": len(repos),
        "ok": ok_count,
        "missing": [m["name"] for m in missing],
        "updated": updated,
    }

    if use_json:
        click.echo(json.dumps(result, indent=2, default=str))
        return

    if missing:
        table = Table(title="❌ Missing Repos", box=box.ROUNDED)
        table.add_column("Name", style="red")
        table.add_column("Path", style="dim")
        for m in missing:
            table.add_row(m["name"], m["path"])
        console.print(table)

    if updated:
        for u in updated:
            console.print(f"[yellow]↻ Updated {u['name']}: {u['field']} changed[/yellow]")

    console.print(f"[green]✓ Synced: {ok_count} ok, {len(missing)} missing, {len(updated)} updated[/green]")


@main.command()
@click.argument("name")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def archive(ctx: click.Context, name: str, json_flag: bool) -> None:
    """Mark a repo as archived (hidden from normal list)."""
    use_json = ctx.obj.get("json") or json_flag
    try:
        archive_repo(name)
        if use_json:
            click.echo(json.dumps({"name": name, "archived": True}))
        else:
            console.print(f"[green]✓ Archived '{name}'[/green]")
    except ValueError as e:
        if use_json:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def unarchive(ctx: click.Context, name: str, json_flag: bool) -> None:
    """Unmark a repo as archived."""
    use_json = ctx.obj.get("json") or json_flag
    try:
        unarchive_repo(name)
        if use_json:
            click.echo(json.dumps({"name": name, "archived": False}))
        else:
            console.print(f"[green]✓ Unarchived '{name}'[/green]")
    except ValueError as e:
        if use_json:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@main.command("ignore")
@click.argument("pattern", required=False)
@click.option("--remove", "-r", is_flag=True, help="Remove the pattern instead of adding it.")
@click.option("--list", "list_all", is_flag=True, help="List all ignore patterns.")
@click.pass_context
def ignore_cmd(ctx: click.Context, pattern: str | None, remove: bool, list_all: bool) -> None:
    """Add, remove, or list ignore patterns for scan (fnmatch-style)."""
    if list_all:
        patterns = list_ignore_patterns()
        if not patterns:
            console.print("[yellow]No ignore patterns set.[/yellow]")
            return
        table = Table(title="🚫 Ignore Patterns", box=box.ROUNDED)
        table.add_column("Pattern", style="yellow")
        for p in patterns:
            table.add_row(p)
        console.print(table)
        return

    if not pattern:
        console.print("[red]Provide a pattern or use --list[/red]")
        sys.exit(1)

    if remove:
        if remove_ignore_pattern(pattern):
            console.print(f"[green]✓ Removed ignore pattern '{pattern}'[/green]")
        else:
            console.print(f"[yellow]Pattern '{pattern}' not found[/yellow]")
    else:
        add_ignore_pattern(pattern)
        console.print(f"[green]✓ Added ignore pattern '{pattern}'[/green]")


@main.command("note")
@click.argument("name")
@click.argument("text", required=False)
@click.option("--delete", "-d", is_flag=True, help="Delete the note for this repo.")
@click.option("--show", "-s", is_flag=True, help="Show the note for this repo.")
@click.pass_context
def note_cmd(ctx: click.Context, name: str, text: str | None, delete: bool, show: bool) -> None:
    """Add, view, or delete a note for a repo."""
    if delete:
        if remove_note(name):
            console.print(f"[green]✓ Note removed for '{name}'[/green]")
        else:
            console.print(f"[yellow]No note found for '{name}'[/yellow]")
        return

    if show:
        note = get_note(name)
        if note:
            console.print(Panel(note, title=f"📝 {name}", border_style="green"))
        else:
            console.print(f"[yellow]No note for '{name}'[/yellow]")
        return

    if text:
        try:
            set_note(name, text)
            console.print(f"[green]✓ Note set for '{name}'[/green]")
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            sys.exit(1)
    else:
        # Open editor if no text given
        import tempfile
        existing = get_note(name) or ""
        editor = os.environ.get("EDITOR", "nano")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, prefix=f"gitshelf-note-{name}-") as f:
            f.write(existing)
            tmppath = f.name
        try:
            os.system(f"{editor} {tmppath}")
            with open(tmppath) as f:
                new_text = f.read().strip()
            if new_text:
                try:
                    set_note(name, new_text)
                    console.print(f"[green]✓ Note set for '{name}'[/green]")
                except ValueError as e:
                    console.print(f"[red]✗ {e}[/red]")
            elif existing:
                remove_note(name)
                console.print(f"[green]✓ Note cleared for '{name}'[/green]")
        finally:
            os.unlink(tmppath)


@main.command("notes")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def notes_cmd(ctx: click.Context, json_flag: bool) -> None:
    """List all repos with notes."""
    use_json = ctx.obj.get("json") or json_flag
    all_notes = list_notes()
    if not all_notes:
        if use_json:
            click.echo(json.dumps({}))
        else:
            console.print("[yellow]No notes set. Use 'gitshelf note' to add some.[/yellow]")
        return

    if use_json:
        click.echo(json.dumps(all_notes, indent=2))
        return

    table = Table(title="📝 Notes", box=box.ROUNDED)
    table.add_column("Repo", style="cyan")
    table.add_column("Note", style="dim", max_width=60)
    for name, note in sorted(all_notes.items()):
        # Truncate for display
        display = note[:80] + "…" if len(note) > 80 else note
        table.add_row(name, display)
    console.print(table)


@main.command()
@click.argument("directory")
@click.option("--deep", is_flag=True, help="Scan two levels deep.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def reconcile(ctx: click.Context, directory: str, deep: bool, json_flag: bool) -> None:
    """Find untracked repos on disk and tracked repos missing from disk."""
    use_json = ctx.obj.get("json") or json_flag

    repos = list_repos()
    tracked_paths = {info["path"]: name for name, info in repos.items()}

    # Find repos on disk not tracked
    disk_repos = scan_directory(directory, deep=deep)
    untracked = []
    for r in disk_repos:
        if r["path"] not in tracked_paths and not is_ignored(r["name"]):
            untracked.append({"name": r["name"], "path": r["path"]})

    # Find tracked repos not on disk
    gone = []
    for name, info in repos.items():
        if not is_git_repo(info["path"]):
            gone.append({"name": name, "path": info["path"]})

    # Find tracked repos on disk but missing from scan directory
    missing_from_dir = []
    disk_paths = {r["path"] for r in disk_repos}
    for name, info in repos.items():
        if is_git_repo(info["path"]) and info["path"] not in disk_paths:
            missing_from_dir.append({"name": name, "path": info["path"]})

    result = {
        "scan_directory": str(Path(directory).resolve()),
        "untracked": untracked,
        "gone": gone,
        "tracked_not_in_scan_dir": missing_from_dir,
    }

    if use_json:
        click.echo(json.dumps(result, indent=2, default=str))
        return

    if untracked:
        table = Table(title="🔍 Untracked Repos (on disk but not tracked)", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="dim")
        for r in untracked:
            table.add_row(r["name"], r["path"])
        console.print(table)

    if gone:
        table = Table(title="❌ Gone Repos (tracked but not on disk)", box=box.ROUNDED)
        table.add_column("Name", style="red")
        table.add_column("Path", style="dim")
        for r in gone:
            table.add_row(r["name"], r["path"])
        console.print(table)

    if not untracked and not gone:
        console.print("[green]✓ All repos reconciled — no discrepancies found.[/green]")


@main.command("log")
@click.argument("name")
@click.option("--count", "-n", default=5, help="Number of commits to show.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def log_cmd(ctx: click.Context, name: str, count: int, json_flag: bool) -> None:
    """Show recent commits for a repo."""
    use_json = ctx.obj.get("json") or json_flag
    repo = get_repo(name)
    if not repo:
        console.print(f"[red]Repo '{name}' not found on shelf[/red]")
        sys.exit(1)

    commits = get_recent_commits(repo["path"], count=count)

    if use_json:
        click.echo(json.dumps(commits, indent=2, default=str))
        return

    if not commits:
        console.print(f"[yellow]No commits found for '{name}'[/yellow]")
        return

    table = Table(title=f"📜 {name} — Recent Commits", box=box.ROUNDED)
    table.add_column("Hash", style="yellow", no_wrap=True, max_width=9)
    table.add_column("Author", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Subject", style="white")

    for c in commits:
        short_hash = c["hash"][:8]
        date_str = c["date"][:10] if c["date"] else ""
        table.add_row(short_hash, c["author"], date_str, c["subject"])

    console.print(table)


if __name__ == "__main__":
    main()
