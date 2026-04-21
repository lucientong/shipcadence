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


def _resolve_token(token: str | None) -> str:
    """Resolve the GitHub token: CLI flag > env var > SecretStore."""
    if token:
        return token

    from shipcadence.secrets import get_token

    stored = get_token()
    if stored:
        return stored

    raise click.UsageError(
        "GitHub token required.  Provide --token, set GITHUB_TOKEN, "
        "or run: shipcadence config set-token"
    )


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="shipcadence")
def cli() -> None:
    """ShipCadence -- Lightweight DORA metrics for dev teams."""


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    default=None,
    help="GitHub personal access token (or set GITHUB_TOKEN / use `config set-token`)",
)
@click.option(
    "--days",
    default=90,
    show_default=True,
    help="Analysis window in days",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.option(
    "--compare",
    is_flag=True,
    default=False,
    help="Compare current period with previous period",
)
def analyze(
    repos: tuple[str, ...],
    token: str | None,
    days: int,
    output_format: str,
    compare: bool,
) -> None:
    """Analyze DORA metrics for one or more GitHub repositories (owner/repo).

    Examples:

        shipcadence analyze acme/api

        shipcadence analyze acme/api acme/web acme/worker
    """
    resolved_token = _resolve_token(token)

    from shipcadence.pipelines.collect import run_analysis

    configs: list[RepoConfig] = []
    for slug in repos:
        try:
            configs.append(RepoConfig.from_slug(slug, resolved_token, days=days))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    # Collect current period for all repos.
    reports: dict[str, dict[str, Any]] = {}
    with console.status("[bold green]Collecting data from GitHub..."):
        for cfg in configs:
            slug = f"{cfg.owner}/{cfg.repo}"
            reports[slug] = run_analysis(
                owner=cfg.owner, repo=cfg.repo, token=cfg.token, days=cfg.days
            )

    # Optional: collect previous period for comparison.
    prev_reports: dict[str, dict[str, Any]] = {}
    if compare:
        with console.status("[bold green]Collecting previous period for comparison..."):
            for cfg in configs:
                slug = f"{cfg.owner}/{cfg.repo}"
                prev_reports[slug] = run_analysis(
                    owner=cfg.owner,
                    repo=cfg.repo,
                    token=cfg.token,
                    days=cfg.days * 2,  # fetch wider window, metrics node uses period_days
                )

    # Render output.
    if output_format == "json":
        import json

        from shipcadence.report import to_json

        if len(reports) == 1:
            report = next(iter(reports.values()))
            console.print_json(to_json(report["metrics"]))
        else:
            combined = {slug: to_json(r["metrics"]) for slug, r in reports.items()}
            console.print_json(json.dumps(combined, indent=2))
    elif output_format == "markdown":
        from shipcadence.report import to_markdown

        for slug, report in reports.items():
            if len(reports) > 1:
                click.echo(f"\n## {slug}\n")
            click.echo(to_markdown(report))
    else:
        if len(reports) == 1:
            slug, report = next(iter(reports.items()))
            if compare and slug in prev_reports:
                _render_comparison_table(slug, report, prev_reports[slug])
            else:
                _render_table(report)
        else:
            _render_multi_repo_table(reports, prev_reports if compare else None)


# ---------------------------------------------------------------------------
# config group
# ---------------------------------------------------------------------------


@cli.group()
def config() -> None:
    """Manage ShipCadence configuration."""


@config.command("set-token")
@click.argument("token")
def config_set_token(token: str) -> None:
    """Encrypt and store a GitHub personal access token."""
    from shipcadence.secrets import save_token

    save_token(token)
    console.print("[green]Token saved successfully.[/green]")


@config.command("show-token")
def config_show_token() -> None:
    """Show the stored GitHub token (masked)."""
    from shipcadence.secrets import get_token

    stored = get_token()
    if stored:
        masked = stored[:4] + "*" * (len(stored) - 8) + stored[-4:]
        console.print(f"Stored token: {masked}")
    else:
        console.print(
            "[yellow]No token stored. Use: shipcadence config set-token <token>[/yellow]"
        )


@config.command("delete-token")
def config_delete_token() -> None:
    """Delete the stored GitHub token."""
    from shipcadence.secrets import delete_token

    if delete_token():
        console.print("[green]Token deleted.[/green]")
    else:
        console.print("[yellow]No token was stored.[/yellow]")


# ---------------------------------------------------------------------------
# watch (scheduled collection)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("repo")
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    default=None,
    help="GitHub personal access token",
)
@click.option(
    "--days",
    default=90,
    show_default=True,
    help="Analysis window in days",
)
@click.option(
    "--schedule",
    default="0 2 * * *",
    show_default=True,
    help="Cron expression for collection schedule",
)
@click.option(
    "--webhook",
    default=None,
    help="Webhook URL for alert notifications",
)
def watch(
    repo: str,
    token: str | None,
    days: int,
    schedule: str,
    webhook: str | None,
) -> None:
    """Run DORA metrics on a schedule (e.g. daily at 2am).

    Uses Dagloom's SchedulerService to register the pipeline for
    repeated execution.  Press Ctrl+C to stop.
    """
    import asyncio

    resolved_token = _resolve_token(token)

    try:
        cfg = RepoConfig.from_slug(repo, resolved_token, days=days)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    async def _run_watch() -> None:
        from dagloom import SchedulerService
        from dagloom.store.db import Database

        from shipcadence.pipelines.alert import build_alert_pipeline

        db = Database()
        await db.connect()

        try:
            scheduler = SchedulerService(db)
            await scheduler.start()

            pipeline = build_alert_pipeline(webhook_url=webhook)
            schedule_id = await scheduler.register(
                pipeline=pipeline,
                cron_expr=schedule,
            )
            console.print(
                f"[green]Watching[/green] [bold]{repo}[/bold] "
                f"on schedule [cyan]{schedule}[/cyan] "
                f"(id: {schedule_id})"
            )
            if webhook:
                console.print(f"[dim]Alerts will be sent to {webhook}[/dim]")
            console.print("[dim]Press Ctrl+C to stop.[/dim]")

            # Run the pipeline once immediately for feedback.
            from shipcadence.pipelines.collect import run_analysis

            with console.status("[bold green]Running initial collection..."):
                report = run_analysis(
                    owner=cfg.owner, repo=cfg.repo, token=cfg.token, days=cfg.days
                )
            _render_table(report)

            # Block until interrupted.
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping watcher...[/yellow]")
        finally:
            await scheduler.stop()
            await db.close()

    asyncio.run(_run_watch())


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


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


