"""CLI interface for gitshelf."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
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
)
from gitshelf.git_utils import (
    is_git_repo,
    scan_directory,
    get_health_report,
    has_uncommitted_changes,
    get_last_commit_date,
)

console = Console()


@click.group()
@click.version_option(__version__)
def main():
    """gitshelf 📚 — Manage your local git repos like a bookshelf."""
    pass


@main.command()
@click.argument("directory")
@click.option("--deep", is_flag=True, help="Scan two levels deep instead of one.")
def scan(directory: str, deep: bool) -> None:
    """Scan a directory for git repos and add them to the shelf."""
    repos = scan_directory(directory)
    if not repos:
        console.print(f"[yellow]No git repos found in {directory}[/yellow]")
        return

    added = 0
    skipped = 0
    for repo in repos:
        existing = get_repo(repo["name"])
        if existing:
            skipped += 1
            continue
        add_repo(repo["name"], repo["path"], repo.get("remote_url"))
        added += 1

    console.print(f"[green]✓ Scanned {directory}: {added} repos added, {skipped} already tracked[/green]")


@main.command("list")
@click.option("--tag", "-t", help="Filter by tag.")
@click.option("--dirty", is_flag=True, help="Show only repos with uncommitted changes.")
def list_cmd(tag: str | None, dirty: bool) -> None:
    """List all tracked repos."""
    repos = list_repos()
    if not repos:
        console.print("[yellow]No repos tracked. Use 'gitshelf scan' to add some.[/yellow]")
        return

    if tag:
        names = get_repos_by_tag(tag)
        repos = {n: repos[n] for n in names if n in repos}

    table = Table(title="📚 Git Shelf", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Path", style="dim")
    table.add_column("Tags", style="magenta")
    table.add_column("Added", style="dim")

    for name, info in sorted(repos.items()):
        repo_path = info["path"]
        is_dirty = has_uncommitted_changes(repo_path) if is_git_repo(repo_path) else False
        if dirty and not is_dirty:
            continue
        dirty_mark = " [red]●[/red]" if is_dirty else ""
        tags = ", ".join(info.get("tags", []))
        added = info.get("added_at", "")[:10]
        table.add_row(f"{name}{dirty_mark}", repo_path, tags, added)

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
def health(name: str) -> None:
    """Show a health report for a repo."""
    repo = get_repo(name)
    if not repo:
        console.print(f"[red]Repo '{name}' not found on shelf[/red]")
        sys.exit(1)

    report = get_health_report(repo["path"])
    panel_content = []
    panel_content.append(f"[cyan]Path:[/cyan]     {report['path']}")
    panel_content.append(f"[cyan]Branch:[/cyan]   {report['branch'] or 'detached'}")
    panel_content.append(f"[cyan]Dirty:[/cyan]    {'[red]Yes[/red]' if report['dirty'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Unpushed:[/cyan] {'[yellow]Yes[/yellow]' if report['unpushed'] else '[green]No[/green]'}")
    panel_content.append(f"[cyan]Stashes:[/cyan]  {report['stashes']}")
    panel_content.append(f"[cyan]Branches:[/cyan] {report['branches']}")
    lc = report["last_commit"]
    panel_content.append(f"[cyan]Last commit:[/cyan] {lc.strftime('%Y-%m-%d %H:%M') if lc else 'N/A'}")

    console.print(Panel("\n".join(panel_content), title=f"🏥 {name}", border_style="blue"))


@main.command()
@click.option("--days", default=30, help="Number of days to consider stale.")
def stale(days: int) -> None:
    """Show repos with no recent activity."""
    repos = list_repos()
    if not repos:
        console.print("[yellow]No repos tracked.[/yellow]")
        return

    threshold = datetime.now() - timedelta(days=days)
    table = Table(title=f"🕸️  Stale Repos (>{days}d)", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Last Commit", style="yellow")
    table.add_column("Days Idle", style="red")

    found = False
    for name, info in sorted(repos.items()):
        lc = get_last_commit_date(info["path"])
        if lc:
            lc_naive = lc.replace(tzinfo=None) if lc.tzinfo else lc
            if lc_naive < threshold:
                delta = (datetime.now() - lc_naive).days
                table.add_row(name, lc_naive.strftime("%Y-%m-%d"), str(delta))
                found = True
        elif not lc:
            table.add_row(name, "unknown", "—")
            found = True

    if found:
        console.print(table)
    else:
        console.print("[green]All repos are active! No stale repos found.[/green]")


@main.command()
def dirty() -> None:
    """Show repos with uncommitted changes."""
    repos = list_repos()
    if not repos:
        console.print("[yellow]No repos tracked.[/yellow]")
        return

    table = Table(title="🔴 Dirty Repos", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")

    found = False
    for name, info in sorted(repos.items()):
        if is_git_repo(info["path"]) and has_uncommitted_changes(info["path"]):
            table.add_row(name, info["path"])
            found = True

    if found:
        console.print(table)
    else:
        console.print("[green]All repos are clean! 🧹[/green]")


@main.command()
def dashboard() -> None:
    """Show a summary dashboard of all repos."""
    repos = list_repos()
    if not repos:
        console.print("[yellow]No repos tracked. Use 'gitshelf scan' to add some.[/yellow]")
        return

    total = len(repos)
    dirty_count = 0
    stale_count = 0
    unpushed_count = 0
    threshold = datetime.now() - timedelta(days=30)

    for name, info in repos.items():
        path = info["path"]
        if is_git_repo(path):
            if has_uncommitted_changes(path):
                dirty_count += 1
        lc = get_last_commit_date(path)
        if lc:
            # Ensure both datetimes are offset-naive for comparison
            lc_naive = lc.replace(tzinfo=None) if lc.tzinfo else lc
            if lc_naive < threshold:
                stale_count += 1
            from gitshelf.git_utils import has_unpushed_commits
            if has_unpushed_commits(path):
                unpushed_count += 1

    tags = list_tags()
    tag_count = len(tags)

    panel = Panel(
        f"[cyan]Total repos:[/cyan]   {total}\n"
        f"[red]Dirty:[/red]          {dirty_count}\n"
        f"[yellow]Unpushed:[/yellow]       {unpushed_count}\n"
        f"[dim]Stale (>30d):[/dim]    {stale_count}\n"
        f"[magenta]Tags:[/magenta]          {tag_count}",
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

    table = Table(title="🏷️  Tags", box=box.ROUNDED)
    table.add_column("Tag", style="magenta")
    table.add_column("Repos", style="cyan")
    table.add_column("Count", style="dim")

    for tag, repo_names in sorted(all_tags.items()):
        table.add_row(tag, ", ".join(repo_names), str(len(repo_names)))

    console.print(table)


if __name__ == "__main__":
    main()
