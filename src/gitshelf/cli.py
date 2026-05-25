"""CLI interface for gitshelf."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

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
)
from gitshelf.git_utils import (
    is_git_repo,
    scan_directory,
    get_health_report,
    get_summary,
    has_uncommitted_changes,
    get_last_commit_date,
    get_repo_size,
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
            click.echo(json.dumps({"added": 0, "skipped": 0, "repos": []}))
        else:
            console.print(f"[yellow]No git repos found in {directory}[/yellow]")
        return

    added = 0
    skipped = 0
    added_repos = []
    for repo in repos:
        existing = get_repo(repo["name"])
        if existing:
            skipped += 1
            continue
        add_repo(repo["name"], repo["path"], repo.get("remote_url"))
        added_repos.append({"name": repo["name"], "path": repo["path"]})
        added += 1

    if ctx.obj["json"]:
        click.echo(json.dumps({"added": added, "skipped": skipped, "repos": added_repos}))
    else:
        console.print(f"[green]✓ Scanned {directory}: {added} repos added, {skipped} already tracked[/green]")


@main.command("list")
@click.option("--tag", "-t", help="Filter by tag.")
@click.option("--dirty", is_flag=True, help="Show only repos with uncommitted changes.")
@click.option("--json-output", "--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def list_cmd(ctx: click.Context, tag: str | None, dirty: bool, json_flag: bool) -> None:
    """List all tracked repos."""
    use_json = ctx.obj.get("json") or json_flag
    repos = list_repos()
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
        repo_path = info["path"]
        is_dirty = has_uncommitted_changes(repo_path) if is_git_repo(repo_path) else False
        if dirty and not is_dirty:
            continue
        result.append({
            "name": name,
            "path": repo_path,
            "tags": info.get("tags", []),
            "dirty": is_dirty,
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
        tags_str = ", ".join(r["tags"])
        added = r["added_at"][:10] if r["added_at"] else ""
        table.add_row(f"{r['name']}{dirty_mark}", r["path"], tags_str, added)

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
    from gitshelf.db import untag_repo
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

    if use_json:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    panel_content = []
    panel_content.append(f"[cyan]Path:[/cyan]        {data['path']}")
    panel_content.append(f"[cyan]Branch:[/cyan]     {data['branch'] or 'detached'}")
    panel_content.append(f"[cyan]Remote:[/cyan]     {data['remote_url'] or 'none'}")
    panel_content.append(f"[cyan]Commits:[/cyan]    {data['commit_count']}")
    panel_content.append(f"[cyan]Dirty:[/cyan]      {'[red]Yes[/red]' if data['dirty'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Unpushed:[/cyan]   {'[yellow]Yes[/yellow]' if data['unpushed'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Stashes:[/cyan]    {data['stashes']}")
    panel_content.append(f"[cyan]Branches:[/cyan]   {data['branches']} local")
    panel_content.append(f"[cyan]Size:[/cyan]       {_format_size(data['size_bytes'])}")
    lc = data["last_commit"]
    panel_content.append(f"[cyan]Last commit:[/cyan] {lc.strftime('%Y-%m-%d %H:%M') if lc else 'N/A'}")

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
    total_size = 0
    threshold = datetime.now() - timedelta(days=30)

    for name, info in repos.items():
        path = info["path"]
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
            total_size += get_repo_size(path)

    tags = list_tags()
    tag_count = len(tags)

    result = {
        "total": total,
        "dirty": dirty_count,
        "unpushed": unpushed_count,
        "stale": stale_count,
        "tags": tag_count,
        "total_size": total_size,
        "total_size_human": _format_size(total_size),
    }

    if use_json:
        click.echo(json.dumps(result, indent=2))
        return

    panel = Panel(
        f"[cyan]Total repos:[/cyan]    {total}\n"
        f"[red]Dirty:[/red]           {dirty_count}\n"
        f"[yellow]Unpushed:[/yellow]       {unpushed_count}\n"
        f"[dim]Stale (>30d):[/dim]      {stale_count}\n"
        f"[magenta]Tags:[/magenta]          {tag_count}\n"
        f"[blue]Total size:[/blue]     {_format_size(total_size)}",
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


if __name__ == "__main__":
    main()
