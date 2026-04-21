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


# ---------------------------------------------------------------------------
# analyze command — single repo
# ---------------------------------------------------------------------------


def test_analyze_table_output() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(cli, ["analyze", "acme/app", "--token", "fake"])
    assert result.exit_code == 0
    assert "Deployment Frequency" in result.output


def test_analyze_json_output() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(cli, ["analyze", "acme/app", "--token", "fake", "--format", "json"])
    assert result.exit_code == 0
    assert "deployment_frequency" in result.output


def test_analyze_markdown_output() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(
            cli, ["analyze", "acme/app", "--token", "fake", "--format", "markdown"]
        )
    assert result.exit_code == 0
    assert "| Deployment Frequency" in result.output


def test_analyze_bad_repo_format() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "noslash", "--token", "fake"])
    assert result.exit_code != 0


def test_analyze_no_token_no_store() -> None:
    """Missing token with no stored token should fail gracefully."""
    runner = CliRunner(env={"GITHUB_TOKEN": ""})
    with patch("shipcadence.secrets.get_token", return_value=None):
        result = runner.invoke(cli, ["analyze", "acme/app"])
    assert result.exit_code != 0
    assert "token" in result.output.lower()


def test_analyze_uses_stored_token() -> None:
    """When --token is omitted, should fall back to SecretStore."""
    runner = CliRunner(env={"GITHUB_TOKEN": ""})
    with (
        patch("shipcadence.secrets.get_token", return_value="ghp_stored_token"),
        patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()),
    ):
        result = runner.invoke(cli, ["analyze", "acme/app"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# analyze command — multi-repo
# ---------------------------------------------------------------------------


def test_analyze_multi_repo() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(cli, ["analyze", "acme/api", "acme/web", "--token", "fake"])
    assert result.exit_code == 0
    assert "Multi-Repo" in result.output


# ---------------------------------------------------------------------------
# analyze command — compare
# ---------------------------------------------------------------------------


def test_analyze_compare() -> None:
    runner = CliRunner()
    with patch("shipcadence.pipelines.collect.run_analysis", return_value=_fake_report()):
        result = runner.invoke(cli, ["analyze", "acme/app", "--token", "fake", "--compare"])
    assert result.exit_code == 0
    assert "Current" in result.output
    assert "Previous" in result.output


# ---------------------------------------------------------------------------
# config commands
# ---------------------------------------------------------------------------


def test_config_set_token() -> None:
    runner = CliRunner()
    with patch("shipcadence.secrets.save_token") as mock_save:
        result = runner.invoke(cli, ["config", "set-token", "ghp_test123"])
    assert result.exit_code == 0
    assert "saved" in result.output.lower()
    mock_save.assert_called_once_with("ghp_test123")


def test_config_show_token_present() -> None:
    runner = CliRunner()
    with patch("shipcadence.secrets.get_token", return_value="ghp_abcdefghijklmno"):
        result = runner.invoke(cli, ["config", "show-token"])
    assert result.exit_code == 0
    assert "ghp_" in result.output
    assert "ghp_abcdefghijklmno" not in result.output  # masked


def test_config_show_token_absent() -> None:
    runner = CliRunner()
    with patch("shipcadence.secrets.get_token", return_value=None):
        result = runner.invoke(cli, ["config", "show-token"])
    assert result.exit_code == 0
    assert "No token" in result.output


def test_config_delete_token() -> None:
    runner = CliRunner()
    with patch("shipcadence.secrets.delete_token", return_value=True):
        result = runner.invoke(cli, ["config", "delete-token"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
