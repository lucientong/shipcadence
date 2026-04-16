"""Tests for the CLI."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from shipcadence.cli import cli
from shipcadence.models import DORAMetrics


def _fake_report() -> dict:
    metrics = DORAMetrics(
        deployment_frequency=1.0,
        deployment_frequency_weekly=7.0,
        lead_time_median_hours=12.0,
        lead_time_p95_hours=48.0,
        change_failure_rate=0.05,
        mttr_median_hours=2.0,
        mttr_p95_hours=8.0,
        period_days=90,
        total_deploys=90,
        total_prs=120,
        total_incidents=5,
        df_rating="Elite",
        lt_rating="Elite",
        cfr_rating="Elite",
        mttr_rating="High",
    )
    return {
        "metrics": metrics,
        "rows": [
            {"metric": "Deployment Frequency", "value": "7.0 / week", "rating": "Elite"},
            {"metric": "Lead Time for Changes", "value": "12.0h (p50)", "rating": "Elite"},
            {"metric": "Change Failure Rate", "value": "5.0%", "rating": "Elite"},
            {"metric": "Mean Time to Restore", "value": "2.0h (p50)", "rating": "High"},
        ],
        "summary": {
            "period_days": 90,
            "total_deploys": 90,
            "total_prs": 120,
            "total_incidents": 5,
        },
    }


def test_analyze_command() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(cli, ["analyze", "acme/app", "--token", "fake"])
    assert result.exit_code == 0
    assert "Deployment Frequency" in result.output


def test_analyze_bad_repo_format() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "noslash", "--token", "fake"])
    assert result.exit_code != 0


def test_analyze_missing_token() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "acme/app"])
    assert result.exit_code != 0


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
