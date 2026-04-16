"""ShipCadence CLI entry point."""

from __future__ import annotations

from typing import Any

import click
from rich.console import Console
from rich.table import Table

from shipcadence.config import RepoConfig

console = Console()

_RATING_COLOURS: dict[str, str] = {
    "Elite": "green",
    "High": "blue",
    "Medium": "yellow",
    "Low": "red",
}


@click.group()
@click.version_option(package_name="shipcadence")
def cli() -> None:
    """ShipCadence -- Lightweight DORA metrics for dev teams."""


@cli.command()
@click.argument("repo")
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    required=True,
    help="GitHub personal access token",
)
@click.option(
    "--days",
    default=90,
    show_default=True,
    help="Analysis window in days",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output raw JSON instead of a table",
)
def analyze(repo: str, token: str, days: int, output_json: bool) -> None:
    """Analyze DORA metrics for a GitHub repository (owner/repo)."""
    try:
        cfg = RepoConfig.from_slug(repo, token, days=days)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    from shipcadence.pipelines.collect import run_analysis

    with console.status("[bold green]Collecting data from GitHub..."):
        report = run_analysis(owner=cfg.owner, repo=cfg.repo, token=cfg.token, days=cfg.days)

    if output_json:
        from shipcadence.report import to_json

        console.print_json(to_json(report["metrics"]))
    else:
        _render_table(report)


def _render_table(report: dict[str, Any]) -> None:
    """Render the DORA report as a Rich table."""
    table = Table(title="DORA Metrics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Rating", justify="center")

    for row in report["rows"]:
        colour = _RATING_COLOURS.get(row["rating"], "white")
        table.add_row(
            row["metric"],
            row["value"],
            f"[{colour}]{row['rating']}[/{colour}]",
        )

    console.print(table)

    s = report["summary"]
    console.print(
        f"\n[dim]Period: {s['period_days']}d | "
        f"{s['total_deploys']} deploys | "
        f"{s['total_prs']} PRs | "
        f"{s['total_incidents']} incidents[/dim]"
    )