def _delta_str(current: float, previous: float, lower_is_better: bool = False) -> str:
    """Format a delta value with arrow indicator."""
    if previous == 0:
        return ""
    diff = current - previous
    if abs(diff) < 0.01:
        return " [dim]=[/dim]"
    improved = diff < 0 if lower_is_better else diff > 0
    arrow = "[green]\u2191[/green]" if improved else "[red]\u2193[/red]"
    return f" {arrow}"


def _render_comparison_table(
    slug: str,
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    """Render a single-repo comparison table (current vs previous period)."""
    cur_m = current["metrics"]
    prev_m = previous["metrics"]

    table = Table(
        title=f"DORA Metrics — {slug}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="bold")
    table.add_column("Current", justify="right")
    table.add_column("Previous", justify="right")
    table.add_column("Trend", justify="center")

    rows = [
        (
            "Deploy Frequency",
            f"{cur_m.deployment_frequency_weekly:.1f}/wk",
            f"{prev_m.deployment_frequency_weekly:.1f}/wk",
            _delta_str(cur_m.deployment_frequency_weekly, prev_m.deployment_frequency_weekly),
        ),
        (
            "Lead Time",
            f"{cur_m.lead_time_median_hours:.1f}h",
            f"{prev_m.lead_time_median_hours:.1f}h",
            _delta_str(
                cur_m.lead_time_median_hours,
                prev_m.lead_time_median_hours,
                lower_is_better=True,
            ),
        ),
        (
            "Change Failure Rate",
            f"{cur_m.change_failure_rate:.1%}",
            f"{prev_m.change_failure_rate:.1%}",
            _delta_str(
                cur_m.change_failure_rate,
                prev_m.change_failure_rate,
                lower_is_better=True,
            ),
        ),
        (
            "MTTR",
            f"{cur_m.mttr_median_hours:.1f}h",
            f"{prev_m.mttr_median_hours:.1f}h",
            _delta_str(cur_m.mttr_median_hours, prev_m.mttr_median_hours, lower_is_better=True),
        ),
    ]

    for metric, cur_val, prev_val, trend in rows:
        table.add_row(metric, cur_val, prev_val, trend)

    console.print(table)


def _render_multi_repo_table(
    reports: dict[str, dict[str, Any]],
    prev_reports: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Render a multi-repo comparison table."""
    table = Table(
        title="DORA Metrics — Multi-Repo",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Repository", style="bold")
    table.add_column("DF (/wk)", justify="right")
    table.add_column("LT (h)", justify="right")
    table.add_column("CFR", justify="right")
    table.add_column("MTTR (h)", justify="right")
    table.add_column("Rating", justify="center")

    for slug, report in reports.items():
        m = report["metrics"]
        # Overall rating = worst of the four
        ratings = [m.df_rating, m.lt_rating, m.cfr_rating, m.mttr_rating]
        rank = {"Elite": 0, "High": 1, "Medium": 2, "Low": 3}
        worst = max(ratings, key=lambda r: rank.get(r, 4))
        colour = _RATING_COLOURS.get(worst, "white")

        trend = ""
        if prev_reports and slug in prev_reports:
            pm = prev_reports[slug]["metrics"]
            trend = _delta_str(m.deployment_frequency_weekly, pm.deployment_frequency_weekly)

        table.add_row(
            slug,
            f"{m.deployment_frequency_weekly:.1f}{trend}",
            f"{m.lead_time_median_hours:.1f}",
            f"{m.change_failure_rate:.1%}",
            f"{m.mttr_median_hours:.1f}",
            f"[{colour}]{worst}[/{colour}]",
        )

    console.print(table)
