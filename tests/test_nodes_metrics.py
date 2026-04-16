"""Tests for DORA metrics computation."""

from __future__ import annotations

from datetime import UTC

from shipcadence.models import Incident, NormalizedData
from shipcadence.nodes.metrics import (
    change_failure_rate,
    compute_metrics,
    deployment_frequency,
    lead_time,
    mttr,
    rate_cfr,
    rate_df,
    rate_lt,
    rate_mttr,
)

# ---------------------------------------------------------------------------
# deployment_frequency
# ---------------------------------------------------------------------------


def test_deployment_frequency_math(sample_deployments) -> None:
    per_day, per_week = deployment_frequency(sample_deployments, period_days=30)
    assert abs(per_day - 2 / 30) < 1e-6
    assert abs(per_week - per_day * 7) < 1e-6


def test_deployment_frequency_empty() -> None:
    assert deployment_frequency((), 90) == (0.0, 0.0)


def test_deployment_frequency_zero_days() -> None:
    assert deployment_frequency((), 0) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# lead_time
# ---------------------------------------------------------------------------


def test_lead_time_with_matches(sample_normalized_data: NormalizedData) -> None:
    med, p95 = lead_time(sample_normalized_data)
    # Both PRs have matched deployments ~2h after merge
    assert med > 0
    assert p95 >= med


def test_lead_time_no_matches() -> None:
    empty = NormalizedData(
        pulls=(), deployments=(), incidents=(), pr_deploy_map={}, period_days=90
    )
    assert lead_time(empty) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# change_failure_rate
# ---------------------------------------------------------------------------


def test_cfr_with_incident_after_deploy(sample_deployments, sample_incidents) -> None:
    cfr = change_failure_rate(sample_deployments, sample_incidents)
    # Incident #99 created ~3h after deployment 1001 → counted as failure
    assert 0.0 < cfr <= 1.0


def test_cfr_no_deployments() -> None:
    assert change_failure_rate((), ()) == 0.0


# ---------------------------------------------------------------------------
# mttr
# ---------------------------------------------------------------------------


def test_mttr_closed_incidents(sample_incidents) -> None:
    med, p95 = mttr(sample_incidents)
    # Only incident #99 is closed (3h restore time)
    assert med > 0
    assert p95 >= med


def test_mttr_no_closed_incidents() -> None:
    from datetime import datetime

    open_inc = Incident(
        number=1,
        title="open",
        created_at=datetime.now(UTC),
        closed_at=None,
        labels=("incident",),
    )
    assert mttr((open_inc,)) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# DORA ratings
# ---------------------------------------------------------------------------


def test_rate_df() -> None:
    assert rate_df(2.0) == "Elite"
    assert rate_df(0.5) == "High"
    assert rate_df(0.05) == "Medium"
    assert rate_df(0.01) == "Low"


def test_rate_lt() -> None:
    assert rate_lt(12) == "Elite"
    assert rate_lt(100) == "High"
    assert rate_lt(500) == "Medium"
    assert rate_lt(1000) == "Low"


def test_rate_cfr() -> None:
    assert rate_cfr(0.03) == "Elite"
    assert rate_cfr(0.08) == "High"
    assert rate_cfr(0.12) == "Medium"
    assert rate_cfr(0.20) == "Low"


def test_rate_mttr() -> None:
    assert rate_mttr(0.5) == "Elite"
    assert rate_mttr(12) == "High"
    assert rate_mttr(100) == "Medium"
    assert rate_mttr(200) == "Low"


# ---------------------------------------------------------------------------
# compute_metrics (integration)
# ---------------------------------------------------------------------------


def test_compute_metrics_full(sample_normalized_data: NormalizedData) -> None:
    result = compute_metrics(sample_normalized_data)
    assert result.total_deploys == 2
    assert result.total_prs == 2
    assert result.total_incidents == 2
    assert result.period_days == 90
    assert result.df_rating in {"Elite", "High", "Medium", "Low"}
    assert result.lt_rating in {"Elite", "High", "Medium", "Low"}


def test_compute_metrics_empty() -> None:
    empty = NormalizedData(
        pulls=(), deployments=(), incidents=(), pr_deploy_map={}, period_days=90
    )
    result = compute_metrics(empty)
    assert result.deployment_frequency == 0.0
    assert result.change_failure_rate == 0.0
    assert result.mttr_median_hours == 0.0
    assert result.lead_time_median_hours == 0.0
